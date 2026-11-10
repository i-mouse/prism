"""Postgres + PDF paper-text loader used by eval/replay_exp3.py,
eval/replay_clean.py and eval/replay_extract.py (via eval.replay_audit's
re-export).

Moved unchanged out of eval/replay_audit.py, which now reads paper text from
raw_text_cache and must not import memory_db or need Postgres. Paper text
cannot be read verbatim from storage (Prism never persists it) - it is
re-derived from the paper's local PDF and the PDF's sha256 is checked against
file_records.content_hash before use; a paper whose local PDF does not match
is skipped (that paper only, not the whole run).

memory_db and main are imported inside the function, so importing this module
needs neither.
"""
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PDF_DIR = REPO_ROOT / "docs" / "research_papers"

_RUN_SQL = """
SELECT fr.content_hash, fr.file_name
FROM   document_extractors de
JOIN   file_records fr ON fr.file_id = de.file_id
WHERE  de.id = %s;
"""


async def _hash_check_and_load_text(paper_id: str, fixture_header: dict) -> str | None:
    from memory_db import create_db_connection_pool

    pool = create_db_connection_pool()
    await pool.open()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(_RUN_SQL, (fixture_header["extraction_run_id"],))
                row = await cur.fetchone()
    finally:
        await pool.close()

    if row is None:
        print(f"[replay_audit] {paper_id}: SKIPPED - extraction run {fixture_header['extraction_run_id']} not found in DB")
        return None
    content_hash, file_name = row

    pdf_path = PDF_DIR / file_name
    if not pdf_path.exists():
        print(f"[replay_audit] {paper_id}: SKIPPED - no local PDF at {pdf_path}")
        return None
    actual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if actual_hash != content_hash:
        print(f"[replay_audit] {paper_id}: SKIPPED - sha256 mismatch (pdf={actual_hash[:12]} db={content_hash[:12]})")
        return None

    from main import extract_pdf_text_sync

    text, _ = extract_pdf_text_sync(str(pdf_path))
    return text
