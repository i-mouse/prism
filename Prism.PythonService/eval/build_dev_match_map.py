"""CLI: builds docs/evals/dev_match_map.json from the hand-adjudicated refusal
rows in docs/evals/dev_adjudication_run1.md.

The 31 refusal-row verdicts below (claim index or "no match") are a one-time,
human-reviewed transcription of that file's "Adjudicated refusal rows" table -
not re-parsed from Markdown on every run, so a prose edit there doesn't
silently change this script's output. Supported rows (P*-S*) are not yet
adjudicated (dev_adjudication_run1.md "Open items") and are written as
all-null skeleton rows, same as eval/generate_match_map.py would produce for
an unadjudicated golden set.

Zero LLM calls - this only transcribes an already-completed human decision and
looks up claim text already sitting in docs/evals/fixtures/dev/run1/.

Usage:
  uv run python -m eval.build_dev_match_map
"""
import argparse
import json
from pathlib import Path

from eval.match_map import MatchMap, MatchMapMetadata, MatchMapRow, SCHEMA_VERSION, fingerprint_claim_text
from eval.matrix_loader import load_matrix
from extraction.prompt_version import get_prompt_version

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"

DECIDED_BY = "Nitin + Claude chat (dev_adjudication_run1.md)"
DECIDED_ON = "2026-10-12"

# row id -> (claim index in that paper's run1 fixture, or None for "no match" /
# extraction miss). Transcribed verbatim from dev_adjudication_run1.md's
# "Adjudicated refusal rows" table (31 rows: 18 with a claim index, 13 "none").
REFUSAL_ADJUDICATION: dict[str, int | None] = {
    "P7-R1": 5,
    "P7-R2": None,
    "P4-R1": 2,
    "P4-R2": 30,
    "P4-R3": None,
    "P2-R1": None,
    "P2-R3": None,
    "P2-R4": None,
    "P2-R5": 24,
    "P3-R1": None,
    "P3-R2": 3,
    "P1-R1": 32,
    "P1-R2": None,
    "P1-R3": 7,
    "P5-R1": 33,
    "P5-R2": 1,
    "P5-R3": None,
    "P6-R1": 4,
    "P6-R2": 3,
    "P8-R1": 6,
    "P8-R2": 7,
    "P8-R3": None,
    "P9-R1": None,
    "P10-R1": 3,
    "P10-R2": 4,
    "P10-R3": 16,
    "P11-R1": None,
    "P11-R2": 7,
    "P11-R3": None,
    "P12-R1": None,
    "P12-R2": 0,
}


def build(dev_eval_path: Path, fixture_dir: Path) -> MatchMap:
    matrix = load_matrix(dev_eval_path)
    golden_ids = [row.id for paper in matrix.papers for row in paper.expected_rows]

    missing_from_matrix = set(REFUSAL_ADJUDICATION) - set(golden_ids)
    if missing_from_matrix:
        raise ValueError(f"{dev_eval_path}: row ids adjudicated but not in dev_eval.json: {sorted(missing_from_matrix)}")

    rows: dict[str, MatchMapRow] = {row_id: MatchMapRow() for row_id in golden_ids}

    for paper in matrix.papers:
        fixture_path = fixture_dir / f"{paper.paper_id}.json"
        claims = None  # lazily loaded only if this paper has an adjudicated row
        for row in paper.expected_rows:
            if row.id not in REFUSAL_ADJUDICATION:
                continue
            claim_index = REFUSAL_ADJUDICATION[row.id]
            if claim_index is None:
                rows[row.id] = MatchMapRow(
                    confirmed_no_match=True, decided_by=DECIDED_BY, decided_on=DECIDED_ON,
                    reason="extraction miss - no claim in run 1 corresponds to this row",
                )
                continue
            if claims is None:
                claims = json.loads(fixture_path.read_text(encoding="utf-8"))["claims"]
            matching = [c for c in claims if c["index"] == claim_index]
            if len(matching) != 1:
                raise ValueError(f"{row.id}: claim index {claim_index} not found uniquely in {fixture_path}")
            fingerprint = fingerprint_claim_text(matching[0]["claim_text_verbatim"])
            rows[row.id] = MatchMapRow(
                claim_fingerprint=fingerprint, decided_by=DECIDED_BY, decided_on=DECIDED_ON,
                reason=f"adjudicated match to run1 claim index {claim_index}",
            )

    return MatchMap(
        metadata=MatchMapMetadata(
            prompt_hash=get_prompt_version(), fixture_file="dev/run1", schema_version=SCHEMA_VERSION
        ),
        rows=rows,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    match_map = build(args.dev_eval_path, args.fixture_dir)
    adjudicated = sum(1 for r in match_map.rows.values() if r.is_adjudicated)
    args.match_map_path.parent.mkdir(parents=True, exist_ok=True)
    args.match_map_path.write_text(match_map.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.match_map_path} ({len(match_map.rows)} rows, {adjudicated} adjudicated)")


if __name__ == "__main__":
    main()
