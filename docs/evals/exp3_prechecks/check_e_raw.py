"""Check E, Steps 1-3 for source (a): raw pipeline text.

Re-extracts every dev PDF fresh via lib.extract_pdf_text_sync (the verbatim
copy of main.py's function) - it does NOT read any previously saved text
file; nothing from Check A's run is reused except the deterministic
splitter functions in lib.py and classify() from check_a.py, both re-run
here from scratch on freshly extracted text. No LLM/API/network calls.

Step 1: CEILING (claim_norm exact substring of the whole paper's
normalised text) / SPLITTER LOSS (in ceiling, not WHOLE under a given
splitter) / READER LOSS (not in ceiling at all).
Step 2: for every reader-loss row, best rapidfuzz partial_ratio match in
the full text, a short diff, and one cause tag (diag_lib.tag_cause). Also
cross-references Check D candidate 3 (windows)'s 7 NOT_FOUND rows against
this same raw-text ceiling (windows were built from this same raw text).
"""
import importlib.metadata
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import diag_lib
from check_a import classify

import fitz


def main():
    print(f"PyMuPDF (fitz) version: {fitz.pymupdf_version}")
    print("Text source: freshly re-extracted via lib.extract_pdf_text_sync for this run - not read from any saved file.")
    print()

    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    filenames = sorted({f for f, _ in rows})
    refusal_labels = {"not_supported", "partially_supported"}
    n_refusal = sum(1 for _, row in rows if row["expected_label"] in refusal_labels)

    raw_text_cache: dict[str, str] = {}
    full_norm: dict[str, str] = {}
    for filename in filenames:
        raw_text = lib.paper_text(filename)
        raw_text_cache[filename] = raw_text
        full_norm[filename] = lib.normalize_for_match(raw_text)

    splitters = {
        "pysbd_pdf_clean": lib.split_pysbd_pdf_clean,
        "pysbd_text_noclean": lib.split_pysbd_text_noclean,
        "regex": lib.split_regex,
    }
    seg_norm_cache: dict[tuple[str, str], list[str]] = {}
    for filename in filenames:
        for name, fn in splitters.items():
            seg_norm_cache[(filename, name)] = [lib.normalize_for_match(s) for s in fn(raw_text_cache[filename])]

    print("=== Check E Step 1: ceiling / splitter loss / reader loss (raw_pipeline_text) ===")
    ceiling_ids = set()
    not_ceiling = []
    for filename, row in rows:
        claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
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
            claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
            cls, _ = classify(claim_norm, seg_norms)
            if cls == "WHOLE":
                whole_ids.add(row["id"])
        splitter_loss = ceiling_ids - whole_ids
        print(f"  [{splitter_name}] SPLITTER LOSS (in ceiling, not WHOLE): {len(splitter_loss)} rows: {sorted(splitter_loss)}")
    print(f"READER LOSS (not in ceiling): {len(not_ceiling)} rows: {sorted(rid for rid, _ in not_ceiling)}")
    print()

    print("=== Check E Step 2: per-row causes for reader-loss rows (raw_pipeline_text) ===")
    row_lookup = {row["id"]: row for _, row in rows}
    cause_counts: dict[str, int] = {}
    for row_id, filename in not_ceiling:
        row = row_lookup[row_id]
        claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
        score, matched = diag_lib.best_fuzzy_match(claim_norm, full_norm[filename])
        cause = diag_lib.tag_cause(claim_norm, matched, score)
        cause_counts[cause] = cause_counts.get(cause, 0) + 1
        is_refusal = row["expected_label"] in refusal_labels
        diff = diag_lib.make_diff(claim_norm, matched)
        print(f"  {row_id} ({filename}) refusal={is_refusal} score={score:.1f} cause={cause}")
        print(f"    diff: {diff}")
    print(f"cause counts: {cause_counts}")
    print()

    print("--- Check D candidate 3 (windows) 7 NOT_FOUND rows vs raw-text ceiling ---")
    windows_not_found_ids = ["P1-S1", "P3-S6", "P5-R2", "P5-S2", "P7-S1", "P9-S6", "P10-S6"]
    for filename, row in rows:
        rid = row["id"]
        if rid not in windows_not_found_ids:
            continue
        claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
        in_raw_ceiling = claim_norm in full_norm[filename]
        print(f"  {rid} ({filename}): in raw-text ceiling = {in_raw_ceiling}")


if __name__ == "__main__":
    main()
