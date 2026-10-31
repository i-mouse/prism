"""T2-R scorer (decisions.md 2026-10-28 "Auditor v2 (D6+D7)" T2 marks and Needs-review scoring, 2026-10-29
"T2-R", 2026-10-30 "T2-R inputs"). Runs AFTER t2r_check.py has written its result file. This module (not the
checker) reads dev_eval.json, the match map, the run-1 fixtures, the blind keys, the pins and the pin
resolutions. No LLM, no network, no git.

    python -X utf8 -m eval.auditor_v2.t2r_score score --check <check.json> --out <core.json>
    python -X utf8 -m eval.auditor_v2.t2r_score finalize --core A.json --core2 B.json --check A_check.json
        --check2 B_check.json --pytest-exit-code 0 --out-json <results.json> --out-md <results.md>

Step 1 reproduces the run-1 baseline (8 caught of 31 refusal rows) with eval.score_replay's own functions and
label field (ActualClaim.label). If it does not reproduce, the scorer STOPs and scores nothing.

Marks (decisions.md T2, applied to the T2-R reference tables):
  1 Gain: final PS/NS on >= 4 of the 10 misses AND >= 3 of the 5 hard rows (Needs review = not fixed; misses
    with no form = not fixed).
  2 Faithful: a miss counts only if (a) its contradicting cells include a pinned breaking cell (same method as
    t2r_build_refs: relaxed glyph compare, pin resolutions applied), or (b) for an "absent" PS its table has a
    breaking structural or caption pin. Mark 2 is read as: marks 1's two thresholds still hold when only
    faithful misses count. (Mark 1 is the same count without the faithfulness filter.)
  3 S rows: 0 of the 10 selected S rows lowered by the CODE result.
  4 Needs review: <= 2 of the 10 selected S rows set by the CODE result.
  5 New unit tests pass, and two full runs give byte-identical output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_PY_ROOT = Path(__file__).resolve().parents[2]  # Prism.PythonService
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from eval.auditor_v2 import latex_probe as lp  # noqa: E402
from eval.auditor_v2 import t2r_build_refs as br  # noqa: E402
from eval.auditor_v2 import t2r_check as ck  # noqa: E402
from eval.auditor_v2 import table_keys as tk  # noqa: E402
from eval.score_replay import (  # noqa: E402
    DEFAULT_DEV_EVAL_PATH,
    DEFAULT_MATCH_MAP_PATH,
    DEFAULT_RUN1_FIXTURE_DIR,
    resolve_adjudicated_rows,
    score_directory,
)

AUD_DIR = ck.AUD_DIR
BLIND_KEY = AUD_DIR / "t2r_blind_key_2026-10-30.json"
BLIND_ADDENDUM = AUD_DIR / "t2r_blind_key_addendum_2026-10-30.json"
RESULTS_JSON = AUD_DIR / "t2r_results_2026-10-31.json"
RESULTS_MD = AUD_DIR / "t2r_results_2026-10-31.md"

EXPECTED_CAUGHT, EXPECTED_REFUSAL_ROWS = 8, 31
MISS_ROWS = ["P1-R1", "P3-R2", "P4-R1", "P4-R2", "P5-R1", "P5-R2", "P6-R2", "P7-R1", "P8-R2", "P11-R2"]
HARD_ROWS = ["P3-R2", "P4-R2", "P5-R2", "P6-R2", "P11-R2"]
LOWERED = (ck.PARTIAL, ck.NOT_SUPPORTED)


def _row_sort(row_id):
    return lp.row_sort_key(row_id)


# ------------------------------------------------------------------ baseline and labels

def load_baseline():
    rows_r = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR,
                                      row_type="R")
    eff_out, eff_lab = score_directory(rows_r, DEFAULT_RUN1_FIXTURE_DIR, "effective")
    raw_out, raw_lab = score_directory(rows_r, DEFAULT_RUN1_FIXTURE_DIR, "raw")
    caught = sum(1 for o in eff_out.values() if o == "REFUSED")
    caught_raw = sum(1 for o in raw_out.values() if o == "REFUSED")
    misses = sorted((r for r, o in eff_out.items() if o not in ("REFUSED", "NOT_EXTRACTED")), key=_row_sort)
    extraction_misses = sorted((r for r, o in eff_out.items() if o == "NOT_EXTRACTED"), key=_row_sort)
    ok = (len(rows_r) == EXPECTED_REFUSAL_ROWS and caught == EXPECTED_CAUGHT and caught_raw == EXPECTED_CAUGHT
          and misses == sorted(MISS_ROWS, key=_row_sort))
    rows_s = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR,
                                      row_type="S")
    s_out, s_lab = score_directory(rows_s, DEFAULT_RUN1_FIXTURE_DIR, "effective")
    expected = {r.row_id: r.expected_row.expected_label for r in rows_r + rows_s}
    return {
        "ok": ok, "refusal_rows": len(rows_r), "caught_effective": caught, "caught_raw": caught_raw,
        "misses": misses, "extraction_misses": extraction_misses,
        "labels": {**eff_lab, **s_lab}, "expected": expected,
        "label_field": "ActualClaim.label (fixture claim['label']) via eval.score_replay.score_directory",
    }


def load_keys():
    keys = json.loads(BLIND_KEY.read_text(encoding="utf-8"))["items"]
    keys = {k: dict(v) for k, v in keys.items()}
    keys.update({k: dict(v) for k, v in json.loads(BLIND_ADDENDUM.read_text(encoding="utf-8"))["items"].items()})
    return keys


# ------------------------------------------------------------------ pins (mark 2)

_REF_RE = re.compile(r"^(?P<paper>.+)_T(?P<num>\d+)(?P<part>[a-z]?)$")


class Pins:
    def __init__(self):
        data = lp.load_json(lp.PINS_FILE)
        self.tables = data["tables"]
        self.by_table: dict = {}
        for p in data["pins"]:
            self.by_table.setdefault(p["table_id"], []).append(p)
        self.resolutions = br.load_resolutions()
        self._refs: dict = {}

    def table(self, ref):
        if ref not in self._refs:
            path = ck.REFS_DIR / f"{ref}.json"
            self._refs[ref] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        return self._refs[ref]

    def table_id(self, ref):
        m = _REF_RE.match(ref)
        if not m:
            return None
        for t in self.tables:
            if t["paper_id"] == m["paper"] and t["caption_number"] == int(m["num"]):
                return t["table_id"]
        return None

    def check(self, table, pin):
        """(verified, (row, col) or None, status) with the t2r_build_refs pin method (strict -> relaxed
        labels; pin resolutions applied to the value)."""
        value = self.resolutions.get(pin["id"], {}).get("page_value", pin.get("value"))
        p = {**pin, "value": value}
        chk = br.check_pin(table, p)
        verified = chk["status"] in br.OK_STATUSES
        cell = None
        if verified and p["kind"] == "cell":
            for t, pp in ((table, p), (br.relaxed_table(table), br.relaxed_pin(p))):
                k = tk.derive_keys(t)
                if pp.get("key_columns"):
                    r = tk.rows_by_key_columns(t, k, pp["key_columns"], pp["row_key_path"])
                else:
                    r = tk.unique_row(t, k, pp["row_key_path"])
                c = tk.unique_col(t, k, pp["column_key_path"])
                if r is not None and c is not None:
                    cell = (r, c)
                    break
        return verified, cell, chk["status"]


def _describe_pin(pin):
    bits = {k: pin[k] for k in ("match", "contains", "column", "count", "names") if pin.get(k) not in (None, "", [])}
    return f"{pin['kind']} {json.dumps(bits, ensure_ascii=False, sort_keys=True)}".strip()


def faithfulness(item: dict, pins: Pins) -> dict:
    """Mark 2 evidence for one code-PS item."""
    out = {"a_cell_pin_matches": [], "b_structural_pins": [], "structural_pins_for_count_rows": [],
           "faithful": False, "faithful_structural_variant": False}
    # (a) pinned breaking cells among the contradicting cells
    for form in item["forms"]:
        if form["result"] != "contradicted":
            continue
        ref = form["table_ref"]
        table, tid = pins.table(ref), pins.table_id(ref)
        if table is None or tid is None:
            continue
        broken = {(c["row_index"], c["column_index"]) for c in form["breaking_cells"]
                  if c.get("row_index") is not None and c.get("column_index") is not None}
        for pin in pins.by_table.get(tid, []):
            if pin["kind"] == "cell" and pin.get("breaking"):
                verified, cell, status = pins.check(table, pin)
                if verified and cell in broken:
                    out["a_cell_pin_matches"].append({"pin": pin["id"], "table_ref": ref, "row": cell[0],
                                                      "column": cell[1], "pin_status": status,
                                                      "value": ck.Ctx(ref, table).info(*cell)["value"]})
        if form["rule"] == "count_rows":
            for pin in pins.by_table.get(tid, []):
                if pin["kind"] != "cell" and pin.get("breaking") and pins.check(table, pin)[0]:
                    out["structural_pins_for_count_rows"].append({"pin": pin["id"], "table_ref": ref,
                                                                  "pin_fact": _describe_pin(pin)})
    # (b) absent PS: a breaking structural or caption pin on the item's table(s)
    if item["absent_members"] and item["code_result"] == ck.CODE_PS:
        seen = set()
        for form in item["forms"]:
            ref = form["table_ref"]
            table, tid = pins.table(ref), pins.table_id(ref)
            if table is None or tid is None or ref in seen:
                continue
            seen.add(ref)
            for pin in pins.by_table.get(tid, []):
                if pin["kind"] != "cell" and pin.get("breaking"):
                    verified, _, status = pins.check(table, pin)
                    if verified:
                        for member in item["absent_members"]:
                            out["b_structural_pins"].append({"absent_member": member, "pin": pin["id"],
                                                             "table_ref": ref, "pin_fact": _describe_pin(pin),
                                                             "pin_status": status})
    out["faithful"] = bool(out["a_cell_pin_matches"] or out["b_structural_pins"])
    out["faithful_structural_variant"] = bool(out["faithful"] or out["structural_pins_for_count_rows"])
    return out


# ------------------------------------------------------------------ scoring

def _form_summary(f):
    return {"table_ref": f["table_ref"], "rule": f["rule"], "reading": f.get("reading"), "partial": f.get("partial"),
            "result": f["result"], "reason": f["reason"], "breaking_cells": f["breaking_cells"]}


def score(check: dict) -> dict:
    base = load_baseline()
    if not base["ok"]:
        return {"stopped": True, "baseline": {k: v for k, v in base.items() if k not in ("labels", "expected")}}
    keys = load_keys()
    pins = Pins()
    items = []
    for it in check["items"]:
        key = keys[it["id"]]
        row_id, rset = key["row_id"], key["set"]
        run1 = base["labels"].get(row_id)
        final = ck.merge_label(run1, it["code_result"])
        rec = {
            "id": it["id"], "row_id": row_id, "set": rset, "hard": row_id in HARD_ROWS,
            "code_result": it["code_result"], "decided_by": it["decided_by"],
            "forms": [_form_summary(f) for f in it["forms"]],
            "absent_members": it["absent_members"], "other_table_members": it["other_table_members"],
            "caveat_refs": it["caveat_refs"], "ties": it["ties"],
            "run1_label": run1, "final_label": final, "expected_label": base["expected"].get(row_id),
        }
        if rset == "R":
            rec["fixed"] = final in LOWERED
            rec["faithfulness"] = faithfulness(it, pins) if it["code_result"] == ck.CODE_PS else None
            rec["counted_faithful"] = bool(rec["fixed"] and rec["faithfulness"] and rec["faithfulness"]["faithful"])
            rec["counted_faithful_structural_variant"] = bool(
                rec["fixed"] and rec["faithfulness"] and rec["faithfulness"]["faithful_structural_variant"])
        items.append(rec)
    by_row = {i["row_id"]: i for i in items}

    # misses: every miss row, including those with no item or no form
    misses = []
    for row_id in MISS_ROWS:
        rec = by_row.get(row_id)
        run1 = base["labels"].get(row_id)
        misses.append({
            "row_id": row_id, "hard": row_id in HARD_ROWS, "item": rec["id"] if rec else None,
            "has_form": bool(rec and rec["forms"]), "run1_label": run1,
            "code_result": rec["code_result"] if rec else ck.CODE_NONE,
            "final_label": rec["final_label"] if rec else run1,
            "fixed": bool(rec and rec["fixed"]),
            "counted_faithful": bool(rec and rec["counted_faithful"]),
            "counted_faithful_structural_variant": bool(rec and rec["counted_faithful_structural_variant"]),
        })

    def gain(field):
        n = sum(1 for m in misses if m[field])
        hard = sum(1 for m in misses if m[field] and m["hard"])
        return {"misses": n, "hard": hard, "pass": n >= 4 and hard >= 3}

    m1, m2 = gain("fixed"), gain("counted_faithful")
    m2_variant = gain("counted_faithful_structural_variant")

    s_items = [i for i in items if i["set"] == "S"]
    already = [i for i in s_items if i["run1_label"] not in (ck.SUPPORTED, None)]
    live = [i for i in s_items if i["run1_label"] == ck.SUPPORTED]
    no_label = [i["row_id"] for i in s_items if i["run1_label"] is None]
    lowered = [i["id"] for i in live if i["code_result"] == ck.CODE_PS]
    nr = [i["id"] for i in live if i["code_result"] == ck.CODE_NR]
    m3 = {"code_lowered": len(lowered), "ids": lowered, "pass": len(lowered) == 0}
    m4 = {"code_needs_review": len(nr), "ids": nr, "pass": len(nr) <= 2}

    return {
        "stopped": False,
        "baseline": {k: v for k, v in base.items() if k not in ("labels", "expected")},
        "check_forms_sha256": check["forms_sha256"], "check_ref_sha256": check["ref_sha256"],
        "items": items, "misses": misses,
        "s_rows": {"selected": len(s_items), "no_run1_label": no_label, "already_lowered_by_run1": [
            {"id": i["id"], "row_id": i["row_id"], "run1_label": i["run1_label"], "code_result": i["code_result"],
             "final_label": i["final_label"]} for i in already]},
        "marks": {"1": m1, "2": {**m2, "reading": "marks 1 thresholds with only faithful misses counted",
                                 "structural_variant": m2_variant},
                  "3": m3, "4": m4},
        "overall_without_mark_5": bool(m1["pass"] and m2["pass"] and m3["pass"] and m4["pass"]),
    }


# ------------------------------------------------------------------ rendering

def _cells_md(cells):
    out = []
    for c in cells:
        if c.get("column_index") is None:
            out.append(f"{c['table']} row {c['row_index']} `{c['row_key']}`")
        else:
            out.append(f"{c['table']} r{c['row_index']} `{c['row_key']}` | c{c['column_index']} `{c['column_key']}` = {c['value']}")
    return out


def _mark(ok):
    return "PASS" if ok else "FAIL"


def render_md(res: dict) -> str:
    b = res["baseline"]
    L = ["# T2-R results - check forms on LaTeX reference tables (2026-10-31)", "",
         "INR 0. No LLM, no network, no git. Facts only. Forms, refs, pins, keys and labels are the frozen inputs "
         "(tag t2r-inputs-frozen); nothing was edited.", ""]
    if res.get("stopped"):
        L += ["**STOP: the run-1 baseline did not reproduce. No marks scored.**", "",
              f"- refusal rows: {b['refusal_rows']} (expected {EXPECTED_REFUSAL_ROWS}); caught effective "
              f"{b['caught_effective']}, raw {b['caught_raw']} (expected {EXPECTED_CAUGHT}); misses {b['misses']}"]
        return "\n".join(L) + "\n"
    mk = res["marks"]
    L += [f"## Overall: **{res['overall']}**", "",
          "| mark | result | counts |", "|---|---|---|",
          f"| 1 Gain | {_mark(mk['1']['pass'])} | final PS/NS on {mk['1']['misses']} of 10 misses (need >= 4); "
          f"{mk['1']['hard']} of 5 hard rows (need >= 3) |",
          f"| 2 Faithful | {_mark(mk['2']['pass'])} | faithful misses only: {mk['2']['misses']} of 10 (>= 4); "
          f"{mk['2']['hard']} of 5 hard (>= 3). With structural pins also accepted for count_rows: "
          f"{mk['2']['structural_variant']['misses']} / {mk['2']['structural_variant']['hard']} "
          f"({_mark(mk['2']['structural_variant']['pass'])}) |",
          f"| 3 S rows lowered by code | {_mark(mk['3']['pass'])} | {mk['3']['code_lowered']} of 10 (need 0) {mk['3']['ids']} |",
          f"| 4 S rows set to Needs review by code | {_mark(mk['4']['pass'])} | {mk['4']['code_needs_review']} of 10 (need <= 2) {mk['4']['ids']} |",
          f"| 5 Tests and identical runs | {_mark(mk['5']['pass'])} | pytest exit code {mk['5']['pytest_exit_code']}; "
          f"check files identical {mk['5']['check_identical']}; score outputs identical {mk['5']['core_identical']}; "
          f"sha256 check {mk['5']['check_sha256']}, score {mk['5']['core_sha256']} |", "",
          "Mark 2 is read as: mark 1's two thresholds when only faithful misses count (a miss is faithful if (a) a "
          "contradicting cell is a pinned breaking cell, or (b) it is an absent-member PS whose table has a breaking "
          "structural or caption pin). Mark 1 is the same count without that filter.", ""]
    L += ["## Baseline (reproduced before scoring)", "",
          f"- Refusal rows {b['refusal_rows']}; caught {b['caught_effective']} (effective) / {b['caught_raw']} (raw); "
          f"extraction misses (no claim) {len(b['extraction_misses'])}; wrongly affirmed (the 10 misses) {b['misses']}.",
          f"- Label field: {b['label_field']}.", ""]
    L += ["## Per item", "",
          "| C | row | set | forms (table / rule: result) | code result | run-1 | final | expected |",
          "|---|---|---|---|---|---|---|---|"]
    for i in res["items"]:
        forms = "<br>".join(f"{f['table_ref'].split('_')[-1]} / {f['rule']}: {f['result']}" for f in i["forms"]) or "(none)"
        L.append(f"| {i['id']} | {i['row_id']} | {i['set']} | {forms} | {i['code_result']} | {i['run1_label']} | "
                 f"{i['final_label']} | {i['expected_label']} |")
    L += ["", "Decided by: " + "; ".join(f"{i['id']}: {i['decided_by']}" for i in res["items"]), ""]
    L += ["## Breaking cells (every contradicted form)", ""]
    any_break = False
    for i in res["items"]:
        for f in i["forms"]:
            if f["result"] == "contradicted":
                any_break = True
                L += [f"### {i['id']} ({i['row_id']}) {f['table_ref']} {f['rule']}", f"{f['reason']}", ""]
                L += [f"- {x}" for x in _cells_md(f["breaking_cells"])] + [""]
    if not any_break:
        L += ["(none)", ""]
    L += ["## Cannot-check, tie and member notes", ""]
    for i in res["items"]:
        for f in i["forms"]:
            if f["result"] in ("cannot_check", "tie"):
                L.append(f"- {i['id']} {f['table_ref']} {f['rule']}: {f['result']} - {f['reason']}")
        if i["absent_members"]:
            L.append(f"- {i['id']} absent members: {i['absent_members']}")
        if i["other_table_members"]:
            L.append(f"- {i['id']} other-table members: {[m['member'] for m in i['other_table_members']]}")
        if i["caveat_refs"]:
            L.append(f"- {i['id']} caveats: {i['caveat_refs']}")
    L.append("")
    L += ["## The 10 misses", "",
          "| row | hard | form | run-1 | code result | final | fixed | faithful & counted |", "|---|---|---|---|---|---|---|---|"]
    for m in res["misses"]:
        L.append(f"| {m['row_id']} | {'yes' if m['hard'] else ''} | {m['item'] or '(no item)'}{'' if m['has_form'] else ' (no form)'} | "
                 f"{m['run1_label']} | {m['code_result']} | {m['final_label']} | {'yes' if m['fixed'] else 'no'} | "
                 f"{'yes' if m['counted_faithful'] else 'no'} |")
    L += ["", "## The 5 hard rows, one by one", ""]
    by_row = {i["row_id"]: i for i in res["items"]}
    for row_id in HARD_ROWS:
        i = by_row[row_id]
        L += [f"### {row_id} ({i['id']})", f"- Forms: " + ("; ".join(f"{f['table_ref']} {f['rule']}: {f['result']} ({f['reason']})"
                                                               for f in i["forms"]) or "none"),
              f"- Code result: {i['code_result']} ({i['decided_by']}); run-1 {i['run1_label']}; final {i['final_label']}; "
              f"expected {i['expected_label']}"]
        fa = i.get("faithfulness")
        if fa:
            L.append(f"- Faithful (a) pinned breaking cells among contradicting cells: "
                     f"{[(x['pin'], x['value']) for x in fa['a_cell_pin_matches']] or 'none'}")
            for x in fa["b_structural_pins"]:
                L.append(f"- Faithful (b) absent member | pin: `{x['absent_member']}` | {x['pin']} ({x['pin_fact']})")
            if fa["structural_pins_for_count_rows"]:
                L.append(f"- Structural pins for a contradicted count_rows: {[x['pin'] for x in fa['structural_pins_for_count_rows']]}")
            L.append(f"- Counted in mark 2: {'yes' if i['counted_faithful'] else 'no'}")
        L.append("")
    L += ["## Mark 2 evidence for every code PS on a miss", ""]
    for i in res["items"]:
        fa = i.get("faithfulness")
        if i["set"] == "R" and fa:
            L.append(f"- {i['row_id']} ({i['id']}): faithful={fa['faithful']}; cell pins matched "
                     f"{[x['pin'] for x in fa['a_cell_pin_matches']]}; absent-PS pins "
                     f"{[(x['absent_member'], x['pin']) for x in fa['b_structural_pins']]}")
    L.append("")
    L += ["## S rows (10 selected)", "",
          "Counted in marks 3 and 4: rows whose run-1 label is supported (code result changes them). "
          "Rows already lowered by the run-1 auditor are listed apart and are not counted.", "",
          "| C | row | run-1 | code result | final |", "|---|---|---|---|---|"]
    for i in res["items"]:
        if i["set"] == "S":
            L.append(f"| {i['id']} | {i['row_id']} | {i['run1_label']} | {i['code_result']} | {i['final_label']} |")
    L += ["", "Already lowered by run-1: " + (", ".join(f"{x['row_id']} ({x['run1_label']}, code {x['code_result']})"
                                                       for x in res["s_rows"]["already_lowered_by_run1"]) or "none"), ""]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ CLI

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cmd_score(args) -> int:
    check = json.loads(Path(args.check).read_text(encoding="utf-8"))
    res = score(check)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_bytes(ck.dumps(res))
    if res.get("stopped"):
        print("STOP: run-1 baseline did not reproduce:", json.dumps(res["baseline"], ensure_ascii=True))
        return 2
    print("baseline ok; marks:", {k: v.get("pass") for k, v in res["marks"].items()})
    return 0


def cmd_finalize(args) -> int:
    c1, c2 = Path(args.core).read_bytes(), Path(args.core2).read_bytes()
    k1, k2 = Path(args.check).read_bytes(), Path(args.check2).read_bytes()
    res = json.loads(c1.decode("utf-8"))
    if res.get("stopped"):
        Path(args.out_md).write_text(render_md(res), encoding="utf-8")
        print("STOP: baseline did not reproduce")
        return 2
    m5 = {"pytest_exit_code": args.pytest_exit_code, "check_identical": k1 == k2, "core_identical": c1 == c2,
          "check_sha256": _sha(k1), "core_sha256": _sha(c1),
          "pass": args.pytest_exit_code == 0 and k1 == k2 and c1 == c2}
    res["marks"]["5"] = m5
    res["overall"] = "PASS" if res["overall_without_mark_5"] and m5["pass"] else "FAIL"
    Path(args.out_json).write_bytes(ck.dumps(res))
    Path(args.out_md).write_text(render_md(res), encoding="utf-8")
    print("overall:", res["overall"], {k: v.get("pass") for k, v in res["marks"].items()})
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("--check", type=Path, default=ck.CHECK_OUT)
    s.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("finalize")
    f.add_argument("--core", type=Path, required=True)
    f.add_argument("--core2", type=Path, required=True)
    f.add_argument("--check", type=Path, required=True)
    f.add_argument("--check2", type=Path, required=True)
    f.add_argument("--pytest-exit-code", type=int, required=True)
    f.add_argument("--out-json", type=Path, default=RESULTS_JSON)
    f.add_argument("--out-md", type=Path, default=RESULTS_MD)
    args = ap.parse_args(argv)
    return cmd_score(args) if args.cmd == "score" else cmd_finalize(args)


if __name__ == "__main__":
    sys.exit(main())
