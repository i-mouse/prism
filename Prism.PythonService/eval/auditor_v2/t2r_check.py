"""T2-R checker (decisions.md 2026-10-28 "Auditor v2 (D6+D7)", 2026-10-29 "T2-R", 2026-10-30 "T2-R inputs").

Runs the frozen check forms on the LaTeX reference tables. Plain code: no LLM, no network. BLIND by
construction: this module reads ONLY the forms file and the reference tables (t2r_refs/*.json). It does
not read dev_eval.json, the blind keys, the pins, the pin resolutions, any label or any fixture. Scoring
is t2r_score.py, which runs after the result file written here exists.

    .venv\\Scripts\\python.exe -X utf8 -m eval.auditor_v2.t2r_check --out <result.json>

Form result: contradicted | holds | cannot_check | tie.
Claim result (first match wins): any contradicted -> PS; any cannot_check -> Needs review; a claimed_group
member "absent" -> PS; any "other_table*" member, any tie, or any caveat_refs -> Needs review; else holds.
An item with no forms -> no_code_result.

Rules (fixed allowlist): all_cmp, beats_baseline, best_in_column, count_rows, count_satisfying.
Comparison (d is the oriented difference; polarity "lower" flips the sign of a pair difference):
  ">"  : d > 0 holds; d == 0 exactly is a tie (no reading is wrong); d < 0 contradicted unless d >= -tolerance
  ">=" : holds if d >= -tolerance
  "<", "<=" : same with d = constant - value (all_cmp / count_satisfying on a constant)
  "==" : holds if |d| <= tolerance
beats_baseline / best_in_column take ">" or ">=" as "better than" and use polarity for the direction.
best_in_column: params carries no pairs; rows[0] is the claimed best and is compared with every other row in
rows, per column. count_rows: counts the selected rows (rows / rows_by_columns, else every data row, minus
excluded_rows), or the distinct value combinations of the distinct_on columns, and compares with params.count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

_PY_ROOT = Path(__file__).resolve().parents[2]  # Prism.PythonService
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from eval.auditor_v2 import table_keys as tk  # noqa: E402
from eval.auditor_v2.cell_parser import parse_cell  # noqa: E402
from eval.auditor_v2.t2r_build_refs import relax_label  # noqa: E402

REPO_ROOT = _PY_ROOT.parent
AUD_DIR = REPO_ROOT / "docs" / "evals" / "auditor_rd"
FORMS_FILE = AUD_DIR / "t2r_forms_final_2026-10-30.json"
REFS_DIR = AUD_DIR / "t2r_refs"
CHECK_OUT = AUD_DIR / "t2r_check_results_2026-10-31.json"

SUPPORTED, PARTIAL, NOT_SUPPORTED, NEEDS_REVIEW = "supported", "partially_supported", "not_supported", "needs_review"
CODE_PS, CODE_NR, CODE_HOLDS, CODE_NONE = "PS", "Needs review", "holds", "no_code_result"

# ------------------------------------------------------------------ label matching on relaxed labels

_MARK_RE = re.compile(r"[*†‡+]+(?=>|$)")


def _match(index: dict, key) -> list:
    """Ids of `index` ({id: relaxed ' > '-joined path}) matching `key`. Tiers: 1 exact; 2 (only if none)
    trailing path suffix; 3 (only if none) marker-insensitive. A tier with several hits is no match."""
    want = relax_label(key)
    if not want:
        return []
    hit = [i for i, s in index.items() if s == want]
    if hit:
        return hit if len(hit) == 1 else []
    hit = [i for i, s in index.items() if s.endswith(">" + want)]
    if hit:
        return hit if len(hit) == 1 else []
    w = _MARK_RE.sub("", want)
    hit = []
    for i, s in index.items():
        s2 = _MARK_RE.sub("", s)
        if s2 == w or s2.endswith(">" + w):
            hit.append(i)
    return hit if len(hit) == 1 else []


class Ctx:
    """One reference table with its derived keys and relaxed label indexes."""

    def __init__(self, ref: str, table: dict):
        self.ref = ref
        self.table = table
        self.k = tk.derive_keys(table)
        self.row_r = {r: relax_label(" > ".join(p)) for r, p in self.k.row_paths.items()}
        self.col_r = {c: relax_label(" > ".join(p)) for c, p in self.k.col_paths.items()
                      if c not in self.k.label_cols and p}
        self.leaf_r = {c: relax_label(p[-1]) for c, p in self.k.col_paths.items() if p}

    def row_key(self, r) -> str:
        return " > ".join(self.k.row_paths.get(r) or [])

    def col_key(self, c) -> str:
        return " > ".join(self.k.col_paths.get(c) or [])

    def info(self, r, c) -> dict:
        txt = tk.cell_text(self.table, self.k, r, c)
        return {"table": self.ref, "row_index": r, "row_key": self.row_key(r), "column_index": c,
                "column_key": self.col_key(c), "value": txt}

    def number(self, r, c):
        """(Decimal or None, reason). Spanning cells resolve to the spanning cell's value."""
        txt = tk.cell_text(self.table, self.k, r, c)
        if txt is None:
            return None, "no cell at row/column"
        p = parse_cell(txt)
        if p.kind == "number" and p.value is not None:
            return p.value, ""
        return None, f"cell not numeric ({p.kind}): {txt!r}"

    def cell_relaxed(self, r, c) -> str:
        return relax_label(tk.cell_text(self.table, self.k, r, c) or "")


def resolve_row(ctx: Ctx, spec):
    """Row index for a key string or a {leaf header: value} selector. (index or None, error)."""
    if isinstance(spec, dict):
        cols = {}
        for label in spec:
            m = _match(ctx.leaf_r, label)
            if len(m) != 1:
                return None, f"selector column not found or ambiguous: {label!r}"
            cols[label] = m[0]
        rows = [r for r in ctx.k.data_rows
                if all(ctx.cell_relaxed(r, cols[l]) == relax_label(v) for l, v in spec.items())]
        if len(rows) != 1:
            return None, f"selector {spec!r} matched {len(rows)} rows"
        return rows[0], ""
    m = _match(ctx.row_r, spec)
    if len(m) != 1:
        return None, f"row not found or ambiguous: {spec!r}"
    return m[0], ""


def resolve_col(ctx: Ctx, key):
    m = _match(ctx.col_r, key)
    if len(m) != 1:
        return None, f"column not found or ambiguous: {key!r}"
    return m[0], ""


def _select_rows(ctx: Ctx, form: dict):
    rows, errors = [], []
    for spec in list(form.get("rows") or []) + list(form.get("rows_by_columns") or []):
        r, err = resolve_row(ctx, spec)
        if r is None:
            errors.append(err)
        elif r not in rows:
            rows.append(r)
    return rows, errors


def _select_cols(ctx: Ctx, form: dict):
    cols, errors = [], []
    for key in form.get("columns") or []:
        c, err = resolve_col(ctx, key)
        if c is None:
            errors.append(err)
        elif c not in cols:
            cols.append(c)
    return cols, errors


# ------------------------------------------------------------------ comparison

def judge(d: Decimal, op: str, tol: Decimal, tie_possible: bool = True) -> str:
    """holds | tie | fail for an oriented difference d against op ('>' or '>=' on d; '==' on |d|)."""
    if op == ">":
        if d > 0:
            return "holds"
        if d == 0:
            return "tie" if tie_possible else "fail"
        return "holds" if d >= -tol else "fail"
    if op == ">=":
        return "holds" if d >= -tol else "fail"
    if op == "==":
        return "holds" if abs(d) <= tol else "fail"
    raise ValueError(f"unsupported op {op!r}")


def _tol(params: dict) -> Decimal:
    return Decimal(str(params.get("tolerance") or 0))


def _constant_d(value: Decimal, op: str, const: Decimal):
    """(oriented d, op for judge) for a cell against a constant."""
    if op in (">", ">=", "=="):
        return value - const, op
    if op == "<":
        return const - value, ">"
    if op == "<=":
        return const - value, ">="
    raise ValueError(f"unsupported op {op!r}")


def _pair_d(m: Decimal, b: Decimal, op: str, polarity) -> tuple:
    if op not in (">", ">="):
        raise ValueError(f"unsupported pair op {op!r}")
    return ((b - m) if polarity == "lower" else (m - b)), op


def _element(status, cells, reason=""):
    return {"status": status, "cells": cells, "reason": reason}


def _cmp_constant(ctx, r, c, op, const, tol, tie_possible=True):
    v, why = ctx.number(r, c)
    cell = ctx.info(r, c)
    if v is None:
        return _element("unreadable", [cell], why)
    try:
        d, jop = _constant_d(v, op, const)
        st = judge(d, jop, tol, tie_possible)
    except ValueError as e:
        return _element("unreadable", [cell], str(e))
    return _element(st, [cell])


def _cmp_pair(ctx, mr, br, c, op, polarity, tol):
    cells = [ctx.info(mr, c), ctx.info(br, c)]
    m, why1 = ctx.number(mr, c)
    b, why2 = ctx.number(br, c)
    if m is None or b is None:
        return _element("unreadable", cells, why1 or why2)
    try:
        d, jop = _pair_d(m, b, op, polarity)
        st = judge(d, jop, tol)
    except ValueError as e:
        return _element("unreadable", cells, str(e))
    return _element(st, cells)


# ------------------------------------------------------------------ rules

def _summarise(elements: list) -> dict:
    fails = [e for e in elements if e["status"] == "fail"]
    unread = [e for e in elements if e["status"] == "unreadable"]
    ties = [e for e in elements if e["status"] == "tie"]
    if fails:
        result, reason = "contradicted", f"{len(fails)} of {len(elements)} comparisons break the claim"
    elif unread:
        result, reason = "cannot_check", "; ".join(sorted({e["reason"] for e in unread}))
    elif ties:
        result, reason = "tie", f"{len(ties)} exact tie(s) on a strict comparison"
    elif not elements:
        result, reason = "cannot_check", "no comparison to run"
    else:
        result, reason = "holds", f"{len(elements)} comparisons hold"
    breaking = [c for e in fails for c in e["cells"]]
    return {"result": result, "reason": reason, "breaking_cells": breaking, "elements": elements}


def _setup_errors(errors):
    return [_element("unreadable", [], e) for e in errors]


def rule_all_cmp(ctx, form):
    p = form["params"]
    rows, row_err = _select_rows(ctx, form)
    cols, col_err = _select_cols(ctx, form)
    if p.get("constant") is None:
        return _summarise([_element("unreadable", [], "all_cmp needs a constant")])
    const, tol, op = Decimal(str(p["constant"])), _tol(p), p.get("op")
    els = _setup_errors(row_err + col_err)
    for r in rows:
        for c in cols:
            els.append(_cmp_constant(ctx, r, c, op, const, tol))
    return _summarise(els)


def rule_beats_baseline(ctx, form):
    p = form["params"]
    cols, col_err = _select_cols(ctx, form)
    els = _setup_errors(col_err)
    pairs = p.get("pairs") or []
    if not pairs:
        els.append(_element("unreadable", [], "beats_baseline has no pairs"))
    for pair in pairs:
        mr, e1 = resolve_row(ctx, pair["method"])
        br, e2 = resolve_row(ctx, pair["baseline"])
        if mr is None or br is None:
            els.append(_element("unreadable", [], e1 or e2))
            continue
        for c in cols:
            els.append(_cmp_pair(ctx, mr, br, c, p.get("op"), p.get("polarity") or "higher", _tol(p)))
    return _summarise(els)


def rule_best_in_column(ctx, form):
    p = form["params"]
    rows, row_err = _select_rows(ctx, form)
    cols, col_err = _select_cols(ctx, form)
    els = _setup_errors(row_err + col_err)
    spec = (form.get("rows") or form.get("rows_by_columns") or [None])[0]
    best, _ = resolve_row(ctx, spec) if spec is not None else (None, "")
    if best is None or len(rows) < 2:
        els.append(_element("unreadable", [], "best_in_column needs a resolvable first row and at least one other row"))
    else:
        for r in rows:
            if r == best:
                continue
            for c in cols:
                els.append(_cmp_pair(ctx, best, r, c, p.get("op") or ">", p.get("polarity") or "higher", _tol(p)))
    return _summarise(els)


def rule_count_satisfying(ctx, form):
    p = form["params"]
    k = int(p.get("k") or 1)
    cols, col_err = _select_cols(ctx, form)
    els = _setup_errors(col_err)
    if p.get("pairs"):
        for pair in p["pairs"]:
            mr, e1 = resolve_row(ctx, pair["method"])
            br, e2 = resolve_row(ctx, pair["baseline"])
            if mr is None or br is None:
                els.append(_element("unreadable", [], e1 or e2))
                continue
            for c in cols:
                els.append(_cmp_pair(ctx, mr, br, c, p.get("op"), p.get("polarity") or "higher", _tol(p)))
    else:
        rows, row_err = _select_rows(ctx, form)
        els += _setup_errors(row_err)
        if p.get("constant") is None:
            els.append(_element("unreadable", [], "count_satisfying needs a constant or pairs"))
        else:
            for r in rows:
                for c in cols:
                    els.append(_cmp_constant(ctx, r, c, p.get("op"), Decimal(str(p["constant"])), _tol(p)))
    sat = sum(1 for e in els if e["status"] == "holds")
    unk = sum(1 for e in els if e["status"] == "unreadable")
    tie = sum(1 for e in els if e["status"] == "tie")
    n = len(els)
    if sat >= k:
        result, reason = "holds", f"{sat} of {n} satisfy (need {k})"
    elif sat + unk >= k:
        result, reason = "cannot_check", f"{sat} satisfy, {unk} unreadable (need {k})"
    elif sat + unk + tie >= k:
        result, reason = "tie", f"{sat} satisfy, {tie} exact tie(s) (need {k})"
    else:
        result, reason = "contradicted", f"only {sat} of {n} satisfy (need {k})"
    breaking = [c for e in els if e["status"] != "holds" for c in e["cells"]] if result == "contradicted" else []
    return {"result": result, "reason": reason, "breaking_cells": breaking, "elements": els}


def rule_count_rows(ctx, form):
    p = form["params"]
    if p.get("count") is None:
        return {"result": "cannot_check", "reason": "count_rows needs a count", "breaking_cells": [], "elements": []}
    listed = bool(form.get("rows") or form.get("rows_by_columns"))
    rows, row_err = _select_rows(ctx, form)
    if row_err:
        return {"result": "cannot_check", "reason": "; ".join(row_err), "breaking_cells": [], "elements": []}
    if not listed:
        excl = set()
        for spec in form.get("excluded_rows") or []:
            r, _ = resolve_row(ctx, spec)
            if r is not None:
                excl.add(r)
        rows = [r for r in ctx.k.data_rows if r not in excl]
    dcols = []
    for label in p.get("distinct_on") or []:
        m = _match(ctx.leaf_r, label)
        if len(m) != 1:
            return {"result": "cannot_check", "reason": f"distinct_on column not found or ambiguous: {label!r}",
                    "breaking_cells": [], "elements": []}
        dcols.append(m[0])
    if dcols:
        found = len({tuple(ctx.cell_relaxed(r, c) for c in dcols) for r in rows})
    else:
        found = len(rows)
    op = p.get("op") or "=="
    target = Decimal(str(p["count"]))
    try:
        if op in ("<", "<="):
            d, jop = target - Decimal(found), (">" if op == "<" else ">=")
        else:
            d, jop = Decimal(found) - target, op
        st = judge(d, jop, _tol(p), tie_possible=False)
    except ValueError as e:
        return {"result": "cannot_check", "reason": str(e), "breaking_cells": [], "elements": []}
    cells = [ctx.info(r, c) for r in rows for c in (dcols or [])] or [
        {"table": ctx.ref, "row_index": r, "row_key": ctx.row_key(r), "column_index": None,
         "column_key": None, "value": None} for r in rows]
    result = "holds" if st == "holds" else "contradicted"
    return {"result": result, "reason": f"counted {found} (claimed {p['count']}, op {op})",
            "breaking_cells": cells if result == "contradicted" else [],
            "elements": [{"status": st, "cells": [], "reason": f"counted {found}"}]}


RULES = {
    "all_cmp": rule_all_cmp,
    "beats_baseline": rule_beats_baseline,
    "best_in_column": rule_best_in_column,
    "count_rows": rule_count_rows,
    "count_satisfying": rule_count_satisfying,
}


def check_form(form: dict, load_table) -> dict:
    """load_table(ref) -> table dict or None."""
    ref = form["table_ref"]
    table = load_table(ref)
    out = {"table_ref": ref, "rule": form["rule"], "reading": form.get("reading"), "partial": bool(form.get("partial"))}
    if table is None:
        return {**out, "result": "cannot_check", "reason": f"reference table {ref} not found",
                "breaking_cells": [], "elements": []}
    fn = RULES.get(form["rule"])
    if fn is None:
        return {**out, "result": "cannot_check", "reason": f"unsupported rule {form['rule']!r}",
                "breaking_cells": [], "elements": []}
    try:
        res = fn(Ctx(ref, table), form)
    except (KeyError, ValueError, TypeError) as e:
        res = {"result": "cannot_check", "reason": f"form could not be run: {type(e).__name__}: {e}",
               "breaking_cells": [], "elements": []}
    return {**out, **res}


# ------------------------------------------------------------------ claim result and merge

def claim_result(item: dict, form_results: list) -> dict:
    members = item.get("claimed_group") or []
    absent = [m["member"] for m in members if m.get("status") == "absent"]
    other = [{"member": m["member"], "status": m["status"]} for m in members
             if str(m.get("status", "")).startswith("other_table")]
    caveats = list(item.get("caveat_refs") or [])
    results = [f["result"] for f in form_results]
    ties = results.count("tie")
    if not form_results:
        code, why = CODE_NONE, "no forms"
    elif "contradicted" in results:
        code, why = CODE_PS, "a form is contradicted"
    elif "cannot_check" in results:
        code, why = CODE_NR, "a form cannot be checked"
    elif absent:
        code, why = CODE_PS, "a claimed_group member is absent"
    elif other or ties or caveats:
        code = CODE_NR
        why = "; ".join(x for x in ("member in another table" if other else "", "exact tie" if ties else "",
                                    "caveat" if caveats else "") if x)
    else:
        code, why = CODE_HOLDS, "all forms hold"
    return {"id": item["id"], "paper": item.get("paper"), "code_result": code, "decided_by": why,
            "forms": form_results, "absent_members": absent, "other_table_members": other,
            "caveat_refs": caveats, "ties": ties}


def merge_label(run1, code_result):
    """Merge order (fixed): can only lower; Needs review only replaces a final Supported; PS/NS never raised."""
    if run1 != SUPPORTED:
        return run1
    if code_result == CODE_PS:
        return PARTIAL
    if code_result == CODE_NR:
        return NEEDS_REVIEW
    return run1


# ------------------------------------------------------------------ run

def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_all(forms_path: Path = FORMS_FILE, refs_dir: Path = REFS_DIR) -> dict:
    forms = json.loads(Path(forms_path).read_text(encoding="utf-8"))
    cache: dict = {}
    used: dict = {}

    def load_table(ref):
        if ref not in cache:
            p = Path(refs_dir) / f"{ref}.json"
            cache[ref] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            if p.exists():
                used[ref] = _sha(p)
        return cache[ref]

    items = []
    for item in forms:
        items.append(claim_result(item, [check_form(f, load_table) for f in item.get("forms", [])]))
    return {"forms_file": Path(forms_path).name, "forms_sha256": _sha(forms_path),
            "ref_sha256": {k: used[k] for k in sorted(used)}, "items": items}


def dumps(obj) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=CHECK_OUT)
    args = ap.parse_args(argv)
    res = run_all()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(dumps(res))
    for it in res["items"]:
        print(f"{it['id']}: {it['code_result']} ({it['decided_by']}); forms: "
              + ", ".join(f["result"] for f in it["forms"]))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
