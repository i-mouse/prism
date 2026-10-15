"""Calls Gemini to extract structured data from paper text.

Builds messages via prompt_loader, translates them into the google-genai
SDK's system_instruction/contents format, and enforces a Pydantic schema
via structured output. No grounding logic, no DB writes - downstream
stages (grounding, DB write) consume this module's output.

extract_metadata (Prompt 1) is a single structured-output call.

extract_claims (Prompt 2) is a sequential three-call pipeline:
  - Call #2, extractor: claim_text_verbatim + claim_summary only, no labels.
  - Call #3, auditor (per claim, concurrent): free-text reasoning ending in
    a VERDICT: line and QUOTE:/SECTION: pairs. No schema - the label isn't
    committed until reasoning is done.
  - Call #4, structurer (per claim, after its audit): turns the audit's
    free text into a ClaimLLM JSON object. This is the only call in the
    claims pipeline that uses response_schema.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

from google import genai
from google.genai import errors, types
from opentelemetry import trace
from pydantic import BaseModel

from config import settings
from extraction.prompt_loader import (
    build_gemini_messages_for_audit,
    build_gemini_messages_for_extractor,
    build_gemini_messages_for_metadata,
    build_gemini_messages_for_structure,
)
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLLM, ClaimsExtractionResponse, MetadataExtractionResponse

tracer = trace.get_tracer(__name__)

AUDIT_STRUCTURE_CONCURRENCY = 5

LOGS_DIR = Path(__file__).parent.parent / "logs"

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1, 2, 4)


def _is_retryable(exc: Exception) -> bool:
    """Returns True for rate limits, server errors, timeouts, and connection drops.

    The `except Exception` blocks around retry loops in this module never see a
    client-disconnect cancellation: asyncio.CancelledError is a BaseException,
    not an Exception, in Python >=3.8, so it always propagates past them.
    """
    if isinstance(exc, errors.APIError):
        return exc.code in RETRYABLE_STATUS_CODES
    return isinstance(exc, (TimeoutError, ConnectionError, asyncio.TimeoutError))


def _to_gemini_contents(messages: list[dict]) -> list[types.Content]:
    return [
        types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["content"])])
        for msg in messages
        if msg["role"] != "system"
    ]


def _extract_system_prompt(messages: list[dict]) -> str:
    for msg in messages:
        if msg["role"] == "system":
            return msg["content"]
    raise ValueError("Message list did not contain a system message")


async def _call_gemini(
    client: genai.Client,
    model: str,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
    chat_id: str,
    correlation_id: str | None = None,
) -> types.GenerateContentResponse:
    """Calls Gemini with retry/backoff, raising the last error if all attempts fail."""
    last_exception: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} model={model} attempt={attempt}/{MAX_ATTEMPTS}")
            return await client.aio.models.generate_content(model=model, contents=contents, config=config)
        except Exception as exc:
            if not _is_retryable(exc):
                print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} model={model} non-retryable error: {exc!r}")
                raise
            last_exception = exc
            print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} model={model} attempt={attempt}/{MAX_ATTEMPTS} failed: {exc!r}")
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])

    assert last_exception is not None
    raise last_exception


def _extract_usage_and_finish_reason(
    response: types.GenerateContentResponse,
) -> tuple[dict | None, str | None]:
    """Reads token-usage and finish-reason metadata off a Gemini response, for
    logging only - this data is never fed back into a function's return value
    or any pipeline decision (side-channel only). Every attribute access is
    guarded since usage_metadata/candidates can be absent or shaped
    unexpectedly depending on SDK version or a malformed response.
    """
    usage_obj = getattr(response, "usage_metadata", None)
    usage = None
    if usage_obj is not None:
        usage = {
            "prompt_tokens": getattr(usage_obj, "prompt_token_count", None),
            "output_tokens": getattr(usage_obj, "candidates_token_count", None),
            "thought_tokens": getattr(usage_obj, "thoughts_token_count", None),
            "total_tokens": getattr(usage_obj, "total_token_count", None),
        }

    finish_reason = None
    candidates = getattr(response, "candidates", None)
    if candidates:
        raw_finish_reason = getattr(candidates[0], "finish_reason", None)
        if raw_finish_reason is not None:
            finish_reason = getattr(raw_finish_reason, "value", None) or str(raw_finish_reason)

    return usage, finish_reason


def _write_structured_log(
    log_subdir: str,
    chat_id: str,
    correlation_id: str | None,
    model_used: str,
    request_message_count: int,
    response_item_count: int,
    response_raw: str,
    usage: dict | None = None,
    finish_reason: str | None = None,
) -> None:
    log_dir = LOGS_DIR / log_subdir
    log_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename_ts = now.strftime("%Y%m%dT%H%M%S%f")
    log_path = log_dir / f"{filename_ts}_{chat_id}_{correlation_id or 'none'}.json"

    log_entry = {
        "timestamp": now.isoformat(),
        "chat_id": chat_id,
        "correlation_id": correlation_id,
        "prompt_version": get_prompt_version(),
        "model_used": model_used,
        "request_message_count": request_message_count,
        "response_item_count": response_item_count,
        "response_raw": response_raw,
        "usage": usage,
        "finish_reason": finish_reason,
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


def _build_client() -> genai.Client:
    return genai.Client(api_key=settings.ai_api_key)


async def _generate_with_fallback(
    client: genai.Client,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
    chat_id: str,
    model_name: str,
    fallback_model: str,
    correlation_id: str | None = None,
    fallback_config: types.GenerateContentConfig | None = None,
) -> tuple[types.GenerateContentResponse, str]:
    """Calls Gemini on model_name with retry/backoff, falling back to
    fallback_model for one final attempt if the primary model's retries are
    exhausted. Returns (response, model_name_actually_used). Raises on
    terminal failure (non-retryable error, or fallback attempt also fails).

    fallback_config, when given, is used for the fallback attempt instead of
    config - callers that build a primary config with a thinking_config pass
    a separate fallback_config without one, so a thinking_level override
    never reaches the fallback model (Experiment 3 amendment 1: thinking
    overrides are a primary-model-only knob). Defaults to reusing config,
    unchanged from before this parameter existed.
    """
    fallback_config = fallback_config if fallback_config is not None else config
    try:
        response = await _call_gemini(client, model_name, contents, config, chat_id, correlation_id)
        return response, model_name
    except Exception as primary_exc:
        if not _is_retryable(primary_exc):
            raise
        try:
            print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} falling back to model={fallback_model}")
            response = await client.aio.models.generate_content(model=fallback_model, contents=contents, config=fallback_config)
            return response, fallback_model
        except Exception as fallback_exc:
            print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} fallback model={fallback_model} failed: {fallback_exc!r}")
            raise RuntimeError(
                f"Gemini call failed after {MAX_ATTEMPTS} attempts on model={model_name} "
                f"and fallback attempt on model={fallback_model} (chat_id={chat_id})"
            ) from fallback_exc


async def _call_gemini_structured(
    messages: list[dict],
    response_schema: type[BaseModel],
    chat_id: str,
    correlation_id: str | None,
    log_subdir: str,
    model_name: str,
    fallback_model: str,
    thinking_level: str | None = None,
) -> BaseModel:
    """Calls Gemini with a schema-enforced structured output config.

    Retries transient failures (429/5xx/timeout/connection) up to 3 times with
    exponential backoff, then falls back to fallback_model for one final
    attempt before raising the last error. Falls back to json.loads/model_validate
    when response.parsed is None. Logs the request/response to
    logs/{log_subdir}/{timestamp}_{chat_id}_{correlation_id}.json.

    thinking_level is None by default, which sends no thinking_config at all -
    byte-identical to this call's behavior before this parameter existed
    (API default, medium on 3.6-flash). When set, it is applied to the
    PRIMARY model only: the fallback attempt (inside _generate_with_fallback)
    gets its own config without a thinking_config, via fallback_config below -
    see docs/decisions.md, "Experiment 3 amendment 1 - 2026-10-15".
    """
    client = _build_client()
    system_prompt = _extract_system_prompt(messages)
    contents = _to_gemini_contents(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema,
        thinking_config=(
            types.ThinkingConfig(thinking_level=types.ThinkingLevel(thinking_level.upper()))
            if thinking_level is not None
            else None
        ),
    )
    fallback_config = (
        types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        if thinking_level is not None
        else None
    )

    # fallback_config is only passed through when thinking_level is set - every
    # existing caller (thinking_level=None, the overwhelming default) calls
    # _generate_with_fallback with the exact same positional args as before
    # this parameter existed, so any code that monkey-patches
    # _generate_with_fallback with the old signature (eval/replay_audit.py,
    # eval/replay_extract.py - neither ever sets thinking_level on a
    # _call_gemini_structured call) keeps working unchanged.
    extra_kwargs = {"fallback_config": fallback_config} if thinking_level is not None else {}
    response, used_model = await _generate_with_fallback(
        client, contents, config, chat_id, model_name, fallback_model, correlation_id, **extra_kwargs,
    )
    raw_text = response.text
    usage, finish_reason = _extract_usage_and_finish_reason(response)

    parsed = response.parsed
    if parsed is None:
        try:
            parsed = response_schema.model_validate(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError) as parse_exc:
            print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} malformed response, raw={raw_text!r}")
            _write_structured_log(
                log_subdir=log_subdir,
                chat_id=chat_id,
                correlation_id=correlation_id,
                model_used=used_model,
                request_message_count=len(messages),
                response_item_count=0,
                response_raw=raw_text,
                usage=usage,
                finish_reason=finish_reason,
            )
            raise ValueError(
                f"Gemini response for chat_id={chat_id} was neither parsed by the SDK nor valid JSON: {parse_exc}"
            ) from parse_exc

    if hasattr(parsed, "claims"):
        item_count = len(parsed.claims)
    elif hasattr(parsed, "sentences"):  # pass-2's SentenceListLLM
        item_count = len(parsed.sentences)
    elif hasattr(parsed, "metadata"):
        item_count = 1
    else:
        item_count = 0
    _write_structured_log(
        log_subdir=log_subdir,
        chat_id=chat_id,
        correlation_id=correlation_id,
        model_used=used_model,
        request_message_count=len(messages),
        response_item_count=item_count,
        response_raw=raw_text,
        usage=usage,
        finish_reason=finish_reason,
    )

    return parsed


async def _call_gemini_json(
    messages: list[dict],
    chat_id: str,
    correlation_id: str | None,
    log_subdir: str,
    model_name: str,
    fallback_model: str,
) -> dict:
    """Calls Gemini in JSON mode without a response_schema, parsing response.text
    as JSON. Same retry/backoff/fallback-model behavior as _call_gemini_structured,
    used for the extractor call where no schema should bias field ordering.
    Logs the request/response to logs/{log_subdir}/{timestamp}_{chat_id}_{correlation_id}.json.
    """
    client = _build_client()
    system_prompt = _extract_system_prompt(messages)
    contents = _to_gemini_contents(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
    )

    response, used_model = await _generate_with_fallback(
        client, contents, config, chat_id, model_name, fallback_model, correlation_id
    )
    raw_text = response.text
    usage, finish_reason = _extract_usage_and_finish_reason(response)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as parse_exc:
        print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} malformed JSON response, raw={raw_text!r}")
        _write_structured_log(
            log_subdir=log_subdir,
            chat_id=chat_id,
            correlation_id=correlation_id,
            model_used=used_model,
            request_message_count=len(messages),
            response_item_count=0,
            response_raw=raw_text,
            usage=usage,
            finish_reason=finish_reason,
        )
        raise ValueError(f"Gemini response for chat_id={chat_id} was not valid JSON: {parse_exc}") from parse_exc

    item_count = len(parsed.get("claims", [])) if isinstance(parsed, dict) else 0
    _write_structured_log(
        log_subdir=log_subdir,
        chat_id=chat_id,
        correlation_id=correlation_id,
        model_used=used_model,
        request_message_count=len(messages),
        response_item_count=item_count,
        response_raw=raw_text,
        usage=usage,
        finish_reason=finish_reason,
    )

    return parsed


async def _call_gemini_freetext(
    messages: list[dict],
    chat_id: str,
    correlation_id: str | None,
    log_subdir: str,
    model_name: str,
    fallback_model: str,
    thinking_level: str | None = None,
) -> str:
    """Calls Gemini for plain free-text output - no JSON mode, no schema.

    Used for the auditor call: reasoning happens in prose first, so the
    label isn't committed to structure before the evidence is weighed.
    Same retry/backoff/fallback-model behavior as _call_gemini_structured.
    Logs the request/response to logs/{log_subdir}/{timestamp}_{chat_id}_{correlation_id}.json.

    thinking_level is None by default, which sends no thinking_config at all -
    byte-identical to this call's pre-Experiment-1 behavior (API default,
    medium on 3.6-flash). Passed explicitly by the caller (settings-driven in
    the live service, CLI-driven in eval/replay_audit.py) - never read from
    global settings in this function.
    """
    client = _build_client()
    system_prompt = _extract_system_prompt(messages)
    contents = _to_gemini_contents(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        thinking_config=(
            types.ThinkingConfig(thinking_level=types.ThinkingLevel(thinking_level.upper()))
            if thinking_level is not None
            else None
        ),
    )

    response, used_model = await _generate_with_fallback(
        client, contents, config, chat_id, model_name, fallback_model, correlation_id
    )
    raw_text = response.text

    _write_structured_log(
        log_subdir=log_subdir,
        chat_id=chat_id,
        correlation_id=correlation_id,
        model_used=used_model,
        request_message_count=len(messages),
        response_item_count=1,
        response_raw=raw_text,
    )

    return raw_text


async def _audit_and_structure_claim(
    semaphore: asyncio.Semaphore,
    paper_text: str,
    claim: dict,
    chat_id: str,
    correlation_id: str | None,
    claim_number: int,
    total_claims: int,
    on_detail: Optional[Callable[[str], Awaitable[None]]] = None,
    thinking_level: str | None = None,
) -> ClaimLLM:
    """Runs Call #3 (audit) then Call #4 (structure) for one claim, in sequence.

    Concurrency across claims is bounded by the shared semaphore. claim_number
    is the claim's fixed position in the extracted list (1-indexed), not a
    live completion count - claims run concurrently, so on_detail messages
    may not appear in strict claim_number order.

    thinking_level reaches only the audit call (Call #3) below, never the
    structure call (Call #4) - Experiment 1 varies the auditor alone.
    """
    claim_text_verbatim = claim["claim_text_verbatim"]
    claim_summary = claim["claim_summary"]

    async with semaphore:
        with tracer.start_as_current_span("auditor") as span:
            span.set_attribute("correlation_id", correlation_id or "")
            span.set_attribute("chat_id", chat_id)
            span.set_attribute("claim_number", claim_number)
            audit_text = await _call_gemini_freetext(
                messages=build_gemini_messages_for_audit(paper_text, claim_text_verbatim, claim_summary),
                chat_id=chat_id,
                correlation_id=correlation_id,
                log_subdir="audit",
                model_name=settings.llm_claim_audit_model,
                fallback_model=settings.llm_claim_audit_fallback_model,
                thinking_level=thinking_level,
            )

        with tracer.start_as_current_span("structurer") as span:
            span.set_attribute("correlation_id", correlation_id or "")
            span.set_attribute("chat_id", chat_id)
            span.set_attribute("claim_number", claim_number)
            structured = await _call_gemini_structured(
                messages=build_gemini_messages_for_structure(claim_text_verbatim, claim_summary, audit_text),
                response_schema=ClaimLLM,
                chat_id=chat_id,
                correlation_id=correlation_id,
                log_subdir="structure",
                model_name=settings.llm_claim_audit_model,
                fallback_model=settings.llm_claim_audit_fallback_model,
            )

    return structured


async def extract_claims(
    paper_text: str,
    chat_id: str,
    correlation_id: str | None = None,
    on_detail: Optional[Callable[[str], Awaitable[None]]] = None,
    on_audit_start: Optional[Callable[[], Awaitable[None]]] = None,
    on_audit_detail: Optional[Callable[[str], Awaitable[None]]] = None,
) -> ClaimsExtractionResponse:
    """Extracts structured claims from paper_text via a sequential three-call pipeline.

    Call #2 (extractor) runs once over the full paper. For each extracted
    claim, Call #3 (audit) and Call #4 (structure) run in sequence, fanned
    out across claims with a bounded semaphore. A claim whose audit or
    structure call fails is logged and dropped rather than failing the
    whole extraction - downstream grounding handles missing claims correctly.
    """
    with tracer.start_as_current_span("extractor") as span:
        span.set_attribute("correlation_id", correlation_id or "")
        span.set_attribute("chat_id", chat_id)
        extracted = await _call_gemini_json(
            messages=build_gemini_messages_for_extractor(paper_text),
            chat_id=chat_id,
            correlation_id=correlation_id,
            log_subdir="extraction",
            model_name=settings.llm_extraction_model,
            fallback_model=settings.llm_extraction_fallback_model,
        )
    claims = extracted.get("claims", [])

    if settings.extractor_second_pass:
        from extraction.merge import merge_pass2_claims
        from extraction.pass2 import run_pass2

        with tracer.start_as_current_span("pass2") as span:
            span.set_attribute("correlation_id", correlation_id or "")
            span.set_attribute("chat_id", chat_id)
            pass2_sentences, failed_window_count = await run_pass2(
                paper_text, chat_id, correlation_id, thinking_level=settings.pass2_thinking_level
            )
        merge_result = merge_pass2_claims(claims, pass2_sentences, paper_text)
        claims = merge_result["merged_claims"]
        print(
            f"[extraction] chat_id={chat_id} correlation_id={correlation_id} pass2: "
            f"{len(pass2_sentences)} raw sentences, {failed_window_count} failed_window_count, "
            f"{merge_result['dropped_ungrounded']} dropped_ungrounded, "
            f"{len(merge_result['dropped_duplicate'])} dropped_duplicate, "
            f"{len(merge_result['kept_but_contained'])} kept_but_contained, "
            f"{len(merge_result['kept_new'])} kept_new"
        )

    if on_detail is not None:
        try:
            await on_detail(f"Extracted {len(claims)} claims from paper")
        except Exception:
            pass  # progress emission never breaks extraction

    if on_audit_start is not None:
        try:
            await on_audit_start()
        except Exception:
            pass

    claims_done = 0
    total_claims = len(claims)

    async def _report_claim_done() -> None:
        nonlocal claims_done
        claims_done += 1
        if on_audit_detail is not None:
            try:
                await on_audit_detail(f"Audited {claims_done} of {total_claims} claims")
            except Exception:
                pass  # progress emission never breaks extraction

    async def _audit_wrapper(*args, **kwargs):
        try:
            return await _audit_and_structure_claim(*args, **kwargs)
        finally:
            await _report_claim_done()

    semaphore = asyncio.Semaphore(AUDIT_STRUCTURE_CONCURRENCY)
    results = await asyncio.gather(
        *(
            _audit_wrapper(
                semaphore, paper_text, claim, chat_id, correlation_id,
                claim_number=i + 1, total_claims=total_claims, on_detail=None,
                thinking_level=settings.auditor_thinking_level,
            )
            for i, claim in enumerate(claims)
        ),
        return_exceptions=True,
    )

    structured_claims: list[ClaimLLM] = []
    for claim, result in zip(claims, results):
        if isinstance(result, Exception):
            print(
                f"[extraction] chat_id={chat_id} correlation_id={correlation_id} audit/structure pipeline failed for "
                f"claim={claim.get('claim_text_verbatim', '')!r}: {result!r}"
            )
            continue
        structured_claims.append(result)

    return ClaimsExtractionResponse(claims=structured_claims)


async def extract_metadata(
    paper_text: str,
    chat_id: str,
    correlation_id: str | None = None,
) -> MetadataExtractionResponse:
    """Extracts paper-level metadata from paper_text via Gemini structured output."""
    messages = build_gemini_messages_for_metadata(paper_text)
    result = await _call_gemini_structured(
        messages=messages,
        response_schema=MetadataExtractionResponse,
        chat_id=chat_id,
        correlation_id=correlation_id,
        log_subdir="metadata",
        model_name=settings.llm_extraction_model,
        fallback_model=settings.llm_extraction_fallback_model,
    )
    return result
