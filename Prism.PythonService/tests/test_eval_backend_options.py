"""eval/backend_options.py (the LiteLLM router, the pre-request checks, run_config) and the
--backend / --model options of eval/probe_cache_schema.py. Offline: fake SDK and fake
litellm.acompletion only (conftest.py makes the real ones fail)."""
import argparse
import asyncio
import importlib.metadata
import json
from types import SimpleNamespace

import litellm
import pytest

from eval import backend_options, pricing
from eval import probe_cache_schema as probe
from eval.probe_cache_schema import ProbeOut
from extraction import grounding, llm_backend
from extraction.llm_backend import Backend
from extraction.schemas import ClaimLabel

VERTEX = Backend("vertex", "proj-x", "global")
_VERDICT = json.dumps({"reasoning": "r", "stance": "supports", "verdict": "Pass", "reason": "ok"})
GROQ = "groq/openai/gpt-oss-20b"
GEMINI_FALLBACK = "gemini/gemini-3.1-flash-lite"


def _response():
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                            prompt_tokens_details=None, completion_tokens_details=None)
    return SimpleNamespace(model="m", usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content=_VERDICT))])


def _recorder(monkeypatch):
    seen: list[dict] = []

    async def fake(**kwargs):
        seen.append(kwargs)
        return _response()

    monkeypatch.setattr(litellm, "acompletion", fake)
    return seen


def _audit(**overrides):
    kwargs = dict(
        messages=[{"role": "user", "content": "q"}], audit_model=GROQ, fallback_model=GEMINI_FALLBACK,
        gemini_api_key="aistudio-key", span_source_section="s",
    )
    kwargs.update(overrides)
    return grounding._call_litellm_audit(**kwargs)


# --- the LiteLLM router ----------------------------------------------------------------------

def test_vertex_router_keeps_a_groq_primary_and_rewrites_only_the_gemini_fallback(monkeypatch):
    seen = _recorder(monkeypatch)
    with backend_options.routed_litellm(VERTEX):
        verdict = asyncio.run(_audit())
    assert verdict.verdict == "Pass"
    (kwargs,) = seen
    assert kwargs["model"] == GROQ
    assert "vertex_project" not in kwargs and "vertex_location" not in kwargs  # nothing Vertex goes to Groq
    assert kwargs["fallbacks"] == [{
        "model": "vertex_ai/gemini-3.1-flash-lite", "vertex_project": "proj-x", "vertex_location": "global",
    }]  # the AI Studio api_key is gone
    assert kwargs["max_tokens"] == grounding.AUDIT_MAX_OUTPUT_TOKENS and kwargs["temperature"] == 0


def test_vertex_router_rewrites_a_gemini_primary(monkeypatch):
    seen = _recorder(monkeypatch)
    with backend_options.routed_litellm(VERTEX):
        asyncio.run(_audit(audit_model="gemini/gemini-3.8-flash"))
    (kwargs,) = seen
    assert kwargs["model"] == "vertex_ai/gemini-3.8-flash"
    assert (kwargs["vertex_project"], kwargs["vertex_location"]) == ("proj-x", "global")
    assert "api_key" not in kwargs
    assert kwargs["fallbacks"][0]["model"] == "vertex_ai/gemini-3.1-flash-lite"


def test_vertex_router_accepts_a_vertex_route_and_a_bare_gemini_name():
    routed = backend_options.route_completion_kwargs(VERTEX, {
        "model": "vertex_ai/gemini-3.1-flash-lite",
        "fallbacks": [{"model": "gemini-3.1-flash-lite", "api_key": "k"}],
    })
    assert routed["model"] == "vertex_ai/gemini-3.1-flash-lite" and routed["vertex_project"] == "proj-x"
    assert routed["fallbacks"] == [{
        "model": "vertex_ai/gemini-3.1-flash-lite", "vertex_project": "proj-x", "vertex_location": "global",
    }]


def test_non_google_routes_pass_through_unchanged():
    kwargs = {"model": "openai/gpt-oss-20b", "fallbacks": [{"model": GROQ, "api_key": "groq-key"}]}
    assert backend_options.route_completion_kwargs(VERTEX, kwargs) == kwargs


def test_aistudio_installs_nothing_and_leaves_kwargs_alone(monkeypatch):
    seen = _recorder(monkeypatch)
    installed = litellm.acompletion
    with backend_options.routed_litellm(llm_backend.AISTUDIO):
        assert litellm.acompletion is installed
        asyncio.run(_audit())
    (kwargs,) = seen
    assert kwargs["model"] == GROQ
    assert kwargs["fallbacks"] == [{"model": GEMINI_FALLBACK, "api_key": "aistudio-key"}]
    kw = {"model": GEMINI_FALLBACK, "api_key": "k"}
    assert backend_options.route_completion_kwargs(llm_backend.AISTUDIO, kw) is kw


def test_router_is_removed_after_the_block(monkeypatch):
    _recorder(monkeypatch)
    installed = litellm.acompletion
    with backend_options.routed_litellm(VERTEX):
        assert litellm.acompletion is not installed
    assert litellm.acompletion is installed


@pytest.mark.parametrize("kwargs", [
    {"model": "gemini/", "messages": []},
    {"model": GROQ, "fallbacks": [{"model": "gemini/"}]},
    {"model": GROQ, "fallbacks": [{"model": "vertex_ai/publishers/google/x"}]},
    {"model": GROQ, "fallbacks": ["gemini/gemini-3.1-flash-lite"]},
    {"model": None},
])
def test_an_unrewritable_gemini_route_fails_before_the_request(monkeypatch, kwargs):
    seen = _recorder(monkeypatch)

    async def go():
        with backend_options.routed_litellm(VERTEX):
            await litellm.acompletion(**kwargs)

    with pytest.raises(backend_options.BackendRoutingError):
        asyncio.run(go())
    assert seen == []


def test_routing_error_is_not_swallowed_into_a_skipped_span(monkeypatch):
    """grounding._audit_span_with_llm turns any Exception into SKIPPED; a routing failure
    must not be hidden that way."""
    assert not issubclass(backend_options.BackendRoutingError, Exception)
    seen = _recorder(monkeypatch)

    async def go():
        with backend_options.routed_litellm(VERTEX):
            return await grounding._audit_span_with_llm(
                claim_text="c", claim_label=ClaimLabel.SUPPORTED, span_source_text="q", span_source_section="s",
                span_context="ctx", semaphore=asyncio.Semaphore(1), audit_model=GROQ, fallback_model="gemini/",
                gemini_api_key="k",
            )

    with pytest.raises(backend_options.BackendRoutingError):
        asyncio.run(go())
    assert seen == []


def test_preflight_accepts_groq_and_rejects_an_unrewritable_gemini_fallback():
    backend_options.check_grounding_routes(VERTEX, GROQ, GEMINI_FALLBACK)
    backend_options.check_grounding_routes(llm_backend.AISTUDIO, GROQ, GEMINI_FALLBACK)
    with pytest.raises(backend_options.BackendRoutingError):
        backend_options.check_grounding_routes(VERTEX, GROQ, "gemini/")


# --- pricing / thinking / run_config helpers -------------------------------------------------

def test_require_priced_checks_google_models_only():
    backend_options.require_priced({
        "auditor": "gemini-3.8-flash", "grounding_primary": GROQ, "other_provider": "acme/not-priced-1",
        "grounding_fallback": GEMINI_FALLBACK,
    })
    with pytest.raises(pricing.UnpricedModelError, match="audit_fallback: no price on file for model 'gemini-9-x'"):
        backend_options.require_priced({"auditor": "gemini-3.8-flash", "audit_fallback": "gemini-9-x"})


def test_thinking_minimal_is_rejected_for_gemini_38_flash_only():
    with pytest.raises(ValueError, match="'minimal' is rejected by vertex_ai/gemini-3.8-flash"):
        backend_options.validate_thinking("vertex_ai/gemini-3.8-flash", "minimal")
    for level in ("low", "medium", "high", None):
        backend_options.validate_thinking("gemini-3.8-flash", level)
    backend_options.validate_thinking("gemini-3.6-flash", "minimal")  # not this module's call for other models


def test_backend_from_args_defaults_and_errors():
    assert backend_options.backend_from_args(argparse.Namespace()) == llm_backend.AISTUDIO
    assert backend_options.backend_from_args(
        argparse.Namespace(backend="vertex", vertex_project="p", vertex_location="eu")) == Backend("vertex", "p", "eu")
    assert backend_options.backend_from_args(argparse.Namespace(backend="vertex", vertex_project="p")).location == "global"
    with pytest.raises(llm_backend.BackendConfigError):
        backend_options.backend_from_args(argparse.Namespace(backend="vertex"))


def test_parser_defaults():
    parser = argparse.ArgumentParser()
    backend_options.add_backend_args(parser)
    args = parser.parse_args([])
    assert (args.backend, args.vertex_project, args.vertex_location) == ("aistudio", None, "global")
    with pytest.raises(SystemExit):
        parser.parse_args(["--backend", "bedrock"])


def test_run_config_records_versions_and_slug():
    config = backend_options.run_config(VERTEX, "gemini-3.8-flash", {"structurer": "gemini-3.6-flash"}, "high")
    assert config == {
        "backend": "vertex", "project": "proj-x", "location": "global", "auditor_model": "gemini-3.8-flash",
        "other_models": {"structurer": "gemini-3.6-flash"}, "thinking_level": "high",
        "google_genai_version": importlib.metadata.version("google-genai"),
        "litellm_version": importlib.metadata.version("litellm"),
    }
    assert backend_options.output_slug(None, VERTEX, "gemini-3.6-flash") == "gemini-3.6-flash-vertex"
    assert backend_options.output_slug("vertex_ai/Gemini-3.8-Flash", llm_backend.AISTUDIO, "x") == "gemini-3.8-flash"


# --- probe_cache_schema ----------------------------------------------------------------------

CACHE_NAME = "cachedContents/probe123"


class _ProbeSdk:
    def __init__(self):
        self.cache_models: list[str] = []
        self.request_models: list[str] = []
        self.deleted: list[str] = []
        self.client = SimpleNamespace(aio=SimpleNamespace(
            caches=SimpleNamespace(create=self._create, delete=self._delete),
            models=SimpleNamespace(generate_content=self._generate),
        ))

    async def _create(self, *, model, config):
        self.cache_models.append(model)
        return SimpleNamespace(name=CACHE_NAME, usage_metadata=SimpleNamespace(total_token_count=13_125))

    async def _delete(self, *, name):
        self.deleted.append(name)

    async def _generate(self, *, model, contents, config):
        self.request_models.append(model)
        usage = SimpleNamespace(
            prompt_token_count=13_200, candidates_token_count=60, thoughts_token_count=40, total_token_count=13_300,
            cached_content_token_count=13_125, tool_use_prompt_token_count=None,
        )
        return SimpleNamespace(
            parsed=ProbeOut(answer="a", quotes=[]), text="{}", usage_metadata=usage,
            candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))],
        )


def _probe_args(**overrides) -> argparse.Namespace:
    values = dict(estimate=False)
    values.update(overrides)
    return argparse.Namespace(**values)


def _probe_setup(monkeypatch):
    sdk, built = _ProbeSdk(), []

    def factory(**kwargs):
        built.append(kwargs)
        return sdk.client

    monkeypatch.setattr(llm_backend, "_client_factory", factory)
    monkeypatch.setattr(probe.engine.settings, "ai_api_key", "test-aistudio-key")
    monkeypatch.setattr(probe, "_load_paper_text", lambda paper_id: "THE FULL PAPER TEXT")
    return sdk, built


def test_probe_vertex_38_cache_and_request_go_to_vertex(monkeypatch, capsys):
    sdk, built = _probe_setup(monkeypatch)
    args = _probe_args(backend="vertex", vertex_project="proj-x", vertex_location="global", model="gemini-3.8-flash")
    assert asyncio.run(probe._main(args)) == 0
    assert built == [{"vertexai": True, "project": "proj-x", "location": "global"}]
    assert sdk.cache_models == ["gemini-3.8-flash"] and sdk.request_models == ["gemini-3.8-flash"]
    assert sdk.deleted == [CACHE_NAME]
    out = capsys.readouterr().out
    assert "run config" in out and "'probe_model': 'gemini-3.8-flash'" in out
    assert llm_backend.get_backend() is llm_backend.AISTUDIO


def test_probe_default_run_is_unchanged(monkeypatch, capsys):
    sdk, built = _probe_setup(monkeypatch)
    assert asyncio.run(probe._main(_probe_args())) == 0
    assert built == [{"api_key": "test-aistudio-key", "vertexai": False}]
    assert sdk.cache_models == ["gemini-3.6-flash"] and sdk.request_models == ["gemini-3.6-flash"]
    assert "run config" not in capsys.readouterr().out


def test_probe_estimate_uses_the_chosen_model_and_builds_no_client(monkeypatch, capsys):
    sdk, built = _probe_setup(monkeypatch)
    assert asyncio.run(probe._main(_probe_args(estimate=True, model="gemini-3.8-flash"))) == 0
    out = capsys.readouterr().out
    assert "on gemini-3.8-flash" in out and built == [] and sdk.cache_models == []


@pytest.mark.parametrize("overrides, message", [
    (dict(backend="vertex"), "--vertex-project"),
    (dict(model="gemini-3.1-flash-lite"), "not a cacheable model"),
    (dict(backend="aistudio", vertex_project="proj-x"), "only valid with --backend vertex"),
])
def test_probe_bad_options_stop_before_any_request(monkeypatch, capsys, overrides, message):
    sdk, built = _probe_setup(monkeypatch)
    assert asyncio.run(probe._main(_probe_args(**overrides))) == 1
    assert message in capsys.readouterr().out
    assert built == [] and sdk.cache_models == [] and sdk.request_models == []


def test_probe_unpriced_cacheable_model_is_refused(monkeypatch, capsys):
    sdk, built = _probe_setup(monkeypatch)
    monkeypatch.setattr(probe, "CACHEABLE_MODELS", probe.CACHEABLE_MODELS | {"gemini-9-x"})
    assert asyncio.run(probe._main(_probe_args(model="gemini-9-x"))) == 1
    assert "no price on file" in capsys.readouterr().out
    assert built == [] and sdk.request_models == []
