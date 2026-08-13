"""CLI: verifies every paper's committed fixture matches the current prompt.

Pure hash comparison — no LLM, no DB. Run in CI ahead of matrix_runner so a
stale or legacy fixture is caught with a clear, per-paper message instead
of silently scoring against out-of-date extraction data.
"""
import argparse
import sys
from pathlib import Path

from eval.data_source import get_fixture_header, read_matches_from_fixture
from eval.matrix_loader import MatrixSpec, load_matrix
from extraction.prompt_version import get_prompt_version

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"


def _check_paper(paper_id: str, fixture_dir: Path, current_hash: str) -> tuple[bool, str]:
    """Returns (fresh, message) for one paper's fixture."""
    fixture_path = fixture_dir / f"{paper_id}.json"

    if not fixture_path.exists():
        return False, f"missing fixture for {paper_id} (expected at {fixture_path})."

    header = get_fixture_header(fixture_path)
    if header is None:
        return False, (
            f"{paper_id}: legacy fixture with no prompt_hash. Regenerate via "
            f"'uv run python -m eval.dump_fixture --paper {paper_id}'."
        )

    fixture_hash = header.get("prompt_hash", "")
    if fixture_hash != current_hash:
        return False, (
            f"{paper_id}: fixture prompt_hash={fixture_hash[:8]} does not match "
            f"current={current_hash[:8]}. Regenerate via "
            f"'uv run python -m eval.dump_fixture --paper {paper_id}'."
        )

    if not read_matches_from_fixture(fixture_path):
        return False, (
            f"{paper_id}: fixture missing frozen matches. Regenerate via "
            f"'uv run python -m eval.dump_fixture --paper {paper_id}'."
        )

    return True, f"{paper_id}: OK (prompt_hash={current_hash[:8]})"


def check_freshness(matrix_path: Path, fixture_dir: Path) -> int:
    matrix_spec: MatrixSpec = load_matrix(matrix_path)
    current_hash = get_prompt_version()

    all_fresh = True
    for paper in matrix_spec.papers:
        fresh, message = _check_paper(paper.paper_id, fixture_dir, current_hash)
        print(message)
        all_fresh = all_fresh and fresh

    return 0 if all_fresh else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check committed fixtures against the current prompt hash")
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(check_freshness(args.matrix_path, args.fixture_dir))


if __name__ == "__main__":
    main()
