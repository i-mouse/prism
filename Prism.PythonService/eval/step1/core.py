"""Pure helpers for the Step 1 free checks: flag counts, histograms, spread, the T rule, claim classes and the 2027
price scaling. No I/O and no heavy imports, so the unit tests need no fixture folder.
"""
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from eval import pricing

# --- flags ---------------------------------------------------------------------------------------------
FLAG_LABELS = ("partially_supported", "not_supported")   # decisions.md 1a: flagged = partially or not supported


def is_flagged(label: str) -> bool:
    return label in FLAG_LABELS


def flag_count(labels: Iterable[str]) -> int:
    """How many of the given labels are flagged."""
    return sum(1 for label in labels if is_flagged(label))


def histogram(counts: Iterable[int], max_count: int) -> list[int]:
    """Index i = how many items have count i, for i in 0..max_count. A count outside the range raises."""
    out = [0] * (max_count + 1)
    for c in counts:
        if not 0 <= c <= max_count:
            raise ValueError(f"count {c} is outside 0..{max_count}")
        out[c] += 1
    return out


def flagged_at_least(counts: Sequence[int], k: int) -> int:
    """How many items were flagged in at least k audits."""
    return sum(1 for c in counts if c >= k)


def flagged_at_least_table(bad: Sequence[int], good: Sequence[int], max_k: int) -> list[tuple[int, int, int]]:
    """[(k, bad claims flagged in >= k audits, good claims flagged in >= k audits)] for k in 1..max_k."""
    return [(k, flagged_at_least(bad, k), flagged_at_least(good, k)) for k in range(1, max_k + 1)]


# --- claim classes (1a) --------------------------------------------------------------------------------
CLASS_ORDER = (
    "R target", "R parked", "R real hit", "P1-R3", "S", "golden negative", "golden positive",
)
BAD_CLASSES = ("R target", "R parked", "R real hit", "P1-R3", "golden negative")    # refusal-family claims
GOOD_CLASSES = ("S", "golden positive")                                              # supported claims
ROLE_CLASS = {
    "target": "R target", "parked": "R parked", "catch": "R real hit", "other": "P1-R3", "s_row": "S",
    "golden_negative": "golden negative", "golden_positive": "golden positive",
}


@dataclass(frozen=True)
class ClaimEntry:
    claim_key: tuple          # (set name, paper_id, claim index)
    claim_class: str
    row_ids: tuple[str, ...]
    note: str


def classify_claims(items: Iterable[tuple[str, str, tuple]]) -> list[ClaimEntry]:
    """items = (row_id, role, claim_key). One entry per distinct claim_key, in CLASS_ORDER then first-seen
    order. A claim reached by several rows takes the class that comes first in CLASS_ORDER (so the dev claim shared
    by P5-R2 and P5-S1 is listed once, under "R parked") and a note naming every row."""
    by_key: dict[tuple, list[tuple[str, str]]] = {}
    for row_id, role, claim_key in items:
        if role not in ROLE_CLASS:
            raise ValueError(f"unknown role {role!r} for row {row_id}")
        by_key.setdefault(claim_key, []).append((row_id, ROLE_CLASS[role]))
    entries = []
    for claim_key, rows in by_key.items():
        claim_class = min((cls for _, cls in rows), key=CLASS_ORDER.index)
        ids = tuple(dict.fromkeys(rid for rid, _ in rows))
        note = f"shared claim: {' = '.join(ids)}" if len(ids) > 1 else ""
        entries.append(ClaimEntry(claim_key, claim_class, ids, note))
    order = {name: i for i, name in enumerate(CLASS_ORDER)}
    return sorted(entries, key=lambda e: order[e.claim_class])   # sorted() is stable: first-seen order inside a class


# --- noise (1b) ----------------------------------------------------------------------------------------
T_CAP = 3


def spread(counts: Sequence[int]) -> int:
    """Highest minus lowest count across the repeats of one group."""
    if not counts:
        raise ValueError("spread of no repeats")
    return max(counts) - min(counts)


def share_changed(label_vectors: Iterable[Sequence[str]]) -> tuple[int, int]:
    """(claims whose label is not the same in every repeat, claims)."""
    vectors = list(label_vectors)
    return sum(1 for v in vectors if len(set(v)) > 1), len(vectors)


@dataclass(frozen=True)
class TResult:
    t: int | None                 # None when there is no non-void product group
    measured: int | None
    capped: bool
    set_by: tuple[str, ...]       # every "group / count" that has the largest spread


def t_rule(spreads: Mapping[str, int]) -> TResult:
    """decisions.md 1b: T = the largest spread over the non-void product-auditor groups and the four counts. If the
    largest spread is above T_CAP (3), T = 3 and the measured value is kept beside it. `spreads` holds only the
    groups that may set T, keyed by "group / count"."""
    if not spreads:
        return TResult(None, None, False, ())
    measured = max(spreads.values())
    set_by = tuple(key for key, value in spreads.items() if value == measured)
    return TResult(min(measured, T_CAP), measured, measured > T_CAP, set_by)


# --- prices (1d) ---------------------------------------------------------------------------------------
# eval/pricing.py says gemini-3.6-flash doubles on 2027-01-01 and (comment only, third-party sources) so does
# gemini-3.8-flash. Every other model is unchanged because pricing.py says nothing else.
DOUBLING_MODELS = ("gemini-3.6-flash", "gemini-3.8-flash")
PRICE_FACTOR_2027 = 2.0


def _doubles(model: str) -> bool:
    return pricing.normalise_model_name(model) in DOUBLING_MODELS


def rates_2027(model: str) -> pricing.Rates:
    """The model's 2027 list rates: input, output and cached read x2 for the doubling models, else unchanged."""
    rates = pricing.rates_for_model(model)
    if not _doubles(model):
        return rates
    return pricing.Rates(
        in_usd=rates.in_usd * PRICE_FACTOR_2027, out_usd=rates.out_usd * PRICE_FACTOR_2027,
        cached_usd=rates.cached_rate * PRICE_FACTOR_2027,
    )


def storage_rate_2027(model: str) -> float:
    """USD per 1M tokens per hour of explicit-cache storage in 2027."""
    rate = pricing.storage_rate_for_model(model)
    return rate * PRICE_FACTOR_2027 if _doubles(model) else rate


def call_cost_usd(
    rates: pricing.Rates, prompt: float, cached: float, output: float, thought: float = 0.0, tool_use: float = 0.0,
) -> float:
    """Same formula as pricing._cost: prompt includes cached; tool-use is billed as input; thought as output."""
    uncached = prompt - cached
    return (
        (uncached + tool_use) / 1e6 * rates.in_usd + cached / 1e6 * rates.cached_rate
        + (output + thought) / 1e6 * rates.out_usd
    )


def usd_to_inr(usd: float) -> float:
    return usd * pricing.INR_PER_USD


@dataclass(frozen=True)
class CallStats:
    """Totals over the calls of one stage, each call priced at the model that served it, at the run-date list
    price (2026) and at the 2027 list price."""
    calls: int
    claims: int               # distinct (paper, claim) keys, summed over folders
    prompt: float             # includes cached
    cached: float
    output: float
    thought: float
    tool_use: float
    usd_2026: float
    usd_2027: float

    def per_claim(self, field: str) -> float:
        return getattr(self, field) / self.claims if self.claims else 0.0


def record_usd(record: Mapping, year: int) -> float:
    """USD for one saved call record at the 2026 or 2027 list price of the model that served it."""
    model = record.get("model_used")
    if not isinstance(model, str):
        raise TypeError("a call record has no model_used")
    rates = pricing.rates_for_model(model) if year == 2026 else rates_2027(model)
    return call_cost_usd(
        rates, record.get("prompt_tokens") or 0, record.get("cached_tokens") or 0, record.get("output_tokens") or 0,
        record.get("thought_tokens") or 0, record.get("tool_use_tokens") or 0,
    )


def summarize_records(records_per_folder: Sequence[Sequence[Mapping]], want_audit: bool) -> CallStats:
    """Totals over the audit calls (want_audit True) or the structurer calls (False) of several replay folders.
    A record counts as audit when its is_audit flag is true."""
    calls = claims = 0
    prompt = cached = output = thought = tool_use = usd26 = usd27 = 0.0
    for records in records_per_folder:
        keys = set()
        for r in records:
            if bool(r.get("is_audit")) != want_audit:
                continue
            calls += 1
            keys.add((r.get("paper_id"), r.get("claim_index")))
            prompt += r.get("prompt_tokens") or 0
            cached += r.get("cached_tokens") or 0
            output += r.get("output_tokens") or 0
            thought += r.get("thought_tokens") or 0
            tool_use += r.get("tool_use_tokens") or 0
            usd26 += record_usd(r, 2026)
            usd27 += record_usd(r, 2027)
        claims += len(keys)
    return CallStats(calls, claims, prompt, cached, output, thought, tool_use, usd26, usd27)


def cache_overhead_usd(
    cache_tokens: float, claims: float, seconds_per_claim: float, rates: pricing.Rates, storage_usd_per_1m_hour: float,
    creation_billed: bool,
) -> tuple[float, float]:
    """(creation USD, storage USD) of one paper's explicit cache that serves `claims` audits. Creation is billed at
    the normal input rate only when creation_billed; storage is billed per token-hour over claims x seconds_per_claim."""
    creation = cache_tokens / 1e6 * rates.in_usd if creation_billed else 0.0
    storage = cache_tokens / 1e6 * (claims * seconds_per_claim / 3600) * storage_usd_per_1m_hour
    return creation, storage
