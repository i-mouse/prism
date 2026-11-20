"""Pydantic response_schema for test B's single gemini-4-carbon call per paper,
plus prompt_hash(), which ties a run to the exact prompt+schema bytes used.
"""
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

PROMPT_PATH = Path(__file__).parent / "one_call_prompt.md"
SCHEMA_PATH = Path(__file__)


class OneCallClaim(BaseModel):
    claim_quote: str
    location: str
    evidence: str
    verdict: Literal["supported", "partially_supported", "not_supported"]
    reason: str


class OneCallResult(BaseModel):
    claims: list[OneCallClaim]


def prompt_hash(prompt_path: Path = PROMPT_PATH, schema_path: Path = SCHEMA_PATH) -> str:
    """First 12 hex chars of sha256(prompt file bytes + schema file bytes)."""
    data = prompt_path.read_bytes() + schema_path.read_bytes()
    return hashlib.sha256(data).hexdigest()[:12]
