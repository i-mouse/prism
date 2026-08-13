"""Integration test for the LLM-as-judge matcher against a hand-labeled gold set.

Makes real Gemini calls - skipped by default (see pyproject.toml's
`addopts = "-m 'not integration'"`). Run explicitly with:
  uv run pytest eval/tests/test_matcher.py -v -m integration
"""
import asyncio
import json
from pathlib import Path

import pytest

from eval.matcher import match
from eval.types import ActualClaim, ExpectedRow

pytestmark = pytest.mark.integration

GOLD_SET_PATH = Path(__file__).parent.parent.parent.parent / "docs" / "evals" / "matcher_gold.json"


def _load_gold_set() -> dict:
    return json.loads(GOLD_SET_PATH.read_text(encoding="utf-8"))


def _pass_threshold(gold: dict) -> int:
    # "13/15 (~87%). LLM noise makes 100% unrealistic; this threshold catches meaningful regressions."
    fraction = gold["metadata"]["pass_threshold"].split(" ", 1)[0]
    numerator, _ = fraction.split("/")
    return int(numerator)


async def _run_pair(pair: dict) -> bool:
    """Runs one gold pair through match() and returns whether the matcher agreed with the gold verdict."""
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

    matches = await match(
        paper_id="matcher_gold_test",
        expected_rows=[expected_row],
        actual_claims=[actual_claim],
    )

    assert len(matches) == 1
    matched = matches[0].actual_index == 0
    return matched == pair["correct_match"]


def test_matcher_gold_set_accuracy():
    gold = _load_gold_set()
    pairs = gold["pairs"]
    threshold = _pass_threshold(gold)

    results = asyncio.run(_gather_results(pairs))

    failures = [pair["id"] for pair, ok in zip(pairs, results) if not ok]
    correct = len(pairs) - len(failures)

    if failures:
        print(f"\nMatcher gold-set failures ({len(failures)}/{len(pairs)}): {failures}")
        for pair in pairs:
            if pair["id"] in failures:
                print(
                    f"  {pair['id']} (expected correct_match={pair['correct_match']}): "
                    f"expected={pair['expected_claim_summary']!r} "
                    f"actual={pair['actual_claim_summary']!r}"
                )

    assert correct >= threshold, (
        f"Matcher gold-set accuracy {correct}/{len(pairs)} below pass threshold {threshold}/{len(pairs)}. "
        f"Failed: {failures}"
    )


async def _gather_results(pairs: list[dict]) -> list[bool]:
    return [await _run_pair(pair) for pair in pairs]
