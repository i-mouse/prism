"""CLI: writes the paper text of the golden papers into the golden text folder
(scratch/auditor_rd/golden_text_cache/), for eval/replay_audit.py --set golden. Zero LLM calls.

For each paper of the golden matrix (docs/evals/matrix_eval.json, through eval.matrix_loader - never a folder
listing), the text is made the way the product makes it, from the PDF the frozen extraction run used:
  1. the paper's fixture header gives extraction_run_id;
  2. eval.replay_stage1._load_run gives that run's content_hash and file_name (from scratch/stage1_replay if
     already cached there, else from Postgres);
  3. eval.replay_stage1._resolve_pdf finds a local PDF whose sha256 equals content_hash and REFUSES (no text is
     written) when none matches;
  4. main.extract_pdf_text_sync - the product's own function - extracts the text.
Nothing is written unless every paper succeeded. A text file that already exists is never overwritten, and a
text that contains a carriage return is refused, because the replay reads the file in text mode and would
change it. Bytes are written as UTF-8 exactly as extracted.

The text folder is under scratch/, which the repo-root .gitignore excludes (the rule `scratch/`, the same one
that covers scratch/auditor_rd/raw_text_cache).

Check afterwards, as a separate step, with the existing Stage-1 check on the frozen spans:
  uv run python -m eval.replay_stage1
That check re-extracts from the same sha-verified PDF with the same function; it does not read this folder.

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


class GoldenTextError(Exception):
    """The golden text cannot be built (nothing was written)."""


async def build(
    matrix_path: Path, fixture_dir: Path, text_dir: Path, *, load_run, resolve_pdf, extract_text, log=print,
) -> list[Path]:
    """Returns the files written. load_run(run_id, refresh) -> {"content_hash", "file_name"} (async),
    resolve_pdf(file_name, sha256) -> Path (SystemExit when no local PDF matches), extract_text(pdf_path_str)
    -> (text, anything) are injected so tests need no Postgres, PDF or main.py."""
    matrix = load_matrix(matrix_path)

    plan: list[tuple[str, Path, str]] = []
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
        plan.append((paper.paper_id, target, run_id))

    texts: list[tuple[Path, str]] = []
    for paper_id, target, run_id in plan:
        run = await load_run(run_id, False)
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
        log(f"[build_golden_text_cache] {paper_id}: pdf={Path(pdf_path).name} sha256={run['content_hash'][:12]}, "
            f"{len(text)} chars")
        texts.append((target, text))

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
            load_run=load_run, resolve_pdf=resolve_pdf, extract_text=extract_text,
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
