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
import contextvars
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

from google import genai
from google.genai import errors, types
from opentelemetry import trace
from pydantic import BaseModel

from config import settings
from extraction import scoped_audit
from extraction.prompt_loader import (
    build_gemini_messages_for_audit,
    build_gemini_messages_for_extractor,
    build_gemini_messages_for_metadata,
    build_gemini_messages_for_structure,
    build_messages_for_inventory,
    build_messages_for_scope,
    build_messages_for_scoped_audit,
)
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLabel, ClaimLLM, ClaimsExtractionResponse, MetadataExtractionResponse
from extraction.scoped_schemas import ClaimScope, PaperInventory, ScopeItem

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


def _build_client() -> genai.Client:
    return genai.Client(api_key=settings.ai_api_key)


# Optional per-task token sink. Unset (None) in the legacy pipeline, so nothing
# changes there; the scoped path and the Experiment 1 replay set it to collect
# per-call usage_metadata.
_USAGE_SINK: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar("usage_sink", default=None)


def _record_usage(response, config: types.GenerateContentConfig, requested_model: str, used_model: str) -> None:
    sink = _USAGE_SINK.get()
    if sink is None:
        return
    um = getattr(response, "usage_metadata", None)
    schema = getattr(config, "response_schema", None)
    sink.append(
        {
            "call": getattr(schema, "__name__", None) or "freetext",
            "requested_model": requested_model,
            "used_model": used_model,
            "fell_back": used_model != requested_model,
            "input_tokens": getattr(um, "prompt_token_count", None),
            "output_tokens": getattr(um, "candidates_token_count", None),
            "thinking_tokens": getattr(um, "thoughts_token_count", None),
        }
    )


async def _generate_with_fallback(
    client: genai.Client,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
    chat_id: str,
    model_name: str,
    fallback_model: str,
    correlation_id: str | None = None,
) -> tuple[types.GenerateContentResponse, str]:
    """Calls Gemini on model_name with retry/backoff, falling back to
    fallback_model for one final attempt if the primary model's retries are
    exhausted. Returns (response, model_name_actually_used). Raises on
    terminal failure (non-retryable error, or fallback attempt also fails).
    """
    try:
        response = await _call_gemini(client, model_name, contents, config, chat_id, correlation_id)
        _record_usage(response, config, model_name, model_name)
        return response, model_name
    except Exception as primary_exc:
        if not _is_retryable(primary_exc):
            raise
        try:
            print(f"[extraction] chat_id={chat_id} correlation_id={correlation_id} falling back to model={fallback_model}")
            response = await client.aio.models.generate_content(model=fallback_model, contents=contents, config=config)
            _record_usage(response, config, model_name, fallback_model)
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
) -> BaseModel:
    """Calls Gemini with a schema-enforced structured output config.

    Retries transient failures (429/5xx/timeout/connection) up to 3 times with
    exponential backoff, then falls back to fallback_model for one final
    attempt before raising the last error. Falls back to json.loads/model_validate
    when response.parsed is None. Logs the request/response to
    logs/{log_subdir}/{timestamp}_{chat_id}_{correlation_id}.json.
    """
    client = _build_client()
    system_prompt = _extract_system_prompt(messages)
    contents = _to_gemini_contents(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    response, used_model = await _generate_with_fallback(
        client, contents, config, chat_id, model_name, fallback_model, correlation_id
    )
    raw_text = response.text

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
    )

    return parsed


async def _call_gemini_freetext(
    messages: list[dict],
    chat_id: str,
    correlation_id: str | None,
    log_subdir: str,
    model_name: str,
    fallback_model: str,
) -> str:
    """Calls Gemini for plain free-text output - no JSON mode, no schema.

    Used for the auditor call: reasoning happens in prose first, so the
    label isn't committed to structure before the evidence is weighed.
    Same retry/backoff/fallback-model behavior as _call_gemini_structured.
    Logs the request/response to logs/{log_subdir}/{timestamp}_{chat_id}_{correlation_id}.json.
    """
    client = _build_client()
    system_prompt = _extract_system_prompt(messages)
    contents = _to_gemini_contents(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
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


# ---------------------------------------------------------------- scoped mode
_VERDICT_LINE_RE = re.compile(r"^\W*VERDICT:\s*\W*(not_supported|partially_supported|supported)\b", re.IGNORECASE | re.MULTILINE)


def parse_verdict_line(audit_text: str) -> Optional[str]:
    """Last VERDICT: line of a free-text audit, or None if unreadable."""
    found = _VERDICT_LINE_RE.findall(audit_text or "")
    return found[-1].lower() if found else None


def _claim_key(claim_text: str) -> str:
    return hashlib.sha256(" ".join(claim_text.split()).lower().encode("utf-8")).hexdigest()[:16]


async def get_inventory(paper_text: str, chat_id: str, correlation_id: str | None) -> tuple[PaperInventory, str]:
    """Scoped step 1: per-paper inventory (structured), cached by paper content
    hash + scoped prompt version under LOGS_DIR/inventory/. Returns
    (inventory, inventory_hash)."""
    cached = scoped_audit.load_cached_inventory(LOGS_DIR, paper_text)
    if cached is not None:
        return cached, scoped_audit.inventory_hash(cached)
    inventory = await _call_gemini_structured(
        messages=build_messages_for_inventory(paper_text),
        response_schema=PaperInventory,
        chat_id=chat_id,
        correlation_id=correlation_id,
        log_subdir="inventory_raw",
        model_name=settings.llm_claim_audit_model,
        fallback_model=settings.llm_claim_audit_fallback_model,
    )
    scoped_audit.save_inventory(LOGS_DIR, paper_text, inventory, settings.llm_claim_audit_model)
    return inventory, scoped_audit.inventory_hash(inventory)


class ScopeStepError(Exception):
    """The scope step failed or returned no items; the claim falls back to the legacy audit."""


@dataclass
class ScopedAuditResult:
    audit_text: str
    scope_items: list[ScopeItem]
    scope_truncated: bool
    parsed: scoped_audit.ParsedChecks
    usage: list[dict] = field(default_factory=list)


async def run_scoped_audit(
    paper_text: str,
    claim_text_verbatim: str,
    claim_summary: str,
    inventory: PaperInventory,
    chat_id: str,
    correlation_id: str | None,
) -> ScopedAuditResult:
    """Scoped steps 2 and 3 for one claim.

    Step 2 (scope) is a structured call that sees the claim and the inventory
    only - never the paper. Step 3 is the free-text audit (no response_schema)
    over the paper, the claim and the fixed scope list. Raises ScopeStepError if
    the scope step fails or is empty (caller falls back to legacy); audit-call
    failures propagate as in legacy mode.
    """
    token = _USAGE_SINK.set([])
    try:
        try:
            scope: ClaimScope = await _call_gemini_structured(
                messages=build_messages_for_scope(claim_text_verbatim, claim_summary, inventory.items),
                response_schema=ClaimScope,
                chat_id=chat_id,
                correlation_id=correlation_id,
                log_subdir="scope",
                model_name=settings.llm_claim_audit_model,
                fallback_model=settings.llm_claim_audit_fallback_model,
            )
            items, truncated = scoped_audit.truncate_scope(list(scope.items))
            if not items:
                raise ValueError("scope step returned no items")
        except Exception as exc:
            raise ScopeStepError(repr(exc)) from exc
        # Ids are re-issued in order so the fixed list is always S1..Sn, unique.
        items = [i.model_copy(update={"scope_id": f"S{n}"}) for n, i in enumerate(items, start=1)]
        audit_text = await _call_gemini_freetext(
            messages=build_messages_for_scoped_audit(paper_text, claim_text_verbatim, claim_summary, items),
            chat_id=chat_id,
            correlation_id=correlation_id,
            log_subdir="audit_scoped_raw",
            model_name=settings.llm_claim_audit_model,
            fallback_model=settings.llm_claim_audit_fallback_model,
        )
        parsed = scoped_audit.parse_checks(audit_text, [i.scope_id for i in items])
        return ScopedAuditResult(audit_text, items, truncated, parsed, list(_USAGE_SINK.get() or []))
    finally:
        _USAGE_SINK.reset(token)


def finish_scoped_audit(
    res: ScopedAuditResult,
    model_verdict: Optional[str],
    paper_text: str,
    claim_text_verbatim: str,
    inventory_hash: str,
    chat_id: str,
    correlation_id: str | None,
    claim_number: int,
    extra_flags: Optional[list[str]] = None,
) -> scoped_audit.Aggregation:
    """Aggregates (lower-only) and writes the audit-request log. The log holds
    hashes, the claim text, the scope list, raw CHECK lines, flags and token
    counts - never the paper text."""
    agg = scoped_audit.aggregate(model_verdict, [i.scope_id for i in res.scope_items], res.parsed, paper_text)
    flags = list(agg.flags) + list(extra_flags or [])
    if res.scope_truncated:
        flags.append("scope_truncated")
        print(f"[scoped] chat_id={chat_id} claim={claim_number} scope truncated to {len(res.scope_items)} items")
    if agg.aggregation_skipped:
        print(f"[scoped] chat_id={chat_id} claim={claim_number} aggregation_skipped flags={flags}")
    scoped_audit.write_scoped_audit_log(
        LOGS_DIR,
        chat_id,
        correlation_id,
        {
            "chat_id": chat_id,
            "correlation_id": correlation_id,
            "claim_number": claim_number,
            "claim_key": _claim_key(claim_text_verbatim),
            "claim_text": claim_text_verbatim,
            "prompt_version": get_prompt_version(),
            "scoped_prompt_version": scoped_audit.get_scoped_prompt_version(),
            "inventory_hash": inventory_hash,
            "model": settings.llm_claim_audit_model,
            "scope": [i.model_dump() for i in res.scope_items],
            "scope_truncated": res.scope_truncated,
            "check_lines": res.parsed.raw_lines,
            "parse_flags": flags,
            "model_verdict": agg.model_verdict,
            "final_verdict": agg.final,
            "lowered": agg.lowered,
            "trigger_id": agg.trigger_id,
            "trigger_quote": agg.trigger_quote,
            "dropped_ungrounded": agg.dropped_ungrounded,
            "aggregation_skipped": agg.aggregation_skipped,
            "calls": res.usage,
        },
    )
    return agg


async def _audit_and_structure_claim_scoped(
    paper_text: str,
    claim: dict,
    inventory: PaperInventory,
    inventory_hash: str,
    chat_id: str,
    correlation_id: str | None,
    claim_number: int,
) -> ClaimLLM:
    """Scoped pipeline path: scope -> scoped audit -> structurer (unchanged) ->
    lower-only aggregation. Called inside the claim semaphore."""
    claim_text_verbatim = claim["claim_text_verbatim"]
    claim_summary = claim["claim_summary"]
    with tracer.start_as_current_span("auditor") as span:
        span.set_attribute("correlation_id", correlation_id or "")
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("claim_number", claim_number)
        res = await run_scoped_audit(paper_text, claim_text_verbatim, claim_summary, inventory, chat_id, correlation_id)

    with tracer.start_as_current_span("structurer") as span:
        span.set_attribute("correlation_id", correlation_id or "")
        span.set_attribute("chat_id", chat_id)
        span.set_attribute("claim_number", claim_number)
        structured = await _call_gemini_structured(
            messages=build_gemini_messages_for_structure(claim_text_verbatim, claim_summary, res.audit_text),
            response_schema=ClaimLLM,
            chat_id=chat_id,
            correlation_id=correlation_id,
            log_subdir="structure",
            model_name=settings.llm_claim_audit_model,
            fallback_model=settings.llm_claim_audit_fallback_model,
        )

    extra = []
    if parse_verdict_line(res.audit_text) != structured.label.value:
        extra.append("verdict_mismatch_structurer")
    agg = finish_scoped_audit(
        res, structured.label.value, paper_text, claim_text_verbatim, inventory_hash,
        chat_id, correlation_id, claim_number, extra_flags=extra,
    )
    if not agg.lowered:
        return structured
    # Code lowered the verdict. The label changes; evidence_spans are NOT touched.
    # The triggering quote and check id are in the scoped audit log only.
    return structured.model_copy(update={"label": ClaimLabel.PARTIALLY_SUPPORTED})


async def _audit_and_structure_claim(
    semaphore: asyncio.Semaphore,
    paper_text: str,
    claim: dict,
    chat_id: str,
    correlation_id: str | None,
    claim_number: int,
    total_claims: int,
    on_detail: Optional[Callable[[str], Awaitable[None]]] = None,
    inventory: Optional[PaperInventory] = None,
    inventory_hash: Optional[str] = None,
) -> ClaimLLM:
    """Runs Call #3 (audit) then Call #4 (structure) for one claim, in sequence.

    Concurrency across claims is bounded by the shared semaphore. claim_number
    is the claim's fixed position in the extracted list (1-indexed), not a
    live completion count - claims run concurrently, so on_detail messages
    may not appear in strict claim_number order.
    """
    claim_text_verbatim = claim["claim_text_verbatim"]
    claim_summary = claim["claim_summary"]

    async with semaphore:
        if inventory is not None:  # AUDIT_MODE=scoped
            try:
                return await _audit_and_structure_claim_scoped(
                    paper_text, claim, inventory, inventory_hash or "", chat_id, correlation_id, claim_number
                )
            except ScopeStepError as exc:
                # Scope step failed or returned nothing: audit this claim the legacy way.
                print(f"[scoped] chat_id={chat_id} claim={claim_number} scoped path failed ({exc!r}); falling back to legacy audit")

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

    inventory: Optional[PaperInventory] = None
    inventory_hash: Optional[str] = None
    if settings.audit_mode == "scoped":
        try:
            inventory, inventory_hash = await get_inventory(paper_text, chat_id, correlation_id)
        except Exception as exc:
            print(f"[scoped] chat_id={chat_id} correlation_id={correlation_id} inventory failed ({exc!r}); auditing legacy")

    semaphore = asyncio.Semaphore(AUDIT_STRUCTURE_CONCURRENCY)
    results = await asyncio.gather(
        *(
            _audit_wrapper(
                semaphore, paper_text, claim, chat_id, correlation_id,
                claim_number=i + 1, total_claims=total_claims, on_detail=None,
                inventory=inventory, inventory_hash=inventory_hash,
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
