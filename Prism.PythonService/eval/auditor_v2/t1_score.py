"""T1 scorer for Auditor v2 (table fidelity). Reads JSON only.

Inputs: the pins file and the normalised table files written by
scratch/auditor_v2/t1env/run_extract.py:
    <tables-root>/<extractor>/<run>/normalised/<paper_id>.json
Applies the rules of decisions.md "Auditor v2 (D6+D7) ... 2026-10-28"
mechanically. No settings, no pins, no thresholds are changed here.

    python -m eval.auditor_v2.t1_score --pins docs/evals/auditor_rd/t1_pins_2026-10-28.json \
        --tables-root Prism.PythonService/scratch/auditor_v2/out --out <scores.json>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from eval.auditor_v2 import table_keys as tk
from eval.auditor_v2.cell_parser import parse_cell, values_equal

EXTRACTORS = ("pymupdf4llm", "docling")  # order = tie-break (pymupdf4llm first)
GATE_USABLE_MIN = 7
OTHER_GATED_MIN_FRACTION = 0.9


# ----------------------------------------------------------------- pin checks

def _rows_by_label(k: tk.Keys, label: str) -> list:
    return tk._unique_match({r: [tk.row_label(k, r)] for r in k.data_rows}, [label])


def evaluate_pin(table: dict, k: tk.Keys, pin: dict) -> dict:
    kind = pin["kind"]
    if kind == "cell":
        return tk.evaluate_cell(table, k, pin)
    if kind == "row_count":
        n = tk.count_data_rows(k)
        return {"correct": n == pin["count"], "got": str(n), "reason": ""}
    if kind in ("row_exists", "row_absent"):
        if pin.get("match"):
            rows = tk.rows_matching(table, k, pin["match"])
            if rows is None:
                return {"correct": False, "got": None, "reason": "named column not found or ambiguous"}
        else:
            rows = tk.rows_by_path(table, k, pin["row_key_path"])
        want = len(rows) >= 1 if kind == "row_exists" else len(rows) == 0
        return {"correct": want, "got": f"{len(rows)} matching rows", "reason": ""}
    if kind == "col_contains_count":
        c = tk.key_column(table, k, pin["column"])
        if c is None:
            return {"correct": False, "got": None, "reason": "named column not found or ambiguous"}
        needle = tk.normalize_label(pin["contains"])
        n = sum(1 for r in k.data_rows if needle in tk.normalize_label(tk.cell_text(table, k, r, c) or ""))
        return {"correct": n == pin["count"], "got": str(n), "reason": ""}
    if kind == "name_set":
        failing = []
        for name in pin["names"]:
            if len(_rows_by_label(k, name)) != 1:
                failing.append(name)
        return {"correct": not failing, "got": "all present once" if not failing else "not exactly once: " + "; ".join(failing), "reason": ""}
    if kind == "label_absent":
        needle = tk.normalize_label(pin["contains"])
        bad = [p[-1] for p in k.row_paths.values() if p and any(needle in tk.normalize_label(x) for x in p)]
        return {"correct": not bad, "got": "absent" if not bad else "present in: " + "; ".join(bad), "reason": ""}
    if kind == "group_counts":
        counts, section = {}, None
        for r in range(k.n_rows):
            if r in k.section_rows:
                section = k.section_rows[r]
                counts.setdefault(section, 0)
            elif r in k.data_rows and section is not None:
                counts[section] += 1
        norm = {tk.normalize_label(s): n for s, n in counts.items()}
        ok = all(norm.get(tk.normalize_label(s)) == n for s, n in pin["groups"].items())
        return {"correct": ok, "got": json.dumps(counts, ensure_ascii=False), "reason": ""}
    if kind == "caption":
        cap = tk.normalize_label(table.get("caption_text") or "")
        missing = [f for f in pin["fragments"] if tk.normalize_label(f) not in cap]
        return {"correct": not missing, "got": "all fragments found" if not missing else "missing: " + "; ".join(missing), "reason": ""}
    if kind == "row_contains":
        r = tk.unique_row(table, k, pin["row_key_path"])
        if r is None:
            return {"correct": False, "got": None, "reason": "row not found or ambiguous"}
        row_cells = {k.cover[(r, c)] for c in range(k.n_cols) if (r, c) in k.cover and c not in k.label_cols}
        parsed = [parse_cell(table["cells"][i]["text"]) for i in row_cells]
        missing = [v for v in pin["values"] if not any(values_equal(parse_cell(v), p) for p in parsed)]
        return {"correct": not missing, "got": "all values in row" if not missing else "missing: " + "; ".join(missing), "reason": ""}
    return {"correct": False, "got": None, "reason": f"unknown pin kind {kind}"}


def is_structural(pin: dict) -> bool:
    return pin["kind"] != "cell"


def is_other_gated_cell(pin: dict) -> bool:
    return pin["kind"] == "cell" and not pin["breaking"] and not pin["key_uncertain"]


# -------------------------------------------------------------------- scoring

def load_tables(root: Path, extractor: str, run: str, paper_id: str) -> Optional[list]:
    p = root / extractor / run / "normalised" / f"{paper_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))["tables"]


def score_table(tables: Optional[list], tinfo: dict, pins: list) -> dict:
    cands = tk.tables_with_caption_number(tables or [], tinfo["caption_number"])
    unique = len(cands) == 1
    out = {"role": tinfo["role"], "n_candidates": len(cands), "detected_unique": unique, "pins": []}
    table = cands[0] if unique else None
    k = tk.derive_keys(table) if table else None
    for pin in pins:
        res = evaluate_pin(table, k, pin) if table else {
            "correct": False, "got": None,
            "reason": "no table" if not cands else f"{len(cands)} tables share caption number",
        }
        out["pins"].append({"id": pin["id"], "correct": res["correct"], "got": res["got"], "reason": res["reason"]})
    by_id = {p["id"]: p for p in pins}
    rs = out["pins"]

    def frac(sel):
        chosen = [r for r in rs if sel(by_id[r["id"]])]
        return [sum(1 for r in chosen if r["correct"]), len(chosen)]

    out["breaking"] = frac(lambda p: p["breaking"])
    out["structural"] = frac(is_structural)
    out["other_gated"] = frac(is_other_gated_cell)
    out["uncertain"] = frac(lambda p: p["key_uncertain"])
    og_ok, og_n = out["other_gated"]
    out["usable"] = bool(
        unique
        and out["breaking"][0] == out["breaking"][1]
        and out["structural"][0] == out["structural"][1]
        and (og_n == 0 or og_ok / og_n >= OTHER_GATED_MIN_FRACTION)
    )
    return out


def first_diffs(a, b, path="$", limit=3) -> list:
    diffs = []

    def walk(x, y, p):
        if len(diffs) >= limit:
            return
        if type(x) is not type(y):
            diffs.append(f"{p}: type {type(x).__name__} vs {type(y).__name__}")
        elif isinstance(x, dict):
            for key in sorted(set(x) | set(y)):
                if key not in x or key not in y:
                    diffs.append(f"{p}.{key}: present in only one run")
                else:
                    walk(x[key], y[key], f"{p}.{key}")
        elif isinstance(x, list):
            if len(x) != len(y):
                diffs.append(f"{p}: length {len(x)} vs {len(y)}")
            for i, (xi, yi) in enumerate(zip(x, y)):
                walk(xi, yi, f"{p}[{i}]")
        elif x != y:
            diffs.append(f"{p}: {x!r} vs {y!r}")

    walk(a, b, path)
    return diffs[:limit]


def stability(root: Path, extractor: str, runs, paper_ids) -> dict:
    ra, rb = runs[0], runs[1]
    problems = []
    for pid in paper_ids:
        fa = root / extractor / ra / "normalised" / f"{pid}.json"
        fb = root / extractor / rb / "normalised" / f"{pid}.json"
        if not fa.exists() or not fb.exists():
            problems.append(f"{pid}: file missing")
            continue
        if fa.read_bytes() != fb.read_bytes():
            d = first_diffs(json.loads(fa.read_text(encoding="utf-8")), json.loads(fb.read_text(encoding="utf-8")))
            problems.append(f"{pid}: " + " | ".join(d) if d else f"{pid}: bytes differ")
    return {"stable": not problems, "first_differences": problems[:5]}


def score_all(pins_doc: dict, root: Path, extractors, runs) -> dict:
    pins_by_table = {}
    for pin in pins_doc["pins"]:
        pins_by_table.setdefault(pin["table_id"], []).append(pin)
    paper_ids = sorted(set(pins_doc["papers"].values()))
    result = {"extractors": {}, "runs_scored": runs[0]}
    for e in extractors:
        tables_out = {}
        for tinfo in pins_doc["tables"]:
            tables = load_tables(root, e, runs[0], tinfo["paper_id"])
            tables_out[tinfo["table_id"]] = score_table(tables, tinfo, pins_by_table.get(tinfo["table_id"], []))
        gate = [t for t in tables_out.values() if t["role"] == "gate"]
        st = stability(root, e, runs, paper_ids)
        result["extractors"][e] = {
            "tables": tables_out,
            "gate_usable": sum(1 for t in gate if t["usable"]),
            "gate_total": len(gate),
            "breaking_correct": sum(t["breaking"][0] for t in gate),
            "breaking_total": sum(t["breaking"][1] for t in gate),
            "stable": st["stable"],
            "first_differences": st["first_differences"],
        }
        result["extractors"][e]["passes"] = bool(
            st["stable"] and result["extractors"][e]["gate_usable"] >= GATE_USABLE_MIN
        )
    passing = [e for e in extractors if result["extractors"][e]["passes"]]
    result["overall_pass"] = bool(passing)
    if passing:
        passing.sort(key=lambda e: (-result["extractors"][e]["gate_usable"],
                                    -result["extractors"][e]["breaking_correct"],
                                    EXTRACTORS.index(e) if e in EXTRACTORS else 99))
        result["winner"] = passing[0]
    else:
        result["winner"] = None
    result["pin_suspects"] = pin_suspects(pins_doc, result, extractors)
    return result


def pin_suspects(pins_doc: dict, result: dict, extractors) -> list:
    if len(extractors) < 2:
        return []
    out = []
    for pin in pins_doc["pins"]:
        if pin["kind"] != "cell" or pin["key_uncertain"]:
            continue
        gate = {t["table_id"]: t["role"] for t in pins_doc["tables"]}.get(pin["table_id"])
        if gate != "gate":
            continue
        got = []
        for e in extractors:
            r = next(p for p in result["extractors"][e]["tables"][pin["table_id"]]["pins"] if p["id"] == pin["id"])
            got.append(r)
        if all(g["got"] is not None and not g["correct"] for g in got) and \
                values_equal(parse_cell(got[0]["got"]), parse_cell(got[1]["got"])):
            out.append({"pin": pin["id"], "pinned": pin["value"], "both_got": got[0]["got"]})
    return out


# --------------------------------------------------------------------- report

def _fx(v) -> str:
    return f"{v[0]}/{v[1]}"


def render_markdown(pins_doc: dict, result: dict, extractors) -> str:
    L = []
    tinfo = {t["table_id"]: t for t in pins_doc["tables"]}
    for role, title in (("gate", "Gate tables"), ("info", "Info tables (info only, not gated)")):
        L += [f"### {title}", "",
              "| extractor | table | detected | breaking | structural | other gated | uncertain (reported) | usable |",
              "|---|---|---|---|---|---|---|---|"]
        for e in extractors:
            for tid, t in result["extractors"][e]["tables"].items():
                if t["role"] != role:
                    continue
                det = "yes" if t["detected_unique"] else f"no ({t['n_candidates']} with caption number)"
                use = ("yes" if t["usable"] else "no") if role == "gate" else "info"
                L.append(f"| {e} | {tid} | {det} | {_fx(t['breaking'])} | {_fx(t['structural'])} | "
                         f"{_fx(t['other_gated'])} | {_fx(t['uncertain'])} | {use} |")
        L.append("")
    L += ["### Stability", "", "| extractor | stable | first differences |", "|---|---|---|"]
    for e in extractors:
        r = result["extractors"][e]
        L.append(f"| {e} | {'yes' if r['stable'] else 'no'} | {'; '.join(r['first_differences']) or '-'} |")
    L += ["", "### Gated mismatches", "",
          "| pin id | table | pinned (keys / value) | " + " | ".join(extractors) + " |", "|---|---|---|" + "---|" * len(extractors)]
    for pin in pins_doc["pins"]:
        t = tinfo[pin["table_id"]]
        if t["role"] != "gate" or pin["key_uncertain"]:
            continue
        rows = []
        for e in extractors:
            r = next(p for p in result["extractors"][e]["tables"][pin["table_id"]]["pins"] if p["id"] == pin["id"])
            rows.append(r)
        if all(r["correct"] for r in rows):
            continue
        L.append(f"| {pin['id']} | {pin['table_id']} | {_pin_desc(pin)} | " +
                 " | ".join(_got(r) for r in rows) + " |")
    L += ["", "### Pin suspects", ""]
    if result["pin_suspects"]:
        L += ["| pin | pinned | both extractors gave |", "|---|---|---|"]
        L += [f"| {s['pin']} | {s['pinned']} | {s['both_got']} |" for s in result["pin_suspects"]]
    else:
        L.append("none")
    L += ["", "### Mechanical verdict", "",
          "| extractor | stable | gate tables usable | breaking cells correct | PASS |", "|---|---|---|---|---|"]
    for e in extractors:
        r = result["extractors"][e]
        L.append(f"| {e} | {'yes' if r['stable'] else 'no'} | {r['gate_usable']}/{r['gate_total']} | "
                 f"{r['breaking_correct']}/{r['breaking_total']} | {'PASS' if r['passes'] else 'FAIL'} |")
    L += ["", f"Overall T1: **{'PASS' if result['overall_pass'] else 'FAIL'}**. "
              f"Winner: **{result['winner'] or 'none'}**.", ""]
    return "\n".join(L)


def _pin_desc(pin: dict) -> str:
    if pin["kind"] == "cell":
        return f"{' > '.join(pin['row_key_path'])} / {' > '.join(pin['column_key_path'])} = {pin['value']}"
    return f"{pin['kind']}: {pin.get('description', '')}"


def _got(r: dict) -> str:
    if r["correct"]:
        return "ok"
    return (r["got"] if r["got"] is not None else r["reason"]) or "-"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pins", required=True)
    ap.add_argument("--tables-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default=None)
    ap.add_argument("--extractors", nargs="+", default=list(EXTRACTORS))
    ap.add_argument("--runs", nargs=2, default=["run_a", "run_b"])
    args = ap.parse_args(argv)
    pins_doc = json.loads(Path(args.pins).read_text(encoding="utf-8"))
    result = score_all(pins_doc, Path(args.tables_root), args.extractors, args.runs)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = Path(args.md) if args.md else Path(args.out).with_suffix(".md")
    md_path.write_text(render_markdown(pins_doc, result, args.extractors), encoding="utf-8")
    print(f"overall={'PASS' if result['overall_pass'] else 'FAIL'} winner={result['winner']}")
    for e in args.extractors:
        r = result["extractors"][e]
        print(f"{e}: stable={r['stable']} gate_usable={r['gate_usable']}/{r['gate_total']} "
              f"breaking={r['breaking_correct']}/{r['breaking_total']}")
    print(f"pin_suspects={len(result['pin_suspects'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
