"""Synthetic-fixture tests for eval/score_clean_bounds.py's K1 band logic.
No LLM calls, no network, no real K1/K6/K7 data (fake in-memory/tmp data
only).

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_score_clean_bounds.py -v
"""
import json
from pathlib import Path

from eval import score_clean_bounds as scb


# ---------------------------------------------------------------------------
# _k1_band: exact edges of the ratio/partial_ratio banding rule
# ---------------------------------------------------------------------------

def test_ratio_90_found_in_both_bounds():
    assert scb._k1_band(ratio=90, partial=0) == "both"


def test_ratio_89_found_only_in_high_bound():
    assert scb._k1_band(ratio=89, partial=0) == "high"


def test_partial_90_with_ratio_below_60_found_only_in_high_bound():
    assert scb._k1_band(ratio=59, partial=90) == "high"


def test_ratio_59_and_partial_below_90_not_found():
    assert scb._k1_band(ratio=59, partial=89) == "none"


def test_ratio_60_found_only_in_high_bound():
    assert scb._k1_band(ratio=60, partial=0) == "high"


def test_ratio_and_partial_both_zero_not_found():
    assert scb._k1_band(ratio=0, partial=0) == "none"


def test_ratio_100_found_in_both_bounds():
    assert scb._k1_band(ratio=100, partial=100) == "both"


# ---------------------------------------------------------------------------
# score_k1_bounds: end-to-end over fake run dirs, exercising _k1_band via
# real (deterministic) fuzz.ratio/partial_ratio on controlled claim text
# ---------------------------------------------------------------------------

def _write_run(run_dir: Path, paper_id: str, claim_texts: list[str]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    claims = [{"claim_text_verbatim": text, "pass": "pass1"} for text in claim_texts]
    (run_dir / f"{paper_id}_filtered.json").write_text(json.dumps({"claims": claims}), encoding="utf-8")
    (run_dir / f"{paper_id}_merged.json").write_text(json.dumps({"claims": claims}), encoding="utf-8")


def test_score_k1_bounds_exact_text_found_in_both_runs(tmp_path, monkeypatch):
    target_row = {
        "row_id": "P2-R3", "paper_id": "paperA",
        "claim_text_verbatim": "The model achieves 95 percent accuracy on the benchmark.",
    }
    monkeypatch.setattr(
        scb, "_k1_target_rows",
        lambda dev_eval_path, match_map_path, run1_fixture_dir: [target_row],
    )

    run1 = tmp_path / "clean_r1"
    run2 = tmp_path / "clean_r2"
    _write_run(run1, "paperA", [target_row["claim_text_verbatim"]])
    _write_run(run2, "paperA", [target_row["claim_text_verbatim"]])

    result = scb.score_k1_bounds({"clean_r1": run1, "clean_r2": run2}, Path("x"), Path("y"), Path("z"))
    assert result["target_total"] == 1
    assert result["per_run"]["clean_r1"]["found_low"] == ["P2-R3"]
    assert result["per_run"]["clean_r1"]["found_high"] == ["P2-R3"]
    assert result["per_run"]["clean_r2"]["found_low"] == ["P2-R3"]
    # P2-R3 is a K1_STABLE_ROWS member, found in both runs -> counts toward the 7-stable tally
    assert result["stable_both_runs_low"] == ["P2-R3"]
    assert result["pass_low"] is False  # only 1 of 7 stable rows found


def test_score_k1_bounds_unrelated_claims_not_found(tmp_path, monkeypatch):
    target_row = {
        "row_id": "P2-R3", "paper_id": "paperA",
        "claim_text_verbatim": "The model achieves 95 percent accuracy on the benchmark.",
    }
    monkeypatch.setattr(
        scb, "_k1_target_rows",
        lambda dev_eval_path, match_map_path, run1_fixture_dir: [target_row],
    )

    run1 = tmp_path / "clean_r1"
    _write_run(run1, "paperA", ["Completely unrelated sentence about photosynthesis in plants."])

    result = scb.score_k1_bounds({"clean_r1": run1}, Path("x"), Path("y"), Path("z"))
    assert result["per_run"]["clean_r1"]["found_low"] == []
    assert result["per_run"]["clean_r1"]["found_high"] == []
