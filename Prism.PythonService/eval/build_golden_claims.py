"""CLI: writes the claims index for the golden replay (eval/replay_audit.py --set golden --claims <this file>):
every claim the golden matrix's frozen matches point at, so a golden replay covers exactly the claims the
golden rows are scored on. Zero LLM calls.

The golden papers come from the golden matrix (docs/evals/matrix_eval.json, through eval.matrix_loader), never
from a listing of the fixtures folder, which may hold files of other sets. Each paper's frozen `matches`
(written by eval/dump_fixture.py from the human match map) give {expected_id -> actual_index}; a null
actual_index is a row with no claim and is not listed. Claims several rows point at are listed once, with all
their row_ids. replay_audit reads only paper_id and claim_index; row_ids is for review.

--output-path is required and must not exist: this script never overwrites a file, and never writes the
dev Stage A index. It prints the final count and every shared claim.

Usage (from Prism.PythonService):
  uv run python -m eval.build_golden_claims --output-path docs/evals/exp1_golden_claims.json
"""
import argparse
import json
import sys
from pathlib import Path

from eval.build_stage_a_claims import check_new_output_path, group_by_claim
from eval.matrix_loader import load_matrix

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"


def build(matrix_path: Path, fixture_dir: Path) -> tuple[list[dict], list[dict]]:
    """Returns (entries, shared) as eval.build_stage_a_claims.group_by_claim does. Raises ValueError for a
    fixture without claims and matches, a match for a row the matrix does not have, or a match that points
    at a claim index the fixture does not have."""
    matrix = load_matrix(matrix_path)
    selected: list[dict] = []
    for paper in matrix.papers:
        fixture = json.loads((Path(fixture_dir) / f"{paper.paper_id}.json").read_text(encoding="utf-8"))
        if not isinstance(fixture, dict) or "claims" not in fixture or "matches" not in fixture:
            raise ValueError(f"{paper.paper_id}: fixture has no claims and matches (a legacy fixture? regenerate it)")
        claim_indices = {claim["index"] for claim in fixture["claims"]}
        row_ids = {row.id for row in paper.expected_rows}
        for match in fixture["matches"]:
            if match["expected_id"] not in row_ids:
                raise ValueError(f"{paper.paper_id}: match for {match['expected_id']}, which is not a row of the matrix")
            actual_index = match["actual_index"]
            if actual_index is None:
                continue
            if actual_index not in claim_indices:
                raise ValueError(
                    f"{paper.paper_id}: {match['expected_id']} points at claim #{actual_index}, which the fixture lacks"
                )
            selected.append({"row_id": match["expected_id"], "paper_id": paper.paper_id, "claim_index": actual_index})
    return group_by_claim(selected)


def _run(args: argparse.Namespace) -> int:
    problem = check_new_output_path(args.output_path, flag="build_golden_claims")
    if problem is not None:
        print(f"ERROR: {problem}")
        return 1
    output_path = Path(args.output_path)

    try:
        entries, shared = build(args.matrix_path, args.fixture_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    rows = sum(len(entry["row_ids"]) for entry in entries)
    print(f"Golden claims: {len(entries)} claims for {rows} matched rows ({len(shared)} shared claims)")
    for entry in shared:
        print(f"  shared: {entry['paper_id']} claim #{entry['claim_index']}: {', '.join(entry['row_ids'])}")

    try:
        with output_path.open("x", encoding="utf-8") as handle:  # "x": never overwrites
            handle.write(json.dumps(entries, indent=2))
    except FileExistsError:
        print(f"ERROR: {output_path} already exists, refusing to overwrite it")
        return 1
    print(f"\nwrote {output_path} ({len(entries)} claims)")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output-path", type=Path, default=None, help="required; must not exist")
    return parser


def main() -> None:
    sys.exit(_run(_build_parser().parse_args()))


if __name__ == "__main__":
    main()
