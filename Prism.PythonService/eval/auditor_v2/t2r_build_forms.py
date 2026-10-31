"""Assemble + validate the final T2-R check forms. Stdlib + table_keys only.
No LLM, no network, no git. Default run is a dry run (prints validation only);
pass --write to also write the two output files (md is built by write_md.py).
"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(r"H:/Work projects/Prism")
sys.path.insert(0, str(ROOT / "Prism.PythonService"))
from eval.auditor_v2 import table_keys as tk  # noqa: E402

AR = ROOT / "docs/evals/auditor_rd"
RAW = AR / "t2r_forms_raw"
REFS = AR / "t2r_refs"
SEP = " > "
DASH = "\u2013"
OUT_JSON = AR / "t2r_forms_final_2026-10-30.json"

RULES = {"all_cmp", "beats_baseline", "best_in_column", "count_rows", "count_satisfying"}
OPS = {">", ">=", "<", "<=", "=="}

# ------------------------------------------------------------------ files
PAPER_FILES = {
    "2610.10871v1": ("2610.10871v1_chatgpt.txt", "2610.10871v1_gemini.json"),
    "2610.11132v1": ("2610.11132v1_chatgpt.txt", "2610.11132v1_gemini.json"),  # C11 excluded, not used
    "2610.11135v1": ("pack_2610.11135v1_chatgpt.txt", "2610.11135v1_gemini.json"),
    "2610.11291v1": ("pack_2610.11291v1_chatgpt.txt", "2610.11291v1_gemini.json"),
    "2610.11312v1": ("pack_2610.11312v1_chatgpt.txt", "2610.11312v1_gemini.json"),
    "2610.11519v1": ("pack_2610.11519v1_chatgpt.txt", "2610.11519v1_gemini.json"),
    "2610.12114v1": ("2610.12114v1_chatgpt.txt", "2610.12114v1_gemini.json"),
    "2610.12124v1": ("pack_2610.12124v1_chatgpt.txt", "gemini_2610.12124v1_medium.json"),
    "2610.12375v1": ("pack_2610.12375v1_chatgpt.txt", "gemini_2610.12375v1_medium.json"),
}
EXTRA_FILES = ["chatgpt_C18.json", "gemini_C18.json", "wording_chatgpt.json", "wording_gemini.json"]

TEXT, LOAD, STATUS = {}, {}, {}


def load_file(name):
    p = RAW / name
    if not p.exists():
        return None, "MISSING"
    t = p.read_text(encoding="utf-8")
    TEXT[name] = t
    try:
        return json.loads(t), "ok"
    except json.JSONDecodeError:
        pass
    t2 = t.replace("\u201c", '"').replace("\u201d", '"')
    try:
        return json.loads(t2, strict=False), "ok after curly-quote repair"
    except json.JSONDecodeError as e:
        err = str(e)
    # salvage complete form objects from a truncated file
    forms, dec = [], json.JSONDecoder()
    i = t.find('"forms"')
    if i >= 0:
        i = t.find("[", i) + 1
        while True:
            while i < len(t) and t[i] in " \r\n\t,":
                i += 1
            try:
                obj, i = dec.raw_decode(t, i)
            except json.JSONDecodeError:
                break
            forms.append(obj)
    return None, f"unparsable ({err[:60]}); {len(forms)} complete forms salvageable"


def judge_group(fname, iid):
    it = next(x for x in LOAD[fname] if x["id"] == iid)
    return [dict(member=g["member"], status=g["status"]) for g in it["claimed_group"]]


# ------------------------------------------------------------------ refs
class Ref:
    def __init__(self, stem):
        self.stem = stem
        self.t = json.loads((REFS / f"{stem}.json").read_text(encoding="utf-8"))
        self.k = tk.derive_keys(self.t)

    def rows(self, pred=lambda p: True):
        return [SEP.join(p) for _, p in sorted(self.k.row_paths.items()) if pred(p)]

    def datacols(self):
        return {c: p for c, p in self.k.col_paths.items() if c not in self.k.label_cols and p}

    def cols(self, pred=lambda p: True):
        return [SEP.join(p) for c, p in sorted(self.datacols().items()) if pred(p)]


REF = {}


def ref(stem):
    if stem not in REF:
        REF[stem] = Ref(stem)
    return REF[stem]


# ------------------------------------------------------------------ resolution
def fold(s):
    s = tk.normalize_label(s)
    for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
        s = s.replace(ch, "-")
    return s.replace("\u2192", "->").replace("\u2190", "<-")


def res_row(r, pathstr):
    path = pathstr.split(SEP)
    hit = tk.rows_by_path(r.t, r.k, path)
    if len(hit) == 1:
        return hit[0], False
    paths = {i: [fold(x) for x in p] for i, p in r.k.row_paths.items()}
    hit = tk._unique_match(paths, [fold(x) for x in path])
    return (hit[0], True) if len(hit) == 1 else (None, False)


def res_col(r, pathstr):
    path = pathstr.split(SEP)
    c = tk.unique_col(r.t, r.k, path)
    if c is not None:
        return c, False
    paths = {c: [fold(x) for x in p] for c, p in r.datacols().items()}
    hit = tk._unique_match(paths, [fold(x) for x in path])
    return (hit[0], True) if len(hit) == 1 else (None, False)


def res_keycol(r, label):
    c = tk.key_column(r.t, r.k, label)
    if c is not None:
        return c, False
    leaf = {c: [fold(p[-1])] for c, p in r.k.col_paths.items() if p}
    hit = tk._unique_match(leaf, [fold(label)])
    return (hit[0], True) if len(hit) == 1 else (None, False)


def res_selector(r, sel):
    rows = tk.rows_matching(r.t, r.k, sel)
    if rows is not None and len(rows) == 1:
        return rows[0], False
    cols = {}
    for label in sel:
        c, _ = res_keycol(r, label)
        if c is None:
            return None, False
        cols[label] = c
    hit = [
        row for row in r.k.data_rows
        if all(fold(tk.cell_text(r.t, r.k, row, cols[l]) or "") == fold(v) for l, v in sel.items())
    ]
    return (hit[0], True) if len(hit) == 1 else (None, False)


def res_excluded(r, pathstr):
    """Unique row path, else a group label shared by >=1 rows."""
    i, rel = res_row(r, pathstr)
    if i is not None:
        return 1, rel, False
    n = sum(1 for p in r.k.row_paths.values() if fold(pathstr) in [fold(x) for x in p])
    return n, False, True


# ------------------------------------------------------------------ builders
def P(**kw):
    base = dict(op=None, constant=None, polarity=None, tolerance=0, k=None, pairs=[], count=None, distinct_on=[])
    base.update(kw)
    return base


def pair(m, b):
    return {"method": m, "baseline": b}


def uniq(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def F(tref, rule, reading, rows=(), rbc=(), cols=(), params=None, excl=(), partial=False):
    return dict(table_ref=tref, rule=rule, reading=reading, rows=list(rows), rows_by_columns=list(rbc),
                columns=list(cols), params=params or P(), excluded_rows=list(excl), partial=partial)


def BB(tref, reading, pairs, cols, excl=(), partial=False):
    """beats_baseline: selected rows = every row named in a pair."""
    rows = uniq([x for p in pairs for x in (p["method"], p["baseline"]) if isinstance(x, str)])
    rbc = uniq([x for p in pairs for x in (p["method"], p["baseline"]) if isinstance(x, dict)])
    return F(tref, "beats_baseline", reading, rows=rows, rbc=rbc, cols=cols,
             params=P(op=">", polarity="higher", pairs=pairs), excl=excl, partial=partial)


def AC(tref, reading, rows, cols, op, const, tol=0, excl=(), partial=False, rbc=()):
    return F(tref, "all_cmp", reading, rows=rows, rbc=rbc, cols=cols,
             params=P(op=op, constant=const, tolerance=tol), excl=excl, partial=partial)


# ------------------------------------------------------------------ items
def build_items():
    items = []

    def item(iid, paper, forms, group, caveats=(), nrr="", note=""):
        items.append(dict(id=iid, paper=paper, forms=forms, claimed_group=group,
                          caveat_refs=list(caveats), no_rule_reason=nrr, source_note=note))

    # ---- C01
    t9 = ref("2610.11135v1_T9")
    blocks = uniq([p[0] for p in t9.k.row_paths.values() if len(p) == 2])
    pairs = [pair(f"{b}{SEP}JevKT", f"{b}{SEP}Best deep KT\u2020") for b in blocks]
    item("C01", "2610.11135v1",
         [BB("2610.11135v1_T9", "narrow", pairs, ["Mean"],
             excl=[f"{b}{SEP}Jev0-shot (N=0)" for b in blocks], partial=True)],
         judge_group("pack_2610.11135v1_chatgpt.txt", "C01"),
         ["Table 9 caption: Position 1 has only 41\u201350 targets per dataset, so its AUC is noisy"],
         note="Narrow Mean form agreed by both judges (ChatGPT pack_2610.11135v1_chatgpt.txt, Gemini "
              "2610.11135v1_gemini.json); 6 Position blocks, JevKT vs Best deep KT, strict, higher. "
              "Member 'unseen items, all learners logged (P3)' lives in Table 10.")

    # ---- C02
    t2 = "2610.11519v1_T2"
    FR, SV, RC, RR, DL, VO = ("Full RA (\u03bb)", "w/o student value baseline (\u03b3x)", "w/o response centering (\u03bb)",
                              "Raw residual (w/o both, \u03b3 raw)", "Direct L2 loss (\u03b1)", "Verifier only (REINFORCE++)")
    w6 = ref(t2).cols(lambda p: len(p) == 2)
    item("C02", "2610.11519v1",
         [BB(t2, "only", [pair(v, VO) for v in (FR, SV, RC, RR)], w6, excl=[DL]),
          BB(t2, "only", [pair(FR, b) for b in (SV, RC, RR, DL, VO)], w6)],
         judge_group("pack_2610.11519v1_chatgpt.txt", "C02"), [],
         note="ChatGPT round-2 forms (A) and (B) from pack_2610.11519v1_chatgpt.txt. Verifier only row is a "
              "column-spanning cell (cs=3) and must resolve at every weight column.")

    # ---- C03
    t = "2610.12124v1_T2"
    dcols = [f"ALFWorld \u2192 ScienceWorld{SEP}\u0394 stream", f"HotpotQA \u2192 FEVER{SEP}\u0394 stream"]
    f03 = [AC(t, "only", [m], dcols, ">", 0, excl=["Plain"]) for m in ("Hippocam", "ACE")]
    for m in ("HiAgent", "mem0", "A-Mem", "Letta", "ReasoningBank"):
        f03.append(F(t, "count_satisfying", "only", rows=[m], cols=dcols,
                     params=P(op="<=", constant=0, k=1), excl=["Plain"]))
    item("C03", "2610.12124v1", f03, judge_group("pack_2610.12124v1_chatgpt.txt", "C03"), [],
         note="ChatGPT round-2 encoding accepted (logically equivalent to the Gemini re-run form). "
              "count_satisfying = at least k=1 of the 2 \u0394 stream cells <= 0. Plain has no \u0394 values.")

    # ---- C04
    t = "2610.10871v1_T9"
    sel = lambda cp, na: {"Setting": "SeerAttention", "Clip p": cp, "Norm \u03b1": na}
    base = sel(DASH, DASH)
    p4 = [pair(sel(c, DASH), base) for c in ("85", "90", "95")]
    rbc = [base] + [p["method"] for p in p4]
    item("C04", "2610.10871v1",
         [F(t, "count_satisfying", "only", rbc=rbc, cols=["Avg."],
            params=P(op=">", polarity="higher", k=1, pairs=p4),
            excl=["MInference", "FlexPrefill-Llama", "FlexPrefill-Qwen"], partial=True)],
         judge_group("2610.10871v1_chatgpt.txt", "C04"), [],
         note="ChatGPT round-2 count_satisfying form (k=1 of 3 Clip p comparisons vs raw MASA row, Avg., "
              "strict, higher). Excluded rows are setting-group labels (several rows each).")

    # ---- C05
    item("C05", "2610.11312v1", [],
         judge_group("pack_2610.11312v1_chatgpt.txt", "C05"), [],
         nrr="Portability and variation claims are qualitative.",
         note="No form: wording judges read 'twelve VLMs' as the main evaluation (Table 3), not Table 10.")

    # ---- C06
    c1 = ["4K", "8K", "16K", "32K", "64K", "128K", "Avg."]
    t2c = ref("2610.10871v1_T2")
    c2 = t2c.cols(lambda p: p[-1] not in ("\u0394Full",))
    assert len(c2) == 11, c2
    g06 = judge_group("2610.10871v1_chatgpt.txt", "C06")
    for g in g06:
        if "latency" in g["member"].lower():
            g["status"] = "other_table: Figure 2"
    g06.append(dict(member="Matched average gains on LongBench for SeerAttention", status="other_table: Table 3"))
    fa = lambda r, m: [x for x in r.rows() if x.endswith(f"{SEP}Full Attention")]
    r1, r2 = ref("2610.10871v1_T1"), ref("2610.10871v1_T2")
    mk = lambda m: pair(f"{m}{SEP}MASA", f"{m}{SEP}Original")
    item("C06", "2610.10871v1",
         [BB("2610.10871v1_T1", "broad", [mk(m) for m in ("MInfer", "SeerAttn", f"FlexPrefill{SEP}Llama", f"FlexPrefill{SEP}Qwen")],
             c1, excl=fa(r1, 0), partial=True),
          BB("2610.10871v1_T2", "broad", [mk(m) for m in ("MInfer", f"FlexPrefill{SEP}Llama", f"FlexPrefill{SEP}Qwen")],
             c2, excl=fa(r2, 0), partial=True)],
         g06, [],
         note="Reading (b) every column (Nitin; wording judges split ChatGPT b / Gemini a). Forms from ChatGPT "
              "2610.10871v1_chatgpt.txt with columns widened from Avg. to every score column; \u0394Full excluded.")

    # ---- C07
    t1a, t1b = "2610.11312v1_T1a", "2610.11312v1_T1b"
    F1 = ["Task-Space Review" + SEP + "F1\u2191"]
    base3 = ["DeepSeek-V4-Flash", "Qwen3.5-9B", "MedGemma-27B"]
    g07 = judge_group("2610.11312v1_gemini.json", "C07")
    item("C07", "2610.11312v1",
         [AC(t1a, "only", ["MedBenchAgent"], F1, "==", 90.9, 0.05),
          BB(t1a, "only", [pair("MedBenchAgent", b) for b in base3 + ["DeepSeek-V4-Flash + T0"]], F1),
          AC(t1a, "only", base3, F1, ">=", 79.2, 0.05),
          AC(t1a, "only", base3, F1, "<=", 80.0, 0.05),
          AC(t1a, "only", ["DeepSeek-V4-Flash + T0"], F1, "==", 85.1, 0.05),
          AC(t1b, "only", ["All criteria"], ["Pass"], "==", 994, 0.5),
          AC(t1b, "only", ["All criteria"], ["Fail"], "==", 6, 0.5)],
         g07, [], note="ChatGPT forms (pack_2610.11312v1_chatgpt.txt; Gemini lacks the Fail cell), partial: "
                       "'correctly identified tasks' not encodable. T1b is the PDF's Table 2.")
    for f in items[-1]["forms"]:
        f["partial"] = True

    # ---- C08
    t = "2610.12375v1_T6"
    item("C08", "2610.12375v1",
         [AC(t, "only", ["0.60"], ["Cost saved"], "==", 18, 1),
          AC(t, "only", ["0.60"], ["Prec. (dep.)"], "==", 83, 0.5)],
         judge_group("pack_2610.12375v1_chatgpt.txt", "C08"),
         ["Section 6.3: 0.60 is an illustrative threshold selected for exposition after the sweep"],
         note="Both judges agree (ChatGPT pack_2610.12375v1_chatgpt.txt; Gemini re-run gemini_2610.12375v1_medium.json).")

    # ---- C09 / C12
    t = "2610.11291v1_T3"
    allrows = ref(t).rows()
    assert len(allrows) == 17
    g09 = judge_group("2610.11291v1_gemini.json", "C09")
    assert not any("common" in g["member"].lower() for g in g09)
    item("C09", "2610.11291v1",
         [F(t, "count_rows", "only", rows=allrows, params=P(op="==", count=17), partial=True),
          F(t, "count_rows", "only", rows=allrows, params=P(op="==", count=2, distinct_on=["Mode"]), partial=True)],
         g09, [], note="Gemini forms (pack_2610.11291v1_chatgpt.txt is not valid JSON, curly quotes; not parsed). "
                       "'most commonly used' is not a claimed-group member. distinct_on resolves via leaf header.")
    item("C12", "2610.11291v1",
         [F(t, "count_rows", "only", rows=allrows, params=P(op="==", count=17), partial=True)],
         judge_group("2610.11291v1_gemini.json", "C12"), [],
         note="Gemini form; correlation part of the claim is not encodable.")

    # ---- C10
    item("C10", "2610.11135v1",
         [AC("2610.11135v1_T1", "only", [], ["Avg"], "==", 0.706, 0.0005, rbc=[{"N": "0", "Method": "Jev0-shot"}])],
         judge_group("pack_2610.11135v1_chatgpt.txt", "C10"), [],
         note="Both judges; selector {N: 0, Method: Jev0-shot} because row key 0 is not unique.")

    # ---- C13
    t4 = "2610.11519v1_T4"
    r4 = ref(t4)
    item("C13", "2610.11519v1",
         [AC(t4, "broad", r4.rows(), r4.cols(), "<", 0, partial=True),
          BB(t2, "broad", [pair(FR, SV), pair(FR, RC)], w6, excl=[RR, DL, VO], partial=True)],
         judge_group("pack_2610.11519v1_chatgpt.txt", "C13"),
         ["Table 4 caption: slightly helps sampled OPD but lowers both students trained with the verifier"],
         note="ChatGPT forms; wording judges (both): all methods, so all 7 columns of Table 4. Member 'log ratio' is in Table 3.")

    # ---- C14
    t = "2610.12114v1_T3"
    g14 = judge_group("2610.12114v1_chatgpt.txt", "C14")
    g14.append(dict(member="Knowledge-distillation methods in evaluated settings other than Pro\u2192Qwen", status="absent"))
    item("C14", "2610.12114v1",
         [BB(t, "broad", [pair("UTT (Ours)", b) for b in ("SeqKD", "Fine-tune-CoT", "RSR", "LUFFY")],
             ref(t).cols(), excl=["Student"], partial=True)],
         g14, ["Table 3 caption: Comparison with KD methods under the Pro\u2192Qwen setting"],
         note="ChatGPT form (2610.12114v1_chatgpt.txt). Other KD settings checked by Nitin in Tables 3 and 6: absent.")

    # ---- C15
    t10 = "2610.11519v1_T10"
    r10 = ref(t10)
    ra_opd = r10.rows(lambda p: p[1].startswith("RA+") and p[1].endswith(" - OPD"))
    co_ra = r10.rows(lambda p: p[1].startswith("Co-RA+") and p[1].endswith((" - RA+REINFORCE++", " - RA+GRPO")))
    ra_x = r10.rows(lambda p: p[1] in ("RA+REINFORCE++ - REINFORCE++", "RA+GRPO - GRPO"))
    assert len(ra_opd) == len(co_ra) == len(ra_x) == 4
    oth = lambda sel: [r for r in r10.rows() if r not in sel]
    dav, dpa = "\u0394 Avg@8", "\u0394 Pass@8"
    item("C15", "2610.11519v1",
         [AC(t10, "only", ra_opd, [dav, dpa], ">", 0, excl=oth(ra_opd)),
          AC(t10, "only", co_ra, [dav], ">=", 1.0, 0.05, excl=oth(co_ra)),
          AC(t10, "only", co_ra, [dav], "<=", 1.5, 0.05, excl=oth(co_ra))],
         judge_group("pack_2610.11519v1_chatgpt.txt", "C15"), [],
         note="ChatGPT forms (reading a: the two RA combinations vs Co-RA are separate groups). Excluded = all other T10 rows.")

    # ---- C16
    g = "Avg."
    item("C16", "2610.10871v1",
         [BB("2610.10871v1_T1", "only", [mk(m) for m in ("MInfer", "SeerAttn", f"FlexPrefill{SEP}Llama", f"FlexPrefill{SEP}Qwen")],
             [g], excl=fa(r1, 0)),
          BB("2610.10871v1_T2", "only", [mk(m) for m in ("MInfer", f"FlexPrefill{SEP}Llama", f"FlexPrefill{SEP}Qwen")],
             [g], excl=fa(r2, 0)),
          BB("2610.10871v1_T3", "only", [pair("MASA", "Original")], [g], excl=["Full Attention"])],
         judge_group("2610.10871v1_chatgpt.txt", "C16"), [],
         note="ChatGPT forms (2610.10871v1_chatgpt.txt): 4 + 3 + 1 matched Original vs MASA pairs on Avg.")

    # ---- C17
    rx = ra_x
    item("C17", "2610.11519v1",
         [AC(t10, "only", rx, [dav, dpa], ">", 0, excl=oth(rx), partial=True),
          AC(t10, "only", rx, [dav], ">=", 1.7, 0.05, excl=oth(rx), partial=True),
          AC(t10, "only", rx, [dav], "<=", 3.6, 0.05, excl=oth(rx), partial=True),
          AC(t10, "only", rx, [dpa], ">=", 3.9, 0.05, excl=oth(rx), partial=True),
          AC(t10, "only", rx, [dpa], "<=", 6.3, 0.05, excl=oth(rx), partial=True)],
         judge_group("pack_2610.11519v1_chatgpt.txt", "C17"), [],
         note="ChatGPT bound forms; the '> 0' form is added per decision (ChatGPT had only the bounds). "
              "'24 benchmark-level comparisons' lives in Table 1.")

    # ---- C18
    t30 = "2610.11519v1_T30"
    ad = ["Adapter, 1.7B + REINFORCE++", "Adapter, 1.7B + GRPO", "Adapter, 4B + REINFORCE++", "Adapter, 4B + GRPO"]
    item("C18", "2610.11519v1",
         [BB(t30, "narrow", [pair("Frozen q0", a) for a in ad], ["Macro" + SEP + "Avg@8", "Macro" + SEP + "Pass@8"],
             partial=True)],
         judge_group("chatgpt_C18.json", "C18"), [],
         note="Both judges (chatgpt_C18.json; gemini_C18.json truncated, forms only). Frozen teacher is the "
              "method (claim: adapted teachers score below it). Gap range 0.8\u20132.3 / 0.7\u20133.5 not encodable.")
    items.sort(key=lambda i: i["id"])
    return items


# ------------------------------------------------------------------ validation
EXPECT_GROUP = {
    "C01": {"unseen items": "other_table: Table 10"},
    "C04": {"raw MASA for FlexPrefill-Llama": "absent", "additional FlexPrefill settings": "other_table: Table 10"},
    "C05": {"BreastGPT": "other_table: Table 3"},
    "C06": {"latency": "other_table: Figure 2", "LongBench": "other_table: Table 3"},
    "C13": {"log ratio": "other_table: Table 3"},
    "C14": {"One-shot": "other_table: Table 2", "other than Pro": "absent"},
    "C17": {"24 benchmark": "other_table: Table 1"},
    "C18": {"1.7B-Base student improvement": "other_table: Table 1"},
}
CAVEAT_PHRASES = {
    "C01": ("pack_2610.11135v1_chatgpt.txt", "2610.11135v1_gemini.json", "41\u201350 targets per dataset, so its AUC is noisy"),
    "C08": ("pack_2610.12375v1_chatgpt.txt", "gemini_2610.12375v1_medium.json", "illustrative threshold"),
    "C13": ("pack_2610.11519v1_chatgpt.txt", None, "slightly helps sampled OPD but lowers both students trained with the verifier"),
    "C14": ("2610.12114v1_chatgpt.txt", None, "Comparison with KD methods under the Pro\u2192Qwen setting"),
}


def validate(items):
    problems, relaxed, notes = [], [], []

    def chk_row(r, s, where):
        i, rel = res_row(r, s)
        if i is None:
            problems.append(f"{where}: row path not resolved/unique: {s!r}")
        elif rel:
            relaxed.append(f"{where}: row {s!r}")
        return i

    def chk_col(r, s, where):
        c, rel = res_col(r, s)
        if c is None:
            problems.append(f"{where}: column path not resolved/unique: {s!r}")
        elif rel:
            relaxed.append(f"{where}: col {s!r}")
        return c

    def chk_sel(r, s, where):
        i, rel = res_selector(r, s)
        if i is None:
            problems.append(f"{where}: selector not resolved/unique: {s!r}")
        elif rel:
            relaxed.append(f"{where}: selector {s!r}")
        return i

    def chk_cell(r, i, c, where, what):
        if i is None or c is None:
            return
        txt = tk.cell_text(r.t, r.k, i, c)
        if txt is None or not txt.strip():
            problems.append(f"{where}: no/blank cell at {what}")

    ids = [it["id"] for it in items]
    if len(items) != 17 or ids != ["C%02d" % n for n in list(range(1, 11)) + list(range(12, 19))]:
        problems.append(f"item ids wrong: {ids}")

    n_pins = 0
    for it in items:
        for fi, f in enumerate(it["forms"]):
            where = f"{it['id']}.f{fi}"
            r = ref(f["table_ref"])
            p = f["params"]
            if f["rule"] not in RULES:
                problems.append(f"{where}: rule {f['rule']} not in allowlist")
            if p["op"] is not None and p["op"] not in OPS:
                problems.append(f"{where}: op {p['op']}")
            if p["polarity"] not in (None, "higher", "lower"):
                problems.append(f"{where}: polarity {p['polarity']}")
            rule = f["rule"]
            need = {"all_cmp": f["columns"] and (f["rows"] or f["rows_by_columns"]) and p["op"] and p["constant"] is not None,
                    "beats_baseline": p["pairs"] and p["polarity"] and p["op"] and f["columns"],
                    "count_rows": p["op"] and p["count"] is not None and f["rows"],
                    "count_satisfying": p["op"] and p["k"] and f["columns"] and (f["rows"] or f["rows_by_columns"])
                    and (p["constant"] is not None or p["pairs"])}.get(rule, True)
            if not need:
                problems.append(f"{where}: missing params for {rule}")
            rows = [chk_row(r, s, where) for s in f["rows"]]
            sels = [chk_sel(r, s, where) for s in f["rows_by_columns"]]
            cols = [chk_col(r, s, where) for s in f["columns"]]
            for s in f["excluded_rows"]:
                n, rel, grp = res_excluded(r, s)
                if n == 0:
                    problems.append(f"{where}: excluded row not found: {s!r}")
                elif grp:
                    notes.append(f"{where}: excluded {s!r} is a group label ({n} rows)")
                elif rel:
                    relaxed.append(f"{where}: excluded {s!r}")
            for d in p["distinct_on"]:
                c, rel = res_keycol(r, d)
                if c is None:
                    problems.append(f"{where}: distinct_on {d!r} not found")
                elif rel:
                    relaxed.append(f"{where}: distinct_on {d!r}")
            sel_idx = [x for x in rows + sels]
            # cell existence for every (row,col) used
            for ri in sel_idx:
                for ci in cols:
                    chk_cell(r, ri, ci, where, f"r{ri} c{ci}")
            for pr in p["pairs"]:
                for side in ("method", "baseline"):
                    x = pr[side]
                    ri = chk_sel(r, x, where) if isinstance(x, dict) else chk_row(r, x, where)
                    for ci in cols:
                        chk_cell(r, ri, ci, where, f"pair {side} r{ri} c{ci}")
            n_pins += len(f["rows"]) + len(f["rows_by_columns"]) + len(f["columns"]) + 2 * len(p["pairs"])
        # group expectations
        for sub, st in EXPECT_GROUP.get(it["id"], {}).items():
            hit = [g for g in it["claimed_group"] if sub.lower() in g["member"].lower()]
            if len(hit) != 1 or hit[0]["status"] != st:
                problems.append(f"{it['id']}: group member {sub!r} expected {st}, got {hit}")
        if it["id"] in CAVEAT_PHRASES:
            fa_, fb_, phrase = CAVEAT_PHRASES[it["id"]]
            if not any(phrase in TEXT.get(x, "") for x in (fa_, fb_) if x):
                problems.append(f"{it['id']}: caveat phrase not found in judge files: {phrase!r}")
        want = 4 if it["id"] in ("C01", "C08", "C13", "C14") else 0
        if (len(it["caveat_refs"]) > 0) != (want > 0):
            problems.append(f"{it['id']}: caveat_refs mismatch")
    return problems, relaxed, notes, n_pins


def main():
    print("== files ==")
    for paper, (cg, gm) in PAPER_FILES.items():
        for name in (cg, gm):
            d, st = load_file(name)
            LOAD[name] = d
            STATUS[name] = st
            print(f"  {paper:14s} {name:38s} {st}")
    for name in EXTRA_FILES:
        d, st = load_file(name)
        LOAD[name] = d
        STATUS[name] = st
        print(f"  {'extra':14s} {name:38s} {st}")
    missing = [n for n, s in STATUS.items() if s == "MISSING"]
    if missing:
        print("MISSING:", missing)
        sys.exit(2)
    items = build_items()
    problems, relaxed, notes, n_pins = validate(items)
    print(f"\n== validation == items={len(items)} forms={sum(len(i['forms']) for i in items)} pins checked={n_pins}")
    print("relaxed-glyph pins:", relaxed or "none")
    print("notes:", *notes, sep="\n  ")
    print("problems:", *(problems or ["none"]), sep="\n  ")
    if problems:
        sys.exit(1)
    if "--write" in sys.argv:
        OUT_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote", OUT_JSON)
        sys.path.insert(0, str(Path(__file__).parent))
        from write_md import write_md
        files = [(p_, f"ChatGPT {c} [{STATUS[c]}]; Gemini {g} [{STATUS[g]}]") for p_, (c, g) in PAPER_FILES.items()]
        files += [(n, STATUS[n]) for n in EXTRA_FILES]
        stats = (f"- Items {len(items)}, forms {sum(len(i['forms']) for i in items)}, pins checked {n_pins}; "
                 f"every row/column/selector pin resolves uniquely via table_keys tiers; problems: none.")
        write_md(AR / "t2r_adjudication_2026-10-30.md", items, files, stats, relaxed)
        print("wrote adjudication md")


if __name__ == "__main__":
    main()
