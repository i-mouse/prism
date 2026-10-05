"""CLI: replays grounding Stage 1 (RapidFuzz) over stored evidence spans with
normalize_for_match off vs on. No LLM calls.

Extraction is held fixed: both arms score the same stored span quotes
against the same paper text, re-read with the worker's own
extract_pdf_text_sync from a PDF whose sha256 is checked. Three span sources:

  (default)        The eval fixtures' frozen runs: spans read from Postgres for
                   each fixture's header.extraction_run_id. Aborts if fixture
                   and DB claims disagree.
  --run-id ID      Any extraction run in Postgres (repeatable). PDF must match
                   that run's file_records.content_hash.
  --trace DIR      B5.1 replay traces (DIR/*.trace.json). PDF must match the
                   pinned hash of the copy the traces were scored against.

Off-arm check (aborts on mismatch): with normalisation off the replay must
reproduce what was stored - for DB spans the Stage-1 verdict (Fail with no
stance <=> score < threshold), for trace spans the recorded fuzz_score.
B5.1 traces' token_exact-gate spans store a synthetic fuzz_score of 100.0
(that gate is not in current code); --exempt-token-exact skips only those
spans in the check - they are still scored and listed as exempted.

Golden row ids come only from the human-adjudicated match map (claim
fingerprint). Unmapped claims are still replayed and counted.

  uv run python -m eval.replay_stage1 --run-id <uuid> --run-id <uuid>
  uv run python -m eval.replay_stage1 --trace scratch/b51_replay/out/v3_b/traces
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from eval.match_map import fingerprint_claim_text
from extraction.grounding import (
    AUDIT_MAX_ATTEMPTS,
    RAPIDFUZZ_THRESHOLD,
    _audit_context,
    _stage1_score,
    normalize_for_match,
    normalize_with_map,
)

REPO_ROOT = Path(__file__).parent.parent.parent
SERVICE_ROOT = Path(__file__).parent.parent
LOGS_DIR = SERVICE_ROOT / "logs" / "eval"
FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"
SPAN_CACHE_DIR = SERVICE_ROOT / "scratch" / "stage1_replay"

POST_RESET_LABEL = "Stage-1 effect on post-reset runs, not the frozen baseline"
TRACE_SCORE_TOLERANCE = 1e-6

GOLDEN = {
    "matrix": REPO_ROOT / "docs" / "evals" / "matrix_eval.json",
    "match_map": REPO_ROOT / "docs" / "evals" / "match_map.json",
}
HELDOUT = {
    "matrix": REPO_ROOT / "docs" / "evals" / "heldout_eval.json",
    "match_map": REPO_ROOT / "docs" / "evals" / "heldout_match_map.json",
}

# Candidate local copies per uploaded filename; the one whose sha256 matches
# is used. downloads/<filename> is deliberately not a candidate - the worker
# overwrites it on every upload of that name.
PDF_CANDIDATES = {
    "cot.pdf": [REPO_ROOT / "docs/research_papers/cot.pdf", SERVICE_ROOT / "downloads/2201.11903v6.pdf"],
    "react.pdf": [REPO_ROOT / "docs/research_papers/react.pdf", SERVICE_ROOT / "downloads/2210.03629v3.pdf"],
    "reflexion.pdf": [REPO_ROOT / "docs/research_papers/reflexion.pdf", SERVICE_ROOT / "downloads/2303.11366v4.pdf"],
    "2609.20812v3.pdf": [SERVICE_ROOT / "downloads/2609.20812v3.pdf", SERVICE_ROOT / "scratch/heldout/2609.20812v3.pdf"],
}

# Trace files carry no content hash. These are the sha256s of
# downloads/<arxiv-id>.pdf, the files scratch/b51_replay/replay.py built its
# paper text from; the fuzz_score reproduction check is what binds the text.
TRACE_PAPERS = {
    "arxiv-2201.11903v6": ("cot.pdf", "7d9f878c23b460e4566aa4ec9201b1abfb3b8faefb2b1356e411cb90fef72a12"),
    "arxiv-2210.03629v3": ("react.pdf", "f285b0971ae4a790e402fb93966bed3adde2cf0a04977d08b2b40d6ab0cace69"),
    "arxiv-2303.11366v4": ("reflexion.pdf", "6059b6f89fea9959bd3dab553fbb97756a3dfb1b15e3cbab2fbf3ab6664333bd"),
}

_RUN_SQL = """
SELECT fr.content_hash, fr.file_name
FROM   document_extractors de
JOIN   file_records fr ON fr.file_id = de.file_id
WHERE  de.id = %s;
"""

_CLAIMS_SQL = """
SELECT pc.claim_text_verbatim, pc.grounding_status, pc.evidence_spans
FROM   paper_claims pc
WHERE  pc.document_extractor_id = %s
ORDER  BY pc.created_at ASC;
"""


# --- span sources -----------------------------------------------------------

async def _fetch_run_from_db(extraction_run_id: str) -> dict:
    from memory_db import create_db_connection_pool

    pool = create_db_connection_pool()
    await pool.open()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(_RUN_SQL, (extraction_run_id,))
                run_row = await cur.fetchone()
                if run_row is None:
                    raise SystemExit(f"extraction run {extraction_run_id} not found in DB")
                await cur.execute(_CLAIMS_SQL, (extraction_run_id,))
                claim_rows = await cur.fetchall()
    finally:
        await pool.close()
    return {
        "extraction_run_id": extraction_run_id,
        "content_hash": run_row[0],
        "file_name": run_row[1],
        "claims": [
            {"claim_text_verbatim": r[0], "grounding_status": r[1], "evidence_spans": r[2]}
            for r in claim_rows
        ],
    }


async def _load_run(extraction_run_id: str, refresh: bool) -> dict:
    """Spans for one extraction run, cached under scratch/ after the first
    DB read so repeat replays don't need Postgres."""
    cache_path = SPAN_CACHE_DIR / f"{extraction_run_id}.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    run = await _fetch_run_from_db(extraction_run_id)
    SPAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    return run


def _db_run_to_input(run: dict, label: str) -> dict:
    return {
        "label": label,
        "file_name": run["file_name"],
        "expected_sha256": run["content_hash"],
        "off_arm_check": "stored_stage1_verdict",
        "claims": [
            {
                "fingerprint": fingerprint_claim_text(c["claim_text_verbatim"]),
                "claim_text_verbatim": c["claim_text_verbatim"],
                "stored_claim_status": c["grounding_status"],
                "spans": [
                    {
                        "source_text": s["source_text"],
                        "source_section": s.get("source_section"),
                        "stored_status": s["grounding_status"],
                        "stored_stance": s.get("stance"),
                    }
                    for s in c["evidence_spans"]
                ],
            }
            for c in run["claims"]
        ],
    }


def _rollup_status(span_statuses: list[str]) -> str:
    # Same precedence as ground_extraction's per-claim rollup.
    for status in ("Pass", "Partial", "Skipped"):
        if status in span_statuses:
            return status
    return "Fail"


def _trace_to_input(trace_path: Path) -> dict:
    paper_id = trace_path.name.removesuffix(".trace.json")
    if paper_id not in TRACE_PAPERS:
        raise SystemExit(f"{trace_path}: no pinned PDF for {paper_id}")
    file_name, sha256 = TRACE_PAPERS[paper_id]
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    return {
        "label": f"trace {trace_path.parent.parent.name}/{paper_id}",
        "file_name": file_name,
        "expected_sha256": sha256,
        "off_arm_check": "stored_fuzz_score",
        "claims": [
            {
                "fingerprint": c["fingerprint"],
                "claim_text_verbatim": None,
                "stored_claim_status": _rollup_status([s["grounding_status"] for s in c["spans"]]),
                "spans": [
                    {
                        "source_text": s["source_text"],
                        "source_section": s.get("role"),
                        "stored_status": s["grounding_status"],
                        "stored_stance": s.get("stance"),
                        "stored_fuzz_score": s["fuzz_score"],
                        "gate": s.get("gate"),
                    }
                    for s in c["spans"]
                ],
            }
            for c in trace["claims"]
        ],
    }


def _check_fixture_matches_run(paper_id: str, fixture: dict, run: dict) -> None:
    fixture_claims = fixture["claims"]
    if len(fixture_claims) != len(run["claims"]):
        raise SystemExit(f"{paper_id}: fixture has {len(fixture_claims)} claims, DB run has {len(run['claims'])}")
    for i, (fc, dc) in enumerate(zip(fixture_claims, run["claims"])):
        if fc["claim_text_verbatim"] != dc["claim_text_verbatim"] or fc["grounding_status"] != dc["grounding_status"]:
            raise SystemExit(f"{paper_id}: fixture/DB disagree at claim index {i}")


# --- replay -----------------------------------------------------------------

def _resolve_pdf(file_name: str, sha256: str) -> Path:
    for candidate in PDF_CANDIDATES.get(file_name, []):
        if candidate.exists() and hashlib.sha256(candidate.read_bytes()).hexdigest() == sha256:
            return candidate
    raise SystemExit(f"no local PDF for {file_name} matches sha256 {sha256}")


def _golden_index(matrix_path: Path, match_map_path: Path) -> tuple[dict, dict]:
    """Returns ({claim_fingerprint: expected_id}, {expected_id: "G" | "N" | None}).

    "G" = grounding_negative row, "N" = not_supported-only row (both are
    golden negatives to the scorer), None = positive row. Only human
    adjudications count - match-map `suggested` values are ignored.
    """
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    negative = {
        r["id"]: "G" if r.get("grounding_negative") else ("N" if r["expected_label"] == "not_supported" else None)
        for p in matrix["papers"] for r in p["expected_matrix"]
    }
    match_map = json.loads(match_map_path.read_text(encoding="utf-8"))
    row_by_fp = {
        row["claim_fingerprint"]: row_id
        for row_id, row in match_map["rows"].items()
        if row.get("claim_fingerprint") and row_id in negative
    }
    return row_by_fp, negative


def _replay(source: dict, paper_text: str, row_by_fp: dict, negative: dict, exempt_token_exact: bool) -> dict:
    claims_out, mismatches, exempted, map_mismatches = [], [], [], []
    if normalize_with_map(paper_text)[0] != normalize_for_match(paper_text):
        map_mismatches.append("paper text")
    for i, claim in enumerate(source["claims"]):
        golden_id = row_by_fp.get(claim["fingerprint"])
        spans_out = []
        for j, span in enumerate(claim["spans"]):
            src = span["source_text"]
            if normalize_with_map(src)[0] != normalize_for_match(src):
                map_mismatches.append(f"claim {i} span {j} quote")
            old = _stage1_score(src, paper_text, normalize=False)
            new = _stage1_score(src, paper_text, normalize=True)
            if source["off_arm_check"] == "stored_fuzz_score":
                if exempt_token_exact and span.get("gate") == "token_exact":
                    exempted.append(f"claim {i} span {j}: old={old:.4f} stored fuzz_score={span['stored_fuzz_score']:.4f} (token_exact)")
                elif abs(old - span["stored_fuzz_score"]) > TRACE_SCORE_TOLERANCE:
                    mismatches.append(f"claim {i} span {j}: old={old:.4f} stored fuzz_score={span['stored_fuzz_score']:.4f}")
            else:
                stored_stage1_fail = span["stored_status"] == "Fail" and span["stored_stance"] is None
                if (old < RAPIDFUZZ_THRESHOLD) != stored_stage1_fail:
                    mismatches.append(
                        f"claim {i} span {j}: old={old:.1f} stored={span['stored_status']} stance={span['stored_stance']}")
            old_pass, new_pass = old >= RAPIDFUZZ_THRESHOLD, new >= RAPIDFUZZ_THRESHOLD
            flip = None if old_pass == new_pass else ("fail->pass" if new_pass else "pass->fail")
            # Audit context each arm would hand Stage 2 (only for spans that reach it).
            context_off = _audit_context(src, paper_text, normalize=False) if old_pass else None
            context_on = _audit_context(src, paper_text, normalize=True) if new_pass else None
            spans_out.append({
                "span_index": j,
                "source_section": span["source_section"],
                "stored_status": span["stored_status"],
                "stored_stance": span["stored_stance"],
                "old_score": round(old, 2),
                "new_score": round(new, 2),
                "flip": flip,
                "context_source_off": context_off[1] if context_off else None,
                "context_source_on": context_on[1] if context_on else None,
                "context_changed": bool(old_pass and new_pass and context_off != context_on),
                "context_on": context_on[0] if context_on else None,
                "source_text": src,
            })
        claims_out.append({
            "claim_index": i,
            "golden_id": golden_id,
            "negative": negative.get(golden_id) if golden_id else None,
            "stored_claim_status": claim["stored_claim_status"],
            "old_max": max((s["old_score"] for s in spans_out), default=None),
            "new_max": max((s["new_score"] for s in spans_out), default=None),
            "claim_stage1_old": any(s["old_score"] >= RAPIDFUZZ_THRESHOLD for s in spans_out),
            "claim_stage1_new": any(s["new_score"] >= RAPIDFUZZ_THRESHOLD for s in spans_out),
            "claim_text_verbatim": claim["claim_text_verbatim"],
            "spans": spans_out,
        })

    if mismatches:
        raise SystemExit(
            f"{source['label']}: normalisation-off replay does not reproduce stored values "
            f"({source['off_arm_check']}):\n  " + "\n  ".join(mismatches))
    if map_mismatches:
        raise SystemExit(f"{source['label']}: normalize_with_map != normalize_for_match for: {map_mismatches}")
    for line in exempted:
        print(f"[replay_stage1] {source['label']}: off-arm check EXEMPTED {line}")
    return {"label": source["label"], "file_name": source["file_name"], "off_arm_exempted": exempted,
            "map_equality_checked": 1 + sum(len(c["spans"]) for c in claims_out), "claims": claims_out}


# --- report -----------------------------------------------------------------

def _print_report(papers: list[dict], post_reset: bool) -> None:
    if post_reset:
        print(f"\n=== {POST_RESET_LABEL} ===")
    print(f"\nPer-claim Stage-1 (max span score; claim passes Stage 1 if any span >= {RAPIDFUZZ_THRESHOLD})")
    print(f"{'source':<34} {'idx':>3} {'golden':<12} {'neg':<3} {'stored':<8} "
          f"{'spans':>5} {'old':>6} {'new':>6} {'f->p':>4} {'p->f':>4} claim")
    for p in papers:
        for c in p["claims"]:
            fp = sum(1 for s in c["spans"] if s["flip"] == "fail->pass")
            pf = sum(1 for s in c["spans"] if s["flip"] == "pass->fail")
            claim_flip = "" if c["claim_stage1_old"] == c["claim_stage1_new"] else (
                "FAIL->PASS" if c["claim_stage1_new"] else "PASS->FAIL")
            print(f"{p['label']:<34} {c['claim_index']:>3} {c['golden_id'] or 'unmapped':<12} "
                  f"{c['negative'] or '':<3} {c['stored_claim_status']:<8} "
                  f"{len(c['spans']):>5} {c['old_max'] or 0:>6.1f} {c['new_max'] or 0:>6.1f} "
                  f"{fp or '':>4} {pf or '':>4} {claim_flip}")

    span_flips = [(p["label"], c, s) for p in papers for c in p["claims"] for s in c["spans"] if s["flip"]]
    print("\nSpan flips")
    if not span_flips:
        print("  (none)")
    for label, c, s in span_flips:
        fb = f" context={s['context_source_on']}" if s["context_source_on"] else ""
        neg = f" NEG-{c['negative']}" if c["negative"] else ""
        print(f"  {label} claim {c['claim_index']} span {s['span_index']} [{c['golden_id'] or 'unmapped'}{neg}] "
              f"{s['flip']} {s['old_score']:.1f} -> {s['new_score']:.1f} "
              f"(stored span {s['stored_status']}, claim {c['stored_claim_status']}){fb}")
        print(f"      {s['source_text'][:200]!r}")

    claims = [c for p in papers for c in p["claims"]]
    fp = [x for x in span_flips if x[2]["flip"] == "fail->pass"]
    pf = [x for x in span_flips if x[2]["flip"] == "pass->fail"]
    claim_flips = [c for c in claims if c["claim_stage1_old"] != c["claim_stage1_new"]]
    total_spans = sum(len(c["spans"]) for c in claims)
    mapped = sum(1 for c in claims if c["golden_id"])
    print("\nSummary")
    print(f"  claims: {len(claims)} ({mapped} mapped, {len(claims) - mapped} unmapped)   spans: {total_spans}")
    print(f"  span flips: fail->pass {len(fp)}, pass->fail {len(pf)}")
    print(f"  claim-level Stage-1 flips: {len(claim_flips)} "
          f"({sum(1 for c in claim_flips if c['claim_stage1_new'])} FAIL->PASS, "
          f"{sum(1 for c in claim_flips if not c['claim_stage1_new'])} PASS->FAIL)")
    print(f"  span flips on G rows: {sum(1 for x in span_flips if x[1]['negative'] == 'G')}   "
          f"on N rows: {sum(1 for x in span_flips if x[1]['negative'] == 'N')}")
    print(f"  fail->pass context: {sum(1 for x in fp if x[2]['context_source_on'] == 'normalized')} real (normalized alignment), "
          f"{sum(1 for x in fp if x[2]['context_source_on'] == 'quote_only')} quote-only fallback")
    already = [s for c in claims for s in c["spans"] if s["context_source_off"] is not None and s["context_source_on"] is not None]
    print(f"  already-passing spans: {len(already)}, context changed: {sum(1 for s in already if s['context_changed'])}, "
          f"off-arm quote-only: {sum(1 for s in already if s['context_source_off'] == 'quote_only')}")
    print(f"  map equality (normalize_with_map == normalize_for_match): "
          f"{sum(p['map_equality_checked'] for p in papers)} texts checked, all equal")
    print(f"  Stage-2 estimate (one audit per fail->pass span): {len(fp)} calls nominal, "
          f"<= {len(fp) * AUDIT_MAX_ATTEMPTS * 2} worst case ({AUDIT_MAX_ATTEMPTS} attempts x primary+fallback)")


async def _run(args: argparse.Namespace) -> int:
    # main.py runs init_telemetry at import; keep it on the no-exporter path.
    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)
    from main import extract_pdf_text_sync

    sources = HELDOUT if args.heldout else GOLDEN
    row_by_fp, negative = _golden_index(sources["matrix"], sources["match_map"])
    post_reset = bool(args.run_id or args.trace)

    inputs: list[dict] = []
    for run_id in args.run_id:
        run = await _load_run(run_id, args.refresh)
        inputs.append(_db_run_to_input(run, f"run {run_id[:8]} {run['file_name']}"))
    for trace_dir in args.trace:
        trace_paths = sorted(Path(trace_dir).glob("*.trace.json"))
        if not trace_paths:
            raise SystemExit(f"no *.trace.json files in {trace_dir}")
        inputs.extend(_trace_to_input(t) for t in trace_paths)
    if not post_reset:
        matrix = json.loads(sources["matrix"].read_text(encoding="utf-8"))
        for paper in matrix["papers"]:
            fixture = json.loads((FIXTURE_DIR / f"{paper['paper_id']}.json").read_text(encoding="utf-8"))
            run = await _load_run(fixture["header"]["extraction_run_id"], args.refresh)
            _check_fixture_matches_run(paper["paper_id"], fixture, run)
            inputs.append(_db_run_to_input(run, f"fixture {paper['paper_id']}"))

    papers, text_cache = [], {}
    for source in inputs:
        pdf_path = _resolve_pdf(source["file_name"], source["expected_sha256"])
        if pdf_path not in text_cache:
            text_cache[pdf_path], _ = extract_pdf_text_sync(str(pdf_path))
        paper_text = text_cache[pdf_path]
        print(f"[replay_stage1] {source['label']}: {len(source['claims'])} claims, pdf={pdf_path.name} "
              f"sha256={source['expected_sha256'][:12]}, {len(paper_text)} chars")
        papers.append(_replay(source, paper_text, row_by_fp, negative, args.exempt_token_exact))

    _print_report(papers, post_reset)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = LOGS_DIR / f"stage1_replay_{'heldout_' if args.heldout else ''}{ts}.json"
    out_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": POST_RESET_LABEL if post_reset else "Stage-1 effect on the frozen fixture runs",
        "threshold": RAPIDFUZZ_THRESHOLD,
        "heldout": args.heldout,
        "run_ids": args.run_id,
        "trace_dirs": args.trace,
        "exempt_token_exact": args.exempt_token_exact,
        "papers": papers,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[replay_stage1] wrote {out_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", action="append", default=[], help="extraction run id in Postgres (repeatable)")
    parser.add_argument("--trace", action="append", default=[], help="directory of *.trace.json files (repeatable)")
    parser.add_argument("--exempt-token-exact", action="store_true",
                        help="skip the trace fuzz_score check for B5.1 token_exact-gate spans (listed in output)")
    parser.add_argument("--heldout", action="store_true", help="use the held-out matrix and match map for golden ids")
    parser.add_argument("--refresh", action="store_true", help="re-read spans from Postgres even if cached")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()
    main()
