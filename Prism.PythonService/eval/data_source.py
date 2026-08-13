"""Loads actual extraction claims for the eval harness.

Two sources produce the same list[ActualClaim] shape so the scorer never
needs to know which one it's looking at: read_from_db pulls the latest
extraction run for a filename from Postgres, read_from_fixture reads a
dumped JSON fixture with the same shape.
"""
import asyncio
import json
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from memory_db import create_db_connection_pool
from eval.types import ActualClaim, Match

_LATEST_CLAIMS_SQL = """
WITH latest AS (
    SELECT de.id AS de_id
    FROM   document_extractors de
    JOIN   file_records fr ON fr.file_id = de.file_id
    WHERE  fr.file_name = %s
    ORDER  BY de.created_at DESC
    LIMIT  1
)
SELECT pc.label, pc.claim_summary
FROM   paper_claims pc
JOIN   latest ON pc.document_extractor_id = latest.de_id
ORDER  BY pc.created_at ASC;
"""

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


async def read_from_db(filename: str) -> list[ActualClaim]:
    """Fetches actual claims for the latest extraction run of `filename`."""
    pool = await _get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_LATEST_CLAIMS_SQL, (filename,))
            rows = await cur.fetchall()

    return [
        ActualClaim(index=i, label=row[0], claim_summary=row[1]) for i, row in enumerate(rows)
    ]


def read_from_fixture(path: str | Path) -> list[ActualClaim]:
    """Reads actual claims from a fixture JSON file.

    Accepts both the current {"header": {...}, "claims": [...]} shape
    written by eval/dump_fixture.py and the legacy bare-array shape, kept
    for one release cycle so older committed fixtures keep working.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    claims = data["claims"] if isinstance(data, dict) else data
    return [ActualClaim.model_validate(item) for item in claims]


def get_fixture_header(path: str | Path) -> dict | None:
    """Returns a fixture's header dict, or None for legacy bare-array fixtures.

    Used by CI to check a fixture's prompt_hash isn't stale relative to the
    current prompt files.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("header") if isinstance(data, dict) else None


def read_matches_from_fixture(path: str | Path) -> list[Match]:
    """Reads the frozen matches from a fixture, written by eval/dump_fixture.py.

    Returns [] for the legacy bare-array shape and for fixtures dumped
    before matches were frozen (no "matches" key), so callers can treat
    both as "no frozen matches" and fall back accordingly.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    matches = data.get("matches")
    if matches is None:
        return []
    return [Match.model_validate(item) for item in matches]


if __name__ == "__main__":
    import asyncio
    import sys

    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()

    filename = sys.argv[1] if len(sys.argv) > 1 else "reflexion.pdf"
    claims = asyncio.run(read_from_db(filename))
    print(f"Fetched {len(claims)} claims for {filename}:")
    for c in claims:
        print(f"  [{c.index}] {c.label}")
