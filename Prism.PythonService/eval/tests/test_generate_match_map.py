import json

from eval.generate_match_map import generate


def _write_matrix(path, ids):
    path.write_text(
        json.dumps(
            {
                "metadata": {},
                "papers": [
                    {
                        "paper_id": "paper-a",
                        "filename": "paper-a.pdf",
                        "title": "Paper A",
                        "expected_matrix": [
                            {"id": row_id, "expected_label": "not_supported", "grounding_negative": True}
                            for row_id in ids
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_generate_writes_all_null_skeleton_for_every_golden_id(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    match_map_path = tmp_path / "match_map.json"
    _write_matrix(matrix_path, ["N1", "N2", "N3"])

    exit_code = generate(matrix_path, match_map_path, fixture_file=None)

    assert exit_code == 0
    written = json.loads(match_map_path.read_text(encoding="utf-8"))
    assert set(written["rows"].keys()) == {"N1", "N2", "N3"}
    for row in written["rows"].values():
        assert row["confirmed_no_match"] is False
        assert all(v is None for k, v in row.items() if k != "confirmed_no_match")
    assert written["metadata"]["schema_version"] == 1


def test_generate_refuses_to_overwrite_adjudicated_map(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    match_map_path = tmp_path / "match_map.json"
    _write_matrix(matrix_path, ["N1", "N2"])

    assert generate(matrix_path, match_map_path, fixture_file=None) == 0

    written = json.loads(match_map_path.read_text(encoding="utf-8"))
    written["rows"]["N1"]["claim_fingerprint"] = "deadbeef"
    match_map_path.write_text(json.dumps(written), encoding="utf-8")

    exit_code = generate(matrix_path, match_map_path, fixture_file=None)

    assert exit_code == 1
    # Untouched - the adjudicated row survives the refused regeneration.
    reread = json.loads(match_map_path.read_text(encoding="utf-8"))
    assert reread["rows"]["N1"]["claim_fingerprint"] == "deadbeef"


def test_generate_allows_overwrite_when_existing_map_is_all_null(tmp_path):
    matrix_path = tmp_path / "matrix_eval.json"
    match_map_path = tmp_path / "match_map.json"
    _write_matrix(matrix_path, ["N1"])

    assert generate(matrix_path, match_map_path, fixture_file=None) == 0
    assert generate(matrix_path, match_map_path, fixture_file=None) == 0
