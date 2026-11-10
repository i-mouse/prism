"""extraction/scope_check.py: the lister and checker requests, failure handling, and
what they are (not) given. Offline: a fake SDK client, invented text only."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from google.genai import errors, types

from extraction import engine, scope_check
from extraction.context_cache import CacheFailed, ContextCacheStats, PaperCache
from extraction.scope_check import ClaimScope, ScopeStats
from extraction.scope_schemas import ScopeCheckResponse, ScopeItem, ScopeListResponse

from replay_fakes import AUDIT_CANARY, MODEL, FakeSdk

CLAIM = "The controller reduces fatigue load on all three turbine models."
ITEMS_JSON = json.dumps({"items": [{"text": "holds for each of the three models", "kind": "count"}]})
CHECK_JSON = json.dumps({"items": [{
    "item": "holds for each of the three models", "reported": ["Table row"], "status": "matches",
    "contradicting_quote": None,
}]})


def _api_error(code: int) -> errors.APIError:
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": f"boom {code}", "status": "X"}})


def _cache(stats=None, **kwargs) -> PaperCache:
    fields = dict(
        name="cachedContents/test1", model=MODEL, token_count=100, ttl_s=3600, prefix_text="PAPER TEXT:\ninvented",
        stats=stats or ContextCacheStats(),
    )
    fields.update(kwargs)
    return PaperCache(**fields)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(engine, "BACKOFF_SECONDS", (0, 0, 0))

    def make(sdk: FakeSdk) -> FakeSdk:
        monkeypatch.setattr(engine, "_build_client", lambda: sdk.client)
        return sdk

    return make


def _run(paper_cache, stats, claim=CLAIM) -> ClaimScope:
    return asyncio.run(scope_check.scope_for_claim(paper_cache, claim, "chat", stats, claim_ref="paper#0"))


def _scope_calls(sdk, kind):
    return [call for call in sdk.calls if call[0] == kind]


# --- request shapes --------------------------------------------------------------

def test_checker_request_is_cache_plus_schema_plus_low_thinking_and_nothing_else(env):
    sdk = env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: CHECK_JSON))
    stats = ScopeStats()
    scope = _run(_cache(), stats)

    (_, model, contents, config), = _scope_calls(sdk, "checker")
    assert model == MODEL
    assert config.cached_content == "cachedContents/test1"
    assert config.response_schema is ScopeCheckResponse
    assert config.response_mime_type == "application/json"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert config.system_instruction is None and config.tools is None and config.tool_config is None
    assert len(contents) == 1 and contents[0].role == "user"
    task = contents[0].parts[0].text
    assert CLAIM in task and "1. [count] holds for each of the three models" in task
    assert "{{CLAIM}}" not in task and "{{ITEMS}}" not in task
    assert scope.checks is not None and scope.checks[0].status == "matches"
    assert (stats.checker_calls, stats.checker_failures, stats.claims_with_items) == (1, 0, 1)


def test_lister_request_has_the_system_prompt_and_the_claim_only(env):
    sdk = env(FakeSdk(lister_fn=lambda c: json.dumps({"items": []})))
    stats = ScopeStats()
    scope = _run(_cache(), stats)

    (_, model, contents, config), = _scope_calls(sdk, "lister")
    assert model == MODEL
    assert config.system_instruction == (scope_check._read_prompt_file("scope_list_system.md"))
    assert config.cached_content is None and config.tools is None and config.tool_config is None
    assert config.response_schema is ScopeListResponse
    assert config.response_mime_type == "application/json"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert len(contents) == 1 and contents[0].role == "user"
    assert contents[0].parts[0].text == CLAIM  # no paper, no verdict
    assert scope.items == [] and scope.checks is None


def test_neither_request_carries_the_auditor_verdict_or_reasoning(env):
    sdk = env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: CHECK_JSON))
    _run(_cache(), ScopeStats())

    for kind in ("lister", "checker"):
        (_, _, contents, config), = _scope_calls(sdk, kind)
        sent = "\n".join(p.text for c in contents for p in c.parts) + str(config.system_instruction)
        assert AUDIT_CANARY not in sent and "VERDICT:" not in sent and "QUOTE:" not in sent
    # and the entry point has no parameter through which they could arrive
    import inspect
    assert set(inspect.signature(scope_check.scope_for_claim).parameters) == {
        "paper_cache", "claim_text", "chat_id", "stats", "correlation_id", "claim_ref",
    }


def test_both_calls_opt_out_of_the_fallback_and_carry_their_kind(env, monkeypatch):
    env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: CHECK_JSON))
    seen = []
    original = engine._generate_with_fallback

    async def spy(*args, **kwargs):
        seen.append(kwargs)
        return await original(*args, **kwargs)

    monkeypatch.setattr(engine, "_generate_with_fallback", spy)
    _run(_cache(), ScopeStats())
    assert [(k["call_kind"], k["allow_fallback"]) for k in seen] == [("lister", False), ("checker", False)]


# --- the checker's task text ------------------------------------------------------

def test_checker_text_substitutes_in_one_pass_and_numbers_the_items():
    items = [ScopeItem(text="a", kind="count"), ScopeItem(text="b {{CLAIM}}", kind="pair")]
    assert scope_check.format_items(items) == "1. [count] a\n2. [pair] b {{CLAIM}}"
    text = scope_check.build_checker_user_text("claim with {{ITEMS}} inside", items)
    assert "claim with {{ITEMS}} inside" in text  # not re-substituted
    assert "2. [pair] b {{CLAIM}}" in text
    assert text.startswith("NEW TASK FOR THIS REQUEST.")


# --- empty list, failures ----------------------------------------------------------

def test_an_empty_item_list_means_no_checker_call_and_no_failure(env):
    sdk = env(FakeSdk())
    stats = ScopeStats()
    scope = _run(_cache(), stats)
    assert sdk.kinds() == ["lister"]
    assert scope == ClaimScope()
    assert (stats.lister_calls, stats.claims_with_items, stats.checker_calls) == (1, 0, 0)
    assert stats.lister_failures == 0


def test_lister_failure_is_counted_and_nothing_raises(env):
    def boom(claim):
        raise _api_error(400)

    sdk = env(FakeSdk(lister_fn=boom))
    stats = ScopeStats()
    scope = _run(_cache(), stats)
    assert scope.lister_failed and scope.items == [] and scope.checks is None
    assert (stats.lister_calls, stats.lister_failures, stats.checker_calls) == (1, 1, 0)
    assert sdk.kinds() == []


def test_lister_parse_failure_is_a_counted_failure(env):
    env(FakeSdk(lister_fn=lambda c: "not json"))
    stats = ScopeStats()
    assert _run(_cache(), stats).lister_failed
    assert stats.lister_failures == 1


def test_checker_failure_is_counted_keeps_the_items_and_nothing_raises(env):
    env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: json.dumps({"items": [{"item": "x"}]})))
    stats = ScopeStats()
    scope = _run(_cache(), stats)
    assert scope.checker_failed and scope.checks is None and len(scope.items) == 1
    assert (stats.checker_calls, stats.checker_failures, stats.lister_failures) == (1, 1, 0)


@pytest.mark.parametrize("make_cache", [
    lambda: None,
    lambda: _cache(active=False),
    lambda: _cache(model="gemini-3.1-flash-lite"),
], ids=["none", "inactive", "other_model"])
def test_an_unusable_cache_is_a_counted_checker_failure_with_no_request(env, make_cache):
    sdk = env(FakeSdk(lister_fn=lambda c: ITEMS_JSON))
    stats = ScopeStats()
    scope = _run(make_cache(), stats)
    assert scope.checker_failed
    assert sdk.kinds() == ["lister"]
    assert (stats.checker_calls, stats.checker_failures) == (1, 1)


def test_retries_stay_on_the_same_model_and_never_switch(env):
    def unavailable(claim):
        raise _api_error(503)

    sdk = env(FakeSdk(lister_fn=unavailable))
    stats = ScopeStats()
    assert _run(_cache(), stats).lister_failed
    assert sdk.requested_models == [MODEL] * engine.MAX_ATTEMPTS

    sdk2 = env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: (_ for _ in ()).throw(_api_error(500))))
    assert _run(_cache(), ScopeStats()).checker_failed
    assert sdk2.requested_models == [MODEL] + [MODEL] * engine.MAX_ATTEMPTS


def test_a_non_retryable_cached_call_error_switches_the_cache_off_and_is_reported(env):
    env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: (_ for _ in ()).throw(_api_error(400))))
    cache_stats = ContextCacheStats()
    cache = _cache(stats=cache_stats)
    stats = ScopeStats()
    scope = _run(cache, stats)
    assert scope.checker_failed and cache.active is False
    assert cache_stats.cached_call_failures == 1
    assert stats.checker_failures == 1


def test_a_cache_failure_callback_that_stops_the_run_is_not_swallowed(env):
    env(FakeSdk(lister_fn=lambda c: ITEMS_JSON, checker_fn=lambda t: (_ for _ in ()).throw(_api_error(400))))

    def stop(reason):
        raise CacheFailed(reason)

    cache = _cache(stats=ContextCacheStats(on_cache_failure=stop))
    with pytest.raises(CacheFailed):
        _run(cache, ScopeStats())


def test_a_cap_stop_passes_straight_through(env, monkeypatch):
    env(FakeSdk())

    class Stop(BaseException):
        pass

    async def stop_call(*args, **kwargs):
        raise Stop()

    monkeypatch.setattr(engine, "_generate_with_fallback", stop_call)
    with pytest.raises(Stop):
        _run(_cache(), ScopeStats())
