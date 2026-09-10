"""Retrieval tools for the paper-scoped chat agent.

Both tools are hard-filtered by active_file_id: query_paper_claims resolves
the file's most recent document_extractors row and scopes the paper_claims
query to it; query_paper_chunks scopes the Qdrant search to points whose
payload.file_id matches. Neither tool ever raises - retrieval failures are
logged and surfaced as an empty list, which the agent's check_empty node
turns into a refusal rather than a silent wrong answer (see PR C2,
fix/chat-retrieval-refusal, and docs/audit/ui_chat_audit_2026-09-08.md for
why the previous fallback-to-everything behavior made refusal unreachable).
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool
from psycopg.rows import dict_row

from memory_db import create_db_connection_pool
from RAGService import RAGService

LOGS_DIR = Path(__file__).parent.parent / "logs" / "chat"

# Cosine similarity floor below which a retrieved chunk is excluded from
# chat context entirely. Introduced in PR C2 (fix/chat-retrieval-refusal) to
# make refusal_node reachable - previously query_paper_chunks returned raw
# top-k regardless of relevance, so context was never empty and the LLM
# always synthesized a soft answer instead of the graph refusing. 0.35 is a
# starting point picked before any real query/score distribution existed -
# every retrieval's raw scores are logged to logs/chat/ (see
# _log_chat_retrieval below) specifically so this value can be retuned from
# real traffic once the PR ships.
CHUNK_SIMILARITY_THRESHOLD = 0.35

_pool = None
_pool_lock = asyncio.Lock()
_ragservice: RAGService | None = None


def _log_chat_retrieval(active_file_id: str, query: str, scores: list[float], returned_count: int) -> None:
    """Logs every chunk retrieval's raw top-k similarity scores next to the
    query text and how many chunks cleared CHUNK_SIMILARITY_THRESHOLD.
    Follows the same append-a-JSON-file-per-event pattern as
    extraction/writer.py and extraction/engine.py under logs/extraction/,
    just rooted at logs/chat/ instead."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        filename_ts = now.strftime("%Y%m%dT%H%M%S%f")
        log_path = LOGS_DIR / f"{filename_ts}_{active_file_id}.json"
        log_entry = {
            "timestamp": now.isoformat(),
            "active_file_id": active_file_id,
            "query": query,
            "top_k_scores": scores,
            "threshold": CHUNK_SIMILARITY_THRESHOLD,
            "returned_chunk_count": returned_count,
        }
        log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f" [WARN] failed to write chat retrieval log for active_file_id={active_file_id}: {exc!r}")


async def _get_pool():
    # get_total_claim_count and query_paper_claims now both resolve this pool
    # concurrently (via asyncio.gather in agent.py's execute_tools), so the
    # first-call initialization needs to be lock-guarded: without it, two
    # coroutines racing here would both see `_pool is None`, and the second
    # would hand back a pool object that's been constructed but not yet
    # open()'d, which hangs the first connection acquire against it.
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                pool = create_db_connection_pool()
                await pool.open()
                _pool = pool
    return _pool


async def _get_ragservice() -> RAGService:
    global _ragservice
    if _ragservice is None:
        _ragservice = await RAGService.create()
    return _ragservice


async def _resolve_document_extractor_id(active_file_id: str) -> uuid.UUID | None:
    pool = await _get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id FROM document_extractors
                WHERE file_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (uuid.UUID(active_file_id),),
            )
            row = await cur.fetchone()
            return row[0] if row else None


_CLAIM_COLUMNS = (
    "id, claim_text_verbatim, claim_summary, label, missing, "
    "grounding_status, reason, evidence_spans, position"
)

_VALID_CLAIM_LABELS = {"supported", "partially_supported", "not_supported"}

# Metadata/bulk lookups ("which claims are refused?", "list every claim")
# have no natural rank to cut off by - unlike the FTS `query` mode's
# per-call `limit`, this cap exists purely so a paper with an unusually
# large claim set can't blow out the LLM's context window.
_METADATA_LOOKUP_LIMIT = 50


@tool
async def query_paper_claims(
    active_file_id: str,
    query: str | None = None,
    position: int | None = None,
    label_filter: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Use this tool to find claims from the current paper.

    Modes (checked in this precedence order when more than one is given):
      position=N       : fetch the one claim at that number (0, 1, 2, ...).
                          Use for "claim 11", "show me claim 3", "what does
                          claim 5 say", etc.
      label_filter=STR  : fetch every claim with that audit label.
                          Values: "supported", "partially_supported",
                          "not_supported". Use for "which claims are
                          refused?", "show partial claims", "any supported
                          claims?", etc.
      query=STR         : full-text search over claim text.
                          Use for topical questions, e.g. "claims about
                          hallucination".
      (all None)        : return every claim for the paper (up to 50,
                          ordered by position). Use for "list every claim",
                          "summary of claims", "how many claims in total",
                          "any refusal?", etc.

    Precedence: position > label_filter > query > all.
    Filter: active_file_id (resolved to the paper's latest document_extractor_id).
    Returns: list of {claim_id, position, claim_summary, claim_text_verbatim,
                      label, missing, grounding_status, reason,
                      evidence_spans (top-2)}.
    Empty list if no matches, an unrecognized label_filter value, a
    position that doesn't exist, or no extraction yet for this paper -
    never raises (see module docstring).
    """
    try:
        document_extractor_id = await _resolve_document_extractor_id(active_file_id)
        if document_extractor_id is None:
            return []

        pool = await _get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if position is not None:
                    mode = "position"
                    await cur.execute(
                        f"""
                        SELECT {_CLAIM_COLUMNS}
                        FROM paper_claims
                        WHERE document_extractor_id = %s AND position = %s
                        LIMIT 1
                        """,
                        (document_extractor_id, position),
                    )
                    rows = await cur.fetchall()
                elif label_filter is not None:
                    mode = "label_filter"
                    if label_filter not in _VALID_CLAIM_LABELS:
                        print(
                            f" [WARN] query_paper_claims: unrecognized label_filter={label_filter!r}, "
                            f"expected one of {sorted(_VALID_CLAIM_LABELS)} - returning no matches"
                        )
                        return []
                    await cur.execute(
                        f"""
                        SELECT {_CLAIM_COLUMNS}
                        FROM paper_claims
                        WHERE document_extractor_id = %s AND label = %s
                        ORDER BY position ASC
                        LIMIT {_METADATA_LOOKUP_LIMIT}
                        """,
                        (document_extractor_id, label_filter),
                    )
                    rows = await cur.fetchall()
                elif query is not None:
                    mode = "query"
                    # websearch_to_tsquery handles punctuation/quoting more gracefully than
                    # plainto_tsquery, but both AND all bare terms together - a single word
                    # in the user's question absent from the claim text (e.g. "baselines")
                    # still yields zero rows. That's expected and desired now: a miss here
                    # is a real signal, not something to paper over with a fallback.
                    await cur.execute(
                        f"""
                        SELECT {_CLAIM_COLUMNS}
                        FROM paper_claims
                        WHERE document_extractor_id = %s
                          AND to_tsvector('english', claim_summary || ' ' || claim_text_verbatim)
                              @@ websearch_to_tsquery('english', %s)
                        ORDER BY ts_rank(
                            to_tsvector('english', claim_summary || ' ' || claim_text_verbatim),
                            websearch_to_tsquery('english', %s)
                        ) DESC
                        LIMIT %s
                        """,
                        (document_extractor_id, query, query, limit),
                    )
                    rows = await cur.fetchall()
                else:
                    mode = "all"
                    await cur.execute(
                        f"""
                        SELECT {_CLAIM_COLUMNS}
                        FROM paper_claims
                        WHERE document_extractor_id = %s
                        ORDER BY position ASC
                        LIMIT {_METADATA_LOOKUP_LIMIT}
                        """,
                        (document_extractor_id,),
                    )
                    rows = await cur.fetchall()

        results = []
        for row in rows:
            results.append({
                "claim_id": str(row["id"]),
                "position": row["position"],
                "claim_summary": row["claim_summary"],
                "claim_text_verbatim": row["claim_text_verbatim"],
                "label": row["label"],
                "missing": row["missing"],
                "grounding_status": row["grounding_status"],
                "reason": row["reason"],
                "evidence_spans": (row["evidence_spans"] or [])[:2],
            })
        print(f" [CLAIMS] query_paper_claims: file_id={active_file_id} mode={mode} returned {len(results)} claims")
        return results
    except Exception as exc:
        print(f" [WARN] query_paper_claims failed for active_file_id={active_file_id}: {exc!r}")
        return []


async def get_total_claim_count(active_file_id: str) -> int:
    """Non-tool helper used directly by the agent graph (like
    query_paper_chunks_scored) to fetch the paper's true total claim count
    on every turn, regardless of which retrieval route the router picked -
    see docs/audit/chat_claim_count_still_wrong_2026-09-10.md. Never raises;
    0 if there's no extraction yet for this paper or the lookup fails."""
    try:
        document_extractor_id = await _resolve_document_extractor_id(active_file_id)
        if document_extractor_id is None:
            return 0

        pool = await _get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM paper_claims WHERE document_extractor_id = %s",
                    (document_extractor_id,),
                )
                row = await cur.fetchone()
                return row[0] if row else 0
    except Exception as exc:
        print(f" [WARN] get_total_claim_count failed for active_file_id={active_file_id}: {exc!r}")
        return 0


async def _search_chunks_scored(
    active_file_id: str, query: str, limit: int
) -> tuple[list[dict], list[float]]:
    """Shared implementation behind query_paper_chunks and
    query_paper_chunks_scored: runs the Qdrant search once, logs the raw
    scores, and returns both the CHUNK_SIMILARITY_THRESHOLD-filtered chunks
    and the raw (unfiltered) score list. The raw scores are needed by
    check_empty to tell a genuinely out-of-scope question apart from one
    that is in-scope but unsupported - both end up with zero chunks past
    the threshold, but only the latter had any real signal below it.
    """
    ragservice = await _get_ragservice()
    hits = await ragservice.search_db(user_query=query, limit=limit, file_id=active_file_id)
    scores = [hit.score for hit in hits]
    filtered = [
        {
            "chunk_text": hit.payload.get("text", ""),
            "section": hit.payload.get("section"),
            "page_number": hit.payload.get("page_number"),
            "score": hit.score,
        }
        for hit in hits
        if hit.score >= CHUNK_SIMILARITY_THRESHOLD
    ]
    _log_chat_retrieval(active_file_id, query, scores, len(filtered))
    return filtered, scores


@tool
async def query_paper_chunks(active_file_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve raw paper chunks from Qdrant for the active paper.
    Embeds the query and runs a cosine similarity search filtered to
    payload.file_id == active_file_id, then drops any chunk scoring below
    CHUNK_SIMILARITY_THRESHOLD. If every top-k result is below the
    threshold, returns an empty list rather than the raw top-k.
    Returns: list of {chunk_text, section, page_number, score}.
    Empty list if no matches clear the threshold.
    """
    try:
        filtered, _ = await _search_chunks_scored(active_file_id, query, limit)
        return filtered
    except Exception as exc:
        print(f" [WARN] query_paper_chunks failed for active_file_id={active_file_id}: {exc!r}")
        return []


async def query_paper_chunks_scored(
    active_file_id: str, query: str, limit: int = 5
) -> tuple[list[dict], list[float]]:
    """Non-tool variant used directly by the agent graph (not via .ainvoke)
    so it can see the raw pre-threshold scores alongside the filtered
    chunks - see _search_chunks_scored docstring for why."""
    try:
        return await _search_chunks_scored(active_file_id, query, limit)
    except Exception as exc:
        print(f" [WARN] query_paper_chunks_scored failed for active_file_id={active_file_id}: {exc!r}")
        return [], []
