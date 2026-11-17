"""Response schema of the step 4 table checker (decisions.md "Pre-registration: step 4 - table checker for table
claims (text only), Vertex, 3 runs - 2026-11-15", ruling 2).

Kept in its own file: this file and table_check_system.md are the two inputs of the checker hash
(eval.step4.table_check.checker_hash). Neither is hashed into the flag-off prompt version.

Default Pydantic config on purpose: NO ConfigDict(extra="forbid"). Gemini rejects additionalProperties:false in a
response schema (docs/decisions.md, "Two-layer Pydantic schema", 2026-08-06). Field order is part of the contract:
the model fills the fields in this order.
"""
from typing import Literal

from pydantic import BaseModel

Answer = Literal["backed", "not_backed", "no_row", "not_a_table_piece"]


class TableCell(BaseModel):
    table: int
    row_label: str
    column_label: str
    value: str


class PieceAnswer(BaseModel):
    piece_id: int
    answer: Answer
    cells: list[TableCell]


class TableCheckResponse(BaseModel):
    pieces: list[PieceAnswer]
