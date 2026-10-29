"""Key paths and structural helpers for extracted tables (Auditor v2 T1).

Reads only the common table schema (plain dicts, see t1_score.py and
scratch/auditor_v2/t1env/run_extract.py). Same code for every extractor.
Stdlib only. Nothing here counts positions to find a value: rows and columns
are found by key path, or by key-column header label.

Rules (decisions.md 2026-10-28 "Key labels", plan rules c):
- Column path: texts of the header cells covering the column, top to bottom.
- Row path: section label (if any) + row-label cells.
- Label match: NFKC, casefold, whitespace collapse; marker-insensitive
  fallback (drop trailing * dagger double-dagger +) only when unique.
- Path match, tiered: 1 exact; 2 (only if none) unique trailing suffix
  (derived path has extra leading levels); 3 (only if none) marker-insensitive.
  A tier with more than one candidate is no match, no fall-through. A pin
  path longer than the derived path never matches.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from eval.auditor_v2.cell_parser import parse_cell, values_equal

MARKERS = "*†‡+"

_CAPTION_RE = re.compile(r"^\s*(?:table|tab)\s*\.?\s*(\d+)\b", re.IGNORECASE)


def normalize_label(text) -> str:
    s = unicodedata.normalize("NFKC", text if isinstance(text, str) else "")
    return " ".join(s.casefold().split())


def strip_markers(norm: str) -> str:
    return norm.rstrip(MARKERS + " ")


def caption_number(text) -> Optional[int]:
    m = _CAPTION_RE.match(unicodedata.normalize("NFKC", text or ""))
    return int(m.group(1)) if m else None


def _path_key(path, fallback: bool):
    norm = [normalize_label(p) for p in path]
    return tuple(strip_markers(p) for p in norm) if fallback else tuple(norm)


@dataclass
class Keys:
    n_rows: int = 0
    n_cols: int = 0
    header_rows: set = field(default_factory=set)
    section_rows: dict = field(default_factory=dict)  # row -> label
    data_rows: list = field(default_factory=list)
    label_cols: list = field(default_factory=list)
    row_paths: dict = field(default_factory=dict)  # data row -> path list
    col_paths: dict = field(default_factory=dict)  # col -> path list
    cover: dict = field(default_factory=dict)  # (row, col) -> cell index


def _cover(table) -> dict:
    cover = {}
    for i, cell in enumerate(table["cells"]):
        for dr in range(max(1, cell["row_span"])):
            for dc in range(max(1, cell["col_span"])):
                cover.setdefault((cell["row"] + dr, cell["col"] + dc), i)
    return cover


def _dedupe(seq):
    out = []
    for item in seq:
        if not out or out[-1] != item:
            out.append(item)
    return out


def derive_keys(table) -> Keys:
    cells = table["cells"]
    k = Keys(n_rows=table["n_rows"], n_cols=table["n_cols"], cover=_cover(table))
    text = lambda i: cells[i]["text"].strip()

    for cell in cells:
        if cell["is_column_header"]:
            for dr in range(max(1, cell["row_span"])):
                k.header_rows.add(cell["row"] + dr)

    # column paths
    for c in range(k.n_cols):
        covering = sorted(
            {k.cover[(r, c)] for r in k.header_rows if (r, c) in k.cover},
            key=lambda i: (cells[i]["row"], cells[i]["col"]),
        )
        k.col_paths[c] = _dedupe([text(i) for i in covering if text(i)])

    # section rows and data rows
    flagged_sections = {
        cell["row"] for cell in cells if cell["is_section_row"] and cell["row"] not in k.header_rows
    }
    for r in range(k.n_rows):
        if r in k.header_rows:
            continue
        covering = {k.cover[(r, c)] for c in range(k.n_cols) if (r, c) in k.cover}
        filled = [i for i in covering if text(i)]
        if r in flagged_sections and filled:
            k.section_rows[r] = text(sorted(filled, key=lambda i: cells[i]["col"])[0])
        elif (
            k.n_cols >= 2
            and len(filled) == 1
            and cells[filled[0]]["col"] == 0
            and cells[filled[0]]["row"] == r
        ):
            k.section_rows[r] = text(filled[0])
        elif filled:
            k.data_rows.append(r)

    # row-label cells
    flagged_row_headers = [
        i for i, cell in enumerate(cells)
        if cell["is_row_header"] and cell["row"] not in k.header_rows
    ]
    if flagged_row_headers:
        k.label_cols = sorted({cells[i]["col"] for i in flagged_row_headers})
        label_idx = set(flagged_row_headers)
    else:
        k.label_cols = _leading_text_columns(table, k)
        label_idx = None  # chosen per row below

    section = None
    for r in range(k.n_rows):
        if r in k.section_rows:
            section = k.section_rows[r]
            continue
        if r not in k.data_rows:
            continue
        if label_idx is not None:
            row_cells = {k.cover[(r, c)] for c in range(k.n_cols) if (r, c) in k.cover}
            chosen = [i for i in row_cells if i in label_idx]
        elif k.label_cols:
            chosen = [k.cover[(r, c)] for c in k.label_cols if (r, c) in k.cover]
        else:  # no text-prefix columns: leftmost non-empty cell of the row
            chosen = []
            for c in range(k.n_cols):
                i = k.cover.get((r, c))
                if i is not None and text(i):
                    chosen = [i]
                    break
        chosen = sorted(dict.fromkeys(chosen), key=lambda i: cells[i]["col"])
        labels = _dedupe([text(i) for i in chosen if text(i)])
        k.row_paths[r] = ([section] if section else []) + labels
    return k


def _leading_text_columns(table, k: Keys) -> list:
    """Leading columns whose non-empty body cells are all text (not number,
    pair or missing). Used as row-label columns when the extractor flags none."""
    cells = table["cells"]
    out = []
    for c in range(k.n_cols):
        seen = {k.cover[(r, c)] for r in k.data_rows if (r, c) in k.cover}
        filled = [cells[i]["text"] for i in seen if cells[i]["text"].strip()]
        if filled and all(parse_cell(t).kind == "text" for t in filled):
            out.append(c)
        else:
            break
    return out


def table_with_keys(table) -> dict:
    k = derive_keys(table)
    out = dict(table)
    out["row_keys"] = [{"row": r, "path": k.row_paths[r]} for r in sorted(k.row_paths)]
    out["col_keys"] = [{"col": c, "path": k.col_paths[c]} for c in sorted(k.col_paths)]
    return out


# ---------------------------------------------------------------- lookups

def _is_suffix(pin: tuple, derived: tuple) -> bool:
    """pin equals derived, or is a suffix of it (derived has extra leading
    levels such as a title row or a spanning group header). A pin longer
    than the derived path never matches."""
    n = len(pin)
    return 0 < n <= len(derived) and derived[len(derived) - n:] == pin


def _unique_match(paths: dict, wanted) -> list:
    """Indices whose path matches `wanted`, in tiers:
    1. exact (normalised) equality;
    2. only if tier 1 found none: unique trailing-suffix match;
    3. only if tiers 1-2 found none: marker-insensitive (equal or suffix).
    A tier with exactly one candidate wins; a tier with more than one
    candidate is no match and does not fall through to the next tier."""
    exact_pin = _path_key(wanted, False)
    exact = [i for i, p in paths.items() if _path_key(p, False) == exact_pin]
    if exact:
        return exact if len(exact) == 1 else []
    suffix = [i for i, p in paths.items() if _is_suffix(exact_pin, _path_key(p, False))]
    if suffix:
        return suffix if len(suffix) == 1 else []
    fb_pin = _path_key(wanted, True)
    fb = [i for i, p in paths.items() if _is_suffix(fb_pin, _path_key(p, True))]
    return fb if len(fb) == 1 else []


def rows_by_path(table, k: Keys, path) -> list:
    return _unique_match(k.row_paths, path)


def unique_row(table, k: Keys, path) -> Optional[int]:
    rows = rows_by_path(table, k, path)
    return rows[0] if len(rows) == 1 else None


def unique_col(table, k: Keys, path) -> Optional[int]:
    paths = {c: p for c, p in k.col_paths.items() if c not in k.label_cols and p}
    cols = _unique_match(paths, path)
    return cols[0] if len(cols) == 1 else None


def key_column(table, k: Keys, label) -> Optional[int]:
    """Column whose own (leaf) header label matches `label`, unique or None."""
    leaf = {c: [p[-1]] for c, p in k.col_paths.items() if p}
    cols = _unique_match(leaf, [label])
    return cols[0] if len(cols) == 1 else None


def cell_text(table, k: Keys, r: int, c: int) -> Optional[str]:
    i = k.cover.get((r, c))
    return None if i is None else table["cells"][i]["text"]


def rows_matching(table, k: Keys, match: dict) -> Optional[list]:
    """Data rows whose cells in the named columns (by header label) equal the
    given values (normalised). None if a named column cannot be found."""
    cols = {}
    for label in match:
        c = key_column(table, k, label)
        if c is None:
            return None
        cols[label] = c
    return [
        r for r in k.data_rows
        if all(
            normalize_label(cell_text(table, k, r, cols[label]) or "") == normalize_label(value)
            for label, value in match.items()
        )
    ]


def rows_by_key_columns(table, k: Keys, key_columns, values) -> Optional[int]:
    rows = rows_matching(table, k, dict(zip(key_columns, values)))
    return rows[0] if rows and len(rows) == 1 else None


def row_label(k: Keys, r: int) -> str:
    path = k.row_paths.get(r) or []
    return path[-1] if path else ""


def count_data_rows(k: Keys) -> int:
    return len(k.data_rows)


def tables_with_caption_number(tables, number: int) -> list:
    return [t for t in tables if t.get("caption_number") == number]


def evaluate_cell(table, k: Keys, pin) -> dict:
    """Check one cell pin. Returns {correct, got, reason}."""
    if pin.get("key_columns"):
        r = rows_by_key_columns(table, k, pin["key_columns"], pin["row_key_path"])
    else:
        r = unique_row(table, k, pin["row_key_path"])
    if r is None:
        return {"correct": False, "got": None, "reason": "row key path not found or ambiguous"}
    c = unique_col(table, k, pin["column_key_path"])
    if c is None:
        return {"correct": False, "got": None, "reason": "column key path not found or ambiguous"}
    got = cell_text(table, k, r, c)
    if got is None:
        return {"correct": False, "got": None, "reason": "no cell at row/column"}
    ok = values_equal(parse_cell(got), parse_cell(pin["value"]))
    return {"correct": ok, "got": got, "reason": "" if ok else "value differs"}
