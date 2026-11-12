"""CLI 1c: which paper section each of the 13 dev extraction misses sits in. Nitin runs it; agents never run it and
never open its output. Read-only, zero LLM calls.

For each miss row it finds the row's sentence in the raw PDF text of its dev paper (exact match on normalised text
first, else the best rapidfuzz alignment, as in docs/evals/exp3_prechecks/check_e_raw.py) and puts the position in a
fixed bucket (eval/step1/sections.py has the method): abstract, introduction, body, conclusion, appendix, table or
figure caption, not found whole.

Only the 12 dev papers of eval.exp3_b4.DEV_PAPER_PDFS are opened, each behind its pinned sha256 check. The row
sentences come from docs/evals/dev_eval.json; exp3_targets.json is not read. The output holds no claim text and no
paper text other than heading lines (<= 80 chars).

Self-check (recorded 2026-10-17): P2-R3, P2-R4 and P11-R3 must land in appendix, else MISMATCH and exit 1.

Usage (from Prism.PythonService):
  uv run python -m eval.step1.section_of_misses [--out-dir PATH]
"""
import argparse
import sys
from pathlib import Path

from rapidfuzz import fuzz

from eval.exp3_b4 import _extract_pdf_text, _resolve_pdf
from eval.score_replay import (
    DEFAULT_DEV_EVAL_PATH,
    DEFAULT_MATCH_MAP_PATH,
    DEFAULT_RUN1_FIXTURE_DIR,
    resolve_adjudicated_rows,
)
from eval.step1 import common, sections
from extraction.grounding import (
    RAPIDFUZZ_THRESHOLD,
    normalize_for_match,
    normalize_with_map,
)

EXPECTED_ROWS = (
    "P7-R2", "P2-R1", "P1-R2", "P12-R1", "P2-R3", "P2-R4", "P9-R1", "P4-R3", "P3-R1", "P5-R3", "P8-R3", "P11-R1",
    "P11-R3",
)
APPENDIX_ROWS = ("P2-R3", "P2-R4", "P11-R3")        # recorded 2026-10-17: after the last References heading
CEILING_BUCKETS = ("abstract", "introduction", "conclusion")


def locate(claim_text: str, norm_paper: str, idx_map: tuple[int, ...]) -> tuple[bool, float, int | None]:
    """(found whole, score, raw offset of the match start). Whole = the normalised sentence is an exact substring of
    the normalised paper; otherwise the best partial_ratio alignment (offset None when there is none)."""
    claim_norm = normalize_for_match(claim_text)
    if not claim_norm or not norm_paper:
        return False, 0.0, None
    exact = norm_paper.find(claim_norm)
    if exact >= 0:
        return True, 100.0, idx_map[exact]
    alignment = fuzz.partial_ratio_alignment(claim_norm, norm_paper)
    if alignment is None:
        return False, 0.0, None
    if alignment.dest_end <= alignment.dest_start:
        return False, float(alignment.score), None
    return False, float(alignment.score), idx_map[alignment.dest_start]


def run(out_dir: Path) -> int:
    rows = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="R")
    misses = {r.row_id: r for r in rows if r.claim_index is None}
    if set(misses) != set(EXPECTED_ROWS):
        print(f"MISMATCH: the match map's extraction-miss R rows are {sorted(misses)}, expected {sorted(EXPECTED_ROWS)}")
        return 1

    texts: dict[str, str] = {}
    results: list[dict] = []
    for row_id in EXPECTED_ROWS:
        row = misses[row_id]
        paper_id = row.paper_id
        if paper_id not in texts:
            try:
                texts[paper_id] = _extract_pdf_text(_resolve_pdf(paper_id))
            except (ValueError, OSError) as exc:
                print(f"INVALID: {paper_id}: {exc}")
                return 1
        text = texts[paper_id]
        norm_paper, idx_map = normalize_with_map(text)
        if norm_paper != normalize_for_match(text):
            print(f"MISMATCH: normalize_with_map differs from normalize_for_match for {paper_id}; offsets unusable")
            return 1
        whole, score, offset = locate(row.expected_row.claim_text_verbatim, norm_paper, idx_map)
        placement = sections.assign_bucket(
            offset, len(text), sections.find_headings(text), sections.find_caption_starts(text),
            whole, score, RAPIDFUZZ_THRESHOLD,
        )
        results.append({
            "row_id": row_id, "paper_id": paper_id, "found_whole": whole, "score": round(score, 1),
            "position_pct": None if placement.position_pct is None else round(placement.position_pct, 1),
            "bucket": placement.bucket, "underneath": placement.underneath, "confidence": placement.confidence,
            "reasons": list(placement.reasons), "heading": placement.heading[:80],
        })

    lines = [
        "Section of the 13 dev extraction misses (raw PDF text; method fixed in eval/step1/sections.py)",
        f"{'row':<7} {'paper':<19} {'whole':<5} {'score':>5} {'pos%':>5} {'bucket':<24} {'underneath':<12} {'conf':<4} nearest heading before it",
    ]
    for r in results:
        pos = "-" if r["position_pct"] is None else f"{r['position_pct']:.1f}"
        lines.append(
            f"{r['row_id']:<7} {r['paper_id']:<19} {'yes' if r['found_whole'] else 'no':<5} {r['score']:>5.1f} {pos:>5} "
            f"{r['bucket']:<24} {r['underneath'] or '-'!s:<12} {r['confidence']:<4} {r['heading'] or '(none)'}"
        )
    totals = sections.bucket_totals([r["bucket"] for r in results])
    lines += ["", "Totals per bucket:"] + [f"  {b:<24} {n}" for b, n in totals.items()]
    ceiling = sum(totals[b] for b in CEILING_BUCKETS)
    under = sum(1 for r in results if r["underneath"] in CEILING_BUCKETS)
    lines.append(f"in abstract + introduction + conclusion: {ceiling} of {len(results)}")
    lines.append(f"(same count by the bucket underneath any caption override: {under} of {len(results)})")
    low = [r["row_id"] for r in results if r["confidence"] == "low"]
    lines.append(f"low confidence, to check against the PDF: {', '.join(low) if low else 'none'}")

    bad = [r["row_id"] for r in results if r["row_id"] in APPENDIX_ROWS and r["bucket"] != "appendix"]
    mismatches = [f"MISMATCH: {rid} should be appendix (recorded 2026-10-17) but is {next(r['bucket'] for r in results if r['row_id'] == rid)}" for rid in bad]
    lines += [""] + (mismatches or ["self-check OK: P2-R3, P2-R4 and P11-R3 are in appendix"])

    text_out = "\n".join(lines) + "\n"
    print(text_out)
    for path in common.write_outputs(out_dir, "1c_sections", text_out, {"rows": results, "totals": totals}):
        print(f"wrote {path}")
    return 1 if mismatches else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=common.DEFAULT_OUT_DIR)
    args = parser.parse_args()
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")     # a heading line may hold characters the console cannot show
    sys.exit(run(args.out_dir))


if __name__ == "__main__":
    main()
