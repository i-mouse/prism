import json

import pytest
from pydantic import ValidationError

from eval.data_source import read_from_fixture, read_matches_from_fixture


def _write_fixture(tmp_path, content: str):
    path = tmp_path / "fixture.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_fixture_with_three_claims_parses(tmp_path):
    path = _write_fixture(
        tmp_path,
        json.dumps(
            [
                {"index": 0, "label": "supported", "claim_summary": "Claim zero."},
                {"index": 1, "label": "not_supported", "claim_summary": "Claim one."},
                {"index": 2, "label": "partially_supported", "claim_summary": "Claim two."},
            ]
        ),
    )

    claims = read_from_fixture(path)

    assert len(claims) == 3
    assert claims[0].index == 0 and claims[0].label == "supported"
    assert claims[0].claim_summary == "Claim zero."
    assert claims[1].index == 1 and claims[1].label == "not_supported"
    assert claims[1].claim_summary == "Claim one."
    assert claims[2].index == 2 and claims[2].label == "partially_supported"
    assert claims[2].claim_summary == "Claim two."


def test_fixture_with_header_shape_parses(tmp_path):
    path = _write_fixture(
        tmp_path,
        json.dumps(
            {
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
        ),
    )

    claims = read_from_fixture(path)

    assert len(claims) == 2
    assert claims[0].index == 0 and claims[0].label == "supported"
    assert claims[1].index == 1 and claims[1].label == "not_supported"


def test_empty_fixture_parses_to_empty_list(tmp_path):
    path = _write_fixture(tmp_path, "[]")

    claims = read_from_fixture(path)

    assert claims == []


def test_missing_file_raises_file_not_found_error(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    with pytest.raises(FileNotFoundError):
        read_from_fixture(missing_path)


def test_invalid_json_raises_json_decode_error(tmp_path):
    path = _write_fixture(tmp_path, "{not valid json")

    with pytest.raises(json.JSONDecodeError):
        read_from_fixture(path)


def test_missing_required_field_raises_validation_error(tmp_path):
    path = _write_fixture(tmp_path, json.dumps([{"index": 0}]))

    with pytest.raises(ValidationError):
        read_from_fixture(path)


def test_read_matches_from_fixture_new_shape(tmp_path):
    path = _write_fixture(
        tmp_path,
        json.dumps(
            {
                "header": {
                    "prompt_hash": "abcdef012345",
                    "model_name": "gemini-3.6-flash",
                    "matcher_model": "gemini-3.1-flash-lite",
                    "generated_at": "2026-08-13T00:00:00+00:00",
                    "paper_id": "arxiv-2303.11366v4",
                    "filename": "reflexion.pdf",
                    "extraction_run_id": "11111111-1111-1111-1111-111111111111",
                },
                "claims": [{"index": 0, "label": "supported", "claim_summary": "Claim zero."}],
                "matches": [
                    {"expected_id": "M1", "actual_index": 0},
                    {"expected_id": "M2", "actual_index": None},
                ],
            }
        ),
    )

    matches = read_matches_from_fixture(path)

    assert len(matches) == 2
    assert matches[0].expected_id == "M1" and matches[0].actual_index == 0
    assert matches[1].expected_id == "M2" and matches[1].actual_index is None


def test_read_matches_from_fixture_legacy_shape_returns_empty(tmp_path):
    path = _write_fixture(
        tmp_path,
        json.dumps([{"index": 0, "label": "supported", "claim_summary": "Claim zero."}]),
    )

    assert read_matches_from_fixture(path) == []


def test_read_matches_from_fixture_missing_matches_key_returns_empty(tmp_path):
    path = _write_fixture(
        tmp_path,
        json.dumps(
            {
                "header": {
                    "prompt_hash": "abcdef012345",
                    "model_name": "gemini-3.6-flash",
                    "generated_at": "2026-08-13T00:00:00+00:00",
                    "paper_id": "arxiv-2303.11366v4",
                    "filename": "reflexion.pdf",
                    "extraction_run_id": "11111111-1111-1111-1111-111111111111",
                },
                "claims": [{"index": 0, "label": "supported", "claim_summary": "Claim zero."}],
            }
        ),
    )

    assert read_matches_from_fixture(path) == []
