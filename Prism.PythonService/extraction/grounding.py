"""Grounds LLM-extracted claims against the source paper text.

Two-stage per-span check (RapidFuzz substring match, then an LLM audit
on Flash Lite for spans that survive), rolled up into per-claim
grounding_status/missing/reason. Failed claims stay in the output —
they are the correct-refusal artifact, not something to drop.

No DB writes, no worker integration — this module only grounds and logs.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

from google import genai
from google.genai import types

from extraction.prompt_version import get_prompt_version
from extraction.schemas import (
    ClaimFinal,
    ClaimsExtractionResponse,
    EvidenceSpanFinal,
    EvidenceSpanLLM,
    GroundingStatus,
)

LOGS_DIR = Path(__file__).parent.parent / "logs" / "grounding"

RAPIDFUZZ_THRESHOLD = 88
AUDIT_CONCURRENCY = 5

AUDIT_PROMPT_TEMPLATE = """Claim: {claim_text}
Evidence quote (from {span_source_section}): {span_source_text}

Does the evidence quote directly support the claim as written?
Answer PASS if the quote states or clearly implies the claim.
Answer FAIL if the quote is unrelated, contradicts, or only weakly related.

Reply with exactly one word: PASS or FAIL."""


async def _audit_span_with_llm(
    claim_text: str,
    span_source_text: str,
    span_source_section: str,
    semaphore: asyncio.Semaphore,
    client: genai.Client,
    audit_model: str,
) -> GroundingStatus:
    """Asks Flash Lite whether the evidence quote supports the claim.

    Defensive: any error (API failure, malformed response) is logged and
    treated as FAIL rather than propagated, since ambiguity here should
    not abort grounding for the rest of the extraction.
    """
    prompt = AUDIT_PROMPT_TEMPLATE.format(
        claim_text=claim_text,
        span_source_section=span_source_section,
        span_source_text=span_source_text,
    )
    async with semaphore:
        try:
            response = await client.aio.models.generate_content(
                model=audit_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=10,
                ),
            )
            verdict = (response.text or "").strip().upper()
            return GroundingStatus.PASS if verdict.startswith("PASS") else GroundingStatus.FAIL
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
    client: genai.Client,
    audit_model: str,
) -> tuple[EvidenceSpanFinal, bool, bool]:
    """Grounds one span. Returns (finalized span, passed_rapidfuzz, passed_audit)."""
    if not _passes_rapidfuzz(span.source_text, paper_text):
        final_span = EvidenceSpanFinal(
            source_text=span.source_text,
            source_section=span.source_section,
            section_header=span.section_header,
            page_number=span.page_number,
            grounding_status=GroundingStatus.FAIL,
        )
        return final_span, False, False

    status = await _audit_span_with_llm(
        claim_text=claim_text,
        span_source_text=span.source_text,
        span_source_section=span.source_section,
        semaphore=semaphore,
        client=client,
        audit_model=audit_model,
    )
    final_span = EvidenceSpanFinal(
        source_text=span.source_text,
        source_section=span.source_section,
        section_header=span.section_header,
        page_number=span.page_number,
        grounding_status=status,
    )
    return final_span, True, status == GroundingStatus.PASS


def _write_grounding_log(
    chat_id: str,
    correlation_id: str | None,
    total_claims: int,
    claims_passed: int,
    claims_failed: int,
    spans_total: int,
    spans_passed_rapidfuzz: int,
    spans_passed_audit: int,
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
        "claims_failed": claims_failed,
        "spans_total": spans_total,
        "spans_passed_rapidfuzz": spans_passed_rapidfuzz,
        "spans_passed_audit": spans_passed_audit,
        "spans_failed_audit": spans_failed_audit,
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


async def ground_extraction(
    extraction: ClaimsExtractionResponse,
    paper_text: str,
    chat_id: str,
    correlation_id: str | None = None,
) -> list[ClaimFinal]:
    """Grounds every claim's evidence spans and rolls up per-claim status.

    Stage 1 (RapidFuzz) filters spans deterministically; Stage 2 (Flash
    Lite audit, capped at 5 concurrent calls) judges the survivors.
    Stage 3 rolls per-span results into claim-level grounding_status,
    missing, and reason. Failed claims are kept, not dropped.
    """
    audit_model = os.getenv("LLM_AUDIT_MODEL")
    if not audit_model:
        raise RuntimeError("LLM_AUDIT_MODEL environment variable is not set")

    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        raise RuntimeError("AI_API_KEY environment variable is not set")

    client = genai.Client(api_key=api_key)
    semaphore = asyncio.Semaphore(AUDIT_CONCURRENCY)

    span_tasks = []
    span_claim_indices: list[int] = []
    for claim_idx, claim in enumerate(extraction.claims):
        for span in claim.evidence_spans:
            span_claim_indices.append(claim_idx)
            span_tasks.append(
                _ground_span(
                    claim_text=claim.claim_text_verbatim,
                    span=span,
                    paper_text=paper_text,
                    semaphore=semaphore,
                    client=client,
                    audit_model=audit_model,
                )
            )

    span_results = await asyncio.gather(*span_tasks) if span_tasks else []

    claims_spans: list[list[EvidenceSpanFinal]] = [[] for _ in extraction.claims]
    claims_rapidfuzz_failed = [0 for _ in extraction.claims]
    claims_audit_failed = [0 for _ in extraction.claims]
    spans_total = 0
    spans_passed_rapidfuzz = 0
    spans_passed_audit = 0
    spans_failed_audit = 0

    for claim_idx, (final_span, passed_rapidfuzz, passed_audit) in zip(span_claim_indices, span_results):
        spans_total += 1
        claims_spans[claim_idx].append(final_span)
        if passed_rapidfuzz:
            spans_passed_rapidfuzz += 1
            if passed_audit:
                spans_passed_audit += 1
            else:
                spans_failed_audit += 1
                claims_audit_failed[claim_idx] += 1
        else:
            claims_rapidfuzz_failed[claim_idx] += 1

    final_claims: list[ClaimFinal] = []
    claims_passed = 0
    claims_failed = 0

    for claim_idx, claim in enumerate(extraction.claims):
        spans = claims_spans[claim_idx]
        any_pass = any(s.grounding_status == GroundingStatus.PASS for s in spans)

        if any_pass:
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
        claims_failed=claims_failed,
        spans_total=spans_total,
        spans_passed_rapidfuzz=spans_passed_rapidfuzz,
        spans_passed_audit=spans_passed_audit,
        spans_failed_audit=spans_failed_audit,
    )

    return final_claims
