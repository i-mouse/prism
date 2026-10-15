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

from google.genai import types as genai_types

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

    async def fake_generate_with_fallback(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None, fallback_config=None):
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


def test_thinking_level_applies_to_primary_only_not_fallback(monkeypatch, tmp_path):
    """Experiment 3 amendment 1: a thinking_level override on
    _call_gemini_structured must reach the primary model's config but never
    the fallback model's - the fallback call gets its own config with no
    thinking_config at all, today's unmodified behavior."""
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)

    claim = ClaimLLM(
        claim_text_verbatim="x", claim_summary="y", label=ClaimLabel.SUPPORTED,
        evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="s")],
    )
    captured = {}

    async def fake_generate_with_fallback(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None, fallback_config=None):
        captured["config"] = config
        captured["fallback_config"] = fallback_config
        return _fake_response("irrelevant", finish_reason="STOP", parsed=claim), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_generate_with_fallback)
    monkeypatch.setattr(engine, "_build_client", lambda: object())

    asyncio.run(engine._call_gemini_structured(
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        response_schema=ClaimLLM, chat_id="chat-1", correlation_id=None,
        log_subdir="structure", model_name="m", fallback_model="fb",
        thinking_level="low",
    ))

    assert captured["config"].thinking_config is not None
    assert captured["config"].thinking_config.thinking_level == genai_types.ThinkingLevel.LOW
    assert captured["fallback_config"] is not None
    assert captured["fallback_config"].thinking_config is None


def test_thinking_level_unset_passes_no_fallback_config_override(monkeypatch, tmp_path):
    """When thinking_level is unset (the default), _generate_with_fallback is
    called exactly as before this parameter existed - no fallback_config
    kwarg at all - so code that monkey-patches _generate_with_fallback with
    the old signature (eval/replay_audit.py, eval/replay_extract.py) is
    unaffected."""
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)

    claim = ClaimLLM(
        claim_text_verbatim="x", claim_summary="y", label=ClaimLabel.SUPPORTED,
        evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="s")],
    )

    async def fake_generate_with_fallback_old_signature(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        return _fake_response("irrelevant", finish_reason="STOP", parsed=claim), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_generate_with_fallback_old_signature)
    monkeypatch.setattr(engine, "_build_client", lambda: object())

    result = asyncio.run(engine._call_gemini_structured(
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        response_schema=ClaimLLM, chat_id="chat-1", correlation_id=None,
        log_subdir="structure", model_name="m", fallback_model="fb",
    ))

    assert result is claim


def test_call_gemini_structured_logs_sentence_count_for_pass2_schema(monkeypatch, tmp_path):
    """AG review fix: response_item_count for pass-2's SentenceListLLM must
    be the real sentence count, not 0 (it has no .claims/.metadata, so the
    old claims-then-metadata check always fell through to 0)."""
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)
    from extraction.pass2 import SentenceListLLM

    parsed = SentenceListLLM(sentences=["s1", "s2", "s3"])

    async def fake_generate_with_fallback(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None, fallback_config=None):
        return _fake_response("irrelevant", finish_reason="STOP", parsed=parsed), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_generate_with_fallback)
    monkeypatch.setattr(engine, "_build_client", lambda: object())

    result = asyncio.run(engine._call_gemini_structured(
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        response_schema=SentenceListLLM, chat_id="chat-1", correlation_id=None,
        log_subdir="pass2", model_name="m", fallback_model="fb",
    ))

    assert result is parsed
    log_files = list((tmp_path / "pass2").glob("*.json"))
    assert len(log_files) == 1
    logged = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert logged["response_item_count"] == 3
