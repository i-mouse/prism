"""Smoke tests for extract_claims (extractor -> audit -> claim built from the checklist).

The structurer (Call #4) is a fallback: it must run only when the audit's
VERDICT line can't be read in code.
"""
import asyncio

from extraction import engine
from extraction.schemas import ClaimLabel, ClaimLLM, EvidenceSpanLLM

EXTRACTOR_RESULT = {
    "claims": [
        {"claim_text_verbatim": "Claim one verbatim.", "claim_summary": "Claim one summary"},
        {"claim_text_verbatim": "Claim two verbatim.", "claim_summary": "Claim two summary"},
    ]
}

AUDIT_TEXT_BY_CLAIM = {
    "Claim one verbatim.": (
        "Reasoning for claim one.\n\n"
        "SUPPORT_QUOTE: Claim one is backed by this result.\n"
        "SUPPORT_SECTION: Table 1\n"
        "LIMIT_QUOTE: NONE\n"
        "LIMIT_SECTION: NONE\n"
        "SCOPE_MATCH: yes\n"
        "COMPARISON_TESTED: n/a\n"
        "VERDICT: supported"
    ),
    "Claim two verbatim.": (
        "Reasoning for claim two.\n\n"
        "SUPPORT_QUOTE: NONE\n"
        "SUPPORT_SECTION: NONE\n"
        "LIMIT_QUOTE: Some narrowing passage.\n"
        "LIMIT_SECTION: Section 2\n"
        "SCOPE_MATCH: no\n"
        "COMPARISON_TESTED: no\n"
        "VERDICT: not_supported"
    ),
}


def _user_content(messages: list[dict]) -> str:
    return next(m["content"] for m in messages if m["role"] == "user")


def _patch_engine(monkeypatch, audit_text_by_claim, calls, structured_result=None, seen_audit_messages=None):
    concurrent = 0
    max_concurrent = [0]

    async def fake_call_gemini_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        calls["json"] += 1
        assert log_subdir == "extraction"
        return EXTRACTOR_RESULT

    async def fake_call_gemini_freetext(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        nonlocal concurrent
        assert log_subdir == "audit"
        concurrent += 1
        max_concurrent[0] = max(max_concurrent[0], concurrent)
        await asyncio.sleep(0.01)
        concurrent -= 1
        calls["freetext"] += 1
        if seen_audit_messages is not None:
            seen_audit_messages.append(messages)

        user_msg = _user_content(messages)
        for claim_text, audit_text in audit_text_by_claim.items():
            if claim_text in user_msg:
                return audit_text, "audit-model-x"
        raise AssertionError(f"unrecognized claim in audit call: {user_msg!r}")

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        assert log_subdir == "structure"
        assert response_schema is ClaimLLM
        calls["structured"] += 1
        return structured_result(_user_content(messages))

    monkeypatch.setattr(engine, "_call_gemini_json", fake_call_gemini_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_call_gemini_freetext)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)
    return max_concurrent


def test_extract_claims_builds_claims_from_checklist_without_structurer(monkeypatch):
    calls = {"json": 0, "freetext": 0, "structured": 0}
    seen: list[list[dict]] = []
    max_concurrent = _patch_engine(monkeypatch, AUDIT_TEXT_BY_CLAIM, calls, seen_audit_messages=seen)

    result = asyncio.run(engine.extract_claims(paper_text="the full paper text", chat_id="chat-1"))

    assert calls == {"json": 1, "freetext": 2, "structured": 0}
    assert max_concurrent[0] <= engine.AUDIT_STRUCTURE_CONCURRENCY

    # The auditor no longer receives the display summary.
    for messages in seen:
        content = _user_content(messages)
        assert "CLAIM_SUMMARY" not in content
        assert "Claim one summary" not in content and "Claim two summary" not in content

    assert len(result.claims) == 2
    by_text = {claim.claim_text_verbatim: claim for claim in result.claims}

    one = by_text["Claim one verbatim."]
    assert one.auditor_verdict == ClaimLabel.SUPPORTED
    assert one.claim_summary == "Claim one summary"
    assert one.checklist.checklist_status == "parsed"
    assert one.checklist.model_used == "audit-model-x"
    assert [(s.role, s.source_section) for s in one.evidence_spans] == [("support", "Table 1")]
    assert one.audit_reasoning == AUDIT_TEXT_BY_CLAIM["Claim one verbatim."]

    two = by_text["Claim two verbatim."]
    assert two.auditor_verdict == ClaimLabel.NOT_SUPPORTED
    assert [(s.role, s.source_text) for s in two.evidence_spans] == [("limit", "Some narrowing passage.")]
    assert two.checklist.comparison_tested == "no"


def test_unparsed_checklist_keeps_auditor_verdict_and_does_not_call_structurer(monkeypatch, capsys):
    audit_texts = {
        "Claim one verbatim.": "Prose only.\n\nVERDICT: partially_supported",
        "Claim two verbatim.": AUDIT_TEXT_BY_CLAIM["Claim two verbatim."],
    }
    calls = {"json": 0, "freetext": 0, "structured": 0}
    _patch_engine(monkeypatch, audit_texts, calls)

    result = asyncio.run(engine.extract_claims(paper_text="paper", chat_id="chat-1"))

    assert calls["structured"] == 0
    one = next(c for c in result.claims if c.claim_text_verbatim == "Claim one verbatim.")
    assert one.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED
    assert one.checklist.checklist_status == "unparsed"
    assert "checklist_unparsed" in capsys.readouterr().out


def test_structurer_fallback_runs_and_is_logged_when_verdict_unreadable(monkeypatch, capsys):
    audit_texts = {
        "Claim one verbatim.": "The model forgot the checklist entirely.",
        "Claim two verbatim.": AUDIT_TEXT_BY_CLAIM["Claim two verbatim."],
    }
    calls = {"json": 0, "freetext": 0, "structured": 0}

    def structured_result(user_msg: str) -> ClaimLLM:
        return ClaimLLM(
            claim_text_verbatim="Claim one verbatim.",
            claim_summary="Claim one summary",
            label=ClaimLabel.SUPPORTED,
            evidence_spans=[EvidenceSpanLLM(source_text="quote", source_section="Section 1")],
        )

    _patch_engine(monkeypatch, audit_texts, calls, structured_result=structured_result)

    result = asyncio.run(engine.extract_claims(paper_text="paper", chat_id="chat-1", correlation_id="corr-9"))

    assert calls["structured"] == 1  # only the claim whose VERDICT was unreadable
    one = next(c for c in result.claims if c.claim_text_verbatim == "Claim one verbatim.")
    assert one.auditor_verdict == ClaimLabel.SUPPORTED
    assert one.checklist.checklist_status == "unparsed"
    assert [(s.role, s.source_text) for s in one.evidence_spans] == [("support", "quote")]

    out = capsys.readouterr().out
    fallback_lines = [line for line in out.splitlines() if "structurer_fallback" in line]
    assert len(fallback_lines) == 1
    assert "claim_number=1" in fallback_lines[0]
    assert "correlation_id=corr-9" in fallback_lines[0]
    assert "reason=verdict_unreadable" in fallback_lines[0]
    assert "claim_fingerprint=" in fallback_lines[0]
