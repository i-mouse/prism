"""eval/testb/score_one_call.py: anchor splitting, the 30-char rule, the threshold edge,
the tie rule, vote/verdict/VOID logic, and the Prism-caught derivation. Made-up papers
and rows only; no network, no real dev_eval.json content is asserted on."""
import json
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval import score_a1, score_exp2
from eval.testb import score_one_call
from extraction.grounding import _stage1_score


def _row(row_id: str, claim_text_verbatim: str) -> SimpleNamespace:
    return SimpleNamespace(id=row_id, claim_text_verbatim=claim_text_verbatim)


# --------------------------------------------------------------------------- anchor

def test_anchor_keeps_longest_piece_when_long_enough():
    text = "short lead in ... this is the long remainder piece that is well over thirty characters long"
    anchor = score_one_call._anchor(text)
    assert anchor == "this is the long remainder piece that is well over thirty characters long"


def test_anchor_joins_gap_removed_pieces_when_all_short():
    text = "first short ... second short"
    anchor = score_one_call._anchor(text)
    assert "..." not in anchor
    assert anchor == "first short second short"


def test_anchor_handles_unicode_ellipsis():
    text = "lead…this long tail piece is comfortably past thirty characters in length"
    anchor = score_one_call._anchor(text)
    assert anchor == "this long tail piece is comfortably past thirty characters in length"


def test_anchor_no_ellipsis_returns_whole_text():
    text = "a plain claim with no ellipsis anywhere in it at all"
    assert score_one_call._anchor(text) == text


# --------------------------------------------------------------------------- 30-char rule and threshold edge

def test_match_score_zero_when_shorter_string_under_30_chars():
    assert score_one_call._match_score("short", "also quite a long claim quote text over thirty chars") == 0.0


def test_row_match_threshold_edge_not_matched_below_88(monkeypatch):
    monkeypatch.setattr(score_one_call, "_match_score", lambda anchor, quote: 87.9)
    row = _row("P1-R1", "x" * 40)
    record = {"status": "OK", "parsed": {"claims": [{"claim_quote": "y" * 40, "verdict": "not_supported"}]}}
    result = score_one_call._row_match(row, record)
    assert result["status"] == "not_found"


def test_row_match_threshold_edge_matched_at_88(monkeypatch):
    monkeypatch.setattr(score_one_call, "_match_score", lambda anchor, quote: 88.0)
    row = _row("P1-R1", "x" * 40)
    record = {"status": "OK", "parsed": {"claims": [{"claim_quote": "y" * 40, "verdict": "not_supported"}]}}
    result = score_one_call._row_match(row, record)
    assert result["status"] == "flagged"


# --------------------------------------------------------------------------- tie rule

def test_tie_rule_keeps_earliest_claim(monkeypatch):
    monkeypatch.setattr(score_one_call, "_match_score", lambda anchor, quote: 95.0)
    row = _row("P1-R1", "x" * 40)
    record = {
        "status": "OK",
        "parsed": {"claims": [
            {"claim_quote": "first " + "y" * 40, "verdict": "supported"},
            {"claim_quote": "second " + "z" * 40, "verdict": "not_supported"},
        ]},
    }
    result = score_one_call._row_match(row, record)
    assert result["claim_index"] == 0
    assert result["status"] == "supported"


# --------------------------------------------------------------------------- a failed paper-run

@pytest.mark.parametrize("record", [{"status": "FAILED"}, None])
def test_failed_or_missing_paper_run_is_not_found(record):
    row = _row("P1-R1", "x" * 40)
    result = score_one_call._row_match(row, record)
    assert result == {"status": "not_found", "score": 0.0, "claim_index": None}


# --------------------------------------------------------------------------- vote logic

def test_vote_single_run_flagged():
    assert score_one_call._vote(["flagged"]) == ("flagged", "SINGLE-RUN")


def test_vote_single_run_not_flagged():
    assert score_one_call._vote(["supported"]) == ("not_flagged", "SINGLE-RUN")


def test_vote_two_of_three_flagged():
    assert score_one_call._vote(["flagged", "flagged", "supported"]) == ("flagged", "3-RUN")


def test_vote_one_of_three_not_enough():
    assert score_one_call._vote(["flagged", "supported", "supported"]) == ("not_flagged", "3-RUN")


@pytest.mark.parametrize("statuses", [["flagged", "flagged"], ["flagged"] * 4])
def test_vote_invalid_run_count_raises(statuses):
    with pytest.raises(ValueError, match="INVALID"):
        score_one_call._vote(statuses)


def test_matched_majority_counts_not_found_as_unmatched():
    assert score_one_call._matched_majority(["flagged", "not_found", "supported"]) is True
    assert score_one_call._matched_majority(["not_found", "not_found", "supported"]) is False


# --------------------------------------------------------------------------- _stage1_score order independence

@pytest.mark.parametrize("a,b", [
    ("a short reference sentence over thirty chars long", "a SHORT reference sentence over thirty-chars long, reworded"),
    ("completely unrelated made-up text snippet number one", "a wholly different made-up text snippet, number two"),
    ("equal length sample text AAAA", "equal length sample text BBBB"),  # same length pair
])
def test_stage1_score_same_regardless_of_argument_order(a, b):
    assert _stage1_score(a, b, normalize=True) == _stage1_score(b, a, normalize=True)


# --------------------------------------------------------------------------- verdict branches + VOID

def _write_fake_dev_eval(path: Path, n_r: int, n_s: int) -> None:
    rows = []
    for i in range(1, n_r + 1):
        rows.append({
            "id": f"P1-R{i}", "expected_label": "partially_supported", "grounding_negative": True,
            "claim_summary": "s", "claim_text_verbatim": f"made up refusal-family claim text number {i}, long enough to anchor",
        })
    for i in range(1, n_s + 1):
        rows.append({
            "id": f"P1-S{i}", "expected_label": "supported", "grounding_negative": False,
            "claim_summary": "s", "claim_text_verbatim": f"made up supported claim text number {i}, long enough to anchor",
        })
    data = {"papers": [{"paper_id": "arxiv-FAKE1", "filename": "fake1.pdf", "title": "t", "expected_matrix": rows}]}
    path.write_text(json.dumps(data), encoding="utf-8")


def _fake_row_match_factory(status_map: dict[str, list[str]]):
    counters: dict = defaultdict(int)

    def _fake(row, paper_record):
        statuses = status_map[row.id]
        idx = counters[row.id]
        counters[row.id] += 1
        status = statuses[idx]
        score = 100.0 if status != "not_found" else 0.0
        return {"status": status, "score": score, "claim_index": 0 if status != "not_found" else None}

    return _fake


def _score(monkeypatch, tmp_path, n_r, n_s, flagged_r_ids, flagged_s_ids, n_runs=3):
    dev_eval_path = tmp_path / "dev_eval.json"
    _write_fake_dev_eval(dev_eval_path, n_r, n_s)
    status_map = {}
    for i in range(1, n_r + 1):
        rid = f"P1-R{i}"
        status_map[rid] = ["flagged"] * n_runs if rid in flagged_r_ids else ["supported"] * n_runs
    for i in range(1, n_s + 1):
        rid = f"P1-S{i}"
        status_map[rid] = ["flagged"] * n_runs if rid in flagged_s_ids else ["supported"] * n_runs
    monkeypatch.setattr(score_one_call, "_load_run", lambda d: {})
    monkeypatch.setattr(score_one_call, "_row_match", _fake_row_match_factory(status_map))
    run_dirs = [Path(f"fake_run_{i}") for i in range(n_runs)]
    return score_one_call.score_runs(run_dirs, dev_eval_path)


def test_verdict_one_call_better(monkeypatch, tmp_path):
    result = _score(monkeypatch, tmp_path, n_r=15, n_s=10,
                     flagged_r_ids={f"P1-R{i}" for i in range(1, 13)}, flagged_s_ids={f"P1-S{i}" for i in range(1, 7)})
    assert result["caught"] == 12 and result["false_rejections"] == 6
    assert result["verdict"] == "ONE CALL BETTER"


def test_verdict_stricter_not_better(monkeypatch, tmp_path):
    result = _score(monkeypatch, tmp_path, n_r=15, n_s=10,
                     flagged_r_ids={f"P1-R{i}" for i in range(1, 13)}, flagged_s_ids={f"P1-S{i}" for i in range(1, 10)})
    assert result["caught"] == 12 and result["false_rejections"] == 9
    assert result["verdict"] == "STRICTER, NOT BETTER"


def test_verdict_prism_better_via_low_caught(monkeypatch, tmp_path):
    result = _score(monkeypatch, tmp_path, n_r=10, n_s=5,
                     flagged_r_ids={"P1-R1", "P1-R2", "P1-R3", "P1-R4"}, flagged_s_ids=set())
    assert result["caught"] == 4 and result["false_rejections"] == 0
    assert result["verdict"] == "PRISM BETTER"


def test_verdict_prism_better_via_high_false_rejections(monkeypatch, tmp_path):
    result = _score(monkeypatch, tmp_path, n_r=15, n_s=10,
                     flagged_r_ids={f"P1-R{i}" for i in range(1, 7)}, flagged_s_ids={f"P1-S{i}" for i in range(1, 10)})
    assert result["caught"] == 6 and result["false_rejections"] == 9
    assert result["verdict"] == "PRISM BETTER"


def test_verdict_no_clear_difference(monkeypatch, tmp_path):
    result = _score(monkeypatch, tmp_path, n_r=15, n_s=10,
                     flagged_r_ids={f"P1-R{i}" for i in range(1, 7)}, flagged_s_ids={f"P1-S{i}" for i in range(1, 6)})
    assert result["caught"] == 6 and result["false_rejections"] == 5
    assert result["verdict"] == "NO CLEAR DIFFERENCE"


def test_void_when_more_than_two_failed_paper_runs(monkeypatch, tmp_path):
    dev_eval_path = tmp_path / "dev_eval.json"
    _write_fake_dev_eval(dev_eval_path, n_r=1, n_s=1)
    monkeypatch.setattr(score_one_call, "_load_run", lambda d: {
        "arxiv-FAKE1": {"status": "FAILED"}, "arxiv-FAKE2": {"status": "FAILED"},
    })
    run_dirs = [Path("r1"), Path("r2"), Path("r3")]
    result = score_one_call.score_runs(run_dirs, dev_eval_path)
    assert result["status"] == "VOID"
    assert result["failed_paper_runs"] == 6


def test_invalid_run_count_in_score_runs(tmp_path):
    dev_eval_path = tmp_path / "dev_eval.json"
    _write_fake_dev_eval(dev_eval_path, n_r=1, n_s=1)
    result = score_one_call.score_runs([Path("r1"), Path("r2")], dev_eval_path)
    assert result["status"] == "INVALID"


# --------------------------------------------------------------------------- Prism-caught derivation

def test_prism_caught_ids_available_when_sets_are_valid(monkeypatch):
    miss = {f"M{i}" for i in range(10)}
    extraction_miss = {f"E{i}" for i in range(13)}
    all_r_ids = miss | extraction_miss | {f"C{i}" for i in range(8)}
    monkeypatch.setattr(score_a1, "MISS_ROWS", tuple(miss))
    monkeypatch.setattr(score_exp2, "ROW_ID_TO_SHAPE", dict.fromkeys(extraction_miss, "E1"))
    prism_caught = score_one_call._prism_caught_ids(all_r_ids)
    assert prism_caught == {f"C{i}" for i in range(8)}


def test_prism_caught_ids_not_available_when_sets_overlap(monkeypatch):
    miss = {f"M{i}" for i in range(10)}
    extraction_miss = {"M0"} | {f"E{i}" for i in range(12)}  # overlaps M0 - not disjoint
    all_r_ids = miss | extraction_miss | {f"C{i}" for i in range(8)}
    monkeypatch.setattr(score_a1, "MISS_ROWS", tuple(miss))
    monkeypatch.setattr(score_exp2, "ROW_ID_TO_SHAPE", dict.fromkeys(extraction_miss, "E1"))
    assert score_one_call._prism_caught_ids(all_r_ids) is None


def test_prism_caught_ids_not_available_when_complement_is_not_8(monkeypatch):
    miss = {f"M{i}" for i in range(10)}
    extraction_miss = {f"E{i}" for i in range(13)}
    all_r_ids = miss | extraction_miss | {f"C{i}" for i in range(5)}  # complement has 5, not 8
    monkeypatch.setattr(score_a1, "MISS_ROWS", tuple(miss))
    monkeypatch.setattr(score_exp2, "ROW_ID_TO_SHAPE", dict.fromkeys(extraction_miss, "E1"))
    assert score_one_call._prism_caught_ids(all_r_ids) is None


def test_caught_breakdown_reports_not_available_string_when_invalid(monkeypatch):
    monkeypatch.setattr(score_a1, "MISS_ROWS", ("M0", "M1"))  # wrong size (2, not 10)
    monkeypatch.setattr(score_exp2, "ROW_ID_TO_SHAPE", {"E0": "E1"})  # wrong size (1, not 13)
    breakdown = score_one_call._caught_breakdown(["M0", "C1"], {"M0", "M1", "E0", "C1"})
    assert breakdown["prism_caught"] == "NOT AVAILABLE"
    assert breakdown["auditor_miss"] == 1
    assert breakdown["unclassified_if_prism_caught_unavailable"] == 1
