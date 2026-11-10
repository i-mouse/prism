"""Unit tests for eval/score_a1.py. Offline: invented fixtures in tmp_path only; the
adjudicated rows are patched in so no dev_eval / match map is read."""
import json
import sys

import pytest

from eval import score_a1
from eval.score_replay import AdjudicatedRow
from eval.types import ExpectedRow

ALL_IDS = list(dict.fromkeys(score_a1.MISS_ROWS + score_a1.ALWAYS_MISSED + score_a1.REAL_HITS))
NOT_FIXED = "supported"
FIXED = "partially_supported"


def _rows() -> list[AdjudicatedRow]:
    return [
        AdjudicatedRow(row_id=rid, paper_id=f"paper-{rid}", claim_index=0,
                       expected_row=ExpectedRow(id=rid, expected_label="not_supported", grounding_negative=True))
        for rid in ALL_IDS
    ]


@pytest.fixture(autouse=True)
def _patch_rows(monkeypatch):
    monkeypatch.setattr(score_a1, "resolve_adjudicated_rows", lambda *a, **k: _rows())


def _claim(index: int, label: str, *, scope: bool = True, **extra) -> dict:
    claim = {"index": index, "label": label, "claim_summary": "s", "missing": False, "grounding_status": None,
             "claim_text_verbatim": "c", "evidence_spans": []}
    if scope:
        claim.update({"auditor_label": label, "scope_lowered": False, "scope_item": None,
                      "scope_item_kind": None, "scope_quote": None, "scope_items": []})
    claim.update(extra)
    return claim


def _write_folder(folder, labels: dict[str, str], *, scope: bool = True, skip: tuple[str, ...] = (),
                  claim_overrides: dict[str, dict] | None = None, extra_claims: list[dict] | None = None):
    folder.mkdir(parents=True, exist_ok=True)
    for rid in ALL_IDS:
        if rid in skip:
            continue
        claim = _claim(0, labels[rid], scope=scope, **((claim_overrides or {}).get(rid, {})))
        (folder / f"paper-{rid}.json").write_text(
            json.dumps({"header": {}, "claims": [claim], "matches": []}), encoding="utf-8")
    if extra_claims:
        (folder / "extra.json").write_text(
            json.dumps({"header": {}, "claims": extra_claims, "matches": []}), encoding="utf-8")


def _passing_labels() -> dict[str, str]:
    labels = {rid: FIXED for rid in score_a1.MISS_ROWS}
    labels.update({rid: "not_supported" for rid in score_a1.REAL_HITS})
    return labels


def _folders(tmp_path, labels=None, n=3):
    return [tmp_path / f"scope_{i}" for i in range(1, n + 1)]


def _run(dirs, capsys):
    code = score_a1.run(dirs, None, None, None)
    return code, capsys.readouterr().out


def _lowered_claim(index=0, **overrides) -> dict:
    claim = _claim(index, FIXED, auditor_label="supported", scope_lowered=True, scope_item="all tasks",
                   scope_item_kind="quantifier", scope_quote="a long contradicting quote here",
                   scope_items=[{"text": "all tasks", "kind": "quantifier", "status": "contradicted",
                                 "contradicting_quote": "a long contradicting quote here", "guard_passed": True}])
    claim.update(overrides)
    return claim


# --- validity -------------------------------------------------------------

def test_invalid_on_missing_fixture_exit_1_and_no_marks(tmp_path, capsys):
    dirs = _folders(tmp_path)
    _write_folder(dirs[0], _passing_labels())
    _write_folder(dirs[1], _passing_labels(), skip=("P3-R2",))
    _write_folder(dirs[2], _passing_labels())
    code, out = _run(dirs, capsys)
    assert code == 1
    assert "INVALID" in out and "P3-R2 FIXTURE_MISSING" in out and "scope_2" in out
    assert "A1-fixed" not in out and "A1 PASS" not in out and "A1 FAIL" not in out


def test_invalid_on_folder_with_no_scope_fields(tmp_path, capsys):
    dirs = _folders(tmp_path)
    _write_folder(dirs[0], _passing_labels())
    _write_folder(dirs[1], _passing_labels(), scope=False)
    _write_folder(dirs[2], _passing_labels())
    code, out = _run(dirs, capsys)
    assert code == 1
    assert "scope_2: no scope fields" in out
    assert "A1-fixed" not in out


def test_invalid_when_one_scored_claim_lacks_scope_fields_in_flag_on_folder(tmp_path, capsys):
    dirs = _folders(tmp_path)
    for d in dirs:
        _write_folder(d, _passing_labels())
    # rewrite one scored row's claim in folder 3 without scope fields; the folder still has them elsewhere
    path = dirs[2] / "paper-P4-R1.json"
    path.write_text(json.dumps({"header": {}, "claims": [_claim(0, FIXED, scope=False)], "matches": []}),
                    encoding="utf-8")
    code, out = _run(dirs, capsys)
    assert code == 1
    assert "scope_3: P4-R1 claim lacks scope fields" in out
    assert "no scope fields (not a flag-on run)" not in out
    assert "A1 PASS" not in out


def test_main_exits_1_on_invalid(tmp_path, monkeypatch):
    dirs = _folders(tmp_path)
    for d in dirs:
        _write_folder(d, _passing_labels(), scope=False)
    monkeypatch.setattr(sys, "argv", ["score_a1"] + [a for d in dirs for a in ("--fixture-dir", str(d))])
    with pytest.raises(SystemExit) as exc:
        score_a1.main()
    assert exc.value.code == 1


def test_main_requires_exactly_three_fixture_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["score_a1", "--fixture-dir", str(tmp_path), "--fixture-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        score_a1.main()
    assert exc.value.code == 2


# --- marks ----------------------------------------------------------------

def _labels_for(miss: dict[str, list[str]]) -> dict[str, list[str]]:
    labels = {rid: [NOT_FIXED] * 3 for rid in score_a1.MISS_ROWS}
    labels.update({rid: ["not_supported"] * 3 for rid in score_a1.REAL_HITS})
    labels.update(miss)
    return labels


def test_fixed_counted_at_two_of_three_not_at_one():
    two = _labels_for({"P3-R2": [FIXED, FIXED, NOT_FIXED]})
    one = _labels_for({"P3-R2": [FIXED, NOT_FIXED, NOT_FIXED]})
    assert score_a1.mark_fixed(two)[0] == ["P3-R2"]
    assert score_a1.mark_fixed(one)[0] == []


def test_fixed_counts_not_supported_too():
    labels = _labels_for({"P3-R2": ["not_supported", FIXED, NOT_FIXED]})
    assert score_a1.mark_fixed(labels)[0] == ["P3-R2"]


def test_always_missed_sub_mark_can_fail_with_enough_fixed():
    # 6 fixed overall, but only 3 of the 6 always-missed
    miss = {rid: [FIXED] * 3 for rid in ("P3-R2", "P4-R1", "P4-R2", "P1-R1", "P5-R1", "P7-R1")}
    fixed, always, passed = score_a1.mark_fixed(_labels_for(miss))
    assert len(fixed) == 6 and len(always) == 3 and not passed


def test_fixed_pass_threshold_boundary():
    four_always_one_other = {rid: [FIXED] * 3 for rid in ("P3-R2", "P4-R1", "P4-R2", "P5-R2", "P1-R1")}
    assert score_a1.mark_fixed(_labels_for(four_always_one_other))[2] is True
    four = {rid: [FIXED] * 3 for rid in ("P3-R2", "P4-R1", "P4-R2", "P5-R2")}
    assert score_a1.mark_fixed(_labels_for(four))[2] is False


def test_lost_at_two_of_three_not_at_one():
    two = _labels_for({})
    two["P2-R5"] = ["supported", "supported", "not_supported"]
    one = _labels_for({})
    one["P2-R5"] = ["supported", "not_supported", "not_supported"]
    assert score_a1.mark_lost(two) == (["P2-R5"], True)
    assert score_a1.mark_lost(one) == ([], True)


def test_lost_fails_at_two_lost_rows():
    labels = _labels_for({})
    labels["P2-R5"] = ["supported"] * 3
    labels["P6-R1"] = ["supported"] * 3
    lost, passed = score_a1.mark_lost(labels)
    assert lost == ["P2-R5", "P6-R1"] and not passed


def test_quote_violation_lowered_with_null_quote():
    claims = {"f": [("p", _lowered_claim(scope_quote=None))]}
    violations = score_a1.mark_quote(claims)
    assert len(violations) == 1 and "null scope_quote" in violations[0]


def test_quote_violation_lowered_with_guard_passed_false():
    item = {"text": "all tasks", "kind": "quantifier", "status": "contradicted",
            "contradicting_quote": "a long contradicting quote here", "guard_passed": False}
    claims = {"f": [("p", _lowered_claim(scope_items=[item]))]}
    violations = score_a1.mark_quote(claims)
    assert len(violations) == 1 and "guard_passed is not true" in violations[0]


def test_quote_violation_no_matching_entry():
    claims = {"f": [("p", _lowered_claim(scope_items=[]))]}
    assert "no matching scope_items entry" in score_a1.mark_quote(claims)[0]


def test_quote_valid_lowered_claim_and_unlowered_claims_pass():
    claims = {"f": [("p", _lowered_claim()), ("p", _claim(1, "supported"))]}
    assert score_a1.mark_quote(claims) == []


# --- end to end -----------------------------------------------------------

def test_all_pass_case(tmp_path, capsys):
    dirs = _folders(tmp_path)
    for d in dirs:
        _write_folder(d, _passing_labels())
    code, out = _run(dirs, capsys)
    assert code == 0
    assert out.rstrip().endswith("A1 PASS")
    assert "A1-fixed: 10/10" in out and "A1-lost: 0/7" in out and "A1-quote: 0 violations" in out


def test_one_mark_fail_names_the_mark(tmp_path, capsys):
    labels = _passing_labels()
    labels["P2-R5"] = "supported"
    labels["P6-R1"] = "supported"
    dirs = _folders(tmp_path)
    for d in dirs:
        _write_folder(d, labels)
    code, out = _run(dirs, capsys)
    assert code == 0
    assert out.rstrip().endswith("A1 FAIL: A1-lost")


def test_quote_violation_in_extra_claim_fails_a1_quote(tmp_path, capsys):
    dirs = _folders(tmp_path)
    for i, d in enumerate(dirs):
        _write_folder(d, _passing_labels(), extra_claims=[_lowered_claim(1, scope_quote=None)] if i == 1 else None)
    code, out = _run(dirs, capsys)
    assert code == 0
    assert out.rstrip().endswith("A1 FAIL: A1-quote")
    assert "scope_2 extra#1: scope_lowered with null scope_quote" in out


def test_report_only_lowered_counts_and_label_source(tmp_path, capsys):
    dirs = _folders(tmp_path)
    for d in dirs:
        _write_folder(d, _passing_labels(),
                      claim_overrides={"P3-R2": {"auditor_label": "supported", "scope_lowered": True,
                                                 "scope_item": "x", "scope_quote": "q" * 30,
                                                 "scope_items": [{"text": "x", "contradicting_quote": "q" * 30,
                                                                  "guard_passed": True}]}})
    code, out = _run(dirs, capsys)
    assert code == 0
    assert "P3-R2: scope, scope, scope" in out
    assert "P4-R1: auditor, auditor, auditor" in out
    assert f"{dirs[0]}: 1" in out


def test_summary_counts_printed_and_missing_summary_is_not_invalid(tmp_path, capsys):
    dirs = _folders(tmp_path)
    for d in dirs:
        _write_folder(d, _passing_labels())
    block = {k: i for i, k in enumerate(score_a1.SUMMARY_COUNTS)}
    (dirs[0] / "_summary.json").write_text(json.dumps({"scope_check": block}), encoding="utf-8")
    (dirs[1] / "_summary.json").write_text(json.dumps({"other": 1}), encoding="utf-8")  # no scope_check block
    # dirs[2] has no _summary.json at all
    code, out = _run(dirs, capsys)
    assert code == 0 and "INVALID" not in out
    assert "lister_calls=0" in out and "verdicts_lowered=8" in out
    assert f"{dirs[1]}: summary missing" in out
    assert f"{dirs[2]}: summary missing" in out
    assert out.rstrip().endswith("A1 PASS")
