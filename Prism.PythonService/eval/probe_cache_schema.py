"""One-call paid probe: does Gemini accept cached_content + response_schema +
thinking_level=LOW in a single generateContent request?

The step-4 scope checker needs all three in one request. The cached auditor
call never sends response_schema (extraction/engine.py::_generate_cached_audit)
and thinking_level=low has never been sent with a cache. See docs/decisions.md,
"Cache + schema + low-thinking probe - 2026-10-27".

Creates ONE explicit cache for ONE dev paper (arxiv-2610.10590v1, the smallest
cached paper in A0: 13,125 tokens) with TTL 300 s, sends exactly ONE request
and deletes the cache in a finally block (paper_context_cache does it). No
retries, no fallback model, no second call of any kind: the request goes
straight to client.aio.models.generate_content, never through
engine._generate_with_fallback.

The request carries cached_content, response_mime_type, response_schema
(ProbeOut) and thinking_config LOW - no system_instruction, tools or
tool_config.

PASS = no API error AND response.parsed is a ProbeOut AND
cached_content_token_count > 0. A FAIL names its reason: CACHE_NOT_CREATED,
API_ERROR, PARSE_FAILED or NO_CACHED_TOKENS.

--estimate prints the expected INR from token counts and exits (no network).
A real run refuses to send when that estimate is above MAX_INR (5).

Usage (from Prism.PythonService):
  & ".\\.venv\\Scripts\\python.exe" -m eval.probe_cache_schema --estimate
  & ".\\.venv\\Scripts\\python.exe" -m eval.probe_cache_schema
"""
import argparse
import asyncio
import sys
from dataclasses import dataclass, field

from google.genai import errors, types
from pydantic import BaseModel

from eval.pricing import INR_PER_USD, cache_creation_cost_usd, cost_usd_for_model, storage_cost_usd
from eval.replay_audit import PaperTextError, _load_paper_text
from extraction import engine
from extraction.context_cache import CACHEABLE_MODEL, ContextCacheStats, cached_audit_contents, paper_context_cache

PAPER_ID = "arxiv-2610.10590v1"
MODEL = CACHEABLE_MODEL
N_CLAIMS = 1  # ttl_for_claims(1) is the 300 s floor
TTL_S = 300
MAX_INR = 5.0

PROBE_PROMPT = (
    "List up to two sentences from the paper above that state a numeric result. Copy them verbatim."
)

# --estimate inputs. The cached size is measured (A0 summary, smallest cached
# paper); the other two are ASSUMPTIONS, deliberately generous.
MEASURED_CACHED_TOKENS = 13_125
ASSUMED_UNCACHED_TOKENS = 100
ASSUMED_OUTPUT_PLUS_THOUGHT_TOKENS = 3_000

FAIL_CACHE_NOT_CREATED = "CACHE_NOT_CREATED"
FAIL_API_ERROR = "API_ERROR"
FAIL_PARSE_FAILED = "PARSE_FAILED"
FAIL_NO_CACHED_TOKENS = "NO_CACHED_TOKENS"


class ProbeOut(BaseModel):
    answer: str
    quotes: list[str]


@dataclass
class ProbeResult:
    ok: bool = False
    fail_reason: str | None = None
    error: str | None = None
    parsed_is_probe_out: bool = False
    finish_reason: str | None = None
    usage: dict | None = None
    cache_tokens: int | None = None
    lifetime_s: float | None = None
    call_inr: float | None = None
    storage_inr: float | None = None
    creation_inr: float | None = None
    requests_sent: int = 0
    cache_errors: list[str] = field(default_factory=list)

    @property
    def total_inr(self) -> float:
        return (self.call_inr or 0.0) + (self.storage_inr or 0.0) + (self.creation_inr or 0.0)


def build_probe_config(cache_name: str) -> types.GenerateContentConfig:
    """cached_content + response_mime_type + response_schema + thinking LOW and
    nothing else: no system_instruction, tools or tool_config."""
    return types.GenerateContentConfig(
        cached_content=cache_name,
        response_mime_type="application/json",
        response_schema=ProbeOut,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    )


def _storage_inr(tokens: float) -> float:
    """Upper bound: cached tokens x the full 300 s TTL. Storage is billed on
    the actual lifetime (A0), which is shorter."""
    return storage_cost_usd(tokens, TTL_S / 3600) * INR_PER_USD


def estimate_inr() -> dict[str, float]:
    """Expected INR from token counts. No network."""
    prompt = MEASURED_CACHED_TOKENS + ASSUMED_UNCACHED_TOKENS
    call_usd = cost_usd_for_model(
        MODEL, prompt, ASSUMED_OUTPUT_PLUS_THOUGHT_TOKENS, thought=0.0, cached=MEASURED_CACHED_TOKENS,
    )
    call_inr = call_usd * INR_PER_USD
    storage_inr = _storage_inr(MEASURED_CACHED_TOKENS)
    creation_inr = cache_creation_cost_usd(MEASURED_CACHED_TOKENS) * INR_PER_USD
    return {
        "call_inr": call_inr, "storage_inr": storage_inr, "creation_inr": creation_inr,
        "total_inr": call_inr + storage_inr + creation_inr,
    }


def _print_estimate() -> float:
    est = estimate_inr()
    print(f"[probe] --estimate for {PAPER_ID} on {MODEL}, one request, no network")
    print(f"[probe] measured: {MEASURED_CACHED_TOKENS} cached tokens (A0 summary, smallest cached paper)")
    print(f"[probe] ASSUMPTION: {ASSUMED_UNCACHED_TOKENS} uncached prompt tokens (the user turn)")
    print(f"[probe] ASSUMPTION: {ASSUMED_OUTPUT_PLUS_THOUGHT_TOKENS} output + thought tokens (generous; thinking is LOW)")
    print(f"[probe] call:     INR {est['call_inr']:.4f}")
    print(f"[probe] storage:  INR {est['storage_inr']:.4f} (separate; {MEASURED_CACHED_TOKENS} tokens x {TTL_S} s, "
          f"an upper bound on the actual lifetime)")
    print(f"[probe] creation: INR {est['creation_inr']:.4f} (not billed, observed on A0)")
    print(f"[probe] TOTAL expected: INR {est['total_inr']:.4f}  (hard stop above INR {MAX_INR})")
    return est["total_inr"]


def _describe_error(exc: BaseException) -> str:
    if isinstance(exc, errors.APIError):
        return f"{type(exc).__name__} code={exc.code} status={getattr(exc, 'status', None)} message={exc.message!r}: {exc!r}"
    return f"{type(exc).__name__}: {exc!r}"


async def run(client, paper_text: str) -> ProbeResult:
    """Creates the cache, sends exactly one request, deletes the cache (the
    context manager's finally). Never retries, never falls back."""
    result = ProbeResult()
    stats = ContextCacheStats(on_cache_failure=result.cache_errors.append)  # records the failure, does not raise

    async with paper_context_cache(client, MODEL, paper_text, N_CLAIMS, stats) as paper_cache:
        if paper_cache is None:
            result.fail_reason = FAIL_CACHE_NOT_CREATED
            result.error = "; ".join(result.cache_errors) or "paper_context_cache yielded no cache"
            return result
        result.cache_tokens = paper_cache.token_count

        response = None
        try:
            result.requests_sent = 1
            response = await client.aio.models.generate_content(
                model=MODEL, contents=cached_audit_contents(PROBE_PROMPT), config=build_probe_config(paper_cache.name),
            )
        except Exception as exc:
            result.fail_reason = FAIL_API_ERROR
            result.error = _describe_error(exc)

        if response is not None:
            usage, finish_reason = engine._extract_usage_and_finish_reason(response)
            result.usage = usage
            result.finish_reason = finish_reason
            result.parsed_is_probe_out = isinstance(getattr(response, "parsed", None), ProbeOut)
            if not result.parsed_is_probe_out:
                result.fail_reason = FAIL_PARSE_FAILED
                result.error = f"response.parsed is {type(getattr(response, 'parsed', None)).__name__}, text={getattr(response, 'text', None)!r}"
            elif not (usage and (usage.get("cached_tokens") or 0) > 0):
                result.fail_reason = FAIL_NO_CACHED_TOKENS
                result.error = f"cached_content_token_count={(usage or {}).get('cached_tokens')!r}"
            else:
                result.ok = True

    # The cache is deleted by now, whichever way the block above exited.
    result.lifetime_s = next(iter(stats.lifetimes_s.values()), None)
    cache_tokens = float(result.cache_tokens if result.cache_tokens is not None else MEASURED_CACHED_TOKENS)
    result.storage_inr = _storage_inr(cache_tokens)
    result.creation_inr = cache_creation_cost_usd(cache_tokens) * INR_PER_USD
    if result.usage:
        u = result.usage
        result.call_inr = (cost_usd_for_model(
            MODEL, u.get("prompt_tokens") or 0, u.get("output_tokens") or 0, u.get("thought_tokens") or 0,
            u.get("cached_tokens") or 0, u.get("tool_use_tokens") or 0,
        ) or 0.0) * INR_PER_USD
    return result


def _print_result(result: ProbeResult) -> None:
    print(f"[probe] {'OK' if result.ok else 'FAIL'}" + (f": {result.fail_reason}" if result.fail_reason else ""))
    if result.error:
        print(f"[probe] error: {result.error}")
    print(f"[probe] requests sent: {result.requests_sent}")
    print(f"[probe] response.parsed is ProbeOut: {result.parsed_is_probe_out}")
    print(f"[probe] finish_reason: {result.finish_reason}")
    u = result.usage or {}
    print(f"[probe] usage: prompt={u.get('prompt_tokens')} cached_content_token_count={u.get('cached_tokens')} "
          f"candidates={u.get('output_tokens')} thoughts={u.get('thought_tokens')}")
    print(f"[probe] cache tokens at creation: {result.cache_tokens}; actual lifetime (s): {result.lifetime_s}")
    if result.call_inr is not None:
        print(f"[probe] call cost:     INR {result.call_inr:.4f}")
    print(f"[probe] storage cost:  INR {result.storage_inr:.4f} (separate; cache tokens x {TTL_S} s, upper bound)")
    print(f"[probe] creation cost: INR {result.creation_inr:.4f} (not billed, observed on A0)")
    print(f"[probe] TOTAL: INR {result.total_inr:.4f}")


async def _main(args: argparse.Namespace) -> int:
    expected = _print_estimate()
    if args.estimate:
        return 0
    if expected > MAX_INR:
        print(f"[probe] REFUSED: estimate INR {expected:.4f} > INR {MAX_INR}; nothing sent")
        return 2
    try:
        paper_text = _load_paper_text(PAPER_ID)
    except PaperTextError as exc:
        print(f"[probe] FAIL: {FAIL_CACHE_NOT_CREATED}: {exc}; nothing sent")
        return 1
    result = await run(engine._build_client(), paper_text)
    _print_result(result)
    return 0 if result.ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--estimate", action="store_true", help="print the expected INR and exit; no network")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
