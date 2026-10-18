"""Compare an inventory-derived answer key against pipeline extraction
output for one dev paper (arxiv-2610.10590v1).

Matching/banding rules follow docs/decisions.md's "Answer-key labelling and
Phase B method for 2610.10590v1 - 2026-10-18", which overrides the
token_set_ratio-based rule in the original Phase B1/B2 brief:
  - fuzz.ratio >= 90                         -> auto match
  - fuzz.ratio in [60, 89] OR partial_ratio >= 90 -> borderline (human review)
  - otherwise                                -> no match
Matching is one-to-one per arm: a key claim is matched at most once, a
pipeline claim is matched at most once, resolved greedily by score.

Pure functions only (load / normalize / shortlist / match / score). No
network. No LLM calls.
"""
import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# normalize_for_match: verbatim copy of extraction/grounding.py lines 253-282.
# Not imported, because `import extraction.grounding` pulls in
# `from config import settings`, and config.py instantiates `PrismSettings()`
# at module import time - which reads .env immediately. This module and its
# tests must never read .env, so the function is inlined instead.
# ---------------------------------------------------------------------------
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")
_QUOTE_DASH_TABLE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-",
})


def _join_hyphen_linebreak(m: re.Match) -> str:
    if m.group(2).islower():
        return m.group(1) + m.group(2)
    return m.group(0)


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")
    text = _HYPHEN_LINEBREAK_RE.sub(_join_hyphen_linebreak, text)
    text = text.translate(_QUOTE_DASH_TABLE)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Claim:
    id: str
    sentence: str
    section: str = ""


Band = str  # "auto" | "borderline" | "none"


@dataclass(frozen=True)
class Candidate:
    key_id: str
    pipeline_id: str
    fuzz_ratio: float
    partial_ratio: float
    band: Band


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_claims_from_json(
    path: str | Path, id_field: str = "id", sentence_field: str = "claim_text_verbatim"
) -> list[Claim]:
    """Load a pipeline fixture: a JSON object with a 'claims' list (or a bare
    list), each item having at least a sentence field. id defaults to a
    positional index when id_field is absent on an item."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data["claims"] if isinstance(data, dict) else data
    out = []
    for i, item in enumerate(items):
        cid = str(item.get(id_field, i))
        out.append(Claim(id=cid, sentence=item[sentence_field]))
    return out


def filter_by_pass(
    claims_raw: list[dict], pass_value: str, sentence_field: str = "claim_text_verbatim"
) -> list[Claim]:
    """Select only entries whose 'pass' field equals pass_value, e.g. to split
    a merged or filtered fixture's full claim list into its pass1/pass2
    members."""
    out = []
    for i, item in enumerate(claims_raw):
        if item.get("pass") != pass_value:
            continue
        out.append(Claim(id=f"{pass_value}-{i}", sentence=item[sentence_field]))
    return out


def load_pass_split(path: str | Path, pass_value: str) -> list[Claim]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return filter_by_pass(data["claims"], pass_value)


def load_key_from_rows(rows: list[dict]) -> list[Claim]:
    """rows: [{"id": ..., "sentence": ..., "section": ...}, ...]. Callers
    parse the reconciled/disputed markdown tables and decide which rows
    belong in a given answer key (A or B); this just wraps them as Claims."""
    return [Claim(id=r["id"], sentence=r["sentence"], section=r.get("section", "")) for r in rows]


# ---------------------------------------------------------------------------
# Shortlist + banding
# ---------------------------------------------------------------------------
def band_for(fuzz_ratio: float, partial_ratio: float) -> Band:
    if fuzz_ratio >= 90:
        return "auto"
    if fuzz_ratio >= 60 or partial_ratio >= 90:
        return "borderline"
    return "none"


def shortlist(key: list[Claim], pipeline: list[Claim]) -> list[Candidate]:
    """Every (key, pipeline) pair, scored by fuzz.ratio and partial_ratio on
    normalize_for_match'd text and banded via band_for. 'none'-band pairs are
    included too, so a caller can audit what was excluded and why."""
    key_norm = {c.id: normalize_for_match(c.sentence) for c in key}
    pipe_norm = {c.id: normalize_for_match(c.sentence) for c in pipeline}
    out = []
    for k in key:
        for p in pipeline:
            fr = fuzz.ratio(key_norm[k.id], pipe_norm[p.id])
            pr = fuzz.partial_ratio(key_norm[k.id], pipe_norm[p.id])
            out.append(Candidate(k.id, p.id, fr, pr, band_for(fr, pr)))
    return out


# ---------------------------------------------------------------------------
# One-to-one matching
# ---------------------------------------------------------------------------
_BAND_ORDER = {"none": 0, "borderline": 1, "auto": 2}


def one_to_one_match(candidates: list[Candidate], min_band: Band = "borderline") -> list[Candidate]:
    """Greedy highest-fuzz_ratio-first matching (ties broken by partial_ratio)
    among candidates whose band is at least min_band ('borderline' admits
    both 'auto' and 'borderline'; 'auto' admits only 'auto'). Each key_id and
    each pipeline_id appears in at most one returned Candidate."""
    allowed = [c for c in candidates if _BAND_ORDER[c.band] >= _BAND_ORDER[min_band]]
    allowed = sorted(allowed, key=lambda c: (-c.fuzz_ratio, -c.partial_ratio))
    used_key: set[str] = set()
    used_pipeline: set[str] = set()
    locked = []
    for c in allowed:
        if c.key_id in used_key or c.pipeline_id in used_pipeline:
            continue
        used_key.add(c.key_id)
        used_pipeline.add(c.pipeline_id)
        locked.append(c)
    return locked


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def recall(matched_key_ids: set[str], key: list[Claim]) -> float:
    if not key:
        return 0.0
    return len(matched_key_ids) / len(key)


def strict_precision(matched_pipeline_ids: set[str], pipeline: list[Claim]) -> float:
    """Strict: a pipeline sentence with no key match counts against precision -
    it is not a claim, per the 2026-10-17 claim-boundary rule."""
    if not pipeline:
        return 0.0
    return len(matched_pipeline_ids) / len(pipeline)


def recall_gain_pp(base_matched: set[str], combined_matched: set[str], key: list[Claim]) -> float:
    """Percentage points: key claims matched by the combined arm that the
    base arm did NOT match, over the key size."""
    if not key:
        return 0.0
    gained = combined_matched - base_matched
    return 100.0 * len(gained) / len(key)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cmd_match(args: argparse.Namespace) -> None:
    key_rows = json.loads(Path(args.key).read_text(encoding="utf-8"))
    key = load_key_from_rows(key_rows)
    pipeline = load_claims_from_json(args.pipeline)
    candidates = shortlist(key, pipeline)
    print(json.dumps([c.__dict__ for c in candidates], indent=1))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    match_cmd = sub.add_parser("match", help="Shortlist + band key vs. pipeline claims")
    match_cmd.add_argument("--key", required=True, help="JSON file: list of {id, sentence, section}")
    match_cmd.add_argument("--pipeline", required=True, help="Pipeline fixture JSON with a 'claims' list")
    match_cmd.set_defaults(func=_cmd_match)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
