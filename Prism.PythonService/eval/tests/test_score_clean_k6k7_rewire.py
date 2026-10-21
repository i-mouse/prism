"""Tests for eval/score_clean.py's K6/K7 gate re-wiring to
eval/score_label_pack.py output (docs/decisions.md, "Clean-extraction
attempt: K6/K7 labelling method, caching dropped, K4 path - 2026-10-19").
No LLM calls, no network, synthetic fixtures only.

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_score_clean_k6k7_rewire.py -v
"""
import json
from pathlib import Path

import pytest

from eval import score_clean


def _write_k6_score(tmp_path: Path, name: str, n: int, a: int, unsure: int, not_found: int = 0) -> Path:
    path = tmp_path / name
    counts = {"A": a, "B": 0, "C": 0, "D": n - a - unsure, "unsure": unsure}
    path.write_text(json.dumps({
        "mode": "k6", "n": n, "counts": counts, "not_found_count": not_found,
        "precision_unsure_not_claim": a / n, "precision_unsure_claim": (a + unsure) / n,
        "pass": (a / n) >= 0.70,
    }), encoding="utf-8")
    return path


def _write_k7_score(tmp_path: Path, name: str, n: int, same: int) -> Path:
    path = tmp_path / name
    counts = {"same": same, "broader": 0, "narrower": 0, "different": n - same, "unsure": 0}
    path.write_text(json.dumps({
        "mode": "k7", "n": n, "counts": counts, "not_same_count": n - same, "pass": (n - same) <= 1,
    }), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# score_k6 / score_k7: reads <mode>_score.json, PASS/FAIL carries through
# ---------------------------------------------------------------------------

def test_score_k6_reads_score_json_and_uses_unsure_as_not_claim_precision(tmp_path):
    score_path = _write_k6_score(tmp_path, "k6_score.json", n=30, a=21, unsure=5)
    result = score_clean.score_k6({"run1": score_path})
    assert result["run1"]["n"] == 30
    assert result["run1"]["counts"]["A"] == 21
    assert result["run1"]["precision_unsure_not_claim"] == pytest.approx(21 / 30)
    assert result["run1"]["pass"] is True


def test_score_k6_fails_below_precision_gate(tmp_path):
    score_path = _write_k6_score(tmp_path, "k6_score.json", n=30, a=20, unsure=5)
    result = score_clean.score_k6({"run1": score_path})
    assert result["run1"]["precision_unsure_not_claim"] == pytest.approx(20 / 30)
    assert result["run1"]["pass"] is False


def test_score_k7_reads_score_json_and_passes_at_one_not_same(tmp_path):
    score_path = _write_k7_score(tmp_path, "k7_score.json", n=30, same=29)
    result = score_clean.score_k7({"run1": score_path})
    assert result["run1"]["not_same"] == 1
    assert result["run1"]["pass"] is True


def test_score_k7_fails_above_one_not_same(tmp_path):
    score_path = _write_k7_score(tmp_path, "k7_score.json", n=30, same=28)
    result = score_clean.score_k7({"run1": score_path})
    assert result["run1"]["not_same"] == 2
    assert result["run1"]["pass"] is False


def test_score_k6_multiple_runs_keyed_by_name(tmp_path):
    (tmp_path / "r1").mkdir()
    (tmp_path / "r2").mkdir()
    p1 = _write_k6_score(tmp_path / "r1", "k6_score.json", n=30, a=25, unsure=0)
    p2 = _write_k6_score(tmp_path / "r2", "k6_score.json", n=30, a=10, unsure=0)
    result = score_clean.score_k6({"r1": p1, "r2": p2})
    assert result["r1"]["pass"] is True
    assert result["r2"]["pass"] is False


# ---------------------------------------------------------------------------
# CLI: --k6k7-run is removed and gives a clear error
# ---------------------------------------------------------------------------

def test_main_rejects_old_k6k7_run_flag_with_clear_error(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["score_clean", "--run", "dummy:does-not-matter", "--k6k7-run", "r1:does-not-matter"],
    )
    with pytest.raises(SystemExit):
        score_clean.main()
    captured = capsys.readouterr()
    assert "--k6-score" in captured.err
    assert "--k7-score" in captured.err


def test_parse_named_paths_handles_new_k6_k7_score_flags():
    parsed = score_clean._parse_named_paths(["r1:k6.json", "r2:k6_other.json"])
    assert parsed == {"r1": Path("k6.json"), "r2": Path("k6_other.json")}
