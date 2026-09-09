"""CLI: verifies every paper's committed fixture matches the current
extraction prompt AND the current matcher (model routing + gold-set
accuracy).

Pure hash/field comparison - no LLM calls, no DB queries. Run in CI ahead
of matrix_runner so a stale or legacy fixture is caught with a clear,
per-paper message naming the exact fix command instead of silently scoring
against out-of-date extraction data or matches frozen under a matcher
configuration that has since changed or was never gold-set verified.

Three independent checks, each pointing at a different regen path:
  prompt_hash            -> full regen (eval.dump_fixture): extraction
                            itself changed, claims must be re-extracted.
  matcher_fingerprint     -> re-match only (eval.rematch_fixture): only the
                            matcher's model routing or prompt changed;
                            claims are still valid, only matches need
                            refreshing.
  matcher_gold_pass_rate  -> re-verify (eval.verify_matcher_gold): the
                            matcher was never calibrated against the gold
                            set, or its last calibration is now stale
                            (eval.rematch_fixture clears this field on
                            purpose - see that module's docstring) or fell
                            below the accuracy floor.
"""
import argparse
import sys
from pathlib import Path

from eval.data_source import get_fixture_header, read_matches_from_fixture
from eval.dump_fixture import get_matcher_fingerprint
from eval.matrix_loader import MatrixSpec, load_matrix
from extraction.prompt_version import get_prompt_version

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"

MATCHER_GOLD_PASS_RATE_FLOOR = 0.9


def _check_paper(
    paper_id: str,
    fixture_dir: Path,
    current_hash: str,
    current_matcher_fingerprint: str,
) -> tuple[bool, str]:
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
            f"current={current_hash[:8]} - extraction changed — full regen: "
            f"'uv run python -m eval.dump_fixture --paper {paper_id}'."
        )

    fixture_matcher_fingerprint = header.get("matcher_fingerprint", "")
    if fixture_matcher_fingerprint != current_matcher_fingerprint:
        stale_display = fixture_matcher_fingerprint[:8] if fixture_matcher_fingerprint else "(none)"
        return False, (
            f"{paper_id}: fixture matcher_fingerprint={stale_display} does not match "
            f"current={current_matcher_fingerprint[:8]} - matcher changed — re-match only "
            f"(no re-extraction): 'uv run python -m eval.rematch_fixture --paper {paper_id}', "
            f"then 'uv run python -m eval.verify_matcher_gold'."
        )

    pass_rate = header.get("matcher_gold_pass_rate")
    if pass_rate is None or pass_rate < MATCHER_GOLD_PASS_RATE_FLOOR:
        rate_display = "missing" if pass_rate is None else f"{pass_rate:.1%}"
        return False, (
            f"{paper_id}: matcher_gold_pass_rate={rate_display} (floor "
            f"{MATCHER_GOLD_PASS_RATE_FLOOR:.0%}) - matcher gold check failed or never ran: "
            f"'uv run python -m eval.verify_matcher_gold'."
        )

    if not read_matches_from_fixture(fixture_path):
        return False, (
            f"{paper_id}: fixture missing frozen matches. Regenerate via "
            f"'uv run python -m eval.dump_fixture --paper {paper_id}'."
        )

    return True, (
        f"{paper_id}: OK (prompt_hash={current_hash[:8]}, "
        f"matcher_fingerprint={current_matcher_fingerprint[:8]}, "
        f"matcher_gold_pass_rate={pass_rate:.1%})"
    )


def check_freshness(matrix_path: Path, fixture_dir: Path) -> int:
    matrix_spec: MatrixSpec = load_matrix(matrix_path)
    current_hash = get_prompt_version()
    current_matcher_fingerprint = get_matcher_fingerprint()

    all_fresh = True
    for paper in matrix_spec.papers:
        fresh, message = _check_paper(paper.paper_id, fixture_dir, current_hash, current_matcher_fingerprint)
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
    from dotenv import load_dotenv

    load_dotenv()
    main()
