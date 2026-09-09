"""Offline tests for eval/verify_matcher_gold.py. No DB, no LLM.

The real matcher is monkeypatched with a fixed pass/fail pattern per gold
pair, so these tests exercise the pass-rate computation and fixture-header
writing without ever calling Gemini.
"""
import asyncio
import json
from pathlib import Path

from eval import verify_matcher_gold
from eval.types import Match


def _write_gold_set(tmp_path, pairs: list[dict]) -> Path:
    path = tmp_path / "matcher_gold.json"
    path.write_text(
        json.dumps({"metadata": {"pass_threshold": "13/15 (~87%)"}, "pairs": pairs}),
        encoding="utf-8",
    )
    return path


def _pair(id_: str, correct_match: bool) -> dict:
    return {
        "id": id_,
        "expected_claim_summary": f"expected {id_}",
        "actual_claim_summary": f"actual {id_}",
        "correct_match": correct_match,
    }


def _write_fixture(fixture_dir, paper_id: str) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture = {
        "header": {
            "prompt_hash": "abcdef012345",
            "matcher_fingerprint": "oldfp000001",
            "model_name": "gemini-3.6-flash",
            "matcher_model": "gemini-3.1-flash-lite",
            "generated_at": "2026-08-13T00:00:00+00:00",
            "paper_id": paper_id,
            "filename": f"{paper_id}.pdf",
            "extraction_run_id": "11111111-1111-1111-1111-111111111111",
        },
        "claims": [{"index": 0, "label": "supported", "claim_summary": "x"}],
        "matches": [{"expected_id": f"{paper_id}-1", "actual_index": 0}],
    }
    (fixture_dir / f"{paper_id}.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")


def _matching_match_factory(correct_ids: set[str]):
    """Builds a fake match() that returns actual_index=0 (a match) only for
    gold pairs whose id is in correct_ids and whose gold verdict is
    correct_match=True - i.e. it "agrees" with the gold set exactly for
    correct_ids and disagrees for everything else."""

    async def _fake_match(paper_id, expected_rows, actual_claims):
        row = expected_rows[0]
        agrees = row.id in correct_ids
        return [Match(expected_id=row.id, actual_index=0 if agrees else None)], "gemini-3.6-flash"

    return _fake_match


def test_all_pairs_correct_writes_pass_rate_one(tmp_path, monkeypatch):
    pairs = [_pair("MG01", True), _pair("MG02", True), _pair("MG03", False)]
    gold_path = _write_gold_set(tmp_path, pairs)
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a")

    # MG01/MG02 expect a match (correct_match=True) and get one; MG03
    # expects no match (correct_match=False) and gets none - all three agree.
    monkeypatch.setattr(verify_matcher_gold, "match", _matching_match_factory({"MG01", "MG02"}))
    monkeypatch.setattr(verify_matcher_gold, "get_matcher_fingerprint", lambda: "newfp000001")

    exit_code = asyncio.run(verify_matcher_gold._run(fixture_dir, gold_path))

    assert exit_code == 0
    written = json.loads((fixture_dir / "paper-a.json").read_text(encoding="utf-8"))
    assert written["header"]["matcher_gold_pass_rate"] == 1.0
    assert written["header"]["matcher_fingerprint"] == "newfp000001"
    assert "matcher_gold_verified_at" in written["header"]


def test_below_floor_does_not_write_headers(tmp_path, monkeypatch, capsys):
    # 15 pairs, matcher agrees on 0 of them that expect a match -> well below 0.9.
    pairs = [_pair(f"MG{i:02d}", True) for i in range(15)]
    gold_path = _write_gold_set(tmp_path, pairs)
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a")

    monkeypatch.setattr(verify_matcher_gold, "match", _matching_match_factory(set()))
    monkeypatch.setattr(verify_matcher_gold, "get_matcher_fingerprint", lambda: "newfp000001")

    exit_code = asyncio.run(verify_matcher_gold._run(fixture_dir, gold_path))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAILED" in captured.err
    unwritten = json.loads((fixture_dir / "paper-a.json").read_text(encoding="utf-8"))
    assert "matcher_gold_pass_rate" not in unwritten["header"]
    assert unwritten["header"]["matcher_fingerprint"] == "oldfp000001"


def test_writes_into_every_fixture_with_a_header(tmp_path, monkeypatch):
    pairs = [_pair("MG01", True)]
    gold_path = _write_gold_set(tmp_path, pairs)
    fixture_dir = tmp_path / "fixtures"
    _write_fixture(fixture_dir, "paper-a")
    _write_fixture(fixture_dir, "paper-b")
    # Legacy bare-array fixture must be skipped, not crash.
    (fixture_dir / "paper-c.json").write_text(
        json.dumps([{"index": 0, "label": "supported", "claim_summary": "x"}]), encoding="utf-8"
    )

    monkeypatch.setattr(verify_matcher_gold, "match", _matching_match_factory({"MG01"}))
    monkeypatch.setattr(verify_matcher_gold, "get_matcher_fingerprint", lambda: "newfp000001")

    exit_code = asyncio.run(verify_matcher_gold._run(fixture_dir, gold_path))

    assert exit_code == 0
    for paper_id in ("paper-a", "paper-b"):
        written = json.loads((fixture_dir / f"{paper_id}.json").read_text(encoding="utf-8"))
        assert written["header"]["matcher_gold_pass_rate"] == 1.0
    # paper-c (legacy) is untouched, not crashed on.
    legacy = json.loads((fixture_dir / "paper-c.json").read_text(encoding="utf-8"))
    assert isinstance(legacy, list)
