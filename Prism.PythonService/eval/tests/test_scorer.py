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
