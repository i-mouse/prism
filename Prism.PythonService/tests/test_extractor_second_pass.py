"""Unit tests for Experiment 3's EXTRACTOR_SECOND_PASS flag.

Covers: the flag off reproduces today's exact prompt hash (cb3272cce551) and
today's exact extract_claims behavior (no pass-2 calls made, pass-1 claims
unchanged), and flipping it on changes the hash to a distinct value. No LLM
calls - extraction.engine._call_gemini_json/_call_gemini_structured are
faked.
"""
import asyncio

from config import settings
from extraction import engine
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLabel, ClaimLLM, EvidenceSpanLLM

EXTRACTOR_RESULT = {
    "claims": [
        {"claim_text_verbatim": "Claim one verbatim.", "claim_summary": "Claim one summary"},
    ]
}


def _structured_claim(claim_text_verbatim: str, claim_summary: str) -> ClaimLLM:
    return ClaimLLM(
        claim_text_verbatim=claim_text_verbatim,
        claim_summary=claim_summary,
        label=ClaimLabel.SUPPORTED,
        evidence_spans=[EvidenceSpanLLM(source_text="quote", source_section="Section 1")],
    )


def test_flag_off_reproduces_todays_exact_prompt_hash():
    assert get_prompt_version(extractor_second_pass=False) == "cb3272cce551"
    assert get_prompt_version() == "cb3272cce551"  # settings.extractor_second_pass defaults False


def test_flag_on_changes_the_hash():
    off_hash = get_prompt_version(extractor_second_pass=False)
    on_hash = get_prompt_version(extractor_second_pass=True)
    assert off_hash != on_hash


def test_flag_off_extract_claims_never_calls_pass2(monkeypatch):
    """With the flag off, extract_claims must behave exactly as before this
    change: no windowing, no pass-2 calls, pass-1 claims pass through
    untouched (no 'pass' key added)."""
    monkeypatch.setattr(settings, "extractor_second_pass", False)
    pass2_called = False

    async def fake_call_gemini_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return EXTRACTOR_RESULT

    async def fake_call_gemini_freetext(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        return "Reasoning.\n\nVERDICT: supported\n\nQUOTE: Claim one verbatim.\nSECTION: Section 1"

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        nonlocal pass2_called
        if log_subdir == "pass2":
            pass2_called = True
        return _structured_claim("Claim one verbatim.", "Claim one summary")

    async def fake_run_pass2(*args, **kwargs):
        nonlocal pass2_called
        pass2_called = True
        return [], 0

    monkeypatch.setattr(engine, "_call_gemini_json", fake_call_gemini_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_call_gemini_freetext)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)
    monkeypatch.setattr("extraction.pass2.run_pass2", fake_run_pass2)

    result = asyncio.run(engine.extract_claims(paper_text="the full paper text", chat_id="chat-1"))

    assert pass2_called is False
    assert len(result.claims) == 1
    assert result.claims[0].claim_text_verbatim == "Claim one verbatim."


def test_flag_on_extract_claims_calls_pass2_and_merges(monkeypatch):
    monkeypatch.setattr(settings, "extractor_second_pass", True)

    async def fake_call_gemini_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return EXTRACTOR_RESULT

    async def fake_run_pass2(paper_text, chat_id, correlation_id=None):
        return ["A brand new pass-2 sentence never seen in pass 1."], 0

    structured_calls = []

    async def fake_call_gemini_freetext(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        return "Reasoning.\n\nVERDICT: supported\n\nQUOTE: x\nSECTION: Section 1"

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        structured_calls.append(log_subdir)
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        claim_text = user_msg.split("CLAIM_TEXT_VERBATIM: ")[1].split("\n")[0]
        return _structured_claim(claim_text, "summary")

    monkeypatch.setattr(engine, "_call_gemini_json", fake_call_gemini_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_call_gemini_freetext)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)
    monkeypatch.setattr("extraction.pass2.run_pass2", fake_run_pass2)
    # merge_pass2_claims runs the real verbatim-grounding check, so paper_text
    # must actually contain the fake pass-2 sentence.
    paper_text = "Preamble. A brand new pass-2 sentence never seen in pass 1. Epilogue."

    result = asyncio.run(engine.extract_claims(paper_text=paper_text, chat_id="chat-1"))

    assert len(result.claims) == 2
    texts = {c.claim_text_verbatim for c in result.claims}
    assert "Claim one verbatim." in texts
    assert "A brand new pass-2 sentence never seen in pass 1." in texts
