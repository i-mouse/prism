"""Pydantic schemas for the scoped auditor (AUDIT_MODE=scoped, Experiment 1).

Kept out of schemas.py on purpose: schemas.py is hashed into the legacy prompt
version (prompt_version.EXTRA_HASHED_FILES), and the legacy hash must not move.
This file is hashed into the separate scoped prompt version instead.

Only the inventory and scope steps use response_schema. The audit step that
reads the evidence and sets the verdict is free text.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

InventoryKind = Literal["model", "dataset", "task", "baseline", "setting"]
ScopeBasis = Literal["named", "implied"]

MAX_SCOPE_ITEMS = 12


class InventoryItem(BaseModel):
    id: str = Field(..., description="Short unique id such as I1, I2, ... in order of appearance")
    name: str = Field(..., description="The item's name exactly as the paper writes it. A name only: no numbers from results, no verdict-like words.")
    kind: InventoryKind = Field(..., description="model, dataset, task, baseline or setting")
    group: Optional[str] = Field(None, description="The paper's own category for this item, or null")


class PaperInventory(BaseModel):
    items: list[InventoryItem] = Field(..., description="Every model, dataset, task, baseline and setting the paper uses or compares")


class ScopeItem(BaseModel):
    scope_id: str = Field(..., description="S1, S2, ... in order")
    inventory_id: Optional[str] = Field(None, description="The inventory item id this covers, or null if the claim names something not in the inventory")
    label: str = Field(..., description="Name of the covered item")
    kind: InventoryKind = Field(..., description="model, dataset, task, baseline or setting")
    basis: ScopeBasis = Field(..., description="named: the claim names it. implied: the claim's wording covers it by category.")
    why: str = Field(..., description="At most 25 words on why the claim covers this item")


class ClaimScope(BaseModel):
    items: list[ScopeItem] = Field(..., description="The inventory items the claim covers")
