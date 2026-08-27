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


class ActualClaim(BaseModel):
    """One claim extracted by the engine.

    missing/grounding_status default to the pre-Slice-2.8 blind spot
    (False / None) so fixtures dumped before these columns were added
    to the SELECT still validate - they just can't contribute to
    false_rejection_rate, which is the whole point of that metric.
    """

    index: int
    label: Literal["supported", "partially_supported", "not_supported"]
    claim_summary: str = ""
    missing: bool = False
    grounding_status: Optional[str] = None


class Match(BaseModel):
    """Pairing of an expected row to an actual claim, produced by the LLM matcher."""

    expected_id: str
    actual_index: Optional[int] = None


class RowOutcome(BaseModel):
    """Per-row scoring result."""

    expected_id: str
    outcome: Literal["PASS", "FAIL", "POSITIVE_HIT", "POSITIVE_MISS", "FALSE_REJECTION"]
    expected_label: str
    actual_label: Optional[str] = None
    actual_claim_summary: Optional[str] = None
    actual_grounding_status: Optional[str] = None


class EvalReport(BaseModel):
    """Aggregated scoring result across all expected rows."""

    correct_refusals: int
    total_negatives: int
    refusal_rate: float
    positive_hits: int
    positive_total: int
    per_row: dict[str, RowOutcome]

    refused_by_label: int
    refused_by_omission: int
    refused_by_grounding: int
    false_rejections: int
    false_rejection_rate: float
    positive_hit_floor: int
    refusal_rate_valid: bool
    invalid_reason: Optional[str] = None
