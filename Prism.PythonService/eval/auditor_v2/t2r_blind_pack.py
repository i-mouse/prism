"""T2-R blind claim pack (decisions.md 2026-10-28 row classes; 2026-10-29 "T2-R first").

Free, no LLM, no network, no PDFs opened. Builds the 17-item blind pack for the dual-label route:
claim text (verbatim) + reference table(s) copied from docs/evals/auditor_rd/t2r_refs/, under neutral ids
C01..C17 in a seeded shuffle, plus a key file that maps ids back to rows (NOT for labellers).
Run from Prism.PythonService:

    .venv\\Scripts\\python.exe -I eval/auditor_v2/t2r_blind_pack.py
"""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

_PY_ROOT = Path(__file__).resolve().parents[2]  # Prism.PythonService
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from eval.auditor_v2 import latex_probe as lp  # noqa: E402

REPO_ROOT = _PY_ROOT.parent
AUD_DIR = REPO_ROOT / "docs" / "evals" / "auditor_rd"
REFS_DIR = AUD_DIR / "t2r_refs"
S_ROWS_FILE = AUD_DIR / "t2r_s_rows_2026-10-29.json"
PACK_FILE = AUD_DIR / "t2r_blind_pack" / "pack.md"
KEY_FILE = AUD_DIR / "t2r_blind_key_2026-10-30.json"
SEED = 20261030

# Miss rows of class T or C (decisions.md "Auditor v2 (D6+D7)", row classes): row -> (class, tables).
# F/P rows (P5-R1, P7-R1, P8-R2) are excluded.
MISS_ROWS = {
    "P1-R1": ("T", ["4"]),
    "P3-R2": ("T", ["9"]),
    "P4-R1": ("T", ["1", "2"]),
    "P4-R2": ("T", ["9"]),
    "P5-R2": ("T", ["3"]),
    "P6-R2": ("T", ["10"]),
    "P11-R2": ("C", ["3"]),
}

BANNED_WORDS = ["refused", "supported", "partially", "miss", "gate", "suspect", "trusted"]
ROW_ID_RE = re.compile(r"P\d+-[RS]\d+")


def fail(msg: str) -> None:
    print("FAIL: " + msg)
    sys.exit(1)


def find_row(dev_eval: dict, row_id: str):
    for paper in dev_eval["papers"]:
        for r in lp._iter_rows(paper):
            if r.get("id") == row_id:
                return paper, r
    fail(f"row {row_id} not found in dev_eval.json")


def derived_tables(row: dict) -> list:
    """Same rule as t2r_build_refs.row_infos: scoring_notes first, then evidence sections."""
    cited = lp.extract_table_refs(str(row.get("scoring_notes") or ""))
    for t in lp.extract_table_refs(lp._evidence_text(row)):
        if t not in cited:
            cited.append(t)
    return cited


def table_parts(arxiv: str, number: str) -> list:
    """[(label, path)] for a table number. Sub-tables T<n>a, T<n>b ... -> 'Table n, part a'."""
    exact = REFS_DIR / f"{arxiv}_T{number}.md"
    if exact.exists():
        return [(f"Table {number}", exact)]
    subs = sorted(REFS_DIR.glob(f"{arxiv}_T{number}[a-z].md"))
    if not subs:
        fail(f"no reference file for {arxiv} table {number}")
    return [(f"Table {number}, part {p.stem[-1]}", p) for p in subs]


def split_ref_md(path: Path) -> dict:
    """Caption line, Flags legend and everything from the grid header to the end of the file."""
    lines = path.read_text(encoding="utf-8").split("\n")
    caption = next((x for x in lines if x.startswith("Caption:")), None)
    flags = next((x for x in lines if x.startswith("Flags:")), None)
    start = next((i for i, x in enumerate(lines) if x.startswith("| r | f |")), None)
    if caption is None or flags is None or start is None:
        fail(f"unexpected layout in {path.name}")
    grid = "\n".join(lines[start:]).rstrip("\n")
    return {"caption": caption, "flags": flags, "grid": grid}


def main() -> int:
    dev_eval = lp.load_json(lp.DEV_EVAL)
    s_rows = lp.load_json(S_ROWS_FILE)
    s_ids = list(s_rows["resolution"]["selected_final"])
    file_tables = {r["row_id"]: r["tables_cited"] for r in s_rows["selected"]}
    labels = sorted({str(r.get("expected_label")).lower()
                     for p in dev_eval["papers"] for r in lp._iter_rows(p) if r.get("expected_label")})

    # canonical item list: miss rows in listed order, then S rows in selected_final order
    items = []
    for row_id, (cls, tables) in MISS_ROWS.items():
        paper, row = find_row(dev_eval, row_id)
        if row.get("expected_label") == "supported":
            fail(f"{row_id} is a supported row, expected a miss row")
        items.append({"row_id": row_id, "kind": "R", "row_class": cls, "tables": list(tables),
                      "paper": paper, "row": row})
    for row_id in s_ids:
        paper, row = find_row(dev_eval, row_id)
        if row.get("expected_label") != "supported":
            fail(f"{row_id} is not a supported row, expected an S row")
        tables = derived_tables(row)
        if row_id in file_tables and tables != file_tables[row_id]:
            fail(f"{row_id}: derived tables {tables} differ from s_rows file {file_tables[row_id]}")
        if not tables:
            fail(f"{row_id}: no table cited")
        items.append({"row_id": row_id, "kind": "S", "row_class": "S", "tables": tables,
                      "paper": paper, "row": row})
    if len(items) != 17:
        fail(f"item count {len(items)}, expected 17")
    if len({i["row_id"] for i in items}) != 17:
        fail("duplicate rows")

    rng = random.Random(SEED)
    order = list(items)
    rng.shuffle(order)

    script_parts: list = []  # script-written text only

    def s(text: str) -> str:
        script_parts.append(text)
        return text

    out = [s("# Blind claim pack"), "",
           s("17 items. Each item is one claim and the reference table(s) it concerns. "
             "Open the named PDF to read the claim in context."), ""]
    key_items = {}
    pdfs, papers = [], []
    for n, it in enumerate(order, 1):
        cid = f"C{n:02d}"
        paper, row = it["paper"], it["row"]
        arxiv = str(paper["paper_id"]).replace("arxiv-", "")
        if paper["filename"] not in pdfs:
            pdfs.append(paper["filename"])
        if arxiv not in papers:
            papers.append(arxiv)
        out += ["---", "", s(f"## {cid}"), "",
                s(f"Paper: {paper['title']}"), "",
                s(f"arXiv: {arxiv}"), "",
                s(f"PDF file: {paper['filename']}"), "",
                s("Claim (verbatim):"), ""]
        claim = str(row["claim_text_verbatim"])
        out += ["> " + ln for ln in claim.split("\n")] + [""]
        key_tables = []
        for number in it["tables"]:
            for label, path in table_parts(arxiv, number):
                ref = split_ref_md(path)
                key_tables.append(label)
                out += [s(f"### {label}"), "",
                        s("PDF page: not recorded (find by caption)"), "",
                        ref["caption"], "", ref["flags"], "", ref["grid"], ""]
        key_items[cid] = {"row_id": it["row_id"], "set": it["kind"], "row_class": it["row_class"],
                          "tables": key_tables}

    pack = "\n".join(out).rstrip("\n") + "\n"

    # leak checks (before anything is written)
    m = ROW_ID_RE.search(pack)
    if m:
        fail(f"row id pattern in pack.md: {m.group(0)}")
    written = "\n".join(script_parts).lower()
    for lab in labels:
        if lab in written:
            fail(f"expected_label value '{lab}' in script-written text")
    for w in BANNED_WORDS:
        if re.search(r"\b" + re.escape(w) + r"\b", written):
            fail(f"banned word '{w}' in script-written text")

    PACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PACK_FILE.write_text(pack, encoding="utf-8", newline="\n")
    key = {"note": "NOT for labellers. Maps neutral ids to dev rows.", "seed": SEED,
           "shuffle": "random.Random(seed).shuffle over MISS_ROWS order then selected_final order",
           "items": key_items}
    lp.dump_json(KEY_FILE, key)

    print(f"items: {len(key_items)} (must be 17)")
    print(f"papers ({len(papers)}): " + ", ".join(sorted(papers)))
    print(f"PDF files needed ({len(pdfs)}): " + ", ".join(sorted(pdfs)))
    print(f"pack.md: {PACK_FILE.stat().st_size / 1024:.1f} KB")
    print("leak checks: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
