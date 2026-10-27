"""Response schemas for the scope lister and the scope checker.

Kept out of schemas.py on purpose: schemas.py is hashed into the flag-off prompt
version, and these schemas only matter when the scope check is on (this file is
hashed only then, see extraction/prompt_version.py).

Default Pydantic config on purpose: NO ConfigDict(extra="forbid"). Gemini rejects
additionalProperties:false in a response schema (docs/decisions.md, "Two-layer
Pydantic schema", 2026-08-06). Field order is part of the contract: the model
fills the fields in this order.
"""
from typing import Literal

from pydantic import BaseModel


class ScopeItem(BaseModel):
    text: str
    kind: Literal["count", "quantifier", "named_set", "plural", "pair"]


class ScopeListResponse(BaseModel):
    items: list[ScopeItem]


class ScopeCheckItem(BaseModel):
    item: str
    reported: list[str]
    status: Literal["matches", "contradicted", "not_reported"]
    contradicting_quote: str | None


class ScopeCheckResponse(BaseModel):
    items: list[ScopeCheckItem]
