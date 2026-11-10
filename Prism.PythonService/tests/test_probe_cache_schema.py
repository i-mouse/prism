"""Unit tests for eval/probe_cache_schema.py (the one-call cache + schema + low
thinking probe).

No network and no real caches: every test uses a fake SDK client. The probe's
request must carry cached_content, response_schema and thinking LOW and no
system_instruction/tools/tool_config; it sends exactly one request (no retry,
no fallback); the cache is deleted whichever way the request ends.
"""
import argparse
import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors, types

from eval import probe_cache_schema as probe
from eval.probe_cache_schema import ProbeOut

PAPER = "THE FULL PAPER TEXT. Table 2 reports 11 of 12."
CACHE_NAME = "cachedContents/probe123"


def _api_error(code: int) -> errors.APIError:
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": f"boom {code}", "status": "INVALID_ARGUMENT"}})


class FakeCaches:
    def __init__(self, events, create_error=None):
        self.events = events
        self.create_error = create_error
        self.deleted: list[str] = []

    async def create(self, *, model, config):
        self.events.append("create")
        if self.create_error is not None:
            raise self.create_error
        return SimpleNamespace(name=CACHE_NAME, usage_metadata=SimpleNamespace(total_token_count=13_125))

    async def delete(self, *, name):
        self.events.append("delete")
        self.deleted.append(name)


class FakeModels:
    def __init__(self, events, handler):
        self.events = events
        self.handler = handler
        self.calls: list[dict] = []

    async def generate_content(self, *, model, contents, config):
        self.events.append("generate")
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.handler()


def _response(parsed="default", cached=13_125):
    if parsed == "default":
        parsed = ProbeOut(answer="a", quotes=["q1", "q2"])
    usage = SimpleNamespace(
        prompt_token_count=13_200, candidates_token_count=60, thoughts_token_count=40,
        total_token_count=13_300, cached_content_token_count=cached, tool_use_prompt_token_count=None,
    )
    return SimpleNamespace(
        parsed=parsed, text='{"answer": "a", "quotes": []}', usage_metadata=usage,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))],
    )


def _fake_client(handler=None, create_error=None):
    events: list = []
    caches = FakeCaches(events, create_error=create_error)
    models = FakeModels(events, handler or (lambda: _response()))
    return SimpleNamespace(aio=SimpleNamespace(caches=caches, models=models)), caches, models, events


def test_probe_config_has_cache_schema_and_low_thinking_only():
    config = probe.build_probe_config(CACHE_NAME)
    assert config.cached_content == CACHE_NAME
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ProbeOut
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert config.system_instruction is None
    assert config.tools is None
    assert config.tool_config is None


def test_ok_run_sends_one_request_then_deletes_cache():
    client, caches, models, events = _fake_client()
    result = asyncio.run(probe.run(client, PAPER))

    assert result.ok and result.fail_reason is None
    assert events == ["create", "generate", "delete"]
    assert caches.deleted == [CACHE_NAME]
    (call,) = models.calls
    assert call["model"] == "gemini-3.6-flash"
    config = call["config"]
    assert config.cached_content == CACHE_NAME
    assert config.response_schema is ProbeOut and config.response_mime_type == "application/json"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert config.system_instruction is None and config.tools is None and config.tool_config is None
    assert [c.parts[0].text for c in call["contents"]] == [probe.PROBE_PROMPT]
    assert result.parsed_is_probe_out and result.finish_reason == "STOP"
    assert result.usage["cached_tokens"] == 13_125
    assert result.call_inr > 0 and result.storage_inr > 0 and result.total_inr > result.call_inr


@pytest.mark.parametrize("code", [400, 503])
def test_api_error_is_one_request_no_retry_and_cache_deleted(code):
    def boom():
        raise _api_error(code)

    client, caches, models, events = _fake_client(handler=boom)
    result = asyncio.run(probe.run(client, PAPER))

    assert not result.ok and result.fail_reason == probe.FAIL_API_ERROR
    assert str(code) in result.error
    assert len(models.calls) == 1  # no retry, no fallback model, even on a retryable status
    assert events == ["create", "generate", "delete"]
    assert caches.deleted == [CACHE_NAME]


def test_unexpected_exception_still_deletes_cache():
    def boom():
        raise RuntimeError("kaboom")

    client, caches, models, _ = _fake_client(handler=boom)
    result = asyncio.run(probe.run(client, PAPER))
    assert result.fail_reason == probe.FAIL_API_ERROR and "kaboom" in result.error
    assert caches.deleted == [CACHE_NAME]


def test_unparsed_response_is_parse_failed():
    client, caches, _, _ = _fake_client(handler=lambda: _response(parsed=None))
    result = asyncio.run(probe.run(client, PAPER))
    assert not result.ok and result.fail_reason == probe.FAIL_PARSE_FAILED
    assert not result.parsed_is_probe_out
    assert caches.deleted == [CACHE_NAME]


def test_zero_cached_tokens_is_no_cached_tokens():
    client, caches, _, _ = _fake_client(handler=lambda: _response(cached=0))
    result = asyncio.run(probe.run(client, PAPER))
    assert not result.ok and result.fail_reason == probe.FAIL_NO_CACHED_TOKENS
    assert caches.deleted == [CACHE_NAME]


def test_cache_creation_failure_sends_no_request():
    client, caches, models, events = _fake_client(create_error=_api_error(400))
    result = asyncio.run(probe.run(client, PAPER))
    assert not result.ok and result.fail_reason == probe.FAIL_CACHE_NOT_CREATED
    assert "400" in result.error
    assert models.calls == [] and result.requests_sent == 0
    assert events == ["create"]


def test_estimate_is_under_the_cap_and_splits_out_storage():
    est = probe.estimate_inr()
    assert 0 < est["total_inr"] < probe.MAX_INR
    assert est["storage_inr"] > 0
    assert est["total_inr"] == pytest.approx(est["call_inr"] + est["storage_inr"] + est["creation_inr"])


def _no_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("network/client/paper access is not allowed here")

    monkeypatch.setattr(probe.engine, "_build_client", forbidden)
    monkeypatch.setattr(probe, "_load_paper_text", forbidden)


def test_estimate_flag_builds_no_client(monkeypatch, capsys):
    _no_network(monkeypatch)
    assert asyncio.run(probe._main(argparse.Namespace(estimate=True))) == 0
    out = capsys.readouterr().out
    assert "ASSUMPTION" in out and "storage" in out and "TOTAL expected" in out


def test_refuses_to_send_when_estimate_is_over_the_cap(monkeypatch, capsys):
    _no_network(monkeypatch)
    monkeypatch.setattr(probe, "MAX_INR", 0.0001)
    assert asyncio.run(probe._main(argparse.Namespace(estimate=False))) == 2
    assert "REFUSED" in capsys.readouterr().out
