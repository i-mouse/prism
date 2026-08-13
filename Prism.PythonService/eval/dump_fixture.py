"""CLI: dumps the latest Postgres extraction run per paper to a JSON fixture.

Fixtures are what CI reads instead of the DB and instead of Gemini
(eval/matrix_runner.py --source fixture). Each fixture carries a header
(prompt_hash, model_name, matcher_model, generated_at, paper_id, filename,
extraction_run_id) so a freshness check can detect a fixture that no
longer matches the current prompt, plus the frozen claims and the frozen
matcher output (list[Match]) so CI never has to call Gemini to score.

Run manually by developers after prompt iteration produces a
high-performing extraction state worth freezing for CI:
  uv run python -m eval.dump_fixture --paper all
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from memory_db import create_db_connection_pool
from extraction.prompt_version import get_prompt_version
from eval.matcher import DEFAULT_MODEL, match
from eval.matrix_loader import MatrixSpec, PaperSpec, load_matrix
from eval.types import ActualClaim

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"

_LATEST_EXTRACTION_ID_SQL = """
SELECT de.id
FROM   document_extractors de
JOIN   file_records fr ON fr.file_id = de.file_id
WHERE  fr.file_name = %s
ORDER  BY de.created_at DESC
LIMIT  1;
"""

_CLAIMS_FOR_EXTRACTION_SQL = """
SELECT pc.label, pc.claim_summary
FROM   paper_claims pc
WHERE  pc.document_extractor_id = %s
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


async def _fetch_latest_extraction(filename: str) -> tuple[str, list[dict]] | None:
    """Returns (extraction_run_id, claims) for the latest run of `filename`.

    Returns None if there is no extraction row for the filename, or the
    row exists but has zero claims.
    """
    pool = await _get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_LATEST_EXTRACTION_ID_SQL, (filename,))
            row = await cur.fetchone()
            if row is None:
                return None
            extraction_id = row[0]

            await cur.execute(_CLAIMS_FOR_EXTRACTION_SQL, (extraction_id,))
            claim_rows = await cur.fetchall()

    if not claim_rows:
        return None

    claims = [
        {"index": i, "label": label, "claim_summary": claim_summary}
        for i, (label, claim_summary) in enumerate(claim_rows)
    ]
    return str(extraction_id), claims


def _paper_matches(paper: PaperSpec, name: str) -> bool:
    if name == "all":
        return True
    needle = name.lower()
    return needle in paper.paper_id.lower() or needle in paper.filename.lower()


def build_fixture(
    paper: PaperSpec,
    extraction_run_id: str,
    claims: list[dict],
    matches: list[dict],
    model_name: str,
    matcher_model: str,
    prompt_hash: str,
    generated_at: datetime,
) -> dict:
    return {
        "header": {
            "prompt_hash": prompt_hash,
            "model_name": model_name,
            "matcher_model": matcher_model,
            "generated_at": generated_at.isoformat(),
            "paper_id": paper.paper_id,
            "filename": paper.filename,
            "extraction_run_id": extraction_run_id,
        },
        "claims": claims,
        "matches": matches,
    }


async def _dump_paper(
    paper: PaperSpec,
    fixture_dir: Path,
    dry_run: bool,
    prompt_hash: str,
    model_name: str,
    matcher_model: str,
) -> bool:
    """Returns True if the paper was (or, for --dry-run, would be) dumped."""
    result = await _fetch_latest_extraction(paper.filename)
    if result is None:
        print(f"SKIPPED (no DB data for {paper.filename})")
        return False

    extraction_run_id, claims = result
    actual_claims = [ActualClaim(**claim) for claim in claims]

    try:
        matches = await match(paper.paper_id, paper.expected_rows, actual_claims)
    except Exception as exc:
        print(f"SKIPPED (matcher failed for {paper.filename}): {exc}")
        return False

    match_dicts = [m.model_dump() for m in matches]
    fixture = build_fixture(
        paper, extraction_run_id, claims, match_dicts, model_name, matcher_model, prompt_hash, datetime.now(timezone.utc)
    )
    fixture_path = fixture_dir / f"{paper.paper_id}.json"

    if dry_run:
        print(
            f"[dry-run] would write {paper.filename} -> {fixture_path} "
            f"({len(claims)} claims, {len(match_dicts)} matches, prompt_hash={prompt_hash[:8]})"
        )
        print(json.dumps(fixture, indent=2))
        return True

    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(
        f"wrote {paper.filename} -> {fixture_path} "
        f"({len(claims)} claims, {len(match_dicts)} matches, prompt_hash={prompt_hash[:8]})"
    )
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dump the latest Postgres extraction run per paper to a JSON fixture")
    parser.add_argument("--paper", default="all", help="paper_id/filename substring, or 'all'")
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--dry-run", action="store_true", help="print what would be written, do not touch disk")
    return parser


async def _run(args: argparse.Namespace) -> int:
    matrix_spec: MatrixSpec = load_matrix(args.matrix_path)

    papers = [p for p in matrix_spec.papers if _paper_matches(p, args.paper)]
    if not papers:
        print(f"No papers match --paper {args.paper!r}", file=sys.stderr)
        return 1

    prompt_hash = get_prompt_version()
    model_name = os.getenv("LLM_EXTRACTION_MODEL", "")
    matcher_model = os.getenv("LLM_AUDIT_MODEL", DEFAULT_MODEL)

    all_dumped = True
    for paper in papers:
        dumped = await _dump_paper(paper, args.fixture_dir, args.dry_run, prompt_hash, model_name, matcher_model)
        all_dumped = all_dumped and dumped

    return 0 if all_dumped else 1


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()
    main()
