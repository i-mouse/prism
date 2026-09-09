"""Offline tests for eval/check_fixture_freshness.py. No LLM calls, no DB queries."""
import json
from pathlib import Path

import pytest

from eval import check_fixture_freshness as cff

CURRENT_HASH = "currenthash1"
CURRENT_MATCHER_FINGERPRINT = "matcherfp01"
CURRENT_PASS_RATE = 0.9333333333333333  # 14/15, above the 0.9 floor


@pytest.fixture(autouse=True)
def _fixed_fingerprints(monkeypatch):
    monkeypatch.setattr(cff, "get_prompt_version", lambda: CURRENT_HASH)
    monkeypatch.setattr(cff, "get_matcher_fingerprint", lambda: CURRENT_MATCHER_FINGERPRINT)


def _write_matrix(tmp_path: Path, paper_ids: list[str]) -> Path:
    matrix = {
        "metadata": {"pass_threshold": {"refusal_rate": 0.8, "positive_hit_floor": 15}},
        "papers": [
            {
                "paper_id": paper_id,
                "filename": f"{paper_id}.pdf",
                "title": paper_id,
                "expected_matrix": [
                    {
                        "id": f"{paper_id}-1",
                        "claim_summary": "x",
                        "expected_label": "supported",
                        "grounding_negative": False,
                    }
                ],
            }
            for paper_id in paper_ids
        ],
    }
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    return path


def _write_fixture(
    fixture_dir: Path,
    paper_id: str,
    prompt_hash: str | None,
    include_matches: bool = True,
    matcher_fingerprint: str | None = CURRENT_MATCHER_FINGERPRINT,
    omit_matcher_fingerprint_key: bool = False,
    matcher_gold_pass_rate: float | None = CURRENT_PASS_RATE,
    omit_pass_rate_key: bool = False,
) -> Path:
    """matcher_fingerprint and matcher_gold_pass_rate default to fresh,
    passing values. Pass a different fingerprint or a low/omitted pass_rate
    to simulate the corresponding drift; omit_matcher_fingerprint_key
    simulates a fixture written before that field existed."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    path = fixture_dir / f"{paper_id}.json"
    claims = [{"index": 0, "label": "supported", "claim_summary": "x"}]

    if prompt_hash is None:
        content = claims  # legacy bare-array shape, no header
    else:
        header = {
            "prompt_hash": prompt_hash,
            "model_name": "gemini-3.6-flash",
            "matcher_model": "gemini-3.1-flash-lite",
            "generated_at": "2026-08-13T00:00:00+00:00",
            "paper_id": paper_id,
            "filename": f"{paper_id}.pdf",
            "extraction_run_id": "11111111-1111-1111-1111-111111111111",
        }
        if not omit_matcher_fingerprint_key:
            header["matcher_fingerprint"] = matcher_fingerprint
        if not omit_pass_rate_key:
            header["matcher_gold_pass_rate"] = matcher_gold_pass_rate
            header["matcher_gold_verified_at"] = "2026-09-09T00:00:00+00:00"
        content = {"header": header, "claims": claims}
        if include_matches:
            content["matches"] = [{"expected_id": f"{paper_id}-1", "actual_index": 0}]

    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_all_fixtures_fresh_returns_zero(tmp_path):
    matrix_path = _write_matrix(tmp_path, ["paper-a", "paper-b"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH)
    _write_fixture(fixture_dir, "paper-b", CURRENT_HASH)

    assert cff.check_freshness(matrix_path, fixture_dir) == 0


def test_stale_prompt_hash_fails_with_full_regen_message(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", "oldhashXYZ12")

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "extraction changed" in out
    assert "eval.dump_fixture --paper paper-a" in out


def test_missing_fixture_fails(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert str(fixture_dir / "paper-a.json") in out


def test_legacy_fixture_without_header_fails(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", None)

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "legacy fixture" in out
    assert "paper-a" in out
    assert "Regenerate via" in out


def test_all_papers_reported_when_multiple_fail(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a", "paper-b", "paper-c"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", "oldhashXYZ12")
    _write_fixture(fixture_dir, "paper-b", "oldhashXYZ12")
    # paper-c has no fixture file at all

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "paper-b" in out
    assert "paper-c" in out


def test_stale_matcher_fingerprint_fails_with_rematch_message(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH, matcher_fingerprint="stalefp0001")

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "matcher_fingerprint" in out
    assert "matcher changed" in out
    assert "re-match only" in out
    assert "eval.rematch_fixture --paper paper-a" in out
    assert "eval.verify_matcher_gold" in out


def test_fixture_missing_matcher_fingerprint_key_fails(tmp_path, capsys):
    """A fixture written before this field existed must be treated as stale,
    not crash or silently pass."""
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH, omit_matcher_fingerprint_key=True)

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "matcher_fingerprint" in out
    assert "re-match only" in out
    assert "eval.rematch_fixture --paper paper-a" in out


def test_pass_rate_missing_fails_with_verify_message(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH, omit_pass_rate_key=True)

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "matcher_gold_pass_rate=missing" in out
    assert "matcher gold check failed or never ran" in out
    assert "eval.verify_matcher_gold" in out


def test_pass_rate_below_floor_fails(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH, matcher_gold_pass_rate=0.8)

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "matcher_gold_pass_rate=80.0%" in out
    assert "matcher gold check failed or never ran" in out
    assert "eval.verify_matcher_gold" in out


def test_pass_rate_exactly_at_floor_passes(tmp_path):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH, matcher_gold_pass_rate=0.9)

    assert cff.check_freshness(matrix_path, fixture_dir) == 0


def test_fixture_missing_matches_key_fails(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH, include_matches=False)

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "missing frozen matches" in out
    assert "Regenerate via" in out
