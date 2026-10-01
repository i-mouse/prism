"""Grounding + post-grounding cap wiring in ground_extraction (no LLM calls).

_audit_span_with_llm is replaced with a fake that returns scripted results
keyed by span text, so these tests exercise role handling, the support-only
roll-up, the cap and the trace-only fields.
"""
import asyncio

import pytest

from extraction import grounding
from extraction.schemas import (
    AuditChecklist,
    AuditedClaim,
    AuditedSpan,
    ClaimFinal,
    ClaimLabel,
    ClaimsExtractionResponse,
    EvidenceSpanFinal,
    GroundingStatus,
)

PAPER = (
    "Table 4 shows that LatchNet lowers peak training memory by 31 percent on average across tasks.\n\n"
    "Appendix B notes that the memory saving vanishes entirely on the longest sequences we tried.\n\n"
    "We compare only against the baseline transformer in all experiments reported here."
)
SUPPORT_QUOTE = "Table 4 shows that LatchNet lowers peak training memory by 31 percent on average across tasks."
LIMIT_QUOTE = "Appendix B notes that the memory saving vanishes entirely on the longest sequences we tried."
FABRICATED_QUOTE = "Zebras were observed to outperform every transformer variant in the zoological appendix."

SPAN_RESULTS = {}  # span text -> SpanAuditResult
AUDIT_LABELS_SEEN: dict[str, ClaimLabel] = {}


def _checklist(*, scope="yes", comparison="n/a", has_limit=False, status="parsed") -> AuditChecklist:
    return AuditChecklist(
        checklist_status=status,
        auditor_verdict=ClaimLabel.SUPPORTED,
        scope_match=scope,
        comparison_tested=comparison,
        has_limit_quote=has_limit,
        model_used="auditor-x",
    )


def _claim(spans, checklist, verdict=ClaimLabel.SUPPORTED, text="LatchNet saves memory.") -> AuditedClaim:
    return AuditedClaim(
        claim_text_verbatim=text,
        claim_summary="summary",
        auditor_verdict=verdict,
        evidence_spans=spans,
        checklist=checklist,
        audit_reasoning="full audit prose",
    )


@pytest.fixture(autouse=True)
def _stub_llm_and_logs(monkeypatch):
    SPAN_RESULTS.clear()
    AUDIT_LABELS_SEEN.clear()

    async def fake_audit(claim_text, claim_label, span_source_text, **kwargs):
        AUDIT_LABELS_SEEN[span_source_text] = claim_label
        return SPAN_RESULTS[span_source_text]

    monkeypatch.setattr(grounding, "_audit_span_with_llm", fake_audit)
    monkeypatch.setattr(grounding, "_write_grounding_log", lambda **kwargs: None)


def _ground(*claims: AuditedClaim) -> list[ClaimFinal]:
    return asyncio.run(
        grounding.ground_extraction(
            extraction=ClaimsExtractionResponse(claims=list(claims)),
            paper_text=PAPER,
            chat_id="chat",
        )
    )


def _result(status, stance="supports", reasoning="why", model="m"):
    return grounding.SpanAuditResult(status, stance, reasoning, model)


def test_grounded_limit_span_caps_supported_and_records_the_trace():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PASS, "supports", "backs it", "groq-model")
    SPAN_RESULTS[LIMIT_QUOTE] = _result(GroundingStatus.PASS, "refutes", "narrows it", "fallback-model")
    claim = _claim(
        [
            AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support"),
            AuditedSpan(source_text=LIMIT_QUOTE, source_section="Appendix B", role="limit"),
        ],
        _checklist(has_limit=True),
    )

    [final] = _ground(claim)

    assert final.label == ClaimLabel.PARTIALLY_SUPPORTED
    assert final.auditor_verdict == ClaimLabel.SUPPORTED
    assert final.cap_reason == "limit"
    assert final.grounding_status == GroundingStatus.PASS and final.missing is False
    assert "Label lowered from supported to partially_supported" in final.reason
    assert final.audit_checklist.model_used == "auditor-x"
    assert final.audit_reasoning == "full audit prose"

    support, limit = final.evidence_spans
    assert (support.role, limit.role) == ("support", "limit")
    assert (support.stance, limit.stance) == ("supports", "refutes")
    assert (support.grounding_reasoning, limit.grounding_reasoning) == ("backs it", "narrows it")
    assert (support.grounding_model, limit.grounding_model) == ("groq-model", "fallback-model")
    assert support.fuzz_score >= grounding.RAPIDFUZZ_THRESHOLD and limit.fuzz_score >= grounding.RAPIDFUZZ_THRESHOLD


def test_limit_span_is_audited_under_the_partially_supported_rubric_support_span_under_the_verdict():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PASS)
    SPAN_RESULTS[LIMIT_QUOTE] = _result(GroundingStatus.PASS, "refutes")
    claim = _claim(
        [
            AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support"),
            AuditedSpan(source_text=LIMIT_QUOTE, source_section="Appendix B", role="limit"),
        ],
        _checklist(has_limit=True),
    )
    _ground(claim)
    assert AUDIT_LABELS_SEEN[SUPPORT_QUOTE] == ClaimLabel.SUPPORTED
    assert AUDIT_LABELS_SEEN[LIMIT_QUOTE] == ClaimLabel.PARTIALLY_SUPPORTED


def test_limit_quote_not_found_in_paper_does_not_cap_and_does_not_hurt_the_rollup():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PASS)
    claim = _claim(
        [
            AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support"),
            AuditedSpan(source_text=FABRICATED_QUOTE, source_section="Appendix Z", role="limit"),
        ],
        _checklist(has_limit=True),
    )

    [final] = _ground(claim)

    assert final.label == ClaimLabel.SUPPORTED and final.cap_reason is None
    assert final.auditor_verdict == ClaimLabel.SUPPORTED
    assert final.grounding_status == GroundingStatus.PASS and final.missing is False
    assert "Label lowered" not in final.reason
    limit = final.evidence_spans[1]
    assert limit.grounding_status == GroundingStatus.FAIL
    assert limit.stance is None and limit.grounding_reasoning is None and limit.grounding_model is None
    assert limit.fuzz_score is not None and limit.fuzz_score < grounding.RAPIDFUZZ_THRESHOLD
    assert FABRICATED_QUOTE not in AUDIT_LABELS_SEEN  # never reached the audit LLM


def test_skipped_limit_span_does_not_cap():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PASS)
    SPAN_RESULTS[LIMIT_QUOTE] = grounding.SpanAuditResult(GroundingStatus.SKIPPED, None)
    claim = _claim(
        [
            AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support"),
            AuditedSpan(source_text=LIMIT_QUOTE, source_section="Appendix B", role="limit"),
        ],
        _checklist(has_limit=True),
    )
    [final] = _ground(claim)
    assert final.label == ClaimLabel.SUPPORTED and final.cap_reason is None


def test_rollup_ignores_limit_spans_so_an_ungrounded_support_quote_stays_missing():
    """A passing limit span must not rescue a claim whose support quote is fabricated."""
    SPAN_RESULTS[LIMIT_QUOTE] = _result(GroundingStatus.PASS, "refutes")
    claim = _claim(
        [
            AuditedSpan(source_text=FABRICATED_QUOTE, source_section="Table 9", role="support"),
            AuditedSpan(source_text=LIMIT_QUOTE, source_section="Appendix B", role="limit"),
        ],
        _checklist(has_limit=True),
    )

    [final] = _ground(claim)

    assert final.grounding_status == GroundingStatus.FAIL
    assert final.missing is True
    assert final.reason == "The auditor's cited passages do not appear in the paper as quoted."
    # The cap itself still records what it did; effective_status is not_supported via `missing`.
    assert final.cap_reason == "limit" and final.label == ClaimLabel.PARTIALLY_SUPPORTED


def test_span_less_claim_rolls_up_to_fail_and_missing():
    claim = _claim([], _checklist())
    [final] = _ground(claim)
    assert final.grounding_status == GroundingStatus.FAIL and final.missing is True
    assert final.label == ClaimLabel.SUPPORTED  # label unchanged; effective_status handles `missing`


def test_scope_cap_without_any_limit_span():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PARTIAL, "supports")
    claim = _claim(
        [AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support")],
        _checklist(scope="no"),
    )
    [final] = _ground(claim)
    assert final.label == ClaimLabel.PARTIALLY_SUPPORTED and final.cap_reason == "scope"
    # Partial grounding roll-up is unchanged: Partial, not missing.
    assert final.grounding_status == GroundingStatus.PARTIAL and final.missing is False


def test_comparison_cap_lowers_to_not_supported_without_touching_grounding():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PASS)
    claim = _claim(
        [AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support")],
        _checklist(comparison="no"),
    )
    [final] = _ground(claim)
    assert final.label == ClaimLabel.NOT_SUPPORTED and final.cap_reason == "comparison"
    assert final.auditor_verdict == ClaimLabel.SUPPORTED
    assert final.grounding_status == GroundingStatus.PASS and final.missing is False


def test_unparsed_checklist_never_caps_through_the_pipeline():
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PASS)
    claim = _claim(
        [AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support")],
        _checklist(status="unparsed", scope="no", comparison="no"),
    )
    [final] = _ground(claim)
    assert final.label == ClaimLabel.SUPPORTED and final.cap_reason is None


def test_trace_fields_do_not_change_status_or_label():
    """Same grounding outcome whether or not reasoning/model/fuzz are populated."""
    SPAN_RESULTS[SUPPORT_QUOTE] = grounding.SpanAuditResult(GroundingStatus.PARTIAL, "supports")  # no trace
    claim = _claim(
        [AuditedSpan(source_text=SUPPORT_QUOTE, source_section="Table 4", role="support")], _checklist()
    )
    [bare] = _ground(claim)
    SPAN_RESULTS[SUPPORT_QUOTE] = _result(GroundingStatus.PARTIAL, "supports", "long reasoning", "model-z")
    [traced] = _ground(claim)
    assert (bare.label, bare.grounding_status, bare.missing, bare.reason) == (
        traced.label,
        traced.grounding_status,
        traced.missing,
        traced.reason,
    )


def test_old_rows_without_new_keys_still_validate():
    old_span = {
        "source_text": "q",
        "source_section": "s",
        "section_header": None,
        "page_number": None,
        "grounding_status": "Pass",
        "stance": "supports",
    }
    span = EvidenceSpanFinal(**old_span)
    assert span.role is None and span.grounding_reasoning is None
    assert span.grounding_model is None and span.fuzz_score is None

    claim = ClaimFinal(
        claim_text_verbatim="c",
        claim_summary="s",
        label="supported",
        evidence_spans=[span],
        grounding_status="Pass",
    )
    assert claim.auditor_verdict is None and claim.cap_reason is None
    assert claim.audit_checklist is None and claim.audit_reasoning is None


def test_audit_checklist_json_shape_for_jsonb():
    dumped = _checklist(has_limit=True).model_dump(mode="json")
    assert dumped["checklist_status"] == "parsed"
    assert dumped["model_used"] == "auditor-x"
    assert dumped["auditor_verdict"] == "supported"
    # quotes are not duplicated into the checklist column
    assert "support_quote" not in dumped and "limit_quote" not in dumped
