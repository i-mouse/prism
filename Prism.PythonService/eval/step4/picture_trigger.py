"""CLI: the step 4 "picture trigger" report (decisions.md "Pre-registration: step 4 - table checker for table claims
(text only), Vertex, 3 runs - 2026-11-15", section "Picture trigger"). Report only; it decides the next entry, not
the step 4 result. Read-only, zero LLM calls, no network, no paper text. Nitin runs it after scoring.

For each target row (the miss rows minus the parked rows, taken from eval.score_a1 / eval.score_screen) and each of
the candidate's 3 dev folders, every cell the table checker quoted for the row's claim is compared with the T2-R
reference table of the same table number, for the rows that have reference tables (eval.step4.tablefind.ROW_TABLES).

A quoted cell is a LAYOUT MISREAD when its value exists in the reference table (shared parse_cell / values_equal,
numbers and pairs only) but no reference cell with that value sits in the quoted row and column. Labels match
loosely on purpose (NFKC, casefold, whitespace removed; a quoted label matches a level of the reference row / column
path when either contains the other), so only a clear row or column mix-up is flagged. A quoted value that is not
in the reference table at all is counted separately and is not a layout misread.

Trigger: at least one target row has a layout misread in >= 2 of the 3 runs.

Output: row ids, counts and y/n only - never cell values, labels or paper text.

Exit codes: 0 = report printed; 1 = bad arguments or a folder problem; 2 = the reference tables could not be loaded.

Usage (from Prism.PythonService):
  uv run python -m eval.step4.picture_trigger --dev-candidate <d1> --dev-candidate <d2> --dev-candidate <d3> [--json-out PATH]
"""
import argparse
import json
import sys
from pathlib import Path

from eval import score_a1, score_screen
from eval.auditor_v2 import table_keys
from eval.auditor_v2.cell_parser import parse_cell, values_equal
from eval.score_replay import (
    DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, resolve_adjudicated_rows,
)
from eval.step4 import tablefind

TRACE_KEY = "table_check"
NUMERIC_KINDS = ("number", "pair")


def target_rows() -> list[str]:
    parked = set(score_screen.PARKED_ROWS)
    return [rid for rid in score_a1.MISS_ROWS if rid not in parked]


def quoted_cells(claim: dict | None) -> list[dict]:
    """Every cell the checker quoted for the claim (all pieces); [] when the claim has no table-check trace."""
    trace = (claim or {}).get(TRACE_KEY)
    if not isinstance(trace, dict):
        return []
    return [
        cell for piece in trace.get("pieces") or [] if isinstance(piece, dict)
        for cell in piece.get("cells") or [] if isinstance(cell, dict)
    ]


def _label_matches(quoted: str, path: list[str]) -> bool:
    norm = tablefind.normalize_text(quoted or "")
    if not norm:
        return False
    levels = [tablefind.normalize_text(level) for level in path]
    levels = [level for level in levels if level]
    joined = "".join(levels)
    return any(norm in level or level in norm for level in levels) or (bool(joined) and norm in joined)


def cell_reading(cell: dict, ref: dict) -> str:
    """One quoted cell against one reference table: "not_numeric", "not_in_reference", "match" or "misread"."""
    wanted = parse_cell(cell.get("value"))
    if wanted.kind not in NUMERIC_KINDS:
        return "not_numeric"
    keys = table_keys.derive_keys(ref)
    positions = [
        (r, c) for (r, c), i in keys.cover.items()
        if r in keys.row_paths and values_equal(parse_cell(ref["cells"][i]["text"]), wanted)
    ]
    if not positions:
        return "not_in_reference"
    for r, c in positions:
        if (
            _label_matches(str(cell.get("row_label") or ""), keys.row_paths.get(r) or [])
            and _label_matches(str(cell.get("column_label") or ""), keys.col_paths.get(c) or [])
        ):
            return "match"
    return "misread"


def run_reading(cells: list[dict], refs_by_number: dict) -> dict:
    """Counts for one row in one run. refs_by_number: table number -> reference table, for this row's tables."""
    out = {"quoted": len(cells), "with_reference": 0, "match": 0, "misread": 0, "not_in_reference": 0, "not_numeric": 0}
    for cell in cells:
        ref = refs_by_number.get(cell.get("table"))
        if ref is None:
            continue
        out["with_reference"] += 1
        out[cell_reading(cell, ref)] += 1
    out["layout_misread"] = out["misread"] >= 1
    return out


def build_report(rows_by_id: dict, dirs: list[Path], refs: dict[str, dict]) -> dict:
    """rows_by_id: row id -> AdjudicatedRow; refs: reference-table id -> reference table (tablefind.TABLE_NUMBERS keys)."""
    rows = []
    for rid in target_rows():
        table_ids = tablefind.ROW_TABLES.get(rid, ())
        refs_by_number = {tablefind.TABLE_NUMBERS[t]: refs[t] for t in table_ids if t in refs}
        row = rows_by_id.get(rid)
        entry: dict = {"row_id": rid, "has_reference": bool(refs_by_number), "per_run": []}
        if refs_by_number and row is not None and row.claim_index is not None:
            for folder in dirs:
                entry["per_run"].append(run_reading(quoted_cells(score_a1._row_claim(row, folder)), refs_by_number))
        runs_with_misread = sum(1 for run in entry["per_run"] if run["layout_misread"])
        entry["runs_with_layout_misread"] = runs_with_misread
        entry["layout_misread_voted"] = runs_with_misread >= score_a1.VOTES_NEEDED
        rows.append(entry)
    return {
        "folders": [str(d) for d in dirs], "rows": rows,
        "trigger": any(r["layout_misread_voted"] for r in rows),
    }


def _yn(flag: bool) -> str:
    return "y" if flag else "n"


def print_report(report: dict) -> None:
    print("Picture trigger (report only). Per run: quoted cells / with a reference table / match / misread / "
          "value not in reference / not numeric")
    for row in report["rows"]:
        if not row["has_reference"]:
            print(f"  {row['row_id']:<8} no reference table")
            continue
        runs = "; ".join(
            f"{run['quoted']}/{run['with_reference']}/{run['match']}/{run['misread']}/{run['not_in_reference']}/"
            f"{run['not_numeric']} misread {_yn(run['layout_misread'])}"
            for run in row["per_run"]
        ) or "no claim"
        print(f"  {row['row_id']:<8} {runs}; misread in >= {score_a1.VOTES_NEEDED} of {score_a1.REPEATS} runs: "
              f"{_yn(row['layout_misread_voted'])}")
    without = sum(1 for row in report["rows"] if not row["has_reference"])
    print(f"Rows with no reference table: {without} of {len(report['rows'])} (cannot be checked)")
    print(f"TRIGGER (>= 1 target row with a layout misread in >= {score_a1.VOTES_NEEDED} of {score_a1.REPEATS} runs): "
          f"{_yn(report['trigger'])}")


def run(dirs: list[Path], json_out: Path | None = None) -> int:
    if len(dirs) != score_a1.REPEATS:
        print(f"INVALID: needs exactly {score_a1.REPEATS} folders, got {len(dirs)}")
        return 1
    missing = [str(d) for d in dirs if not d.is_dir()]
    if missing:
        print(f"INVALID: folder missing: {missing}")
        return 1
    from eval.step4.tablefind_run import preflight   # reads the pins file and the reference tables only

    loaded, problems = preflight()
    if loaded is None:
        for problem in problems:
            print(f"REFERENCES NOT LOADED: {problem}")
        return 2
    rows = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="R")
    report = build_report({r.row_id: r for r in rows}, dirs, loaded["refs"])
    print_report(report)
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {json_out.resolve()}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-candidate", action="append", required=True, dest="dev_candidate", type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    sys.exit(run([d.resolve() for d in args.dev_candidate], args.json_out))


if __name__ == "__main__":
    main()
