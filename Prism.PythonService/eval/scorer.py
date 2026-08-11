"""Pure scoring function for the eval harness.

Takes expected rows, actual extracted claims, and LLM-produced matches,
and computes the correct-refusal rate plus per-row outcomes. No I/O.
"""
from eval.types import ActualClaim, EvalReport, ExpectedRow, Match, RowOutcome

_REFUSAL_LABELS = {"not_supported", "partially_supported"}


def score(
    expected_rows: list[ExpectedRow],
    actual_claims: list[ActualClaim],
    matches: list[Match],
) -> EvalReport:
    actual_by_index = {claim.index: claim for claim in actual_claims}
    match_by_expected_id = {match.expected_id: match for match in matches}

    per_row: dict[str, RowOutcome] = {}
    correct_refusals = 0
    total_negatives = 0
    positive_hits = 0
    positive_total = 0

    for row in expected_rows:
        is_negative = row.grounding_negative or row.expected_label == "not_supported"

        match = match_by_expected_id.get(row.id)
        actual_claim = None
        if match is not None and match.actual_index is not None:
            actual_claim = actual_by_index.get(match.actual_index)
        actual_label = actual_claim.label if actual_claim is not None else None

        if is_negative:
            total_negatives += 1
            if actual_claim is None or actual_claim.label in _REFUSAL_LABELS:
                outcome = "PASS"
                correct_refusals += 1
            else:
                outcome = "FAIL"
        else:
            positive_total += 1
            if actual_claim is not None and actual_claim.label == row.expected_label:
                outcome = "POSITIVE_HIT"
                positive_hits += 1
            else:
                outcome = "POSITIVE_MISS"

        per_row[row.id] = RowOutcome(
            expected_id=row.id,
            outcome=outcome,
            expected_label=row.expected_label,
            actual_label=actual_label,
        )

    refusal_rate = correct_refusals / total_negatives if total_negatives else 0.0

    return EvalReport(
        correct_refusals=correct_refusals,
        total_negatives=total_negatives,
        refusal_rate=refusal_rate,
        positive_hits=positive_hits,
        positive_total=positive_total,
        per_row=per_row,
    )
