"""Tests for eval/inventory_compare.py.

Run only these tests (no network, no LLM):
  uv run pytest eval/tests/test_inventory_compare.py -v
"""
from eval.inventory_compare import (
    Candidate,
    Claim,
    band_for,
    normalize_for_match,
    one_to_one_match,
    recall,
    recall_gain_pp,
    shortlist,
    strict_precision,
)


# ---------------------------------------------------------------------------
# normalize_for_match
# ---------------------------------------------------------------------------
def test_normalize_hyphen_linebreak_joins_lowercase_continuation():
    assert normalize_for_match("exam-\nple") == "example"


def test_normalize_hyphen_linebreak_keeps_hyphen_before_digit():
    assert normalize_for_match("foo-\n9") == "foo- 9"


def test_normalize_hyphen_linebreak_keeps_hyphen_before_capital():
    assert normalize_for_match("foo-\nBar") == "foo- Bar"


def test_normalize_quote_and_dash_translation():
    assert normalize_for_match("“quoted” — text") == '"quoted" - text'


def test_normalize_collapses_all_whitespace():
    assert normalize_for_match("a   b\n\nc\t d") == "a b c d"


def test_normalize_is_idempotent():
    s = "Exam-\nple with “curly” quotes — and  spacing."
    once = normalize_for_match(s)
    twice = normalize_for_match(once)
    assert once == twice


# ---------------------------------------------------------------------------
# band_for
# ---------------------------------------------------------------------------
def test_band_for_auto_at_90():
    assert band_for(90, 0) == "auto"


def test_band_for_borderline_by_fuzz_ratio_floor():
    assert band_for(60, 0) == "borderline"


def test_band_for_borderline_by_partial_ratio():
    assert band_for(10, 90) == "borderline"


def test_band_for_none_below_both_floors():
    assert band_for(59, 89) == "none"


# ---------------------------------------------------------------------------
# shortlist
# ---------------------------------------------------------------------------
def test_shortlist_scores_every_pair():
    key = [Claim("K1", "a"), Claim("K2", "b")]
    pipeline = [Claim("P1", "x"), Claim("P2", "y")]
    cands = shortlist(key, pipeline)
    assert len(cands) == 4
    pairs = {(c.key_id, c.pipeline_id) for c in cands}
    assert pairs == {("K1", "P1"), ("K1", "P2"), ("K2", "P1"), ("K2", "P2")}


def test_shortlist_identical_text_is_auto():
    key = [Claim("K1", "The method is fast.")]
    pipeline = [Claim("P1", "The method is fast.")]
    cands = shortlist(key, pipeline)
    assert len(cands) == 1
    assert cands[0].fuzz_ratio == 100.0
    assert cands[0].band == "auto"


# ---------------------------------------------------------------------------
# one_to_one_match: a key claim matched at most once per arm, a pipeline
# claim matched at most once.
# ---------------------------------------------------------------------------
def test_one_to_one_no_double_use_of_key_or_pipeline():
    cands = [
        Candidate("K1", "P1", 95.0, 95.0, "auto"),
        Candidate("K1", "P2", 92.0, 92.0, "auto"),  # K1 already used by P1 at higher score
        Candidate("K2", "P1", 99.0, 99.0, "auto"),  # P1 already used; higher score wins it first
    ]
    locked = one_to_one_match(cands, min_band="auto")
    key_ids = [c.key_id for c in locked]
    pipeline_ids = [c.pipeline_id for c in locked]
    assert len(key_ids) == len(set(key_ids))
    assert len(pipeline_ids) == len(set(pipeline_ids))
    locked_pairs = {(c.key_id, c.pipeline_id) for c in locked}
    assert ("K2", "P1") in locked_pairs  # highest score wins P1
    assert ("K1", "P1") not in locked_pairs
    assert ("K1", "P2") in locked_pairs  # K1's next-best, still available


def test_one_to_one_respects_min_band_auto_excludes_borderline():
    cands = [Candidate("K1", "P1", 70.0, 10.0, "borderline")]
    assert one_to_one_match(cands, min_band="auto") == []


def test_one_to_one_min_band_borderline_admits_borderline_and_auto():
    cands = [
        Candidate("K1", "P1", 70.0, 10.0, "borderline"),
        Candidate("K2", "P2", 95.0, 95.0, "auto"),
    ]
    locked = one_to_one_match(cands, min_band="borderline")
    assert len(locked) == 2


def test_one_to_one_empty_input():
    assert one_to_one_match([]) == []


# ---------------------------------------------------------------------------
# strict precision, recall, recall-gain arithmetic
# ---------------------------------------------------------------------------
def test_recall_basic_fraction():
    key = [Claim("K1", "a"), Claim("K2", "b"), Claim("K3", "c"), Claim("K4", "d")]
    assert recall({"K1", "K2"}, key) == 0.5


def test_recall_empty_key_is_zero_not_zero_division():
    assert recall({"K1"}, []) == 0.0


def test_strict_precision_basic_fraction():
    pipeline = [Claim("P1", "a"), Claim("P2", "b"), Claim("P3", "c")]
    assert strict_precision({"P1", "P2"}, pipeline) == 2 / 3


def test_strict_precision_unmatched_pipeline_sentence_counts_against_it():
    pipeline = [Claim("P1", "a"), Claim("P2", "b")]
    assert strict_precision({"P1"}, pipeline) == 0.5


def test_strict_precision_empty_pipeline_is_zero_not_zero_division():
    assert strict_precision(set(), []) == 0.0


def test_recall_gain_pp_only_counts_newly_matched_key_claims():
    key = [Claim(f"K{i}", str(i)) for i in range(10)]
    base_matched = {"K0", "K1"}
    combined_matched = {"K0", "K1", "K2", "K3"}
    assert recall_gain_pp(base_matched, combined_matched, key) == 20.0


def test_recall_gain_pp_zero_when_combined_adds_nothing_new():
    key = [Claim(f"K{i}", str(i)) for i in range(5)]
    base_matched = {"K0", "K1"}
    combined_matched = {"K0"}  # subset, nothing new
    assert recall_gain_pp(base_matched, combined_matched, key) == 0.0


def test_recall_gain_pp_empty_key_is_zero():
    assert recall_gain_pp({"K0"}, {"K0", "K1"}, []) == 0.0
