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
    global _pool
    if _pool is None:
        _pool = create_db_connection_pool()
        await _pool.open()
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


@tool
async def query_paper_claims(active_file_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve claims from paper_claims table for the active paper.
    Uses Postgres full-text search (to_tsvector/websearch_to_tsquery) on
    claim_summary + claim_text_verbatim. No fallback: a query whose terms
    don't overlap any claim's text returns an empty list, full stop - see
    docs/audit/ui_chat_audit_2026-09-08.md for why the previous
    top-N-by-position fallback made the graph's refusal path unreachable.
    Summary/overview questions are out of scope for this tool (and for
    chat generally - that's the Overview tab's job).
    Filter: active_file_id (resolved to the paper's latest document_extractor_id).
    Returns: list of {claim_id, claim_summary, claim_text_verbatim, label,
                      missing, grounding_status, reason, evidence_spans (top-2)}.
    Empty list if no matches or no extraction exists yet for this paper.
    """
    try:
        document_extractor_id = await _resolve_document_extractor_id(active_file_id)
        if document_extractor_id is None:
            return []

        pool = await _get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # websearch_to_tsquery handles punctuation/quoting more gracefully than
                # plainto_tsquery, but both AND all bare terms together - a single word
                # in the user's question absent from the claim text (e.g. "baselines")
                # still yields zero rows. That's expected and desired now: a miss here
                # is a real signal, not something to paper over with a fallback.
                await cur.execute(
                    """
                    SELECT id, claim_text_verbatim, claim_summary, label, missing,
                           grounding_status, reason, evidence_spans
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

        results = []
        for row in rows:
            results.append({
                "claim_id": str(row["id"]),
                "claim_summary": row["claim_summary"],
                "claim_text_verbatim": row["claim_text_verbatim"],
                "label": row["label"],
                "missing": row["missing"],
                "grounding_status": row["grounding_status"],
                "reason": row["reason"],
                "evidence_spans": (row["evidence_spans"] or [])[:2],
            })
        print(f" [CLAIMS] query_paper_claims: file_id={active_file_id} returned {len(results)} claims")
        return results
    except Exception as exc:
        print(f" [WARN] query_paper_claims failed for active_file_id={active_file_id}: {exc!r}")
        return []


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
