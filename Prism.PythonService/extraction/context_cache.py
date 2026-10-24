"""Explicit context caching for the auditor call (Call #3).

BETA: Gemini explicit caching (client.caches) is served from v1beta, so its
behaviour, limits and billing may change. All SDK cache access lives in this
module; extraction/engine.py only sees a PaperCache handle.

Design (docs/decisions.md, "Auditor redesign agreed ... - 2026-10-22"): the
system prompt and the paper text are cached once per paper, and each claim's
audit references that cache. Prompt order stays paper -> claim. Cached tokens
are billed at the cached rate; creation and storage are billed separately
(see eval/pricing.py), so a cache is only worth creating for a paper with
several claims.

Gemini rejects a generateContent request that combines cached_content with
system_instruction, tools or tool_config, so the system prompt lives INSIDE
the cache and a cached audit request carries none of those three fields.

The cache holds a user turn with the paper; the per-claim request is a second
user turn with the claim. The concatenated text is identical to the uncached
request, but the two-turn structure is not (approved, decisions.md).

Flag: the cache is switched on by an explicit parameter only (extract_claims
context_cache=..., replay_audit --cache), default off. Wiring it to a
config.py settings field is a later follow-up.

Failure policy: a failed creation or a failed cached call never blocks an
audit. It is logged in full, counted in ContextCacheStats, and the audit
continues uncached. Eval runs can set ContextCacheStats.on_cache_failure to
turn the first failure into a stop (see CacheFailed).
"""
import logging
import math
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Callable

from google import genai
from google.genai import types

from extraction.prompt_loader import build_gemini_messages_for_audit

logger = logging.getLogger(__name__)

# Only this model uses explicit caching; any other audit model runs uncached.
CACHEABLE_MODEL = "gemini-3.6-flash"

# TTL = claims x slowest observed per-claim time x margin, clamped. Measured on
# dev replays (docs/evals/fixtures/dev/exp1_*): slowest audit call 37.7 s
# (exp1_high_2), slowest structure call 13.1 s; 37.7 + 13.1 = 50.8 -> 51 s.
# Storage is billed on the TTL, not on the actual lifetime, so the TTL is
# sized to each paper's own claim count rather than fixed.
PER_CLAIM_SECONDS = 51
TTL_MARGIN = 1.25
MIN_TTL_S = 300
MAX_TTL_S = 3600

_CLAIM_MARKER = "CLAIM TO AUDIT:\n"


class CacheFailed(BaseException):
    """Raised by an eval run's on_cache_failure callback to stop the run.

    A BaseException on purpose, like eval.replay_audit.CapExceeded: the retry
    loops around the model calls use `except Exception`, which it passes
    straight through, so a stop is never retried or swallowed.
    """


@dataclass
class ContextCacheStats:
    """Counters for one process or one eval run. on_cache_failure is called
    (after the failure is logged and counted) on a creation failure and on a
    cached-call API error, before any uncached retry."""
    papers_cached: int = 0
    creation_failures: int = 0
    cached_call_failures: int = 0
    # Claims whose audit ran uncached because of a cache problem: the one
    # retry after a cached-call failure, later claims of a paper whose cache
    # was switched off, and every claim of a paper whose creation failed.
    cache_fallbacks: int = 0
    tokens_created_total: int = 0
    token_count_missing: int = 0
    on_cache_failure: Callable[[str], None] | None = None

    def report_failure(self, reason: str) -> None:
        if self.on_cache_failure is not None:
            self.on_cache_failure(reason)


@dataclass
class PaperCache:
    """One paper's live cache. active goes False when a cached call fails, and
    every later claim of the paper then runs uncached."""
    name: str
    model: str
    token_count: int | None
    ttl_s: int
    prefix_text: str
    stats: ContextCacheStats
    active: bool = True


def ttl_for_claims(n_claims: int) -> int:
    return min(MAX_TTL_S, max(MIN_TTL_S, math.ceil(n_claims * PER_CLAIM_SECONDS * TTL_MARGIN)))


def _is_cacheable_model(model: str) -> bool:
    return model.lower().rsplit("/", 1)[-1] == CACHEABLE_MODEL


def _split_probe(paper_text: str) -> tuple[str, str]:
    """Returns (system_prompt, paper_prefix_text) taken from the same builder
    the uncached request uses, so the cached text cannot drift from it."""
    system_msg, user_msg = build_gemini_messages_for_audit(paper_text, "", "")
    user_content = user_msg["content"]
    prefix = user_content[: user_content.rindex(_CLAIM_MARKER)]
    if paper_text not in prefix:
        raise ValueError("audit user message does not carry the paper text before the claim marker")
    return system_msg["content"], prefix


def split_audit_user_message(paper_cache: PaperCache, user_content: str) -> str | None:
    """Returns the per-claim part of the audit user message (everything after
    the cached paper prefix), or None when the message does not start with the
    cached prefix (the caller then audits uncached)."""
    if not user_content.startswith(paper_cache.prefix_text):
        return None
    return user_content[len(paper_cache.prefix_text):]


def cached_audit_contents(claim_text: str) -> list[types.Content]:
    return [types.Content(role="user", parts=[types.Part.from_text(text=claim_text)])]


async def _create(
    client: genai.Client, model: str, paper_text: str, n_claims: int, stats: ContextCacheStats,
) -> PaperCache | None:
    ttl_s = ttl_for_claims(n_claims)
    try:
        system_prompt, prefix = _split_probe(paper_text)
        created = await client.aio.caches.create(
            model=model,
            config=types.CreateCachedContentConfig(
                display_name=f"prism-audit-{n_claims}claims",
                system_instruction=system_prompt,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prefix)])],
                ttl=f"{ttl_s}s",
            ),
        )
        if not created.name:
            raise ValueError("caches.create returned no cache name")
    except Exception as exc:
        reason = (
            f"context cache creation failed (model={model}, claims={n_claims}, ttl={ttl_s}s, "
            f"code={getattr(exc, 'code', None)}): {exc!r}"
        )
        logger.error("%s; continuing uncached", reason, exc_info=True)
        stats.creation_failures += 1
        stats.cache_fallbacks += n_claims
        stats.report_failure(reason)
        return None

    usage = getattr(created, "usage_metadata", None)
    token_count = getattr(usage, "total_token_count", None)
    stats.papers_cached += 1
    if token_count is None:
        stats.token_count_missing += 1
    else:
        stats.tokens_created_total += token_count
    logger.info("context cache created: name=%s tokens=%s ttl=%ss claims=%d model=%s",
                created.name, token_count, ttl_s, n_claims, model)
    return PaperCache(
        name=created.name, model=model, token_count=token_count, ttl_s=ttl_s, prefix_text=prefix, stats=stats,
    )


async def _delete(client: genai.Client, paper_cache: PaperCache) -> None:
    """Housekeeping only: storage is billed on the TTL whether or not this
    succeeds, and an undeleted cache expires on its own."""
    try:
        await client.aio.caches.delete(name=paper_cache.name)
    except Exception as exc:
        logger.warning("context cache delete failed (name=%s): %r", paper_cache.name, exc, exc_info=True)


@asynccontextmanager
async def paper_context_cache(
    client: genai.Client, model: str, paper_text: str, n_claims: int, stats: ContextCacheStats,
) -> AsyncIterator[PaperCache | None]:
    """Creates one cache for a paper, yields it (or None when the model is not
    cacheable, there are no claims, or creation failed), and deletes it on
    exit. The delete runs for any exit, including a BaseException such as
    CapExceeded or CacheFailed, and never raises itself.

    Create the cache before the paper's first claim audit and open this
    around the whole claim loop: one create per paper, so claims running
    concurrently never race to create it.
    """
    paper_cache = None
    if n_claims > 0 and _is_cacheable_model(model):
        paper_cache = await _create(client, model, paper_text, n_claims, stats)
    try:
        yield paper_cache
    finally:
        if paper_cache is not None:
            await _delete(client, paper_cache)
