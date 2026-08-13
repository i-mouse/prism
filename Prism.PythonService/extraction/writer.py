"""Writes finalized extraction results (metadata + grounded claims) to Postgres.

Reuses the shared connection pool from memory_db.py - no duplicate pool,
no ORM, no migrations (schema is owned by C# EF Core). One connection,
one transaction per write: either everything for a paper lands, or nothing
does.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from memory_db import create_db_connection_pool
from extraction.schemas import ClaimFinal, PaperMetadataFinal

LOGS_DIR = Path(__file__).parent.parent / "logs" / "writer"

# Fixed, greppable Guid seeded via Prism.ApiService/Migrations/20260809055747_SeedResearchPaperDomain.cs.
# The Python extraction pipeline currently only produces research-paper extractions.
RESEARCH_PAPER_DOMAIN_ID = "11111111-1111-1111-1111-111111111111"

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> AsyncConnectionPool:
    """Lazily creates and opens the shared connection pool on first use."""
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                pool = create_db_connection_pool()
                await pool.open()
                _pool = pool
    return _pool


def _write_writer_log(
    chat_id: str,
    correlation_id: str | None,
    file_id: str,
    document_extractor_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    claims_written_count: int,
    fields_stored_keys: list[str],
    prompt_version: str,
    model_used: str,
) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename_ts = now.strftime("%Y%m%dT%H%M%S%f")
    log_path = LOGS_DIR / f"{filename_ts}_{chat_id}_{correlation_id or 'none'}.json"

    log_entry = {
        "timestamp": now.isoformat(),
        "chat_id": chat_id,
        "correlation_id": correlation_id,
        "file_id": file_id,
        "document_extractor_id": str(document_extractor_id),
        "extraction_run_id": str(extraction_run_id),
        "domain_id": RESEARCH_PAPER_DOMAIN_ID,
        "claims_written_count": claims_written_count,
        "fields_stored_keys": fields_stored_keys,
        "prompt_version": prompt_version,
        "model_used": model_used,
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


async def write_extraction_result(
    file_id: str,
    metadata: PaperMetadataFinal,
    claims: list[ClaimFinal],
    chat_id: str,
    correlation_id: str | None = None,
) -> str:
    """Writes one paper's metadata and grounded claims to Postgres in one transaction.

    Inserts one document_extractors row (paper-level metadata as jsonb) and one
    paper_claims row per claim, all sharing a single extraction_run_id. On any
    failure the transaction rolls back automatically and the error is re-raised
    with file_id/chat_id context - nothing is silently swallowed.

    Returns the new document_extractor_id as a string.
    """
    pool = await _get_pool()

    document_extractor_id = uuid.uuid4()
    extraction_run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    fields_dict = metadata.model_dump(mode="json")
    fields_jsonb = Jsonb(fields_dict)

    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO document_extractors
                        (id, file_id, domain_id, fields, latest_run_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        document_extractor_id,
                        uuid.UUID(file_id),
                        uuid.UUID(RESEARCH_PAPER_DOMAIN_ID),
                        fields_jsonb,
                        extraction_run_id,
                        now,
                        now,
                    ),
                )

                for claim in claims:
                    evidence_spans_jsonb = Jsonb(
                        [span.model_dump(mode="json") for span in claim.evidence_spans]
                    )
                    await conn.execute(
                        """
                        INSERT INTO paper_claims
                            (id, document_extractor_id, extraction_run_id, claim_text_verbatim,
                             claim_summary, label, grounding_status, missing, reason,
                             evidence_spans, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            uuid.uuid4(),
                            document_extractor_id,
                            extraction_run_id,
                            claim.claim_text_verbatim,
                            claim.claim_summary,
                            claim.label.value,
                            claim.grounding_status.value,
                            claim.missing,
                            claim.reason,
                            evidence_spans_jsonb,
                            now,
                            now,
                        ),
                    )
    except Exception as exc:
        print(f"[write_extraction_result] chat_id={chat_id} file_id={file_id} failed: {exc!r}")
        raise RuntimeError(
            f"Failed to write extraction result for file_id={file_id} chat_id={chat_id}: {exc}"
        ) from exc

    _write_writer_log(
        chat_id=chat_id,
        correlation_id=correlation_id,
        file_id=file_id,
        document_extractor_id=document_extractor_id,
        extraction_run_id=extraction_run_id,
        claims_written_count=len(claims),
        fields_stored_keys=list(fields_dict.keys()),
        prompt_version=metadata.prompt_version,
        model_used=metadata.model_used,
    )

    return str(document_extractor_id)
