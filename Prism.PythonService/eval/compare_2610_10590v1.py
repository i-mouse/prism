"""B2 driver: score pass-1 / raw pass-2 / filtered pass-2 against the
inventory-derived answer key for arxiv-2610.10590v1, and apply the
pass-2 keep/drop rule.

Amends, per docs/decisions.md:
  - "Pass-2 keep/drop rule for the 2610.10590v1 comparison - 2026-10-18"
    (thresholds: gain >= 10pp, strict precision >= 0.70 - unchanged)
  - "Answer-key labelling and Phase B method for 2610.10590v1 - 2026-10-18"
    (overrides matching/banding; scores under TWO answer keys, A and B;
    different A/B verdicts -> DROP)

Pure scoring functions (decide_keep_drop, combine_verdicts, score_key) take
already-locked eval.inventory_compare.Candidate lists and plain id/size
values - no file I/O, no network, no LLM calls. Matching itself (shortlist +
one_to_one_match) is done once against the LARGER key (B, 78 items); Key A's
numbers are obtained by restricting those same locked matches to Key A's own
id set, not by rematching - so a filtered-pass-2 sentence that only matched
an "unsure" key item correctly stops counting once Key A excludes that item.

main()/write_report() do the real file I/O for an actual run; everything
else is unit-testable without touching disk.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from eval.inventory_compare import Candidate, Claim, recall, recall_gain_pp

GAIN_THRESHOLD_PP = 10.0
PRECISION_THRESHOLD = 0.70


# ---------------------------------------------------------------------------
# Pure decision functions
# ---------------------------------------------------------------------------
def decide_keep_drop(
    gain_pp: float,
    precision: float,
    gain_threshold_pp: float = GAIN_THRESHOLD_PP,
    precision_threshold: float = PRECISION_THRESHOLD,
) -> str:
    """"Pass 2 kept only if both: (a) recall gain >= 10pp; (b) strict
    precision >= 0.70." Returns "KEEP" or "DROP"."""
    if gain_pp >= gain_threshold_pp and precision >= precision_threshold:
        return "KEEP"
    return "DROP"


def combine_verdicts(verdict_a: str, verdict_b: str) -> str:
    """"final = verdict if A and B agree, else DROP." """
    return verdict_a if verdict_a == verdict_b else "DROP"


# ---------------------------------------------------------------------------
# Restricting one global (vs. Key B) matching run to a specific key's ids
# ---------------------------------------------------------------------------
def restrict_to_key(locked: list[Candidate], key_ids: set[str]) -> tuple[set[str], set[str]]:
    """Given matches locked against the superset key (B), keep only the ones
    whose key_id actually belongs to key_ids. Returns (matched_key_ids,
    matched_pipeline_ids) - both restricted."""
    kept = [c for c in locked if c.key_id in key_ids]
    return {c.key_id for c in kept}, {c.pipeline_id for c in kept}


@dataclass(frozen=True)
class KeyScore:
    recall_pass1: float
    recall_raw_pass2: float
    recall_filtered_pass2: float
    recall_combined: float
    gain_pp: float
    precision_filtered_pass2: float
    verdict: str


def score_key(
    key_claims: list[Claim],
    key_ids: set[str],
    pass1_locked: list[Candidate],
    raw_pass2_locked: list[Candidate],
    filtered_pass2_locked: list[Candidate],
    filtered_pass2_size: int,
) -> KeyScore:
    """One answer key's full set of metrics, per
    docs/decisions.md's 2026-10-18 entries:
      - recall per arm (pass1, raw pass2, filtered pass2) vs this key
      - combined = pass1 UNION filtered pass2 (matched key ids)
      - recall gain (pp) = (combined - pass1) / key, as percentage points
      - strict precision = filtered pass-2 sentences matching this key / its
        total size (filtered_pass2_size - NOT len(key): a pipeline sentence
        with no key match counts against precision)
      - verdict: KEEP iff gain >= 10pp AND precision >= 0.70
    key_claims must be the Claim objects whose ids == key_ids (used only so
    inventory_compare.recall/recall_gain_pp's len(key) denominator is right).
    """
    pass1_key_ids, _ = restrict_to_key(pass1_locked, key_ids)
    raw2_key_ids, _ = restrict_to_key(raw_pass2_locked, key_ids)
    filt2_key_ids, filt2_pipeline_ids = restrict_to_key(filtered_pass2_locked, key_ids)

    combined_key_ids = pass1_key_ids | filt2_key_ids

    r_pass1 = recall(pass1_key_ids, key_claims)
    r_raw2 = recall(raw2_key_ids, key_claims)
    r_filt2 = recall(filt2_key_ids, key_claims)
    r_combined = recall(combined_key_ids, key_claims)
    gain_pp = recall_gain_pp(pass1_key_ids, combined_key_ids, key_claims)
    precision = (len(filt2_pipeline_ids) / filtered_pass2_size) if filtered_pass2_size else 0.0

    verdict = decide_keep_drop(gain_pp, precision)
    return KeyScore(
        recall_pass1=r_pass1,
        recall_raw_pass2=r_raw2,
        recall_filtered_pass2=r_filt2,
        recall_combined=r_combined,
        gain_pp=gain_pp,
        precision_filtered_pass2=precision,
        verdict=verdict,
    )


@dataclass(frozen=True)
class ComparisonResult:
    score_a: KeyScore
    score_b: KeyScore
    final_verdict: str


def score_both_keys(
    key_a_claims: list[Claim],
    key_a_ids: set[str],
    key_b_claims: list[Claim],
    key_b_ids: set[str],
    pass1_locked: list[Candidate],
    raw_pass2_locked: list[Candidate],
    filtered_pass2_locked: list[Candidate],
    filtered_pass2_size: int,
) -> ComparisonResult:
    score_a = score_key(key_a_claims, key_a_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, filtered_pass2_size)
    score_b = score_key(key_b_claims, key_b_ids, pass1_locked, raw_pass2_locked, filtered_pass2_locked, filtered_pass2_size)
    final = combine_verdicts(score_a.verdict, score_b.verdict)
    return ComparisonResult(score_a=score_a, score_b=score_b, final_verdict=final)


# ---------------------------------------------------------------------------
# Real-run file I/O (not exercised by unit tests)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent
INVENTORY_DIR = REPO_ROOT / "docs" / "evals" / "claim_inventory" / "arxiv-2610.10590v1"


def write_report(path: Path, result: ComparisonResult, extra_sections: str) -> None:
    lines = [
        "# pass-1 vs pass-2 comparison - arxiv-2610.10590v1",
        "",
        "Amends, per docs/decisions.md:",
        '- "Pass-2 keep/drop rule for the 2610.10590v1 comparison - 2026-10-18"',
        "  (thresholds unchanged: gain >= 10pp, strict precision >= 0.70)",
        '- "Answer-key labelling and Phase B method for 2610.10590v1 - 2026-10-18"',
        "  (matching/banding override; scored under two answer keys A and B;",
        "  different A/B verdicts -> DROP)",
        "",
        "## Score under Key A (reconciled + disputed \"claim\" only)",
        "",
        f"- Recall pass 1: {result.score_a.recall_pass1:.3f}",
        f"- Recall raw pass 2: {result.score_a.recall_raw_pass2:.3f}",
        f"- Recall filtered pass 2: {result.score_a.recall_filtered_pass2:.3f}",
        f"- Recall combined (pass 1 ∪ filtered pass 2): {result.score_a.recall_combined:.3f}",
        f"- Recall gain (pp): {result.score_a.gain_pp:.2f}",
        f"- Strict precision (filtered pass 2): {result.score_a.precision_filtered_pass2:.3f}",
        f"- Verdict under Key A: {result.score_a.verdict}",
        "",
        "## Score under Key B (reconciled + disputed \"claim\" + \"unsure\")",
        "",
        f"- Recall pass 1: {result.score_b.recall_pass1:.3f}",
        f"- Recall raw pass 2: {result.score_b.recall_raw_pass2:.3f}",
        f"- Recall filtered pass 2: {result.score_b.recall_filtered_pass2:.3f}",
        f"- Recall combined (pass 1 ∪ filtered pass 2): {result.score_b.recall_combined:.3f}",
        f"- Recall gain (pp): {result.score_b.gain_pp:.2f}",
        f"- Strict precision (filtered pass 2): {result.score_b.precision_filtered_pass2:.3f}",
        f"- Verdict under Key B: {result.score_b.verdict}",
        "",
        "## Final verdict",
        "",
        f"**{result.final_verdict}** "
        f"(Key A: {result.score_a.verdict}, Key B: {result.score_b.verdict} -> "
        + ("agree" if result.score_a.verdict == result.score_b.verdict else "disagree, DROP per rule")
        + ")",
        "",
        extra_sections,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(INVENTORY_DIR / "comparison_pass1_pass2.md"))
    return parser


def main(argv: list[str] | None = None) -> None:
    # Real-run wiring (loading the three pipeline arms, the two keys, the
    # locked matches) lives in the B1/B2 orchestration step, not here - this
    # main() is a placeholder CLI entrypoint for --out path validation only,
    # consistent with inventory_compare.py being a library of pure functions.
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(
        f"compare_2610_10590v1.main() is a placeholder; wire real locked matches "
        f"before running. Intended output: {args.out}"
    )


if __name__ == "__main__":
    main()
