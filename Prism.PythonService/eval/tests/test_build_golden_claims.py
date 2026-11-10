"""Unit tests for eval/build_golden_claims.py. Offline: an invented matrix and fixtures in tmp_path. A file of
another set (not valid JSON) sits in the fixture folder: reading it would fail, so a pass also shows the
builder only opens the matrix's papers."""
import json
import sys

import pytest

from eval import build_golden_claims as mod
from eval import build_stage_a_claims as stage_a_mod

PAPER_1 = "arxiv-1.0v1"
PAPER_2 = "arxiv-2.0v1"


def _matrix(path, rows_by_paper):
    path.write_text(json.dumps({
        "metadata": {"pass_threshold": {"refusal_rate": 0.7, "positive_hit_floor": 10}},
        "papers": [
            {
                "paper_id": pid, "filename": f"{pid}.pdf", "title": pid,
                "expected_matrix": [
                    {"id": rid, "expected_label": "supported", "grounding_negative": False} for rid in rows
                ],
            }
            for pid, rows in rows_by_paper.items()
        ],
    }), encoding="utf-8")


def _fixture(folder, paper_id, n_claims, matches):
    (folder / f"{paper_id}.json").write_text(json.dumps({
        "header": {"extraction_run_id": "run"},
        "claims": [{"index": i, "claim_text_verbatim": f"c{i}", "claim_summary": f"s{i}"} for i in range(n_claims)],
        "matches": [{"expected_id": e, "actual_index": a} for e, a in matches],
    }), encoding="utf-8")


@pytest.fixture
def golden(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    matrix = tmp_path / "matrix_eval.json"
    _matrix(matrix, {PAPER_1: ["A-1", "A-2", "A-3", "A-4"], PAPER_2: ["B-1", "B-2"]})
    _fixture(fixtures, PAPER_1, 6, [("A-1", 4), ("A-2", None), ("A-3", 0), ("A-4", 4)])   # A-1 and A-4 share claim 4
    _fixture(fixtures, PAPER_2, 3, [("B-1", 2), ("B-2", None)])
    (fixtures / "arxiv-8888.00009v1.json").write_text("{not json", encoding="utf-8")   # another set's file
    return matrix, fixtures


def test_every_matched_claim_is_listed_once_with_all_its_row_ids(golden):
    matrix, fixtures = golden
    entries, shared = mod.build(matrix, fixtures)
    assert entries == [
        {"row_ids": ["A-3"], "paper_id": PAPER_1, "claim_index": 0},
        {"row_ids": ["A-1", "A-4"], "paper_id": PAPER_1, "claim_index": 4},
        {"row_ids": ["B-1"], "paper_id": PAPER_2, "claim_index": 2},
    ]
    assert shared == [{"row_ids": ["A-1", "A-4"], "paper_id": PAPER_1, "claim_index": 4}]


def test_rows_without_a_claim_are_not_listed(golden):
    matrix, fixtures = golden
    entries, _ = mod.build(matrix, fixtures)
    listed = {row_id for entry in entries for row_id in entry["row_ids"]}
    assert "A-2" not in listed and "B-2" not in listed


def test_only_the_matrix_papers_are_opened(golden):
    matrix, fixtures = golden
    entries, _ = mod.build(matrix, fixtures)   # the foreign fixture is invalid JSON: opening it would raise
    assert {e["paper_id"] for e in entries} == {PAPER_1, PAPER_2}


def test_a_match_for_a_row_the_matrix_lacks_raises(golden):
    matrix, fixtures = golden
    _fixture(fixtures, PAPER_2, 3, [("B-1", 2), ("Z-9", 1)])
    with pytest.raises(ValueError, match="Z-9"):
        mod.build(matrix, fixtures)


def test_a_match_to_a_missing_claim_raises(golden):
    matrix, fixtures = golden
    _fixture(fixtures, PAPER_2, 3, [("B-1", 7)])
    with pytest.raises(ValueError, match="claim #7"):
        mod.build(matrix, fixtures)


@pytest.mark.parametrize("body", ["[]", json.dumps({"claims": []}), json.dumps({"matches": []})])
def test_a_legacy_fixture_raises(golden, body):
    matrix, fixtures = golden
    (fixtures / f"{PAPER_1}.json").write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="no claims and matches"):
        mod.build(matrix, fixtures)


# --- the CLI ----------------------------------------------------------------------------------

def _main(monkeypatch, matrix, fixtures, *extra):
    monkeypatch.setattr(sys, "argv", [
        "build_golden_claims", "--matrix-path", str(matrix), "--fixture-dir", str(fixtures), *extra,
    ])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    return exc.value.code


def test_cli_writes_the_index_and_prints_count_and_shared_claims(golden, tmp_path, monkeypatch, capsys):
    matrix, fixtures = golden
    out = tmp_path / "golden_claims.json"
    assert _main(monkeypatch, matrix, fixtures, "--output-path", str(out)) == 0
    entries, _ = mod.build(matrix, fixtures)
    assert json.loads(out.read_text(encoding="utf-8")) == entries
    text = capsys.readouterr().out
    assert "Golden claims: 3 claims for 4 matched rows (1 shared claims)" in text
    assert f"shared: {PAPER_1} claim #4: A-1, A-4" in text


def test_cli_requires_an_explicit_output_path(golden, monkeypatch, capsys):
    matrix, fixtures = golden
    assert _main(monkeypatch, matrix, fixtures) == 1
    assert "requires an explicit --output-path" in capsys.readouterr().out


def test_cli_refuses_an_existing_file_and_the_stage_a_file(golden, tmp_path, monkeypatch, capsys):
    matrix, fixtures = golden
    out = tmp_path / "exists.json"
    out.write_text("KEEP", encoding="utf-8")
    assert _main(monkeypatch, matrix, fixtures, "--output-path", str(out)) == 1
    assert "already exists" in capsys.readouterr().out and out.read_text(encoding="utf-8") == "KEEP"

    stage_a = tmp_path / "exp1_stage_a_claims.json"
    monkeypatch.setattr(stage_a_mod, "DEFAULT_OUTPUT_PATH", stage_a)
    assert _main(monkeypatch, matrix, fixtures, "--output-path", str(stage_a)) == 1
    assert "must not write the Stage A file" in capsys.readouterr().out and not stage_a.exists()


def test_cli_reports_a_bad_fixture_and_writes_nothing(golden, tmp_path, monkeypatch, capsys):
    matrix, fixtures = golden
    _fixture(fixtures, PAPER_2, 3, [("B-1", 7)])
    out = tmp_path / "golden_claims.json"
    assert _main(monkeypatch, matrix, fixtures, "--output-path", str(out)) == 1
    assert "ERROR" in capsys.readouterr().out and not out.exists()
