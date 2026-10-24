"""Unit tests for explicit context caching of the auditor call
(extraction/context_cache.py and its wiring in extraction/engine.py).

No network and no real caches.create: every test uses a fake SDK client. The
flag (extract_claims context_cache=...) defaults off; with it off the
request must be exactly what it was before caching existed.
"""
import asyncio
import logging
from types import SimpleNamespace

import pytest
from google.genai import errors, types

from eval.replay_audit import CapExceeded
from extraction import context_cache, engine
from extraction.context_cache import CacheFailed, ContextCacheStats, PaperCache, paper_context_cache, ttl_for_claims
from extraction.prompt_loader import build_gemini_messages_for_audit
from extraction.schemas import ClaimLabel, ClaimLLM, EvidenceSpanLLM

PAPER = "THE FULL PAPER TEXT. Table 2 reports 11 of 12."
MODEL = "gemini-3.6-flash"
FALLBACK_MODEL = "gemini-3.1-flash-lite"
CACHE_NAME = "cachedContents/abc123"


def _api_error(code: int) -> errors.APIError:
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": f"boom {code}", "status": "INVALID_ARGUMENT"}})


class FakeCaches:
    def __init__(self, events: list, create_error: Exception | None = None, tokens: int | None = 40_000,
                 delete_error: Exception | None = None):
        self.events = events
        self.create_error = create_error
        self.tokens = tokens
        self.delete_error = delete_error
        self.created: list[dict] = []
        self.deleted: list[str] = []

    async def create(self, *, model, config):
        self.events.append("create")
        if self.create_error is not None:
            raise self.create_error
        self.created.append({"model": model, "config": config})
        usage = SimpleNamespace(total_token_count=self.tokens)
        return SimpleNamespace(name=CACHE_NAME, usage_metadata=usage)

    async def delete(self, *, name):
        self.events.append("delete")
        self.deleted.append(name)
        if self.delete_error is not None:
            raise self.delete_error


class FakeModels:
    """handler(model, contents, config) -> response or raises."""

    def __init__(self, events: list, handler=None):
        self.events = events
        self.calls: list[dict] = []
        self.handler = handler or (lambda model, contents, config: _response(config))

    async def generate_content(self, *, model, contents, config):
        self.events.append("generate")
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.handler(model, contents, config)


def _response(config, text="Reasoning.\n\nVERDICT: supported\n\nQUOTE: q\nSECTION: s"):
    cached = 39_000 if getattr(config, "cached_content", None) else 0
    usage = SimpleNamespace(
        prompt_token_count=40_000, candidates_token_count=10, thoughts_token_count=0,
        total_token_count=40_010, cached_content_token_count=cached, tool_use_prompt_token_count=None,
    )
    return SimpleNamespace(text=text, usage_metadata=usage)


def _fake_client(create_error=None, tokens=40_000, handler=None, delete_error=None):
    events: list = []
    caches = FakeCaches(events, create_error=create_error, tokens=tokens, delete_error=delete_error)
    models = FakeModels(events, handler)
    client = SimpleNamespace(aio=SimpleNamespace(caches=caches, models=models))
    return client, caches, models, events


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(engine, "BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr(engine.settings, "llm_claim_audit_model", MODEL)
    monkeypatch.setattr(engine.settings, "llm_claim_audit_fallback_model", FALLBACK_MODEL)


def _system_prompt() -> str:
    return build_gemini_messages_for_audit(PAPER, "c", "s")[0]["content"]


async def _audit_call(client, paper_cache, claim="Claim A.", summary="Sum A", monkeypatch=None):
    messages = build_gemini_messages_for_audit(PAPER, claim, summary)
    kwargs = {"paper_cache": paper_cache} if paper_cache is not None else {}
    return await engine._call_gemini_freetext(
        messages=messages, chat_id="chat-1", correlation_id=None, log_subdir="audit",
        model_name=MODEL, fallback_model=FALLBACK_MODEL, **kwargs,
    )


def _run_with_cache(client, stats, n_claims, body):
    """Opens a paper cache on `client`, runs `await body(paper_cache)`."""
    async def run():
        async with paper_context_cache(client, MODEL, PAPER, n_claims, stats) as paper_cache:
            return await body(paper_cache)

    return asyncio.run(run())


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(engine, "_build_client", lambda: client)


def _patch_pipeline(monkeypatch, claims):
    async def fake_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return {"claims": claims}

    async def fake_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return ClaimLLM(
            claim_text_verbatim="v", claim_summary="s", label=ClaimLabel.SUPPORTED,
            evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="S")],
        )

    monkeypatch.setattr(engine, "_call_gemini_json", fake_json)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_structured)


CLAIMS = [
    {"claim_text_verbatim": "Claim A.", "claim_summary": "Sum A"},
    {"claim_text_verbatim": "Claim B.", "claim_summary": "Sum B"},
    {"claim_text_verbatim": "Claim C.", "claim_summary": "Sum C"},
]


# --- TTL -------------------------------------------------------------------

def test_ttl_arithmetic():
    # ceil(n x 51 s x 1.25), clamped to [300, 3600]
    assert ttl_for_claims(1) == 300
    assert ttl_for_claims(2) == 300
    assert ttl_for_claims(16) == 1020
    assert ttl_for_claims(30) == 1913
    assert ttl_for_claims(42) == 2678
    assert ttl_for_claims(56) == 3570
    assert ttl_for_claims(57) == 3600
    assert ttl_for_claims(500) == 3600


# --- flag off ----------------------------------------------------------------

def test_flag_off_makes_zero_cache_calls_and_requests_are_unchanged(monkeypatch):
    client, caches, models, events = _fake_client()
    _patch_client(monkeypatch, client)
    _patch_pipeline(monkeypatch, CLAIMS)

    result = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="chat-1"))

    assert len(result.claims) == 3
    assert caches.created == [] and caches.deleted == []
    assert "create" not in events and "delete" not in events
    assert len(models.calls) == 3
    for call in models.calls:
        # exactly today's request: system_instruction + one full user turn
        assert call["config"] == types.GenerateContentConfig(system_instruction=_system_prompt())
        assert call["config"].cached_content is None
        assert len(call["contents"]) == 1
        assert call["contents"][0].parts[0].text.startswith(f"PAPER TEXT:\n{PAPER}\n\nCLAIM TO AUDIT:\n")


def test_no_paper_cache_leaves_the_audit_call_untouched(monkeypatch):
    client, caches, models, _ = _fake_client()
    _patch_client(monkeypatch, client)

    asyncio.run(_audit_call(client, None))

    assert caches.created == []
    assert models.calls[0]["config"] == types.GenerateContentConfig(system_instruction=_system_prompt())


# --- flag on -------------------------------------------------------------------

def test_flag_on_one_create_per_paper_cached_content_on_each_audit_delete_after_last(monkeypatch):
    client, caches, models, events = _fake_client()
    _patch_client(monkeypatch, client)
    _patch_pipeline(monkeypatch, CLAIMS)

    result = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="chat-1", context_cache=True))

    assert len(result.claims) == 3
    # one create, with the system prompt and the paper inside it
    assert len(caches.created) == 1
    create = caches.created[0]
    assert create["model"] == MODEL
    cfg = create["config"]
    assert cfg.system_instruction == _system_prompt()
    assert cfg.contents[0].parts[0].text == f"PAPER TEXT:\n{PAPER}\n\n"
    assert cfg.ttl == "300s"
    # every audit references the cache and carries none of the forbidden fields
    assert len(models.calls) == 3
    for call in models.calls:
        config = call["config"]
        assert config.cached_content == CACHE_NAME
        assert config.system_instruction is None
        assert config.tools is None
        assert config.tool_config is None
        assert len(call["contents"]) == 1
        assert call["contents"][0].parts[0].text.startswith("CLAIM TO AUDIT:\n")
        assert PAPER not in call["contents"][0].parts[0].text
    # deleted once, after the last audit
    assert caches.deleted == [CACHE_NAME]
    assert events[0] == "create" and events[-1] == "delete"
    assert events.index("delete") > max(i for i, e in enumerate(events) if e == "generate")


def test_thinking_config_rides_along_with_cached_content(monkeypatch):
    client, caches, models, _ = _fake_client()
    _patch_client(monkeypatch, client)
    messages = build_gemini_messages_for_audit(PAPER, "Claim A.", "Sum A")

    async def body(paper_cache):
        await engine._call_gemini_freetext(
            messages=messages, chat_id="c", correlation_id=None, log_subdir="audit",
            model_name=MODEL, fallback_model=FALLBACK_MODEL, thinking_level="high", paper_cache=paper_cache,
        )

    _run_with_cache(client, ContextCacheStats(), 3, body)

    config = models.calls[0]["config"]
    assert config.cached_content == CACHE_NAME
    assert config.thinking_config == types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
    assert config.system_instruction is None


def test_model_visible_text_with_cache_equals_flag_off_text(monkeypatch):
    client, caches, models, _ = _fake_client()
    _patch_client(monkeypatch, client)
    claim, summary = "Claim A.", "Sum A"
    plain_messages = build_gemini_messages_for_audit(PAPER, claim, summary)
    plain_text = plain_messages[0]["content"] + plain_messages[1]["content"]

    async def body(paper_cache):
        await _audit_call(client, paper_cache, claim, summary)

    _run_with_cache(client, ContextCacheStats(), 3, body)

    cfg = caches.created[0]["config"]
    request = models.calls[0]
    cached_text = (
        cfg.system_instruction + cfg.contents[0].parts[0].text + request["contents"][0].parts[0].text
    )
    assert cached_text == plain_text
    # the approved difference: two user turns instead of one
    assert cfg.contents[0].role == "user" and request["contents"][0].role == "user"


# --- lifecycle -----------------------------------------------------------------

@pytest.mark.parametrize("exc", [RuntimeError("boom"), CapExceeded("cap"), CacheFailed("stop")])
def test_cache_is_deleted_when_the_body_raises_even_a_base_exception(exc):
    client, caches, _, _ = _fake_client()

    async def body(paper_cache):
        raise exc

    with pytest.raises(type(exc)):
        _run_with_cache(client, ContextCacheStats(), 3, body)

    assert caches.deleted == [CACHE_NAME]


def test_delete_failure_is_logged_and_never_raised(caplog):
    client, caches, _, _ = _fake_client(delete_error=_api_error(500))

    async def body(paper_cache):
        return "ok"

    with caplog.at_level(logging.WARNING, logger="extraction.context_cache"):
        assert _run_with_cache(client, ContextCacheStats(), 3, body) == "ok"

    assert "delete failed" in caplog.text and CACHE_NAME in caplog.text


def test_no_cache_for_another_model_or_zero_claims():
    client, caches, _, _ = _fake_client()
    stats = ContextCacheStats()

    async def run():
        async with paper_context_cache(client, FALLBACK_MODEL, PAPER, 3, stats) as other:
            assert other is None
        async with paper_context_cache(client, MODEL, PAPER, 0, stats) as empty:
            assert empty is None

    asyncio.run(run())

    assert caches.created == [] and stats.papers_cached == 0


def test_ttl_is_sized_to_the_claims_actually_audited(monkeypatch):
    client, caches, _, _ = _fake_client()

    async def body(paper_cache):
        assert paper_cache.ttl_s == 1020

    _run_with_cache(client, ContextCacheStats(), 16, body)

    assert caches.created[0]["config"].ttl == "1020s"


# --- fallback model ------------------------------------------------------------

def test_fallback_model_never_receives_cached_content(monkeypatch):
    def handler(model, contents, config):
        if model == MODEL:
            raise _api_error(503)
        return _response(config)

    client, caches, models, _ = _fake_client(handler=handler)
    _patch_client(monkeypatch, client)
    stats = ContextCacheStats()
    seen = {}

    async def body(paper_cache):
        await _audit_call(client, paper_cache)
        seen["active"] = paper_cache.active

    _run_with_cache(client, stats, 3, body)

    primary = [c for c in models.calls if c["model"] == MODEL]
    fallback = [c for c in models.calls if c["model"] == FALLBACK_MODEL]
    assert len(primary) == engine.MAX_ATTEMPTS and all(c["config"].cached_content == CACHE_NAME for c in primary)
    assert len(fallback) == 1
    assert fallback[0]["config"].cached_content is None
    assert fallback[0]["config"].system_instruction == _system_prompt()
    # the fallback call carries the full uncached prompt: paper + claim in one turn
    assert len(fallback[0]["contents"]) == 1
    assert fallback[0]["contents"][0].parts[0].text.startswith(f"PAPER TEXT:\n{PAPER}\n\nCLAIM TO AUDIT:\n")
    # a 503 is not a cache problem
    assert seen["active"] is True and stats.cached_call_failures == 0 and stats.cache_fallbacks == 0


# --- creation failure ------------------------------------------------------------

def test_creation_failure_logs_full_error_counts_and_audits_uncached(monkeypatch, caplog):
    err = _api_error(400)
    client, caches, models, events = _fake_client(create_error=err)
    _patch_client(monkeypatch, client)
    _patch_pipeline(monkeypatch, CLAIMS)

    with caplog.at_level(logging.ERROR, logger="extraction.context_cache"):
        result = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="chat-1", context_cache=True))

    assert len(result.claims) == 3  # the audit was never blocked
    assert caches.created == [] and caches.deleted == []
    assert len(models.calls) == 3
    for call in models.calls:
        assert call["config"] == types.GenerateContentConfig(system_instruction=_system_prompt())
    assert repr(err) in caplog.text  # the FULL error text
    assert "boom 400" in caplog.text


def test_creation_failure_is_counted():
    client, caches, _, _ = _fake_client(create_error=_api_error(400))
    stats = ContextCacheStats()

    async def body(paper_cache):
        assert paper_cache is None

    _run_with_cache(client, stats, 3, body)

    assert stats.creation_failures == 1 and stats.papers_cached == 0
    assert stats.cache_fallbacks == 3


def test_creation_failure_calls_the_stop_callback_and_nothing_is_deleted():
    client, caches, _, _ = _fake_client(create_error=_api_error(400))
    reasons: list[str] = []

    def stop(reason):
        reasons.append(reason)
        raise CacheFailed(reason)

    stats = ContextCacheStats(on_cache_failure=stop)

    async def body(paper_cache):
        raise AssertionError("body must not run after a creation failure stop")

    with pytest.raises(CacheFailed):
        _run_with_cache(client, stats, 3, body)

    assert stats.creation_failures == 1  # counted before the stop
    assert "boom 400" in reasons[0]
    assert caches.deleted == []


def test_missing_token_count_is_recorded():
    client, _, _, _ = _fake_client(tokens=None)
    stats = ContextCacheStats()

    async def body(paper_cache):
        assert paper_cache.token_count is None

    _run_with_cache(client, stats, 3, body)

    assert stats.token_count_missing == 1 and stats.papers_cached == 1 and stats.tokens_created_total == 0


# --- cached-call API error -------------------------------------------------------------

def test_cached_call_api_error_switches_cache_off_retries_once_uncached_and_counts(monkeypatch, caplog):
    def handler(model, contents, config):
        if config.cached_content:
            raise _api_error(400)
        return _response(config)

    client, caches, models, _ = _fake_client(handler=handler)
    _patch_client(monkeypatch, client)
    stats = ContextCacheStats()
    seen = {}

    async def body(paper_cache):
        with caplog.at_level(logging.ERROR, logger="extraction.engine"):
            await _audit_call(client, paper_cache, "Claim A.", "Sum A")
            seen["active_after_first"] = paper_cache.active
            seen["calls_after_first"] = len(models.calls)
            await _audit_call(client, paper_cache, "Claim B.", "Sum B")

    _run_with_cache(client, stats, 3, body)

    first = models.calls[:2]
    assert first[0]["config"].cached_content == CACHE_NAME  # the cached attempt
    assert first[1]["config"] == types.GenerateContentConfig(system_instruction=_system_prompt())  # one uncached retry
    assert seen["calls_after_first"] == 2
    assert seen["active_after_first"] is False
    # the next claim of the paper goes straight to the uncached path
    assert len(models.calls) == 3 and models.calls[2]["config"].cached_content is None
    assert stats.cached_call_failures == 1
    assert stats.cache_fallbacks == 2  # the retry + the next claim
    assert "status=400" in caplog.text and "boom 400" in caplog.text
    assert caches.deleted == [CACHE_NAME]


def test_cached_call_error_is_retried_uncached_exactly_once(monkeypatch):
    client, _, models, _ = _fake_client(handler=lambda m, c, cfg: (_ for _ in ()).throw(_api_error(400)))
    _patch_client(monkeypatch, client)
    stats = ContextCacheStats()

    async def body(paper_cache):
        with pytest.raises(errors.ClientError):
            await _audit_call(client, paper_cache)

    _run_with_cache(client, stats, 3, body)

    assert len(models.calls) == 2  # one cached attempt + ONE uncached retry, no second retry
    assert stats.cached_call_failures == 1


def test_cached_call_error_stop_callback_fires_before_the_uncached_retry(monkeypatch):
    def handler(model, contents, config):
        if config.cached_content:
            raise _api_error(400)
        return _response(config)

    client, caches, models, _ = _fake_client(handler=handler)
    _patch_client(monkeypatch, client)

    def stop(reason):
        raise CacheFailed(reason)

    stats = ContextCacheStats(on_cache_failure=stop)

    async def body(paper_cache):
        await _audit_call(client, paper_cache)

    with pytest.raises(CacheFailed):
        _run_with_cache(client, stats, 3, body)

    assert len(models.calls) == 1  # no paid uncached retry after the stop
    assert stats.cached_call_failures == 1
    assert caches.deleted == [CACHE_NAME]  # the cache is still cleaned up


def test_cache_for_another_model_is_not_used(monkeypatch):
    client, caches, models, _ = _fake_client()
    _patch_client(monkeypatch, client)
    stats = ContextCacheStats()
    other = PaperCache(
        name=CACHE_NAME, model="some-other-model", token_count=1, ttl_s=300,
        prefix_text=f"PAPER TEXT:\n{PAPER}\n\n", stats=stats,
    )

    asyncio.run(_audit_call(client, other))

    assert models.calls[0]["config"].cached_content is None
    assert stats.cache_fallbacks == 1


def test_context_cache_module_is_the_only_sdk_cache_caller():
    import pathlib

    root = pathlib.Path(context_cache.__file__).parent
    offenders = [
        p.name for p in root.glob("*.py")
        if p.name != "context_cache.py" and ".caches." in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
