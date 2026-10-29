"""Cell parser for Auditor v2 table cells (decisions.md 2026-10-28, "Cell parser").

Plain code, stdlib only. Turns a table cell string into a ParsedCell and
compares two parsed cells numerically. Used by the T1 scorer (and later T2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# Characters that stand for "minus" before a digit.
_SIGN_MINUS = ("-", "−", "–")
# Cells that mean "no value" when they are the whole cell.
_MISSING_DASHES = {"-", "—", "–", "−"}
_MISSING_WORDS = {"n/a", "oom"}
# Trailing footnote markers that are recorded and stripped.
_MARKER_CHARS = "*†‡"

_NUM = (
    r"(?P<{p}sign>[+\-−–])?"
    r"(?P<{p}int>\d{{1,3}}(?:,\d{{3}})+|\d*)"
    r"(?:\.(?P<{p}frac>\d+))?"
)
_NUM_A = _NUM.format(p="a_")
_NUM_B = _NUM.format(p="b_")

_PAIR_RE = re.compile(rf"^{_NUM_A}\s*/\s*{_NUM_B}$")
_SD_RE = re.compile(rf"^{_NUM_A}\s*(?:\+-|\+/-|±)\s*{_NUM_B}$")
_NUMBER_RE = re.compile(rf"^{_NUM_A}$")
_BOLD_RE = re.compile(r"^\*\*(.+)\*\*$|^<(?:b|strong)>(.+)</(?:b|strong)>$", re.S)


@dataclass(frozen=True)
class ParsedCell:
    kind: str  # "number" | "pair" | "missing" | "text"
    value: Optional[Decimal] = None
    sd: Optional[Decimal] = None
    pair: Optional[tuple] = None
    unit: Optional[str] = None
    markers: tuple = ()
    bold: bool = False
    raw: str = ""


def _to_decimal(sign, integer, frac) -> Optional[Decimal]:
    integer = (integer or "").replace(",", "")
    if not integer and not frac:
        return None
    neg = sign in _SIGN_MINUS
    number = Decimal(f"{integer or '0'}.{frac}" if frac else (integer or "0"))
    return -number if neg else number


def _decimal_from(match, prefix: str) -> Optional[Decimal]:
    return _to_decimal(
        match.group(f"{prefix}sign"),
        match.group(f"{prefix}int"),
        match.group(f"{prefix}frac"),
    )


def parse_cell(text) -> ParsedCell:
    raw = text if isinstance(text, str) else ""
    s = raw.replace(" ", " ").strip()

    bold = False
    m = _BOLD_RE.match(s)
    if m:
        s = (m.group(1) or m.group(2)).strip()
        bold = True

    markers = []
    while s and s[-1] in _MARKER_CHARS:
        markers.append(s[-1])
        s = s[:-1].rstrip()
    markers.reverse()

    if s == "" or s in _MISSING_DASHES or s.casefold() in _MISSING_WORDS:
        return ParsedCell("missing", markers=tuple(markers), bold=bold, raw=raw)

    unit = None
    if s.endswith("%"):
        unit = "%"
        s = s[:-1].rstrip()

    m = _PAIR_RE.match(s)
    if m:
        a, b = _decimal_from(m, "a_"), _decimal_from(m, "b_")
        if a is not None and b is not None:
            return ParsedCell(
                "pair", pair=(a, b), unit=unit, markers=tuple(markers), bold=bold, raw=raw
            )

    m = _SD_RE.match(s)
    if m:
        a, b = _decimal_from(m, "a_"), _decimal_from(m, "b_")
        if a is not None and b is not None:
            return ParsedCell(
                "number", value=a, sd=abs(b), unit=unit, markers=tuple(markers), bold=bold, raw=raw
            )

    m = _NUMBER_RE.match(s)
    if m:
        a = _decimal_from(m, "a_")
        if a is not None:
            return ParsedCell(
                "number", value=a, unit=unit, markers=tuple(markers), bold=bold, raw=raw
            )

    return ParsedCell("text", markers=tuple(markers), bold=bold, raw=raw)


def values_equal(a: ParsedCell, b: ParsedCell, with_sd: bool = False) -> bool:
    """Numeric equality of two parsed cells. SD is ignored unless with_sd."""
    if a.kind != b.kind:
        return False
    if a.kind == "missing":
        return True
    if a.kind == "number":
        if a.value != b.value:
            return False
        return a.sd == b.sd if with_sd else True
    if a.kind == "pair":
        return a.pair == b.pair
    return a.raw.strip() == b.raw.strip()
