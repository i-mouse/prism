"""CLI: writes the paper text of the golden papers into the golden text folder
(scratch/auditor_rd/golden_text_cache/), for eval/replay_audit.py --set golden. Zero LLM calls.

For each paper of the golden matrix (docs/evals/matrix_eval.json, through eval.matrix_loader - never a folder
listing), the text is made the way the product makes it, from the PDF the frozen extraction run used:
  1. the paper's fixture header gives extraction_run_id;
  2. eval.replay_stage1._load_run gives that run's content_hash and file_name (from scratch/stage1_replay if
     already cached there, else from Postgres), treating the id as a document_extractors.id. A fixture frozen
     with --extraction-run-id carries a RUN id instead, so on _load_run's "not found in DB" (and only then) the
     id is looked up as document_extractors.latest_run_id, then as paper_claims.extraction_run_id, and followed
     through file_id to file_records (file_name, content_hash). Found nowhere: STOP for all papers;
  3. eval.replay_stage1._resolve_pdf finds a local PDF whose sha256 equals content_hash and REFUSES (no text is
     written) when none matches (byte-identical copies are one match);
  4. main.extract_pdf_text_sync - the product's own function - extracts the text;
  5. a two-way Stage-1 guard on the fixture's frozen evidence spans, using production's own scoring function and
     threshold (extraction.grounding._stage1_score, RAPIDFUZZ_THRESHOLD): a span stored as a Stage-1 failure
     (status Fail, no stance) must score below the threshold on this text, every other span at or above it.
     Tried with normalize=False, and only if that leaves a mismatch with normalize=True; the paper passes only if
     ONE setting reproduces every span (never mixed per span), and the setting is reported. A fixture with no
     usable frozen span cannot be checked and stops the run. Every mismatch of every paper is listed.
Nothing is written unless every paper succeeded and passed the guard. A text file that already exists is never
overwritten, and a text that contains a carriage return is refused, because the replay reads the file in text
mode and would change it. Bytes are written as UTF-8 exactly as extracted.

The text folder is under scratch/, which the repo-root .gitignore excludes (the rule `scratch/`, the same one
that covers scratch/auditor_rd/raw_text_cache).

The guard in step 5 runs on the text that is written, from the fixtures alone (no Postgres). It shows the text is
consistent with every frozen Stage-1 verdict; the proof that it is the same file is the sha256 match of step 3.
eval.replay_stage1 is unchanged and still needs document_extractors.id rows.

Usage (from Prism.PythonService):
  uv run python -m eval.build_golden_text_cache
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from eval.matrix_loader import load_matrix
from eval.replay_audit import GOLDEN_FIXTURE_DIR, GOLDEN_MATRIX_PATH, GOLDEN_TEXT_CACHE_DIR, _cache_file_name
from extraction import grounding

# replay_stage1._fetch_run_from_db raises SystemExit("extraction run <id> not found in DB") when the header id is
# not a document_extractors.id. Only that message sends the builder on to lookup_run_by_run_id.
NOT_FOUND_MARKER = "not found in DB"

# A fixture frozen with --extraction-run-id carries a run id (the value of document_extractors.latest_run_id and
# paper_claims.extraction_run_id), not a document_extractors.id (eval/dump_fixture.py). Looked up in this order.
RUN_ID_LOOKUPS = (
    (
        "document_extractors.latest_run_id",
        """
        SELECT fr.content_hash, fr.file_name
        FROM   document_extractors de
        JOIN   file_records fr ON fr.file_id = de.file_id
        WHERE  de.latest_run_id = %s;
        """,
    ),
    (
        "paper_claims.extraction_run_id",
        """
        SELECT fr.content_hash, fr.file_name
        FROM   paper_claims pc
        JOIN   document_extractors de ON de.id = pc.document_extractor_id
        JOIN   file_records fr ON fr.file_id = de.file_id
        WHERE  pc.extraction_run_id = %s;
        """,
    ),
)


class GoldenTextError(Exception):
    """The golden text cannot be built (nothing was written)."""


async def lookup_run_by_run_id(run_id: str, *, pool_factory=None) -> dict | None:
    """Resolves a fixture header id that is a run id: document_extractors.latest_run_id first, then
    paper_claims.extraction_run_id, each through file_id to file_records. Returns
    {"content_hash", "file_name", "found_by"}, or None when neither finds it. Raises GoldenTextError when one
    lookup finds more than one distinct file, or a file with no content_hash. Read-only."""
    if pool_factory is None:
        from memory_db import create_db_connection_pool as pool_factory
    pool = pool_factory()
    await pool.open()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                for found_by, sql in RUN_ID_LOOKUPS:
                    await cur.execute(sql, (run_id,))
                    files = sorted({(row[0], row[1]) for row in await cur.fetchall()}, key=str)
                    if len(files) > 1:
                        raise GoldenTextError(f"run {run_id} resolves via {found_by} to {len(files)} different files: {files}")
                    if files:
                        content_hash, file_name = files[0]
                        if not content_hash:
                            raise GoldenTextError(f"run {run_id} resolves via {found_by} to {file_name!r}, which has no content_hash")
                        return {"content_hash": content_hash, "file_name": file_name, "found_by": found_by}
    finally:
        await pool.close()
    return None


# --- the offline Stage-1 guard ----------------------------------------------------------------------

def _collect_spans(claims, problems: list[str]) -> list[tuple]:
    """(claim index, span index, quote, stored status, stored stance) for every frozen evidence span. A span
    without a quote or a stored status is a problem (it cannot be checked), and so is a fixture with no span."""
    spans = []
    for claim_index, claim in enumerate(claims if isinstance(claims, list) else []):
        for span_index, span in enumerate((claim.get("evidence_spans") if isinstance(claim, dict) else None) or []):
            quote, status = span.get("source_text"), span.get("grounding_status")
            if not isinstance(quote, str) or not quote.strip() or status is None:
                problems.append(f"claim {claim_index} span {span_index}: no source_text or no frozen grounding_status")
                continue
            spans.append((claim_index, span_index, quote, status, span.get("stance")))
    if not spans and not problems:
        problems.append("the fixture has no frozen evidence spans, so there is nothing to check the text against")
    return spans


def _stage1_mismatches(spans: list[tuple], text: str, normalize: bool) -> list[str]:
    """The spans whose Stage-1 verdict on `text` differs from the stored one, in either direction. Production's
    own function and threshold: grounding._passes_rapidfuzz is _stage1_score(quote, paper, normalize) >=
    RAPIDFUZZ_THRESHOLD. A stored Fail with no stance is a span that failed Stage 1 originally."""
    found = []
    for claim_index, span_index, quote, status, stance in spans:
        score = grounding._stage1_score(quote, text, normalize)
        passes = score >= grounding.RAPIDFUZZ_THRESHOLD
        failed_originally = status == "Fail" and stance is None
        if passes == failed_originally:
            found.append(
                f"claim {claim_index} span {span_index}: score {score:.1f} "
                f"{'>=' if passes else '<'} {grounding.RAPIDFUZZ_THRESHOLD}, but the frozen span "
                f"{'failed' if failed_originally else 'passed'} Stage 1 (status {status}, stance {stance})"
            )
    return found


def check_stage1(claims, text: str) -> dict:
    """The two-way guard on one paper: every frozen span's Stage-1 verdict must be reproduced by `text`.
    normalize=False first; only if that leaves a mismatch, normalize=True. The paper passes only if ONE setting
    reproduces every span (never mixed per span). Returns {"spans": n, "setting": "normalize=False" |
    "normalize=True" | None, "problems": [...], "mismatches": {setting: [...]}} - a problem is a fixture that
    cannot be checked at all (nothing is tried then)."""
    problems: list[str] = []
    spans = _collect_spans(claims, problems)
    result = {"spans": len(spans), "setting": None, "problems": problems, "mismatches": {}}
    if problems:
        return result
    for normalize in (False, True):
        setting = f"normalize={normalize}"
        mismatches = _stage1_mismatches(spans, text, normalize)
        result["mismatches"][setting] = mismatches
        if not mismatches:
            result["setting"] = setting
            return result
    return result


async def _resolve_run(paper_id: str, run_id: str, load_run, lookup_run) -> tuple[dict, str]:
    """(run with content_hash and file_name, how it was found). The existing path first: load_run(run_id) treats
    the header id as a document_extractors.id. Only its "not found in DB" SystemExit - and only when a
    lookup_run is given - goes on to lookup_run (latest_run_id, then paper_claims.extraction_run_id). Any other
    SystemExit or error is raised as it was. Found nowhere: GoldenTextError."""
    try:
        return await load_run(run_id, False), "document_extractors.id"
    except SystemExit as exc:
        if lookup_run is None or NOT_FOUND_MARKER not in str(exc):
            raise
    run = await lookup_run(run_id)
    if run is None:
        raise GoldenTextError(
            f"{paper_id}: run {run_id} is not a document_extractors.id, a document_extractors.latest_run_id or a "
            f"paper_claims.extraction_run_id; nothing was written for any paper"
        )
    return run, run["found_by"]


async def build(
    matrix_path: Path, fixture_dir: Path, text_dir: Path, *, load_run, resolve_pdf, extract_text, lookup_run=None,
    log=print,
) -> list[Path]:
    """Returns the files written, or raises GoldenTextError with nothing written. load_run(run_id, refresh) ->
    {"content_hash", "file_name"} (async), resolve_pdf(file_name, sha256) -> Path (SystemExit when no local PDF
    matches), extract_text(pdf_path_str) -> (text, anything) and lookup_run(run_id) -> {"content_hash",
    "file_name", "found_by"} | None (async; lookup_run_by_run_id) are injected so tests need no Postgres, PDF or
    main.py. Every paper must resolve, extract and pass the Stage-1 guard before the first file is written."""
    matrix = load_matrix(matrix_path)

    plan: list[tuple[str, Path, str, list]] = []
    for paper in matrix.papers:
        target = Path(text_dir) / _cache_file_name(paper.paper_id)
        if target.exists():
            raise GoldenTextError(f"{target} already exists, refusing to overwrite it")
        fixture_path = Path(fixture_dir) / f"{paper.paper_id}.json"
        if not fixture_path.is_file():
            raise GoldenTextError(f"{paper.paper_id}: no fixture file {fixture_path}")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        header = fixture.get("header") if isinstance(fixture, dict) else None
        run_id = header.get("extraction_run_id") if isinstance(header, dict) else None
        if not run_id:
            raise GoldenTextError(f"{paper.paper_id}: the fixture header has no extraction_run_id")
        plan.append((paper.paper_id, target, run_id, fixture.get("claims")))

    texts: list[tuple[Path, str]] = []
    failures: list[str] = []
    for paper_id, target, run_id, claims in plan:
        run, found_by = await _resolve_run(paper_id, run_id, load_run, lookup_run)
        try:
            pdf_path = resolve_pdf(run["file_name"], run["content_hash"])
        except SystemExit as exc:  # replay_stage1._resolve_pdf: no local PDF has the run's sha256
            raise GoldenTextError(f"{paper_id}: {exc}") from exc
        text, _ = extract_text(str(pdf_path))
        if not text or not text.strip():
            raise GoldenTextError(f"{paper_id}: the extracted text of {Path(pdf_path).name} is empty")
        if "\r" in text:
            raise GoldenTextError(
                f"{paper_id}: the extracted text contains carriage returns; the replay's text-mode read would change it"
            )
        log(f"[build_golden_text_cache] {paper_id}: run {run_id} found via {found_by}; pdf={Path(pdf_path).name} "
            f"sha256={run['content_hash'][:12]}, {len(text)} chars")

        guard = check_stage1(claims, text)
        if guard["setting"] is not None:
            log(f"[build_golden_text_cache] {paper_id}: Stage-1 guard passed with {guard['setting']} "
                f"({guard['spans']} frozen spans reproduced, both directions)")
        else:
            failures.append(f"{paper_id}: Stage-1 guard FAILED ({guard['spans']} frozen spans)")
            failures.extend(f"  fixture: {problem}" for problem in guard["problems"])
            for setting, mismatches in guard["mismatches"].items():
                failures.append(f"  {setting}: {len(mismatches)} mismatching spans")
                failures.extend(f"    {line}" for line in mismatches)
        texts.append((target, text))

    if failures:
        raise GoldenTextError(
            "the extracted text does not reproduce the frozen Stage-1 verdicts; nothing was written for any paper:\n"
            + "\n".join(failures)
        )

    Path(text_dir).mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for target, text in texts:
        with target.open("xb") as handle:  # "x": never overwrites
            handle.write(text.encode("utf-8"))
        written.append(target)
        log(f"[build_golden_text_cache] wrote {target}")
    return written


def _default_dependencies():
    """The real Postgres/PDF/product functions. main.py runs init_telemetry at import: keep it on the
    no-exporter path first (as replay_stage1 does)."""
    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)
    from eval import replay_stage1

    def extract_text(pdf_path: str):
        from main import extract_pdf_text_sync
        return extract_pdf_text_sync(pdf_path)

    return replay_stage1._load_run, replay_stage1._resolve_pdf, extract_text


async def _run(args: argparse.Namespace) -> int:
    load_run, resolve_pdf, extract_text = _default_dependencies()
    try:
        written = await build(
            args.matrix_path, args.fixture_dir, args.text_dir,
            load_run=load_run, resolve_pdf=resolve_pdf, extract_text=extract_text, lookup_run=lookup_run_by_run_id,
        )
    except (GoldenTextError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"\nwrote {len(written)} golden text files to {args.text_dir}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix-path", type=Path, default=GOLDEN_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=GOLDEN_FIXTURE_DIR)
    parser.add_argument("--text-dir", type=Path, default=GOLDEN_TEXT_CACHE_DIR)
    return parser


def main() -> None:
    sys.exit(asyncio.run(_run(_build_parser().parse_args())))


if __name__ == "__main__":
    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()
    main()
