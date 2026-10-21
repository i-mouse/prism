"""Unit tests for Experiment 1's auditor thinking_level knob.

Covers: config validation fails fast on a bad value, and the audit call's
GenerateContentConfig is byte-identical to pre-Experiment-1 behavior when
thinking_level is not given.
"""
import asyncio

import pytest
from google.genai import types

from config import PrismSettings
from extraction.engine import _call_gemini_freetext


def test_auditor_thinking_level_rejects_invalid_value():
    with pytest.raises(ValueError, match="auditor_thinking_level"):
        PrismSettings(auditor_thinking_level="minimal")


def test_auditor_thinking_level_accepts_unset():
    assert PrismSettings(auditor_thinking_level=None).auditor_thinking_level is None


@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_auditor_thinking_level_accepts_valid_values(level):
    assert PrismSettings(auditor_thinking_level=level).auditor_thinking_level == level


class _FakeResponse:
    text = "ok"


def _fake_client(captured_config: dict):
    class FakeModels:
        async def generate_content(self, model, contents, config):
            captured_config["config"] = config
            return _FakeResponse()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        aio = FakeAio()

    return FakeClient()


def test_call_gemini_freetext_sends_no_thinking_config_when_unset(monkeypatch):
    captured_config: dict = {}
    monkeypatch.setattr("extraction.engine._build_client", lambda: _fake_client(captured_config))

    asyncio.run(
        _call_gemini_freetext(
            messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            chat_id="chat-1",
            correlation_id=None,
            log_subdir="audit",
            model_name="gemini-3.6-flash",
            fallback_model="gemini-3.1-flash-lite",
        )
    )

    sent_config = captured_config["config"]
    assert sent_config.thinking_config is None
    assert sent_config == types.GenerateContentConfig(system_instruction="sys")


def test_call_gemini_freetext_sends_thinking_level_when_given(monkeypatch):
    captured_config: dict = {}
    monkeypatch.setattr("extraction.engine._build_client", lambda: _fake_client(captured_config))

    asyncio.run(
        _call_gemini_freetext(
            messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            chat_id="chat-1",
            correlation_id=None,
            log_subdir="audit",
            model_name="gemini-3.6-flash",
            fallback_model="gemini-3.1-flash-lite",
            thinking_level="high",
        )
    )

    sent_config = captured_config["config"]
    assert sent_config.thinking_config == types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
