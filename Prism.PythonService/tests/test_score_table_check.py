"""Unit tests for eval/step4/score_table_check.py and its hook in eval/score_full_check.py: the flagged folder cost
(M7), the projection, the found -> routed -> failed -> caught report and V6. Offline, invented ids and folders."""
import json
from types import SimpleNamespace

import pytest

from eval import pricing, score_full_check as sfc
from eval.step4 import score_table_check as stc

MODEL = "gemini-3.6-flash"
SUP, PS, NS = "supported", "partially_supported", "not_supported"


def _record(stage, is_audit, prompt=1000, output=100, thought=400, cached=0, model=MODEL):
    return {"stage": stage, "is_audit": is_audit, "model_used": model, "prompt_tokens": prompt, "output_tokens": output,
            "thought_tokens": thought, "cached_tokens": cached, "tool_use_tokens": 0}


def _usd(prompt=1000, output=100, thought=400, cached=0):
    return pricing.strict_cost_usd_for_model(MODEL, prompt, output, thought, cached, 0)


def _block(**overrides):
    block = {
        "claims": 4, "routed_claims": 2, "pieces": 3, "failed_pieces": 1, "guard_failures": 1, "fallback_claims": 1,
        "lister_failures": 0, "checker_failures": 0, "answers": {"backed": 2, "not_backed": 1},
        "could_not_check": {"guard_failed": 1}, "guard_reasons": {"value_missing": 1},
        "fallback_reasons": {"could_not_check": 1}, "checker_labels": {PS: 1}, "unrouted": {"no_table_mention": 2},
        "config": {"lister_hash": "aaa", "checker_hash": "bbb", "finder_commit": "f7ca8a3", "block_cap_hits": {}},
    }
    block.update(overrides)
    return block


FLAGGED_RECORDS = [
    _record("audit", True), _record("audit", False),                      # unrouted claim: audit + structure
    _record("audit", True), _record("audit", False),
    _record("lister", False, 500, 60, 100), _record("table_checker", False, 3000, 150, 500),
    _record("lister", False, 500, 60, 100), _record("table_checker", False, 3000, 150, 500),
    _record("audit_fallback", True), _record("audit_fallback", False),     # fallback audit + its structure
]


def _flagged_summary(**overrides):
    return {"status": "OK", "records": list(FLAGGED_RECORDS), "table_check": _block(**overrides)}


# --- cost -----------------------------------------------------------------------------------------------------

def test_is_flagged():
    assert stc.is_flagged(_flagged_summary())
    assert not stc.is_flagged({"records": []}) and not stc.is_flagged(None) and not stc.is_flagged({"table_check": None})


def test_record_kind_counts_audit_fallback_lister_checker_and_never_the_structurer():
    assert [stc.record_kind(r) for r in FLAGGED_RECORDS] == [
        "audit", None, "audit", None, "lister", "table_checker", "lister", "table_checker", "audit_fallback", None,
    ]


def test_flagged_folder_cost_counts_all_three_new_call_kinds_per_claim(tmp_path):
    invalid: list[str] = []
    cost = stc.folder_cost(tmp_path, _flagged_summary(), invalid)
    assert invalid == []
    counted_usd = 3 * _usd() + 2 * _usd(500, 60, 100) + 2 * _usd(3000, 150, 500)
    assert cost["claims"] == 4 and cost["table_check"] is True
    assert cost["calls_by_kind"] == {"audit": 2, "audit_fallback": 1, "lister": 2, "table_checker": 2}
    assert cost["audit_calls"] == 3
    assert cost["audit_inr_total"] == pytest.approx(counted_usd * pricing.INR_PER_USD, abs=0.01)
    assert cost["audit_inr_per_claim"] == pytest.approx(counted_usd * pricing.INR_PER_USD / 4, abs=1e-4)
    assert cost["inr_by_kind"]["audit_fallback"] == pytest.approx(_usd() * pricing.INR_PER_USD, abs=0.01)
    assert cost["mean_prompt_tokens"] == pytest.approx((3 * 1000 + 2 * 500 + 2 * 3000) / 4)
    # no cache block: the overhead is zero and the two per-claim numbers agree
    assert cost["cache_overhead_inr"] == 0 and cost["audit_inr_per_claim_incl_cache_overhead"] == cost["audit_inr_per_claim"]


def test_cache_overhead_is_reported_beside_the_cost_not_inside_it(tmp_path):
    summary = _flagged_summary()
    summary["cache"] = {"overhead_usd": 0.02}
    cost = stc.folder_cost(tmp_path, summary, [])
    plain = stc.folder_cost(tmp_path, _flagged_summary(), [])
    assert cost["audit_inr_per_claim"] == plain["audit_inr_per_claim"]
    assert cost["cache_overhead_inr"] == pytest.approx(0.02 * pricing.INR_PER_USD)
    assert cost["audit_inr_per_claim_incl_cache_overhead"] == pytest.approx(
        plain["audit_inr_per_claim"] + 0.02 * pricing.INR_PER_USD / 4, abs=1e-4)


def test_flagged_folder_cost_invalid_cases(tmp_path):
    for summary, needle in (
        ({"table_check": _block()}, "no records"),
        (_flagged_summary(claims=0), "no claim count"),
        ({"records": [_record("lister", False, model=None)], "table_check": _block()}, "no model_used"),
        ({"records": [_record("table_checker", False, model="made-up-model-9")], "table_check": _block()}, str(tmp_path)),
    ):
        invalid: list[str] = []
        assert stc.folder_cost(tmp_path, summary, invalid) is None
        assert len(invalid) == 1 and needle in invalid[0]


def test_score_full_check_folder_cost_dispatches_on_the_flag_and_leaves_unflagged_folders_alone(tmp_path):
    flagged = sfc._folder_cost(sfc.FolderMeta(tmp_path, _flagged_summary(), {}), [])
    assert flagged["table_check"] is True and flagged["claims"] == 4

    unflagged_summary = {"status": "OK", "records": [_record("audit", True), _record("audit", False)]}
    unflagged = sfc._folder_cost(sfc.FolderMeta(tmp_path, unflagged_summary, {}), [])
    assert set(unflagged) == {
        "folder", "audit_calls", "mean_prompt_tokens", "mean_cached_tokens", "mean_output_tokens",
        "mean_thought_tokens", "audit_inr_per_claim", "audit_inr_total",
    }
    assert unflagged["audit_calls"] == 1
    assert unflagged["audit_inr_per_claim"] == pytest.approx(_usd() * pricing.INR_PER_USD, abs=1e-4)


# --- M7 -------------------------------------------------------------------------------------------------------

def test_m7_projection_and_gate():
    candidate = [{"audit_inr_per_claim": v, "audit_inr_per_claim_incl_cache_overhead": v + 0.01} for v in (0.50, 0.52, 0.54)]
    baseline = [{"audit_inr_per_claim": v} for v in (0.48, 0.50, 0.52)]
    m = stc.m7(candidate, baseline)
    assert (m["D_inr_per_claim"], m["Bc_inr_per_claim"]) == (0.52, 0.5)
    assert m["projected_inr_per_paper"] == pytest.approx(196 + 0.02 * 2 * 30.17, abs=0.01) and m["pass"] is True
    assert m["projected_inr_per_paper_incl_cache_overhead"] == pytest.approx(196 + 0.03 * 2 * 30.17, abs=0.01)

    over = stc.m7([{"audit_inr_per_claim": 0.60}], [{"audit_inr_per_claim": 0.50}])
    assert over["projected_inr_per_paper"] == pytest.approx(202.03, abs=0.01) and over["pass"] is False
    cheaper = stc.m7([{"audit_inr_per_claim": 0.40}], [{"audit_inr_per_claim": 0.50}])
    assert cheaper["projected_inr_per_paper"] < 196 and cheaper["pass"] is True


# --- rows -----------------------------------------------------------------------------------------------------

def _trace(source="checker", n_failed=0, routed=True):
    if not routed:
        return {"routed": False, "source": "audit", "reason": "no_table_mention", "cited": []}
    return {"routed": True, "source": source, "n_failed": n_failed, "pieces": []}


def _row(row_id, has_claim=True):
    return SimpleNamespace(row_id=row_id, paper_id=f"paper-{row_id}", claim_index=0 if has_claim else None)


def _folder(root, name, claims: dict) -> object:
    """claims: row id -> (label, table_check trace) or None for a paper file with no such claim."""
    folder = root / name
    folder.mkdir()
    for row_id, value in claims.items():
        body = {"header": {}, "matches": [], "claims": []}
        if value is not None:
            label, trace = value
            body["claims"].append({"index": 0, "label": label, "table_check": trace})
        (folder / f"paper-{row_id}.json").write_text(json.dumps(body), encoding="utf-8")
    return folder


def test_row_report_steps_per_run_and_voted(tmp_path):
    runs = [
        _folder(tmp_path, "d1", {
            "R1": (PS, _trace(n_failed=1)), "R2": (SUP, _trace()), "R3": (NS, _trace(routed=False)), "R4": None,
            "S1": (PS, _trace(n_failed=1)), "S2": (PS, _trace(source="fallback_audit")), "S3": (SUP, _trace(routed=False)),
        }),
        _folder(tmp_path, "d2", {
            "R1": (PS, _trace(n_failed=2)), "R2": (SUP, _trace()), "R3": (NS, _trace(routed=False)), "R4": None,
            "S1": (NS, _trace(n_failed=1)), "S2": (SUP, _trace()), "S3": (SUP, _trace(routed=False)),
        }),
        _folder(tmp_path, "d3", {
            "R1": (SUP, _trace(source="fallback_audit")), "R2": (PS, _trace(n_failed=1)),
            "R3": (NS, _trace(routed=False)), "R4": None,
            "S1": (SUP, _trace()), "S2": (SUP, _trace()), "S3": (SUP, _trace(routed=False)),
        }),
    ]
    report = stc.row_report(
        [_row("R1"), _row("R2"), _row("R3"), _row("R4"), _row("R5", has_claim=False)],
        [_row("S1"), _row("S2"), _row("S3"), _row("S4", has_claim=False)], runs,
    )
    by_id = {r["row_id"]: r for r in report["refusal_rows"]}
    assert by_id["R1"]["per_run"] == [
        {"found": True, "routed": True, "failed": True, "caught": True},
        {"found": True, "routed": True, "failed": True, "caught": True},
        {"found": True, "routed": True, "failed": False, "caught": False},
    ]
    assert by_id["R1"]["voted"] == {"found": True, "routed": True, "failed": True, "caught": True}
    assert by_id["R2"]["voted"] == {"found": True, "routed": True, "failed": False, "caught": False}
    # caught by today's auditor without being routed: found and caught, never routed or failed
    assert by_id["R3"]["voted"] == {"found": True, "routed": False, "failed": False, "caught": True}
    assert by_id["R4"]["voted"] == by_id["R5"]["voted"] == {"found": False, "routed": False, "failed": False, "caught": False}

    s = report["s_rows"]
    assert s["routed_per_run"] == [["S1", "S2"], ["S1", "S2"], ["S1", "S2"]] and s["routed_voted"] == ["S1", "S2"]
    # S2's run-1 lowering came from the fallback audit, not from the checker
    assert s["lowered_per_run"] == [["S1"], ["S1"], []] and s["lowered_voted"] == ["S1"]


# --- totals and V6 --------------------------------------------------------------------------------------------

def test_totals_sum_counters_and_dicts(tmp_path):
    folders = [
        stc.folder_totals(tmp_path / "a", {"table_check": _block()}),
        stc.folder_totals(tmp_path / "b", {"table_check": _block(routed_claims=5, answers={"no_row": 4})}),
    ]
    total = stc.totals(folders)
    assert (total["claims"], total["routed_claims"], total["pieces"], total["guard_failures"]) == (8, 7, 6, 2)
    assert total["answers"] == {"backed": 2, "no_row": 4, "not_backed": 1}
    assert total["fallback_claims"] == 2 and total["v6"]["void"] is False and total["v6"]["share"] == 0
    assert stc.config_differences(folders) == []


@pytest.mark.parametrize("failures, routed, void", [
    (0, 100, False), (5, 100, False), (6, 100, True), (1, 20, False), (2, 20, True), (0, 0, False),
])
def test_v6_is_void_only_above_five_percent_of_routed_claims(tmp_path, failures, routed, void):
    folders = [
        stc.folder_totals(tmp_path, {"table_check": _block(routed_claims=routed, lister_failures=failures, checker_failures=0)}),
        stc.folder_totals(tmp_path, {"table_check": _block(routed_claims=0, lister_failures=0, checker_failures=0)}),
    ]
    v6 = stc.totals(folders)["v6"]
    assert (v6["failures_after_retry"], v6["routed_claims"], v6["void"]) == (failures, routed, void)


def test_v6_adds_lister_and_checker_failures():
    folder = stc.folder_totals("x", {"table_check": _block(routed_claims=20, lister_failures=1, checker_failures=1)})
    assert stc.totals([folder])["v6"]["void"] is True


def test_config_differences_name_a_changed_hash(tmp_path):
    a = stc.folder_totals(tmp_path, {"table_check": _block()})
    changed = _block()
    changed["config"] = {**changed["config"], "checker_hash": "zzz"}
    reasons = stc.config_differences([a, stc.folder_totals(tmp_path, {"table_check": changed})])
    assert len(reasons) == 1 and "checker_hash" in reasons[0]


# --- printout -------------------------------------------------------------------------------------------------

def test_print_report_shows_ids_counts_and_letters_only(tmp_path, capsys):
    run = _folder(tmp_path, "d1", {"R1": (PS, _trace(n_failed=1)), "S1": (PS, _trace(n_failed=1))})
    folders = [stc.folder_totals(tmp_path / "d1", {"table_check": _block(routed_claims=10, checker_failures=1)})]
    report = {
        "m7": stc.m7([{"audit_inr_per_claim": 0.60}], [{"audit_inr_per_claim": 0.50}]),
        "rows": stc.row_report([_row("R1")], [_row("S1")], [run, run, run]),
        "per_folder": folders, "totals": stc.totals(folders),
    }
    stc.print_report(report)
    out = capsys.readouterr().out
    assert "M7 cost gate" in out and "FAIL" in out
    assert "R1" in out and "yyyy" in out
    assert "S rows lowered by the checker: per run [1, 1, 1], voted 1 ['S1']" in out
    assert "V6: lister + checker failures after retry 1 of 10 routed claims = 10.00%" in out and "VOID" in out
