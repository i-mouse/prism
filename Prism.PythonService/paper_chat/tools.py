"""Retrieval tools for the paper-scoped chat agent.

Both tools are hard-filtered by active_file_id: query_paper_claims resolves
the file's most recent document_extractors row and scopes the paper_claims
query to it; query_paper_chunks scopes the Qdrant search to points whose
payload.file_id matches. Neither tool ever raises - retrieval failures are
logged and surfaced as an empty list, which the agent's check_empty node
turns into a loud refusal rather than a silent wrong answer.
"""
import uuid

from langchain_core.tools import tool
from psycopg.rows import dict_row

from memory_db import create_db_connection_pool
from RAGService import RAGService

_pool = None
_ragservice: RAGService | None = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = create_db_connection_pool()
        await _pool.open()
    return _pool


def _get_ragservice() -> RAGService:
    global _ragservice
    if _ragservice is None:
        _ragservice = RAGService()
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
    claim_summary + claim_text_verbatim, falling back to the paper's top
    claims by position when the tsquery yields no rows (e.g. the question's
    wording doesn't overlap with claim text at all).
    Filter: active_file_id (resolved to the paper's latest document_extractor_id).
    Returns: list of {claim_id, claim_summary, claim_text_verbatim, label,
                      missing, grounding_status, evidence_spans (top-2)}.
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
                # still yields zero rows. That's expected here; the fallback below is
                # the real safety net, not a smarter match.
                await cur.execute(
                    """
                    SELECT id, claim_text_verbatim, claim_summary, label, missing,
                           grounding_status, evidence_spans
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

                if not rows:
                    # Full-text search found nothing for this query's terms. Matching
                    # the whole conversational question against claim text via ILIKE
                    # (the previous fallback) never matches - fall back to the paper's
                    # top claims by position instead, so a genuinely on-topic question
                    # about the paper still gets claim context to answer from.
                    await cur.execute(
                        """
                        SELECT id, claim_text_verbatim, claim_summary, label, missing,
                               grounding_status, evidence_spans
                        FROM paper_claims
                        WHERE document_extractor_id = %s
                        ORDER BY position ASC
                        LIMIT %s
                        """,
                        (document_extractor_id, limit),
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
                "evidence_spans": (row["evidence_spans"] or [])[:2],
            })
        print(f" [CLAIMS] query_paper_claims: file_id={active_file_id} returned {len(results)} claims")
        return results
    except Exception as exc:
        print(f" [WARN] query_paper_claims failed for active_file_id={active_file_id}: {exc!r}")
        return []


@tool
async def query_paper_chunks(active_file_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve raw paper chunks from Qdrant for the active paper.
    Embeds the query and runs a cosine similarity search filtered to
    payload.file_id == active_file_id.
    Returns: list of {chunk_text, section, page_number, score}.
    Empty list if no matches.
    """
    try:
        ragservice = _get_ragservice()
        hits = ragservice.search_db(user_query=query, limit=limit, file_id=active_file_id)
        return [
            {
                "chunk_text": hit.payload.get("text", ""),
                "section": hit.payload.get("section"),
                "page_number": hit.payload.get("page_number"),
                "score": hit.score,
            }
            for hit in hits
        ]
    except Exception as exc:
        print(f" [WARN] query_paper_chunks failed for active_file_id={active_file_id}: {exc!r}")
        return []
