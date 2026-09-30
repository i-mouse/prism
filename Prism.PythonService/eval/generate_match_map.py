"""CLI: emits an all-null match_map.json skeleton, one entry per golden row.

This script never adjudicates anything - every field of every row is null.
A human fills in claim_fingerprint (and optionally persisted_claim_id) by
hand after reviewing the actual matcher output for that row. Refuses to
overwrite an existing map that already has any adjudicated entry, so a
re-run can't silently wipe human work.

Usage:
  uv run python -m eval.generate_match_map
"""
import argparse
import sys
from pathlib import Path

from eval.match_map import MatchMap, MatchMapMetadata, MatchMapRow, SCHEMA_VERSION
from eval.matrix_loader import MatrixSpec, load_matrix
from extraction.prompt_version import get_prompt_version

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "match_map.json"


def _golden_ids(matrix_spec: MatrixSpec) -> list[str]:
    return [row.id for paper in matrix_spec.papers for row in paper.expected_rows]


def _existing_map_has_adjudication(path: Path) -> bool:
    """True if `path` exists and already has at least one non-null entry."""
    if not path.exists():
        return False
    try:
        raw = path.read_text(encoding="utf-8")
        existing = MatchMap.model_validate_json(raw)
    except Exception:
        # Unparseable/legacy content is not "adjudicated" in the schema
        # sense, but overwriting garbage silently is still risky - treat it
        # as adjudicated so the human has to look before regenerating.
        return True
    return any(row.is_adjudicated for row in existing.rows.values())


def generate(matrix_path: Path, match_map_path: Path, fixture_file: str | None) -> int:
    if _existing_map_has_adjudication(match_map_path):
        print(
            f"Refusing to overwrite {match_map_path}: it already has at least one "
            "adjudicated row. Delete or move it aside first if you really want a "
            "fresh skeleton.",
            file=sys.stderr,
        )
        return 1

    matrix_spec = load_matrix(matrix_path)
    golden_ids = _golden_ids(matrix_spec)

    match_map = MatchMap(
        metadata=MatchMapMetadata(
            prompt_hash=get_prompt_version(),
            fixture_file=fixture_file,
            schema_version=SCHEMA_VERSION,
        ),
        rows={row_id: MatchMapRow() for row_id in golden_ids},
    )

    match_map_path.parent.mkdir(parents=True, exist_ok=True)
    match_map_path.write_text(match_map.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"wrote {match_map_path} ({len(golden_ids)} rows, all unadjudicated)")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an all-null match_map.json skeleton")
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument(
        "--fixture-file", default=None, help="fixture filename to stamp into metadata (informational only)"
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(generate(args.matrix_path, args.match_map_path, args.fixture_file))


if __name__ == "__main__":
    main()
