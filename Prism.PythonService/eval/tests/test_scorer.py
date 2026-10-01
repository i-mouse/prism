from eval.scorer import score
from eval.types import ActualClaim, ExpectedRow, Match


def test_negative_row_engine_says_supported_fails():
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N1"].outcome == "WRONGLY_AFFIRMED"
    assert report.correct_refusals == 0
    assert report.total_negatives == 1


def test_negative_row_engine_says_not_supported_passes():
    expected = [ExpectedRow(id="N2", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="not_supported")]
    matches = [Match(expected_id="N2", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N2"].outcome == "REFUSED"
    assert report.correct_refusals == 1
    assert report.total_negatives == 1


def test_negative_row_engine_says_partially_supported_passes():
    expected = [ExpectedRow(id="N3", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="partially_supported")]
    matches = [Match(expected_id="N3", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N3"].outcome == "REFUSED"
    assert report.correct_refusals == 1
    assert report.total_negatives == 1


def test_negative_row_omitted_earns_no_credit():
    """Renamed from test_negative_row_engine_omitted_passes: an unmatched
    golden row used to be scored as a correct refusal (PASS). That was the
    omission-credit bug - the extractor has no way to know which golden
    rows are grounding-negative, so silence is an accident, not judgment.
    It must earn zero credit while still counting toward total_negatives."""
    expected = [ExpectedRow(id="N4", expected_label="not_supported", grounding_negative=True)]
    actual: list[ActualClaim] = []
    matches = [Match(expected_id="N4", actual_index=None)]

    report = score(expected, actual, matches)

    assert report.per_row["N4"].outcome == "NOT_EXTRACTED"
    assert report.per_row["N4"].actual_label is None
    assert report.correct_refusals == 0
    assert report.not_extracted == 1
    assert report.total_negatives == 1


def test_grounding_negative_partial_support_expected_engine_says_supported_fails():
    expected = [ExpectedRow(id="N5", expected_label="partially_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported")]
    matches = [Match(expected_id="N5", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N5"].outcome == "WRONGLY_AFFIRMED"
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

    # N1 wrongly affirmed, N2/N3 refused by label, N4 not extracted (no
    # credit), N5 wrongly affirmed. correct_refusals = N2 + N3 only.
    assert report.correct_refusals == 2
    assert report.total_negatives == 5
    assert report.refusal_rate == 2 / 5
    assert report.wrongly_affirmed == 2
    assert report.not_extracted == 1
    assert report.positive_hits == 1
    assert report.positive_total == 1

    assert report.per_row["N1"].outcome == "WRONGLY_AFFIRMED"
    assert report.per_row["N2"].outcome == "REFUSED"
    assert report.per_row["N3"].outcome == "REFUSED"
    assert report.per_row["N4"].outcome == "NOT_EXTRACTED"
    assert report.per_row["N5"].outcome == "WRONGLY_AFFIRMED"
    assert report.per_row["P1"].outcome == "POSITIVE_HIT"


def test_refused_by_label_incremented():
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="not_supported")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.refused_by_label == 1
    assert report.not_extracted == 0


def test_not_extracted_incremented_but_not_credited():
    """Renamed from test_refused_by_omission_incremented: an unmatched row
    increments not_extracted, never refused_by_label/correct_refusals -
    omission is tracked, not rewarded."""
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual: list[ActualClaim] = []
    matches = [Match(expected_id="N1", actual_index=None)]

    report = score(expected, actual, matches)

    assert report.not_extracted == 1
    assert report.refused_by_label == 0
    assert report.correct_refusals == 0


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

    assert report.per_row["N1"].outcome == "REFUSED"
    assert report.correct_refusals == 1
    assert report.refused_by_grounding == 1
    assert report.refused_by_label == 0


def test_grounding_rejection_takes_precedence_over_wrongly_affirmed():
    """A claim the extractor optimistically labeled 'supported' but that the
    grounder vetoed must be scored REFUSED (via grounding), never
    WRONGLY_AFFIRMED - grounding rejection is checked before label."""
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported", missing=True, grounding_status="Fail")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N1"].outcome == "REFUSED"
    assert report.wrongly_affirmed == 0


def test_wrongly_affirmed_incremented_and_not_credited():
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported", missing=False, grounding_status="Pass")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches)

    assert report.per_row["N1"].outcome == "WRONGLY_AFFIRMED"
    assert report.wrongly_affirmed == 1
    assert report.correct_refusals == 0
    assert report.refused_by_label == 0
    assert report.refused_by_grounding == 0


def test_skipped_claim_excluded_from_negative_denominators():
    """A negative row matched to a Skipped claim must not count as a correct
    refusal (positive-sounding) or a fail (negative-sounding) - it's simply
    excluded from total_negatives entirely."""
    expected = [ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True)]
    actual = [ActualClaim(index=0, label="supported", grounding_status="Skipped")]
    matches = [Match(expected_id="N1", actual_index=0)]

    report = score(expected, actual, matches, positive_hit_floor=0)

    assert report.per_row["N1"].outcome == "SKIPPED"
    assert report.skipped == 1
    assert report.total_negatives == 0
    assert report.correct_refusals == 0
    assert report.refused_by_label == 0
    assert report.not_extracted == 0
    assert report.refused_by_grounding == 0


def test_skipped_claim_excluded_from_positive_denominators():
    expected = [ExpectedRow(id="P1", expected_label="supported", grounding_negative=False)]
    actual = [ActualClaim(index=0, label="supported", grounding_status="Skipped")]
    matches = [Match(expected_id="P1", actual_index=0)]

    report = score(expected, actual, matches, positive_hit_floor=0)

    assert report.per_row["P1"].outcome == "SKIPPED"
    assert report.skipped == 1
    assert report.positive_total == 0
    assert report.positive_hits == 0
    assert report.false_rejections == 0


def test_strict_refusal_rate_lower_than_family_tolerant_rate():
    """correct_refusals (family tolerance) credits both grounding-rejection
    and label-based refusal, but never omission. strict_correct_refusals
    requires the extractor's own label to exactly match expected_label, and
    is 0 for an omitted row (no label was ever emitted) as well as for a
    grounding-rejected row whose label happened to read differently. Same
    denominator (total_negatives), lower numerator."""
    expected = [
        ExpectedRow(id="N1", expected_label="not_supported", grounding_negative=True),  # not extracted
        ExpectedRow(id="N2", expected_label="not_supported", grounding_negative=True),  # grounded away
        ExpectedRow(id="N3", expected_label="not_supported", grounding_negative=True),  # exact label match
        ExpectedRow(id="N4", expected_label="not_supported", grounding_negative=True),  # family match, not exact
    ]
    actual = [
        ActualClaim(index=1, label="supported", missing=True, grounding_status="Fail"),
        ActualClaim(index=2, label="not_supported"),
        ActualClaim(index=3, label="partially_supported"),
    ]
    matches = [
        Match(expected_id="N1", actual_index=None),
        Match(expected_id="N2", actual_index=1),
        Match(expected_id="N3", actual_index=2),
        Match(expected_id="N4", actual_index=3),
    ]

    report = score(expected, actual, matches, positive_hit_floor=0)

    assert report.total_negatives == 4
    assert report.not_extracted == 1
    assert report.correct_refusals == 3
    assert report.refusal_rate == 0.75
    assert report.strict_correct_refusals == 1
    assert report.strict_refusal_rate == 0.25


def test_total_silence_earns_zero_refusal_credit():
    """Renamed from test_silence_gaming_caught. Previously: an engine that
    emits zero claims for every negative row was scored as a 100% refusal
    rate via omission credit - the exact bug this PR removes. Now silence
    earns nothing: refusal_rate is honestly 0%, not_extracted absorbs all 17
    rows, and the positive-hit floor still independently invalidates the run.
    """
    expected = [
        ExpectedRow(id=f"N{i}", expected_label="not_supported", grounding_negative=True)
        for i in range(17)
    ]
    actual: list[ActualClaim] = []
    matches = [Match(expected_id=f"N{i}", actual_index=None) for i in range(17)]

    report = score(expected, actual, matches)

    assert report.correct_refusals == 0
    assert report.total_negatives == 17
    assert report.refusal_rate == 0.0
    assert report.not_extracted == 17
    assert report.refused_by_label == 0
    assert report.positive_hits == 0
    assert report.refusal_rate_valid is False
    assert report.invalid_reason == "positive hits 0 below floor 15"
