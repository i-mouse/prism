"""CLI: dumps the latest Postgres extraction run per paper to a JSON fixture.

Fixtures are what CI reads instead of the DB and instead of Gemini
(eval/matrix_runner.py --source fixture). Each fixture carries a header
(prompt_hash, matcher_fingerprint, model_name, matcher_model, generated_at,
paper_id, filename, extraction_run_id) so a freshness check can detect a
fixture that no longer matches the current extraction prompt OR the current
matcher configuration, plus the frozen claims and the frozen matcher output
(list[Match]) so CI never has to call Gemini to score.

Each claim also carries its frozen evidence_spans (source_text,
source_section, grounding_status, stance), so grounding changes can be
replayed against the exact quotes of a fixture's run even after the DB that
produced it is gone. Readers that only need claims ignore the key.

Run manually by developers after prompt iteration produces a
high-performing extraction state worth freezing for CI:
  uv run python -m eval.dump_fixture --paper all

To freeze one specific run with human-adjudicated matches instead (no
matcher call), pin the run and pass the match map:
  uv run python -m eval.dump_fixture --paper <paper> \
      --extraction-run-id <uuid> --match-map <match_map.json>
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from memory_db import create_db_connection_pool
from extraction.prompt_version import get_prompt_version
from eval.match_map import MatchMap, fingerprint_claim_text, load_match_map
from eval.matcher import match
from eval.matrix_loader import MatrixSpec, PaperSpec, load_matrix
from eval.types import ActualClaim, Match

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"

# No dedicated matcher prompt file exists yet - matcher.py's system prompt is
# a string constant (_SYSTEM_PROMPT). This path is where one would live if
# extracted later, so get_matcher_fingerprint() picks it up automatically
# without another freshness-check change.
MATCHER_PROMPT_PATH = Path(__file__).parent / "matcher_prompt.md"


def get_matcher_fingerprint() -> str:
    """Returns a 12-character SHA-256 hash of everything that can change the
    matcher's behavior independently of the extraction prompt: the model
    routing envs (LLM_EVAL_MATCHER_MODEL, LLM_EVAL_MATCHER_FALLBACK_MODEL)
    plus MATCHER_PROMPT_PATH's bytes, if that file exists on disk.

    Written into every fixture header alongside prompt_hash so
    check_fixture_freshness can catch a fixture whose matches were frozen
    under different matcher routing (model swap, added fallback) even when
    the extraction prompt itself is unchanged - prompt_hash alone is blind
    to this because the matcher is a separate LLM call from extraction.
    """
    primary = os.getenv("LLM_EVAL_MATCHER_MODEL", "")
    fallback = os.getenv("LLM_EVAL_MATCHER_FALLBACK_MODEL", "")
    combined = primary.encode("utf-8") + b"\x00" + fallback.encode("utf-8")

    if MATCHER_PROMPT_PATH.exists():
        combined += MATCHER_PROMPT_PATH.read_bytes()

    return hashlib.sha256(combined).hexdigest()[:12]

_LATEST_EXTRACTION_ID_SQL = """
SELECT de.id
FROM   document_extractors de
JOIN   file_records fr ON fr.file_id = de.file_id
WHERE  fr.file_name = %s
ORDER  BY de.created_at DESC
LIMIT  1;
"""

_CLAIMS_FOR_EXTRACTION_SQL = """
SELECT pc.label, pc.claim_summary, pc.missing, pc.grounding_status, pc.claim_text_verbatim,
       pc.evidence_spans
FROM   paper_claims pc
WHERE  pc.document_extractor_id = %s
ORDER  BY pc.position ASC;
"""

# Every claim of a run is written in one transaction and shares one
# created_at, so position is the only stable order.
_CLAIMS_FOR_RUN_SQL = """
SELECT pc.label, pc.claim_summary, pc.missing, pc.grounding_status, pc.claim_text_verbatim,
       pc.evidence_spans
FROM   paper_claims pc
JOIN   document_extractors de ON de.id = pc.document_extractor_id
JOIN   file_records fr ON fr.file_id = de.file_id
WHERE  pc.extraction_run_id = %s
AND    fr.file_name = %s
ORDER  BY pc.position ASC;
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

    return str(extraction_id), claims_from_rows(claim_rows)


async def _fetch_extraction_run(filename: str, extraction_run_id: str) -> tuple[str, list[dict]] | None:
    """Returns (extraction_run_id, claims) for one pinned run of `filename`.

    Returns None if the run has no claims or does not belong to `filename`.
    """
    pool = await _get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_CLAIMS_FOR_RUN_SQL, (extraction_run_id, filename))
            claim_rows = await cur.fetchall()

    if not claim_rows:
        return None

    return extraction_run_id, claims_from_rows(claim_rows)


def matches_from_match_map(paper: PaperSpec, claims: list[dict], match_map: MatchMap) -> list[Match]:
    """Builds the frozen matches from human-adjudicated fingerprints - no
    matcher call. Raises ValueError if a row is unadjudicated or its
    fingerprint does not resolve to exactly one claim."""
    index_by_fingerprint: dict[str, list[int]] = {}
    for claim in claims:
        fingerprint = fingerprint_claim_text(claim.get("claim_text_verbatim") or "")
        index_by_fingerprint.setdefault(fingerprint, []).append(claim["index"])

    matches = []
    for row in paper.expected_rows:
        entry = match_map.rows[row.id]
        if entry.confirmed_no_match:
            matches.append(Match(expected_id=row.id, actual_index=None))
        elif entry.claim_fingerprint is not None:
            indexes = index_by_fingerprint.get(entry.claim_fingerprint, [])
            if len(indexes) != 1:
                raise ValueError(
                    f"{row.id}: fingerprint {entry.claim_fingerprint[:12]} resolves to {len(indexes)} claims, expected 1"
                )
            matches.append(Match(expected_id=row.id, actual_index=indexes[0]))
        else:
            raise ValueError(f"{row.id}: no claim_fingerprint or confirmed_no_match in the match map")
    return matches


FROZEN_SPAN_FIELDS = ("source_text", "source_section", "grounding_status", "stance")


def claims_from_rows(claim_rows: list[tuple]) -> list[dict]:
    """Maps _CLAIMS_FOR_EXTRACTION_SQL rows to fixture claim dicts, freezing
    FROZEN_SPAN_FIELDS of each evidence span (missing fields become None)."""
    return [
        {
            "index": i,
            "label": label,
            "claim_summary": claim_summary,
            "missing": missing,
            "grounding_status": grounding_status,
            "claim_text_verbatim": claim_text_verbatim,
            "evidence_spans": [
                {field: span.get(field) for field in FROZEN_SPAN_FIELDS}
                for span in (evidence_spans or [])
            ],
        }
        for i, (label, claim_summary, missing, grounding_status, claim_text_verbatim, evidence_spans)
        in enumerate(claim_rows)
    ]


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
    matcher_fingerprint: str,
    generated_at: datetime,
) -> dict:
    return {
        "header": {
            "prompt_hash": prompt_hash,
            "matcher_fingerprint": matcher_fingerprint,
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
    extraction_run_id: str | None = None,
    match_map: MatchMap | None = None,
) -> bool:
    """Returns True if the paper was (or, for --dry-run, would be) dumped.

    extraction_run_id pins the run instead of taking the latest one;
    match_map freezes human-adjudicated matches instead of calling the matcher.
    """
    if extraction_run_id is not None:
        result = await _fetch_extraction_run(paper.filename, extraction_run_id)
    else:
        result = await _fetch_latest_extraction(paper.filename)
    if result is None:
        print(f"SKIPPED (no DB data for {paper.filename})")
        return False

    extraction_run_id, claims = result

    if match_map is not None:
        try:
            matches = matches_from_match_map(paper, claims, match_map)
        except ValueError as exc:
            print(f"SKIPPED (match map does not resolve for {paper.filename}): {exc}")
            return False
        used_matcher_model = f"match_map:{match_map.metadata.prompt_hash}"
    else:
        actual_claims = [ActualClaim(**claim) for claim in claims]
        try:
            matches, used_matcher_model = await match(paper.paper_id, paper.expected_rows, actual_claims)
        except Exception as exc:
            print(f"SKIPPED (matcher failed for {paper.filename}): {exc}")
            return False

    match_dicts = [m.model_dump() for m in matches]
    fixture = build_fixture(
        paper,
        extraction_run_id,
        claims,
        match_dicts,
        model_name,
        used_matcher_model,
        prompt_hash,
        get_matcher_fingerprint(),
        datetime.now(timezone.utc),
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
    parser.add_argument("--extraction-run-id", help="pin this extraction run instead of the latest (one paper only)")
    parser.add_argument(
        "--match-map", type=Path, help="freeze matches from this human match map instead of calling the matcher"
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    matrix_spec: MatrixSpec = load_matrix(args.matrix_path)

    papers = [p for p in matrix_spec.papers if _paper_matches(p, args.paper)]
    if not papers:
        print(f"No papers match --paper {args.paper!r}", file=sys.stderr)
        return 1
    if args.extraction_run_id and len(papers) != 1:
        print(f"--extraction-run-id needs --paper to match exactly one paper, got {len(papers)}", file=sys.stderr)
        return 1

    match_map = None
    if args.match_map:
        golden_ids = {row.id for paper in matrix_spec.papers for row in paper.expected_rows}
        match_map = load_match_map(args.match_map, golden_ids)

    prompt_hash = get_prompt_version()
    model_name = os.getenv("LLM_EXTRACTION_MODEL", "")

    all_dumped = True
    for paper in papers:
        dumped = await _dump_paper(
            paper, args.fixture_dir, args.dry_run, prompt_hash, model_name, args.extraction_run_id, match_map
        )
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
