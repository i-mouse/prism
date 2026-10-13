"""Shared gemini-3.6-flash pricing constants and cost formula for eval replay
scripts (eval/replay_audit.py, eval/replay_extract.py).

Pricing per docs/decisions.md:1676 (2026-10-12): $0.75/1M input tokens,
$3.75/1M output tokens (thinking counted as output), through 2026-12-31
(doubles from 2027-01-01). Planning rate 100 INR/USD.
"""
USD_PER_1M_INPUT = 0.75
USD_PER_1M_OUTPUT = 3.75
INR_PER_USD = 100


def cost_usd(prompt_tokens: float, output_tokens: float, thought_tokens: float = 0.0) -> float:
    """Returns USD cost for one call given prompt/output/thought token counts.
    Thought tokens are billed as output per the pricing note above."""
    input_cost = prompt_tokens / 1e6 * USD_PER_1M_INPUT
    output_cost = (output_tokens + thought_tokens) / 1e6 * USD_PER_1M_OUTPUT
    return input_cost + output_cost


def cost_inr(prompt_tokens: float, output_tokens: float, thought_tokens: float = 0.0) -> float:
    return cost_usd(prompt_tokens, output_tokens, thought_tokens) * INR_PER_USD
