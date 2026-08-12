import json

import pytest
from pydantic import ValidationError

from eval.data_source import read_from_fixture


def _write_fixture(tmp_path, content: str):
    path = tmp_path / "fixture.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_fixture_with_three_claims_parses(tmp_path):
    path = _write_fixture(
        tmp_path,
        json.dumps(
            [
                {"index": 0, "label": "supported"},
                {"index": 1, "label": "not_supported"},
                {"index": 2, "label": "partially_supported"},
            ]
        ),
    )

    claims = read_from_fixture(path)

    assert len(claims) == 3
    assert claims[0].index == 0 and claims[0].label == "supported"
    assert claims[1].index == 1 and claims[1].label == "not_supported"
    assert claims[2].index == 2 and claims[2].label == "partially_supported"


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
