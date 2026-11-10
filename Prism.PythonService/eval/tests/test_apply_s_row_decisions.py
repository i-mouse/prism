"""Tests for eval/apply_s_row_decisions.py, on small synthetic inputs under tmp_path."""
import json

import pytest

from eval.apply_s_row_decisions import apply_decisions, run, serialize
from eval.match_map import fingerprint_claim_text

ARXIV = "2610.11519"  # P1
CLAIMS = ["First claim text.", "Second  claim\ntext.", "Third claim text."]
_BLANK = {
    "persisted_claim_id": None, "claim_fingerprint": None, "decided_by": None, "decided_on": None,
    "reason": None, "confirmed_no_match": False, "suggested": None,
}
_R_ROW = {**_BLANK, "claim_fingerprint": "a" * 64, "decided_by": "old", "decided_on": "2026-10-12",
          "reason": "adjudicated match to run1 claim index 0"}


def _decisions(**overrides):
    base = {
        "match_rule": "subset", "decided_by": "Tester", "decided_on": "2026-10-27",
        "expected_totals": {"match": 1, "no_match": 1, "total": 2},
        "rows": [
            {"row_id": "P1-S1", "arxiv": ARXIV, "gemini": [1, "high"], "chatgpt": [1, "high"],
             "decision_source": "judges_agreed", "final": 1, "reviewed": True},
            {"row_id": "P1-S2", "arxiv": ARXIV, "gemini": ["NO_MATCH", "high"], "chatgpt": ["NO_MATCH", "high"],
             "decision_source": "judges_agreed", "final": "NO_MATCH", "reviewed": True},
        ],
    }
    base.update(overrides)
    return base


def _setup(tmp_path, decisions=None):
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / f"arxiv-{ARXIV}v1.json").write_text(json.dumps({"claims": [
        {"index": i, "claim_text_verbatim": t} for i, t in enumerate(CLAIMS)
    ]}), encoding="utf-8")
    map_raw = {
        "metadata": {"prompt_hash": "h", "fixture_file": "dev/run1", "schema_version": 1},
        "rows": {"P1-R1": _R_ROW, "P1-S1": dict(_BLANK), "P1-S2": dict(_BLANK)},
    }
    map_path = tmp_path / "dev_match_map.json"
    map_path.write_text(serialize(map_raw), encoding="utf-8", newline="")
    dec_path = tmp_path / "decisions.json"
    dec_path.write_text(json.dumps(decisions or _decisions()), encoding="utf-8")
    eval_path = tmp_path / "dev_eval.json"
    eval_path.write_text(json.dumps({"metadata": {}, "papers": [{
        "paper_id": f"arxiv-{ARXIV}v1", "filename": "a.pdf", "title": "A",
        "expected_matrix": [
            {"id": rid, "expected_label": lab, "grounding_negative": neg, "claim_text_verbatim": "row text " + rid}
            for rid, lab, neg in (("P1-R1", "partially_supported", True), ("P1-S1", "supported", False),
                                  ("P1-S2", "supported", False))
        ],
    }]}), encoding="utf-8")
    return dec_path, map_path, fixture_dir, eval_path, map_raw


def test_non_s_rows_and_metadata_unchanged(tmp_path):
    dec_path, map_path, fixture_dir, eval_path, before = _setup(tmp_path)
    original = map_path.read_text(encoding="utf-8")

    dry = run(dec_path, map_path, fixture_dir, eval_path)  # dry run is the default
    assert map_path.read_text(encoding="utf-8") == original
    assert dry["changed"] == ["P1-S1", "P1-S2"]

    run(dec_path, map_path, fixture_dir, eval_path, write=True)

    after = json.loads(map_path.read_text(encoding="utf-8"))
    assert after["metadata"] == before["metadata"]
    assert after["rows"]["P1-R1"] == before["rows"]["P1-R1"]
    assert after["rows"]["P1-S1"]["claim_fingerprint"] is not None
    assert after["rows"]["P1-S2"]["confirmed_no_match"] is True


def test_out_of_range_index_is_rejected(tmp_path):
    decisions = _decisions()
    decisions["rows"][0]["final"] = 3  # paper has claims 0..2
    dec_path, map_path, fixture_dir, eval_path, map_raw = _setup(tmp_path, decisions)
    original = map_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="out of range"):
        run(dec_path, map_path, fixture_dir, eval_path, write=True)
    with pytest.raises(ValueError, match="out of range"):
        apply_decisions(map_raw, decisions, {ARXIV: [{"claim_text_verbatim": t} for t in CLAIMS]})

    assert map_path.read_text(encoding="utf-8") == original


def test_unreviewed_row_blocks_write(tmp_path):
    decisions = _decisions()
    decisions["rows"][1]["reviewed"] = False
    dec_path, map_path, fixture_dir, eval_path, _ = _setup(tmp_path, decisions)
    original = map_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="reviewed"):
        run(dec_path, map_path, fixture_dir, eval_path, write=True)

    assert map_path.read_text(encoding="utf-8") == original


def test_match_rule_other_than_subset_blocks_write(tmp_path):
    dec_path, map_path, fixture_dir, eval_path, _ = _setup(tmp_path, _decisions(match_rule="strict"))
    original = map_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="match_rule"):
        run(dec_path, map_path, fixture_dir, eval_path, write=True)

    assert map_path.read_text(encoding="utf-8") == original


def test_fingerprints_equal_fingerprint_claim_text(tmp_path):
    dec_path, map_path, fixture_dir, eval_path, _ = _setup(tmp_path)

    run(dec_path, map_path, fixture_dir, eval_path, write=True)

    row = json.loads(map_path.read_text(encoding="utf-8"))["rows"]["P1-S1"]
    assert row["claim_fingerprint"] == fingerprint_claim_text(CLAIMS[1])
    assert row["reason"] == "adjudicated match to run1 claim index 1"
    assert row["confirmed_no_match"] is False
    assert (row["decided_by"], row["decided_on"]) == ("Tester", "2026-10-27")
