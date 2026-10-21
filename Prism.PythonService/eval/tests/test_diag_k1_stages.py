"""Synthetic-fixture tests for eval/diag_k1_stages.py. No LLM calls, no
network, no real K1 data, no `_key/` files (fake in-memory/tmp data only).

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_diag_k1_stages.py -v
"""
import json
from pathlib import Path

import pytest

from eval import diag_k1_stages as diag

ROW_TEXT = "The model achieves 95 percent accuracy on the benchmark dataset overall."
ROW = {"row_id": "P2-R3", "paper_id": "paperA", "claim_text_verbatim": ROW_TEXT}


def _write(run_dir: Path, paper_id: str, suffix: str, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{paper_id}_{suffix}.json").write_text(json.dumps(payload), encoding="utf-8")


def _header() -> dict:
    return {"paper_id": "paperA", "run_id": "r"}


# ---------------------------------------------------------------------------
# _k1_band edges (same edges already covered for score_clean_bounds._k1_band;
# this module duplicates that function and must agree on the same boundaries)
# ---------------------------------------------------------------------------

def test_ratio_90_found_in_both_bounds():
    assert diag._k1_band(ratio=90, partial=0) == "both"


def test_ratio_89_found_only_in_high_bound():
    assert diag._k1_band(ratio=89, partial=0) == "high"


def test_partial_90_with_ratio_below_60_found_only_in_high_bound():
    assert diag._k1_band(ratio=59, partial=90) == "high"


def test_ratio_59_and_partial_below_90_not_found():
    assert diag._k1_band(ratio=59, partial=89) == "none"


# ---------------------------------------------------------------------------
# C{i}/P{j} id-mapping rebuild
# ---------------------------------------------------------------------------

def test_split_pass1_pass2_assigns_p_ids_in_pass2_order():
    merged_claims = [
        {"claim_text_verbatim": "c0", "pass": "pass1"},
        {"claim_text_verbatim": "p0", "pass": "pass2"},
        {"claim_text_verbatim": "c1", "pass": "pass1"},
        {"claim_text_verbatim": "p1", "pass": "pass2"},
    ]
    ids = diag._split_pass1_pass2(merged_claims)
    assert ids[id(merged_claims[1])] == "P0"
    assert ids[id(merged_claims[3])] == "P1"
    assert id(merged_claims[0]) not in ids  # pass-1 claims get no candidate id
    assert id(merged_claims[2]) not in ids


def test_s2_items_attach_candidate_ids(tmp_path):
    run_dir = tmp_path / "run"
    merged = {
        "header": _header(),
        "claims": [
            {"claim_text_verbatim": "pass1 claim text", "pass": "pass1"},
            {"claim_text_verbatim": "pass2 claim text", "pass": "pass2"},
        ],
    }
    _write(run_dir, "paperA", "merged", merged)
    items = diag._s2_items(run_dir, ["paperA"])
    by_text = {item["text"]: item["candidate_id"] for item in items}
    assert by_text["pass1 claim text"] is None
    assert by_text["pass2 claim text"] == "P0"


# ---------------------------------------------------------------------------
# One fixture per loss type, via diagnose_row directly
# ---------------------------------------------------------------------------

def _empty_run(tmp_path: Path, paper_id: str = "paperA") -> Path:
    run_dir = tmp_path / "run"
    _write(run_dir, paper_id, "pass1", {"header": _header(), "claims": []})
    _write(run_dir, paper_id, "pass2", {"header": _header(), "sentences": []})
    _write(run_dir, paper_id, "merged", {"header": _header(), "claims": []})
    _write(run_dir, paper_id, "buckets", {"header": _header(), "dropped_ungrounded": 0, "dropped_duplicate": []})
    _write(run_dir, paper_id, "filtered", {"header": _header(), "claims": []})
    _write(run_dir, paper_id, "clean", {"header": _header(), "decisions": {}})
    return run_dir


def test_loss_type_prompt_miss(tmp_path):
    run_dir = _empty_run(tmp_path)  # S1 (pass2 sentences) stays empty -> never generated
    result = diag.diagnose_row(run_dir, ROW, [], [], [], [])
    assert result["loss_stage_low"] == "pass-2 prompt miss"
    assert result["loss_stage_high"] == "pass-2 prompt miss"
    assert result["loss_detail_low"] is None


def test_loss_type_merge_drop_duplicate(tmp_path):
    run_dir = _empty_run(tmp_path)
    _write(run_dir, "paperA", "buckets", {
        "header": _header(), "dropped_ungrounded": 0,
        "dropped_duplicate": [{"sentence": ROW_TEXT, "best_match": ROW_TEXT, "ratio_score": 100.0, "partial_ratio_score": 100.0}],
    })
    s1 = [{"paper_id": "paperA", "text": ROW_TEXT}]  # present at S1
    s2 = []  # absent at S2 -> merge drop
    result = diag.diagnose_row(run_dir, ROW, [], s1, s2, [])
    assert result["loss_stage_low"] == "merge drop"
    assert "dropped_duplicate" in result["loss_detail_low"]["bucket"]


def test_loss_type_merge_drop_ungrounded_inferred(tmp_path):
    run_dir = _empty_run(tmp_path)  # buckets.dropped_duplicate stays empty
    s1 = [{"paper_id": "paperA", "text": ROW_TEXT}]
    s2 = []
    result = diag.diagnose_row(run_dir, ROW, [], s1, s2, [])
    assert result["loss_stage_low"] == "merge drop"
    assert "dropped_ungrounded" in result["loss_detail_low"]["bucket"]
    assert "inferred" in result["loss_detail_low"]["bucket"]


def test_loss_type_filter_drop(tmp_path):
    run_dir = _empty_run(tmp_path)
    _write(run_dir, "paperA", "clean", {
        "header": _header(),
        "decisions": {
            "P0": {"decision": "dropped", "reason_code": "same_relation_only",
                   "relations": [{"neighbour_id": "C3", "relation": "same"},
                                 {"neighbour_id": "P1", "relation": "same"}],
                   "is_paper_claim": False},
            "P1": {"decision": "kept", "reason_code": "contribution", "relations": [], "is_paper_claim": True},
        },
    })
    s1 = [{"paper_id": "paperA", "text": ROW_TEXT}]
    s2 = [{"paper_id": "paperA", "text": ROW_TEXT, "candidate_id": "P0"}]  # present at S2
    s3 = []  # absent at S3 -> filter drop
    result = diag.diagnose_row(run_dir, ROW, [], s1, s2, s3)
    assert result["loss_stage_low"] == "filter drop"
    detail = result["loss_detail_low"]
    assert detail["candidate_id"] == "P0"
    assert detail["decision"] == "dropped"
    assert detail["reason_code"] == "same_relation_only"
    assert detail["is_paper_claim"] is False
    neighbours = {n["neighbour_id"]: n["status"] for n in detail["same_neighbours"]}
    assert neighbours["C3"] == "kept (pass-1, always retained)"  # C-neighbour: always kept
    assert neighbours["P1"] == "kept"  # P-neighbour: looked up in decisions


def test_loss_type_found(tmp_path):
    run_dir = _empty_run(tmp_path)
    item = {"paper_id": "paperA", "text": ROW_TEXT}
    result = diag.diagnose_row(run_dir, ROW, [], [item], [item], [item])
    assert result["loss_stage_low"] == "found"
    assert result["loss_stage_high"] == "found"


# ---------------------------------------------------------------------------
# cross-paper flag
# ---------------------------------------------------------------------------

def test_cross_paper_flag_set_when_match_is_in_a_different_paper(tmp_path):
    run_dir = _empty_run(tmp_path)
    item_other_paper = {"paper_id": "paperB", "text": ROW_TEXT}
    result = diag.diagnose_row(run_dir, ROW, [], [item_other_paper], [item_other_paper], [item_other_paper])
    assert result["stages"]["s1"]["cross_paper"] is True
    assert result["stages"]["s1"]["paper_id"] == "paperB"


def test_cross_paper_flag_not_set_for_same_paper(tmp_path):
    run_dir = _empty_run(tmp_path)
    item_same_paper = {"paper_id": "paperA", "text": ROW_TEXT}
    result = diag.diagnose_row(run_dir, ROW, [], [item_same_paper], [item_same_paper], [item_same_paper])
    assert result["stages"]["s1"]["cross_paper"] is False


# ---------------------------------------------------------------------------
# Hard stop: S3 recomputation must match EXPECTED_S3_COUNTS, else no report
# ---------------------------------------------------------------------------

def test_hard_stop_fires_on_mismatch_and_writes_no_report(tmp_path, monkeypatch):
    run_dir = _empty_run(tmp_path)  # no claims anywhere -> S3 found count = 0, not 5
    monkeypatch.setattr(
        diag, "_k1_target_rows",
        lambda dev_eval_path, match_map_path, run1_fixture_dir: [ROW],
    )
    output_path = tmp_path / "report.md"
    monkeypatch.setattr("sys.argv", [
        "diag_k1_stages", "--run", f"clean_r1:{run_dir}", "--output-path", str(output_path),
    ])
    with pytest.raises(SystemExit):
        diag.main()
    assert not output_path.exists()


def test_no_hard_stop_for_run_name_not_in_expected_counts(tmp_path, monkeypatch):
    run_dir = _empty_run(tmp_path)  # same "empty" data, but run name isn't checked
    monkeypatch.setattr(
        diag, "_k1_target_rows",
        lambda dev_eval_path, match_map_path, run1_fixture_dir: [ROW],
    )
    output_path = tmp_path / "report.md"
    monkeypatch.setattr("sys.argv", [
        "diag_k1_stages", "--run", f"unrelated_run:{run_dir}", "--output-path", str(output_path),
    ])
    diag.main()
    assert output_path.exists()


# ---------------------------------------------------------------------------
# --no-filter mode: S3 == S2, never reads _filtered.json/_clean.json, and
# default (no_filter=False) stays byte-identical to existing behavior.
# ---------------------------------------------------------------------------

def test_no_filter_makes_s3_equal_s2_without_filtered_or_clean_files(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    _write(run_dir, "paperA", "pass1", {"header": _header(), "claims": []})
    _write(run_dir, "paperA", "pass2", {"header": _header(), "sentences": [ROW_TEXT]})
    _write(run_dir, "paperA", "merged", {"header": _header(), "claims": [
        {"claim_text_verbatim": ROW_TEXT, "pass": "pass2"},
    ]})
    _write(run_dir, "paperA", "buckets", {"header": _header(), "dropped_ungrounded": 0, "dropped_duplicate": []})
    # Deliberately NOT writing _filtered.json or _clean.json - they must never be read.
    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: [ROW])

    result = diag.run_diagnostic({"exp3_r1": run_dir}, Path("x"), Path("y"), Path("z"), no_filter=True)
    row = result["per_run"]["exp3_r1"]["rows"][0]
    assert row["loss_stage_low"] == "found"  # S3 (== S2) finds it, even with no filter files
    assert row["loss_stage_high"] == "found"
    assert (run_dir / "paperA_filtered.json").exists() is False
    assert (run_dir / "paperA_clean.json").exists() is False


def test_no_filter_default_false_matches_previous_behavior(tmp_path, monkeypatch):
    run_dir = _empty_run(tmp_path)
    item = {"paper_id": "paperA", "text": ROW_TEXT}
    monkeypatch.setattr(diag, "_s0_items", lambda *a, **k: [])
    monkeypatch.setattr(diag, "_s1_items", lambda *a, **k: [item])
    monkeypatch.setattr(diag, "_s2_items", lambda *a, **k: [item])
    monkeypatch.setattr(diag, "_s3_items", lambda *a, **k: [item])
    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: [ROW])

    default_result = diag.run_diagnostic({"r": run_dir}, Path("x"), Path("y"), Path("z"))
    explicit_false_result = diag.run_diagnostic({"r": run_dir}, Path("x"), Path("y"), Path("z"), no_filter=False)
    assert default_result == explicit_false_result


def test_main_no_filter_flag_threads_through(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    _write(run_dir, "paperA", "pass1", {"header": _header(), "claims": []})
    _write(run_dir, "paperA", "pass2", {"header": _header(), "sentences": [ROW_TEXT]})
    _write(run_dir, "paperA", "merged", {"header": _header(), "claims": [
        {"claim_text_verbatim": ROW_TEXT, "pass": "pass2"},
    ]})
    _write(run_dir, "paperA", "buckets", {"header": _header(), "dropped_ungrounded": 0, "dropped_duplicate": []})
    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: [ROW])
    output_path = tmp_path / "report.md"

    monkeypatch.setattr("sys.argv", [
        "diag_k1_stages", "--run", f"exp3_r1:{run_dir}", "--no-filter", "--output-path", str(output_path),
    ])
    diag.main()
    assert output_path.exists()
    assert "found" in output_path.read_text(encoding="utf-8")
