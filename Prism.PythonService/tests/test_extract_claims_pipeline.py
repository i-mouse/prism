"""Smoke test for extract_claims' three-call pipeline (extractor -> audit -> structure)."""
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
        "Reasoning for claim one.\n\nVERDICT: supported\n\n"
        "QUOTE: Claim one verbatim.\nSECTION: Section 1"
    ),
    "Claim two verbatim.": (
        "Reasoning for claim two.\n\nVERDICT: not_supported\n\n"
        "QUOTE: Some other passage.\nSECTION: Section 2"
    ),
}


def _structured_claim(claim_text_verbatim: str, claim_summary: str, label: ClaimLabel) -> ClaimLLM:
    return ClaimLLM(
        claim_text_verbatim=claim_text_verbatim,
        claim_summary=claim_summary,
        label=label,
        evidence_spans=[EvidenceSpanLLM(source_text="quote", source_section="Section 1")],
    )


def _user_content(messages: list[dict]) -> str:
    return next(m["content"] for m in messages if m["role"] == "user")


def test_extract_claims_runs_extractor_audit_structure_pipeline(monkeypatch):
    concurrent = 0
    max_concurrent = 0
    calls = {"json": 0, "freetext": 0, "structured": 0}

    async def fake_call_gemini_json(messages, chat_id, correlation_id, log_subdir):
        calls["json"] += 1
        assert log_subdir == "extraction"
        return EXTRACTOR_RESULT

    async def fake_call_gemini_freetext(messages, chat_id, correlation_id, log_subdir):
        nonlocal concurrent, max_concurrent
        assert log_subdir == "audit"
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        await asyncio.sleep(0.01)
        concurrent -= 1
        calls["freetext"] += 1

        user_msg = _user_content(messages)
        for claim_text, audit_text in AUDIT_TEXT_BY_CLAIM.items():
            if claim_text in user_msg:
                return audit_text
        raise AssertionError(f"unrecognized claim in audit call: {user_msg!r}")

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir):
        assert log_subdir == "structure"
        assert response_schema is ClaimLLM
        calls["structured"] += 1

        user_msg = _user_content(messages)
        if "Claim one verbatim." in user_msg:
            return _structured_claim("Claim one verbatim.", "Claim one summary", ClaimLabel.SUPPORTED)
        return _structured_claim("Claim two verbatim.", "Claim two summary", ClaimLabel.NOT_SUPPORTED)

    monkeypatch.setattr(engine, "_call_gemini_json", fake_call_gemini_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_call_gemini_freetext)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)

    result = asyncio.run(engine.extract_claims(paper_text="the full paper text", chat_id="chat-1"))

    assert calls == {"json": 1, "freetext": 2, "structured": 2}
    assert max_concurrent <= engine.AUDIT_STRUCTURE_CONCURRENCY

    assert len(result.claims) == 2
    labels = {claim.claim_text_verbatim: claim.label for claim in result.claims}
    assert labels["Claim one verbatim."] == ClaimLabel.SUPPORTED
    assert labels["Claim two verbatim."] == ClaimLabel.NOT_SUPPORTED
