"""Unit tests for eval/score_replay.py.

Covers the confirmed_no_match scoring defect found while compiling the
Experiment 1 Stage A control report: a row with no claim_index (extraction
miss) must score NOT_EXTRACTED without requiring that row's paper to have a
fixture file in the scored directory at all - and the raw/effective scoring
mode split added for the Stage A amendment.
"""
from pathlib import Path

from eval.score_replay import AdjudicatedRow, score_directory
from eval.types import ExpectedRow


def _expected_row(row_id: str, label: str) -> ExpectedRow:
    return ExpectedRow(id=row_id, expected_label=label, grounding_negative=True)


def test_confirmed_no_match_row_scores_not_extracted_without_any_fixture(tmp_path):
    """A row whose paper was never part of this replay's --claims scope (so
    no fixture file for that paper exists in this directory at all) must
    still score NOT_EXTRACTED, not FIXTURE_MISSING - no claim ever existed
    for a confirmed_no_match row under any replay."""
    rows = [AdjudicatedRow(row_id="P9-R1", paper_id="arxiv-nonexistent", claim_index=None,
                            expected_row=_expected_row("P9-R1", "partially_supported"))]

    outcomes, labels = score_directory(rows, tmp_path)

    assert outcomes["P9-R1"] == "NOT_EXTRACTED"
    assert labels["P9-R1"] is None


def test_claim_index_row_scores_fixture_missing_when_paper_file_absent(tmp_path):
    rows = [AdjudicatedRow(row_id="P1-R1", paper_id="arxiv-missing", claim_index=3,
                            expected_row=_expected_row("P1-R1", "partially_supported"))]

    outcomes, labels = score_directory(rows, tmp_path)

    assert outcomes["P1-R1"] == "FIXTURE_MISSING"


def test_raw_mode_ignores_grounding_rejection():
    """A claim with raw label 'supported' but missing=True (grounded away)
    must score WRONGLY_AFFIRMED under --mode raw (pure label check), but
    REFUSED under the default effective mode."""
    import json

    def _write_fixture(dir_path: Path, paper_id: str) -> None:
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / f"{paper_id}.json").write_text(json.dumps({
            "header": {},
            "claims": [{
                "index": 0, "label": "supported", "claim_summary": "s", "missing": True,
                "grounding_status": "Fail", "claim_text_verbatim": "c", "evidence_spans": [],
            }],
            "matches": [],
        }), encoding="utf-8")

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        fixture_dir = Path(d)
        _write_fixture(fixture_dir, "paperA")
        rows = [AdjudicatedRow(row_id="R1", paper_id="paperA", claim_index=0,
                                expected_row=_expected_row("R1", "partially_supported"))]

        effective_outcomes, _ = score_directory(rows, fixture_dir, mode="effective")
        raw_outcomes, _ = score_directory(rows, fixture_dir, mode="raw")

    assert effective_outcomes["R1"] == "REFUSED"
    assert raw_outcomes["R1"] == "WRONGLY_AFFIRMED"
