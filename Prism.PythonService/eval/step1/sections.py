"""Pure section logic for 1c: heading lines, caption lines and the bucket of a match offset. No I/O and no heavy
imports. The method is fixed by Nitin (2026-11-11) and is not tuned after a run:

- Heading line = a line of <= 80 chars that, after stripping a leading section number ("1", "2.3", "A.1", "IV."),
  starts (case-insensitive) with one of HEADING_STARTS. "Starts with" is literal, so "Methodology" also counts.
- Bucket by the nearest heading line before the match: Abstract -> abstract; Introduction -> introduction;
  Conclusion(s) -> conclusion; any position after the LAST References/Bibliography heading -> appendix (overrides);
  everything else -> body. No heading before the match -> abstract if the position is < 5% of the paper, else body
  with low confidence.
- Caption = the match starts within 300 chars after a line that starts with "Table N", "Figure N" or "Fig. N"
  (measured from the start of that line, so a match inside the caption line itself counts). Caption overrides every
  bucket except appendix; the bucket underneath is reported too.
- Confidence is low when the match was not found whole, the best fuzzy score is below the threshold, or there is no
  heading before the match past 5%.
"""
import re
from collections.abc import Iterator
from dataclasses import dataclass

BUCKETS = ("abstract", "introduction", "body", "conclusion", "appendix", "table or figure caption", "not found whole")
HEADING_STARTS = (
    "abstract", "introduction", "background", "related work", "method", "methods", "approach", "experiments",
    "experimental", "results", "evaluation", "analysis", "discussion", "limitations", "conclusion", "conclusions",
    "references", "bibliography", "acknowledgments", "acknowledgements", "appendix", "supplementary",
)
MAX_HEADING_CHARS = 80
EARLY_FRACTION = 0.05            # of the paper: a match before any heading this early is the abstract
CAPTION_WINDOW = 300

_NUMBER_RE = re.compile(r"^(?:(?:\d+(?:\.\d+)*|[A-Z](?:\.\d+)+)\.?|[IVXLC]+\.)\s+")
_CAPTION_RE = re.compile(r"^\s*(?:table|figure|fig\.)\s*\d+", re.IGNORECASE)


@dataclass(frozen=True)
class Heading:
    offset: int          # raw-text offset of the start of the line
    line: str            # the stripped line (<= 80 chars)
    kind: str            # "abstract" | "introduction" | "conclusion" | "references" | "other"


@dataclass(frozen=True)
class Placement:
    bucket: str
    underneath: str | None           # the bucket before the caption override; None when not found whole
    heading: str                     # nearest heading line before the match, "" if none
    confidence: str                  # "high" | "low"
    reasons: tuple[str, ...]         # why the confidence is low
    position_pct: float | None


def heading_kind(line: str) -> str | None:
    """The kind of heading this line is, or None if it is not a heading line."""
    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_CHARS:
        return None
    lowered = _NUMBER_RE.sub("", stripped, count=1).lower()
    for word in HEADING_STARTS:
        if lowered.startswith(word):
            if word == "abstract":
                return "abstract"
            if word == "introduction":
                return "introduction"
            if word in ("conclusion", "conclusions"):
                return "conclusion"
            if word in ("references", "bibliography"):
                return "references"
            return "other"
    return None


def _lines(text: str) -> Iterator[tuple[int, str]]:
    offset = 0
    for raw in text.splitlines(keepends=True):
        yield offset, raw.rstrip("\r\n")
        offset += len(raw)


def find_headings(text: str) -> list[Heading]:
    out = []
    for offset, line in _lines(text):
        kind = heading_kind(line)
        if kind is not None:
            out.append(Heading(offset, line.strip(), kind))
    return out


def find_caption_starts(text: str) -> list[int]:
    return [offset for offset, line in _lines(text) if _CAPTION_RE.match(line)]


def is_caption(match_start: int, caption_starts: list[int]) -> bool:
    return any(0 <= match_start - c <= CAPTION_WINDOW for c in caption_starts)


def assign_bucket(
    match_start: int | None, text_len: int, headings: list[Heading], caption_starts: list[int],
    found_whole: bool, score: float, threshold: float,
) -> Placement:
    """Bucket of a match at raw offset match_start. A match that is neither whole nor fuzzy-matched at or above
    `threshold` has no usable location and lands in "not found whole"."""
    usable = match_start is not None and (found_whole or score >= threshold)
    if not usable or match_start is None:
        return Placement("not found whole", None, "", "low", ("no usable match",), None)

    position_pct = 100.0 * match_start / text_len if text_len else 0.0
    ordered = sorted(headings, key=lambda h: h.offset)
    reasons: list[str] = []
    if not found_whole:
        reasons.append("not found whole")
    if score < threshold:
        reasons.append(f"fuzzy score {score:.1f} below {threshold:g}")

    before = [h for h in ordered if h.offset <= match_start]
    nearest = before[-1] if before else None
    reference_offsets = [h.offset for h in ordered if h.kind == "references"]
    last_references = max(reference_offsets) if reference_offsets else None

    if last_references is not None and match_start > last_references:
        underneath = "appendix"
    elif nearest is None:
        if position_pct < 100 * EARLY_FRACTION:
            underneath = "abstract"
        else:
            underneath = "body"
            reasons.append("no heading before the match past 5%")
    elif nearest.kind in ("abstract", "introduction", "conclusion"):
        underneath = nearest.kind
    else:
        underneath = "body"

    bucket = "table or figure caption" if underneath != "appendix" and is_caption(match_start, caption_starts) else underneath
    return Placement(
        bucket, underneath, nearest.line if nearest else "", "low" if reasons else "high", tuple(reasons),
        position_pct,
    )


def bucket_totals(buckets: list[str]) -> dict[str, int]:
    return {b: sum(1 for x in buckets if x == b) for b in BUCKETS}
