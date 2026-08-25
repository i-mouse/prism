"""Typed block output for the paper-scoped chat agent.

The agent's answer is a sequence of blocks streamed to the client over SSE.
TextBlock is prose; ClaimReferenceBlock is a structured citation into a
paper_claims row, carrying enough data (claim_summary, display_label) for
the frontend to render without a Postgres round-trip.
"""
from typing import Literal, Union

from pydantic import BaseModel


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str


class ClaimReferenceBlock(BaseModel):
    type: Literal["claim_reference"] = "claim_reference"
    claim_id: str
    claim_summary: str
    display_label: Literal["supported", "partially_supported", "not_supported"]


Block = Union[TextBlock, ClaimReferenceBlock]


def block_to_sse(block: Block) -> str:
    """Serializes a block to a single SSE frame (including the trailing blank line)."""
    return f"data: {block.model_dump_json()}\n\n"
