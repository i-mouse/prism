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
    """One claim extracted by the engine."""

    index: int
    label: Literal["supported", "partially_supported", "not_supported"]
    claim_summary: str = ""


class Match(BaseModel):
    """Pairing of an expected row to an actual claim, produced by the LLM matcher."""

    expected_id: str
    actual_index: Optional[int] = None


class RowOutcome(BaseModel):
    """Per-row scoring result."""

    expected_id: str
    outcome: Literal["PASS", "FAIL", "POSITIVE_HIT", "POSITIVE_MISS"]
    expected_label: str
    actual_label: Optional[str] = None


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
    positive_hit_floor: int
    refusal_rate_valid: bool
    invalid_reason: Optional[str] = None
