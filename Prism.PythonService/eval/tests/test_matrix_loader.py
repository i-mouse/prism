import json
from pathlib import Path

import pytest

from eval.matrix_loader import load_matrix

REAL_MATRIX_PATH = Path(__file__).parent.parent.parent.parent / "docs" / "evals" / "matrix_eval.json"


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "matrix.json"
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_matrix(**paper_overrides) -> dict:
    paper = {
        "paper_id": "arxiv-0000.00000v1",
        "filename": "synthetic.pdf",
        "title": "Synthetic Paper",
        "expected_matrix": [
            {
                "id": "SYN-M01",
                "claim_summary": "A synthetic claim summary.",
                "expected_label": "supported",
                "grounding_negative": False,
            },
            {
                "id": "SYN-M02",
                "claim_summary": "A synthetic negative claim summary.",
                "expected_label": "not_supported",
                "grounding_negative": True,
            },
        ],
    }
    paper.update(paper_overrides)
    return {"metadata": {"name": "Synthetic"}, "papers": [paper]}


def test_loads_real_matrix_eval():
    spec = load_matrix(REAL_MATRIX_PATH)

    assert len(spec.papers) == 3
    assert spec.pass_threshold_refusal_rate == 0.80
    assert spec.pass_threshold_positive_floor == 10


def test_missing_pass_threshold_uses_defaults(tmp_path):
    path = _write(tmp_path, json.dumps(_minimal_matrix()))

    spec = load_matrix(path)

    assert spec.pass_threshold_refusal_rate == 0.80
    assert spec.pass_threshold_positive_floor == 10


def test_malformed_json_raises(tmp_path):
    path = _write(tmp_path, "{not valid json")

    with pytest.raises(ValueError) as exc_info:
        load_matrix(path)

    assert str(path) in str(exc_info.value)


def test_missing_filename_field_raises(tmp_path):
    matrix = _minimal_matrix()
    del matrix["papers"][0]["filename"]
    path = _write(tmp_path, json.dumps(matrix))

    with pytest.raises(ValueError):
        load_matrix(path)


def test_expected_rows_populated(tmp_path):
    path = _write(tmp_path, json.dumps(_minimal_matrix()))

    spec = load_matrix(path)

    assert len(spec.papers) == 1
    rows = spec.papers[0].expected_rows
    assert len(rows) == 2
    assert rows[0].id == "SYN-M01"
    assert rows[0].claim_summary == "A synthetic claim summary."
    assert rows[1].id == "SYN-M02"
    assert rows[1].claim_summary == "A synthetic negative claim summary."
