"""CLI: pre-fills docs/evals/match_map.json rows with a fuzzy-match
suggestion for a human to review and confirm - it never adjudicates.

For each of the 37 golden rows, finds the best-scoring actual claim (by
rapidfuzz token_sort_ratio on claim_text_verbatim, same library already used
in extraction/grounding.py Stage 1) within the SAME paper's fixture only,
and writes only the additive `suggested` field: claim_fingerprint, score,
and a short text snippet for quick eyeballing. Leaves `suggested` null when
nothing scores above SCORE_FLOOR.

This script NEVER writes persisted_claim_id, claim_fingerprint, decided_by,
decided_on, or reason - the fields matrix_runner.py's coverage gate actually
reads. A suggestion is not an adjudication, no matter the score: a human
still has to copy suggested.claim_fingerprint into claim_fingerprint (or
confirm a genuine omission) and fill in decided_by/decided_on/reason by
hand. See docs/decisions.md and RUNBOOK.md for the two-step review flow.

Usage:
  uv run python -m eval.suggest_match_map
"""
import argparse
import json
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from eval.data_source import read_from_fixture
from eval.match_map import MatchMap, fingerprint_claim_text
from eval.matrix_loader import MatrixSpec, load_matrix
from eval.types import ActualClaim

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "match_map.json"

SCORE_FLOOR = 60
SNIPPET_LENGTH = 120


def _best_candidate(golden_text: str, actual_claims: list[ActualClaim]) -> Optional[tuple[ActualClaim, float]]:
    """Returns (best actual claim, score) scoring highest against
    golden_text by rapidfuzz token_sort_ratio, or None if the paper has no
    claim with verbatim text or nothing clears SCORE_FLOOR. Ties keep the
    first (lowest-index) candidate, since fixture claims are already
    ordered by created_at ascending."""
    best_claim: Optional[ActualClaim] = None
    best_score = -1.0
    for claim in actual_claims:
        if not claim.claim_text_verbatim:
            continue
        score = fuzz.token_sort_ratio(golden_text, claim.claim_text_verbatim)
        if score > best_score:
            best_score = score
            best_claim = claim

    if best_claim is None or best_score <= SCORE_FLOOR:
        return None
    return best_claim, best_score


def suggest(matrix_path: Path, fixture_dir: Path, match_map_path: Path) -> list[dict]:
    """Writes match_map_path's `suggested` fields in place - every other
    field (including metadata) passes through untouched - and returns the
    per-row summary list ({id, score, snippet}) for console printing, in
    golden-row order."""
    matrix_spec: MatrixSpec = load_matrix(matrix_path)
    match_map_raw = json.loads(match_map_path.read_text(encoding="utf-8"))
    rows_raw = match_map_raw["rows"]

    summary: list[dict] = []

    for paper in matrix_spec.papers:
        fixture_path = fixture_dir / f"{paper.paper_id}.json"
        try:
            actual_claims = read_from_fixture(fixture_path)
        except Exception as exc:
            for row in paper.expected_rows:
                _row_raw(rows_raw, row.id)["suggested"] = None
                summary.append({"id": row.id, "score": None, "snippet": f"FIXTURE READ FAILED: {exc}"})
            continue

        for row in paper.expected_rows:
            row_raw = _row_raw(rows_raw, row.id)
            candidate = _best_candidate(row.claim_text_verbatim, actual_claims)

            if candidate is None:
                row_raw["suggested"] = None
                summary.append({"id": row.id, "score": None, "snippet": "NO CANDIDATE — likely not extracted"})
            else:
                claim, score = candidate
                snippet = claim.claim_text_verbatim[:SNIPPET_LENGTH]
                row_raw["suggested"] = {
                    "claim_fingerprint": fingerprint_claim_text(claim.claim_text_verbatim),
                    "score": round(score, 1),
                    "claim_text_snippet": snippet,
                }
                summary.append({"id": row.id, "score": round(score, 1), "snippet": snippet})

    # Sanity check before writing: the file we're about to write must still
    # validate as a MatchMap (catches a corrupt match_map.json early, loudly,
    # instead of silently writing something matrix_runner can't load).
    MatchMap.model_validate(match_map_raw)

    match_map_path.write_text(json.dumps(match_map_raw, indent=2) + "\n", encoding="utf-8")
    return summary


def _row_raw(rows_raw: dict, row_id: str) -> dict:
    if row_id not in rows_raw:
        raise ValueError(
            f"match_map.json has no row for golden id {row_id!r} - regenerate the skeleton first "
            "('uv run python -m eval.generate_match_map')"
        )
    return rows_raw[row_id]


def _print_summary(summary: list[dict]) -> None:
    id_width = max((len(row["id"]) for row in summary), default=2)
    for row in summary:
        score_display = "  -- " if row["score"] is None else f"{row['score']:5.1f}"
        print(f"{row['id'].ljust(id_width)}   {score_display}   {row['snippet']}")

    no_candidate = sum(1 for row in summary if row["score"] is None)
    print()
    print(f"{no_candidate}/{len(summary)} rows have no candidate above {SCORE_FLOOR} " "(likely not_extracted / omission rows).")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pre-fill match_map.json's `suggested` field with fuzzy-match candidates for human review"
    )
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    summary = suggest(args.matrix_path, args.fixture_dir, args.match_map_path)
    _print_summary(summary)


if __name__ == "__main__":
    main()
