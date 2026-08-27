"""Pure scoring function for the eval harness.

Takes expected rows, actual extracted claims, and LLM-produced matches,
and computes the correct-refusal rate, the false-rejection rate, and
per-row outcomes. No I/O.
"""
from eval.types import ActualClaim, EvalReport, ExpectedRow, Match, RowOutcome

_REFUSAL_LABELS = {"not_supported", "partially_supported"}


def _was_grounded_away(actual_claim: ActualClaim) -> bool:
    """True if the grounding pipeline rejected this claim - missing=true or
    grounding_status=Fail - independent of whatever label the extractor
    optimistically assigned it. This is the exact blind spot Slice 2.8's
    false_rejection_rate metric exists to close: a claim can carry
    label='supported' and still have been grounded away entirely."""
    return actual_claim.missing or actual_claim.grounding_status == "Fail"


def score(
    expected_rows: list[ExpectedRow],
    actual_claims: list[ActualClaim],
    matches: list[Match],
    positive_hit_floor: int = 15,
) -> EvalReport:
    actual_by_index = {claim.index: claim for claim in actual_claims}
    match_by_expected_id = {match.expected_id: match for match in matches}

    per_row: dict[str, RowOutcome] = {}
    correct_refusals = 0
    total_negatives = 0
    positive_hits = 0
    positive_total = 0
    refused_by_label = 0
    refused_by_omission = 0
    refused_by_grounding = 0
    false_rejections = 0

    for row in expected_rows:
        is_negative = row.grounding_negative or row.expected_label == "not_supported"

        match = match_by_expected_id.get(row.id)
        actual_claim = None
        if match is not None and match.actual_index is not None:
            actual_claim = actual_by_index.get(match.actual_index)
        actual_label = actual_claim.label if actual_claim is not None else None
        actual_claim_summary = actual_claim.claim_summary if actual_claim is not None else None
        actual_grounding_status = actual_claim.grounding_status if actual_claim is not None else None

        if is_negative:
            total_negatives += 1
            if actual_claim is None:
                outcome = "PASS"
                correct_refusals += 1
                refused_by_omission += 1
            elif _was_grounded_away(actual_claim):
                outcome = "PASS"
                correct_refusals += 1
                refused_by_grounding += 1
            elif actual_claim.label in _REFUSAL_LABELS:
                outcome = "PASS"
                correct_refusals += 1
                refused_by_label += 1
            else:
                outcome = "FAIL"
        else:
            positive_total += 1
            if actual_claim is None:
                outcome = "POSITIVE_MISS"
            elif _was_grounded_away(actual_claim):
                outcome = "FALSE_REJECTION"
                false_rejections += 1
            elif actual_claim.label == row.expected_label:
                outcome = "POSITIVE_HIT"
                positive_hits += 1
            else:
                outcome = "POSITIVE_MISS"

        per_row[row.id] = RowOutcome(
            expected_id=row.id,
            outcome=outcome,
            expected_label=row.expected_label,
            actual_label=actual_label,
            actual_claim_summary=actual_claim_summary,
            actual_grounding_status=actual_grounding_status,
        )

    refusal_rate = correct_refusals / total_negatives if total_negatives else 0.0
    false_rejection_rate = false_rejections / positive_total if positive_total else 0.0

    refusal_rate_valid = positive_hits >= positive_hit_floor
    invalid_reason = (
        None
        if refusal_rate_valid
        else f"positive hits {positive_hits} below floor {positive_hit_floor}"
    )

    return EvalReport(
        correct_refusals=correct_refusals,
        total_negatives=total_negatives,
        refusal_rate=refusal_rate,
        positive_hits=positive_hits,
        positive_total=positive_total,
        per_row=per_row,
        refused_by_label=refused_by_label,
        refused_by_omission=refused_by_omission,
        refused_by_grounding=refused_by_grounding,
        false_rejections=false_rejections,
        false_rejection_rate=false_rejection_rate,
        positive_hit_floor=positive_hit_floor,
        refusal_rate_valid=refusal_rate_valid,
        invalid_reason=invalid_reason,
    )
