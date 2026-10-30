"""T2-R reference-table builder (decisions.md 2026-10-29, "Auditor v2 T1 result ... T2-R first").

Free, no LLM, no network. Builds reference tables from the arXiv LaTeX of the dev papers,
identifies each table by its PDF caption text, checks every T1 pin of the gate tables and
resolves the S-row list. Run from Prism.PythonService:

    .venv\\Scripts\\python.exe -I eval/auditor_v2/t2r_build_refs.py

The dev PDFs are opened only by read_pdf_captions, which keeps only the caption text of lines that
start "Table <N>" followed by ':' '.' or '|' (at most 80 characters of each are printed or reported).
Pins, the identification rule and the relaxed label compare are never changed by this script.
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

_PY_ROOT = Path(__file__).resolve().parents[2]  # Prism.PythonService
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from eval.auditor_v2 import latex_probe as lp  # noqa: E402
from eval.auditor_v2 import latex_table as lt  # noqa: E402
from eval.auditor_v2 import t1_score as t1s  # noqa: E402
from eval.auditor_v2 import table_keys as tk  # noqa: E402
from eval.auditor_v2.cell_parser import parse_cell, values_equal  # noqa: E402

REPO_ROOT = _PY_ROOT.parent
PDF_DIR = REPO_ROOT / "docs" / "research_papers"
AUD_DIR = REPO_ROOT / "docs" / "evals" / "auditor_rd"
OUT_DIR = AUD_DIR / "t2r_refs"
REPORT_FILE = AUD_DIR / "t2r_refs_report_2026-10-29.md"
S_ROWS_IN = lp.DEFAULT_ROOT / "s_rows.json"
S_ROWS_OUT = AUD_DIR / "t2r_s_rows_2026-10-29.json"
FALLBACK_ROW = "P1-S2"
OK_STATUSES = ("strict", "relaxed", "ambiguous-consistent")


# ----------------------------------------------------------------- relaxed label compare

_DASHES = "‐‑‒–—―−"  # hyphens, en/em dash, minus sign -> "-"


def relax_label(s) -> str:
    """Fixed relaxed compare: citations removed (rule amendment 5), NFKC, casefold, Greek (alpha,
    lambda, delta incl. the PDF's INCREMENT sign) to ASCII words, -/en dash/em dash/minus treated
    as one character (rule amendment 2), all whitespace removed."""
    s = lt.strip_citations(s if isinstance(s, str) else "")
    s = unicodedata.normalize("NFKC", s).casefold()
    s = "".join(lt._WORD_OF_CHAR.get(ch, ch) for ch in s)
    s = "".join("-" if ch in _DASHES else ch for ch in s)
    return re.sub(r"\s+", "", s)


def relaxed_table(table: dict) -> dict:
    out = copy.deepcopy(table)
    for c in out["cells"]:
        if parse_cell(c["text"]).kind in ("text", "missing"):
            c["text"] = relax_label(c["text"])
    return out


def relaxed_pin(pin: dict) -> dict:
    out = copy.deepcopy(pin)
    for key in ("row_key_path", "column_key_path", "key_columns", "names"):
        if out.get(key):
            out[key] = [relax_label(x) for x in out[key]]
    if out.get("match"):
        out["match"] = {relax_label(k): relax_label(v) for k, v in out["match"].items()}
    for key in ("column", "contains"):
        if out.get(key):
            out[key] = relax_label(out[key])
    return out


def _candidates(paths: dict, wanted) -> list:
    want = tuple(tk.normalize_label(p) for p in wanted)
    hit = [i for i, p in paths.items() if tk._is_suffix(want, tuple(tk.normalize_label(x) for x in p))]
    if hit:
        return hit
    want_m = tuple(tk.strip_markers(w) for w in want)
    return [i for i, p in paths.items()
            if tk._is_suffix(want_m, tuple(tk.strip_markers(tk.normalize_label(x)) for x in p))]


def _ambiguous_consistent(rt: dict, pin: dict) -> Optional[dict]:
    """key_uncertain cell pin whose row or column path matches several cells: passes only if the
    pinned value is in the pinned column of at least one matching row."""
    k = tk.derive_keys(rt)
    rows = _candidates(k.row_paths, pin["row_key_path"])
    cols = _candidates({c: p for c, p in k.col_paths.items() if c not in k.label_cols and p},
                       pin["column_key_path"])
    if len(rows) * len(cols) <= 1:
        return None
    want = parse_cell(pin["value"])
    for r in rows:
        for c in cols:
            got = tk.cell_text(rt, k, r, c)
            if got is not None and values_equal(parse_cell(got), want):
                return {"correct": True, "got": f"{len(rows)} rows x {len(cols)} cols candidate; value present in ({r},{c})",
                        "reason": ""}
    return {"correct": False, "got": f"{len(rows)} rows x {len(cols)} cols candidate; value in none",
            "reason": "ambiguous path and value not present"}


def check_pin(table: dict, pin: dict) -> dict:
    """strict (unchanged t1_score.evaluate_pin) -> relaxed labels -> ambiguous-consistent (uncertain
    cell pins only). Only labels are relaxed; values always go through values_equal."""
    k = tk.derive_keys(table)
    res = t1s.evaluate_pin(table, k, pin)
    base = {"id": pin["id"], "kind": pin["kind"], "key_uncertain": bool(pin.get("key_uncertain")),
            "breaking": bool(pin.get("breaking")), "strict_reason": res["reason"]}
    if res["correct"]:
        return {**base, "status": "strict", "got": res["got"], "reason": ""}
    rt = relaxed_table(table)
    rp = relaxed_pin(pin)
    res2 = t1s.evaluate_pin(rt, tk.derive_keys(rt), rp)
    if res2["correct"]:
        labels = [x for key in ("row_key_path", "column_key_path", "key_columns") for x in (pin.get(key) or [])]
        return {**base, "status": "relaxed", "got": res2["got"], "reason": "",
                "pin_labels": labels, "strict_got": res["got"]}
    if pin["kind"] == "cell" and pin.get("key_uncertain"):
        amb = _ambiguous_consistent(rt, rp)
        if amb is not None:
            return {**base, "status": "ambiguous-consistent" if amb["correct"] else "mismatch",
                    "got": amb["got"], "reason": amb["reason"]}
    return {**base, "status": "mismatch", "got": res2["got"] if res2["got"] is not None else res["got"],
            "reason": res2["reason"] or res["reason"]}


def check_table_pins(table, pins: list) -> dict:
    """`table` is one schema table or a list of sub-tables (T<n>a, T<n>b). With sub-tables a pin
    takes the first sub-table where it passes, else the result on the first sub-table."""
    tables = table if isinstance(table, list) else [table]
    results = []
    for p in pins:
        best = None
        for k, t in enumerate(tables):
            r = check_pin(t, p)
            if len(tables) > 1:
                r["part"] = chr(ord("a") + k)
            if r["status"] in OK_STATUSES:
                best = r
                break
            best = best or r
        results.append(best)

    def frac(sel):
        chosen = [r for r in results if sel(r)]
        return [sum(1 for r in chosen if r["status"] in OK_STATUSES), len(chosen)]

    return {
        "results": results,
        "cell": frac(lambda r: r["kind"] == "cell" and not r["key_uncertain"]),
        "structural": frac(lambda r: r["kind"] != "cell"),
        "uncertain": frac(lambda r: r["key_uncertain"]),
        "relaxed": [r for r in results if r["status"] == "relaxed"],
        "mismatches": [r for r in results if r["status"] == "mismatch"],
    }


# ----------------------------------------------------------------- PDF captions (the only PDF read)

def _import_pymupdf():
    try:
        import pymupdf  # type: ignore
        return pymupdf
    except ImportError:
        import fitz  # type: ignore
        return fitz


def read_pdf_captions(pdf_path: Path, number: int) -> list:
    """Caption texts of lines starting `Table <number>` + ':' '.' or '|'. No other PDF text is kept."""
    pymupdf = _import_pymupdf()
    caps = []
    with pymupdf.open(str(pdf_path)) as doc:
        for page in doc:
            caps += lt.find_captions_in_lines(page.get_text("text").splitlines(), number)
    return caps


# ----------------------------------------------------------------- S rows: order, resolution

def row_infos(dev_eval: dict, match_map: dict) -> list:
    """All dev S rows with criteria a-d, sorted by row id. Same rule as latex_probe.select_s_rows."""
    rows = []
    for paper in dev_eval.get("papers", []):
        for r in lp._iter_rows(paper):
            rows.append({"paper_id": paper.get("paper_id"), **r})
    mm = match_map.get("rows", {})

    def claim_id(row_id):
        e = mm.get(row_id) or {}
        return None if e.get("confirmed_no_match") else (e.get("claim_fingerprint") or e.get("persisted_claim_id"))

    by_claim: dict = {}
    for r in rows:
        if r.get("expected_label") != "supported":
            cid = claim_id(r["id"])
            if cid:
                by_claim.setdefault(cid, []).append(r["id"])
    infos = []
    for r in rows:
        if r.get("expected_label") != "supported":
            continue
        cid = claim_id(r["id"])
        cited = lp.extract_table_refs(str(r.get("scoring_notes") or ""))
        for t in lp.extract_table_refs(lp._evidence_text(r)):
            if t not in cited:
                cited.append(t)
        words = sorted({w.lower() for w in lp._SCOPE_RE.findall(str(r.get("claim_text_verbatim") or ""))})
        shared = by_claim.get(cid, []) if cid else []
        infos.append({
            "row_id": r["id"], "paper": f"P{lp.paper_number(r['id'])}", "paper_id": r.get("paper_id"),
            "tables_cited": cited, "a": bool(cid), "b": bool(cited), "c": bool(words), "d": not shared,
        })
    infos.sort(key=lambda x: lp.row_sort_key(x["row_id"]))
    return infos


def ordered_full_rows(infos: list) -> list:
    return [x for x in infos if x["a"] and x["b"] and x["c"] and x["d"]]


def reproduce_selection(full: list) -> list:
    selected, seen = [], set()
    for x in full:
        if x["paper"] not in seen:
            seen.add(x["paper"])
            selected.append(x["row_id"])
    selected = selected[:10]
    for x in full:
        if len(selected) >= 10:
            break
        if x["row_id"] not in selected:
            selected.append(x["row_id"])
    return selected


def resolve_s_rows(s_rows: dict, pool_full: list, table_ok) -> dict:
    """table_ok(paper_label, table_number) -> (bool, reason). Replacement rule (decisions.md T2):
    a selected row with an unidentified cited table gets no form and is replaced by the next row in
    the existing order (a-b-c-d rows not yet selected, by row id), skipping rows whose tables are
    also unidentified."""
    selected = s_rows["selected"]
    selected_ids = [r["row_id"] for r in selected]
    pool = [x for x in pool_full if x["row_id"] not in selected_ids]
    used = set(selected_ids)
    unidentified, replacements, skipped, final = [], [], [], []

    def row_state(row):
        bad = []
        for t in row["tables_cited"]:
            if not str(t).isdigit():
                bad.append({"paper": row["paper"], "table": t, "reason": "non-numeric table id"})
                continue
            ok, why = table_ok(row["paper"], int(t))
            if not ok:
                bad.append({"paper": row["paper"], "table": int(t), "reason": why})
        return bad

    for sel in selected:
        bad = row_state(sel)
        if not bad:
            final.append(sel["row_id"])
            continue
        for b in bad:
            if b not in unidentified:
                unidentified.append(b)
        chosen = None
        for cand in pool:
            if cand["row_id"] in used:
                continue
            cbad = row_state(cand)
            if cbad:
                if not any(x["row"] == cand["row_id"] for x in skipped):
                    skipped.append({"row": cand["row_id"], "reason": "; ".join(
                        f"{b['paper']} T{b['table']}: {b['reason']}" for b in cbad)})
                continue
            chosen = cand
            break
        if chosen is None:
            final.append(None)
            replacements.append({"old": sel["row_id"], "new": None,
                                 "reason": "no replacement row with identified tables"})
            continue
        used.add(chosen["row_id"])
        final.append(chosen["row_id"])
        replacements.append({"old": sel["row_id"], "new": chosen["row_id"],
                             "reason": "; ".join(f"{b['paper']} T{b['table']}: {b['reason']}" for b in bad)})
    return {"selected_final": final, "replacements": replacements,
            "unidentified_tables": unidentified, "skipped_candidates": skipped}


# ----------------------------------------------------------------- building tables

class Builder:
    def __init__(self, pdf_dir: Path = PDF_DIR, src_root: Path = lp.DEFAULT_ROOT, reader=read_pdf_captions):
        self.pdf_dir, self.src_root, self.reader = Path(pdf_dir), Path(src_root), reader
        self._papers: dict = {}
        self._tables: dict = {}

    def paper(self, paper_id: str) -> lt.PaperTables:
        if paper_id not in self._papers:
            self._papers[paper_id] = lt.PaperTables(self.src_root / paper_id / "src")
        return self._papers[paper_id]

    def table(self, paper_id: str, number: int) -> dict:
        key = (paper_id, number)
        if key not in self._tables:
            self._tables[key] = self._build(paper_id, number)
        return self._tables[key]

    def _build(self, paper_id: str, number: int) -> dict:
        pt_src = self.paper(paper_id)
        caps = self.reader(self.pdf_dir / f"{paper_id}.pdf", number)
        ident = lt.identify([lt.normalise_caption(c) for c in caps], pt_src.candidates())
        res = {"paper_id": paper_id, "number": number, "status": ident["status"],
               "identified": ident["status"] == "identified", "matches": ident["matches"],
               "pdf_caption_start": (caps[0][:80] if caps else None), "n_pdf_captions": len(caps),
               "source_problems": list(pt_src.problems), "table": None, "parts": []}
        if not res["identified"]:
            return res
        idx = ident["index"]
        t = pt_src.get(idx)
        res["latex_index"] = idx
        res["latex_caption_start"] = (t["caption_plain"] or "")[:80]
        for pt in pt_src.parse_parts(idx):
            schema = lt.to_schema(pt, t["caption_plain"] or "", number, idx, meta={
                "paper_id": paper_id, "latex_table_index": idx,
                "latex_caption_start": res["latex_caption_start"],
                "pdf_caption_start": res["pdf_caption_start"]})
            res["parts"].append({"suffix": pt.part, "parsed": pt, "table": schema})
        res["parsed"] = res["parts"][0]["parsed"]
        res["table"] = res["parts"][0]["table"]
        return res

    def ok(self, paper_label: str, number: int):
        res = self.table(lp.DEV_PAPERS[paper_label], number)
        if res["identified"]:
            return True, ""
        return False, res["status"]


# ----------------------------------------------------------------- output files

def _cell(v) -> str:
    return str(v).replace("|", "/").replace("\n", " ")


def _md_table(header: list, rows: list) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def render_ref_md(res: dict, part: Optional[dict] = None) -> str:
    part = part or res["parts"][0]
    t = part["table"]
    keys_r = "\n".join(f"- row {k['row']}: {' > '.join(k['path'])}" for k in t["row_keys"])
    keys_c = "\n".join(f"- col {k['col']}: {' > '.join(k['path'])}" for k in t["col_keys"])
    return "\n".join([
        f"# {res['paper_id']} Table {res['number']}{part['suffix']} (reference from LaTeX)", "",
        f"Caption: {t['caption_text']}", "",
        f"LaTeX table index {res['latex_index']}; {t['n_rows']} rows x {t['n_cols']} cols; "
        f"header rows {t['latex_meta']['header_rows']}; multirow {t['latex_meta']['n_multirow']}, "
        f"multicolumn {t['latex_meta']['n_multicolumn']}. Check against the PDF page.", "",
        "Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.", "",
        lt.render_grid_md(t), "", "## Row key paths", keys_r or "(none)", "", "## Column key paths", keys_c or "(none)", ""])


PARSER_FIXES = [
    "1. `\\href{url}{text}` now yields `text` (P5 T3 cells).",
    "3. A table environment with more than one tabular is parsed as sub-tables T<n>a, T<n>b, ... in source order; "
    "each is its own ref file. A pin on such a table takes the first sub-table where it passes.",
    "4. `\\makebox`, `\\framebox`, `\\raisebox` keep their content; `\\put(x,y){c}` keeps c; picture environments are "
    "dropped and flagged \"drawing removed\".",
]
RULE_AMENDMENTS = [
    "2. Relaxed label compare also treats `-`, en dash, em dash and minus sign as one character "
    "(decisions.md 2026-10-29: glyph differences in labels do not count). LaTeX `--` is still rendered as an en dash "
    "in cell text. Lone-dash cells (missing values) are relaxed too.",
    "5. Citation-blind matching for caption identification and for the relaxed label compare, on both sides: "
    "parenthetical groups that contain a year 1900-2099 (optional letter), e.g. `(Hsieh et al., 2024)`, and numeric "
    "brackets such as `[12]` or `[3,4]` are removed (LaTeX `\\cite*` was already dropped). Uniqueness is still required.",
]


def build_report(state: dict) -> str:
    L = ["# T2-R reference tables - build report (2026-10-29)", "",
         f"INR 0. No LLM, no network. Run state: **{state['run_state']}**", ""]
    for r in state["stop_reasons"]:
        L.append(f"- STOP: {r}")
    L += ["", "## Tables", ""]
    rows = []
    for res in state["tables"]:
        pc = state["pin_checks"].get((res["paper_id"], res["number"]))
        parts = res.get("parts") or [None]
        for part in parts:
            p = part["parsed"] if part else None
            t = part["table"] if part else None
            rows.append([
                res["paper_id"], f"{res['number']}{part['suffix'] if part else ''}",
                "y" if res["identified"] else f"n ({res['status']})",
                res["pdf_caption_start"] or "-",
                f"{t['n_rows']}x{t['n_cols']}" if t else "-",
                len(t["latex_meta"]["header_rows"]) if t else "-",
                f"{p.n_multirow}/{p.n_multicolumn}" if p else "-",
                ", ".join("\\" + m for m in p.unknown_macros) or "-" if p else "-",
                ", ".join(p.flags) or "-" if p else "-",
                "; ".join(p.problems) or "-" if p else "-",
                f"{pc['cell'][0]}/{pc['cell'][1]}" if pc else "-",
                f"{pc['structural'][0]}/{pc['structural'][1]}" if pc else "-",
                f"{pc['uncertain'][0]}/{pc['uncertain'][1]}" if pc else "-",
                len(pc["relaxed"]) if pc else "-"])
    L += [_md_table(["paper", "table", "identified", "PDF caption start (<=80)", "rows x cols", "header rows",
                     "multirow/multicolumn", "unknown macros", "flags", "parse problems", "pins cell x/y (certain)",
                     "structural x/y", "uncertain x/y", "relaxed"], rows), ""]

    L += ["## Pin check (gate tables)", ""]
    for key, pc in state["pin_checks"].items():
        L += [f"### {key[0]} Table {key[1]}", ""]
        prow = [[r["id"], r["kind"], "uncertain" if r["key_uncertain"] else ("breaking" if r["breaking"] else "-"),
                 r["status"], r.get("got") or "-", r.get("reason") or "-"] for r in pc["results"]]
        L += [_md_table(["pin", "kind", "class", "status", "got", "reason"], prow), ""]
        if pc["relaxed"]:
            L += ["Pins that needed the relaxed label compare:", ""]
            L += [f"- {r['id']}: labels {r.get('pin_labels')}; strict: {r['strict_reason'] or r.get('strict_got')}" for r in pc["relaxed"]]
            L.append("")
    L += ["## S rows (resolution)", ""]
    sr = state["resolution"]
    if sr:
        L += [f"selected_final: {sr['selected_final']}", ""]
        L += [_md_table(["old", "new", "reason"], [[x["old"], x["new"], x["reason"]] for x in sr["replacements"]])
              if sr["replacements"] else "(no replacements)", ""]
        if sr["skipped_candidates"]:
            L += ["Skipped replacement candidates:", ""]
            L += [f"- {x['row']}: {x['reason']}" for x in sr["skipped_candidates"]]
            L.append("")
        p7 = next((r for r in state["tables"] if r["paper_id"] == lp.DEV_PAPERS["P7"] and r["number"] == 1), None)
        if p7 is not None:
            L += ["P7-S2: " + ("table identified" if p7["identified"] else
                  f"P7 Table 1 not identified ({p7['status']}); replaced by "
                  + next((x["new"] or "none" for x in sr["replacements"] if x["old"] == "P7-S2"), "n/a")
                  + " per entry rule"), ""]
    else:
        L += ["(not computed)", ""]
    L += ["## Parser fixes after run 1", ""] + PARSER_FIXES + [""]
    L += ["## Rule amendments after run 1 (approved by Nitin)", ""] + RULE_AMENDMENTS + [""]
    if state["stop_grids"]:
        L += ["## Grids of failing gate tables", ""]
        for title, grid in state["stop_grids"]:
            L += [f"### {title}", "", grid, ""]
    return "\n".join(L)


# ----------------------------------------------------------------- main

def _safe(s) -> str:
    return str(s).encode("ascii", "replace").decode("ascii")


def run(out_files: bool = True) -> dict:
    pins = lp.load_pins()
    s_rows = lp.load_json(S_ROWS_IN)
    infos = row_infos(lp.load_json(lp.DEV_EVAL), lp.load_json(lp.DEV_MATCH_MAP))
    full = ordered_full_rows(infos)
    expected = [r["row_id"] for r in s_rows["selected"]]
    reproduced = reproduce_selection(full)
    order_ok = reproduced == expected
    stop: list = []
    if not order_ok:
        stop.append(f"order check: reproduced selection {reproduced} != s_rows.json selected {expected}")

    builder = Builder()
    targets: list = []

    def add(paper_id, number):
        if (paper_id, number) not in targets:
            targets.append((paper_id, number))

    for tid, t in pins["gate_tables"].items():
        add(t["paper_id"], t["caption_number"])
    for r in s_rows["selected"]:
        for n in r["tables_cited"]:
            if str(n).isdigit():
                add(lp.DEV_PAPERS[r["paper"]], int(n))
    pool = [x for x in full if x["row_id"] not in expected]
    fallback = next((x for x in pool if x["row_id"] == FALLBACK_ROW), None)
    if fallback is None:
        stop.append(f"fallback row {FALLBACK_ROW} not found in the ordered pool")
    else:
        for n in fallback["tables_cited"]:
            if str(n).isdigit():
                add(lp.DEV_PAPERS[fallback["paper"]], int(n))

    for paper_id, number in targets:
        res = builder.table(paper_id, number)
        print(_safe(f"{paper_id} T{number}: {res['status']}; PDF caption start: {(res['pdf_caption_start'] or '-')[:80]}"))

    pin_checks: dict = {}
    stop_grids: list = []
    gate_keys = set()
    for tid, t in pins["gate_tables"].items():
        key = (t["paper_id"], t["caption_number"])
        gate_keys.add(key)
        res = builder.table(*key)
        if not res["identified"]:
            stop.append(f"gate table {tid} unidentified ({res['status']})")
            continue
        pc = check_table_pins([p["table"] for p in res["parts"]], pins["pins_by_table"].get(tid, []))
        pin_checks[key] = pc
        if pc["mismatches"]:
            stop.append(f"gate table {tid}: {len(pc['mismatches'])} pin(s) not matched: "
                        + ", ".join(r["id"] for r in pc["mismatches"]))
            for p in res["parts"]:
                stop_grids.append((f"{tid}{p['suffix']} (pins failed)", lt.render_grid_md(p["table"])))

    resolution = resolve_s_rows(s_rows, pool, builder.ok)
    # tables a replacement row needs are built on demand by builder.ok; collect everything built
    built = [builder.table(*k) for k in sorted(builder._tables, key=lambda k: (k[0], k[1]))]
    for res in built:
        for part in res.get("parts", []):
            p = part["parsed"]
            if p.problems:
                name = f"{res['paper_id']} T{res['number']}{part['suffix']}"
                stop.append(f"parse problems in {name}: " + "; ".join(p.problems))
                stop_grids.append((f"{name} (parse problems)", lt.render_grid_md(part["table"])))

    run_state = "OK" if not stop else "STOPPED"
    state = {"run_state": run_state, "stop_reasons": stop, "tables": built, "pin_checks": pin_checks,
             "resolution": resolution, "stop_grids": stop_grids}
    if out_files:
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(build_report(state) + "\n", encoding="utf-8")
        print("wrote", REPORT_FILE)
        if not stop:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            n_files = 0
            for res in built:
                for part in res.get("parts", []):
                    base = f"{res['paper_id']}_T{res['number']}{part['suffix']}"
                    lp.dump_json(OUT_DIR / f"{base}.json", part["table"])
                    (OUT_DIR / f"{base}.md").write_text(render_ref_md(res, part), encoding="utf-8")
                    n_files += 1
            out = copy.deepcopy(s_rows)
            out["resolution"] = {**resolution, "order_check": {"ok": order_ok, "reproduced": reproduced, "expected": expected}}
            lp.dump_json(S_ROWS_OUT, out)
            print("wrote", S_ROWS_OUT, "and", n_files, "reference tables")
    print("run state:", run_state)
    for r in stop:
        print(_safe("STOP: " + r[:200]))
    return state


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    state = run()
    return 0 if state["run_state"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
