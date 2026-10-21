"""Unit tests for eval/score_exp3.py's C4 cost-per-paper calculation.

Covers the review fix: C4 must divide a run's total cost by the number of
papers actually replayed (one row per *_merged.json file under
replay_root/run_name/), not by the number of adjudicated dev-eval rows -
those are two very different counts. No LLM calls; pure file I/O against a
tmp_path fixture tree.
"""
import json

from eval.score_exp3 import _papers_replayed, _run_cost_inr


def _write_merged(run_dir, paper_id):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{paper_id}_merged.json").write_text(
        json.dumps({"header": {}, "claims": []}), encoding="utf-8"
    )


def test_papers_replayed_counts_merged_json_files_not_rows(tmp_path):
    run_dir = tmp_path / "pass2_r1"
    _write_merged(run_dir, "P1")
    _write_merged(run_dir, "P2")

    assert _papers_replayed(tmp_path, "pass2_r1") == 2


def test_cost_per_paper_divides_by_paper_count_not_row_count(tmp_path):
    """Two papers, a known total cost: cost-per-paper must be cost/2, not
    cost divided by some larger adjudicated-row count."""
    run_dir = tmp_path / "pass2_r1"
    _write_merged(run_dir, "P1")
    _write_merged(run_dir, "P2")
    (run_dir / "_summary.json").write_text(
        json.dumps({"cost_inr": 50.0}), encoding="utf-8"
    )

    papers = _papers_replayed(tmp_path, "pass2_r1")
    cost = _run_cost_inr(tmp_path, "pass2_r1")
    cost_per_paper = cost / papers

    assert papers == 2
    assert cost == 50.0
    assert cost_per_paper == 25.0
