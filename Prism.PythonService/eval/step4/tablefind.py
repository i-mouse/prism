"""Pure logic for the table-finding check before step 4 (decisions.md "Pre-registration: table-finding check before
step 4 (code only, INR 0) - 2026-11-14" and its "Reading notes" entry). No I/O, no LLM, no network. The rule, the
12,000-character cap and the 90% threshold are frozen by those entries and are not tuned after a run.

- Caption line for table N: optional spaces or tabs, "Table", spaces, N, optional spaces, then ":", "." or "|".
  Case-sensitive. Found = exactly one such line.
- Block: from the caption line up to (not including) the next Table / Figure / Fig. caption line (any number), or a
  line whose stripped text casefolds to "references", or 12,000 characters from the caption start.
- Values: whitespace-split tokens, each given to the shared cell parser (eval.auditor_v2.cell_parser.parse_cell)
  unchanged. A number gives its value, a pair gives both members, SD is ignored.
- Usable = caption found, every breaking CELL pin's value is in the block, and >= 90% of the reference table's
  distinct values are in the block. Structural breaking pins are reported, never gated.
- Row ready = all its tables usable. PASS = at least 4 of the 5 rows ready.

Nothing built here holds paper text, cell values or labels: see build_payload / check_payload.
"""
import re
import unicodedata
from decimal import Decimal

from eval.auditor_v2.cell_parser import ParsedCell, parse_cell

BLOCK_CAP_CHARS = 12_000
VALUE_MIN_PERCENT = 90          # "90% as in T1"
PASS_MIN_ROWS = 4
NOT_CHECKABLE = "not checkable"

# --- fixed targets (the 6 tables of the 5 rows) -----------------------------------------------------------------
TABLE_NUMBERS: dict[str, int] = {"P1-T4": 4, "P3-T9": 9, "P4-T1": 1, "P4-T2": 2, "P4-T9": 9, "P11-T3": 3}
ROW_TABLES: dict[str, tuple[str, ...]] = {
    "P1-R1": ("P1-T4",),
    "P3-R2": ("P3-T9",),
    "P4-R1": ("P4-T1", "P4-T2"),
    "P4-R2": ("P4-T9",),
    "P11-R2": ("P11-T3",),
}
# The breaking pin ids the entry's reading is built on; the CLI preflight stops if the pins file differs.
EXPECTED_BREAKING: dict[str, frozenset[str]] = {
    "P1-T4": frozenset({"P1-T4-01"}),
    "P3-T9": frozenset({"P3-T9-01", "P3-T9-02"}),
    "P4-T1": frozenset({"P4-T1-01"}),
    "P4-T2": frozenset({"P4-T2-01", "P4-T2-02"}),
    "P4-T9": frozenset({"P4-T9-03", "P4-T9-04", "P4-T9-05", "P4-T9-06", "P4-T9-S1"}),
    "P11-T3": frozenset({"P11-T3-S1"}),
}

_END_CAPTION_RE = re.compile(r"^[ \t]*(?:Table|Figure|Fig\.)[ \t]*\d+[ \t]*[:.|]", re.MULTILINE)
_MENTION_RE = re.compile(r"\bTable[ \t]+(\d+)(?![0-9A-Za-z])")


# --- caption lines and blocks --------------------------------------------------------------------------------

def _caption_re(n: int) -> re.Pattern[str]:
    return re.compile(rf"^[ \t]*Table[ \t]+{n}[ \t]*[:.|]", re.MULTILINE)


def find_caption_lines(text: str, n: int) -> list[int]:
    """Character offsets of the start of every caption line for table n."""
    return [m.start() for m in _caption_re(n).finditer(text)]


def _references_line_offset(text: str, start: int, limit: int) -> int | None:
    """Offset of the first line at or after `start`, beginning before `limit`, whose stripped text casefolds to
    "references"; None if there is none."""
    offset = start
    while offset < limit and offset < len(text):
        newline = text.find("\n", offset)
        end = len(text) if newline == -1 else newline
        if text[offset:end].strip().casefold() == "references":
            return offset
        if newline == -1:
            break
        offset = newline + 1
    return None


def cut_block(text: str, caption_start: int) -> tuple[str, bool]:
    """(block, cap_hit). The block starts at caption_start and stops before the earliest of: the next
    Table/Figure/Fig. caption line, a References line, caption_start + 12,000. cap_hit is True only when the cap cut
    the block (a natural end at or before the cap, or the end of the text, is not a cap hit)."""
    cap_end = caption_start + BLOCK_CAP_CHARS
    ends: list[int] = []
    newline = text.find("\n", caption_start)
    if newline != -1:
        scan_from = newline + 1
        next_caption = _END_CAPTION_RE.search(text, scan_from)
        if next_caption is not None:
            ends.append(next_caption.start())
        references = _references_line_offset(text, scan_from, cap_end)
        if references is not None:
            ends.append(references)
    natural_end = min(ends) if ends else None
    if natural_end is not None and natural_end <= cap_end:
        return text[caption_start:natural_end], False
    return text[caption_start:cap_end], len(text) > cap_end


# --- values ---------------------------------------------------------------------------------------------------

def _numbers(parsed: ParsedCell) -> list[Decimal]:
    if parsed.kind == "number" and parsed.value is not None:
        return [parsed.value]
    if parsed.kind == "pair" and parsed.pair is not None:
        return [parsed.pair[0], parsed.pair[1]]
    return []


def values_in_block(block: str) -> set[Decimal]:
    """Whitespace-split the block; every token goes to parse_cell unchanged (brackets and commas are not stripped)."""
    out: set[Decimal] = set()
    for token in block.split():
        out.update(_numbers(parse_cell(token)))
    return out


def ref_values(ref: dict) -> set[Decimal]:
    """The reference table's distinct values: parse_cell over the whole text of every cell (so "a +- b" gives a;
    "a / b" gives a and b)."""
    out: set[Decimal] = set()
    for cell in ref.get("cells", []):
        out.update(_numbers(parse_cell(cell.get("text"))))
    return out


def pin_values(pin: dict) -> set[Decimal]:
    """The value(s) a cell pin asks for; empty if the pin value is not numeric."""
    return set(_numbers(parse_cell(pin.get("value"))))


# --- labels (reported only) ----------------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """NFKC, casefold, all whitespace removed."""
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def ref_labels(ref: dict) -> set[str]:
    """Normalised, non-empty texts of the reference header, row-header and section cells."""
    out: set[str] = set()
    for cell in ref.get("cells", []):
        if cell.get("is_column_header") or cell.get("is_row_header") or cell.get("is_section_row"):
            norm = normalize_text(cell.get("text") or "")
            if norm:
                out.add(norm)
    return out


# --- one table ------------------------------------------------------------------------------------------------

def _percent(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _structural_report(pin: dict, norm_block: str, found: bool) -> bool | str:
    """A caption pin: are all its fragments in the block (y/n). Any other structural pin cannot be read from a
    text block (a missing row is not visible in text)."""
    fragments = pin.get("fragments")
    if pin.get("kind") == "caption" and isinstance(fragments, list) and fragments:
        return found and all(normalize_text(str(f)) in norm_block for f in fragments)
    return NOT_CHECKABLE


def score_table(*, text: str, n: int, ref: dict, pins: list[dict]) -> dict:
    """Scores table n of one paper's text against its reference table and its T1 pins. Returns ids, counts, ints,
    floats and bools only (plus the fixed word "not checkable")."""
    caption_lines = find_caption_lines(text, n)
    found = len(caption_lines) == 1
    block, cap_hit = cut_block(text, caption_lines[0]) if found else ("", False)

    block_values = values_in_block(block)
    wanted = ref_values(ref)
    matched = len(wanted & block_values)
    value_test = len(wanted) > 0 and matched * 100 >= len(wanted) * VALUE_MIN_PERCENT

    norm_block = normalize_text(block)
    labels = ref_labels(ref)
    label_matched = sum(1 for label in labels if label in norm_block)

    cell_pins: dict[str, bool] = {}
    structural: dict[str, bool | str] = {}
    for pin in sorted(pins, key=lambda p: str(p["id"])):
        if not pin.get("breaking"):
            continue
        pin_id = str(pin["id"])
        if pin.get("kind") == "cell":
            needed = pin_values(pin)
            cell_pins[pin_id] = bool(needed) and needed <= block_values
        else:
            structural[pin_id] = _structural_report(pin, norm_block, found)

    usable = found and all(cell_pins.values()) and value_test
    return {
        "caption_lines": len(caption_lines),
        "found": found,
        "breaking_cell_pins": cell_pins,
        "structural_breaking": structural,
        "ref_distinct_total": len(wanted),
        "ref_matched": matched,
        "ref_pct": _percent(matched, len(wanted)),
        "value_test": value_test,
        "label_total": len(labels),
        "label_matched": label_matched,
        "label_pct": _percent(label_matched, len(labels)),
        "block_chars": len(block),
        "est_tokens": len(block) // 4,       # ESTIMATED: chars / 4
        "cap_hit": cap_hit,
        "usable": usable,
    }


def all_tables_view(text: str) -> dict[int, bool]:
    """Every table number mentioned ("Table", spaces, digits; not followed by a letter or digit) mapped to whether
    exactly one caption line exists for it."""
    numbers = {int(m.group(1)) for m in _MENTION_RE.finditer(text)}
    return {n: len(find_caption_lines(text, n)) == 1 for n in sorted(numbers)}


# --- rows and verdict -----------------------------------------------------------------------------------------

def rows_ready(usable_by_table: dict[str, bool]) -> dict[str, bool]:
    return {row: all(usable_by_table[t] for t in tables) for row, tables in ROW_TABLES.items()}


def verdict(rows: dict[str, bool]) -> str:
    """PASS if at least 4 rows are ready, else FAIL."""
    return "PASS" if sum(1 for ready in rows.values() if ready) >= PASS_MIN_ROWS else "FAIL"


# --- output (ids, counts, bools only) -------------------------------------------------------------------------

KNOWN_KEYS = frozenset({
    "verdict", "rows_ready", "rows_ready_count", "rows_total", "row_tables", "tables", "all_tables",
    "all_tables_counts", "mentioned", "captions_found_once", "breaking_pin_ids", "rules", "cap_chars",
    "value_min_percent", "pass_min_rows", "paper_id", "caption_number", "caption_lines", "found",
    "breaking_cell_pins", "structural_breaking", "ref_distinct_total", "ref_matched", "ref_pct", "value_test",
    "label_total", "label_matched", "label_pct", "block_chars", "est_tokens", "cap_hit", "usable",
})
_ID_RE = re.compile(r"^(?:\d{4}\.\d{4,5}v\d+|P\d+-R\d+|P\d+-T\d+(?:-S?\d+)?|\d+)$")
_WORDS = frozenset({"PASS", "FAIL", NOT_CHECKABLE})


def build_payload(
    *, scored: dict[str, dict], papers: dict[str, str], all_tables: dict[str, dict[int, bool]],
) -> dict:
    """scored: table id -> score_table result; papers: table id -> paper id; all_tables: paper id -> all_tables_view."""
    ready = rows_ready({tid: bool(res["usable"]) for tid, res in scored.items()})
    tables = {
        tid: {**res, "paper_id": papers[tid], "caption_number": TABLE_NUMBERS[tid]} for tid, res in scored.items()
    }
    return {
        "verdict": verdict(ready),
        "rows_ready": dict(ready),
        "rows_ready_count": sum(1 for v in ready.values() if v),
        "rows_total": len(ready),
        "row_tables": {row: list(tables_) for row, tables_ in ROW_TABLES.items()},
        "tables": tables,
        "all_tables": {pid: {str(n): ok for n, ok in view.items()} for pid, view in all_tables.items()},
        "all_tables_counts": {
            pid: {"mentioned": len(view), "captions_found_once": sum(1 for ok in view.values() if ok)}
            for pid, view in all_tables.items()
        },
        "breaking_pin_ids": {tid: sorted(ids) for tid, ids in EXPECTED_BREAKING.items()},
        "rules": {
            "cap_chars": BLOCK_CAP_CHARS, "value_min_percent": VALUE_MIN_PERCENT, "pass_min_rows": PASS_MIN_ROWS,
        },
    }


def check_payload(obj: object, path: str = "$") -> None:
    """Raises ValueError unless every key is a known key or an id, every string is an id or one of the fixed words,
    and every other value is a bool, int, float, None, list, or dict. Messages carry the path, never the value."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str) or not (key in KNOWN_KEYS or _ID_RE.match(key)):
                raise ValueError(f"{path}: a key is neither a known key nor an id")
            check_payload(value, f"{path}.{key}")
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            check_payload(item, f"{path}[{i}]")
    elif isinstance(obj, str):
        if obj not in _WORDS and not _ID_RE.match(obj):
            raise ValueError(f"{path}: a string value is neither an id nor a fixed word")
    elif obj is not None and not isinstance(obj, (bool, int, float)):
        raise ValueError(f"{path}: type {type(obj).__name__} is not allowed")


def _yn(flag: bool) -> str:
    return "yes" if flag else "no"


def render_md(payload: dict) -> str:
    """Markdown from the payload only, so it cannot hold anything the payload does not."""
    rules = payload["rules"]
    lines = [
        "# Table-finding check before step 4 (code only, INR 0) - result",
        "",
        f"Verdict: **{payload['verdict']}** - {payload['rows_ready_count']} of {payload['rows_total']} rows ready "
        f"(PASS needs >= {rules['pass_min_rows']}).",
        f"Rule: block cap {rules['cap_chars']} chars; a table needs >= {rules['value_min_percent']}% of the reference "
        "table's distinct values in the block. Ids, counts and y/n only; no paper text.",
        "",
        "## Rows",
        "",
        "| row | tables | ready |",
        "|---|---|---|",
    ]
    for row, ready in payload["rows_ready"].items():
        lines.append(f"| {row} | {', '.join(payload['row_tables'][row])} | {_yn(ready)} |")

    lines += [
        "", "## Tables", "",
        "| table | paper | caption lines | found | breaking cell pins present | ref values matched | pct | "
        "value test | usable | block chars | est. tokens (ESTIMATED) | cap hit |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for tid, res in payload["tables"].items():
        pins = res["breaking_cell_pins"]
        lines.append(
            f"| {tid} | {res['paper_id']} | {res['caption_lines']} | {_yn(res['found'])} | "
            f"{sum(1 for ok in pins.values() if ok)}/{len(pins)} | {res['ref_matched']}/{res['ref_distinct_total']} | "
            f"{res['ref_pct']} | {_yn(res['value_test'])} | {_yn(res['usable'])} | {res['block_chars']} | "
            f"{res['est_tokens']} | {_yn(res['cap_hit'])} |"
        )

    lines += ["", "## Breaking cell pins", "", "| table | pin | value in block |", "|---|---|---|"]
    for tid, res in payload["tables"].items():
        for pin_id, ok in res["breaking_cell_pins"].items():
            lines.append(f"| {tid} | {pin_id} | {_yn(ok)} |")

    lines += [
        "", "## Structural breaking pins (reported, not gated)", "", "| table | pin | reported |", "|---|---|---|",
    ]
    for tid, res in payload["tables"].items():
        for pin_id, reported in res["structural_breaking"].items():
            shown = reported if isinstance(reported, str) else _yn(reported)
            lines.append(f"| {tid} | {pin_id} | {shown} |")

    lines += [
        "", "## Label coverage (reported, not gated)", "", "| table | labels matched | pct |", "|---|---|---|",
    ]
    for tid, res in payload["tables"].items():
        lines.append(f"| {tid} | {res['label_matched']}/{res['label_total']} | {res['label_pct']} |")

    lines += [
        "", "## All-tables view (12 dev papers; reported, not gated)", "",
        "| paper | tables mentioned | caption found exactly once | numbers not found exactly once |",
        "|---|---|---|---|",
    ]
    for pid, view in payload["all_tables"].items():
        counts = payload["all_tables_counts"][pid]
        missing = sorted((int(n) for n, ok in view.items() if not ok))
        lines.append(
            f"| {pid} | {counts['mentioned']} | {counts['captions_found_once']} | "
            f"{', '.join(str(n) for n in missing) or '-'} |"
        )
    return "\n".join(lines) + "\n"
