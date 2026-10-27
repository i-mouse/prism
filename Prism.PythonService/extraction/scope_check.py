"""Scope lister + scope checker (replay only for now; production wiring is a later step).

Design: docs/decisions.md, "Auditor redesign agreed: caching + scope check,
marks and caps - 2026-10-22", step-4 additions 2026-10-27.

Per claim, in the paper's claim loop while the paper's context cache is alive:
  - lister: its own call (gemini-3.6-flash, thinking LOW, no paper, no cache).
    System prompt prompts/scope_list_system.md; the user turn is the claim text
    only. Returns the claim's scope items.
  - checker: one call per claim that has items, referencing the paper's cache.
    The task is the user turn (prompts/scope_check_user.md); the cache carries
    the system prompt and the paper, so the request has no system_instruction,
    tools or tool_config.
Neither call is given the auditor's verdict, reasoning or quotes: scope_for_claim
takes the claim text and the paper's cache, nothing else. The result is combined
into the verdict later, at paper level, by extraction/scope_combine.py.

Both calls opt out of the cross-model fallback (a scope call is never served by
another model) and carry a call-kind tag; same-model retries and backoff are the
existing call path's. An error, timeout or parse failure of either call leaves the
claim's verdict unchanged, is counted in ScopeStats and logged loudly.

engine._generate_with_fallback and engine._build_client are always reached through
the engine module at call time: eval/replay_audit.py instruments the call by
replacing that attribute, which a `from ... import` would bypass.
"""
import json
import logging
import re
from dataclasses import dataclass, field

from google.genai import errors, types
from pydantic import BaseModel

from extraction import engine
from extraction.context_cache import PaperCache, cached_audit_contents
from extraction.prompt_loader import _read_prompt_file
from extraction.scope_schemas import ScopeCheckItem, ScopeCheckResponse, ScopeItem, ScopeListResponse

logger = logging.getLogger(__name__)

SCOPE_MODEL = "gemini-3.6-flash"
SCOPE_THINKING_LEVEL = "low"
LISTER_PROMPT_FILE = "scope_list_system.md"
CHECKER_TEMPLATE_FILE = "scope_check_user.md"
LISTER_CALL_KIND = "lister"
CHECKER_CALL_KIND = "checker"

_TEMPLATE_FIELD_RE = re.compile(r"\{\{(CLAIM|ITEMS)\}\}")


@dataclass
class ScopeStats:
    """Counters for one eval run.

    checker_calls counts claims for which the checker was attempted, including an
    attempt that failed before any request because the paper's cache was unusable.
    item_count_mismatches, contradicted_items, guard_failed and verdicts_lowered
    are filled in by extraction/scope_combine.py.
    """
    lister_calls: int = 0
    lister_failures: int = 0
    claims_with_items: int = 0
    checker_calls: int = 0
    checker_failures: int = 0
    item_count_mismatches: int = 0
    contradicted_items: int = 0
    guard_failed: int = 0
    verdicts_lowered: int = 0


@dataclass
class ClaimScope:
    """One claim's lister + checker outcome. checks is None when the checker was
    not called (no items, or the lister failed) or failed."""
    items: list[ScopeItem] = field(default_factory=list)
    checks: list[ScopeCheckItem] | None = None
    lister_failed: bool = False
    checker_failed: bool = False


class ScopeCacheUnavailable(Exception):
    """The checker has no usable cache for the paper."""


def _low_thinking() -> types.ThinkingConfig:
    return types.ThinkingConfig(thinking_level=types.ThinkingLevel(SCOPE_THINKING_LEVEL.upper()))


def format_items(items: list[ScopeItem]) -> str:
    """The checker's {{ITEMS}}: one "1. [kind] text" line per item."""
    return "\n".join(f"{i}. [{item.kind}] {item.text}" for i, item in enumerate(items, start=1))


def build_checker_user_text(claim_text: str, items: list[ScopeItem]) -> str:
    """prompts/scope_check_user.md with {{CLAIM}} and {{ITEMS}} replaced. One pass
    over the template, so text inside the claim is never itself substituted."""
    values = {"CLAIM": claim_text, "ITEMS": format_items(items)}
    return _TEMPLATE_FIELD_RE.sub(lambda m: values[m.group(1)], _read_prompt_file(CHECKER_TEMPLATE_FILE))


async def _generate_scope_json(
    contents: list[types.Content],
    config: types.GenerateContentConfig,
    response_schema: type[BaseModel],
    chat_id: str,
    correlation_id: str | None,
    log_subdir: str,
    call_kind: str,
) -> BaseModel:
    """One schema-enforced request on SCOPE_MODEL: no cross-model fallback, tagged
    with call_kind, parsed like engine._call_gemini_structured does (response.parsed,
    else json + model_validate), logged to logs/{log_subdir}/."""
    client = engine._build_client()
    response, used_model = await engine._generate_with_fallback(
        client, contents, config, chat_id, SCOPE_MODEL, SCOPE_MODEL, correlation_id,
        allow_fallback=False, call_kind=call_kind,
    )
    raw_text = response.text
    usage, finish_reason = engine._extract_usage_and_finish_reason(response)

    parsed = response.parsed
    if parsed is None:
        try:
            parsed = response_schema.model_validate(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError, TypeError) as parse_exc:
            engine._write_structured_log(
                log_subdir=log_subdir, chat_id=chat_id, correlation_id=correlation_id, model_used=used_model,
                request_message_count=len(contents), response_item_count=0, response_raw=str(raw_text),
                usage=usage, finish_reason=finish_reason,
            )
            raise ValueError(
                f"{call_kind} response for chat_id={chat_id} was neither parsed by the SDK nor valid for "
                f"{response_schema.__name__}: {parse_exc}"
            ) from parse_exc

    engine._write_structured_log(
        log_subdir=log_subdir, chat_id=chat_id, correlation_id=correlation_id, model_used=used_model,
        request_message_count=len(contents), response_item_count=len(parsed.items), response_raw=str(raw_text),
        usage=usage, finish_reason=finish_reason,
    )
    return parsed


async def list_scope_items(claim_text: str, chat_id: str, correlation_id: str | None = None) -> list[ScopeItem]:
    """The lister. Raises on any failure (scope_for_claim handles it)."""
    config = types.GenerateContentConfig(
        system_instruction=_read_prompt_file(LISTER_PROMPT_FILE),
        response_mime_type="application/json",
        response_schema=ScopeListResponse,
        thinking_config=_low_thinking(),
    )
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=claim_text)])]
    parsed = await _generate_scope_json(
        contents, config, ScopeListResponse, chat_id, correlation_id, "scope_list", LISTER_CALL_KIND,
    )
    return list(parsed.items)


async def check_scope_items(
    paper_cache: PaperCache | None, claim_text: str, items: list[ScopeItem], chat_id: str,
    correlation_id: str | None = None,
) -> list[ScopeCheckItem]:
    """The checker. Raises on any failure (scope_for_claim handles it).

    A non-retryable API error on the cached call follows context_cache's policy
    for the auditor: the cache is switched off for the rest of the paper, counted,
    and reported through ContextCacheStats.report_failure (an eval run stops there
    with CacheFailed). Unlike the audit, there is no uncached retry: the checker's
    paper lives only in the cache, so the call is a failed checker call and the
    verdict stays as it was.
    """
    if paper_cache is None or not paper_cache.active or paper_cache.model != SCOPE_MODEL:
        raise ScopeCacheUnavailable(
            f"no usable context cache on {SCOPE_MODEL} for this paper "
            f"(cache={getattr(paper_cache, 'name', None)}, active={getattr(paper_cache, 'active', None)})"
        )
    config = types.GenerateContentConfig(
        cached_content=paper_cache.name,
        thinking_config=_low_thinking(),
        response_mime_type="application/json",
        response_schema=ScopeCheckResponse,
    )
    contents = cached_audit_contents(build_checker_user_text(claim_text, items))
    try:
        parsed = await _generate_scope_json(
            contents, config, ScopeCheckResponse, chat_id, correlation_id, "scope_check", CHECKER_CALL_KIND,
        )
    except errors.APIError as exc:
        if engine._is_retryable(exc):
            raise
        stats = paper_cache.stats
        paper_cache.active = False
        stats.cached_call_failures += 1
        reason = (
            f"cached scope-check call failed (cache={paper_cache.name}, status={exc.code}, "
            f"message={exc.message!r}): {exc!r}"
        )
        logger.error("%s; cache switched off for this paper, this claim's scope check fails", reason)
        stats.report_failure(reason)
        raise
    return list(parsed.items)


async def scope_for_claim(
    paper_cache: PaperCache | None, claim_text: str, chat_id: str, stats: ScopeStats,
    correlation_id: str | None = None, claim_ref: str = "",
) -> ClaimScope:
    """Lister, then checker if there are items. Takes the claim text and the
    paper's cache only. Never raises an Exception: a failure is counted, logged
    loudly, and leaves the claim's verdict alone (BaseExceptions such as
    CapExceeded and CacheFailed still stop the run)."""
    stats.lister_calls += 1
    try:
        items = await list_scope_items(claim_text, chat_id, correlation_id)
    except Exception as exc:
        stats.lister_failures += 1
        logger.error("SCOPE LISTER FAILED for %s; verdict unchanged: %r", claim_ref or chat_id, exc, exc_info=True)
        return ClaimScope(lister_failed=True)
    logger.info("scope lister: %s: %d items", claim_ref or chat_id, len(items))
    if not items:
        return ClaimScope()

    stats.claims_with_items += 1
    stats.checker_calls += 1
    try:
        checks = await check_scope_items(paper_cache, claim_text, items, chat_id, correlation_id)
    except Exception as exc:
        stats.checker_failures += 1
        logger.error("SCOPE CHECKER FAILED for %s; verdict unchanged: %r", claim_ref or chat_id, exc, exc_info=True)
        return ClaimScope(items=items, checker_failed=True)
    return ClaimScope(items=items, checks=checks)
