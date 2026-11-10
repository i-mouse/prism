"""extraction/scope_combine.py: when a scope check may lower a verdict. Invented
paper text only; no model call."""
import logging

import pytest

from extraction import grounding, scope_combine
from extraction.scope_check import ClaimScope, ScopeStats
from extraction.scope_combine import combine_scope
from extraction.scope_schemas import ScopeCheckItem, ScopeItem

PAPER = (
    "Results. The controller reduces fatigue load on turbine models T1, T2 and T3.\n"
    "Table 2: Model | Low wind | Gusty wind\n"
    "T3 | -11.2 | +1.3\n"
    "Limitations. On T3 the gusty-wind load rose slightly (+1.3 percent).\n"
)
GOOD_QUOTE = "On T3 the gusty-wind load rose slightly (+1.3 percent)."  # in PAPER, > 20 normalised chars
SHORT_QUOTE = "T3 | -11.2 | +1.3"  # in PAPER, but only 17 chars
FOREIGN_QUOTE = "Quantum entanglement dominates the spectral gap of lattice simulations."


def _item(text="holds for each model", kind="count") -> ScopeItem:
    return ScopeItem(text=text, kind=kind)


def _check(status, quote=None, item="x") -> ScopeCheckItem:
    return ScopeCheckItem(item=item, reported=[quote] if quote else [], status=status, contradicting_quote=quote)


def _combine(label, items, checks, stats=None):
    stats = stats or ScopeStats()
    trace = combine_scope(label, ClaimScope(items=items, checks=checks), PAPER, stats, claim_ref="p#0")
    return trace, stats


def test_supported_with_a_guard_passing_contradiction_is_lowered_with_a_full_trace():
    trace, stats = _combine(
        "supported", [_item("each model", "count")], [_check("contradicted", GOOD_QUOTE)],
    )
    assert trace.label == "partially_supported" and trace.auditor_label == "supported"
    assert trace.scope_lowered is True
    assert (trace.scope_item, trace.scope_item_kind, trace.scope_quote) == ("each model", "count", GOOD_QUOTE)
    assert trace.scope_items == [{
        "text": "each model", "kind": "count", "status": "contradicted",
        "contradicting_quote": GOOD_QUOTE, "guard_passed": True,
    }]
    assert (stats.contradicted_items, stats.guard_failed, stats.verdicts_lowered) == (1, 0, 1)
    assert list(trace.to_fields()) == [
        "auditor_label", "label", "scope_lowered", "scope_item", "scope_item_kind", "scope_quote", "scope_items",
    ]


def test_a_quote_that_is_not_in_the_paper_leaves_the_verdict():
    trace, stats = _combine("supported", [_item()], [_check("contradicted", FOREIGN_QUOTE)])
    assert trace.label == "supported" and not trace.scope_lowered
    assert trace.scope_item is None and trace.scope_item_kind is None and trace.scope_quote is None
    assert trace.scope_items[0]["guard_passed"] is False
    assert (stats.contradicted_items, stats.guard_failed, stats.verdicts_lowered) == (1, 1, 0)


def test_a_quote_under_20_normalised_chars_leaves_the_verdict_even_if_it_is_in_the_paper():
    assert SHORT_QUOTE in PAPER and len(grounding.normalize_for_match(SHORT_QUOTE)) < 20
    trace, stats = _combine("supported", [_item()], [_check("contradicted", SHORT_QUOTE)])
    assert trace.label == "supported" and trace.scope_items[0]["guard_passed"] is False
    assert stats.guard_failed == 1 and stats.verdicts_lowered == 0


def test_the_length_floor_is_on_the_normalised_quote():
    padded = "On   T3   the   gusty"  # 21 raw chars, 15 once whitespace is collapsed
    assert len(padded) >= 20 and len(grounding.normalize_for_match(padded)) == 15
    assert scope_combine.MIN_QUOTE_NORM_LEN == 20
    assert scope_combine.quote_passes_guard(padded, PAPER) is False
    assert scope_combine.quote_passes_guard(None, PAPER) is False
    assert scope_combine.quote_passes_guard(GOOD_QUOTE, PAPER) is True


def test_a_null_quote_on_a_contradicted_item_leaves_the_verdict():
    trace, stats = _combine("supported", [_item()], [_check("contradicted", None)])
    assert trace.label == "supported" and trace.scope_items[0]["guard_passed"] is False
    assert stats.guard_failed == 1


@pytest.mark.parametrize("label", ["partially_supported", "not_supported"])
def test_partial_and_not_supported_never_change(label):
    trace, stats = _combine(label, [_item()], [_check("contradicted", GOOD_QUOTE)])
    assert trace.label == label == trace.auditor_label and not trace.scope_lowered
    assert trace.scope_items[0]["guard_passed"] is True  # still traced
    assert stats.verdicts_lowered == 0 and stats.contradicted_items == 1


@pytest.mark.parametrize("status", ["matches", "not_reported"])
def test_matches_and_not_reported_never_lower(status):
    trace, stats = _combine("supported", [_item()], [_check(status, GOOD_QUOTE)])
    assert trace.label == "supported" and not trace.scope_lowered
    assert trace.scope_items[0]["guard_passed"] is None
    assert (stats.contradicted_items, stats.verdicts_lowered) == (0, 0)


def test_the_first_guard_passing_item_in_item_order_is_reported():
    items = [_item("first", "quantifier"), _item("second", "pair"), _item("third", "plural")]
    checks = [
        _check("contradicted", FOREIGN_QUOTE),  # fails the guard
        _check("contradicted", GOOD_QUOTE),     # first to pass
        _check("contradicted", "Table 2: Model | Low wind | Gusty wind"),  # also passes, later
    ]
    trace, stats = _combine("supported", items, checks)
    assert trace.scope_lowered and (trace.scope_item, trace.scope_item_kind) == ("second", "pair")
    assert stats.contradicted_items == 3 and stats.guard_failed == 1 and stats.verdicts_lowered == 1


def test_more_checker_items_than_lister_items_pairs_by_index_and_counts_the_mismatch():
    trace, stats = _combine("supported", [_item("only", "count")], [
        _check("matches"), _check("contradicted", GOOD_QUOTE),
    ])
    assert len(trace.scope_items) == 1 and trace.label == "supported"
    assert stats.item_count_mismatches == 1 and stats.contradicted_items == 0


def test_fewer_checker_items_than_lister_items_pairs_the_shorter_and_counts_the_mismatch():
    trace, stats = _combine(
        "supported", [_item("a", "count"), _item("b", "pair")], [_check("contradicted", GOOD_QUOTE)],
    )
    assert trace.scope_lowered and trace.scope_item == "a"
    assert len(trace.scope_items) == 1 and stats.item_count_mismatches == 1


def test_equal_lengths_are_not_a_mismatch():
    _, stats = _combine("supported", [_item()], [_check("matches")])
    assert stats.item_count_mismatches == 0


@pytest.mark.parametrize("scope", [
    None,
    ClaimScope(),
    ClaimScope(lister_failed=True),
    ClaimScope(items=[ScopeItem(text="t", kind="count")], checker_failed=True),
])
def test_no_checker_result_leaves_the_verdict_with_an_empty_trace(scope):
    stats = ScopeStats()
    trace = combine_scope("supported", scope, PAPER, stats)
    assert trace.label == "supported" and not trace.scope_lowered and trace.scope_items == []
    assert stats == ScopeStats()


def test_every_contradicted_item_is_logged_with_its_kind(caplog):
    items = [_item("a", "named_set"), _item("b", "plural"), _item("c", "count")]
    checks = [_check("contradicted", GOOD_QUOTE), _check("contradicted", FOREIGN_QUOTE), _check("matches")]
    with caplog.at_level(logging.INFO, logger="extraction.scope_combine"):
        _combine("supported", items, checks)
    messages = [r.getMessage() for r in caplog.records if "contradicted item" in r.getMessage()]
    assert len(messages) == 2
    assert "kind=named_set" in messages[0] and "guard_passed=True" in messages[0]
    assert "kind=plural" in messages[1] and "guard_passed=False" in messages[1]


def test_combine_never_raises_and_leaves_the_verdict_on_an_internal_error(monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("matcher exploded")

    monkeypatch.setattr(grounding, "_passes_rapidfuzz", broken)
    with caplog.at_level(logging.ERROR, logger="extraction.scope_combine"):
        trace, _ = _combine("supported", [_item()], [_check("contradicted", GOOD_QUOTE)])
    assert trace.label == "supported" and not trace.scope_lowered and trace.scope_items == []
    assert any("SCOPE COMBINE FAILED" in r.getMessage() for r in caplog.records)
