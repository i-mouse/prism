"""Unit tests for resolve_adjudicated_rows' row_type guard in eval/score_replay.py.

Filling the dev match map's S (supported) rows must not change what existing
callers see: the default returns refusal (R) rows only.
"""
import json

import pytest

from eval.match_map import fingerprint_claim_text
from eval.score_replay import resolve_adjudicated_rows

_R_TEXT = "refusal claim text"
_S_TEXT = "supported claim text"


def _write_inputs(tmp_path):
    matrix = {
        "metadata": {},
        "papers": [{
            "paper_id": "paperA", "filename": "a.pdf", "title": "A",
            "expected_matrix": [
                {"id": "P1-R1", "expected_label": "partially_supported", "grounding_negative": True},
                {"id": "P1-R2", "expected_label": "not_supported", "grounding_negative": True},
                {"id": "P1-S1", "expected_label": "supported", "grounding_negative": False},
                {"id": "P1-S2", "expected_label": "supported", "grounding_negative": False},
            ],
        }],
    }
    blank = {
        "persisted_claim_id": None, "claim_fingerprint": None, "decided_by": None, "decided_on": None,
        "reason": None, "confirmed_no_match": False, "suggested": None,
    }
    rows = {
        "P1-R1": {**blank, "claim_fingerprint": fingerprint_claim_text(_R_TEXT), "decided_by": "t"},
        "P1-R2": {**blank, "confirmed_no_match": True, "decided_by": "t"},
        "P1-S1": {**blank, "claim_fingerprint": fingerprint_claim_text(_S_TEXT), "decided_by": "t"},
        "P1-S2": {**blank, "confirmed_no_match": True, "decided_by": "t"},
    }
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / "paperA.json").write_text(json.dumps({"claims": [
        {"index": 0, "claim_text_verbatim": _R_TEXT},
        {"index": 1, "claim_text_verbatim": _S_TEXT},
    ]}), encoding="utf-8")
    matrix_path = tmp_path / "dev_eval.json"
    map_path = tmp_path / "dev_match_map.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    map_path.write_text(json.dumps({"metadata": {}, "rows": rows}), encoding="utf-8")
    return matrix_path, map_path, fixture_dir


def test_default_returns_only_refusal_rows_when_s_rows_are_filled(tmp_path):
    rows = resolve_adjudicated_rows(*_write_inputs(tmp_path))

    assert {r.row_id for r in rows} == {"P1-R1", "P1-R2"}


def test_row_type_s_returns_only_s_rows(tmp_path):
    rows = resolve_adjudicated_rows(*_write_inputs(tmp_path), row_type="S")

    assert {r.row_id: r.claim_index for r in rows} == {"P1-S1": 1, "P1-S2": None}


def test_invalid_row_type_raises(tmp_path):
    with pytest.raises(ValueError, match="row_type"):
        resolve_adjudicated_rows(*_write_inputs(tmp_path), row_type="X")
