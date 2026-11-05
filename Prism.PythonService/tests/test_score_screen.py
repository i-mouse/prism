"""Unit tests for eval/score_screen.py. Offline: invented row ids and fixtures in tmp_path only; the
adjudicated rows and the row-group constants are patched in, so no dev_eval / match map is read."""
import copy
import json
import sys

import pytest

from eval import score_screen
from eval.score_replay import AdjudicatedRow
from eval.types import ExpectedRow

MISSES = ("M1", "M2", "M3", "M4")      # M1, M2 are the parked rows
REALS = ("H1", "H2")
OTHERS = ("O1",)
PARKED = ("M1", "M2")
ALL_IDS = MISSES + REALS + OTHERS
SUP, PS, NS = "supported", "partially_supported", "not_supported"
CFG = {"backend": "vertex", "auditor_model": "gemini-3.8-flash", "thinking_level": "medium",
       "other_models": {"grounding": "gemini-3.1-flash-lite"}, "project": "p"}


def _rows() -> list[AdjudicatedRow]:
    return [
        AdjudicatedRow(row_id=rid, paper_id=f"paper-{rid}", claim_index=0,
                       expected_row=ExpectedRow(id=rid, expected_label="not_supported", grounding_negative=True))
        for rid in ALL_IDS
    ]


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(score_screen, "resolve_adjudicated_rows", lambda *a, **k: _rows())
    monkeypatch.setattr(score_screen, "MISS_ROWS", MISSES)
    monkeypatch.setattr(score_screen, "REAL_HITS", REALS)
    monkeypatch.setattr(score_screen, "OTHER_ROWS", OTHERS)
    monkeypatch.setattr(score_screen, "PARKED_ROWS", PARKED)


def _base_labels() -> dict[str, list[str]]:
    labels = {rid: [SUP] * 3 for rid in MISSES}
    labels.update({rid: [NS] * 3 for rid in REALS})
    labels.update({rid: [SUP] * 3 for rid in OTHERS})
    return labels


def _write_folder(folder, labels: dict[str, str], *, summary="none", skip=(), served=None):
    """summary: None = no _summary.json, "none" = summary without run_config, dict = that run_config."""
    folder.mkdir(parents=True, exist_ok=True)
    for rid in ALL_IDS:
        if rid in skip:
            continue
        claim = {"index": 0, "label": labels[rid], "missing": False, "grounding_status": None,
                 "claim_text_verbatim": "c", "evidence_spans": []}
        if served is not None and rid in served:
            claim["audit_model_served"] = served[rid]
        (folder / f"paper-{rid}.json").write_text(
            json.dumps({"header": {}, "claims": [claim], "matches": []}), encoding="utf-8")
    if summary is not None:
        body = {"calls": 1} if summary == "none" else {"run_config": summary}
        (folder / "_summary.json").write_text(json.dumps(body), encoding="utf-8")


def _arm(tmp_path, labels=None, configs=("none", "none", "none"), skips=((), (), ()), served=(None, None, None)):
    labels = labels or _base_labels()
    dirs = [tmp_path / f"rep_{i}" for i in (1, 2, 3)]
    for i, d in enumerate(dirs):
        _write_folder(d, {rid: labels[rid][i] for rid in ALL_IDS}, summary=configs[i], skip=skips[i], served=served[i])
    return dirs


def _run(dirs, capsys, json_out=None):
    code = score_screen.run(dirs, None, None, None, json_out)
    return code, capsys.readouterr().out


def _cfg(**changes):
    cfg = copy.deepcopy(CFG)
    cfg.update(changes)
    return cfg


def _row_line(out, rid):
    return next(line for line in out.splitlines() if line.strip().startswith(rid + " "))


# --- votes ---------------------------------------------------------------

def test_miss_caught_at_two_of_three_not_at_one(tmp_path, capsys):
    labels = _base_labels()
    labels["M3"] = [PS, PS, SUP]
    labels["M4"] = [PS, SUP, SUP]
    code, out = _run(_arm(tmp_path, labels), capsys)
    assert code == 0
    assert _row_line(out, "M3").endswith("CAUGHT") and "[miss]" in _row_line(out, "M3")
    assert _row_line(out, "M4").endswith("-")


def test_not_supported_counts_as_caught(tmp_path, capsys):
    labels = _base_labels()
    labels["M3"] = [NS, PS, SUP]
    _, out = _run(_arm(tmp_path, labels), capsys)
    assert _row_line(out, "M3").endswith("CAUGHT")


def test_real_hit_lost_at_two_of_three_not_at_one(tmp_path, capsys):
    labels = _base_labels()
    labels["H1"] = [SUP, SUP, NS]
    labels["H2"] = [SUP, NS, NS]
    _, out = _run(_arm(tmp_path, labels), capsys)
    assert _row_line(out, "H1").endswith("LOST") and "[real hit]" in _row_line(out, "H1")
    assert _row_line(out, "H2").endswith("-")


def test_lost_label_is_not_a_caught_vote_and_vice_versa(tmp_path, capsys):
    labels = _base_labels()
    labels["M3"] = [SUP, SUP, SUP]      # a miss labelled supported is simply not caught, never "LOST"
    labels["H1"] = [PS, PS, PS]         # a real hit labelled partially_supported is not lost
    _, out = _run(_arm(tmp_path, labels), capsys)
    assert _row_line(out, "M3").endswith("-") and "LOST" not in _row_line(out, "M3")
    assert _row_line(out, "H1").endswith("-")


def test_totals_and_parked_exclusion(tmp_path, capsys):
    labels = _base_labels()
    labels["M1"] = [PS] * 3      # parked, caught
    labels["M3"] = [NS] * 3      # target, caught
    labels["H1"] = [SUP] * 3     # lost
    code, out = _run(_arm(tmp_path, labels), capsys)
    assert code == 0
    assert "Misses caught: 2/4" in out
    assert "Misses caught excluding parked rows (auditor targets): 1/2" in out
    assert "Real hits lost: 1/2" in out
    parked = out.split("Parked rows")[1].split("Report only")[0]
    assert "M1" in parked and "M2" in parked and "CAUGHT" in parked


def test_other_row_is_printed_with_dash_and_counted_nowhere(tmp_path, capsys):
    labels = _base_labels()
    labels["O1"] = [PS] * 3
    _, out = _run(_arm(tmp_path, labels), capsys)
    assert "[other]" in _row_line(out, "O1") and _row_line(out, "O1").endswith("-")
    assert "Misses caught: 0/4" in out and "Real hits lost: 0/2" in out


def test_prints_each_folder_as_absolute_path(tmp_path, capsys):
    dirs = _arm(tmp_path)
    _, out = _run(dirs, capsys)
    for d in dirs:
        assert str(d.resolve()) in out


# --- INVALID (S5) ----------------------------------------------------------

def _assert_invalid(code, out, *reasons):
    assert code == 1
    for reason in reasons:
        assert f"INVALID: " in out and reason in out
    assert "Misses caught" not in out and "Real hits lost" not in out


def test_invalid_when_a_row_has_no_claim_in_one_folder(tmp_path, capsys):
    dirs = _arm(tmp_path, skips=((), ("M3",), ()))
    code, out = _run(dirs, capsys)
    _assert_invalid(code, out, "M3 FIXTURE_MISSING")
    assert "rep_2" in out


def test_invalid_when_claim_out_of_scope_or_absent(tmp_path, capsys):
    dirs = _arm(tmp_path)
    path = dirs[0] / "paper-H1.json"
    path.write_text(json.dumps({"header": {"claims_scope": [5]}, "claims": [], "matches": []}), encoding="utf-8")
    code, out = _run(dirs, capsys)
    _assert_invalid(code, out, "H1 no claim data")


def test_invalid_on_label_outside_replay_labels_without_crash(tmp_path, capsys):
    labels = _base_labels()
    labels["M3"] = [PS, "mostly_supported", PS]
    code, out = _run(_arm(tmp_path, labels), capsys)
    _assert_invalid(code, out, "M3 label 'mostly_supported' is not a replay label")


def test_invalid_when_a_folder_has_no_summary(tmp_path, capsys):
    code, out = _run(_arm(tmp_path, configs=("none", None, "none")), capsys)
    _assert_invalid(code, out, "rep_2")
    assert "no _summary.json" in out


def test_invalid_when_a_folder_is_missing(tmp_path, capsys):
    dirs = _arm(tmp_path)
    dirs[1] = tmp_path / "does_not_exist"
    code, out = _run(dirs, capsys)
    _assert_invalid(code, out, "does_not_exist: folder missing")


def test_invalid_when_a_row_is_not_adjudicated(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(score_screen, "resolve_adjudicated_rows", lambda *a, **k: _rows()[:-1])
    code, out = _run(_arm(tmp_path), capsys)
    _assert_invalid(code, out, "rows not adjudicated refusal rows: O1")


@pytest.mark.parametrize("key,other", [
    ("backend", "aistudio"), ("auditor_model", "gemini-3.6-flash"), ("thinking_level", "high"),
    ("other_models", {"grounding": "something-else"}),
])
def test_invalid_when_run_config_differs(tmp_path, capsys, key, other):
    code, out = _run(_arm(tmp_path, configs=(CFG, CFG, _cfg(**{key: other}))), capsys)
    _assert_invalid(code, out, f"run_config.{key} differs")


def test_run_config_fields_outside_the_four_may_differ(tmp_path, capsys):
    code, out = _run(_arm(tmp_path, configs=(CFG, CFG, _cfg(project="other-project"))), capsys)
    assert code == 0 and "INVALID" not in out


@pytest.mark.parametrize("configs", [("none", CFG, CFG), (CFG, CFG, "none")])
def test_invalid_when_default_folder_mixed_with_run_config_folders(tmp_path, capsys, configs):
    code, out = _run(_arm(tmp_path, configs=configs), capsys)
    _assert_invalid(code, out, "run_config present in some folders but not in")


def test_all_default_folders_without_run_config_are_valid(tmp_path, capsys):
    code, out = _run(_arm(tmp_path), capsys)
    assert code == 0 and "INVALID" not in out
    assert "run_config: default" in out
    assert "n/a" in out


def test_all_matching_run_configs_are_valid(tmp_path, capsys):
    code, out = _run(_arm(tmp_path, configs=(CFG, CFG, CFG)), capsys)
    assert code == 0 and "gemini-3.8-flash" in out


# --- backup report (S6) ----------------------------------------------------

def test_backup_count_and_ids_per_folder(tmp_path, capsys):
    served_ok = {rid: "gemini-3.8-flash" for rid in ALL_IDS}
    served_bad = dict(served_ok, M3="gemini-3.1-flash-lite", H1=None)
    dirs = _arm(tmp_path, configs=(CFG, CFG, CFG), served=(served_ok, served_bad, {**served_ok, "M4": "vertex_ai/gemini-3.8-flash"}))
    code, out = _run(dirs, capsys)
    assert code == 0
    report = out.split("Report only")[1]
    assert f"{dirs[0].resolve()}: 0 (none)" in report
    assert f"{dirs[1].resolve()}: 2 (M3, H1)" in report
    assert f"{dirs[2].resolve()}: 0 (none)" in report   # a provider prefix is not a different model


def test_backup_is_report_only_and_does_not_change_votes(tmp_path, capsys):
    labels = _base_labels()
    labels["M3"] = [PS] * 3
    served = {rid: "other-model" for rid in ALL_IDS}
    _, out = _run(_arm(tmp_path, labels, configs=(CFG, CFG, CFG), served=(served, served, served)), capsys)
    assert _row_line(out, "M3").endswith("CAUGHT")
    assert "Misses caught: 1/4" in out


def test_backup_is_na_for_folder_without_the_field(tmp_path, capsys):
    served = {rid: "gemini-3.8-flash" for rid in ALL_IDS}
    dirs = _arm(tmp_path, configs=(CFG, CFG, CFG), served=(served, None, served))
    _, out = _run(dirs, capsys)
    assert f"{dirs[1].resolve()}: n/a" in out
    assert f"{dirs[0].resolve()}: 0 (none)" in out


# --- JSON output (S7) --------------------------------------------------------

def test_json_out_matches_results_and_is_outside_fixture_folders(tmp_path, capsys):
    labels = _base_labels()
    labels["M3"] = [PS] * 3
    labels["M1"] = [NS] * 3
    dirs = _arm(tmp_path, labels, configs=(CFG, CFG, CFG))
    out_path = tmp_path / "out" / "arm.json"
    code, _ = _run(dirs, capsys, out_path)
    assert code == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["totals"]["misses_caught"] == 2 and data["totals"]["auditor_targets_caught"] == 1
    assert data["totals"]["misses_caught_ids"] == ["M1", "M3"]
    assert {r["row_id"]: r["verdict"] for r in data["rows"]}["M3"] == "CAUGHT"
    assert [p["row_id"] for p in data["parked"]] == ["M1", "M2"]
    assert data["run_config"] == CFG
    assert data["fixture_dirs"] == [str(d.resolve()) for d in dirs]
    assert len(data["backup"]) == 3


def test_json_out_inside_a_fixture_folder_is_refused_and_nothing_written(tmp_path, capsys):
    dirs = _arm(tmp_path)
    target = dirs[0] / "nested" / "arm.json"
    code, out = _run(dirs, capsys, target)
    assert code == 1 and "INVALID" in out and "--json-out" in out
    assert not target.exists() and not (dirs[0] / "nested").exists()


def test_json_out_not_written_when_invalid(tmp_path, capsys):
    dirs = _arm(tmp_path, skips=((), ("M3",), ()))
    target = tmp_path / "arm.json"
    code, _ = _run(dirs, capsys, target)
    assert code == 1 and not target.exists()


# --- CLI and setup ---------------------------------------------------------

def _argv(monkeypatch, dirs, *extra):
    monkeypatch.setattr(sys, "argv", ["score_screen"] + [a for d in dirs for a in ("--fixture-dir", str(d))] + list(extra))


def test_main_requires_exactly_three_fixture_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["score_screen", "--fixture-dir", str(tmp_path), "--fixture-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        score_screen.main()
    assert exc.value.code == 2


def test_main_exit_codes(tmp_path, monkeypatch):
    dirs = _arm(tmp_path)
    _argv(monkeypatch, dirs)
    with pytest.raises(SystemExit) as ok:
        score_screen.main()
    assert ok.value.code == 0
    _argv(monkeypatch, [dirs[0], dirs[1], tmp_path / "nope"])
    with pytest.raises(SystemExit) as bad:
        score_screen.main()
    assert bad.value.code == 1


def test_stop_when_parked_row_is_not_a_miss_row(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(score_screen, "PARKED_ROWS", ("M1", "H1"))
    code, out = _run(_arm(tmp_path), capsys)
    assert code == 1 and "STOP: parked row H1 is not a miss row" in out
    assert "Misses caught" not in out


def test_real_constants_are_consistent(monkeypatch):
    from eval import score_a1
    monkeypatch.undo()   # drop the invented ids; check the shipped ones
    assert set(score_screen.PARKED_ROWS) <= set(score_a1.MISS_ROWS)
    groups = score_a1.MISS_ROWS + score_a1.REAL_HITS + score_screen.OTHER_ROWS
    assert len(groups) == len(set(groups)) == 18
    assert score_screen._setup_errors() == []
    assert score_screen.VOTES_NEEDED == score_a1.VOTES_NEEDED and score_screen.FIXED_LABELS == score_a1.FIXED_LABELS
