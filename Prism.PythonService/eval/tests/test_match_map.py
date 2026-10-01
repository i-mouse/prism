import json

import pytest

from eval.match_map import fingerprint_claim_text, load_match_map, normalize_claim_text


def _write(path, metadata, rows):
    path.write_text(json.dumps({"metadata": metadata, "rows": rows}), encoding="utf-8")


def test_normalize_claim_text_lowercases_collapses_and_strips():
    assert normalize_claim_text("  Reflexion   Achieves\n91%  ") == "reflexion achieves 91%"


def test_fingerprint_is_stable_across_incidental_whitespace_differences():
    a = fingerprint_claim_text("Reflexion achieves 91% pass@1")
    b = fingerprint_claim_text("  reflexion   achieves\n91% pass@1  ")

    assert a == b


def test_fingerprint_differs_for_different_text():
    a = fingerprint_claim_text("claim one")
    b = fingerprint_claim_text("claim two")

    assert a != b


def test_load_match_map_valid(tmp_path):
    path = tmp_path / "match_map.json"
    _write(
        path,
        {"prompt_hash": "abc123", "fixture_file": None, "schema_version": 1},
        {"N1": {"persisted_claim_id": None, "claim_fingerprint": None, "decided_by": None, "decided_on": None, "reason": None}},
    )

    match_map = load_match_map(path, golden_ids={"N1"})

    assert match_map.metadata.prompt_hash == "abc123"
    assert match_map.rows["N1"].is_adjudicated is False
    assert match_map.coverage_count == 0


def test_load_match_map_rejects_missing_ids(tmp_path):
    path = tmp_path / "match_map.json"
    _write(path, {"schema_version": 1}, {"N1": {}})

    with pytest.raises(ValueError, match="missing golden row ids"):
        load_match_map(path, golden_ids={"N1", "N2"})


def test_load_match_map_rejects_unknown_ids(tmp_path):
    path = tmp_path / "match_map.json"
    _write(path, {"schema_version": 1}, {"N1": {}, "N999": {}})

    with pytest.raises(ValueError, match="unknown row ids"):
        load_match_map(path, golden_ids={"N1"})


def test_coverage_count_counts_fingerprint_or_persisted_id_either_way(tmp_path):
    path = tmp_path / "match_map.json"
    _write(
        path,
        {"schema_version": 1},
        {
            "N1": {"claim_fingerprint": "abc"},
            "N2": {"persisted_claim_id": "11111111-1111-1111-1111-111111111111"},
            "N3": {},
        },
    )

    match_map = load_match_map(path, golden_ids={"N1", "N2", "N3"})

    assert match_map.coverage_count == 2


def test_confirmed_no_match_counts_as_adjudicated(tmp_path):
    path = tmp_path / "match_map.json"
    _write(path, {"schema_version": 1}, {"N1": {"confirmed_no_match": True}, "N2": {}})

    match_map = load_match_map(path, golden_ids={"N1", "N2"})

    assert match_map.rows["N1"].is_adjudicated is True
    assert match_map.rows["N2"].is_adjudicated is False
    assert match_map.coverage_count == 1


def test_confirmed_no_match_defaults_false(tmp_path):
    path = tmp_path / "match_map.json"
    _write(path, {"schema_version": 1}, {"N1": {}})

    match_map = load_match_map(path, golden_ids={"N1"})

    assert match_map.rows["N1"].confirmed_no_match is False


def test_decided_by_alone_does_not_count_as_adjudicated(tmp_path):
    path = tmp_path / "match_map.json"
    _write(
        path,
        {"schema_version": 1},
        {"N1": {"decided_by": "nitin", "decided_on": "2026-10-01", "reason": "x"}},
    )

    match_map = load_match_map(path, golden_ids={"N1"})

    assert match_map.rows["N1"].is_adjudicated is False
    assert match_map.coverage_count == 0
