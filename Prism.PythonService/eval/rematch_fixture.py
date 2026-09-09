"""CLI: re-runs ONLY the matcher against a paper's already-extracted claims,
for when the matcher (model routing or prompt) changed but extraction did
not.

Reads the paper's already-extracted, already-grounded claims straight from
Postgres - the same "latest extraction" lookup eval/dump_fixture.py uses -
so this does NO re-extraction and NO re-grounding. Re-runs only the matcher
against matrix_eval.json's golden rows, then rewrites the fixture's
`matches` and `matcher_model`/`matcher_fingerprint` header fields in place.
`prompt_hash`, `model_name`, `extraction_run_id`, and `claims` are left
byte-for-byte untouched.

Deliberately CLEARS matcher_gold_pass_rate/matcher_gold_verified_at rather
than carrying them forward: those fields describe how well the matcher
scored against the hand-labeled gold set, measured under whatever matcher
config was active at the time - which is now the OLD one. Leaving a
pass_rate number in place after swapping the matcher underneath it would
silently misrepresent an unverified matcher as calibrated. Clearing them
makes eval/check_fixture_freshness.py correctly demand a fresh
eval.verify_matcher_gold run before the fixture is trusted again:

  uv run python -m eval.rematch_fixture --paper all
  uv run python -m eval.verify_matcher_gold
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from eval.dump_fixture import _fetch_latest_extraction, get_matcher_fingerprint
from eval.matcher import match
from eval.matrix_loader import MatrixSpec, PaperSpec, load_matrix
from eval.types import ActualClaim

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"


def _paper_matches(paper: PaperSpec, name: str) -> bool:
    if name == "all":
        return True
    needle = name.lower()
    return needle in paper.paper_id.lower() or needle in paper.filename.lower()


async def _rematch_paper(paper: PaperSpec, fixture_dir: Path) -> bool:
    """Returns True if the paper's fixture was re-matched."""
    fixture_path = fixture_dir / f"{paper.paper_id}.json"
    if not fixture_path.exists():
        print(f"SKIPPED ({paper.paper_id}: no existing fixture - use eval.dump_fixture for a first-time freeze)")
        return False

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    header = data.get("header") if isinstance(data, dict) else None
    if header is None:
        print(f"SKIPPED ({paper.paper_id}: legacy fixture with no header - use eval.dump_fixture for a full regen)")
        return False

    result = await _fetch_latest_extraction(paper.filename)
    if result is None:
        print(f"SKIPPED (no DB data for {paper.filename})")
        return False

    _extraction_run_id, claims = result
    actual_claims = [ActualClaim(**claim) for claim in claims]

    try:
        matches, used_matcher_model = await match(paper.paper_id, paper.expected_rows, actual_claims)
    except Exception as exc:
        print(f"SKIPPED (matcher failed for {paper.filename}): {exc}")
        return False

    header["matcher_model"] = used_matcher_model
    header["matcher_fingerprint"] = get_matcher_fingerprint()
    header.pop("matcher_gold_pass_rate", None)
    header.pop("matcher_gold_verified_at", None)

    data["matches"] = [m.model_dump() for m in matches]

    fixture_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(
        f"re-matched {paper.filename} -> {fixture_path} "
        f"({len(matches)} matches, matcher_model={used_matcher_model}). "
        "Run 'uv run python -m eval.verify_matcher_gold' next to re-verify pass_rate."
    )
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Re-run only the matcher against a paper's already-extracted claims (no re-extraction, no re-grounding)"
    )
    parser.add_argument("--paper", default="all", help="paper_id/filename substring, or 'all'")
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    return parser


async def _run(args: argparse.Namespace) -> int:
    matrix_spec: MatrixSpec = load_matrix(args.matrix_path)

    papers = [p for p in matrix_spec.papers if _paper_matches(p, args.paper)]
    if not papers:
        print(f"No papers match --paper {args.paper!r}", file=sys.stderr)
        return 1

    all_rematched = True
    for paper in papers:
        rematched = await _rematch_paper(paper, args.fixture_dir)
        all_rematched = all_rematched and rematched

    return 0 if all_rematched else 1


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()
    main()
