"""Offline tests for eval/rematch_fixture.py. No DB, no LLM."""
import asyncio
import json

from eval import rematch_fixture
from eval.matrix_loader import PaperSpec
from eval.types import ExpectedRow, Match


def _fake_paper() -> PaperSpec:
    return PaperSpec(
        paper_id="arxiv-2303.11366v4",
        filename="reflexion.pdf",
        title="Reflexion",
        expected_rows=[
            ExpectedRow(id="REFLEX-M01", expected_label="supported", grounding_negative=False, claim_summary="x"),
            ExpectedRow(id="REFLEX-M02", expected_label="not_supported", grounding_negative=True, claim_summary="y"),
        ],
    )


def _write_existing_fixture(tmp_path) -> None:
    fixture = {
        "header": {
            "prompt_hash": "abcdef012345",
            "matcher_fingerprint": "oldfp000001",
            "model_name": "gemini-3.6-flash",
            "matcher_model": "gemini-3.1-flash-lite",
            "matcher_gold_pass_rate": 0.9333333333333333,
            "matcher_gold_verified_at": "2026-09-01T00:00:00+00:00",
            "generated_at": "2026-08-13T00:00:00+00:00",
            "paper_id": "arxiv-2303.11366v4",
            "filename": "reflexion.pdf",
            "extraction_run_id": "11111111-1111-1111-1111-111111111111",
        },
        "claims": [{"index": 0, "label": "supported", "claim_summary": "Synthetic claim."}],
        "matches": [{"expected_id": "REFLEX-M01", "actual_index": None}],
    }
    (tmp_path / "arxiv-2303.11366v4.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")


async def _fake_fetch_latest_extraction(filename: str):
    return (
        "11111111-1111-1111-1111-111111111111",
        [{"index": 0, "label": "supported", "claim_summary": "Synthetic claim."}],
    )


async def _fake_match(paper_id, expected_rows, actual_claims):
    return (
        [
            Match(expected_id=row.id, actual_index=0 if i == 0 else None)
            for i, row in enumerate(expected_rows)
        ],
        "gemini-4.0-flash",
    )


async def _raising_match(paper_id, expected_rows, actual_claims):
    raise RuntimeError("simulated matcher failure")


def test_rematch_updates_matches_and_fingerprint(tmp_path, monkeypatch):
    _write_existing_fixture(tmp_path)
    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(rematch_fixture, "match", _fake_match)
    monkeypatch.setattr(rematch_fixture, "get_matcher_fingerprint", lambda: "newfp000001")

    ok = asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    assert ok is True
    written = json.loads((tmp_path / "arxiv-2303.11366v4.json").read_text(encoding="utf-8"))
    assert written["header"]["matcher_fingerprint"] == "newfp000001"
    assert written["header"]["matcher_model"] == "gemini-4.0-flash"
    assert written["matches"] == [
        {"expected_id": "REFLEX-M01", "actual_index": 0},
        {"expected_id": "REFLEX-M02", "actual_index": None},
    ]


def test_rematch_clears_pass_rate_fields(tmp_path, monkeypatch):
    """The exact invariant this script protects: a re-match under a new
    matcher must not leave a pass_rate measured under the old one in place."""
    _write_existing_fixture(tmp_path)
    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(rematch_fixture, "match", _fake_match)
    monkeypatch.setattr(rematch_fixture, "get_matcher_fingerprint", lambda: "newfp000001")

    asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    written = json.loads((tmp_path / "arxiv-2303.11366v4.json").read_text(encoding="utf-8"))
    assert "matcher_gold_pass_rate" not in written["header"]
    assert "matcher_gold_verified_at" not in written["header"]


def test_rematch_leaves_prompt_hash_and_claims_untouched(tmp_path, monkeypatch):
    _write_existing_fixture(tmp_path)
    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(rematch_fixture, "match", _fake_match)
    monkeypatch.setattr(rematch_fixture, "get_matcher_fingerprint", lambda: "newfp000001")

    asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    written = json.loads((tmp_path / "arxiv-2303.11366v4.json").read_text(encoding="utf-8"))
    assert written["header"]["prompt_hash"] == "abcdef012345"
    assert written["header"]["extraction_run_id"] == "11111111-1111-1111-1111-111111111111"
    assert written["header"]["model_name"] == "gemini-3.6-flash"
    assert written["claims"] == [{"index": 0, "label": "supported", "claim_summary": "Synthetic claim."}]


def test_rematch_missing_fixture_skips(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(rematch_fixture, "match", _fake_match)

    ok = asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    assert ok is False
    assert "no existing fixture" in capsys.readouterr().out


def test_rematch_legacy_fixture_no_header_skips(tmp_path, monkeypatch, capsys):
    (tmp_path / "arxiv-2303.11366v4.json").write_text(
        json.dumps([{"index": 0, "label": "supported", "claim_summary": "x"}]), encoding="utf-8"
    )
    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(rematch_fixture, "match", _fake_match)

    ok = asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    assert ok is False
    assert "legacy fixture" in capsys.readouterr().out


def test_rematch_no_db_data_skips(tmp_path, monkeypatch, capsys):
    _write_existing_fixture(tmp_path)

    async def _no_data(filename):
        return None

    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _no_data)
    monkeypatch.setattr(rematch_fixture, "match", _fake_match)

    ok = asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    assert ok is False
    assert "no DB data" in capsys.readouterr().out


def test_rematch_matcher_failure_skips(tmp_path, monkeypatch, capsys):
    _write_existing_fixture(tmp_path)
    monkeypatch.setattr(rematch_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(rematch_fixture, "match", _raising_match)

    ok = asyncio.run(rematch_fixture._rematch_paper(_fake_paper(), tmp_path))

    assert ok is False
    assert "matcher failed" in capsys.readouterr().out

    # The fixture must be left exactly as it was - a failed re-match is not
    # a partial write.
    written = json.loads((tmp_path / "arxiv-2303.11366v4.json").read_text(encoding="utf-8"))
    assert written["header"]["matcher_fingerprint"] == "oldfp000001"
