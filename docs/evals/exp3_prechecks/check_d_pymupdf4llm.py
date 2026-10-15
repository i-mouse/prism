"""Experiment 3 pre-check D, candidate 2: PyMuPDF4LLM, headers/footers off.

pymupdf4llm.to_markdown(path, header=False, footer=False) per dev paper
(kwargs confirmed accepted by the installed version 1.28.2 via
scratch/exp3/sig_check.py before writing this). The markdown markup strip
rule below is applied SYMMETRICALLY to both the markdown text (before
splitting) and each dev row's claim_text_verbatim (before normalising),
so neither side gets an unfair advantage:

  - remove bare markup characters: # * _ | ` (backtick)
  - remove a leading list marker at line start ONLY when it is "-"/"+"
    followed by whitespace, or one-or-more digits followed by "." or ")"
    THEN whitespace, at the very start of a line - so "3.2 Results" and
    "0.825" are never touched (the character after the digits is itself a
    digit there, not "." /")"+whitespace... concretely: "3.2" fails the
    digit+[.)]+whitespace pattern because "." is followed by "2", not
    whitespace; "0.825" fails the same way).

Then split the cleaned markdown with the existing lib.split_regex AND
lib.split_pysbd_pdf_clean, classify both ways (classify() imported from
check_a.py, WHOLE/SPLIT/MERGED/NOT_FOUND unchanged), report separately.

No LLM calls. No tuning against dev rows.
"""
import importlib.metadata
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib
from check_a import classify

import pymupdf4llm

_LEADING_BULLET_RE = re.compile(r"(?m)^[ \t]*[-+][ \t]+")
_LEADING_NUM_RE = re.compile(r"(?m)^[ \t]*\d+[.)][ \t]+")
_MARKUP_CHARS_RE = re.compile(r"[#*_|`]")


def strip_markdown(text: str) -> str:
    text = _LEADING_BULLET_RE.sub("", text)
    text = _LEADING_NUM_RE.sub("", text)
    text = _MARKUP_CHARS_RE.sub("", text)
    return text


def main():
    print(f"pymupdf4llm version: {importlib.metadata.version('pymupdf4llm')}")

    dev_eval = lib.load_dev_eval()
    rows = list(lib.iter_dev_rows(dev_eval))
    filenames = sorted({f for f, _ in rows})
    assert len(filenames) == 12, f"expected 12 dev papers, got {len(filenames)}"

    refusal_labels = {"not_supported", "partially_supported"}

    splitters = {
        "regex": lib.split_regex,
        "pysbd_pdf_clean": lib.split_pysbd_pdf_clean,
    }

    md_cache: dict[str, str] = {}
    seg_cache: dict[tuple[str, str], list[str]] = {}

    for filename in filenames:
        pdf_path = lib.PDF_DIR / filename
        raw_md = pymupdf4llm.to_markdown(str(pdf_path), header=False, footer=False)
        md_cache[filename] = strip_markdown(raw_md)

    counts = {name: {"WHOLE": 0, "SPLIT": 0, "MERGED": 0, "NOT_FOUND": 0} for name in splitters}
    refusal_counts = {name: {"WHOLE": 0, "SPLIT": 0, "MERGED": 0, "NOT_FOUND": 0} for name in splitters}
    non_whole_detail = {name: [] for name in splitters}
    n_refusal = 0

    for filename, row in rows:
        cleaned_md = md_cache[filename]
        claim = strip_markdown(row["claim_text_verbatim"])
        claim_norm = lib.normalize_for_match(claim)
        label = row["expected_label"]
        is_refusal = label in refusal_labels
        if is_refusal:
            n_refusal += 1

        for name, split_fn in splitters.items():
            key = (filename, name)
            if key not in seg_cache:
                segs = split_fn(cleaned_md)
                seg_cache[key] = [lib.normalize_for_match(s) for s in segs]
            seg_norms = seg_cache[key]

            cls, idxs = classify(claim_norm, seg_norms)
            counts[name][cls] += 1
            if is_refusal:
                refusal_counts[name][cls] += 1
                if cls != "WHOLE":
                    shown = [seg_norms[i][:300] for i in idxs]
                    non_whole_detail[name].append((row["id"], filename, cls, shown))

    total = len(rows)
    print()
    print("=== Check D candidate 2: PyMuPDF4LLM (header=False, footer=False) ===")
    print(f"Total dev rows: {total}; refusal-family rows: {n_refusal}")
    print(f"Strip rule: remove leading '-'/'+ ' or '<digits>.'/'<digits>)' + space at "
          f"line start, then remove bare # * _ | ` chars - applied to both segments and claim text.")
    print()
    for name in splitters:
        c = counts[name]
        whole_pct = 100.0 * c["WHOLE"] / total
        print(f"[{name}] overall: WHOLE={c['WHOLE']} SPLIT={c['SPLIT']} MERGED={c['MERGED']} "
              f"NOT_FOUND={c['NOT_FOUND']}  WHOLE%={whole_pct:.1f}  "
              f"bar(>=95%)={'PASS' if whole_pct >= 95.0 else 'FAIL'}")
        rc = refusal_counts[name]
        print(f"[{name}] refusal-family ({n_refusal} rows): WHOLE={rc['WHOLE']} "
              f"SPLIT={rc['SPLIT']} MERGED={rc['MERGED']} NOT_FOUND={rc['NOT_FOUND']}")
    print()

    for name in splitters:
        detail = non_whole_detail[name]
        print(f"--- [{name}] non-WHOLE refusal-family rows ({len(detail)}) ---")
        for rid, filename, cls, shown in detail:
            print(f"  {rid} ({filename}) -> {cls}")
            for j, seg in enumerate(shown):
                print(f"    segment[{j}]: {seg!r}")
        print()

    print("--- per-paper segment counts ---")
    for filename in filenames:
        counts_line = {name: len(seg_cache[(filename, name)]) for name in splitters}
        print(f"  {filename}: {counts_line}")


if __name__ == "__main__":
    main()
