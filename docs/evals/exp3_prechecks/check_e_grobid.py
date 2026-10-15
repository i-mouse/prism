"""Check E, Steps 1-3 for source (b): GROBID.

Reuses the TEI XML saved by check_d_grobid_v2.py under
scratch/exp3/grobid_tei/*.tei.xml - makes NO network call. Re-parses with
the same corrected parse_tei (note-fallback fixed) and re-runs classify()
from check_a.py, both deterministic, to get per-row data for diagnosis.

GROBID has only one segmentation (not multiple splitters like the other
two sources), so "SPLITTER LOSS" here means: rows in the ceiling but not
classified WHOLE by classify() against the GROBID segments - the same
definition used for the other sources' splitters, applied to GROBID's one
segmentation.

CEILING here is defined against " ".join(seg_norms) in document order
(abstract, then body, then caption, then note) - the same joined text
classify()'s SPLIT branch already uses - because TEI only gives us
fragments, not one continuous original-order string, unlike the other two
sources where the real continuous text is available.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
import diag_lib
from check_a import classify
from check_d_grobid_v2 import parse_tei

TEI_DIR = Path(__file__).resolve().parent / "grobid_tei"


def main():
    print("Text source: TEI XML reused from scratch/exp3/grobid_tei/*.tei.xml (saved by check_d_grobid_v2.py) - no network call made in this script.")
    print()

    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    filenames = sorted({f for f, _ in rows})
    refusal_labels = {"not_supported", "partially_supported"}
    n_refusal = sum(1 for _, row in rows if row["expected_label"] in refusal_labels)

    combined_cache: dict[str, list[tuple[str, str]]] = {}
    seg_norms_cache: dict[str, list[str]] = {}
    full_norm: dict[str, str] = {}

    for filename in filenames:
        tei_path = TEI_DIR / f"{filename}.tei.xml"
        xml_text = tei_path.read_text(encoding="utf-8")
        parsed = parse_tei(xml_text)
        combined = (
            [("abstract", s) for s in parsed["abstract"]]
            + [("body", s) for s in parsed["body"]]
            + [("caption", s) for s in parsed["caption"]]
            + [("note", s) for s in parsed["note"]]
        )
        combined_cache[filename] = combined
        seg_norms = [lib.normalize_for_match(s) for _, s in combined]
        seg_norms_cache[filename] = seg_norms
        full_norm[filename] = " ".join(seg_norms)

    print("=== Check E Step 1: ceiling / splitter loss / reader loss (grobid) ===")
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

    whole_ids = set()
    for filename, row in rows:
        seg_norms = seg_norms_cache[filename]
        claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
        cls, _ = classify(claim_norm, seg_norms)
        if cls == "WHOLE":
            whole_ids.add(row["id"])
    splitter_loss = ceiling_ids - whole_ids
    print(f"  [grobid_sentences] SPLITTER LOSS (in ceiling, not WHOLE): {len(splitter_loss)} rows: {sorted(splitter_loss)}")
    print(f"READER LOSS (not in ceiling): {len(not_ceiling)} rows: {sorted(rid for rid, _ in not_ceiling)}")
    print()

    print("=== Check E Step 2: per-row causes for reader-loss rows (grobid) ===")
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


if __name__ == "__main__":
    main()
