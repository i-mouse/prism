"""One-off inspection: pymupdf4llm.to_markdown's real signature and version.

Not part of Check D's classification - just confirms the installed
version's accepted kwargs before candidate 2 calls it with header=False,
footer=False, so an invalid kwarg is caught before any PDF is processed.
"""
import importlib.metadata
import inspect

import pymupdf4llm

print("pymupdf4llm version:", importlib.metadata.version("pymupdf4llm"))
print("to_markdown signature:", inspect.signature(pymupdf4llm.to_markdown))

try:
    unwrapped = inspect.unwrap(pymupdf4llm.to_markdown)
    print("unwrapped signature:", inspect.signature(unwrapped))
except (TypeError, ValueError) as e:
    print("unwrap failed:", e)

print("__wrapped__ present:", hasattr(pymupdf4llm.to_markdown, "__wrapped__"))

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

dev_eval = lib.load_dev_eval()
test_filename = sorted({f for f, _ in lib.iter_dev_rows(dev_eval)})[0]
test_path = lib.PDF_DIR / test_filename
print(f"test call on {test_filename} with header=False, footer=False ...")
try:
    md = pymupdf4llm.to_markdown(str(test_path), header=False, footer=False)
    print("SUCCESS: header=False, footer=False accepted. len(markdown) =", len(md))
except TypeError as e:
    print("TypeError raised - header/footer kwargs rejected:", e)

