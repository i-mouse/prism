"""Check E shared helpers: ceiling check, fuzzy best-match, diff, cause tag.

Read-only diagnostic code, no LLM/API calls. Cause tagging is a fixed,
documented, priority-ordered set of generic regex checks - not tuned to
any specific dev row. Priority order (first match wins):

  1. score < 80                                   -> text_dropped
  2. inserted/deleted text contains digit-only     -> footer_or_header_inside
     tokens or boilerplate words (Preprint, arXiv,
     Appendix, Figure, Table, DOI)
  3. inserted/deleted text is only '-' and/or       -> hyphenation_or_linebreak
     whitespace characters
  4. inserted/deleted text contains a math/symbol  -> symbol_or_math_changed
     character (x divide plusminus etc., or LaTeX-
     ish backslash sequences)
  5. inserted/deleted text contains a ligature or  -> ligature_or_unicode
     other non-ASCII character not already covered
  6. inserted/deleted text matches a bracketed     -> citation_marker
     numeric cite "[12]" or an author-year cite
     "(Smith et al., 2020)"
  7. inserted/deleted text is only whitespace       -> missing_or_extra_space
  8. claim and matched text share >=90% of their    -> text_reordered
     word tokens (Jaccard) despite a low raw score
  9. otherwise                                      -> other
"""
import difflib
import re

from rapidfuzz import fuzz

BOILERPLATE_RE = re.compile(r"(?i)\b(preprint|arxiv|appendix|figure|table|doi)\b")
DIGIT_ONLY_RE = re.compile(r"^\s*\d{1,4}\s*$")
MATH_SYMBOL_RE = re.compile(r"[×÷±≤≥≈≠→←↑↓∑∏√∫αβγδθλμσΩ]|\\[a-zA-Z]+")
LIGATURE_RE = re.compile(r"[ﬀ-ﬆ]")
NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
CITATION_NUM_RE = re.compile(r"\[\d+(,\s*\d+)*\]")
CITATION_AUTHOR_RE = re.compile(r"\([A-Z][a-zA-Z]+(?:\s+et al\.)?,?\s*\d{4}[a-z]?\)")


def best_fuzzy_match(claim_norm: str, full_norm: str) -> tuple[float, str]:
    """Returns (score, matched_text) - matched_text is the aligned region
    of full_norm that rapidfuzz's partial_ratio_alignment found best."""
    if not claim_norm or not full_norm:
        return 0.0, ""
    aln = fuzz.partial_ratio_alignment(claim_norm, full_norm)
    matched = full_norm[aln.dest_start:aln.dest_end]
    return aln.score, matched


def make_diff(a: str, b: str, max_chars: int = 300) -> str:
    sm = difflib.SequenceMatcher(None, a, b)
    parts = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(a[i1:i2])
        elif tag == "delete":
            parts.append(f"[-{a[i1:i2]}-]")
        elif tag == "insert":
            parts.append(f"{{+{b[j1:j2]}+}}")
        elif tag == "replace":
            parts.append(f"[-{a[i1:i2]}-]{{+{b[j1:j2]}+}}")
    diff = "".join(parts)
    if len(diff) > max_chars:
        diff = diff[:max_chars] + "...[truncated]"
    return diff


def _changed_text(a: str, b: str) -> str:
    sm = difflib.SequenceMatcher(None, a, b)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            out.append(a[i1:i2])
        if tag in ("insert", "replace"):
            out.append(b[j1:j2])
    return "".join(out)


def tag_cause(claim_norm: str, matched: str, score: float) -> str:
    if score < 80:
        return "text_dropped"

    changed = _changed_text(claim_norm, matched)

    if DIGIT_ONLY_RE.match(changed) or BOILERPLATE_RE.search(changed):
        return "footer_or_header_inside"

    stripped_changed = changed.replace("-", "").strip()
    if changed and not stripped_changed:
        return "hyphenation_or_linebreak"

    if MATH_SYMBOL_RE.search(changed):
        return "symbol_or_math_changed"

    if LIGATURE_RE.search(changed) or NON_ASCII_RE.search(changed):
        return "ligature_or_unicode"

    if CITATION_NUM_RE.search(changed) or CITATION_AUTHOR_RE.search(changed):
        return "citation_marker"

    if changed and not changed.strip():
        return "missing_or_extra_space"

    claim_tokens = set(claim_norm.split())
    matched_tokens = set(matched.split())
    if claim_tokens and matched_tokens:
        jaccard = len(claim_tokens & matched_tokens) / len(claim_tokens | matched_tokens)
        if jaccard >= 0.90:
            return "text_reordered"

    return "other"
