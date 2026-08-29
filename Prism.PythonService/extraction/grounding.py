"""Grounds LLM-extracted claims against the source paper text.

Two-stage per-span check (RapidFuzz substring match, then an LLM audit
via LiteLLM - Groq primary, Gemini Flash Lite fallback - for spans that
survive), rolled up into per-claim grounding_status/missing/reason.
Failed claims stay in the output - they are the correct-refusal
artifact, not something to drop.

No DB writes, no worker integration - this module only grounds and logs.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

import litellm
from rapidfuzz import fuzz

from config import settings
from extraction.prompt_loader import build_gemini_messages_for_span_audit
from extraction.prompt_version import get_prompt_version
from extraction.schemas import (
    ClaimFinal,
    ClaimsExtractionResponse,
    EvidenceSpanFinal,
    EvidenceSpanLLM,
    GroundingStatus,
    SpanAuditVerdict,
)

litellm.enable_json_schema_validation = True

AUDIT_MAX_OUTPUT_TOKENS = 512

LOGS_DIR = Path(__file__).parent.parent / "logs" / "grounding"

RAPIDFUZZ_THRESHOLD = 88
AUDIT_CONCURRENCY = 1

AUDIT_MAX_ATTEMPTS = 3
AUDIT_BACKOFF_SECONDS = (1, 2, 4)

PARAGRAPH_SEPARATORS = ["\n\n", "\r\n\r\n"]
MIN_CONTEXT_CHARS = 500  # floor - always at least this wide
MAX_CONTEXT_CHARS = 1500  # ceiling - never wider than this
TARGET_CONTEXT_CHARS = 800  # preferred window before hitting caps


def _extract_span_context(
    paper_text: str,
    match_start: int,
    match_end: int,
) -> str:
    """Extract context around a matched evidence span, snapping to
    paragraph boundaries when possible. Falls back to sentence
    boundaries, then to raw char slice, if paragraphs are too
    far apart or absent.

    Guarantees:
      - Returns at least MIN_CONTEXT_CHARS of context (padding
        equally left/right if the natural window is too small).
      - Never returns more than MAX_CONTEXT_CHARS.
      - Prefers to start/end at a paragraph break to give the
        auditor coherent readable context.
    """
    # 1. Find nearest paragraph break BEFORE match_start.
    prior_break = 0
    for sep in PARAGRAPH_SEPARATORS:
        idx = paper_text.rfind(sep, 0, match_start)
        if idx > prior_break:
            prior_break = idx + len(sep)

    # 2. Find nearest paragraph break AFTER match_end.
    next_break = len(paper_text)
    for sep in PARAGRAPH_SEPARATORS:
        idx = paper_text.find(sep, match_end)
        if idx != -1 and idx < next_break:
            next_break = idx

    # 3. If paragraph window is too wide, fall back to sentence
    #    boundaries (period + space).
    window_size = next_break - prior_break
    if window_size > MAX_CONTEXT_CHARS:
        # Fall back to sentence-ish boundaries
        # Look for ". " or "\n" as sentence boundary
        for pattern in [". ", "\n"]:
            sent_start = paper_text.rfind(pattern, max(match_start - MAX_CONTEXT_CHARS // 2, 0), match_start)
            if sent_start != -1:
                prior_break = sent_start + len(pattern)
                break
        for pattern in [". ", "\n"]:
            sent_end = paper_text.find(pattern, match_end, min(match_end + MAX_CONTEXT_CHARS // 2, len(paper_text)))
            if sent_end != -1:
                next_break = sent_end
                break

    # 4. If window is STILL too wide, hard-cap symmetrically.
    window_size = next_break - prior_break
    if window_size > MAX_CONTEXT_CHARS:
        center = (match_start + match_end) // 2
        half = MAX_CONTEXT_CHARS // 2
        prior_break = max(center - half, 0)
        next_break = min(center + half, len(paper_text))

    # 5. If window is too narrow (paragraph is very short), pad
    #    symmetrically to hit MIN_CONTEXT_CHARS.
    window_size = next_break - prior_break
    if window_size < MIN_CONTEXT_CHARS:
        shortage = MIN_CONTEXT_CHARS - window_size
        left_pad = shortage // 2
        right_pad = shortage - left_pad
        prior_break = max(prior_break - left_pad, 0)
        next_break = min(next_break + right_pad, len(paper_text))

    return paper_text[prior_break:next_break].strip()


def _to_litellm_messages(messages: list[dict]) -> list[dict]:
    """Translates prompt_loader's Gemini-style "model" role to the
    "assistant" role LiteLLM/OpenAI-compatible providers expect."""
    return [
        {"role": "assistant" if msg["role"] == "model" else msg["role"], "content": msg["content"]}
        for msg in messages
    ]


def _is_retryable(exc: Exception) -> bool:
    """Returns True for rate limits, server errors, and timeouts - the
    exception types LiteLLM normalizes across every backend provider."""
    return isinstance(
        exc,
        (
            litellm.RateLimitError,
            litellm.APIConnectionError,
            litellm.Timeout,
            litellm.ServiceUnavailableError,
            litellm.InternalServerError,
        ),
    )


async def _call_litellm_audit(
    messages: list[dict],
    audit_model: str,
    fallback_model: str,
    gemini_api_key: str,
    span_source_section: str,
) -> SpanAuditVerdict:
    """Calls the span-audit model with retry/backoff, raising the last error
    if all attempts fail. Each attempt carries LiteLLM's built-in `fallbacks`
    so a Groq failure fails over to Gemini Flash Lite before the attempt is
    counted as failed.
    """
    last_exception: Exception | None = None

    for attempt in range(1, AUDIT_MAX_ATTEMPTS + 1):
        try:
            response = await litellm.acompletion(
                model=audit_model,
                messages=messages,
                temperature=0,
                max_tokens=AUDIT_MAX_OUTPUT_TOKENS,
                response_format=SpanAuditVerdict,
                fallbacks=[{"model": fallback_model, "api_key": gemini_api_key}],
            )
            content = response.choices[0].message.content
            return SpanAuditVerdict.model_validate_json(content)
        except Exception as exc:
            if not _is_retryable(exc):
                print(f"[ground_extraction] audit non-retryable error for span in {span_source_section!r}: {exc!r}")
                raise
            last_exception = exc
            print(
                f"[ground_extraction] audit attempt={attempt}/{AUDIT_MAX_ATTEMPTS} "
                f"failed for span in {span_source_section!r}: {exc!r}"
            )
            if attempt < AUDIT_MAX_ATTEMPTS:
                await asyncio.sleep(AUDIT_BACKOFF_SECONDS[attempt - 1])

    assert last_exception is not None
    raise last_exception


async def _audit_span_with_llm(
    claim_text: str,
    span_source_text: str,
    span_source_section: str,
    span_context: str,
    semaphore: asyncio.Semaphore,
    audit_model: str,
    fallback_model: str,
    gemini_api_key: str,
) -> GroundingStatus:
    """Asks the audit model whether the evidence quote supports the claim.

    Receives the surrounding paper context (extracted via
    _extract_span_context) so the LLM can interpret table cell values
    and short quotes in their proper passage context. Uses the 3-tier
    Pass/Partial/Fail rubric (prompts/audit_system.txt +
    prompts/audit_fewshot.json) via structured JSON output, so an
    on-topic-but-unconfirmable passage lands on Partial instead of
    forcing a binary guess into Fail.

    Defensive: any error (API failure, malformed response) is logged and
    treated as FAIL rather than propagated, since ambiguity here should
    not abort grounding for the rest of the extraction.
    """
    messages = _to_litellm_messages(
        build_gemini_messages_for_span_audit(
            claim_text=claim_text,
            quote=span_source_text,
            context=span_context,
        )
    )

    async with semaphore:
        try:
            verdict = await _call_litellm_audit(
                messages=messages,
                audit_model=audit_model,
                fallback_model=fallback_model,
                gemini_api_key=gemini_api_key,
                span_source_section=span_source_section,
            )
            return GroundingStatus(verdict.verdict)
        except Exception as exc:
            print(f"[ground_extraction] LLM audit failed for span in {span_source_section!r}: {exc!r}")
            return GroundingStatus.FAIL


def _passes_rapidfuzz(span_source_text: str, paper_text: str) -> bool:
    return fuzz.partial_ratio(span_source_text, paper_text) >= RAPIDFUZZ_THRESHOLD


async def _ground_span(
    claim_text: str,
    span: EvidenceSpanLLM,
    paper_text: str,
    semaphore: asyncio.Semaphore,
    audit_model: str,
    fallback_model: str,
    gemini_api_key: str,
) -> tuple[EvidenceSpanFinal, bool]:
    """Grounds one span. Returns (finalized span, passed_rapidfuzz)."""
    if not _passes_rapidfuzz(span.source_text, paper_text):
        final_span = EvidenceSpanFinal(
            source_text=span.source_text,
            source_section=span.source_section,
            section_header=span.section_header,
            page_number=span.page_number,
            grounding_status=GroundingStatus.FAIL,
        )
        return final_span, False

    alignment = fuzz.partial_ratio_alignment(span.source_text, paper_text)
    if alignment.score >= RAPIDFUZZ_THRESHOLD:
        span_context = _extract_span_context(paper_text, alignment.dest_start, alignment.dest_end)
    else:
        span_context = span.source_text
    print(f"[ground_extraction] audit context: {len(span_context)} chars for span in {span.source_section!r}")

    status = await _audit_span_with_llm(
        claim_text=claim_text,
        span_source_text=span.source_text,
        span_source_section=span.source_section,
        span_context=span_context,
        semaphore=semaphore,
        audit_model=audit_model,
        fallback_model=fallback_model,
        gemini_api_key=gemini_api_key,
    )
    final_span = EvidenceSpanFinal(
        source_text=span.source_text,
        source_section=span.source_section,
        section_header=span.section_header,
        page_number=span.page_number,
        grounding_status=status,
    )
    return final_span, True


def _write_grounding_log(
    chat_id: str,
    correlation_id: str | None,
    total_claims: int,
    claims_passed: int,
    claims_partial: int,
    claims_failed: int,
    spans_total: int,
    spans_passed_rapidfuzz: int,
    spans_passed_audit: int,
    spans_partial_audit: int,
    spans_failed_audit: int,
) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename_ts = now.strftime("%Y%m%dT%H%M%S%f")
    log_path = LOGS_DIR / f"{filename_ts}_{chat_id}_{correlation_id or 'none'}.json"

    log_entry = {
        "timestamp": now.isoformat(),
        "chat_id": chat_id,
        "correlation_id": correlation_id,
        "prompt_version": get_prompt_version(),
        "total_claims": total_claims,
        "claims_passed": claims_passed,
        "claims_partial": claims_partial,
        "claims_failed": claims_failed,
        "spans_total": spans_total,
        "spans_passed_rapidfuzz": spans_passed_rapidfuzz,
        "spans_passed_audit": spans_passed_audit,
        "spans_partial_audit": spans_partial_audit,
        "spans_failed_audit": spans_failed_audit,
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


async def ground_extraction(
    extraction: ClaimsExtractionResponse,
    paper_text: str,
    chat_id: str,
    correlation_id: str | None = None,
    on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
) -> list[ClaimFinal]:
    """Grounds every claim's evidence spans and rolls up per-claim status.

    Stage 1 (RapidFuzz) filters spans deterministically; Stage 2 (LiteLLM
    audit, capped at AUDIT_CONCURRENCY concurrent calls) judges the
    survivors. Stage 3 rolls per-span results into claim-level grounding_status,
    missing, and reason. Failed claims are kept, not dropped.

    Grounding runs at the span level (one task per evidence span, fanned
    out with the same semaphore), not per claim, so on_progress - a
    per-claim counter - fires once a claim's last outstanding span
    finishes rather than serializing claims. Counts are exact (tracked
    with a plain counter; asyncio has no preemption between awaits) but
    the order claims complete in is not guaranteed to match extraction
    order.
    """
    audit_model = settings.audit_model
    fallback_model = settings.audit_fallback_model
    gemini_api_key = settings.ai_api_key

    semaphore = asyncio.Semaphore(AUDIT_CONCURRENCY)

    total_claims = len(extraction.claims)
    remaining_spans_per_claim = [len(claim.evidence_spans) for claim in extraction.claims]
    claims_done = sum(1 for count in remaining_spans_per_claim if count == 0)

    async def _report_claim_done(claim_idx: int) -> None:
        nonlocal claims_done
        remaining_spans_per_claim[claim_idx] -= 1
        if remaining_spans_per_claim[claim_idx] == 0:
            claims_done += 1
            if on_progress is not None:
                try:
                    await on_progress(claims_done, total_claims)
                except Exception:
                    pass  # progress emission never breaks grounding

    async def _ground_span_tracked(claim_idx: int, claim_text: str, span: EvidenceSpanLLM):
        result = await _ground_span(
            claim_text=claim_text,
            span=span,
            paper_text=paper_text,
            semaphore=semaphore,
            audit_model=audit_model,
            fallback_model=fallback_model,
            gemini_api_key=gemini_api_key,
        )
        await _report_claim_done(claim_idx)
        return result

    if on_progress is not None and claims_done:
        try:
            await on_progress(claims_done, total_claims)
        except Exception:
            pass

    span_tasks = []
    span_claim_indices: list[int] = []
    for claim_idx, claim in enumerate(extraction.claims):
        for span in claim.evidence_spans:
            span_claim_indices.append(claim_idx)
            span_tasks.append(
                _ground_span_tracked(claim_idx, claim.claim_text_verbatim, span)
            )

    span_results = await asyncio.gather(*span_tasks) if span_tasks else []

    claims_spans: list[list[EvidenceSpanFinal]] = [[] for _ in extraction.claims]
    claims_rapidfuzz_failed = [0 for _ in extraction.claims]
    claims_audit_failed = [0 for _ in extraction.claims]
    spans_total = 0
    spans_passed_rapidfuzz = 0
    spans_passed_audit = 0
    spans_partial_audit = 0
    spans_failed_audit = 0

    for claim_idx, (final_span, passed_rapidfuzz) in zip(span_claim_indices, span_results):
        spans_total += 1
        claims_spans[claim_idx].append(final_span)
        if passed_rapidfuzz:
            spans_passed_rapidfuzz += 1
            if final_span.grounding_status == GroundingStatus.PASS:
                spans_passed_audit += 1
            elif final_span.grounding_status == GroundingStatus.PARTIAL:
                spans_partial_audit += 1
                claims_audit_failed[claim_idx] += 1
            else:
                spans_failed_audit += 1
                claims_audit_failed[claim_idx] += 1
        else:
            claims_rapidfuzz_failed[claim_idx] += 1

    final_claims: list[ClaimFinal] = []
    claims_passed = 0
    claims_partial = 0
    claims_failed = 0

    for claim_idx, claim in enumerate(extraction.claims):
        spans = claims_spans[claim_idx]
        passes = [s for s in spans if s.grounding_status == GroundingStatus.PASS]
        partials = [s for s in spans if s.grounding_status == GroundingStatus.PARTIAL]

        if passes:
            claims_passed += 1
            final_claims.append(
                ClaimFinal(
                    claim_text_verbatim=claim.claim_text_verbatim,
                    claim_summary=claim.claim_summary,
                    label=claim.label,
                    evidence_spans=spans,
                    grounding_status=GroundingStatus.PASS,
                    missing=False,
                    reason=None,
                )
            )
        elif partials:
            claims_partial += 1
            noun = "passage" if len(partials) == 1 else "passages"
            reason = (
                "The auditor accepted the cited evidence as partial support: "
                f"{len(partials)} {noun} provided partial support to the claim."
            )
            final_claims.append(
                ClaimFinal(
                    claim_text_verbatim=claim.claim_text_verbatim,
                    claim_summary=claim.claim_summary,
                    label=claim.label,
                    evidence_spans=spans,
                    grounding_status=GroundingStatus.PARTIAL,
                    missing=False,
                    reason=reason,
                )
            )
        else:
            claims_failed += 1
            reason = (
                f"all evidence spans failed grounding: "
                f"{claims_rapidfuzz_failed[claim_idx]} spans failed RapidFuzz check; "
                f"{claims_audit_failed[claim_idx]} spans failed LLM audit"
            )
            final_claims.append(
                ClaimFinal(
                    claim_text_verbatim=claim.claim_text_verbatim,
                    claim_summary=claim.claim_summary,
                    label=claim.label,
                    evidence_spans=spans,
                    grounding_status=GroundingStatus.FAIL,
                    missing=True,
                    reason=reason,
                )
            )

    _write_grounding_log(
        chat_id=chat_id,
        correlation_id=correlation_id,
        total_claims=len(extraction.claims),
        claims_passed=claims_passed,
        claims_partial=claims_partial,
        claims_failed=claims_failed,
        spans_total=spans_total,
        spans_passed_rapidfuzz=spans_passed_rapidfuzz,
        spans_passed_audit=spans_passed_audit,
        spans_partial_audit=spans_partial_audit,
        spans_failed_audit=spans_failed_audit,
    )

    return final_claims
