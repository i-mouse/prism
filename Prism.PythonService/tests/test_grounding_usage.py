"""Unit tests for extraction/grounding.py's LiteLLM usage capture and the
_usage_observer hook. Fake response objects only - no network."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from extraction import grounding

_VERDICT = json.dumps({"reasoning": "r", "stance": "supports", "verdict": "Pass", "reason": "ok"})


def _litellm_response(model="openai/gpt-oss-20b", prompt=100, completion=50, total=150, cached=None, reasoning=None, content=_VERDICT):
    usage = SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached) if cached is not None else None,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning) if reasoning is not None else None,
    )
    return SimpleNamespace(model=model, usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_extract_litellm_usage_reads_all_fields():
    usage = grounding._extract_litellm_usage(_litellm_response(cached=40, reasoning=30))
    assert usage == {
        "prompt_tokens": 100, "output_tokens": 50, "thought_tokens": 30, "total_tokens": 150,
        "cached_tokens": 40, "model": "openai/gpt-oss-20b",
    }


def test_extract_litellm_usage_missing_details_stay_null():
    usage = grounding._extract_litellm_usage(_litellm_response(cached=None, reasoning=None))
    assert usage["cached_tokens"] is None
    assert usage["thought_tokens"] is None


def test_extract_litellm_usage_no_usage_or_broken_response_returns_none(caplog):
    assert grounding._extract_litellm_usage(SimpleNamespace(model="m")) is None

    class Exploding:
        @property
        def usage(self):
            raise RuntimeError("boom")

    with caplog.at_level("WARNING", logger="extraction.grounding"):
        assert grounding._extract_litellm_usage(Exploding()) is None
    assert len(caplog.records) == 1


def _run_audit(monkeypatch, response):
    async def fake_acompletion(**kwargs):
        return response

    monkeypatch.setattr(grounding.litellm, "acompletion", fake_acompletion)
    return asyncio.run(grounding._call_litellm_audit(
        messages=[{"role": "user", "content": "q"}], audit_model="groq/openai/gpt-oss-20b",
        fallback_model="gemini/gemini-3.1-flash-lite", gemini_api_key="k", span_source_section="s",
    ))


def test_observer_receives_usage_from_audit_call(monkeypatch):
    seen: list[dict] = []
    monkeypatch.setattr(grounding, "_usage_observer", seen.append)

    verdict = _run_audit(monkeypatch, _litellm_response(model="gemini-3.1-flash-lite", cached=10))

    assert verdict.verdict == "Pass"
    assert len(seen) == 1
    assert seen[0]["model"] == "gemini-3.1-flash-lite"
    assert seen[0]["cached_tokens"] == 10


def test_observer_that_raises_does_not_change_the_result(monkeypatch, caplog):
    def bad_observer(_usage):
        raise RuntimeError("observer bug")

    monkeypatch.setattr(grounding, "_usage_observer", bad_observer)

    with caplog.at_level("WARNING", logger="extraction.grounding"):
        verdict = _run_audit(monkeypatch, _litellm_response())

    assert verdict.verdict == "Pass"
    assert len(caplog.records) == 1


def test_no_observer_set_is_a_no_op(monkeypatch):
    monkeypatch.setattr(grounding, "_usage_observer", None)
    assert _run_audit(monkeypatch, _litellm_response()).verdict == "Pass"


def test_usage_is_reported_even_when_verdict_parsing_fails(monkeypatch):
    seen: list[dict] = []
    monkeypatch.setattr(grounding, "_usage_observer", seen.append)

    with pytest.raises(Exception):
        _run_audit(monkeypatch, _litellm_response(content="not json"))

    assert len(seen) == 1
