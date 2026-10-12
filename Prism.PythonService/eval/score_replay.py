"""CLI: scores one or more replay fixture directories (run 1 itself, or an
Experiment 1 exp1_<level>_<n>/ directory) against the 31 hand-adjudicated
refusal rows in docs/evals/dev_match_map.json. Zero LLM calls -
eval.scorer.score() is pure/no-I/O (see its own docstring).

A --claims-scoped replay directory (header.claims_scope present in its
fixture files) is scored only on the refusal rows whose matched claim index
is in that scope - a row with no replayed data for this directory would
otherwise silently score stale run-1 output as if it were part of the
replay. Extraction-miss rows (no claim exists under any replay) are always
scored, since scope never changes their outcome.

Pass --fixture-dir more than once to score several repeats in run order and
see each row's label flip across repeats, e.g. "P7-R1: S, PS, PS".

Usage:
  uv run python -m eval.score_replay --fixture-dir docs/evals/fixtures/dev/run1
  uv run python -m eval.score_replay --fixture-dir docs/evals/fixtures/dev/exp1_high_1 \
      --fixture-dir docs/evals/fixtures/dev/exp1_high_2 --fixture-dir docs/evals/fixtures/dev/exp1_high_3
"""
import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from eval.match_map import load_match_map
from eval.matrix_loader import load_matrix
from eval.scorer import score
from eval.types import ActualClaim, ExpectedRow, Match

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"


@dataclass
class AdjudicatedRow:
    row_id: str
    paper_id: str
    claim_index: int | None  # None = confirmed_no_match (extraction miss)
    expected_row: ExpectedRow


def resolve_adjudicated_rows(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path) -> list[AdjudicatedRow]:
    matrix = load_matrix(dev_eval_path)
    golden_ids = {row.id for paper in matrix.papers for row in paper.expected_rows}
    match_map = load_match_map(match_map_path, golden_ids)

    by_fingerprint: dict[str, tuple[str, int]] = {}
    for paper in matrix.papers:
        fixture_path = run1_fixture_dir / f"{paper.paper_id}.json"
        if not fixture_path.exists():
            continue
        claims = json.loads(fixture_path.read_text(encoding="utf-8"))["claims"]
        from eval.match_map import fingerprint_claim_text

        for claim in claims:
            by_fingerprint[fingerprint_claim_text(claim["claim_text_verbatim"])] = (paper.paper_id, claim["index"])

    resolved = []
    for paper in matrix.papers:
        for row in paper.expected_rows:
            map_row = match_map.rows.get(row.id)
            if map_row is None or not map_row.is_adjudicated:
                continue
            if map_row.confirmed_no_match:
                resolved.append(AdjudicatedRow(row_id=row.id, paper_id=paper.paper_id, claim_index=None, expected_row=row))
                continue
            paper_id, claim_index = by_fingerprint[map_row.claim_fingerprint]
            resolved.append(AdjudicatedRow(row_id=row.id, paper_id=paper_id, claim_index=claim_index, expected_row=row))
    return resolved


def _load_fixture(fixture_dir: Path, paper_id: str) -> dict | None:
    path = fixture_dir / f"{paper_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def score_directory(rows: list[AdjudicatedRow], fixture_dir: Path) -> tuple[dict, dict]:
    """Returns (per_row_outcome, per_row_actual_label) across all papers the
    adjudicated rows touch, restricted to each fixture's claims_scope when
    present."""
    by_paper: dict[str, list[AdjudicatedRow]] = defaultdict(list)
    for row in rows:
        by_paper[row.paper_id].append(row)

    per_row_outcome: dict[str, str] = {}
    per_row_label: dict[str, str | None] = {}

    for paper_id, paper_rows in by_paper.items():
        fixture = _load_fixture(fixture_dir, paper_id)
        if fixture is None:
            for row in paper_rows:
                per_row_outcome[row.row_id] = "FIXTURE_MISSING"
                per_row_label[row.row_id] = None
            continue

        claims_scope = fixture["header"].get("claims_scope")
        scored_rows = [
            row for row in paper_rows
            if row.claim_index is None or claims_scope is None or row.claim_index in claims_scope
        ]
        out_of_scope = [row for row in paper_rows if row not in scored_rows]
        for row in out_of_scope:
            per_row_outcome[row.row_id] = "OUT_OF_SCOPE"
            per_row_label[row.row_id] = None
        if not scored_rows:
            continue

        actual_claims = [ActualClaim(**claim) for claim in fixture["claims"]]
        expected_rows = [row.expected_row for row in scored_rows]
        matches = [Match(expected_id=row.row_id, actual_index=row.claim_index) for row in scored_rows]

        report = score(expected_rows, actual_claims, matches, positive_hit_floor=0)
        for row in scored_rows:
            outcome = report.per_row[row.row_id]
            per_row_outcome[row.row_id] = outcome.outcome
            per_row_label[row.row_id] = outcome.actual_label

    return per_row_outcome, per_row_label


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture-dir", action="append", required=True, dest="fixture_dirs", type=Path)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    rows = resolve_adjudicated_rows(args.dev_eval_path, args.match_map_path, args.run1_fixture_dir)

    results = [score_directory(rows, d) for d in args.fixture_dirs]

    for fixture_dir, (outcomes, _) in zip(args.fixture_dirs, results):
        scored = [o for o in outcomes.values() if o not in ("OUT_OF_SCOPE", "FIXTURE_MISSING")]
        hits = sum(1 for o in scored if o == "REFUSED")
        print(f"{fixture_dir}: {hits}/{len(scored)} refusal hits (scored {len(scored)}/{len(rows)} adjudicated rows)")

    if len(args.fixture_dirs) > 1:
        print("\nPer-row label across repeats:")
        for row in rows:
            labels = [results_i[1].get(row.row_id) or results_i[0].get(row.row_id) for results_i in results]
            print(f"  {row.row_id}: {', '.join(str(l) for l in labels)}")


if __name__ == "__main__":
    main()
