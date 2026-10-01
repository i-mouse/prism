import json

import pytest

from eval.match_map import fingerprint_claim_text
from eval.suggest_match_map import SCORE_FLOOR, suggest


def _write_matrix(path, papers: list[dict]) -> None:
    path.write_text(json.dumps({"metadata": {}, "papers": papers}), encoding="utf-8")


def _paper(paper_id: str, filename: str, rows: list[dict]) -> dict:
    return {
        "paper_id": paper_id,
        "filename": filename,
        "title": paper_id,
        "expected_matrix": rows,
    }


def _row(row_id: str, claim_text_verbatim: str, expected_label="not_supported", grounding_negative=True) -> dict:
    return {
        "id": row_id,
        "expected_label": expected_label,
        "grounding_negative": grounding_negative,
        "claim_text_verbatim": claim_text_verbatim,
    }


def _write_fixture(path, claims: list[dict]) -> None:
    path.write_text(json.dumps({"header": {}, "claims": claims}), encoding="utf-8")


def _write_match_map_skeleton(path, ids: list[str]) -> None:
    rows = {row_id: {"persisted_claim_id": None, "claim_fingerprint": None, "decided_by": None, "decided_on": None, "reason": None} for row_id in ids}
    path.write_text(json.dumps({"metadata": {"prompt_hash": "abc", "fixture_file": None, "schema_version": 1}, "rows": rows}), encoding="utf-8")


def test_suggest_fills_suggested_field_only(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    match_map_path = tmp_path / "match_map.json"

    _write_matrix(
        matrix_path,
        [_paper("paper-a", "paper-a.pdf", [_row("N1", "Reflexion achieves 91% pass at 1 on HumanEval")])],
    )
    _write_fixture(
        fixture_dir / "paper-a.json",
        [{"index": 0, "label": "supported", "claim_text_verbatim": "Reflexion achieves 91% pass@1 on HumanEval"}],
    )
    _write_match_map_skeleton(match_map_path, ["N1"])

    summary = suggest(matrix_path, fixture_dir, match_map_path)

    assert summary[0]["id"] == "N1"
    assert summary[0]["score"] > SCORE_FLOOR

    written = json.loads(match_map_path.read_text(encoding="utf-8"))
    row = written["rows"]["N1"]
    # Hard constraint: only `suggested` is written, every adjudication field
    # stays exactly as the skeleton had it.
    assert row["persisted_claim_id"] is None
    assert row["claim_fingerprint"] is None
    assert row["decided_by"] is None
    assert row["decided_on"] is None
    assert row["reason"] is None
    assert row["suggested"]["claim_fingerprint"] == fingerprint_claim_text("Reflexion achieves 91% pass@1 on HumanEval")
    assert row["suggested"]["score"] > SCORE_FLOOR
    assert "Reflexion achieves" in row["suggested"]["claim_text_snippet"]


def test_suggest_leaves_suggested_null_below_score_floor(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    match_map_path = tmp_path / "match_map.json"

    _write_matrix(matrix_path, [_paper("paper-a", "paper-a.pdf", [_row("N1", "Completely unrelated golden claim text")])])
    _write_fixture(fixture_dir / "paper-a.json", [{"index": 0, "label": "supported", "claim_text_verbatim": "zzz qqq xyz totally different"}])
    _write_match_map_skeleton(match_map_path, ["N1"])

    summary = suggest(matrix_path, fixture_dir, match_map_path)

    assert summary[0]["score"] is None
    written = json.loads(match_map_path.read_text(encoding="utf-8"))
    assert written["rows"]["N1"]["suggested"] is None


def test_suggest_never_matches_across_papers(tmp_path):
    """A near-identical claim living in a DIFFERENT paper's fixture must
    never be suggested - matching is scoped per paper."""
    matrix_path = tmp_path / "matrix_eval.json"
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    match_map_path = tmp_path / "match_map.json"

    shared_text = "Reflexion achieves 91% pass at 1 on HumanEval benchmark results"
    _write_matrix(
        matrix_path,
        [
            _paper("paper-a", "paper-a.pdf", [_row("A1", shared_text)]),
            _paper("paper-b", "paper-b.pdf", [_row("B1", shared_text)]),
        ],
    )
    # The exact matching text only exists in paper-b's fixture, not paper-a's.
    _write_fixture(fixture_dir / "paper-a.json", [{"index": 0, "label": "supported", "claim_text_verbatim": "nothing like it at all"}])
    _write_fixture(fixture_dir / "paper-b.json", [{"index": 0, "label": "supported", "claim_text_verbatim": shared_text}])
    _write_match_map_skeleton(match_map_path, ["A1", "B1"])

    summary = suggest(matrix_path, fixture_dir, match_map_path)

    by_id = {row["id"]: row for row in summary}
    assert by_id["A1"]["score"] is None  # must not borrow paper-b's matching claim
    assert by_id["B1"]["score"] is not None


def test_suggest_raises_if_match_map_missing_golden_row(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    match_map_path = tmp_path / "match_map.json"

    _write_matrix(matrix_path, [_paper("paper-a", "paper-a.pdf", [_row("N1", "some claim")])])
    _write_fixture(fixture_dir / "paper-a.json", [{"index": 0, "label": "supported", "claim_text_verbatim": "some claim"}])
    _write_match_map_skeleton(match_map_path, [])  # skeleton missing N1 entirely

    with pytest.raises(ValueError, match="no row for golden id"):
        suggest(matrix_path, fixture_dir, match_map_path)


def test_suggest_handles_missing_fixture_gracefully(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    match_map_path = tmp_path / "match_map.json"

    _write_matrix(matrix_path, [_paper("paper-a", "paper-a.pdf", [_row("N1", "some claim")])])
    # No fixture file written for paper-a at all.
    _write_match_map_skeleton(match_map_path, ["N1"])

    summary = suggest(matrix_path, fixture_dir, match_map_path)

    assert summary[0]["score"] is None
    written = json.loads(match_map_path.read_text(encoding="utf-8"))
    assert written["rows"]["N1"]["suggested"] is None
