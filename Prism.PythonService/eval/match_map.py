"""Human-adjudicated match map for the eval golden set.

The LLM-as-judge matcher (eval/matcher.py) decides, at run time, which
actual claim corresponds to which golden row - a live judgment call that can
be wrong and that nothing currently checks. match_map.json is the place a
human records the *correct* answer for each golden row once, so that answer
can be checked against future runs instead of trusted blindly forever.

This module owns the schema, fingerprinting, and load-time validation. It
does not decide any entry - eval/generate_match_map.py emits an all-null
skeleton, and a human fills it in by hand.
"""
import hashlib
import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

SCHEMA_VERSION = 1


class MatchMapMetadata(BaseModel):
    prompt_hash: Optional[str] = None
    fixture_file: Optional[str] = None
    schema_version: int = SCHEMA_VERSION


class MatchMapSuggestion(BaseModel):
    """A machine-generated candidate for a row's adjudication - never an
    adjudication itself. Written by eval/suggest_match_map.py, read only by
    a human deciding whether to accept it. Nothing in this module or in
    matrix_runner.py's coverage gate reads this field - see
    MatchMapRow.is_adjudicated below, which deliberately does not
    reference it."""

    claim_fingerprint: str
    score: float
    claim_text_snippet: str


class MatchMapRow(BaseModel):
    """One golden row's adjudication. All-null means not yet adjudicated.

    Resolution order at runtime is fingerprint first, persisted_claim_id as
    fallback - claim_fingerprint survives a re-extraction that regenerates
    claim ids (paper_claims.id is a fresh uuid4 on every extraction run, so
    persisted_claim_id alone would silently break on every re-ingest).
    """

    persisted_claim_id: Optional[str] = None
    claim_fingerprint: Optional[str] = None
    decided_by: Optional[str] = None
    decided_on: Optional[str] = None
    reason: Optional[str] = None

    # A human-confirmed genuine omission: the paper has no claim matching this
    # golden row, so there is no fingerprint or claim id to record. Counts as
    # adjudicated; decided_by alone never does - see is_adjudicated.
    confirmed_no_match: bool = False

    # A suggestion for a human to review, not a decision. Deliberately
    # excluded from is_adjudicated: a row with only a `suggested` value and
    # nothing else must still count as coverage gap. Accepting this exact
    # temptation is the one thing this field must never be allowed to do -
    # see eval/suggest_match_map.py's module docstring.
    suggested: Optional[MatchMapSuggestion] = None

    @property
    def is_adjudicated(self) -> bool:
        return (
            self.persisted_claim_id is not None
            or self.claim_fingerprint is not None
            or self.confirmed_no_match is True
        )


class MatchMap(BaseModel):
    metadata: MatchMapMetadata
    rows: dict[str, MatchMapRow]

    @property
    def coverage_count(self) -> int:
        return sum(1 for row in self.rows.values() if row.is_adjudicated)


def normalize_claim_text(text: str) -> str:
    """Lowercase, collapse internal whitespace, strip - the exact
    normalization claim_fingerprint is computed over, so two callers hashing
    the same logical claim text always agree regardless of incidental
    whitespace differences."""
    return " ".join(text.lower().split())


def fingerprint_claim_text(text: str) -> str:
    """SHA-256 hex digest of the normalized claim text."""
    return hashlib.sha256(normalize_claim_text(text).encode("utf-8")).hexdigest()


def load_match_map(path: str | Path, golden_ids: set[str]) -> MatchMap:
    """Loads and validates match_map.json against the current golden set.

    Validation: every id in golden_ids must appear in rows exactly once (it
    can only appear once - rows is a dict keyed by id), and rows must
    contain no id outside golden_ids. Either violation raises ValueError
    with a message naming the offending ids, so a stale or hand-edited map
    fails loudly instead of silently scoring a mismatched set of rows.
    """
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    match_map = MatchMap.model_validate(raw)

    map_ids = set(match_map.rows.keys())
    missing = golden_ids - map_ids
    unknown = map_ids - golden_ids

    if missing or unknown:
        problems = []
        if missing:
            problems.append(f"missing golden row ids: {sorted(missing)}")
        if unknown:
            problems.append(f"unknown row ids not in the golden set: {sorted(unknown)}")
        raise ValueError(f"{path}: match map does not match the current golden set - {'; '.join(problems)}")

    return match_map
