"""Calls Gemini to extract structured data from paper text.

Builds messages via prompt_loader, translates them into the google-genai
SDK's system_instruction/contents format, and enforces a Pydantic schema
via structured output. No grounding logic, no DB writes — downstream
stages (grounding, DB write) consume this module's output.

Two extraction types share the same Gemini-calling machinery:
  - extract_claims: Prompt 2, per-claim evidence extraction
  - extract_metadata: Prompt 1, paper-level metadata extraction
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from extraction.prompt_loader import build_gemini_messages_for_claims, build_gemini_messages_for_metadata
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimsExtractionResponse, MetadataExtractionResponse

LOGS_DIR = Path(__file__).parent.parent / "logs"

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1, 2, 4)


def _is_retryable(exc: Exception) -> bool:
    """Returns True for rate limits, server errors, timeouts, and connection drops."""
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
) -> types.GenerateContentResponse:
    """Calls Gemini with retry/backoff, raising the last error if all attempts fail."""
    last_exception: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"[extraction] chat_id={chat_id} model={model} attempt={attempt}/{MAX_ATTEMPTS}")
            return await client.aio.models.generate_content(model=model, contents=contents, config=config)
        except Exception as exc:
            if not _is_retryable(exc):
                print(f"[extraction] chat_id={chat_id} model={model} non-retryable error: {exc!r}")
                raise
            last_exception = exc
            print(f"[extraction] chat_id={chat_id} model={model} attempt={attempt}/{MAX_ATTEMPTS} failed: {exc!r}")
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_SECONDS[attempt - 1])

    assert last_exception is not None
    raise last_exception


def _write_structured_log(
    log_subdir: str,
    chat_id: str,
    correlation_id: str | None,
    model_used: str,
    request_message_count: int,
    response_item_count: int,
    response_raw: str,
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
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


async def _call_gemini_structured(
    messages: list[dict],
    response_schema: type[BaseModel],
    chat_id: str,
    correlation_id: str | None,
    log_subdir: str,
) -> BaseModel:
    """Calls Gemini with a schema-enforced structured output config.

    Retries transient failures (429/5xx/timeout/connection) up to 3 times with
    exponential backoff, then falls back to LLM_AUDIT_MODEL for one final
    attempt before raising the last error. Falls back to json.loads/model_validate
    when response.parsed is None. Logs the request/response to
    logs/{log_subdir}/{timestamp}_{chat_id}_{correlation_id}.json.
    """
    model_name = os.getenv("LLM_EXTRACTION_MODEL")
    if not model_name:
        raise RuntimeError("LLM_EXTRACTION_MODEL environment variable is not set")

    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        raise RuntimeError("AI_API_KEY environment variable is not set")

    system_prompt = _extract_system_prompt(messages)
    contents = _to_gemini_contents(messages)

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    used_model = model_name
    try:
        response = await _call_gemini(client, model_name, contents, config, chat_id)
    except Exception as primary_exc:
        if not _is_retryable(primary_exc):
            raise
        fallback_model = os.getenv("LLM_AUDIT_MODEL")
        if not fallback_model:
            raise RuntimeError(
                f"Gemini call failed after {MAX_ATTEMPTS} attempts on model={model_name} "
                f"(chat_id={chat_id}) and LLM_AUDIT_MODEL is not set for fallback"
            ) from primary_exc
        used_model = fallback_model
        try:
            print(f"[extraction] chat_id={chat_id} falling back to model={fallback_model}")
            response = await client.aio.models.generate_content(model=fallback_model, contents=contents, config=config)
        except Exception as fallback_exc:
            print(f"[extraction] chat_id={chat_id} fallback model={fallback_model} failed: {fallback_exc!r}")
            raise RuntimeError(
                f"Gemini call failed after {MAX_ATTEMPTS} attempts on model={model_name} "
                f"and fallback attempt on model={fallback_model} (chat_id={chat_id})"
            ) from fallback_exc

    raw_text = response.text

    parsed = response.parsed
    if parsed is None:
        try:
            parsed = response_schema.model_validate(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError) as parse_exc:
            print(f"[extraction] chat_id={chat_id} malformed response, raw={raw_text!r}")
            _write_structured_log(
                log_subdir=log_subdir,
                chat_id=chat_id,
                correlation_id=correlation_id,
                model_used=used_model,
                request_message_count=len(messages),
                response_item_count=0,
                response_raw=raw_text,
            )
            raise ValueError(
                f"Gemini response for chat_id={chat_id} was neither parsed by the SDK nor valid JSON: {parse_exc}"
            ) from parse_exc

    if hasattr(parsed, "claims"):
        item_count = len(parsed.claims)
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
    )

    return parsed


async def extract_claims(
    paper_text: str,
    chat_id: str,
    correlation_id: str | None = None,
) -> ClaimsExtractionResponse:
    """Extracts structured claims from paper_text via Gemini structured output."""
    messages = build_gemini_messages_for_claims(paper_text)
    result = await _call_gemini_structured(
        messages=messages,
        response_schema=ClaimsExtractionResponse,
        chat_id=chat_id,
        correlation_id=correlation_id,
        log_subdir="extraction",
    )
    return result


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
    )
    return result
