"""Experiment 3 pre-check A: splitter survival.

For each of the 12 dev papers, extract text exactly as the pipeline does
(lib.extract_pdf_text_sync, copied verbatim from main.py), split with (1)
pysbd and (2) a simple regex baseline, then classify each of the 119 dev
rows per splitter as WHOLE / SPLIT / MERGED / NOT_FOUND on
GROUNDING_NORMALIZE-normalised text (lib.normalize_for_match, copied
verbatim from extraction/grounding.py).

No LLM/API calls. No splitter tuning against dev rows. Read-only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

WHOLE_EXTRA_RATIO = 0.10
MAX_SPLIT_WINDOW = 8


def classify(claim_norm: str, seg_norms: list[str]) -> tuple[str, list[int]]:
    if not claim_norm:
        return "NOT_FOUND", []

    containing = [i for i, s in enumerate(seg_norms) if s and claim_norm in s]
    if containing:
        i = containing[0]
        seg_len = len(seg_norms[i])
        claim_len = len(claim_norm)
        extra_ratio = (seg_len - claim_len) / claim_len if claim_len else 0.0
        if extra_ratio <= WHOLE_EXTRA_RATIO:
            return "WHOLE", [i]
        return "MERGED", [i]

    n = len(seg_norms)
    for start in range(n):
        joined = ""
        for w in range(1, MAX_SPLIT_WINDOW + 1):
            end = start + w
            if end > n:
                break
            joined = " ".join(s for s in seg_norms[start:end] if s)
            if claim_norm in joined:
                return "SPLIT", list(range(start, end))
    return "NOT_FOUND", []


def main():
    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    assert len(rows) == 119, f"expected 119 dev rows, got {len(rows)}"

    refusal_labels = {"not_supported", "partially_supported"}

    splitters = {
        "pysbd_pdf_clean": lib.split_pysbd_pdf_clean,
        "pysbd_text_noclean": lib.split_pysbd_text_noclean,
        "regex": lib.split_regex,
    }

    text_cache: dict[str, str] = {}
    seg_cache: dict[tuple[str, str], list[str]] = {}

    counts = {name: {"WHOLE": 0, "SPLIT": 0, "MERGED": 0, "NOT_FOUND": 0} for name in splitters}
    refusal_counts = {name: {"WHOLE": 0, "SPLIT": 0, "MERGED": 0, "NOT_FOUND": 0} for name in splitters}
    refusal_non_whole_detail = {name: [] for name in splitters}

    n_refusal_rows = 0

    for filename, row in rows:
        if filename not in text_cache:
            text_cache[filename] = lib.paper_text(filename)
        raw_text = text_cache[filename]

        claim = row["claim_text_verbatim"]
        claim_norm = lib.normalize_for_match(claim)
        label = row["expected_label"]
        is_refusal = label in refusal_labels
        if is_refusal:
            n_refusal_rows += 1

        for name, split_fn in splitters.items():
            key = (filename, name)
            if key not in seg_cache:
                segs = split_fn(raw_text)
                seg_cache[key] = [lib.normalize_for_match(s) for s in segs]
            seg_norms = seg_cache[key]

            cls, idxs = classify(claim_norm, seg_norms)
            counts[name][cls] += 1
            if is_refusal:
                refusal_counts[name][cls] += 1
                if cls != "WHOLE":
                    shown = [seg_norms[i][:300] for i in idxs]
                    refusal_non_whole_detail[name].append(
                        (row["id"], filename, cls, shown)
                    )

    total_rows = len(rows)
    print("=== Check A: splitter survival ===")
    print(f"Total dev rows: {total_rows}; refusal-family rows: {n_refusal_rows}")
    print()
    for name in splitters:
        c = counts[name]
        whole_pct = 100.0 * c["WHOLE"] / total_rows
        print(f"[{name}] overall: WHOLE={c['WHOLE']} SPLIT={c['SPLIT']} MERGED={c['MERGED']} "
              f"NOT_FOUND={c['NOT_FOUND']}  WHOLE%={whole_pct:.1f}  "
              f"bar(>=95%)={'PASS' if whole_pct >= 95.0 else 'FAIL'}")
        rc = refusal_counts[name]
        print(f"[{name}] refusal-family ({n_refusal_rows} rows): WHOLE={rc['WHOLE']} "
              f"SPLIT={rc['SPLIT']} MERGED={rc['MERGED']} NOT_FOUND={rc['NOT_FOUND']}")
    print()

    for name in splitters:
        detail = refusal_non_whole_detail[name]
        print(f"--- [{name}] non-WHOLE refusal-family rows ({len(detail)}) ---")
        for rid, filename, cls, shown in detail:
            print(f"  {rid} ({filename}) -> {cls}")
            for j, seg in enumerate(shown):
                print(f"    segment[{j}]: {seg!r}")
        print()


if __name__ == "__main__":
    main()
