"""Shared gemini-3.6-flash pricing constants and cost formula for eval replay
scripts (eval/replay_audit.py, eval/replay_extract.py).

Pricing per docs/decisions.md:1676 (2026-10-12): $0.75/1M input tokens,
$3.75/1M output tokens (thinking counted as output), through 2026-12-31
(doubles from 2027-01-01). Planning rate 100 INR/USD. Cached input is billed
at $0.075/1M; explicit-cache storage at $0.50/1M tokens per hour.
"""
from dataclasses import dataclass

USD_PER_1M_INPUT = 0.75
USD_PER_1M_OUTPUT = 3.75
USD_PER_1M_CACHED_INPUT = 0.075
USD_PER_1M_STORAGE_PER_HOUR = 0.50
INR_PER_USD = 100


@dataclass(frozen=True)
class Rates:
    """USD per 1M tokens. cached_usd falls back to in_usd when not given."""
    in_usd: float
    out_usd: float
    cached_usd: float | None = None

    @property
    def cached_rate(self) -> float:
        return self.in_usd if self.cached_usd is None else self.cached_usd


# Only models with a verified price belong here - an absent model is reported
# as "unpriced" rather than guessed. Rates copied from the official pricing
# page; record the date.
RATES_BY_MODEL: dict[str, Rates] = {
    "gemini-3.6-flash": Rates(
        in_usd=USD_PER_1M_INPUT, out_usd=USD_PER_1M_OUTPUT, cached_usd=USD_PER_1M_CACHED_INPUT,
    ),
}


def normalise_model_name(model: str) -> str:
    """Lowercases and keeps the part after the last "/", so
    "groq/openai/gpt-oss-20b" and "gpt-oss-20b" share one key."""
    return model.lower().rsplit("/", 1)[-1]


def cost_usd_for_model(
    model: str,
    prompt: float,
    output: float,
    thought: float = 0.0,
    cached: float = 0.0,
    tool_use: float = 0.0,
) -> float | None:
    """Returns USD cost for one model's token counts, or None when the model
    has no entry in RATES_BY_MODEL.

    prompt includes cached tokens (both SDKs report it that way), so cached
    is subtracted from the full-rate input and billed once at the cached rate.
    thought is billed as output; pass 0 when the provider already counts
    reasoning inside output (LiteLLM's completion_tokens).
    """
    rates = RATES_BY_MODEL.get(normalise_model_name(model))
    if rates is None:
        return None
    return _cost(rates.in_usd, rates.out_usd, rates.cached_rate, prompt, output, thought, cached, tool_use)


def _cost(
    in_rate: float, out_rate: float, cached_rate: float,
    prompt: float, output: float, thought: float, cached: float, tool_use: float,
) -> float:
    uncached_in = prompt - cached
    input_cost = (uncached_in + tool_use) / 1e6 * in_rate + cached / 1e6 * cached_rate
    output_cost = (output + thought) / 1e6 * out_rate
    return input_cost + output_cost


def cost_usd(
    prompt_tokens: float,
    output_tokens: float,
    thought_tokens: float = 0.0,
    cached_tokens: float = 0.0,
    tool_use_tokens: float = 0.0,
) -> float:
    """Returns USD cost for one call at gemini-3.6-flash rates given
    prompt/output/thought token counts. prompt_tokens includes cached_tokens.
    Thought tokens are billed as output per the pricing note above."""
    return _cost(
        USD_PER_1M_INPUT, USD_PER_1M_OUTPUT, USD_PER_1M_CACHED_INPUT,
        prompt_tokens, output_tokens, thought_tokens, cached_tokens, tool_use_tokens,
    )


def cost_inr(
    prompt_tokens: float,
    output_tokens: float,
    thought_tokens: float = 0.0,
    cached_tokens: float = 0.0,
    tool_use_tokens: float = 0.0,
) -> float:
    return cost_usd(prompt_tokens, output_tokens, thought_tokens, cached_tokens, tool_use_tokens) * INR_PER_USD


def storage_cost_usd(tokens: float, hours: float) -> float:
    """USD cost of keeping `tokens` of explicit cache alive for `hours`."""
    return tokens / 1e6 * hours * USD_PER_1M_STORAGE_PER_HOUR
