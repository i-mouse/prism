"""CLI: table-finding check before step 4 (decisions.md "Pre-registration: table-finding check before step 4 (code
only, INR 0) - 2026-11-14" and its "Reading notes"). Nitin runs it; agents never run it and read only its output
files. Zero LLM calls, no network.

Order of work:
  1. Preflight, before any PDF is read: the T1 pins file and the 6 reference tables load, each caption_number equals
     N, and the breaking pin ids of each table are exactly the ones the reading is built on. Any mismatch prints the
     reason and exits 2 without opening a PDF. --preflight-only stops here and prints "PREFLIGHT OK".
  2. Paper text for the 12 dev papers through eval.exp3_b4 (_resolve_pdf with the pinned sha256, then
     _extract_pdf_text: the product extract loop, as in step 1c). main.py is not imported. exp3_b4 is imported only
     after preflight passes (its import chain reads .env settings, as in 1c).
  3. Score the 6 tables, build the all-tables view, write <out-dir>/4_tablefind.md and 4_tablefind.json.

Output holds ids, counts, ints, floats, bools and the verdict only: never paper text, cell values or labels.
Console shows only the verdict and per-row ready y/n.

Exit codes: 0 = finished (PASS or FAIL is a recorded result, not an error); 1 = a PDF could not be read; 2 = preflight
failed.

Usage (from Prism.PythonService):
  .venv\\Scripts\\python.exe -X utf8 -m eval.step4.tablefind_run --out-dir ../docs/evals/step4_tablefind_2026-11-14
  .venv\\Scripts\\python.exe -X utf8 -m eval.step4.tablefind_run --out-dir <dir> --preflight-only
"""
import argparse
import json
import sys
from pathlib import Path

from eval.step4 import tablefind

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AUD_DIR = REPO_ROOT / "docs" / "evals" / "auditor_rd"
PINS_PATH = AUD_DIR / "t1_pins_2026-10-28.json"
REFS_DIR = AUD_DIR / "t2r_refs"
DEV_KEY_PREFIX = "arxiv-"
OUT_STEM = "4_tablefind"


def _load_json(path: Path, problems: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"{path.name}: cannot be read ({type(exc).__name__})")
        return None
    if not isinstance(data, dict):
        problems.append(f"{path.name}: not a JSON object")
        return None
    return data


def preflight() -> tuple[dict | None, list[str]]:
    """(loaded inputs, problems). Reads only the pins file and the 6 reference tables; no PDF."""
    problems: list[str] = []
    pins_doc = _load_json(PINS_PATH, problems)
    if pins_doc is None:
        return None, problems

    infos = {t.get("table_id"): t for t in pins_doc.get("tables", [])}
    papers: dict[str, str] = {}
    refs: dict[str, dict] = {}
    pins_by_table: dict[str, list[dict]] = {}
    for table_id, number in tablefind.TABLE_NUMBERS.items():
        info = infos.get(table_id)
        if info is None:
            problems.append(f"{table_id}: not in the pins file's tables")
            continue
        if info.get("caption_number") != number:
            problems.append(f"{table_id}: pins file caption_number {info.get('caption_number')!r}, expected {number}")
        paper_id = str(info.get("paper_id"))
        papers[table_id] = paper_id

        ref = _load_json(REFS_DIR / f"{paper_id}_T{number}.json", problems)
        if ref is not None:
            if ref.get("caption_number") != number:
                problems.append(f"{table_id}: reference caption_number {ref.get('caption_number')!r}, expected {number}")
            refs[table_id] = ref

        pins = [p for p in pins_doc.get("pins", []) if p.get("table_id") == table_id]
        pins_by_table[table_id] = pins
        breaking = {str(p.get("id")) for p in pins if p.get("breaking")}
        expected = tablefind.EXPECTED_BREAKING[table_id]
        if breaking != expected:
            problems.append(
                f"{table_id}: breaking pin ids {sorted(breaking)} differ from the expected {sorted(expected)}"
            )
    if problems:
        return None, problems
    return {"papers": papers, "refs": refs, "pins": pins_by_table}, problems


def _read_dev_texts(wanted_papers: set[str]) -> tuple[dict[str, str] | None, str]:
    """{paper id: text} for the 12 dev papers, or (None, reason). Imported here, after preflight."""
    from eval.exp3_b4 import DEV_PAPERS, _extract_pdf_text, _resolve_pdf

    dev_ids = [key[len(DEV_KEY_PREFIX):] for key in DEV_PAPERS if key.startswith(DEV_KEY_PREFIX)]
    unknown = sorted(wanted_papers - set(dev_ids))
    if unknown:
        return None, f"target papers {unknown} are not among the dev papers"
    texts: dict[str, str] = {}
    for paper_id in dev_ids:
        try:
            texts[paper_id] = _extract_pdf_text(_resolve_pdf(DEV_KEY_PREFIX + paper_id))
        except ValueError as exc:       # not a listed dev paper, or sha256 mismatch: message holds paths and hashes
            return None, f"{paper_id}: {exc}"
        except Exception as exc:        # noqa: BLE001 - unreadable or password-protected PDF; class name only
            return None, f"{paper_id}: {type(exc).__name__}"
    return texts, ""


def run(out_dir: Path, preflight_only: bool) -> int:
    loaded, problems = preflight()
    if loaded is None:
        for problem in problems:
            print(f"PREFLIGHT FAILED: {problem}")
        return 2
    if preflight_only:
        print("PREFLIGHT OK")
        return 0

    papers: dict[str, str] = loaded["papers"]
    texts, reason = _read_dev_texts(set(papers.values()))
    if texts is None:
        print(f"INVALID: {reason}")
        return 1

    scored = {
        table_id: tablefind.score_table(
            text=texts[papers[table_id]], n=number, ref=loaded["refs"][table_id], pins=loaded["pins"][table_id],
        )
        for table_id, number in tablefind.TABLE_NUMBERS.items()
    }
    all_tables = {paper_id: tablefind.all_tables_view(text) for paper_id, text in sorted(texts.items())}

    payload = tablefind.build_payload(scored=scored, papers=papers, all_tables=all_tables)
    tablefind.check_payload(payload)
    md_text = tablefind.render_md(payload)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{OUT_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n",
    )
    (out_dir / f"{OUT_STEM}.md").write_text(md_text, encoding="utf-8", newline="\n")

    print(f"VERDICT: {payload['verdict']} ({payload['rows_ready_count']} of {payload['rows_total']} rows ready)")
    for row, ready in payload["rows_ready"].items():
        print(f"{row} ready: {'yes' if ready else 'no'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    sys.exit(run(args.out_dir, args.preflight_only))


if __name__ == "__main__":
    main()
