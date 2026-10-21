"""Step 0 self-audit helper (read-only inspection, not part of Check D/E's
measurement scripts): does pymupdf4llm backslash-escape markdown-significant
characters (_, *, etc.) inside prose? If so, check_d_pymupdf4llm.py's
strip_markdown (which strips # * _ | ` but never strips a backslash) would
leave a stray "\\" in the cleaned text wherever the source had an escaped
"_" or "*", which would NOT be mirrored in the (never-escaped) dev claim
text even after the same strip_markdown call - an asymmetry despite the
function being "applied symmetrically" in the literal sense of "the same
function runs on both sides".

This script only inspects pymupdf4llm's raw output for backslash-escape
patterns on one dev paper; it does not change check_d_pymupdf4llm.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

import pymupdf4llm

filename = sorted({f for f, _ in lib.iter_dev_rows(lib.load_dev_eval())})[0]
raw_md = pymupdf4llm.to_markdown(str(lib.PDF_DIR / filename), header=False, footer=False)

escaped_underscore = re.findall(r"\\_", raw_md)
escaped_asterisk = re.findall(r"\\\*", raw_md)
escaped_other = re.findall(r"\\[#|`]", raw_md)
any_backslash = re.findall(r"\\.", raw_md)

print(f"paper: {filename}")
print(f"len(raw_md): {len(raw_md)}")
print(f"escaped underscore count (\\_): {len(escaped_underscore)}")
print(f"escaped asterisk count (\\*): {len(escaped_asterisk)}")
print(f"escaped other (#|`) count: {len(escaped_other)}")
print(f"any backslash-followed-by-char count: {len(any_backslash)}")
if any_backslash:
    print("sample backslash occurrences (up to 10), with context:")
    for m in re.finditer(r".{20}\\..{20}", raw_md):
        print("  ", repr(m.group(0)))
        if len(escaped_underscore) + len(escaped_asterisk) >= 10:
            break

# Also check for literal underscores/asterisks/pipes surviving un-escaped
# (i.e. real content using these chars, which strip_markdown would remove
# from BOTH sides symmetrically - not a bug by itself, just confirming the
# scale of what gets removed).
lone_underscore = len(re.findall(r"(?<!\\)_", raw_md))
lone_asterisk = len(re.findall(r"(?<!\\)\*", raw_md))
lone_pipe = raw_md.count("|")
print(f"un-escaped underscore count: {lone_underscore}")
print(f"un-escaped asterisk count: {lone_asterisk}")
print(f"pipe count: {lone_pipe}")
