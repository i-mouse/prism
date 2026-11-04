"""extraction/llm_backend.py and the eval-only Vertex backend / --auditor-model options of
eval/replay_audit.py. Offline: fake SDK (tests/replay_fakes.py), invented text, and the
autouse guard in conftest.py, which makes a real genai client or a real litellm call fail.

R2: under --backend vertex every call kind reaches Vertex - auditor, structurer, cache
create / use / delete, scope lister and checker (here, through the real engine._build_client
and llm_backend, with only the SDK constructor faked) and the grounding LiteLLM call
(test_eval_backend_options.py, through the router)."""
import argparse
import asyncio
import json
import re
from pathlib import Path

import pytest

from eval import replay_audit
from extraction import engine, llm_backend
from extraction.context_cache import CACHEABLE_MODELS, _is_cacheable_model

import replay_fakes
from replay_fakes import MODEL, FakeSdk

AUDITOR_38 = "gemini-3.8-flash"
EXTRACTION_DIR = Path(__file__).parent.parent / "extraction"


class ModelRecordingSdk(FakeSdk):
    """FakeSdk that also remembers the model each cache was created with."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_models: list[str] = []

    async def _create(self, *, model, config):
        self.cache_models.append(model)
        return await super()._create(model=model, config=config)


def _lister(claim: str) -> str:
    return json.dumps({"items": [{"text": "x", "kind": "count"}]})


def _checker(task: str) -> str:
    return json.dumps({"items": [{"item": "x", "reported": [], "status": "matches", "contradicting_quote": None}]})


def _sdk(**kwargs) -> ModelRecordingSdk:
    return ModelRecordingSdk(lister_fn=_lister, checker_fn=_checker, **kwargs)


def _args(claims_path, **overrides) -> argparse.Namespace:
    values = dict(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=False, dry_run=False,
        max_inr=None, cache=True,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _setup(tmp_path, monkeypatch, sdk):
    """replay_fakes.setup_replay, but the REAL engine._build_client -> llm_backend path is
    kept; only the SDK constructor is replaced, and records the kwargs it was called with."""
    real_build_client = engine._build_client
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    monkeypatch.setattr(engine, "_build_client", real_build_client)
    built: list[dict] = []

    def factory(**kwargs):
        built.append(kwargs)
        return sdk.client

    monkeypatch.setattr(llm_backend, "_client_factory", factory)
    for name, value in (
        ("llm_claim_audit_fallback_model", "gemini-3.1-flash-lite"),
        ("llm_grounding_model", "groq/openai/gpt-oss-20b"),
        ("llm_grounding_fallback_model", "gemini/gemini-3.1-flash-lite"),
        ("ai_api_key", "test-aistudio-key"),
    ):
        monkeypatch.setattr(engine.settings, name, value)
    return claims_path, built


def _run(claims_path, **overrides) -> int:
    return asyncio.run(replay_audit._main(_args(claims_path, **overrides)))


VERTEX = dict(backend="vertex", vertex_project="proj-x", vertex_location="global")


# --- the client factory ----------------------------------------------------------------------

def test_aistudio_client_passes_vertexai_false_even_if_the_environment_says_vertex(monkeypatch):
    built = []
    monkeypatch.setattr(llm_backend, "_client_factory", lambda **kw: built.append(kw))
    for name, value in (
        ("GOOGLE_GENAI_USE_VERTEXAI", "true"), ("GOOGLE_CLOUD_PROJECT", "env-project"),
        ("GOOGLE_CLOUD_LOCATION", "us-central1"),
    ):
        monkeypatch.setenv(name, value)
    llm_backend.build_genai_client("the-key")
    assert built == [{"api_key": "the-key", "vertexai": False}]


def test_vertex_client_uses_project_and_location_and_no_api_key(monkeypatch):
    built = []
    monkeypatch.setattr(llm_backend, "_client_factory", lambda **kw: built.append(kw))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    llm_backend.set_backend(llm_backend.Backend("vertex", "proj-x", "global"))
    llm_backend.build_genai_client("the-key")
    assert built == [{"vertexai": True, "project": "proj-x", "location": "global"}]


def test_vertex_without_a_project_fails_before_building_a_client(monkeypatch):
    with pytest.raises(llm_backend.BackendConfigError, match="--vertex-project"):
        llm_backend.set_backend(llm_backend.Backend("vertex", None, "global"))
    assert llm_backend.get_backend() is llm_backend.AISTUDIO
    with pytest.raises(llm_backend.BackendConfigError, match="only valid with --backend vertex"):
        llm_backend.set_backend(llm_backend.Backend("aistudio", "proj-x"))
    with pytest.raises(llm_backend.BackendConfigError, match="unknown backend"):
        llm_backend.set_backend(llm_backend.Backend("bedrock", "p", "l"))


def test_engine_build_client_goes_through_the_backend(monkeypatch):
    built = []
    monkeypatch.setattr(llm_backend, "_client_factory", lambda **kw: built.append(kw))
    monkeypatch.setattr(engine.settings, "ai_api_key", "test-aistudio-key")
    engine._build_client()
    assert built == [{"api_key": "test-aistudio-key", "vertexai": False}]


def test_no_other_module_builds_a_genai_client_in_extraction():
    """engine._build_client -> llm_backend is the only place a client is created, so no call
    kind can reach AI Studio while the Vertex backend is active."""
    offenders = [
        p.name for p in sorted(EXTRACTION_DIR.glob("*.py"))
        if p.name != "llm_backend.py" and re.search(r"\bgenai\.Client\(|\bClient\(", p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
    assert "_client_factory(" in (EXTRACTION_DIR / "llm_backend.py").read_text(encoding="utf-8")


def test_gemini_38_flash_is_cacheable_and_other_models_are_unchanged():
    assert CACHEABLE_MODELS == {"gemini-3.6-flash", AUDITOR_38}
    assert _is_cacheable_model("gemini-3.6-flash") and _is_cacheable_model(AUDITOR_38)
    assert not _is_cacheable_model("gemini-3.1-flash-lite")


# --- R2: every call kind goes to Vertex ------------------------------------------------------

def test_vertex_run_sends_every_call_kind_to_vertex(tmp_path, monkeypatch):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)

    assert _run(claims_path, scope_check=True, **VERTEX) == 0

    # auditor, structurer, lister, checker all ran, and so did cache create / use / delete
    assert set(sdk.kinds()) == {"audit", "structure", "lister", "checker"}
    assert sdk.created and sdk.deleted
    assert any(kind == "audit" and config.cached_content for kind, _m, _c, config in sdk.calls)
    assert any(kind == "checker" and config.cached_content for kind, _m, _c, config in sdk.calls)
    # every client of the process is a Vertex client: no api_key, no AI Studio client
    assert built and all(kw == {"vertexai": True, "project": "proj-x", "location": "global"} for kw in built)
    assert llm_backend.get_backend() is llm_backend.AISTUDIO  # restored after the run

    summary = json.loads((tmp_path / "out" / f"exp1_medium_{MODEL}-vertex_scope_1" / "_summary.json").read_text("utf-8"))
    run_config = summary["run_config"]
    assert run_config["backend"] == "vertex" and run_config["project"] == "proj-x"
    assert run_config["location"] == "global" and run_config["auditor_model"] == MODEL
    assert run_config["thinking_level"] == "medium"
    assert run_config["other_models"]["structurer"] == MODEL
    assert run_config["other_models"]["scope_lister"] == "gemini-3.6-flash"
    assert run_config["other_models"]["grounding_primary"] == "groq/openai/gpt-oss-20b"
    assert run_config["google_genai_version"] and run_config["litellm_version"]


def test_default_run_builds_aistudio_clients_with_vertexai_false(tmp_path, monkeypatch):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path) == 0
    assert built and all(kw == {"api_key": "test-aistudio-key", "vertexai": False} for kw in built)
    out_dir = tmp_path / "out" / "exp1_medium_1"
    assert "run_config" not in json.loads((out_dir / "_summary.json").read_text("utf-8"))
    claim = json.loads((out_dir / f"{replay_fakes.PAPER_A}.json").read_text("utf-8"))["claims"][0]
    assert "audit_model_served" not in claim


@pytest.mark.parametrize("overrides, message", [
    (dict(backend="vertex", vertex_project=None), "--vertex-project"),
    (dict(backend="aistudio", vertex_project="proj-x"), "only valid with --backend vertex"),
])
def test_bad_backend_options_stop_before_any_request(tmp_path, monkeypatch, capsys, overrides, message):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, **overrides) == 1
    assert message in capsys.readouterr().out
    assert sdk.calls == [] and built == [] and not (tmp_path / "out").exists()


def test_vertex_estimate_builds_no_client(tmp_path, monkeypatch, capsys):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, estimate=True, **VERTEX) == 0
    assert built == [] and sdk.calls == []
    assert "run config" in capsys.readouterr().out


# --- R4: --auditor-model ---------------------------------------------------------------------

def test_auditor_model_changes_only_the_audit_call_and_the_cache(tmp_path, monkeypatch):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)

    assert _run(claims_path, auditor_model=AUDITOR_38, **VERTEX) == 0

    models = {kind: {m for k, m, _c, _cfg in sdk.calls if k == kind} for kind in ("audit", "structure")}
    assert models == {"audit": {AUDITOR_38}, "structure": {MODEL}}
    assert sdk.cache_models == [AUDITOR_38, AUDITOR_38]  # one cache per paper, created with the auditor model
    # the cached audit calls reference that cache, on the same Vertex backend
    assert all(config.cached_content for kind, _m, _c, config in sdk.calls if kind == "audit")
    assert all(kw["vertexai"] is True for kw in built)

    out_dir = tmp_path / "out" / f"exp1_medium_{AUDITOR_38}-vertex_1"
    assert out_dir.is_dir() and not (tmp_path / "out" / "exp1_medium_1").exists()
    fixture = json.loads((out_dir / f"{replay_fakes.PAPER_A}.json").read_text("utf-8"))
    assert fixture["header"]["model_name"] == AUDITOR_38
    assert {c["audit_model_served"] for c in fixture["claims"]} == {AUDITOR_38}
    summary = json.loads((out_dir / "_summary.json").read_text("utf-8"))
    assert summary["run_config"]["auditor_model"] == AUDITOR_38
    audit_records = [r for r in summary["records"] if r["is_audit"]]
    assert audit_records and {r["model_used"] for r in audit_records} == {AUDITOR_38}
    assert summary["gemini_calls_not_priced_at_own_model_rate"] == {}
    assert all(p["storage_usd"] > 0 for p in summary["cache"]["papers"])  # 3.8 storage rate used


def test_auditor_model_on_aistudio_uses_a_separate_folder_and_aistudio_clients(tmp_path, monkeypatch):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, cache=False, auditor_model=AUDITOR_38) == 0
    assert (tmp_path / "out" / f"exp1_medium_{AUDITOR_38}_1" / "_summary.json").is_file()
    assert built and all(kw == {"api_key": "test-aistudio-key", "vertexai": False} for kw in built)


def test_scope_check_with_a_different_auditor_model_is_refused(tmp_path, monkeypatch, capsys):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, scope_check=True, auditor_model=AUDITOR_38) == 1
    assert "--scope-check cannot be combined with --auditor-model" in capsys.readouterr().out
    assert sdk.calls == [] and built == []


def test_existing_output_folder_is_never_overwritten(tmp_path, monkeypatch, capsys):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    existing = tmp_path / "out" / f"exp1_medium_{AUDITOR_38}_1"
    existing.mkdir(parents=True)
    (existing / "keep.txt").write_text("fixture", encoding="utf-8")
    assert _run(claims_path, cache=False, auditor_model=AUDITOR_38) == 1
    assert "refusing to overwrite" in capsys.readouterr().out
    assert sdk.calls == [] and built == []
    assert [p.name for p in existing.iterdir()] == ["keep.txt"]


# --- R5 / R6 ---------------------------------------------------------------------------------

def test_minimal_thinking_with_gemini_38_flash_is_refused_before_any_call(tmp_path, monkeypatch, capsys):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, level="minimal", auditor_model=AUDITOR_38, **VERTEX) == 1
    out = capsys.readouterr().out
    assert "minimal" in out and "HTTP 400" in out
    assert sdk.calls == [] and built == []


def test_unknown_auditor_model_is_refused_before_any_call(tmp_path, monkeypatch, capsys):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, auditor_model="gemini-9-imaginary") == 1
    assert "auditor: no price on file for model 'gemini-9-imaginary'" in capsys.readouterr().out
    assert sdk.calls == [] and built == []


def test_unpriced_google_fallback_model_names_the_role_and_model(tmp_path, monkeypatch, capsys):
    sdk = _sdk()
    claims_path, built = _setup(tmp_path, monkeypatch, sdk)
    monkeypatch.setattr(engine.settings, "llm_claim_audit_fallback_model", "gemini-2.0-unlisted")
    assert _run(claims_path, auditor_model=AUDITOR_38) == 1
    assert "audit_fallback: no price on file for model 'gemini-2.0-unlisted'" in capsys.readouterr().out
    assert sdk.calls == [] and built == []


def test_estimate_prices_each_call_at_its_own_model(monkeypatch):
    stats = {
        "audit_prompt": 40_000, "audit_output": 300, "audit_thought_medium": 2_000,
        "struct_prompt": 1_400, "struct_output": 250, "struct_thought": 800,
    }
    default = replay_audit._estimate_one_claim_cost_usd(stats, "medium")
    # a model priced at exactly double the default rates, for the audit calls only
    monkeypatch.setitem(replay_audit.pricing.RATES_BY_MODEL, "double-model", replay_audit.pricing.Rates(1.5, 7.5, 0.15))
    same = replay_audit._estimate_one_claim_cost_usd(stats, "medium", audit_model="gemini-3.6-flash", struct_model="gemini-3.6-flash")
    assert same == pytest.approx(default)
    audit_double = replay_audit._estimate_one_claim_cost_usd(stats, "medium", audit_model="double-model", struct_model="gemini-3.6-flash")
    audit_only_default = 40_000 / 1e6 * 0.75 + (300 + 2_000) / 1e6 * 3.75
    audit_only_double = 2 * audit_only_default
    assert audit_double[0] == pytest.approx(default[0] + (audit_only_double - audit_only_default))
    both_double = replay_audit._estimate_one_claim_cost_usd(stats, "medium", audit_model="double-model", struct_model="double-model")
    assert both_double == pytest.approx((default[0] * 2, default[1] * 2))
    with pytest.raises(replay_audit.pricing.UnpricedModelError):
        replay_audit._estimate_one_claim_cost_usd(stats, "medium", audit_model="gemini-9-imaginary", struct_model=MODEL)
