"""Unit test for eval/replay_clean.py's --estimate token counting fix.

The Gemini Developer API's countTokens rejects a system_instruction in its
config (Vertex-only field); _estimate_tokens must never pass one, and must
still count the system prompt text by folding it into contents. No LLM
calls, no DB, no real PDFs.
"""
import asyncio

import pytest

from eval import replay_clean


class _FakeCountTokensResult:
    def __init__(self, total_tokens):
        self.total_tokens = total_tokens


def _fake_client(captured: dict):
    class FakeModels:
        async def count_tokens(self, model, contents, config=None):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return _FakeCountTokensResult(total_tokens=42)

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        aio = FakeAio()

    return FakeClient()


def test_estimate_tokens_never_sends_system_instruction_config(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(replay_clean.engine, "_build_client", lambda: _fake_client(captured))

    messages = [
        {"role": "system", "content": "SYSTEM PROMPT TEXT"},
        {"role": "user", "content": "window text"},
    ]

    result = asyncio.run(replay_clean._estimate_tokens(messages))

    assert result == 42
    assert captured["config"] is None


def test_estimate_tokens_counts_system_prompt_as_content(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(replay_clean.engine, "_build_client", lambda: _fake_client(captured))

    messages = [
        {"role": "system", "content": "SYSTEM PROMPT TEXT"},
        {"role": "user", "content": "window text"},
    ]

    asyncio.run(replay_clean._estimate_tokens(messages))

    contents = captured["contents"]
    texts = [part.text for content in contents for part in content.parts]
    assert "SYSTEM PROMPT TEXT" in texts
    assert "window text" in texts
    # system content must come first, as its own entry (not merged into the
    # user content), mirroring eval/replay_extract.py's own pattern.
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "SYSTEM PROMPT TEXT"
