"""Offline tests for eval/dump_fixture.py. No DB, no LLM."""
import asyncio
import json

from eval import dump_fixture
from eval.data_source import get_fixture_header, read_from_fixture
from eval.matrix_loader import PaperSpec
from eval.types import ActualClaim, ExpectedRow, Match


def _write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _locked_shape_fixture() -> dict:
    return {
        "header": {
            "prompt_hash": "abcdef012345",
            "model_name": "gemini-2.5-flash",
            "generated_at": "2026-08-13T00:00:00+00:00",
            "paper_id": "arxiv-2303.11366v4",
            "filename": "reflexion.pdf",
            "extraction_run_id": "11111111-1111-1111-1111-111111111111",
        },
        "claims": [
            {"index": 0, "label": "supported", "claim_summary": "Claim zero."},
            {"index": 1, "label": "not_supported", "claim_summary": "Claim one."},
        ],
    }


def test_fixture_shape_round_trips(tmp_path):
    fixture = _locked_shape_fixture()
    path = _write(tmp_path, "fixture.json", json.dumps(fixture))

    claims = read_from_fixture(path)

    assert claims == [ActualClaim.model_validate(item) for item in fixture["claims"]]


def test_legacy_bare_array_still_parses(tmp_path):
    legacy = [
        {"index": 0, "label": "supported", "claim_summary": "Claim zero."},
        {"index": 1, "label": "partially_supported", "claim_summary": "Claim one."},
    ]
    path = _write(tmp_path, "fixture.json", json.dumps(legacy))

    claims = read_from_fixture(path)

    assert claims == [ActualClaim.model_validate(item) for item in legacy]


def test_get_fixture_header_returns_dict_on_new_shape(tmp_path):
    fixture = _locked_shape_fixture()
    path = _write(tmp_path, "fixture.json", json.dumps(fixture))

    assert get_fixture_header(path) == fixture["header"]


def test_get_fixture_header_returns_none_on_legacy_shape(tmp_path):
    legacy = [{"index": 0, "label": "supported", "claim_summary": "Claim zero."}]
    path = _write(tmp_path, "fixture.json", json.dumps(legacy))

    assert get_fixture_header(path) is None


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


async def _fake_fetch_latest_extraction(filename: str):
    return (
        "11111111-1111-1111-1111-111111111111",
        [{"index": 0, "label": "supported", "claim_summary": "Synthetic claim."}],
    )


async def _fake_match(paper_id, expected_rows, actual_claims):
    return [
        Match(expected_id=row.id, actual_index=0 if i == 0 else None)
        for i, row in enumerate(expected_rows)
    ]


async def _raising_match(paper_id, expected_rows, actual_claims):
    raise RuntimeError("simulated matcher failure")


def test_dump_fixture_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(dump_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(dump_fixture, "match", _fake_match)

    dumped = asyncio.run(
        dump_fixture._dump_paper(_fake_paper(), tmp_path, True, "abcdef012345", "gemini-2.5-flash", "gemini-2.5-flash-lite")
    )

    assert dumped is True
    assert list(tmp_path.iterdir()) == []


def test_dump_fixture_writes_file_when_not_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(dump_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(dump_fixture, "match", _fake_match)

    dumped = asyncio.run(
        dump_fixture._dump_paper(_fake_paper(), tmp_path, False, "abcdef012345", "gemini-2.5-flash", "gemini-2.5-flash-lite")
    )

    assert dumped is True
    fixture_path = tmp_path / "arxiv-2303.11366v4.json"
    written = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert written["header"]["paper_id"] == "arxiv-2303.11366v4"
    assert written["header"]["prompt_hash"] == "abcdef012345"
    assert written["header"]["matcher_model"] == "gemini-2.5-flash-lite"
    assert written["claims"] == [{"index": 0, "label": "supported", "claim_summary": "Synthetic claim."}]
    assert written["matches"] == [
        {"expected_id": "REFLEX-M01", "actual_index": 0},
        {"expected_id": "REFLEX-M02", "actual_index": None},
    ]


def test_dump_fixture_writes_matches_when_not_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(dump_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(dump_fixture, "match", _fake_match)

    paper = _fake_paper()
    dumped = asyncio.run(
        dump_fixture._dump_paper(paper, tmp_path, False, "abcdef012345", "gemini-2.5-flash", "gemini-2.5-flash-lite")
    )

    assert dumped is True
    written = json.loads((tmp_path / "arxiv-2303.11366v4.json").read_text(encoding="utf-8"))

    assert "matches" in written
    assert len(written["matches"]) == len(paper.expected_rows)
    assert written["matches"][0] == {"expected_id": "REFLEX-M01", "actual_index": 0}
    assert written["matches"][1] == {"expected_id": "REFLEX-M02", "actual_index": None}


def test_dump_fixture_matcher_failure_skips_and_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dump_fixture, "_fetch_latest_extraction", _fake_fetch_latest_extraction)
    monkeypatch.setattr(dump_fixture, "match", _raising_match)

    dumped = asyncio.run(
        dump_fixture._dump_paper(_fake_paper(), tmp_path, False, "abcdef012345", "gemini-2.5-flash", "gemini-2.5-flash-lite")
    )

    assert dumped is False
    assert list(tmp_path.iterdir()) == []
    assert "matcher failed" in capsys.readouterr().out
