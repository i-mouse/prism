"""LLM-as-judge matcher for the eval harness.

Pairs each expected row (from docs/evals/matrix_eval.json) with the
semantically-closest actual claim emitted by the extraction engine, or
None if no actual claim describes the same assertion. One Gemini call
per paper - all expected + actual claims go in a single prompt, not
one call per pair, to stay inside the Flash Lite daily quota.

Reuses the retry/backoff/fallback pattern from extraction/engine.py's
_call_gemini_structured, adapted for a list[Match] response schema.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import TypeAdapter

from eval.types import ActualClaim, ExpectedRow, Match

LOGS_DIR = Path(__file__).parent.parent / "logs" / "matcher"

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1, 2, 4)
DEFAULT_MODEL = "gemini-3.1-flash-lite"

_MATCH_LIST_ADAPTER = TypeAdapter(list[Match])

_SYSTEM_PROMPT = (
    "You are a matcher. Given a list of expected claim summaries and a "
    "list of actual extracted claim summaries from the same research "
    "paper, return a Match record for each expected claim identifying "
    "the semantically-closest actual claim (by index), or "
    "actual_index=null if no actual claim describes the same assertion. "
    "Two claims match if they describe the same underlying assertion, "
    "even when worded differently. Return exactly one Match per expected "
    "claim, using its expected_id."
)


def _is_retryable(exc: Exception) -> bool:
    """Returns True for rate limits, server errors, timeouts, and connection drops."""
    if isinstance(exc, errors.APIError):
        return exc.code in RETRYABLE_STATUS_CODES
    return isinstance(exc, (TimeoutError, ConnectionError, asyncio.TimeoutError))


def _build_user_content(expected_rows: list[ExpectedRow], actual_claims: list[ActualClaim]) -> str:
    payload = {
        "expected_rows": [
            {"id": row.id, "claim_summary": row.claim_summary} for row in expected_rows
        ],
        "actual_claims": [
            {"index": claim.index, "claim_summary": claim.claim_summary}
            for claim in actual_claims
        ],
    }
    return json.dumps(payload, indent=2)


def _write_matcher_log(
    paper_id: str,
    model_used: str,
    expected_row_count: int,
    response_match_count: int,
    response_raw: str,
) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename_ts = now.strftime("%Y%m%dT%H%M%S%f")
    log_path = LOGS_DIR / f"{filename_ts}_{paper_id}.json"

    log_entry = {
        "timestamp": now.isoformat(),
        "paper_id": paper_id,
        "model_used": model_used,
        "expected_row_count": expected_row_count,
        "response_match_count": response_match_count,
        "response_raw": response_raw,
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


async def _call_gemini(
    client: genai.Client,
    model: str,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
    paper_id: str,
) -> types.GenerateContentResponse:
    """Calls Gemini with retry/backoff, raising the last error if all attempts fail."""
    last_exception: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"[matcher] paper_id={paper_id} model={model} attempt={attempt}/{MAX_ATTEMPTS}")
            return await client.aio.models.generate_content(model=model, contents=contents, config=config)
        except Exception as exc:
            if not _is_retryable(exc):
                print(f"[matcher] paper_id={paper_id} model={model} non-retryable error: {exc!r}")
                raise
            last_exception = exc
            print(f"[matcher] paper_id={paper_id} model={model} attempt={attempt}/{MAX_ATTEMPTS} failed: {exc!r}")
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])

    assert last_exception is not None
    raise last_exception


async def match(
    paper_id: str,
    expected_rows: list[ExpectedRow],
    actual_claims: list[ActualClaim],
) -> list[Match]:
    """LLM-as-judge matcher. One call per paper.

    Returns exactly len(expected_rows) Match objects - one per expected
    row, with actual_index = None if no matching actual claim.
    """
    model_name = os.getenv("LLM_AUDIT_MODEL", DEFAULT_MODEL)
    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        raise RuntimeError("AI_API_KEY environment variable is not set")

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=_build_user_content(expected_rows, actual_claims))],
        )
    ]
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        temperature=0,
        response_mime_type="application/json",
        response_schema=list[Match],
    )

    used_model = model_name
    try:
        response = await _call_gemini(client, model_name, contents, config, paper_id)
    except Exception as primary_exc:
        if not _is_retryable(primary_exc):
            raise
        fallback_model = os.getenv("LLM_EXTRACTION_MODEL")
        if not fallback_model:
            raise RuntimeError(
                f"Gemini call failed after {MAX_ATTEMPTS} attempts on model={model_name} "
                f"(paper_id={paper_id}) and LLM_EXTRACTION_MODEL is not set for fallback"
            ) from primary_exc
        used_model = fallback_model
        try:
            print(f"[matcher] paper_id={paper_id} falling back to model={fallback_model}")
            response = await client.aio.models.generate_content(model=fallback_model, contents=contents, config=config)
        except Exception as fallback_exc:
            print(f"[matcher] paper_id={paper_id} fallback model={fallback_model} failed: {fallback_exc!r}")
            raise RuntimeError(
                f"Gemini call failed after {MAX_ATTEMPTS} attempts on model={model_name} "
                f"and fallback attempt on model={fallback_model} (paper_id={paper_id})"
            ) from fallback_exc

    raw_text = response.text

    parsed = response.parsed
    if parsed is None:
        try:
            parsed = _MATCH_LIST_ADAPTER.validate_python(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError) as parse_exc:
            print(f"[matcher] paper_id={paper_id} malformed response, raw={raw_text!r}")
            _write_matcher_log(
                paper_id=paper_id,
                model_used=used_model,
                expected_row_count=len(expected_rows),
                response_match_count=0,
                response_raw=raw_text,
            )
            raise ValueError(
                f"Gemini response for paper_id={paper_id} was neither parsed by the SDK nor valid JSON: {parse_exc}"
            ) from parse_exc

    _write_matcher_log(
        paper_id=paper_id,
        model_used=used_model,
        expected_row_count=len(expected_rows),
        response_match_count=len(parsed),
        response_raw=raw_text,
    )

    match_by_expected_id = {m.expected_id: m for m in parsed}
    return [
        match_by_expected_id.get(row.id, Match(expected_id=row.id, actual_index=None))
        for row in expected_rows
    ]
