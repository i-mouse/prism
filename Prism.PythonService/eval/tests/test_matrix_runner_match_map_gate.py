"""Tests for the match-map gate: hash mismatch warning, coverage gate, and
the always-printed bucket counts (refused/wrongly_affirmed/not_extracted/
skipped/matcher_miss), independent of eval.matcher or the DB."""
import json

from eval import matrix_runner
from eval.matrix_runner import MatchMapGate, MatrixReport, _build_match_map_gate, _print_report
from eval.matrix_runner import PaperRunResult
from eval.types import EvalReport


def _minimal_report() -> EvalReport:
    return EvalReport(
        correct_refusals=1,
        total_negatives=1,
        refusal_rate=1.0,
        positive_hits=0,
        positive_total=0,
        per_row={},
        refused_by_label=1,
        refused_by_grounding=0,
        wrongly_affirmed=0,
        not_extracted=0,
        false_rejections=0,
        false_rejection_rate=0.0,
        positive_hit_floor=0,
        refusal_rate_valid=True,
    )


def _write_match_map(path, prompt_hash, rows: dict):
    path.write_text(
        json.dumps({"metadata": {"prompt_hash": prompt_hash, "fixture_file": None, "schema_version": 1}, "rows": rows}),
        encoding="utf-8",
    )


def test_gate_missing_match_map_is_zero_coverage(tmp_path):
    gate = _build_match_map_gate({"N1", "N2"}, tmp_path / "does_not_exist.json")

    assert gate.coverage_count == 0
    assert gate.matcher_miss == 2
    assert gate.coverage_ok is False
    assert gate.load_error is not None
    assert gate.hash_mismatch is False


def test_gate_full_coverage_matching_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix_runner, "get_prompt_version", lambda: "abc123")
    path = tmp_path / "match_map.json"
    _write_match_map(path, "abc123", {"N1": {"claim_fingerprint": "x"}, "N2": {"claim_fingerprint": "y"}})

    gate = _build_match_map_gate({"N1", "N2"}, path)

    assert gate.coverage_count == 2
    assert gate.matcher_miss == 0
    assert gate.coverage_ok is True
    assert gate.hash_mismatch is False
    assert gate.load_error is None


def test_gate_partial_coverage_not_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix_runner, "get_prompt_version", lambda: "abc123")
    path = tmp_path / "match_map.json"
    _write_match_map(path, "abc123", {"N1": {"claim_fingerprint": "x"}, "N2": {}})

    gate = _build_match_map_gate({"N1", "N2"}, path)

    assert gate.coverage_count == 1
    assert gate.matcher_miss == 1
    assert gate.coverage_ok is False


def test_gate_detects_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(matrix_runner, "get_prompt_version", lambda: "current-hash")
    path = tmp_path / "match_map.json"
    _write_match_map(path, "stale-hash", {"N1": {"claim_fingerprint": "x"}})

    gate = _build_match_map_gate({"N1"}, path)

    assert gate.hash_mismatch is True
    assert gate.match_map_prompt_hash == "stale-hash"
    assert gate.current_prompt_hash == "current-hash"


def _minimal_aggregate(**overrides) -> MatrixReport:
    base = dict(
        correct_refusals=5,
        total_negatives=14,
        refusal_rate=5 / 14,
        refused_by_label=5,
        refused_by_grounding=0,
        wrongly_affirmed=3,
        not_extracted=6,
        positive_hits=11,
        positive_total=23,
        false_rejections=0,
        false_rejection_rate=0.0,
        positive_hit_floor=10,
        refusal_rate_valid=True,
        scored_papers=3,
        strict_correct_refusals=3,
        strict_refusal_rate=3 / 14,
        skipped=0,
    )
    base.update(overrides)
    return MatrixReport(**base)


def test_print_report_suppresses_headline_when_coverage_incomplete(tmp_path, capsys):
    gate = MatchMapGate(
        total_rows=37,
        coverage_count=0,
        matcher_miss=37,
        coverage_ok=False,
        hash_mismatch=False,
        current_prompt_hash="abc123",
        match_map_prompt_hash=None,
        load_error=None,
    )
    result = PaperRunResult(paper_id="p", filename="p.pdf", status="SCORED", claims_count=1, reports=[_minimal_report()])

    _print_report([result], _minimal_aggregate(), gate, 0.70, tmp_path / "log.json", exit_code=1)

    out = capsys.readouterr().out
    assert "HEADLINE SUPPRESSED" in out
    assert "match map coverage 0/37" in out
    assert "matcher_miss:        37" in out
    assert "Refusal-family rate" not in out


def test_print_report_shows_headline_and_bucket_counts_when_coverage_complete(tmp_path, capsys):
    gate = MatchMapGate(
        total_rows=37,
        coverage_count=37,
        matcher_miss=0,
        coverage_ok=True,
        hash_mismatch=False,
        current_prompt_hash="abc123",
        match_map_prompt_hash="abc123",
        load_error=None,
    )
    result = PaperRunResult(paper_id="p", filename="p.pdf", status="SCORED", claims_count=1, reports=[_minimal_report()])

    _print_report([result], _minimal_aggregate(), gate, 0.70, tmp_path / "log.json", exit_code=1)

    out = capsys.readouterr().out
    assert "Refusal-family rate: 5/14" in out
    assert "HEADLINE SUPPRESSED" not in out
    assert "wrongly affirmed:    3" in out
    assert "not extracted:       6" in out
    assert "matcher_miss:        0" in out


def test_print_report_warns_on_hash_mismatch(tmp_path, capsys):
    gate = MatchMapGate(
        total_rows=37,
        coverage_count=37,
        matcher_miss=0,
        coverage_ok=True,
        hash_mismatch=True,
        current_prompt_hash="new-hash",
        match_map_prompt_hash="old-hash",
        load_error=None,
    )
    result = PaperRunResult(paper_id="p", filename="p.pdf", status="SCORED", claims_count=1, reports=[_minimal_report()])

    _print_report([result], _minimal_aggregate(), gate, 0.70, tmp_path / "log.json", exit_code=0)

    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "old-hash" in out
    assert "new-hash" in out
