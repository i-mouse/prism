"""Pydantic schemas for the eval harness scorer.

expected_label/label values are lowercase snake_case, matching what
Postgres stores and what matrix_eval.json uses.
"""
from typing import Literal, Optional
from pydantic import BaseModel


class ExpectedRow(BaseModel):
    """One row from docs/evals/matrix_eval.json."""

    id: str
    expected_label: Literal["supported", "partially_supported", "not_supported"]
    grounding_negative: bool
    claim_summary: str = ""
    claim_text_verbatim: str = ""


class ActualClaim(BaseModel):
    """One claim extracted by the engine.

    missing/grounding_status default to the pre-Slice-2.8 blind spot
    (False / None) so fixtures dumped before these columns were added
    to the SELECT still validate - they just can't contribute to
    false_rejection_rate, which is the whole point of that metric.
    claim_text_verbatim defaults to "" for the same reason - fixtures
    dumped before this field existed still validate.
    """

    index: int
    label: Literal["supported", "partially_supported", "not_supported"]
    claim_summary: str = ""
    claim_text_verbatim: str = ""
    missing: bool = False
    grounding_status: Optional[str] = None


class Match(BaseModel):
    """Pairing of an expected row to an actual claim, produced by the LLM matcher."""

    expected_id: str
    actual_index: Optional[int] = None


# RowOutcome JSON shape, as written into logs/eval/matrix_*.json under
# papers[].report.per_row.<expected_id>:
#   expected_id              golden-set row id, e.g. "REACT-M13"
#   outcome                  REFUSED | WRONGLY_AFFIRMED | NOT_EXTRACTED | POSITIVE_HIT |
#                            POSITIVE_MISS | FALSE_REJECTION | SKIPPED
#   expected_label           golden-set label: supported | partially_supported | not_supported
#   expected_claim_text_verbatim  golden-set claim quote, from matrix_eval.json (may be "" if absent)
#   expected_claim_summary   golden-set short claim description
#   actual_label             engine's label for the matched claim, or null if no match
#   actual_claim_text_verbatim    matched claim's verbatim quote, or null if no match
#   actual_claim_summary     matched claim's short description, or null if no match
#   actual_grounding_status  matched claim's grounding verdict (Pass/Partial/Fail/Skipped), or null
# The two verbatim/summary pairs exist purely for human diagnosis - reading a
# WRONGLY_AFFIRMED row should not require cross-referencing matrix_eval.json
# and a separate DB query by hand.
#
# For a golden-negative row (grounding_negative or expected_label=="not_supported"):
#   REFUSED           a claim was emitted and the pipeline refused it, either by
#                      grounding rejection (checked first) or by label
#                      (not_supported/partially_supported). Counted toward
#                      correct_refusals.
#   WRONGLY_AFFIRMED   a claim was emitted, labeled 'supported', and grounding
#                      did not reject it. FAIL - not counted anywhere as a pass.
#   NOT_EXTRACTED      no claim was emitted for this row at all. This earns NO
#                      credit - an omission is not evidence of judgment, since
#                      the extractor has no way to know which golden rows are
#                      grounding-negative. Still counted in total_negatives.
class RowOutcome(BaseModel):
    """Per-row scoring result."""

    expected_id: str
    outcome: Literal[
        "REFUSED", "WRONGLY_AFFIRMED", "NOT_EXTRACTED", "POSITIVE_HIT", "POSITIVE_MISS", "FALSE_REJECTION", "SKIPPED"
    ]
    expected_label: str
    expected_claim_text_verbatim: Optional[str] = None
    expected_claim_summary: Optional[str] = None
    actual_label: Optional[str] = None
    actual_claim_text_verbatim: Optional[str] = None
    actual_claim_summary: Optional[str] = None
    actual_grounding_status: Optional[str] = None


class EvalReport(BaseModel):
    """Aggregated scoring result across all expected rows.

    correct_refusals = refused_by_label + refused_by_grounding only. Omission
    (not_extracted) is NOT credited: the extractor has no way to know which
    golden rows are grounding-negative, so an absent claim is an accident,
    not a refusal. not_extracted still counts toward total_negatives.
    """

    correct_refusals: int
    total_negatives: int
    refusal_rate: float
    positive_hits: int
    positive_total: int
    per_row: dict[str, RowOutcome]

    refused_by_label: int
    refused_by_grounding: int
    wrongly_affirmed: int
    not_extracted: int
    false_rejections: int
    false_rejection_rate: float
    positive_hit_floor: int
    refusal_rate_valid: bool
    invalid_reason: Optional[str] = None

    # strict_correct_refusals requires actual_claim.label == row.expected_label
    # exactly - no omission/grounding-rejection credit, unlike correct_refusals
    # above (the "family" tolerance: not_supported OR partially_supported).
    # Same denominator (total_negatives) so the two rates are comparable.
    strict_correct_refusals: int = 0
    strict_refusal_rate: float = 0.0

    # Claims the grounding pipeline could not evaluate (transient service
    # error, not a semantic verdict) - excluded from every denominator above,
    # not scored either way. See GroundingStatus.SKIPPED.
    skipped: int = 0
