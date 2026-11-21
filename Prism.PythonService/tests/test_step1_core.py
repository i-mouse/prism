"""Unit tests for eval/step1/core.py on small made-up data: flag counts, histograms, claim classes, spread, the T rule
(including the cap), call-record totals, cache overhead and the 2027 price x2. No test reads a fixture folder."""
import pytest

from eval import pricing
from eval.step1 import core


def test_flag_count_counts_partially_and_not_supported_only():
    labels = ["supported", "partially_supported", "not_supported", "supported", "not_supported"]
    assert core.flag_count(labels) == 3
    assert core.flag_count([]) == 0
    assert core.is_flagged("not_supported") and not core.is_flagged("supported")


def test_histogram_buckets_counts_and_rejects_out_of_range():
    assert core.histogram([0, 0, 1, 3, 3, 3], 3) == [2, 1, 0, 3]
    with pytest.raises(ValueError):
        core.histogram([4], 3)


def test_flagged_at_least_table():
    bad = [0, 1, 3, 3]
    good = [0, 0, 1, 2]
    assert core.flagged_at_least_table(bad, good, 3) == [(1, 3, 2), (2, 2, 1), (3, 2, 0)]


def test_classify_claims_lists_a_shared_claim_once_under_the_earlier_class():
    shared = ("dev", "paper-a", 1)
    items = [
        ("P5-S1", "s_row", shared),
        ("P1-S1", "s_row", ("dev", "paper-b", 2)),
        ("P5-R2", "parked", shared),
        ("G-1", "golden_negative", ("golden", "paper-g", 5)),
        ("P2-R1", "target", ("dev", "paper-c", 3)),
    ]
    entries = core.classify_claims(items)
    assert [e.claim_class for e in entries] == ["R target", "R parked", "S", "golden negative"]
    parked = entries[1]
    assert parked.row_ids == ("P5-S1", "P5-R2")
    assert "P5-S1" in parked.note and "P5-R2" in parked.note
    assert len(entries) == 4


def test_classify_claims_rejects_an_unknown_role():
    with pytest.raises(ValueError):
        core.classify_claims([("X", "mystery", ("dev", "p", 1))])


def test_spread_is_highest_minus_lowest():
    assert core.spread([5, 8, 6]) == 3
    assert core.spread([4]) == 0
    with pytest.raises(ValueError):
        core.spread([])


def test_share_changed_counts_claims_with_a_different_label_in_some_repeat():
    vectors = [["supported"] * 3, ["supported", "not_supported", "supported"], ["not_supported"] * 3, ["a", "b", "c"]]
    assert core.share_changed(vectors) == (2, 4)
    assert core.share_changed([]) == (0, 0)


def test_t_rule_below_the_cap_is_the_largest_spread():
    r = core.t_rule({"g1 / refusal": 2, "g1 / false rejections": 1, "g2 / golden": 2})
    assert (r.t, r.measured, r.capped) == (2, 2, False)
    assert r.set_by == ("g1 / refusal", "g2 / golden")        # every count that ties for the largest


def test_t_rule_at_the_cap_is_not_capped():
    r = core.t_rule({"g / x": 3})
    assert (r.t, r.measured, r.capped) == (3, 3, False)


def test_t_rule_above_the_cap_is_three_and_keeps_the_measured_value():
    r = core.t_rule({"g / x": 5, "g / y": 2})
    assert (r.t, r.measured, r.capped) == (3, 5, True)
    assert r.set_by == ("g / x",)


def test_t_rule_with_no_eligible_group_has_no_t():
    r = core.t_rule({})
    assert r.t is None and r.measured is None and not r.capped and r.set_by == ()


def test_rates_2027_doubles_gemini_3_6_flash_and_leaves_other_models_alone():
    r = core.rates_2027("gemini-3.6-flash")
    assert (r.in_usd, r.out_usd, r.cached_rate) == (1.50, 7.50, 0.15)
    assert core.rates_2027("gemini/gemini-3.8-flash").in_usd == 1.50           # pricing.py: doubles too (comment)
    assert core.rates_2027("gemini-3.1-flash-lite") == pricing.rates_for_model("gemini-3.1-flash-lite")
    with pytest.raises(pricing.UnpricedModelError):
        core.rates_2027("no-such-model")


def test_storage_rate_2027():
    assert core.storage_rate_2027("gemini-3.6-flash") == 1.00
    assert pricing.storage_rate_for_model("gemini-3.6-flash") == 0.50


def test_call_cost_matches_pricing_and_doubles_in_2027():
    usd = core.call_cost_usd(pricing.rates_for_model("gemini-3.6-flash"), 1_000_000, 400_000, 100_000, 100_000)
    assert usd == pytest.approx(1.23)
    assert usd == pytest.approx(pricing.strict_cost_usd_for_model("gemini-3.6-flash", 1_000_000, 100_000, 100_000, 400_000))
    assert core.call_cost_usd(core.rates_2027("gemini-3.6-flash"), 1_000_000, 400_000, 100_000, 100_000) == pytest.approx(2 * usd)


def _rec(paper, index, is_audit, prompt, cached, output, thought, model="gemini-3.6-flash"):
    return {
        "paper_id": paper, "claim_index": index, "is_audit": is_audit, "model_used": model, "prompt_tokens": prompt,
        "cached_tokens": cached, "output_tokens": output, "thought_tokens": thought, "tool_use_tokens": 0,
    }


def test_summarize_records_splits_audit_from_structurer_and_counts_claims_per_folder():
    folder1 = [
        _rec("a", 1, True, 1000, 400, 100, 50), _rec("a", 1, False, 200, 0, 40, 10),
        _rec("a", 2, True, 1200, 600, 80, 20), _rec("a", 2, False, 220, 0, 30, 0),
    ]
    folder2 = [_rec("a", 1, True, 1000, 0, 100, 50), _rec("a", 1, False, 200, 0, 40, 10)]
    audit = core.summarize_records([folder1, folder2], want_audit=True)
    assert (audit.calls, audit.claims) == (3, 3)
    assert (audit.prompt, audit.cached, audit.output, audit.thought) == (3200, 1000, 280, 120)
    assert audit.per_claim("prompt") == pytest.approx(3200 / 3)
    structure = core.summarize_records([folder1, folder2], want_audit=False)
    assert (structure.calls, structure.claims, structure.prompt) == (3, 3, 620)
    assert audit.usd_2027 == pytest.approx(2 * audit.usd_2026)
    expected = core.call_cost_usd(pricing.rates_for_model("gemini-3.6-flash"), 1000, 400, 100, 50)
    one = core.summarize_records([[_rec("a", 1, True, 1000, 400, 100, 50)]], want_audit=True)
    assert one.usd_2026 == pytest.approx(expected)


def test_a_fallback_served_call_is_priced_at_the_serving_model():
    flash = core.summarize_records([[_rec("a", 1, True, 1000, 0, 100, 0)]], want_audit=True)
    lite = core.summarize_records([[_rec("a", 1, True, 1000, 0, 100, 0, model="gemini-3.1-flash-lite")]], want_audit=True)
    assert lite.usd_2026 < flash.usd_2026
    assert lite.usd_2027 == pytest.approx(lite.usd_2026)       # flash-lite is not doubled


def test_record_usd_needs_a_model():
    with pytest.raises(TypeError):
        core.record_usd({"prompt_tokens": 10}, 2026)


def test_cache_overhead_creation_billed_or_not_and_storage_by_claims():
    rates = pricing.rates_for_model("gemini-3.6-flash")
    creation, storage = core.cache_overhead_usd(100_000, 10, 51, rates, 0.50, creation_billed=True)
    assert creation == pytest.approx(0.075)
    assert storage == pytest.approx(0.1 * (10 * 51 / 3600) * 0.5)
    creation0, storage0 = core.cache_overhead_usd(100_000, 10, 51, rates, 0.50, creation_billed=False)
    assert creation0 == 0.0 and storage0 == pytest.approx(storage)
    _, storage_2027 = core.cache_overhead_usd(100_000, 10, 51, rates, core.storage_rate_2027("gemini-3.6-flash"), True)
    assert storage_2027 == pytest.approx(2 * storage)
