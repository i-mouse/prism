"""CLI: resolves docs/evals/dev_match_map.json's claim-fingerprint rows back to
{paper_id, claim_index} pairs and writes docs/evals/exp1_stage_a_claims.json -
the claim set eval/replay_audit.py --claims consumes for Experiment 1 Stage A.

Only rows with claim_fingerprint set are included (a real claim exists to
re-audit) - rows with only confirmed_no_match (extraction misses) are excluded,
since there is nothing to re-audit. Prints the resolved list for review before
anything is spent on it. Zero LLM calls.

Usage:
  uv run python -m eval.build_stage_a_claims
"""
import argparse
import json
from pathlib import Path

from eval.match_map import fingerprint_claim_text, load_match_map
from eval.matrix_loader import load_matrix

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "evals" / "exp1_stage_a_claims.json"


def _resolve(fixture_dir: Path, paper_ids: list[str]) -> dict[str, int]:
    """Returns {claim_fingerprint: claim_index} across all given papers' run1
    fixtures, keyed only by papers that actually contain that fingerprint."""
    by_fingerprint: dict[str, tuple[str, int]] = {}
    for paper_id in paper_ids:
        claims = json.loads((fixture_dir / f"{paper_id}.json").read_text(encoding="utf-8"))["claims"]
        for claim in claims:
            fp = fingerprint_claim_text(claim["claim_text_verbatim"])
            by_fingerprint[fp] = (paper_id, claim["index"])
    return by_fingerprint


def build(dev_eval_path: Path, match_map_path: Path, fixture_dir: Path) -> list[dict]:
    matrix = load_matrix(dev_eval_path)
    golden_ids = {row.id for paper in matrix.papers for row in paper.expected_rows}
    match_map = load_match_map(match_map_path, golden_ids)
    paper_ids = [paper.paper_id for paper in matrix.papers]

    by_fingerprint = _resolve(fixture_dir, paper_ids)

    selected = []
    for row_id, row in sorted(match_map.rows.items()):
        if row.claim_fingerprint is None:
            continue
        resolved = by_fingerprint.get(row.claim_fingerprint)
        if resolved is None:
            raise ValueError(f"{row_id}: claim_fingerprint {row.claim_fingerprint[:12]} not found in any run1 fixture")
        paper_id, claim_index = resolved
        selected.append({"row_id": row_id, "paper_id": paper_id, "claim_index": claim_index})
    return selected


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    selected = build(args.dev_eval_path, args.match_map_path, args.fixture_dir)

    print(f"Resolved {len(selected)} Stage A claims:")
    for entry in selected:
        print(f"  {entry['row_id']:<8} -> {entry['paper_id']} claim #{entry['claim_index']}")

    # replay_audit.py --claims consumes only paper_id/claim_index; row_id is kept
    # in the file purely for human review/debugging.
    args.output_path.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(f"\nwrote {args.output_path} ({len(selected)} claims)")


if __name__ == "__main__":
    main()
