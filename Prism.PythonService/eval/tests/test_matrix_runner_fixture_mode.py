"""Offline tests: matrix_runner's fixture mode never touches the matcher.

Fixture mode reads claims + frozen matches straight off disk, so it must
never call eval.matcher.match (and therefore never import google.genai).
matcher.match is monkeypatched to raise if invoked - if fixture mode ever
regresses to calling it, these tests fail loudly instead of quietly
burning a Gemini call.
"""
import asyncio
import json
from pathlib import Path

from eval import matrix_runner
from eval.matrix_loader import PaperSpec
from eval.types import ExpectedRow


def _raise_if_called(*args, **kwargs):
    raise AssertionError("matcher.match should never be called in fixture mode")


def _write_fixture(fixture_dir: Path, paper_id: str, claims: list[dict], matches: list[dict] | None) -> Path:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    path = fixture_dir / f"{paper_id}.json"
    content: dict = {
        "header": {
            "prompt_hash": "abcdef012345",
            "model_name": "gemini-3.6-flash",
            "matcher_model": "gemini-3.1-flash-lite",
            "generated_at": "2026-08-13T00:00:00+00:00",
            "paper_id": paper_id,
            "filename": f"{paper_id}.pdf",
            "extraction_run_id": "11111111-1111-1111-1111-111111111111",
        },
        "claims": claims,
    }
    if matches is not None:
        content["matches"] = matches
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def _paper() -> PaperSpec:
    return PaperSpec(
        paper_id="paper-a",
        filename="paper-a.pdf",
        title="Paper A",
        expected_rows=[
            ExpectedRow(id="E1", expected_label="supported", grounding_negative=False, claim_summary="x"),
            ExpectedRow(id="E2", expected_label="not_supported", grounding_negative=True, claim_summary="y"),
        ],
    )


def test_fixture_mode_uses_frozen_matches_no_gemini_call(tmp_path, monkeypatch):
    import eval.matcher as matcher_module

    monkeypatch.setattr(matcher_module, "match", _raise_if_called)

    fixture_dir = tmp_path / "fixtures"
    claims = [{"index": 0, "label": "supported", "claim_summary": "x"}]
    matches = [
        {"expected_id": "E1", "actual_index": 0},
        {"expected_id": "E2", "actual_index": None},
    ]
    _write_fixture(fixture_dir, "paper-a", claims, matches)

    result = asyncio.run(matrix_runner._run_paper(_paper(), "fixture", fixture_dir, 1, 15))

    assert result.status == "SCORED"
    assert result.claims_count == 1
    assert len(result.reports) == 1


def test_fixture_mode_legacy_fixture_marks_paper_skipped(tmp_path, monkeypatch):
    import eval.matcher as matcher_module

    monkeypatch.setattr(matcher_module, "match", _raise_if_called)

    fixture_dir = tmp_path / "fixtures"
    claims = [{"index": 0, "label": "supported", "claim_summary": "x"}]
    _write_fixture(fixture_dir, "paper-a", claims, matches=None)  # no "matches" key -> legacy

    result = asyncio.run(matrix_runner._run_paper(_paper(), "fixture", fixture_dir, 1, 15))

    assert result.status == "SKIPPED"
    assert "matches" in result.reason
    assert "dump_fixture" in result.reason
