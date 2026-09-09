"""CLI: verifies the LLM-as-judge matcher against the hand-labeled gold set
and freezes the result into every paper fixture's header.

Matcher quality is not paper-specific - one gold-set run produces one
pass_rate and one matcher_fingerprint, written identically into every paper
fixture (docs/evals/fixtures/*.json). Does NOT touch claims or matches;
see eval/rematch_fixture.py for re-running the matcher against a paper's
actual extracted claims.

Real Gemini calls - not run in CI (see docs/decisions.md, "Revert
live-matcher CI back to frozen-fixture design"). Run manually after a
matcher model swap or matcher prompt change:
  uv run python -m eval.verify_matcher_gold
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from eval.dump_fixture import get_matcher_fingerprint
from eval.matcher import match
from eval.types import ActualClaim, ExpectedRow

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_GOLD_SET_PATH = REPO_ROOT / "docs" / "evals" / "matcher_gold.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"

PASS_RATE_FLOOR = 0.9


def _load_gold_set(gold_set_path: Path) -> dict:
    return json.loads(gold_set_path.read_text(encoding="utf-8"))


async def _run_pair(pair: dict) -> bool:
    """Runs one gold pair through match() and returns whether the matcher
    agreed with the gold verdict. Mirrors eval/tests/test_matcher.py's
    _run_pair - same fixed not_supported/grounding_negative shape, since
    the gold set only exercises the matcher's semantic-equivalence judgment,
    not label handling."""
    expected_row = ExpectedRow(
        id=pair["id"],
        expected_label="not_supported",
        grounding_negative=True,
        claim_summary=pair["expected_claim_summary"],
    )
    actual_claim = ActualClaim(
        index=0,
        label="not_supported",
        claim_summary=pair["actual_claim_summary"],
    )

    matches, _used_model = await match(
        paper_id="matcher_gold_verify",
        expected_rows=[expected_row],
        actual_claims=[actual_claim],
    )
    matched = matches[0].actual_index == 0
    return matched == pair["correct_match"]


async def _run_gold_set(pairs: list[dict]) -> tuple[int, list[str]]:
    """Returns (correct_count, failed_ids)."""
    results = [await _run_pair(pair) for pair in pairs]
    failures = [pair["id"] for pair, ok in zip(pairs, results) if not ok]
    return len(pairs) - len(failures), failures


def _write_matcher_verification(
    fixture_dir: Path,
    matcher_fingerprint: str,
    pass_rate: float,
    verified_at: datetime,
) -> list[Path]:
    """Writes matcher_fingerprint/matcher_gold_pass_rate/matcher_gold_verified_at
    into every fixture's header in place. Does not touch claims or matches."""
    written: list[Path] = []
    for fixture_path in sorted(fixture_dir.glob("*.json")):
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        header = data.get("header") if isinstance(data, dict) else None
        if header is None:
            continue  # legacy bare-array fixture predates headers entirely

        header["matcher_fingerprint"] = matcher_fingerprint
        header["matcher_gold_pass_rate"] = pass_rate
        header["matcher_gold_verified_at"] = verified_at.isoformat()

        fixture_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        written.append(fixture_path)
    return written


async def _run(fixture_dir: Path, gold_set_path: Path) -> int:
    gold = _load_gold_set(gold_set_path)
    pairs = gold["pairs"]

    correct, failures = await _run_gold_set(pairs)
    pass_rate = correct / len(pairs)

    print(f"Matcher gold-set: {correct}/{len(pairs)} ({pass_rate:.1%})")
    if failures:
        print(f"Failed pairs: {failures}")

    if pass_rate < PASS_RATE_FLOOR:
        print(
            f"FAILED - pass_rate {pass_rate:.1%} is below the {PASS_RATE_FLOOR:.0%} floor. "
            "Fixture headers NOT written. Fix the matcher (model or prompt) before re-running.",
            file=sys.stderr,
        )
        return 1

    matcher_fingerprint = get_matcher_fingerprint()
    verified_at = datetime.now(timezone.utc)
    written = _write_matcher_verification(fixture_dir, matcher_fingerprint, pass_rate, verified_at)

    for path in written:
        print(f"wrote matcher_fingerprint={matcher_fingerprint} pass_rate={pass_rate:.1%} -> {path}")

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the matcher against the hand-labeled gold set and freeze the result into every fixture header"
    )
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--gold-set-path", type=Path, default=DEFAULT_GOLD_SET_PATH)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_run(args.fixture_dir, args.gold_set_path)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()
    main()
