"""eval/replay_audit.py with --scope-check: flag validation, TTL, call order, the
trace, cost accounting, failures, --estimate. Offline: fake SDK, fake grounding,
invented text only (tests/replay_fakes.py)."""
import argparse
import asyncio
import json
import logging

import pytest
from google.genai import errors

from eval import pricing, replay_audit
from extraction import engine, grounding
from extraction.scope_check import ScopeStats

import replay_fakes
from replay_fakes import AUDIT_CANARY, PAPER_A, PAPER_B, FakeSdk

# Quote that is verbatim in PAPER_A's invented text.
GOOD_QUOTE = "Limitations. On T3 the gusty-wind load rose slightly (+1.3 percent)."
FOREIGN_QUOTE = "Quantum entanglement dominates the spectral gap of lattice simulations."

C_A0 = "The controller reduces fatigue load on all three turbine models."
C_A1 = "The controller reduces fatigue load under both low and gusty wind."
C_A2 = "Gusty wind is harder than low wind for every model."
C_B0 = "Method M beats the baseline on both tasks."
C_B1 = "Method M is the fastest method."

# lister output per claim; C_B1 has no scope element
LISTED = {
    C_A0: [("holds for each of the three models", "count")],
    C_A1: [("holds under low wind and under gusty wind", "pair")],
    C_A2: [("every model", "quantifier")],
    C_B0: [("both tasks", "pair")],
}
# checker output per claim: (status, quote)
CHECKED = {
    C_A0: ("contradicted", GOOD_QUOTE),     # supported + guard pass -> lowered
    C_A1: ("contradicted", FOREIGN_QUOTE),  # supported, quote not in the paper -> unchanged
    C_A2: ("contradicted", GOOD_QUOTE),     # partially_supported -> never changes
    C_B0: ("matches", None),
}


def _claim_in(text: str) -> str:
    return next(c for c in LISTED if c in text)


def _lister(claim_text: str) -> str:
    items = LISTED.get(claim_text.strip(), [])
    return json.dumps({"items": [{"text": t, "kind": k} for t, k in items]})


def _checker(task_text: str) -> str:
    claim = _claim_in(task_text)
    status, quote = CHECKED[claim]
    return json.dumps({"items": [{
        "item": LISTED[claim][0][0], "reported": [quote] if quote else [], "status": status,
        "contradicting_quote": quote,
    }]})


def _sdk(**kwargs) -> FakeSdk:
    kwargs.setdefault("lister_fn", _lister)
    kwargs.setdefault("checker_fn", _checker)
    return FakeSdk(**kwargs)


def _args(claims_path, cache=True, scope_check=True, max_inr=None, estimate=False) -> argparse.Namespace:
    return argparse.Namespace(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=estimate,
        dry_run=False, max_inr=max_inr, cache=cache, scope_check=scope_check,
    )


def _go(tmp_path, monkeypatch, sdk=None, **arg_overrides):
    sdk = sdk or _sdk()
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    rc = asyncio.run(replay_audit._main(_args(claims_path, **arg_overrides)))
    return rc, sdk


def _out(tmp_path, paper_id) -> dict:
    return json.loads((tmp_path / "out" / "exp1_medium_scope_1" / f"{paper_id}.json").read_text(encoding="utf-8"))


def _summary(tmp_path) -> dict:
    return json.loads((tmp_path / "out" / "exp1_medium_scope_1" / "_summary.json").read_text(encoding="utf-8"))


# --- the flag ---------------------------------------------------------------------------

def test_scope_check_without_cache_is_a_value_error_everywhere(tmp_path, monkeypatch):
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, _sdk())
    with pytest.raises(ValueError, match="requires cache"):
        asyncio.run(replay_audit._main(_args(claims_path, cache=False, scope_check=True)))
    with pytest.raises(ValueError, match="requires cache"):
        asyncio.run(replay_audit._main(_args(claims_path, cache=False, scope_check=True, estimate=True)))
    with pytest.raises(ValueError, match="requires cache"):
        replay_audit._print_estimate([], "medium", 1, cache=False, scope_check=True)
    ledger = replay_audit._ScopeLedger(stats=ScopeStats(), prompt_hash="x")
    with pytest.raises(ValueError, match="requires cache"):
        asyncio.run(replay_audit._run_once([], "medium", 1, False, {}, None, scope_ledger=ledger))


def test_the_flag_defaults_off_and_is_a_cli_option_next_to_cache():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "high"]).scope_check is False
    assert parser.parse_args(["--level", "high", "--cache", "--scope-check"]).scope_check is True


def test_no_scope_field_appears_with_the_flag_off(tmp_path, monkeypatch):
    sdk = FakeSdk()
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    assert asyncio.run(replay_audit._main(_args(claims_path, scope_check=False))) == 0
    assert set(sdk.kinds()) == {"audit", "structure"}
    out = tmp_path / "out" / "exp1_medium_1"
    assert not (tmp_path / "out" / "exp1_medium_scope_1").exists()
    claim = json.loads((out / f"{PAPER_A}.json").read_text(encoding="utf-8"))["claims"][0]
    assert not any(key.startswith("scope") or key == "auditor_label" for key in claim)
    assert "scope_check" not in json.loads((out / "_summary.json").read_text(encoding="utf-8"))
    assert "scope_check_prompt_hash" not in json.loads((out / f"{PAPER_A}.json").read_text(encoding="utf-8"))["header"]["replay"]


# --- TTL --------------------------------------------------------------------------------

def test_cache_ttl_is_3600_with_the_flag_and_unchanged_without(tmp_path, monkeypatch):
    on_root, off_root = tmp_path / "on", tmp_path / "off"
    on_root.mkdir()
    off_root.mkdir()

    rc, sdk_on = _go(on_root, monkeypatch, scope_check=True)
    assert rc == 0
    assert [c.ttl for c in sdk_on.created] == ["3600s", "3600s"]

    rc, sdk_off = _go(off_root, monkeypatch, sdk=FakeSdk(), scope_check=False)
    assert rc == 0
    # paper A has 3 claims and paper B has 2: both sit on the 300 s floor of the claim-count rule
    assert [c.ttl for c in sdk_off.created] == ["300s", "300s"]


# --- order and trace --------------------------------------------------------------------

def test_per_claim_order_then_cache_delete_then_grounding_then_combine(tmp_path, monkeypatch):
    sdk = _sdk()
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    at_ground = []

    async def spying_ground(extraction, paper_text, chat_id, **kwargs):
        at_ground.append((len(sdk.calls), list(sdk.deleted)))
        return await replay_fakes.fake_ground(extraction, paper_text, chat_id, **kwargs)

    monkeypatch.setattr(grounding, "ground_extraction", spying_ground)
    assert asyncio.run(replay_audit._main(_args(claims_path))) == 0

    # paper A: three claims, each audit -> structure -> lister -> checker; paper B: four calls + three calls
    assert sdk.kinds() == (
        ["audit", "structure", "lister", "checker"] * 3
        + ["audit", "structure", "lister", "checker"]
        + ["audit", "structure", "lister"]
    )
    # grounding saw the paper's cache already deleted and no scope call came after it for that paper
    assert at_ground == [(12, ["cachedContents/fake1"]), (19, ["cachedContents/fake1", "cachedContents/fake2"])]
    assert len(sdk.calls) == 19


def test_trace_summary_and_header(tmp_path, monkeypatch, caplog):
    with caplog.at_level(logging.INFO, logger="extraction.scope_combine"):
        rc, sdk = _go(tmp_path, monkeypatch)
    assert rc == 0

    a = _out(tmp_path, PAPER_A)
    assert a["header"]["replay"]["scope_check_prompt_hash"] == "scopehash001"
    a0, a1, a2 = a["claims"]
    assert (a0["auditor_label"], a0["label"], a0["scope_lowered"]) == ("supported", "partially_supported", True)
    assert (a0["scope_item"], a0["scope_item_kind"], a0["scope_quote"]) == (
        "holds for each of the three models", "count", GOOD_QUOTE,
    )
    assert a0["scope_items"] == [{
        "text": "holds for each of the three models", "kind": "count", "status": "contradicted",
        "contradicting_quote": GOOD_QUOTE, "guard_passed": True,
    }]
    assert (a1["auditor_label"], a1["label"], a1["scope_lowered"]) == ("supported", "supported", False)
    assert a1["scope_item"] is a1["scope_item_kind"] is a1["scope_quote"] is None
    assert a1["scope_items"][0]["guard_passed"] is False and a1["scope_items"][0]["kind"] == "pair"
    assert (a2["auditor_label"], a2["label"]) == ("partially_supported", "partially_supported")
    assert a2["scope_items"][0]["guard_passed"] is True and not a2["scope_lowered"]

    b0, b1 = _out(tmp_path, PAPER_B)["claims"]
    assert b0["scope_items"][0]["status"] == "matches" and b0["scope_items"][0]["guard_passed"] is None
    assert (b1["auditor_label"], b1["label"], b1["scope_items"]) == ("not_supported", "not_supported", [])

    scope = _summary(tmp_path)["scope_check"]
    assert scope["prompt_hash"] == "scopehash001"
    counts = {k: v for k, v in scope.items() if k not in ("prompt_hash", "by_call")}
    assert counts == {
        "lister_calls": 5, "lister_failures": 0, "claims_with_items": 4, "checker_calls": 4, "checker_failures": 0,
        "item_count_mismatches": 0, "contradicted_items": 3, "guard_failed": 1, "verdicts_lowered": 1,
    }
    contradicted_logs = [r.getMessage() for r in caplog.records if "contradicted item" in r.getMessage()]
    assert len(contradicted_logs) == 3
    assert {k for m in contradicted_logs for k in ("kind=count", "kind=pair", "kind=quantifier") if k in m} == {
        "kind=count", "kind=pair", "kind=quantifier",
    }


def test_lister_and_checker_never_receive_the_auditor_output(tmp_path, monkeypatch):
    _, sdk = _go(tmp_path, monkeypatch)
    scope_calls = [c for c in sdk.calls if c[0] in ("lister", "checker")]
    assert len(scope_calls) == 9
    for kind, _, contents, config in scope_calls:
        sent = "\n".join(p.text for c in contents for p in c.parts) + str(config.system_instruction)
        assert AUDIT_CANARY not in sent and "VERDICT:" not in sent


def test_audit_structure_and_grounding_inputs_match_the_flag_off_run(tmp_path, monkeypatch):
    def run(root, scope):
        root.mkdir()
        sdk = _sdk()
        claims_path = replay_fakes.setup_replay(root, monkeypatch, sdk)
        grounded_inputs = []

        async def spy(extraction, paper_text, chat_id, **kwargs):
            grounded_inputs.append((extraction.model_dump_json(), paper_text, chat_id))
            return await replay_fakes.fake_ground(extraction, paper_text, chat_id, **kwargs)

        monkeypatch.setattr(grounding, "ground_extraction", spy)
        assert asyncio.run(replay_audit._main(_args(claims_path, scope_check=scope))) == 0

        def text_of(contents):
            return [p.text for c in contents for p in c.parts]

        base = [(k, text_of(c)) for k, _, c, _ in sdk.calls if k in ("audit", "structure")]
        return base, grounded_inputs

    off = run(tmp_path / "off", False)
    on = run(tmp_path / "on", True)
    assert on == off


# --- tags and cost ----------------------------------------------------------------------

def test_scope_calls_are_tagged_priced_and_counted(tmp_path, monkeypatch):
    rc, sdk = _go(tmp_path, monkeypatch)
    assert rc == 0
    summary = _summary(tmp_path)
    records = summary["records"]
    # today's rule is unchanged for the old calls (the structurer is recorded under the "audit" context
    # and told apart by is_audit); only the two tagged calls get their own stage
    assert [r["stage"] for r in records[:4]] == ["audit", "audit", "lister", "checker"]
    assert [r["is_audit"] for r in records[:4]] == [True, False, False, False]
    assert sum(1 for r in records if r["stage"] == "lister") == 5
    assert sum(1 for r in records if r["stage"] == "checker") == 4

    by_call = summary["scope_check"]["by_call"]
    lister_usd = 5 * pricing.cost_usd(500, 60, 100)
    checker_usd = 4 * pricing.cost_usd(40_000, 200, 400, cached_tokens=39_500)
    assert by_call["lister"]["calls"] == 5 and by_call["lister"]["cached_tokens"] == 0
    assert by_call["checker"]["calls"] == 4 and by_call["checker"]["cached_tokens"] == 4 * 39_500
    assert by_call["lister"]["cost_usd"] == pytest.approx(lister_usd, abs=1e-4)
    assert by_call["checker"]["cost_usd"] == pytest.approx(checker_usd, abs=1e-4)
    audit_usd = 5 * pricing.cost_usd(40_000, 120, 300, cached_tokens=39_500)
    structure_usd = 5 * pricing.cost_usd(1_400, 250, 800)
    assert summary["cost_usd"] == pytest.approx(audit_usd + structure_usd + lister_usd + checker_usd, abs=1e-3)
    # the cache block still counts only the audit calls
    assert summary["cache"]["audit_calls"] == 5


def test_max_inr_counts_the_scope_calls(tmp_path, monkeypatch):
    # audit (INR 0.49) + structure (INR 0.50) stay under 1.05; the lister (INR 0.10) takes it over
    rc, sdk = _go(tmp_path, monkeypatch, max_inr=1.05)
    assert rc == replay_audit.EXIT_CAP_HIT
    assert sdk.kinds() == ["audit", "structure", "lister"]
    assert sdk.deleted == ["cachedContents/fake1"]
    assert _summary(tmp_path)["status"] == "VOID_CAP_HIT"


# --- failures ---------------------------------------------------------------------------

def test_lister_and_checker_failures_leave_the_verdict_and_are_counted(tmp_path, monkeypatch, caplog):
    def lister(claim_text):
        if claim_text.strip() == C_A0:
            raise errors.ClientError(400, {"error": {"code": 400, "message": "no", "status": "X"}})
        return _lister(claim_text)

    def checker(task_text):
        if C_A1 in task_text:
            return "not json"
        return _checker(task_text)

    with caplog.at_level(logging.ERROR, logger="extraction.scope_check"):
        rc, _ = _go(tmp_path, monkeypatch, sdk=_sdk(lister_fn=lister, checker_fn=checker))
    assert rc == 0
    a0, a1, a2 = _out(tmp_path, PAPER_A)["claims"]
    assert a0["label"] == a0["auditor_label"] == "supported" and a0["scope_items"] == []
    assert a1["label"] == "supported" and a1["scope_items"] == []
    scope = _summary(tmp_path)["scope_check"]
    assert (scope["lister_failures"], scope["checker_failures"], scope["verdicts_lowered"]) == (1, 1, 0)
    assert any("SCOPE LISTER FAILED" in r.getMessage() for r in caplog.records)
    assert any("SCOPE CHECKER FAILED" in r.getMessage() for r in caplog.records)


def test_item_count_mismatch_is_paired_by_index_and_counted(tmp_path, monkeypatch):
    def checker(task_text):
        # two checked items for the one listed item: the first matches, the second is dropped
        return json.dumps({"items": [
            {"item": "a", "reported": [], "status": "matches", "contradicting_quote": None},
            {"item": "b", "reported": [GOOD_QUOTE], "status": "contradicted", "contradicting_quote": GOOD_QUOTE},
        ]})

    rc, _ = _go(tmp_path, monkeypatch, sdk=_sdk(checker_fn=checker))
    assert rc == 0
    a0 = _out(tmp_path, PAPER_A)["claims"][0]
    assert a0["label"] == "supported" and len(a0["scope_items"]) == 1
    scope = _summary(tmp_path)["scope_check"]
    assert scope["item_count_mismatches"] == 4 and scope["contradicted_items"] == 0


def test_a_cached_checker_call_error_voids_the_run_like_a_cached_audit_error(tmp_path, monkeypatch):
    def checker(task_text):
        raise errors.ClientError(400, {"error": {"code": 400, "message": "bad cache", "status": "X"}})

    rc, sdk = _go(tmp_path, monkeypatch, sdk=_sdk(checker_fn=checker))
    assert rc == replay_audit.EXIT_CAP_HIT
    assert sdk.kinds() == ["audit", "structure", "lister"]
    assert sdk.deleted == ["cachedContents/fake1"]
    summary = _summary(tmp_path)
    assert summary["status"] == "VOID_CACHE_FAILED"
    assert summary["cache"]["cached_call_api_failures"] == 1


# --- --estimate -------------------------------------------------------------------------

def _targets(n):
    return [
        replay_audit.ReplayTarget(paper_id=PAPER_A, claim_index=i, claim_text_verbatim="c", claim_summary="s")
        for i in range(n)
    ]


def test_estimate_scope_check_prints_assumptions_and_the_3600_ttl_and_builds_no_client(monkeypatch, capsys):
    def fail():
        raise AssertionError("--estimate must not build a client")

    monkeypatch.setattr(engine, "_build_client", fail)
    replay_audit._print_estimate(_targets(30), "medium", 1, cache=True, scope_check=True)

    out = capsys.readouterr().out
    assert "cache TTL 3600 s" in out
    assert f"{PAPER_A}': 3600" in out and f"{PAPER_A}': 300" not in out  # the cache section agrees
    assert out.count("ASSUMPTION (lister") == 1 and out.count("ASSUMPTION (checker") == 1
    assert "ASSUMPTION: the lister + checker add" in out
    assert "cached total + scope check:" in out
    assert "suggested --max-inr with --cache --scope-check" in out
    assert "guaranteed" not in out.lower()


def test_estimate_without_the_scope_flag_is_unchanged(capsys):
    replay_audit._print_estimate(_targets(3), "medium", 1, cache=True)
    out = capsys.readouterr().out
    assert "scope" not in out.lower()
    assert "cached total" in out


def test_estimate_scope_total_is_the_cached_total_plus_the_scope_calls(capsys):
    import re

    replay_audit._print_estimate(_targets(30), "medium", 1, cache=True, scope_check=True)
    out = capsys.readouterr().out
    cached = re.search(r"\] cached total:\s+USD ([\d.]+)-([\d.]+)", out)
    scope_part = re.search(r"= USD ([\d.]+) \(INR", out)
    both = re.search(r"cached total \+ scope check: USD ([\d.]+)-([\d.]+)", out)
    assert float(both.group(2)) == pytest.approx(float(cached.group(2)) + float(scope_part.group(1)), abs=2e-3)


def test_main_estimate_prints_the_flag_on_prompt_hash(tmp_path, monkeypatch, capsys):
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, _sdk())
    assert asyncio.run(replay_audit._main(_args(claims_path, estimate=True))) == 0
    assert "scope-check prompt hash (recorded in the replay header): scopehash001" in capsys.readouterr().out
