"""CLI: deterministically checks that every row's claim_text_verbatim is an
exact (or near-exact) substring of its paper's extracted PDF text.

No fragment-splitting fallback: a row either matches the page-joined source
text directly (STRICT), matches after stripping page-number lines and hyphen
characters (LOOSE), or FAILs. Does not call any LLM, run matrix_runner, or
touch the network. Takes explicit --eval-path/--pdf-dir; does not glob
docs/evals/.

Text extraction: PyMuPDF (fitz), the same library used for the prior manual
verification pass on this eval set.

Usage:
  uv run python -m eval.verify_eval_verbatim --eval-path docs/evals/dev_eval.json --pdf-dir docs/research_papers
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import fitz

RUNNING_LINE_MAX_LEN = 40

HYPHENS = "-­‐‑"
HYPHEN_RE = re.compile(f"[{HYPHENS}]")
PAGE_NUM_LINE_RE = re.compile(r"^\s*\d{1,3}\s*$")
END_PUNCT_RE = re.compile(r"[.?!][\"'’”)\]]*\s*$")
START_PUNCT_RE = re.compile(r"[.?!][\"'’”)\]]*\s*$")

# LOOSE-only quote folding: single-quote family -> ', double-quote family -> ".
# STRICT comparison never applies this.
SINGLE_QUOTE_RE = re.compile("[‘’‛′]")
DOUBLE_QUOTE_RE = re.compile("[“”‟″]")


def fold_quotes_loose(s: str) -> str:
    s = SINGLE_QUOTE_RE.sub("'", s)
    s = DOUBLE_QUOTE_RE.sub('"', s)
    return s


def nfkc_collapse(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def strip_page_number_lines(text: str) -> str:
    lines = text.split("\n")
    kept = [ln for ln in lines if not PAGE_NUM_LINE_RE.match(ln)]
    return "\n".join(kept)


def compute_running_lines(pages: list[str]) -> set[str]:
    """LOOSE-only: a stripped line of RUNNING_LINE_MAX_LEN characters or
    fewer that appears on at least half of this paper's pages is treated as
    a running header/footer, not prose."""
    n_pages = len(pages)
    page_counts: Counter[str] = Counter()
    for page_text in pages:
        seen_on_this_page = set()
        for line in page_text.split("\n"):
            stripped = line.strip()
            if stripped and len(stripped) <= RUNNING_LINE_MAX_LEN:
                seen_on_this_page.add(stripped)
        page_counts.update(seen_on_this_page)
    return {line for line, count in page_counts.items() if count * 2 >= n_pages}


def strip_running_lines(text: str, running_lines: set[str]) -> str:
    if not running_lines:
        return text
    lines = text.split("\n")
    kept = [ln for ln in lines if ln.strip() not in running_lines]
    return "\n".join(kept)


def loose_key(s: str) -> str:
    s = fold_quotes_loose(s)
    s = HYPHEN_RE.sub("", s)
    s = re.sub(r"\s+", "", s)
    return s


def extract_pages(pdf_path: Path) -> list[str]:
    doc = fitz.open(str(pdf_path))
    try:
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()
    return pages


def extract_page_joined_text(pdf_path: Path) -> str:
    return "\n".join(extract_pages(pdf_path))


def find_strict(claim_norm: str, source_norm: str):
    idx = source_norm.find(claim_norm)
    if idx == -1:
        return None
    return idx


CONTEXT_CHARS = 60


def check_row(claim: str, raw_source_text: str, running_lines: set[str] | None = None):
    """Returns (mode, warnings, context) where mode in {STRICT, LOOSE, FAIL}.

    context maps each warning name present to the 60-character source
    snippet it was raised from (before the match for START_WARN, after the
    match for END_WARN).

    running_lines (LOOSE only): stripped lines recognized as running
    headers/footers for this paper, dropped before the LOOSE comparison.
    STRICT never uses this.
    """
    source_norm = nfkc_collapse(raw_source_text)
    claim_norm = nfkc_collapse(claim)

    idx = find_strict(claim_norm, source_norm)
    if idx is not None:
        warnings, context = _boundary_warnings(claim_norm, source_norm, idx)
        return "STRICT", warnings, context

    stripped_source = strip_page_number_lines(raw_source_text)
    stripped_source = strip_running_lines(stripped_source, running_lines or set())
    source_loose = loose_key(nfkc_collapse(stripped_source))
    claim_loose = loose_key(claim_norm)
    if claim_loose and claim_loose in source_loose:
        # Boundary warnings are computed against the STRICT-normalized
        # (non-loose-keyed) source so punctuation context is still legible;
        # locate the match region in source_norm after stripping page-number
        # lines the same way, for the warning check only.
        source_norm_for_warn = nfkc_collapse(stripped_source)
        warnings, context = _boundary_warnings_loose(claim_norm, source_norm_for_warn)
        return "LOOSE", warnings, context

    return "FAIL", [], {}


def _boundary_warnings(claim_norm: str, source_norm: str, idx: int):
    warnings = []
    context = {}
    if not END_PUNCT_RE.search(claim_norm):
        warnings.append("END_WARN")
        end_idx = idx + len(claim_norm)
        context["END_WARN"] = source_norm[end_idx:end_idx + CONTEXT_CHARS]
    before = source_norm[:idx].rstrip()
    if before:
        last_char = before[-1]
        # "starts a line" has no meaning once whitespace is collapsed to
        # single spaces, so the only exemption left is sentence-boundary
        # punctuation immediately before the match.
        if last_char not in ".?!":
            warnings.append("START_WARN")
            context["START_WARN"] = source_norm[max(0, idx - CONTEXT_CHARS):idx]
    return warnings, context


def _boundary_warnings_loose(claim_norm: str, source_norm_for_warn: str):
    # Best-effort: locate the claim's leading/trailing words in the
    # page-number-stripped, NFKC-collapsed (but not hyphen/space-stripped)
    # source to evaluate the same boundary rule under LOOSE mode.
    warnings = []
    context = {}
    if not END_PUNCT_RE.search(claim_norm):
        warnings.append("END_WARN")
        tail_words = claim_norm.split()[-4:]
        tail_probe = " ".join(tail_words)
        tail_idx = source_norm_for_warn.find(tail_probe) if tail_probe else -1
        if tail_idx != -1:
            end_idx = tail_idx + len(tail_probe)
            context["END_WARN"] = source_norm_for_warn[end_idx:end_idx + CONTEXT_CHARS]
    lead_words = claim_norm.split()[:4]
    probe = " ".join(lead_words)
    idx = source_norm_for_warn.find(probe) if probe else -1
    if idx == -1:
        # Can't locate a boundary in the non-loose text (hyphenation differs
        # right at the start); do not guess, do not add START_WARN.
        return warnings, context
    before = source_norm_for_warn[:idx].rstrip()
    if before:
        last_char = before[-1]
        if last_char not in ".?!":
            warnings.append("START_WARN")
            context["START_WARN"] = source_norm_for_warn[max(0, idx - CONTEXT_CHARS):idx]
    return warnings, context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-path", required=True, type=Path)
    parser.add_argument("--pdf-dir", required=True, type=Path)
    args = parser.parse_args()

    eval_path: Path = args.eval_path
    pdf_dir: Path = args.pdf_dir

    data = json.loads(eval_path.read_text(encoding="utf-8"))

    pdf_text_cache: dict[str, str] = {}
    running_lines_cache: dict[str, set[str]] = {}
    mode_counts = {"STRICT": 0, "LOOSE": 0, "FAIL": 0}
    label_counts: dict[str, int] = {}
    any_fail = False

    rows_out = []
    for paper in data["papers"]:
        filename = paper["filename"]
        pdf_path = pdf_dir / filename
        if filename not in pdf_text_cache:
            pages = extract_pages(pdf_path)
            pdf_text_cache[filename] = "\n".join(pages)
            running_lines_cache[filename] = compute_running_lines(pages)
        source_text = pdf_text_cache[filename]
        running_lines = running_lines_cache[filename]

        for row in paper["expected_matrix"]:
            rid = row["id"]
            label = row["expected_label"]
            claim = row["claim_text_verbatim"]
            mode, warnings, context = check_row(claim, source_text, running_lines)
            mode_counts[mode] += 1
            label_counts[label] = label_counts.get(label, 0) + 1
            if mode == "FAIL":
                any_fail = True
            rows_out.append((rid, label, mode, warnings, context))

    for rid, label, mode, warnings, context in rows_out:
        warn_str = ",".join(warnings) if warnings else "-"
        print(f"{rid}\t{label}\t{mode}\t{warn_str}")
        if "START_WARN" in context:
            print(f"  START_WARN context (60 chars before match): {context['START_WARN']!r}")
        if "END_WARN" in context:
            print(f"  END_WARN context (60 chars after match): {context['END_WARN']!r}")

    print()
    print("Counts per mode:", mode_counts)
    print("Counts per label:", label_counts)
    print("Total rows:", len(rows_out))

    recorded_label_counts = data.get("metadata", {}).get("label_counts", {})
    label_count_mismatch = False
    for label in ("not_supported", "partially_supported", "supported"):
        actual = label_counts.get(label, 0)
        recorded = recorded_label_counts.get(label)
        if recorded != actual:
            label_count_mismatch = True
            print(f"LABEL_COUNT_MISMATCH: metadata.label_counts.{label}={recorded!r} but actual rows have {actual}")
    recorded_total = recorded_label_counts.get("total")
    actual_total = len(rows_out)
    if recorded_total != actual_total:
        label_count_mismatch = True
        print(f"LABEL_COUNT_MISMATCH: metadata.label_counts.total={recorded_total!r} but actual rows have {actual_total}")

    actual_refusal_total = label_counts.get("not_supported", 0) + label_counts.get("partially_supported", 0)
    recorded_refusal_total = recorded_label_counts.get("refusal_family_total")
    if recorded_refusal_total != actual_refusal_total:
        label_count_mismatch = True
        print(f"LABEL_COUNT_MISMATCH: metadata.label_counts.refusal_family_total={recorded_refusal_total!r} but actual rows have {actual_refusal_total}")

    if any_fail or label_count_mismatch:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
