from eval.scorer import score
from eval.types import ActualClaim, ExpectedRow, Match


def test_negative_row_engine_says_supported_fails():
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N1"].outcome == "FAIL"
    assert report.correct_refusals == 0
    assert report.total_negatives == 1


def test_negative_row_engine_says_not_supported_passes():
    expected = [ExpectedRow(id="N2", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="not_supported")]
    matches = [Match(expected_id="N2", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N2"].outcome == "PASS"
    assert report.correct_refusals == 1
    assert report.total_negatives == 1


def test_negative_row_engine_says_partially_supported_passes():
    expected = [ExpectedRow(id="N3", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="partially_supported")]
    matches = [Match(expected_id="N3", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N3"].outcome == "PASS"
    assert report.correct_refusals == 1
    assert report.total_negatives == 1


def test_negative_row_engine_omitted_passes():
    expected = [ExpectedRow(id="N4", expected_label="not_supported", grounding_negative=True)]
    actual: list[ActualClaim] = []
    matches = [Match(expected_id="N4", actual_index=None)]

    report = score(expected, actual, matches)

    assert report.per_row["N4"].outcome == "PASS"
    assert report.per_row["N4"].actual_label is None
    assert report.correct_refusals == 1
    assert report.total_negatives == 1


def test_grounding_negative_partial_support_expected_engine_says_supported_fails():
    expected = [ExpectedRow(id="N5", expected_label="partially_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported")]
    matches = [Match(expected_id="N5", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N5"].outcome == "FAIL"
    assert report.correct_refusals == 0
    assert report.total_negatives == 1


def test_positive_row_correctly_extracted_tracked_as_hit():
    expected = [ExpectedRow(id="P1", expected_label="supported", grounding_negative=False)]
    actual = [ActualClaim(index=0, label="supported")]
    matches = [Match(expected_id="P1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["P1"].outcome == "POSITIVE_HIT"
    assert report.positive_hits == 1
    assert report.positive_total == 1
    # Positive rows must not move the refusal headline numbers.
    assert report.total_negatives == 0
    assert report.correct_refusals == 0


def test_aggregate_matrix_report():
    expected = [
        ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True),
        ExpectedRow(id="N2", expected_label="not_supported", grounding_negative=True),
        ExpectedRow(id="N3", expected_label="not_supported", grounding_negative=True),
        ExpectedRow(id="N4", expected_label="not_supported", grounding_negative=True),
        ExpectedRow(id="N5", expected_label="partially_supported", grounding_negative=True),
        ExpectedRow(id="P1", expected_label="supported", grounding_negative=False),
    ]
    actual = [
        ActualClaim(index=0, label="supported"),
        ActualClaim(index=1, label="not_supported"),
        ActualClaim(index=2, label="partially_supported"),
        ActualClaim(index=3, label="supported"),
        ActualClaim(index=4, label="supported"),
    ]
    matches = [
        Match(expected_id="N1", actual_index=0),
        Match(expected_id="N2", actual_index=1),
        Match(expected_id="N3", actual_index=2),
        Match(expected_id="N4", actual_index=None),
        Match(expected_id="N5", actual_index=3),
        Match(expected_id="P1", actual_index=4),
    ]

    report = score(expected, actual, matches)

    assert report.correct_refusals == 3
    assert report.total_negatives == 5
    assert report.refusal_rate == 3 / 5
    assert report.positive_hits == 1
    assert report.positive_total == 1

    assert report.per_row["N1"].outcome == "FAIL"
    assert report.per_row["N2"].outcome == "PASS"
    assert report.per_row["N3"].outcome == "PASS"
    assert report.per_row["N4"].outcome == "PASS"
    assert report.per_row["N5"].outcome == "FAIL"
    assert report.per_row["P1"].outcome == "POSITIVE_HIT"


def test_refused_by_label_incremented():
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="not_supported")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.refused_by_label == 1
    assert report.refused_by_omission == 0


def test_refused_by_omission_incremented():
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual: list[ActualClaim] = []
    matches = [Match(expected_id="N1", actual_index=None)]

    report = score(expected, actual, matches)

    assert report.refused_by_omission == 1
    assert report.refused_by_label == 0


def test_positive_floor_below_marks_invalid():
    expected = [
        ExpectedRow(id=f"N{i}", expected_label="not_supported", grounding_negative=True)
        for i in range(17)
    ] + [
        ExpectedRow(id=f"P{i}", expected_label="supported", grounding_negative=False)
        for i in range(5)
    ]
    actual = [ActualClaim(index=i, label="not_supported") for i in range(17)] + [
        ActualClaim(index=17 + i, label="supported") for i in range(5)
    ]
    matches = [Match(expected_id=f"N{i}", actual_index=i) for i in range(17)] + [
        Match(expected_id=f"P{i}", actual_index=17 + i) for i in range(5)
    ]

    report = score(expected, actual, matches, positive_hit_floor=15)

    assert report.correct_refusals == 17
    assert report.total_negatives == 17
    assert report.refusal_rate == 1.0
    assert report.positive_hits == 5
    assert report.refusal_rate_valid is False
    assert report.invalid_reason == "positive hits 5 below floor 15"


def test_positive_floor_met_marks_valid():
    expected = [
        ExpectedRow(id=f"P{i}", expected_label="supported", grounding_negative=False)
        for i in range(15)
    ]
    actual = [ActualClaim(index=i, label="supported") for i in range(15)]
    matches = [Match(expected_id=f"P{i}", actual_index=i) for i in range(15)]

    report = score(expected, actual, matches, positive_hit_floor=15)

    assert report.positive_hits == 15
    assert report.refusal_rate_valid is True
    assert report.invalid_reason is None


def test_positive_row_grounded_away_is_false_rejection_not_a_hit():
    """The exact Slice 2.8 blind spot: extractor label is 'supported' (its
    own optimistic assessment survives grounding rejection unchanged) but
    missing=True means the grounder vetoed it. Must not count as a hit."""
    expected = [ExpectedRow(id="P1", expected_label="supported", grounding_negative=False)]
    actual = [ActualClaim(index=0, label="supported", missing=True, grounding_status="Fail")]
    matches = [Match(expected_id="P1", actual_index=0)]

    report = score(expected, actual, matches, positive_hit_floor=0)

    assert report.per_row["P1"].outcome == "FALSE_REJECTION"
    assert report.positive_hits == 0
    assert report.false_rejections == 1
    assert report.false_rejection_rate == 1.0


def test_positive_row_grounding_status_fail_without_missing_flag_is_false_rejection():
    """grounding_status='Fail' alone (missing not set) is still a rejection -
    the metric's OR condition, not just the missing flag."""
    expected = [ExpectedRow(id="P1", expected_label="supported", grounding_negative=False)]
    actual = [ActualClaim(index=0, label="supported", missing=False, grounding_status="Fail")]
    matches = [Match(expected_id="P1", actual_index=0)]

    report = score(expected, actual, matches, positive_hit_floor=0)

    assert report.per_row["P1"].outcome == "FALSE_REJECTION"


def test_positive_hits_and_false_rejections_are_complementary():
    expected = [
        ExpectedRow(id="P1", expected_label="supported", grounding_negative=False),
        ExpectedRow(id="P2", expected_label="supported", grounding_negative=False),
    ]
    actual = [
        ActualClaim(index=0, label="supported", missing=False, grounding_status="Pass"),
        ActualClaim(index=1, label="supported", missing=True, grounding_status="Fail"),
    ]
    matches = [
        Match(expected_id="P1", actual_index=0),
        Match(expected_id="P2", actual_index=1),
    ]

    report = score(expected, actual, matches, positive_hit_floor=0)

    assert report.positive_hits == 1
    assert report.false_rejections == 1
    assert report.positive_hits + report.false_rejections == report.positive_total


def test_negative_row_grounded_away_counts_as_refused_by_grounding():
    """A grounding-negative row where the grounder rejected the claim (rather
    than the extractor's own label happening to be not_supported) is still
    a correct refusal - just via a different bucket than refused_by_label."""
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported", missing=True, grounding_status="Fail")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N1"].outcome == "PASS"
    assert report.correct_refusals == 1
    assert report.refused_by_grounding == 1
    assert report.refused_by_label == 0


def test_silence_gaming_caught():
    """Engine emits zero claims: every negative row passes by omission,
    refusal_rate hits 100%, but positive_hits=0 must invalidate the number.
    """
    expected = [
        ExpectedRow(id=f"N{i}", expected_label="not_supported", grounding_negative=True)
        for i in range(17)
    ]
    actual: list[ActualClaim] = []
    matches = [Match(expected_id=f"N{i}", actual_index=None) for i in range(17)]

    report = score(expected, actual, matches)

    assert report.correct_refusals == 17
    assert report.total_negatives == 17
    assert report.refusal_rate == 1.0
    assert report.refused_by_omission == 17
    assert report.refused_by_label == 0
    assert report.positive_hits == 0
    assert report.refusal_rate_valid is False
    assert report.invalid_reason == "positive hits 0 below floor 15"
