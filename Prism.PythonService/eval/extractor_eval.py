"""Extractor-only eval: how much of each golden row the extractor's claims cover.

Runs Call #2 alone (extraction.engine.run_extractor - the production
extractor call, no copied prompt logic) N times per paper, sequentially, on
text read with the worker's own reader (main.extract_pdf_text_sync), and
scores the raw claims against the matrix rows. No audit, structure or
grounding calls.

Coverage, all in normalize_for_match space:
  - each golden row's claim_text_verbatim is split into segments on "..." /
    "…" (stitched excerpts); every segment is located in the paper with
    rapidfuzz partial_ratio_alignment, score >= 88. The row's span is the
    set of its segment spans; if any segment fails the row is UNLOCATED
    (listed by row id, excluded from FULL/PARTIAL/MISS);
  - each extracted claim is segmented and located the same way; any
    segment < 88 -> UNANCHORED (counted only);
  - a row is FULL if the spans of ONE located claim cover >= 80% of the
    row's span chars, PARTIAL if any located claim overlaps it but none
    reaches 80%, else MISS. Reported separately for grounding_negative
    true/false rows.

A live run is INVALID if the fallback model answered, finish_reason is not
STOP, or the JSON did not parse; an invalid run is retried at most twice.

Held-out mode prints and writes counts only (no row ids, no text), redacts
every text field of the production extraction log record to its length,
and swallows engine stdout/stderr/logging during the call.

  uv run python -m eval.extractor_eval --arm before --runs 5 --paper all
  uv run python -m eval.extractor_eval --arm after --runs 1 --paper heldout
  uv run python -m eval.extractor_eval --from-fixture ../docs/evals/fixtures/arxiv-2303.11366v4.json
  uv run python -m eval.extractor_eval --estimate --runs 5 --paper all
  uv run python -m eval.extractor_eval --compare logs/extractor_eval/before_all_X.json logs/extractor_eval/after_all_Y.json

Results go to Prism.PythonService/logs/extractor_eval/ (gitignored).
"""
import argparse
import asyncio
import contextlib
import hashlib
import inspect
import io
import json
import logging
import os
import re
import statistics
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from rapidfuzz import fuzz

from extraction.grounding import normalize_for_match

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_DIR.parent
GOLDEN_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
HELDOUT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "heldout_eval.json"
OUTPUT_DIR = SERVICE_DIR / "logs" / "extractor_eval"

LOCATE_THRESHOLD = 88
FULL_COVERAGE = 0.80
MAX_RETRIES = 2
HELDOUT = "heldout"

FULL, PARTIAL, MISS, UNLOCATED = "FULL", "PARTIAL", "MISS", "UNLOCATED"

ELLIPSIS_RE = re.compile(r"\.\.\.|…")

# _write_structured_log arguments that never carry paper or claim text; in
# held-out mode every other str argument is replaced by its length.
LOG_NON_TEXT_STR_ARGS = frozenset({"log_subdir", "chat_id", "correlation_id", "model_used"})

RUN_METRICS = (
    "claims", "full_total", "negative_full", "negative_partial", "negative_miss",
    "positive_full", "positive_partial", "positive_miss", "unanchored", "unanchored_rate", "unlocated",
    "prompt_tokens", "cached_tokens", "output_tokens", "thinking_tokens", "total_tokens",
)


@dataclass
class Paper:
    paper_id: str
    tag: str  # short name for console/chat_id; "heldout" for the sealed paper
    pdf_path: Path
    sha256: str
    rows: list[dict]
    heldout: bool


# --- coverage (pure) -------------------------------------------------------

def locate(text: str, norm_paper: str) -> tuple[int, int] | None:
    """(start, end) of text's best alignment in the normalised paper, or None
    below LOCATE_THRESHOLD."""
    needle = normalize_for_match(text or "")
    if not needle or len(needle) > len(norm_paper):
        return None
    alignment = fuzz.partial_ratio_alignment(needle, norm_paper)
    if alignment is None or alignment.score < LOCATE_THRESHOLD or alignment.dest_end <= alignment.dest_start:
        return None
    return alignment.dest_start, alignment.dest_end


def segments(text: str) -> list[str]:
    """Splits stitched text on "..." / "…"; whitespace-stripped, empty segments dropped."""
    return [part.strip() for part in ELLIPSIS_RE.split(text or "") if part.strip()]


def locate_segments(text: str, norm_paper: str) -> list[tuple[int, int]] | None:
    """Located span of every ellipsis segment, or None if any segment (or the
    whole text) fails to locate."""
    parts = segments(text)
    if not parts:
        return None
    spans = []
    for part in parts:
        span = locate(part, norm_paper)
        if span is None:
            return None
        spans.append(span)
    return spans


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _covered_chars(row_spans: list[tuple[int, int]], claim_spans: list[tuple[int, int]]) -> int:
    """Chars of the row's (merged) spans covered by the (merged) spans of one claim."""
    return sum(
        max(0, min(r_end, c_end) - max(r_start, c_start))
        for r_start, r_end in _merge(row_spans)
        for c_start, c_end in _merge(claim_spans)
    )


def _claim_text(claim: object) -> str:
    if isinstance(claim, dict) and isinstance(claim.get("claim_text_verbatim"), str):
        return claim["claim_text_verbatim"]
    return ""


def compute_coverage(paper_text: str, rows: list[dict], claims: list) -> dict:
    """Row-level FULL/PARTIAL/MISS/UNLOCATED plus claim-level UNANCHORED."""
    norm_paper = normalize_for_match(paper_text)
    claim_span_sets = []
    unanchored = 0
    for claim in claims:
        spans = locate_segments(_claim_text(claim), norm_paper)
        if spans is None:
            unanchored += 1
        else:
            claim_span_sets.append(spans)

    row_status: dict[str, str] = {}
    counts = {side: {FULL: 0, PARTIAL: 0, MISS: 0} for side in ("negative", "positive")}
    for row in rows:
        row_spans = locate_segments(row["claim_text_verbatim"], norm_paper)
        if row_spans is None:
            row_status[row["id"]] = UNLOCATED
            continue
        row_len = sum(end - start for start, end in _merge(row_spans))
        best = max((_covered_chars(row_spans, spans) for spans in claim_span_sets), default=0)
        if best >= FULL_COVERAGE * row_len:
            status = FULL
        elif best > 0:
            status = PARTIAL
        else:
            status = MISS
        row_status[row["id"]] = status
        counts["negative" if row.get("grounding_negative") else "positive"][status] += 1

    claim_count = len(claims)
    unlocated_ids = [row_id for row_id, status in row_status.items() if status == UNLOCATED]
    return {
        "claims": claim_count,
        "unanchored": unanchored,
        "unanchored_rate": unanchored / claim_count if claim_count else 0.0,
        "unlocated": len(unlocated_ids),
        "unlocated_row_ids": unlocated_ids,
        "full_total": counts["negative"][FULL] + counts["positive"][FULL],
        "negative_full": counts["negative"][FULL],
        "negative_partial": counts["negative"][PARTIAL],
        "negative_miss": counts["negative"][MISS],
        "positive_full": counts["positive"][FULL],
        "positive_partial": counts["positive"][PARTIAL],
        "positive_miss": counts["positive"][MISS],
        "row_status": row_status,
    }


def counts_only(record: dict) -> dict:
    """Drops every row-identifying field - what held-out output is limited to."""
    return {k: v for k, v in record.items() if k not in ("row_status", "unlocated_row_ids")}


# --- run validity ----------------------------------------------------------

def invalid_reasons(call_info: dict, raw: object, error_type: str | None) -> list[str]:
    """Why a live extractor run is invalid; empty list means valid."""
    reasons = []
    if call_info.get("json_parse_ok") is False or (
        error_type is None and not (isinstance(raw, dict) and isinstance(raw.get("claims"), list))
    ):
        reasons.append("json_parse_failed")
    elif error_type is not None:
        reasons.append(f"call_failed:{error_type}")
    if call_info.get("fallback_used"):
        reasons.append("fallback_model")
    if error_type is None and call_info.get("finish_reason") != "STOP":
        reasons.append(f"finish_reason:{call_info.get('finish_reason')}")
    return reasons


def token_fields(call_info: dict) -> dict:
    return {
        "prompt_tokens": call_info.get("prompt_token_count"),
        "cached_tokens": call_info.get("cached_content_token_count"),
        "output_tokens": call_info.get("candidates_token_count"),
        "thinking_tokens": call_info.get("thoughts_token_count"),
        "total_tokens": call_info.get("total_token_count"),
    }


# --- aggregation (pure) ----------------------------------------------------

def _stats(values: list) -> dict | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"mean": statistics.mean(values), "min": min(values), "max": max(values), "n": len(values)}


def aggregate_paper(valid_runs: list[dict]) -> dict:
    agg = {metric: _stats([run.get(metric) for run in valid_runs]) for metric in RUN_METRICS}
    prompt = sum(run.get("prompt_tokens") or 0 for run in valid_runs)
    cached = sum(run.get("cached_tokens") or 0 for run in valid_runs)
    agg["cached_share"] = cached / prompt if prompt else None
    if valid_runs and "row_status" in valid_runs[0]:
        row_ids = list(valid_runs[0]["row_status"])
        agg["row_full_frequency"] = {
            row_id: f"{sum(1 for run in valid_runs if run['row_status'].get(row_id) == FULL)}/{len(valid_runs)}"
            for row_id in row_ids
        }
    return agg


def aggregate_arm(papers: dict[str, dict]) -> dict:
    """Arm-level per-run totals across papers, paired by run number. A run
    number counts only if every paper has a valid run for it."""
    run_numbers = None
    for paper in papers.values():
        numbers = {run["run"] for run in paper["runs"]}
        run_numbers = numbers if run_numbers is None else run_numbers & numbers
    per_run = []
    for run_no in sorted(run_numbers or []):
        runs = [next(r for r in paper["runs"] if r["run"] == run_no) for paper in papers.values()]
        claims = sum(r["claims"] for r in runs)
        unanchored = sum(r["unanchored"] for r in runs)
        per_run.append({
            "run": run_no,
            "full_total": sum(r["full_total"] for r in runs),
            "negative_full": sum(r["negative_full"] for r in runs),
            "positive_full": sum(r["positive_full"] for r in runs),
            "claims": claims,
            "unanchored": unanchored,
            "unanchored_rate": unanchored / claims if claims else 0.0,
        })
    return {
        "per_run": per_run,
        **{f"{m}_stats": _stats([r[m] for r in per_run]) for m in
           ("full_total", "negative_full", "positive_full", "claims", "unanchored_rate")},
    }


# --- pre-registered marks (fixed before any live run) ----------------------

def evaluate_marks(before: dict, after: dict) -> list[dict]:
    """M1-M5 from the PR-1 plan; inputs are two live golden result files."""
    b_arm, a_arm = before["arm_aggregate"], after["arm_aggregate"]
    b_full = [r["full_total"] for r in b_arm["per_run"]]
    a_full = [r["full_total"] for r in a_arm["per_run"]]
    b_neg = [r["negative_full"] for r in b_arm["per_run"]]
    a_neg = [r["negative_full"] for r in a_arm["per_run"]]
    b_rate = [r["unanchored_rate"] for r in b_arm["per_run"]]
    a_rate = [r["unanchored_rate"] for r in a_arm["per_run"]]
    marks = []

    ok = bool(a_full and b_full) and min(a_full) > max(b_full)
    marks.append({"mark": "M1", "rule": "golden FULL total: min(after) > max(before)", "pass": ok,
                  "detail": f"min(after)={min(a_full, default=None)} max(before)={max(b_full, default=None)}"})

    ok = bool(a_neg and b_neg) and statistics.mean(a_neg) >= statistics.mean(b_neg)
    marks.append({"mark": "M2", "rule": "grounding-negative FULL: mean(after) >= mean(before)", "pass": ok,
                  "detail": f"mean(after)={_fmt(a_neg)} mean(before)={_fmt(b_neg)}"})

    claim_means = {pid: (p["aggregate"]["claims"] or {}).get("mean") for pid, p in after["papers"].items()}
    ok = all(m is not None and m <= 50 for m in claim_means.values())
    marks.append({"mark": "M3", "rule": "mean claims per paper <= 50 for every paper (after)", "pass": ok,
                  "detail": ", ".join(f"{pid}={_num(m)}" for pid, m in claim_means.items())})

    ok = bool(a_rate and b_rate) and statistics.mean(a_rate) <= statistics.mean(b_rate) + 0.05
    marks.append({"mark": "M4", "rule": "UNANCHORED rate: mean(after) <= mean(before) + 5 pts", "pass": ok,
                  "detail": f"mean(after)={_pct(a_rate)} mean(before)={_pct(b_rate)}"})

    drops = {}
    for pid, paper in after["papers"].items():
        a_mean = (paper["aggregate"]["full_total"] or {}).get("mean")
        b_mean = ((before["papers"].get(pid) or {}).get("aggregate", {}).get("full_total") or {}).get("mean")
        drops[pid] = (b_mean, a_mean)
    ok = all(b is not None and a is not None and a >= b - 1 for b, a in drops.values())
    marks.append({"mark": "M5", "rule": "no paper's FULL mean drops by more than 1 row", "pass": ok,
                  "detail": ", ".join(f"{pid}: {_num(b)}->{_num(a)}" for pid, (b, a) in drops.items())})
    return marks


def _num(value) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt(values: list) -> str:
    return _num(statistics.mean(values)) if values else "n/a"


def _pct(values: list) -> str:
    return f"{statistics.mean(values) * 100:.1f}%" if values else "n/a"


# --- papers and text -------------------------------------------------------

def _pdf_sources() -> dict[str, tuple[Path, str]]:
    """PDF filename -> (path, pinned sha256), from the leak-index builder."""
    from scripts.build_leak_index import SOURCES

    return {path.name: (path, sha) for path, sha, _ in SOURCES.values()}


def load_papers(selector: str) -> list[Paper]:
    pdfs = _pdf_sources()
    heldout = selector == HELDOUT
    matrix = json.loads((HELDOUT_MATRIX_PATH if heldout else GOLDEN_MATRIX_PATH).read_text(encoding="utf-8"))
    papers = []
    for spec in matrix["papers"]:
        tag = HELDOUT if heldout else Path(spec["filename"]).stem
        if not heldout and selector != "all" and selector not in (spec["paper_id"], tag):
            continue
        path, sha = pdfs[spec["filename"]]
        papers.append(Paper(spec["paper_id"], tag, path, sha, spec["expected_matrix"], heldout))
    if not papers:
        raise SystemExit(f"no paper matches --paper {selector!r}")
    return papers


def paper_for_fixture(fixture: dict) -> Paper:
    paper_id = fixture["header"]["paper_id"]
    heldout_ids = {p["paper_id"] for p in json.loads(HELDOUT_MATRIX_PATH.read_text(encoding="utf-8"))["papers"]}
    if paper_id in heldout_ids:
        return load_papers(HELDOUT)[0]
    return load_papers(paper_id)[0]


def read_paper_text(paper: Paper) -> str:
    """Verifies the pinned sha256, then reads the PDF exactly like the worker."""
    data = paper.pdf_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != paper.sha256:
        raise SystemExit(f"sha256 mismatch for {paper.tag} PDF - refusing to read it")
    # main.py runs init_telemetry at import; keep it on the no-exporter path.
    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)
    from main import extract_pdf_text_sync

    text, _ = extract_pdf_text_sync(str(paper.pdf_path))
    return text


# --- held-out guard --------------------------------------------------------

def _redacting_log_writer(original):
    signature = inspect.signature(original)

    def wrapper(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        for name, value in bound.arguments.items():
            if isinstance(value, str) and name not in LOG_NON_TEXT_STR_ARGS:
                bound.arguments[name] = f"[redacted held-out text: {len(value)} chars]"
        return original(*bound.args, **bound.kwargs)

    return wrapper


@contextlib.contextmanager
def heldout_guard():
    """Redacts text fields of the production extraction log record and
    swallows everything the engine prints or logs during the call."""
    from extraction import engine

    sink = io.StringIO()
    logging.disable(logging.CRITICAL)
    try:
        with mock.patch.object(engine, "_write_structured_log", _redacting_log_writer(engine._write_structured_log)), \
                contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            yield
    finally:
        logging.disable(logging.NOTSET)


# --- live runs -------------------------------------------------------------

async def _attempt(paper: Paper, paper_text: str, arm: str, run_no: int, attempt: int) -> dict:
    from extraction.engine import run_extractor
    from extraction.prompt_version import get_prompt_version

    chat_id = f"extractor-eval-{arm}-{paper.tag}-r{run_no}-a{attempt}-{uuid.uuid4().hex[:8]}"
    call_info: dict = {}
    raw, error_type = None, None
    guard = heldout_guard() if paper.heldout else contextlib.nullcontext()
    with guard:
        try:
            raw, _ = await run_extractor(paper_text, chat_id, None, call_info)
        except Exception as exc:
            error_type = type(exc).__name__

    record = {
        "run": run_no,
        "attempt": attempt,
        "chat_id": chat_id,
        "prompt_version": get_prompt_version(),
        "used_model": call_info.get("used_model"),
        "fallback_used": call_info.get("fallback_used"),
        "model_version": call_info.get("model_version"),
        "finish_reason": call_info.get("finish_reason"),
        "json_parse_ok": call_info.get("json_parse_ok"),
        "error_type": error_type,
        **token_fields(call_info),
    }
    record["invalid_reasons"] = invalid_reasons(call_info, raw, error_type)
    if not record["invalid_reasons"]:
        record.update(compute_coverage(paper_text, paper.rows, raw["claims"]))
    if paper.heldout:
        record = counts_only(record)
    return record


async def run_paper(paper: Paper, paper_text: str, arm: str, runs: int) -> dict:
    valid, invalid, failed_runs = [], [], []
    for run_no in range(1, runs + 1):
        for attempt in range(1, MAX_RETRIES + 2):
            record = await _attempt(paper, paper_text, arm, run_no, attempt)
            _print_run(paper, record)
            if record["invalid_reasons"]:
                invalid.append(record)
                continue
            valid.append(record)
            break
        else:
            failed_runs.append(run_no)
    return {"runs": valid, "invalid_attempts": invalid, "failed_runs": failed_runs, "aggregate": aggregate_paper(valid)}


def _print_run(paper: Paper, record: dict) -> None:
    head = f"[{paper.tag}] run {record['run']} attempt {record['attempt']}"
    tokens = (f"tokens prompt={record.get('prompt_tokens')} cached={record.get('cached_tokens')} "
              f"out={record.get('output_tokens')} think={record.get('thinking_tokens')}")
    if record.get("invalid_reasons"):
        print(f"{head}: INVALID {record['invalid_reasons']} {tokens}")
        return
    print(f"{head}: claims={record['claims']} FULL={record['full_total']} "
          f"neg F/P/M={record['negative_full']}/{record['negative_partial']}/{record['negative_miss']} "
          f"pos F/P/M={record['positive_full']}/{record['positive_partial']}/{record['positive_miss']} "
          f"unanchored={record['unanchored']} unlocated={record['unlocated']} {tokens} "
          f"finish={record['finish_reason']} model={record['used_model']} prompt={record['prompt_version']}")


# --- reporting -------------------------------------------------------------

def _print_aggregate(results: dict) -> None:
    print()
    print(f"=== arm={results['arm']} mode={results['mode']} ===")
    header = f"{'paper':<10} {'metric':<18} {'mean':>8} {'min':>6} {'max':>6} {'n':>3}"
    print(header)
    for paper_id, paper in results["papers"].items():
        tag = paper["tag"]
        for metric in RUN_METRICS:
            st = paper["aggregate"].get(metric)
            if st is None:
                continue
            fmt = (lambda v: f"{v * 100:.1f}%") if metric == "unanchored_rate" else (lambda v: f"{v:g}")
            print(f"{tag:<10} {metric:<18} {fmt(st['mean']):>8} {fmt(st['min']):>6} {fmt(st['max']):>6} {st['n']:>3}")
        share = paper["aggregate"].get("cached_share")
        print(f"{tag:<10} {'cached_share':<18} {('n/a' if share is None else f'{share * 100:.1f}%'):>8}")
        if paper.get("invalid_attempts") or paper.get("failed_runs"):
            print(f"{tag:<10} invalid attempts={len(paper['invalid_attempts'])} failed runs={paper['failed_runs']}")
        if paper.get("unlocated_row_ids"):
            print(f"{tag:<10} UNLOCATED rows: {', '.join(paper['unlocated_row_ids'])}")
        freq = paper["aggregate"].get("row_full_frequency")
        if freq:
            print(f"{tag:<10} row FULL frequency: " + ", ".join(f"{k}={v}" for k, v in freq.items()))
    arm = results.get("arm_aggregate")
    if arm and arm["per_run"]:
        print()
        print("all papers, per run: " + "; ".join(
            f"r{r['run']} FULL={r['full_total']} negFULL={r['negative_full']} claims={r['claims']} "
            f"unanchored={r['unanchored_rate'] * 100:.1f}%" for r in arm["per_run"]))
        for m in ("full_total", "negative_full", "claims"):
            st = arm[f"{m}_stats"]
            print(f"  {m}: mean={st['mean']:.2f} min={st['min']} max={st['max']} n={st['n']}")
    totals = results.get("token_totals")
    if totals:
        print("token totals (all attempts incl. invalid): " + ", ".join(f"{k}={v}" for k, v in totals.items()))


def _write_results(results: dict, name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = OUTPUT_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {path.relative_to(SERVICE_DIR)}")
    return path


def _paper_entry(paper: Paper, body: dict) -> dict:
    entry = {"tag": paper.tag, "heldout": paper.heldout, **body}
    if not paper.heldout and body["runs"]:
        entry["unlocated_row_ids"] = body["runs"][0]["unlocated_row_ids"]
    return entry


def _token_totals(papers: dict) -> dict:
    attempts = [r for p in papers.values() for r in p["runs"] + p.get("invalid_attempts", [])]
    return {k: sum(r.get(k) or 0 for r in attempts) for k in
            ("prompt_tokens", "cached_tokens", "output_tokens", "thinking_tokens", "total_tokens")} | {
        "calls": len(attempts)}


# --- modes -----------------------------------------------------------------

async def run_live(arm: str, runs: int, selector: str) -> None:
    from config import settings
    from extraction.prompt_version import get_prompt_version

    papers = load_papers(selector)
    results = {
        "arm": arm, "mode": "live", "paper_selector": selector, "runs_requested": runs,
        "extraction_model": settings.llm_extraction_model,
        "extraction_fallback_model": settings.llm_extraction_fallback_model,
        "prompt_version": get_prompt_version(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "papers": {},
    }
    for paper in papers:
        paper_text = read_paper_text(paper)
        body = await run_paper(paper, paper_text, arm, runs)
        results["papers"][paper.tag if paper.heldout else paper.paper_id] = _paper_entry(paper, body)
    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    if not any(p.heldout for p in papers):
        results["arm_aggregate"] = aggregate_arm(results["papers"])
    results["token_totals"] = _token_totals(results["papers"])
    _print_aggregate(results)
    _write_results(results, f"{arm}_{selector}")


def run_from_fixtures(fixture_paths: list[str], arm: str) -> None:
    results = {"arm": arm, "mode": "fixture", "papers": {}}
    for fixture_path in fixture_paths:
        fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        paper = paper_for_fixture(fixture)
        paper_text = read_paper_text(paper)
        record = {"run": 1, "attempt": 1, "extraction_run_id": fixture["header"].get("extraction_run_id"),
                  "prompt_hash": fixture["header"].get("prompt_hash"), "invalid_reasons": [],
                  **compute_coverage(paper_text, paper.rows, fixture["claims"])}
        if paper.heldout:
            record = counts_only(record)
        _print_run(paper, {**record, "finish_reason": "fixture", "used_model": fixture["header"].get("model_name"),
                           "prompt_version": record.get("prompt_hash")})
        body = {"runs": [record], "invalid_attempts": [], "failed_runs": [], "aggregate": aggregate_paper([record])}
        results["papers"][paper.tag if paper.heldout else paper.paper_id] = _paper_entry(paper, body)
    if not any(p["heldout"] for p in results["papers"].values()):
        results["arm_aggregate"] = aggregate_arm(results["papers"])
    _print_aggregate(results)
    name = "heldout" if any(p["heldout"] for p in results["papers"].values()) else "all"
    _write_results(results, f"{arm}_fixture_{name}")


def run_estimate(runs: int, selector: str) -> None:
    """Call count and input-size estimate from char counts (~4 chars/token); no LLM calls."""
    from extraction.prompt_loader import build_gemini_messages_for_extractor

    total_chars = 0
    papers = load_papers(selector)
    for paper in papers:
        messages = build_gemini_messages_for_extractor(read_paper_text(paper))
        system = sum(len(m["content"]) for m in messages if m["role"] == "system")
        fewshot = sum(len(m["content"]) for m in messages[1:-1])
        body = len(messages[-1]["content"])
        per_call = system + fewshot + body
        total_chars += per_call * runs
        print(f"[{paper.tag}] chars per call: system={system} fewshot={fewshot} paper={body} "
              f"total={per_call} (~{per_call // 4} tokens)")
    calls = len(papers) * runs
    print(f"calls: {calls} nominal, <= {calls * (MAX_RETRIES + 1)} with retries; "
          f"input ~{total_chars // 4} tokens nominal, <= ~{total_chars * (MAX_RETRIES + 1) // 4} worst case")


def run_compare(before_path: str, after_path: str) -> None:
    before = json.loads(Path(before_path).read_text(encoding="utf-8"))
    after = json.loads(Path(after_path).read_text(encoding="utf-8"))
    for name, res in (("before", before), ("after", after)):
        if res.get("mode") != "live" or "arm_aggregate" not in res:
            raise SystemExit(f"--compare needs two live golden result files; {name} is not one")
    print(f"{'paper':<20} {'metric':<16} {'before':>16} {'after':>16}")
    for pid in after["papers"]:
        for metric in ("claims", "full_total", "negative_full", "positive_full", "unanchored_rate"):
            cells = []
            for res in (before, after):
                st = (res["papers"].get(pid) or {}).get("aggregate", {}).get(metric)
                if st is None:
                    cells.append("n/a")
                elif metric == "unanchored_rate":
                    cells.append(f"{st['mean'] * 100:.1f}% [{st['min'] * 100:.0f}-{st['max'] * 100:.0f}]")
                else:
                    cells.append(f"{st['mean']:.2f} [{st['min']}-{st['max']}]")
            print(f"{pid:<20} {metric:<16} {cells[0]:>16} {cells[1]:>16}")
    print()
    print("per-row FULL frequency (before -> after):")
    for pid in after["papers"]:
        b_freq = (before["papers"].get(pid) or {}).get("aggregate", {}).get("row_full_frequency", {})
        a_freq = after["papers"][pid]["aggregate"].get("row_full_frequency", {})
        for row_id in a_freq:
            print(f"  {row_id:<12} {b_freq.get(row_id, 'n/a'):>5} -> {a_freq[row_id]}")
    print()
    for mark in evaluate_marks(before, after):
        print(f"{mark['mark']} {'PASS' if mark['pass'] else 'FAIL'}  {mark['rule']}  ({mark['detail']})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extractor-only eval (Call #2 coverage of golden rows)")
    parser.add_argument("--arm", help="label for this arm, e.g. before/after")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--paper", default="all", help="paper_id, short name (reflexion/cot/react), 'all' or 'heldout'")
    parser.add_argument("--from-fixture", nargs="+", metavar="PATH", help="score existing fixture claims; no LLM calls")
    parser.add_argument("--estimate", action="store_true", help="print call count and input size; no LLM calls")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="before/after table and marks M1-M5")
    args = parser.parse_args(argv)

    if args.compare:
        run_compare(*args.compare)
    elif args.from_fixture:
        run_from_fixtures(args.from_fixture, args.arm or "fixture")
    elif args.estimate:
        run_estimate(args.runs, args.paper)
    else:
        if not args.arm:
            parser.error("--arm is required for a live run")
        asyncio.run(run_live(args.arm, args.runs, args.paper))


if __name__ == "__main__":
    main(sys.argv[1:])
