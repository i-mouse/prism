"""Synthetic-fixture tests for eval/compare_k1_prompt.py. No LLM calls, no
network, no real K1 data, no `_key/` files (fake in-memory/tmp data only).

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_compare_k1_prompt.py -v
"""
import json
from pathlib import Path

import pytest

from eval import compare_k1_prompt as cmp_mod
from eval import diag_k1_stages as diag


def _write(run_dir: Path, paper_id: str, suffix: str, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{paper_id}_{suffix}.json").write_text(json.dumps(payload), encoding="utf-8")


def _header(model_name: str = "gemini-3.6-flash") -> dict:
    return {"paper_id": "paperA", "run_id": "r", "model_name": model_name}


def _make_run(tmp_path: Path, name: str, sentences: list[str], model_name: str = "gemini-3.6-flash") -> Path:
    run_dir = tmp_path / name
    _write(run_dir, "paperA", "pass1", {"header": _header(model_name), "claims": []})
    _write(run_dir, "paperA", "pass2", {"header": _header(model_name), "sentences": sentences})
    merged_claims = [{"claim_text_verbatim": s, "pass": "pass2"} for s in sentences]
    _write(run_dir, "paperA", "merged", {"header": _header(model_name), "claims": merged_claims})
    _write(run_dir, "paperA", "buckets", {"header": _header(model_name), "dropped_ungrounded": 0, "dropped_duplicate": []})
    _write(run_dir, "paperA", "_summary", {"calls": 1})  # no-op, _summary.json written separately below
    (run_dir / "_summary.json").write_text(json.dumps({"calls": 1}), encoding="utf-8")
    return run_dir


ROW_A = {"row_id": "P2-R3", "paper_id": "paperA", "claim_text_verbatim": "Row A text about the experiment outcome overall."}
ROW_B = {"row_id": "P7-R2", "paper_id": "paperA", "claim_text_verbatim": "Row B text about a totally different finding here."}


# ---------------------------------------------------------------------------
# compare(): old found-not-new / new found-not-old row diff, with shape
# ---------------------------------------------------------------------------

def test_compare_finds_old_not_new_and_new_not_old_with_shape(tmp_path, monkeypatch):
    # old side generates ROW_A (verbatim) but not ROW_B; new side generates ROW_B but not ROW_A
    old_dir = _make_run(tmp_path, "old_r1", [ROW_A["claim_text_verbatim"]])
    new_dir = _make_run(tmp_path, "new_r1", [ROW_B["claim_text_verbatim"]])

    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: [ROW_A, ROW_B])
    monkeypatch.setattr(diag, "EXPECTED_S3_COUNTS", {})  # skip regression hard-stop for this synthetic run name

    result = cmp_mod.compare({"old_r1": old_dir}, {"new_r1": new_dir}, Path("x"), Path("y"), Path("z"))
    pairing = result["per_pairing"][0]
    low = pairing["bounds"]["low"]
    old_not_new_ids = {r["row_id"] for r in low["old_not_new"]}
    new_not_old_ids = {r["row_id"] for r in low["new_not_old"]}
    assert old_not_new_ids == {"P2-R3"}
    assert new_not_old_ids == {"P7-R2"}
    # shapes attached from ROW_ID_TO_SHAPE
    shapes = {r["row_id"]: r["shape"] for r in low["old_not_new"]}
    assert shapes["P2-R3"] == "E2"


# ---------------------------------------------------------------------------
# Interpretation rule: old_S1 >= new_S1 + 2 in BOTH pairings
# ---------------------------------------------------------------------------

def test_rule_triggers_when_old_s1_at_least_two_higher_in_both_pairings(tmp_path, monkeypatch):
    rows = [ROW_A, ROW_B]
    # old finds both rows (S1=2), new finds none (S1=0) -> delta=2 in each pairing
    old_r1 = _make_run(tmp_path, "old_r1", [ROW_A["claim_text_verbatim"], ROW_B["claim_text_verbatim"]])
    old_r2 = _make_run(tmp_path, "old_r2", [ROW_A["claim_text_verbatim"], ROW_B["claim_text_verbatim"]])
    new_r1 = _make_run(tmp_path, "new_r1", ["unrelated sentence one here for padding text."])
    new_r2 = _make_run(tmp_path, "new_r2", ["unrelated sentence two here for padding text."])

    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: rows)
    monkeypatch.setattr(diag, "EXPECTED_S3_COUNTS", {})

    result = cmp_mod.compare(
        {"old_r1": old_r1, "old_r2": old_r2}, {"new_r1": new_r1, "new_r2": new_r2}, Path("x"), Path("y"), Path("z"),
    )
    assert result["rule_outcome"]["low"]["triggers"] is True


def test_rule_does_not_trigger_when_delta_below_two_in_one_pairing(tmp_path, monkeypatch):
    rows = [ROW_A, ROW_B]
    old_r1 = _make_run(tmp_path, "old_r1", [ROW_A["claim_text_verbatim"], ROW_B["claim_text_verbatim"]])
    old_r2 = _make_run(tmp_path, "old_r2", [ROW_A["claim_text_verbatim"], ROW_B["claim_text_verbatim"]])
    new_r1 = _make_run(tmp_path, "new_r1", ["unrelated sentence one here for padding text."])
    # new_r2 finds both rows too -> delta=0 for this pairing, rule must not trigger
    new_r2 = _make_run(tmp_path, "new_r2", [ROW_A["claim_text_verbatim"], ROW_B["claim_text_verbatim"]])

    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: rows)
    monkeypatch.setattr(diag, "EXPECTED_S3_COUNTS", {})

    result = cmp_mod.compare(
        {"old_r1": old_r1, "old_r2": old_r2}, {"new_r1": new_r1, "new_r2": new_r2}, Path("x"), Path("y"), Path("z"),
    )
    assert result["rule_outcome"]["low"]["triggers"] is False


# ---------------------------------------------------------------------------
# Regression hard-stop on the "new" side
# ---------------------------------------------------------------------------

def test_regression_hard_stop_fires_when_new_side_mismatches(tmp_path, monkeypatch):
    old_dir = _make_run(tmp_path, "old_r1", [ROW_A["claim_text_verbatim"]])
    new_dir = _make_run(tmp_path, "clean_r1", [])  # finds nothing -> S3 count 0, not the expected 5

    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: [ROW_A])
    # Leave EXPECTED_S3_COUNTS at its real default (keyed by "clean_r1") so the mismatch fires.

    result = cmp_mod.compare({"old_r1": old_dir}, {"clean_r1": new_dir}, Path("x"), Path("y"), Path("z"))
    assert "hard_stop_mismatches" in result
    assert result["hard_stop_mismatches"]


def test_main_hard_stop_writes_no_report(tmp_path, monkeypatch):
    old_dir = _make_run(tmp_path, "old_r1", [ROW_A["claim_text_verbatim"]])
    new_dir = _make_run(tmp_path, "clean_r1", [])
    monkeypatch.setattr(diag, "_k1_target_rows", lambda *a, **k: [ROW_A])
    output_path = tmp_path / "report.md"

    monkeypatch.setattr("sys.argv", [
        "compare_k1_prompt",
        "--old-run", f"old_r1:{old_dir}", "--new-run", f"clean_r1:{new_dir}",
        "--output-path", str(output_path),
    ])
    with pytest.raises(SystemExit):
        cmp_mod.main()
    assert not output_path.exists()


# ---------------------------------------------------------------------------
# Mismatched --old-run/--new-run counts refused
# ---------------------------------------------------------------------------

def test_main_refuses_mismatched_run_counts(tmp_path, monkeypatch):
    old_dir = _make_run(tmp_path, "old_r1", [])
    output_path = tmp_path / "report.md"
    monkeypatch.setattr("sys.argv", [
        "compare_k1_prompt",
        "--old-run", f"old_r1:{old_dir}", "--old-run", f"old_r2:{old_dir}",
        "--new-run", f"new_r1:{old_dir}",
        "--output-path", str(output_path),
    ])
    with pytest.raises(SystemExit, match="must match"):
        cmp_mod.main()
