"""Unit tests for eval/pricing.py: per-model rates, cached/tool_use/thought
billing, and the storage cost. Pure arithmetic - no network."""
import pytest

from eval import pricing


def test_known_model_has_a_price():
    # 1M prompt at 0.75 + 1M output at 3.75
    assert pricing.cost_usd_for_model("gemini-3.6-flash", 1e6, 1e6) == pytest.approx(4.50)


def test_unknown_model_returns_none():
    assert pricing.cost_usd_for_model("groq/openai/gpt-oss-20b", 1e6, 1e6) is None
    assert pricing.cost_usd_for_model("gemini/gemini-3.1-flash-lite", 1e6, 1e6) is None


def test_model_name_is_normalised_before_lookup():
    expected = pricing.cost_usd_for_model("gemini-3.6-flash", 1000, 500)
    assert pricing.cost_usd_for_model("GEMINI-3.6-FLASH", 1000, 500) == expected
    assert pricing.cost_usd_for_model("models/gemini-3.6-flash", 1000, 500) == expected
    assert pricing.normalise_model_name("groq/openai/GPT-OSS-20B") == "gpt-oss-20b"
    assert pricing.normalise_model_name("gpt-oss-20b") == "gpt-oss-20b"


def test_cached_tokens_are_not_billed_twice():
    # prompt=1M of which 400k cached: 600k at 0.75 + 400k at 0.075, nothing more.
    cost = pricing.cost_usd_for_model("gemini-3.6-flash", 1e6, 0, cached=4e5)
    assert cost == pytest.approx(0.6 * 0.75 + 0.4 * 0.075)
    assert cost < 1.0 * 0.75  # cheaper than billing all of prompt at the full rate
    assert cost != pytest.approx(1.0 * 0.75 + 0.4 * 0.075)  # not full prompt plus cached again


def test_thinking_tokens_are_billed_once_at_output_rate():
    with_thought = pricing.cost_usd_for_model("gemini-3.6-flash", 0, 1e6, thought=1e6)
    assert with_thought == pytest.approx(2.0 * 3.75)  # 1M candidates + 1M thoughts, each once
    thought_only = pricing.cost_usd_for_model("gemini-3.6-flash", 0, 0, thought=1e6)
    assert thought_only == pytest.approx(3.75)


def test_grounding_style_call_passes_thought_zero():
    """LiteLLM's completion_tokens already contains reasoning, so a caller
    prices output_tokens alone (thought=0); adding reasoning would double-bill."""
    output_tokens = 1000  # includes e.g. 700 reasoning tokens
    right = pricing.cost_usd_for_model("gemini-3.6-flash", 0, output_tokens, thought=0.0)
    wrong = pricing.cost_usd_for_model("gemini-3.6-flash", 0, output_tokens, thought=700)
    assert right == pytest.approx(1000 / 1e6 * 3.75)
    assert wrong > right


def test_tool_use_tokens_are_billed_as_input_on_top_of_prompt():
    cost = pricing.cost_usd_for_model("gemini-3.6-flash", 0, 0, tool_use=1e6)
    assert cost == pytest.approx(0.75)


def test_rates_cached_defaults_to_input_rate():
    assert pricing.Rates(in_usd=2.0, out_usd=8.0).cached_rate == 2.0
    assert pricing.Rates(in_usd=2.0, out_usd=8.0, cached_usd=0.2).cached_rate == 0.2


def test_only_gemini_3_6_flash_is_in_the_rate_table():
    assert set(pricing.RATES_BY_MODEL) == {"gemini-3.6-flash"}
    assert pricing.RATES_BY_MODEL["gemini-3.6-flash"] == pricing.Rates(0.75, 3.75, 0.075)


def test_storage_cost_is_tokens_times_hours_times_rate():
    assert pricing.storage_cost_usd(1e6, 1) == pytest.approx(0.50)
    assert pricing.storage_cost_usd(2e6, 3) == pytest.approx(3.00)
    assert pricing.storage_cost_usd(0, 10) == 0.0


def test_legacy_cost_usd_and_inr_unchanged_for_three_arg_callers():
    assert pricing.cost_usd(1e6, 1e6, 1e6) == pytest.approx(0.75 + 2 * 3.75)
    assert pricing.cost_inr(1e6, 0, 0) == pytest.approx(0.75 * pricing.INR_PER_USD)


def test_cost_usd_with_cached_matches_cost_usd_for_model():
    assert pricing.cost_usd(1e6, 1e5, 2e5, cached_tokens=4e5, tool_use_tokens=1e5) == pytest.approx(
        pricing.cost_usd_for_model("gemini-3.6-flash", 1e6, 1e5, thought=2e5, cached=4e5, tool_use=1e5)
    )
