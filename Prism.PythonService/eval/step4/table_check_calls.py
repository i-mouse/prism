"""The two model calls of the step 4 table checker (eval path only) and the per-claim sequence around them
(decisions.md "Pre-registration: step 4 - table checker for table claims (text only), Vertex, 3 runs - 2026-11-15",
rulings 2 and 4).

  - lister: extraction.scope_check.list_scope_items, reused unchanged (its prompt, schema, model, thinking level
    and "lister" call kind are its own). One retry here on any failure.
  - checker: one schema-enforced call per routed claim on CHECKER_MODEL at the auditor's thinking level, with the
    claim, its pieces and the paper's table blocks in the user turn. No cross-model fallback, call kind
    CHECKER_CALL_KIND. One retry on a call failure, invalid JSON or invalid piece ids.

check_claim never raises an Exception: a failure is counted in the trace and the claim falls back to today's
auditor (the caller runs it). BaseExceptions (a cost-cap stop, a cache failure) pass through untouched.

engine._generate_with_fallback and engine._build_client are reached through the engine module at call time:
eval/replay_audit.py instruments the call by replacing that attribute.
"""
import json
import logging
from typing import cast

from google.genai import types

from eval.step4 import table_check
from eval.step4.table_check import ClaimTrace, Piece, TableBlocks
from eval.step4.table_check_schemas import PieceAnswer, TableCheckResponse
from extraction import engine, scope_check

logger = logging.getLogger(__name__)

CHECKER_MODEL = "gemini-3.6-flash"
CHECKER_CALL_KIND = "table_checker"
LISTER_CALL_KIND = scope_check.LISTER_CALL_KIND
LISTER_MODEL = scope_check.SCOPE_MODEL
LOG_SUBDIR = "table_check"
ATTEMPTS = 2     # the call and one retry (ruling 4)


def _thinking(level: str | None) -> types.ThinkingConfig | None:
    if level is None:
        return None
    return types.ThinkingConfig(thinking_level=types.ThinkingLevel(level.upper()))


async def list_pieces(claim_text: str, chat_id: str, correlation_id: str | None = None) -> list[Piece]:
    """The scope lister's items as numbered pieces. One retry; raises the last error when both attempts fail."""
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            items = await scope_check.list_scope_items(claim_text, chat_id, correlation_id)
            return table_check.pieces_from_items(items)
        except Exception as exc:
            last = exc
            logger.warning("table-check lister attempt %d/%d failed for %s: %r", attempt, ATTEMPTS, chat_id, exc)
    assert last is not None
    raise last


async def _checker_request(
    user_text: str, n_pieces: int, level: str | None, chat_id: str, correlation_id: str | None,
) -> tuple[list[PieceAnswer], str]:
    """One checker request. Raises on an API failure, on a response that is not valid for TableCheckResponse, and
    on piece ids that are out of range or repeated."""
    client = engine._build_client()
    config = types.GenerateContentConfig(
        system_instruction=table_check.checker_system_prompt(),
        response_mime_type="application/json",
        response_schema=TableCheckResponse,
        thinking_config=_thinking(level),
    )
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_text)])]
    response, used_model = await engine._generate_with_fallback(
        client, contents, config, chat_id, CHECKER_MODEL, CHECKER_MODEL, correlation_id,
        allow_fallback=False, call_kind=CHECKER_CALL_KIND,
    )
    raw_text = response.text
    usage, finish_reason = engine._extract_usage_and_finish_reason(response)

    def log(item_count: int) -> None:
        engine._write_structured_log(
            log_subdir=LOG_SUBDIR, chat_id=chat_id, correlation_id=correlation_id, model_used=used_model,
            request_message_count=len(contents), response_item_count=item_count, response_raw=str(raw_text),
            usage=usage, finish_reason=finish_reason,
        )

    parsed = response.parsed
    if not isinstance(parsed, TableCheckResponse):
        try:
            parsed = TableCheckResponse.model_validate(json.loads(cast(str, raw_text)))
        except (json.JSONDecodeError, ValueError, TypeError) as parse_exc:
            log(0)
            raise ValueError(
                f"{CHECKER_CALL_KIND} response for chat_id={chat_id} is not valid for TableCheckResponse: {parse_exc}"
            ) from parse_exc
    log(len(parsed.pieces))
    problem = table_check.invalid_answer_ids(n_pieces, parsed.pieces)
    if problem is not None:
        raise ValueError(f"{CHECKER_CALL_KIND} response for chat_id={chat_id}: {problem}")
    return list(parsed.pieces), used_model


async def check_pieces(
    claim_text: str, pieces: list[Piece], blocks: TableBlocks, level: str | None, chat_id: str,
    correlation_id: str | None = None,
) -> tuple[list[PieceAnswer], str]:
    """(answers, served model). One retry; raises the last error when both attempts fail."""
    user_text = table_check.build_checker_user_text(claim_text, pieces, blocks.text)
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return await _checker_request(user_text, len(pieces), level, chat_id, correlation_id)
        except Exception as exc:
            last = exc
            logger.warning("table checker attempt %d/%d failed for %s: %r", attempt, ATTEMPTS, chat_id, exc)
    assert last is not None
    raise last


async def check_claim(
    claim_text: str, cited: tuple[int, ...], blocks: TableBlocks, level: str | None, chat_id: str,
    correlation_id: str | None = None, claim_ref: str = "",
) -> ClaimTrace:
    """Lister, then the checker, then the code guard and the claim result. The claim must already be routed.
    trace.use_fallback tells the caller to run today's auditor on the claim."""
    ref = claim_ref or chat_id
    trace = ClaimTrace(cited=list(cited))
    try:
        pieces = await list_pieces(claim_text, chat_id, correlation_id)
    except Exception as exc:
        logger.error("TABLE-CHECK LISTER FAILED for %s after retry; today's auditor decides: %r", ref, exc)
        trace.lister_failed = True
        trace.use_fallback = True
        trace.fallback_reason = table_check.FALLBACK_LISTER_FAILED
        return trace
    if not pieces:
        trace.use_fallback = True
        trace.fallback_reason = table_check.FALLBACK_ZERO_PIECES
        return trace

    answers: list[PieceAnswer] | None
    try:
        answers, trace.checker_model_served = await check_pieces(
            claim_text, pieces, blocks, level, chat_id, correlation_id,
        )
    except Exception as exc:
        logger.error("TABLE CHECKER FAILED for %s after retry; its pieces are could-not-check: %r", ref, exc)
        trace.checker_failed = True
        answers = None

    trace.pieces = table_check.piece_outcomes(pieces, answers, blocks)
    result = table_check.claim_result(trace.pieces)
    trace.n_failed = result.n_failed
    trace.n_could_not_check = result.n_could_not_check
    trace.label = result.label
    trace.use_fallback = result.use_fallback
    if result.use_fallback:
        trace.fallback_reason = table_check.FALLBACK_COULD_NOT_CHECK
    logger.info(
        "table check: %s: %d pieces, %d failed, %d could-not-check -> %s",
        ref, len(trace.pieces), result.n_failed, result.n_could_not_check, result.label or "fallback audit",
    )
    return trace
