"""Experiment 3 pre-check D, candidate 3: fixed-size windows, no sentence
splitting.

On today's pipeline text (lib.extract_pdf_text_sync copy, unchanged), makes
sliding windows of 6000 characters with 1500 characters overlap (step =
4500). A row is WHOLE if its normalize_for_match-normalised claim text is
a substring of at least one normalised window; otherwise NOT_FOUND. No
SPLIT/MERGED categories here - windows are fixed-size blocks, not sentence
units, so Check A's classify() does not apply.

Separately (not folded into WHOLE), among rows not found by exact
containment, reports which are found via rapidfuzz.fuzz.partial_ratio >= 95
against some window - rapidfuzz is an existing project dependency
(pyproject.toml), not an extra package.

No LLM calls. No window-size tuning against dev rows.
"""
import importlib.metadata
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

from rapidfuzz import fuzz

WINDOW_SIZE = 6000
OVERLAP = 1500
STEP = WINDOW_SIZE - OVERLAP
FUZZY_THRESHOLD = 95


def make_windows(text: str) -> list[str]:
    windows = []
    n = len(text)
    start = 0
    while start < n:
        windows.append(text[start:start + WINDOW_SIZE])
        if start + WINDOW_SIZE >= n:
            break
        start += STEP
    return windows


def main():
    print(f"rapidfuzz version: {importlib.metadata.version('rapidfuzz')}")
    print(f"window_size={WINDOW_SIZE} overlap={OVERLAP} step={STEP}")

    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    filenames = sorted({f for f, _ in rows})
    assert len(filenames) == 12, f"expected 12 dev papers, got {len(filenames)}"

    refusal_labels = {"not_supported", "partially_supported"}

    window_cache: dict[str, list[str]] = {}
    window_count: dict[str, int] = {}
    for filename in filenames:
        raw_text = lib.paper_text(filename)
        windows = make_windows(raw_text)
        window_cache[filename] = [lib.normalize_for_match(w) for w in windows]
        window_count[filename] = len(windows)

    counts = {"WHOLE": 0, "NOT_FOUND": 0}
    refusal_counts = {"WHOLE": 0, "NOT_FOUND": 0}
    fuzzy_only_rows = []
    not_found_refusal_detail = []
    n_refusal = 0

    for filename, row in rows:
        windows_norm = window_cache[filename]
        claim_norm = lib.normalize_for_match(row["claim_text_verbatim"])
        label = row["expected_label"]
        is_refusal = label in refusal_labels
        if is_refusal:
            n_refusal += 1

        exact_hit = any(claim_norm in w for w in windows_norm) if claim_norm else False
        cls = "WHOLE" if exact_hit else "NOT_FOUND"
        counts[cls] += 1
        if is_refusal:
            refusal_counts[cls] += 1

        if not exact_hit:
            best_score = 0.0
            best_idx = -1
            for i, w in enumerate(windows_norm):
                score = fuzz.partial_ratio(claim_norm, w)
                if score > best_score:
                    best_score = score
                    best_idx = i
            if best_score >= FUZZY_THRESHOLD:
                fuzzy_only_rows.append((row["id"], filename, best_score, best_idx))
            if is_refusal:
                shown = windows_norm[best_idx][:300] if best_idx != -1 else ""
                not_found_refusal_detail.append((row["id"], filename, best_score, shown))

    total = len(rows)
    whole_pct = 100.0 * counts["WHOLE"] / total
    print()
    print("=== Check D candidate 3: fixed windows (6000/1500 overlap) ===")
    print(f"Total dev rows: {total}; refusal-family rows: {n_refusal}")
    print(f"overall: WHOLE={counts['WHOLE']} NOT_FOUND={counts['NOT_FOUND']}  "
          f"WHOLE%={whole_pct:.1f}  bar(>=95%)={'PASS' if whole_pct >= 95.0 else 'FAIL'}")
    print(f"refusal-family ({n_refusal} rows): WHOLE={refusal_counts['WHOLE']} "
          f"NOT_FOUND={refusal_counts['NOT_FOUND']}")
    print()
    print(f"--- fuzzy-only hits (exact miss, rapidfuzz partial_ratio >= {FUZZY_THRESHOLD}): "
          f"{len(fuzzy_only_rows)} ---")
    for rid, filename, score, idx in fuzzy_only_rows:
        print(f"  {rid} ({filename}) score={score:.1f} window_idx={idx}")
    print()
    print(f"--- non-WHOLE refusal-family rows ({len(not_found_refusal_detail)}) with best-window fuzzy score ---")
    for rid, filename, score, shown in not_found_refusal_detail:
        print(f"  {rid} ({filename}) best_fuzzy_score={score:.1f}")
        print(f"    best window (truncated): {shown!r}")
    print()
    print("--- per-paper window counts ---")
    for filename in filenames:
        print(f"  {filename}: {window_count[filename]}")


if __name__ == "__main__":
    main()
