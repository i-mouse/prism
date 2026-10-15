"""Unit tests for extraction/engine.py's usage_metadata/finish_reason
side-channel logging in _call_gemini_json and _call_gemini_structured.

Covers: the captured data reaches only the log write, never the function's
return value; a response missing usage_metadata/candidates degrades to None
rather than raising. No LLM calls - google.genai.Client is faked at the
_build_client/_generate_with_fallback boundary.
"""
import asyncio
import json
from types import SimpleNamespace

from extraction import engine
from extraction.schemas import ClaimLLM, ClaimLabel, EvidenceSpanLLM


def _fake_response(text: str, prompt_tokens=10, output_tokens=20, thought_tokens=0, total_tokens=30, finish_reason="STOP", parsed=None):
    usage = SimpleNamespace(
        prompt_token_count=prompt_tokens,
        candidates_token_count=output_tokens,
        thoughts_token_count=thought_tokens,
        total_token_count=total_tokens,
    )
    candidate = SimpleNamespace(finish_reason=SimpleNamespace(value=finish_reason) if finish_reason else None)
    return SimpleNamespace(text=text, usage_metadata=usage, candidates=[candidate], parsed=parsed)


def test_extract_usage_and_finish_reason_reads_expected_fields():
    response = _fake_response("{}", prompt_tokens=5, output_tokens=7, thought_tokens=1, total_tokens=13, finish_reason="STOP")
    usage, finish_reason = engine._extract_usage_and_finish_reason(response)
    assert usage == {"prompt_tokens": 5, "output_tokens": 7, "thought_tokens": 1, "total_tokens": 13}
    assert finish_reason == "STOP"


def test_extract_usage_and_finish_reason_handles_missing_fields_gracefully():
    bare_response = SimpleNamespace(text="{}")  # no usage_metadata, no candidates
    usage, finish_reason = engine._extract_usage_and_finish_reason(bare_response)
    assert usage is None
    assert finish_reason is None


def test_call_gemini_json_return_value_unaffected_by_usage_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)

    async def fake_generate_with_fallback(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        return _fake_response(json.dumps({"claims": []}), finish_reason="MAX_TOKENS"), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_generate_with_fallback)
    monkeypatch.setattr(engine, "_build_client", lambda: object())

    result = asyncio.run(engine._call_gemini_json(
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        chat_id="chat-1", correlation_id=None, log_subdir="extraction",
        model_name="m", fallback_model="fb",
    ))

    assert result == {"claims": []}  # unaffected - usage/finish_reason are side-channel only

    log_files = list((tmp_path / "extraction").glob("*.json"))
    assert len(log_files) == 1
    logged = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert logged["finish_reason"] == "MAX_TOKENS"
    assert logged["usage"]["prompt_tokens"] == 10


def test_call_gemini_structured_return_value_unaffected_by_usage_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)

    claim = ClaimLLM(
        claim_text_verbatim="x", claim_summary="y", label=ClaimLabel.SUPPORTED,
        evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="s")],
    )

    async def fake_generate_with_fallback(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        return _fake_response("irrelevant", finish_reason="STOP", parsed=claim), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_generate_with_fallback)
    monkeypatch.setattr(engine, "_build_client", lambda: object())

    result = asyncio.run(engine._call_gemini_structured(
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        response_schema=ClaimLLM, chat_id="chat-1", correlation_id=None,
        log_subdir="structure", model_name="m", fallback_model="fb",
    ))

    assert result is claim

    log_files = list((tmp_path / "structure").glob("*.json"))
    assert len(log_files) == 1
    logged = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert logged["finish_reason"] == "STOP"
    assert logged["usage"]["total_tokens"] == 30
