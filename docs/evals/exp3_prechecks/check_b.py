"""Experiment 3 pre-check B: sentence counts per paper and splitter.

Reports total sentence count, sentence count before the first standalone
"References"/"Bibliography" heading line, and chunks needed at 40
sentences/chunk. Read-only, no LLM calls.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

HEADING_RE = re.compile(r"^[ \t]*(References|Bibliography)[ \t]*$", re.IGNORECASE | re.MULTILINE)


def count_before_heading(raw_text: str, segments: list[str]) -> tuple[int, int, bool]:
    """Returns (total_segments, segments_before_heading, heading_found)."""
    m = HEADING_RE.search(raw_text)
    total = len(segments)
    if not m:
        return total, total, False
    heading_idx = m.start()
    cursor = 0
    before = 0
    for seg in segments:
        idx = raw_text.find(seg, cursor)
        if idx == -1:
            # Segment not locatable verbatim (whitespace trimmed by splitter);
            # fall back to treating it as "before" only if cursor is still
            # before the heading - conservative, does not inflate the count.
            start = cursor
        else:
            start = idx
            cursor = idx + len(seg)
        if start < heading_idx:
            before += 1
    return total, before, True


def main():
    dev_eval = lib.load_dev_eval()
    filenames = sorted({p["filename"] for p in dev_eval["papers"]})
    assert len(filenames) == 12, f"expected 12 dev papers, got {len(filenames)}"

    splitters = {
        "pysbd_pdf_clean": lib.split_pysbd_pdf_clean,
        "pysbd_text_noclean": lib.split_pysbd_text_noclean,
        "regex": lib.split_regex,
    }

    print("=== Check B: sentence counts ===")
    print(f"{'paper':45s} {'splitter':7s} {'total':>6s} {'pre-refs':>9s} {'refs?':>6s} "
          f"{'chunks(total)':>13s} {'chunks(pre-refs)':>16s}")

    for filename in filenames:
        raw_text = lib.paper_text(filename)
        for name, split_fn in splitters.items():
            segments = split_fn(raw_text)
            total, before, heading_found = count_before_heading(raw_text, segments)
            chunks_total = math.ceil(total / 40)
            chunks_before = math.ceil(before / 40)
            print(f"{filename:45s} {name:7s} {total:6d} {before:9d} "
                  f"{'yes' if heading_found else 'no':>6s} {chunks_total:13d} {chunks_before:16d}")


if __name__ == "__main__":
    main()
