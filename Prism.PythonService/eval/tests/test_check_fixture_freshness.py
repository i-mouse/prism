"""Offline tests for eval/check_fixture_freshness.py. No DB, no LLM."""
import json
from pathlib import Path

import pytest

from eval import check_fixture_freshness as cff

CURRENT_HASH = "currenthash1"


@pytest.fixture(autouse=True)
def _fixed_prompt_hash(monkeypatch):
    monkeypatch.setattr(cff, "get_prompt_version", lambda: CURRENT_HASH)


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


def _write_fixture(fixture_dir: Path, paper_id: str, prompt_hash: str | None) -> Path:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    path = fixture_dir / f"{paper_id}.json"
    claims = [{"index": 0, "label": "supported", "claim_summary": "x"}]

    if prompt_hash is None:
        content = claims  # legacy bare-array shape, no header
    else:
        content = {
            "header": {
                "prompt_hash": prompt_hash,
                "model_name": "gemini-3.6-flash",
                "generated_at": "2026-08-13T00:00:00+00:00",
                "paper_id": paper_id,
                "filename": f"{paper_id}.pdf",
                "extraction_run_id": "11111111-1111-1111-1111-111111111111",
            },
            "claims": claims,
        }

    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_all_fixtures_fresh_returns_zero(tmp_path):
    matrix_path = _write_matrix(tmp_path, ["paper-a", "paper-b"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", CURRENT_HASH)
    _write_fixture(fixture_dir, "paper-b", CURRENT_HASH)

    assert cff.check_freshness(matrix_path, fixture_dir) == 0


def test_stale_fixture_fails_with_clear_message(tmp_path, capsys):
    matrix_path = _write_matrix(tmp_path, ["paper-a"])
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a", "oldhashXYZ12")

    exit_code = cff.check_freshness(matrix_path, fixture_dir)
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "paper-a" in out
    assert "Regenerate via" in out
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
