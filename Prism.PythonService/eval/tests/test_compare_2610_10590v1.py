"""Synthetic-fixture tests for eval/compare_2610_10590v1.py's keep/drop logic.

Run only these tests (no network, no LLM):
  uv run pytest eval/tests/test_compare_2610_10590v1.py -v
"""
from eval.compare_2610_10590v1 import (
    Candidate,
    Claim,
    combine_verdicts,
    decide_keep_drop,
    score_key,
)


def _key(n: int) -> tuple[list[Claim], set[str]]:
    claims = [Claim(f"K{i}", f"sentence {i}") for i in range(n)]
    return claims, {c.id for c in claims}


# ---------------------------------------------------------------------------
# decide_keep_drop / combine_verdicts: atomic unit tests
# ---------------------------------------------------------------------------
def test_decide_keep_drop_keep_at_both_thresholds():
    assert decide_keep_drop(10.0, 0.70) == "KEEP"


def test_decide_keep_drop_drop_below_gain():
    assert decide_keep_drop(9.99, 0.95) == "DROP"


def test_decide_keep_drop_drop_below_precision():
    assert decide_keep_drop(50.0, 0.69) == "DROP"


def test_combine_verdicts_agree_keep():
    assert combine_verdicts("KEEP", "KEEP") == "KEEP"


def test_combine_verdicts_agree_drop():
    assert combine_verdicts("DROP", "DROP") == "DROP"


def test_combine_verdicts_disagree_is_drop():
    assert combine_verdicts("KEEP", "DROP") == "DROP"
    assert combine_verdicts("DROP", "KEEP") == "DROP"


# ---------------------------------------------------------------------------
# score_key: tiny synthetic fixture, one KEEP
# key size 10; pass1 matches 2; filtered pass2 matches 3 MORE (gain = 3/10 =
# 30pp >= 10); filtered pass2 pipeline size 3, all 3 match the key (precision
# 3/3 = 1.0 >= 0.70) -> KEEP
# ---------------------------------------------------------------------------
def test_score_key_keep_fixture():
    key, key_ids = _key(10)
    pass1_locked = [Candidate("K0", "P1_0", 100.0, 100.0, "auto"), Candidate("K1", "P1_1", 100.0, 100.0, "auto")]
    raw_pass2_locked: list[Candidate] = []
    filtered_pass2_locked = [
        Candidate("K2", "P2_0", 100.0, 100.0, "auto"),
        Candidate("K3", "P2_1", 100.0, 100.0, "auto"),
        Candidate("K4", "P2_2", 100.0, 100.0, "auto"),
    ]
    result = score_key(key, key_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, filtered_pass2_size=3)
    assert result.gain_pp == 30.0
    assert result.precision_filtered_pass2 == 1.0
    assert result.verdict == "KEEP"


# ---------------------------------------------------------------------------
# score_key: tiny synthetic fixture, DROP on gain
# key size 10; pass1 matches 5; filtered pass2 adds only the SAME ids pass 1
# already matched (0 new) -> gain 0pp < 10 -> DROP, even though precision is
# perfect.
# ---------------------------------------------------------------------------
def test_score_key_drop_on_gain_fixture():
    key, key_ids = _key(10)
    pass1_locked = [Candidate(f"K{i}", f"P1_{i}", 100.0, 100.0, "auto") for i in range(5)]
    raw_pass2_locked: list[Candidate] = []
    filtered_pass2_locked = [Candidate("K0", "P2_0", 100.0, 100.0, "auto"), Candidate("K1", "P2_1", 100.0, 100.0, "auto")]
    result = score_key(key, key_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, filtered_pass2_size=2)
    assert result.gain_pp == 0.0
    assert result.precision_filtered_pass2 == 1.0
    assert result.verdict == "DROP"


# ---------------------------------------------------------------------------
# score_key: tiny synthetic fixture, DROP on precision
# key size 10; pass1 matches 0; filtered pass2 matches 2 NEW key claims
# (gain = 20pp >= 10) but its pipeline has 10 sentences total, only 2 match
# any key claim -> precision 2/10 = 0.20 < 0.70 -> DROP.
# ---------------------------------------------------------------------------
def test_score_key_drop_on_precision_fixture():
    key, key_ids = _key(10)
    pass1_locked: list[Candidate] = []
    raw_pass2_locked: list[Candidate] = []
    filtered_pass2_locked = [Candidate("K0", "P2_0", 100.0, 100.0, "auto"), Candidate("K1", "P2_1", 100.0, 100.0, "auto")]
    result = score_key(key, key_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, filtered_pass2_size=10)
    assert result.gain_pp == 20.0
    assert result.precision_filtered_pass2 == 0.20
    assert result.verdict == "DROP"


# ---------------------------------------------------------------------------
# A/B disagreement, direction 1: Key A KEEP, Key B DROP via gain dilution.
# ONE shared filtered_pass2_size (as the real run always has - 18). Key B
# adds unsure items pass 2 never matches, which only dilutes the gain
# PERCENTAGE (bigger key-size denominator, same numerator) - precision is
# untouched since its own denominator (filtered_pass2_size) is identical for
# both keys.
#   Key A = 5 items (K0..K4). Key B = Key A + 6 unmatched "unsure" items
#   (K5..K10, 11 total). filtered pass 2 has exactly 1 sentence, matching K0
#   (common to both keys). precision = 1/1 = 1.0 for both (>=0.70, passes).
#   gain under A = 1/5 = 20pp (>=10 -> KEEP). gain under B = 1/11 ~ 9.09pp
#   (<10 -> DROP, purely from the larger key denominator).
# ---------------------------------------------------------------------------
def test_score_both_keys_disagreement_gain_direction():
    key_a, key_a_ids = _key(5)
    key_b_claims = key_a + [Claim(f"K{i}", f"unsure {i}") for i in range(5, 11)]
    key_b_ids = key_a_ids | {f"K{i}" for i in range(5, 11)}

    pass1_locked: list[Candidate] = []
    raw_pass2_locked: list[Candidate] = []
    filtered_pass2_locked = [Candidate("K0", "P2_0", 100.0, 100.0, "auto")]
    shared_filtered_pass2_size = 1  # same for A and B, as in the real run

    score_a = score_key(key_a, key_a_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, shared_filtered_pass2_size)
    score_b = score_key(key_b_claims, key_b_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, shared_filtered_pass2_size)

    assert score_a.precision_filtered_pass2 == score_b.precision_filtered_pass2 == 1.0
    assert score_a.gain_pp == 20.0
    assert round(score_b.gain_pp, 2) == 9.09
    assert score_a.verdict == "KEEP"
    assert score_b.verdict == "DROP"

    final = combine_verdicts(score_a.verdict, score_b.verdict)
    assert final == "DROP"


# ---------------------------------------------------------------------------
# A/B disagreement, direction 2: Key A DROP (on precision), Key B KEEP.
# ONE shared filtered_pass2_size = 10. filtered pass 2 matches 6 key-A
# claims plus 2 claims that exist only in key B (unsure). pass 1 matches
# none.
#   Key A = 12 items (K0..K11); only K0..K5 (6) get matched.
#   Key B = Key A + 2 unsure items (K12, K13, 14 total); both ALSO matched.
#   Under A: the 2 unsure matches are excluded by restrict_to_key ->
#     matched pipeline ids = 6 -> precision 6/10 = 0.60 -> DROP (gain alone,
#     6/12=50pp, would pass, but precision fails).
#   Under B: all 8 matches count -> precision 8/10 = 0.80; gain 8/14 ~
#     57.1pp (>=10) -> KEEP.
#   Final = combine(DROP, KEEP) = DROP.
# ---------------------------------------------------------------------------
def test_score_both_keys_disagreement_precision_direction():
    key_a, key_a_ids = _key(12)
    key_b_claims = key_a + [Claim("K12", "unsure 12"), Claim("K13", "unsure 13")]
    key_b_ids = key_a_ids | {"K12", "K13"}

    pass1_locked: list[Candidate] = []
    raw_pass2_locked: list[Candidate] = []
    filtered_pass2_locked = [Candidate(f"K{i}", f"P2_{i}", 100.0, 100.0, "auto") for i in range(6)] + [
        Candidate("K12", "P2_12", 100.0, 100.0, "auto"),
        Candidate("K13", "P2_13", 100.0, 100.0, "auto"),
    ]
    shared_filtered_pass2_size = 10

    score_a = score_key(key_a, key_a_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, shared_filtered_pass2_size)
    score_b = score_key(key_b_claims, key_b_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, shared_filtered_pass2_size)

    assert score_a.precision_filtered_pass2 == 0.60
    assert score_a.verdict == "DROP"
    assert score_b.precision_filtered_pass2 == 0.80
    assert score_b.verdict == "KEEP"

    final = combine_verdicts(score_a.verdict, score_b.verdict)
    assert final == "DROP"
