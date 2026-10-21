"""Check E, Steps 1-3 for source (c): PyMuPDF4LLM, headers/footers off.

Re-runs pymupdf4llm.to_markdown(path, header=False, footer=False) fresh for
every dev PDF - it does NOT read any previously saved markdown file;
nothing from Check D's run is reused except the deterministic strip_markdown
function (imported from check_d_pymupdf4llm.py) and the splitter functions
in lib.py / classify() from check_a.py, all re-run here from scratch. No
LLM/API/network calls.

Step 1: CEILING (claim_norm, after the same strip_markdown rule, exact
substring of the whole cleaned+normalised document) / SPLITTER LOSS (in
ceiling, not WHOLE under a given splitter) / READER LOSS (not in ceiling).
Step 2: for every reader-loss row, best rapidfuzz partial_ratio match, a
short diff, and one cause tag (diag_lib.tag_cause).
"""
import importlib.metadata
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import diag_lib
from check_a import classify
from check_d_pymupdf4llm import strip_markdown

import fitz
import pymupdf4llm


def main():
    print(f"PyMuPDF (fitz) version: {fitz.pymupdf_version}")
    print(f"pymupdf4llm version: {importlib.metadata.version('pymupdf4llm')}")
    print("Text source: freshly re-generated via pymupdf4llm.to_markdown for this run - not read from any saved file.")
    print()

    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    filenames = sorted({f for f, _ in rows})
    refusal_labels = {"not_supported", "partially_supported"}
    n_refusal = sum(1 for _, row in rows if row["expected_label"] in refusal_labels)

    cleaned_cache: dict[str, str] = {}
    full_norm: dict[str, str] = {}
    for filename in filenames:
        raw_md = pymupdf4llm.to_markdown(str(lib.PDF_DIR / filename), header=False, footer=False)
        cleaned_md = strip_markdown(raw_md)
        cleaned_cache[filename] = cleaned_md
        full_norm[filename] = lib.normalize_for_match(cleaned_md)

    splitters = {
        "regex": lib.split_regex,
        "pysbd_pdf_clean": lib.split_pysbd_pdf_clean,
    }
    seg_norm_cache: dict[tuple[str, str], list[str]] = {}
    for filename in filenames:
        for name, fn in splitters.items():
            seg_norm_cache[(filename, name)] = [lib.normalize_for_match(s) for s in fn(cleaned_cache[filename])]

    print("=== Check E Step 1: ceiling / splitter loss / reader loss (pymupdf4llm) ===")
    ceiling_ids = set()
    not_ceiling = []
    for filename, row in rows:
        claim_norm = lib.normalize_for_match(strip_markdown(row["claim_text_verbatim"]))
        in_ceiling = bool(claim_norm) and claim_norm in full_norm[filename]
        if in_ceiling:
            ceiling_ids.add(row["id"])
        else:
            not_ceiling.append((row["id"], filename))

    refusal_ceiling = sum(1 for _, row in rows if row["id"] in ceiling_ids and row["expected_label"] in refusal_labels)
    print(f"CEILING: {len(ceiling_ids)}/119 overall; {refusal_ceiling}/{n_refusal} refusal-family")

    for splitter_name in splitters:
        whole_ids = set()
        for filename, row in rows:
            seg_norms = seg_norm_cache[(filename, splitter_name)]
            claim_norm = lib.normalize_for_match(strip_markdown(row["claim_text_verbatim"]))
            cls, _ = classify(claim_norm, seg_norms)
            if cls == "WHOLE":
                whole_ids.add(row["id"])
        splitter_loss = ceiling_ids - whole_ids
        print(f"  [{splitter_name}] SPLITTER LOSS (in ceiling, not WHOLE): {len(splitter_loss)} rows: {sorted(splitter_loss)}")
    print(f"READER LOSS (not in ceiling): {len(not_ceiling)} rows: {sorted(rid for rid, _ in not_ceiling)}")
    print()

    print("=== Check E Step 2: per-row causes for reader-loss rows (pymupdf4llm) ===")
    row_lookup = {row["id"]: row for _, row in rows}
    cause_counts: dict[str, int] = {}
    for row_id, filename in not_ceiling:
        row = row_lookup[row_id]
        claim_norm = lib.normalize_for_match(strip_markdown(row["claim_text_verbatim"]))
        score, matched = diag_lib.best_fuzzy_match(claim_norm, full_norm[filename])
        cause = diag_lib.tag_cause(claim_norm, matched, score)
        cause_counts[cause] = cause_counts.get(cause, 0) + 1
        is_refusal = row["expected_label"] in refusal_labels
        diff = diag_lib.make_diff(claim_norm, matched)
        print(f"  {row_id} ({filename}) refusal={is_refusal} score={score:.1f} cause={cause}")
        print(f"    diff: {diff}")
    print(f"cause counts: {cause_counts}")


if __name__ == "__main__":
    main()
