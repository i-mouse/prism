"""CLI 1d: real cost per stage from saved usage data, at the run-date list price and at the 2027 list price.
Read-only, zero LLM calls. Every figure is tagged MEASURED, ESTIMATED or NOT FOUND with its source path and file count;
a gap is never filled with a guess. The INR 130 gate is printed for reference only (no pass or fail).

Prices: eval/pricing.py (run date, checked 2026-10-23). 2027 = the gemini-3.6-flash rates x 2 for input, output, cached
read and cache storage, and the same x2 for gemini-3.8-flash because pricing.py says so in a comment; every other model
is unchanged because pricing.py says nothing else. INR 100 per USD.

Sources, one line per stage (see the output for file counts):
  extractor pass 1   docs/evals/fixtures/dev/exp2/control_r1/_summary.json (a proxy: loader fix on, shapes off)
  auditor, structurer  _summary.json records of the 3 full-check B dev folders (gemini-3.6-flash medium)
  grounding          the same summaries, grounding.by_model (eval setup)
  auditor, explicit cache  scratch/a0_output_2026-10-24/_summary.json (A0: 18 claims, 1-3 per cached paper)
  claims per paper   docs/evals/fixtures/dev/run1/*.json (dev run 1)
  metadata, embedding  no usage data saved

Usage (from Prism.PythonService):
  uv run python -m eval.step1.cost_per_stage [--out-dir PATH]
"""
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from eval import pricing
from eval.step1 import common, core
from extraction.context_cache import PER_CLAIM_SECONDS

RECORDED_INR_PER_PAPER = 87.0     # decisions.md / PRISM_REPORT.md: INR 1,048.40 / 12 papers (run-1 ingestion billing)
RECORDED_NOTE = "INR 87 per paper = INR 1,048.40 / 12 papers, run-1 ingestion billing (the other recorded figure is about INR 101)"
GATE_INR = 130.0
RECORDED_CLAIMS = 362
RECORDED_PAPERS = 12
AUDITOR_MODEL = "gemini-3.6-flash"
GROUNDING_LABEL = "eval setup (gemini-3.1-flash-lite primary); product uses Groq primary with flash-lite fallback"

B_DEV_DIRS = common.full_check_dirs(common.ARM_B, "dev")
A0_SUMMARY = common.SCRATCH_DIR / "a0_output_2026-10-24" / "_summary.json"
EXP2_CONTROL_SUMMARY = common.DEV_FIXTURE_DIR / "exp2" / "control_r1" / "_summary.json"
METADATA_LOG_DIR = common.REPO_ROOT / "Prism.PythonService" / "logs" / "metadata"


def _load_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class Line:
    """One stage figure, per paper."""
    stage: str
    tag: str                       # MEASURED | ESTIMATED | NOT FOUND
    source: str
    files: int
    calls: float | None = None
    prompt: float | None = None
    cached: float | None = None
    out_thought: float | None = None
    inr_2026: float | None = None
    inr_2027: float | None = None
    note: str = ""


def claims_per_paper() -> tuple[float | None, str]:
    files = [p for p in sorted(common.RUN1_FIXTURE_DIR.glob("*.json")) if not p.name.startswith("_")]
    total = 0
    for p in files:
        data = _load_json(p)
        if data is None:
            return None, f"{p} unreadable"
        total += len(data.get("claims", []))
    if not files:
        return None, f"no fixtures in {common.RUN1_FIXTURE_DIR}"
    note = f"{total} claims / {len(files)} papers in {common.RUN1_FIXTURE_DIR.relative_to(common.REPO_ROOT)}"
    if (total, len(files)) != (RECORDED_CLAIMS, RECORDED_PAPERS):
        note += f" (decisions.md records {RECORDED_CLAIMS} / {RECORDED_PAPERS})"
    return total / len(files), note


def _per_paper_from_claim_stats(stage: str, stats: core.CallStats, cpp: float, source: str, files: int, note: str) -> Line:
    """Scales per-claim means (MEASURED) by claims per paper; the scaling makes the per-paper figure ESTIMATED."""
    if not stats.claims:
        return Line(stage, "NOT FOUND", source, files, note="no calls of this kind in the summaries")
    return Line(
        stage, "ESTIMATED", source, files,
        calls=stats.calls / stats.claims * cpp, prompt=stats.per_claim("prompt") * cpp,
        cached=stats.per_claim("cached") * cpp, out_thought=(stats.per_claim("output") + stats.per_claim("thought")) * cpp,
        inr_2026=core.usd_to_inr(stats.usd_2026) / stats.claims * cpp,
        inr_2027=core.usd_to_inr(stats.usd_2027) / stats.claims * cpp,
        note=note,
    )


def _grounding_line(summaries: list[dict], cpp: float, source: str) -> Line:
    claims = 0
    calls = prompt = cached = out = 0.0
    usd26 = usd27 = 0.0
    for s in summaries:
        records = s.get("records") or []
        claims += len({(r.get("paper_id"), r.get("claim_index")) for r in records})
        for model, agg in ((s.get("grounding") or {}).get("by_model") or {}).items():
            try:
                rates26, rates27 = pricing.rates_for_model(model), core.rates_2027(model)
            except pricing.UnpricedModelError:
                return Line("grounding", "NOT FOUND", source, len(summaries), note=f"model {model!r} has no price in pricing.py")
            p, c, o = agg.get("prompt_tokens") or 0, agg.get("cached_tokens") or 0, agg.get("output_tokens") or 0
            calls += agg.get("calls") or 0
            prompt += p
            cached += c
            out += o
            usd26 += core.call_cost_usd(rates26, p, c, o)
            usd27 += core.call_cost_usd(rates27, p, c, o)
    if not claims:
        return Line("grounding", "NOT FOUND", source, len(summaries), note="no claims in the summaries")
    return Line(
        "grounding", "ESTIMATED", source, len(summaries), calls=calls / claims * cpp, prompt=prompt / claims * cpp,
        cached=cached / claims * cpp, out_thought=out / claims * cpp,
        inr_2026=core.usd_to_inr(usd26) / claims * cpp, inr_2027=core.usd_to_inr(usd27) / claims * cpp,
        note=GROUNDING_LABEL + "; thought tokens are not recorded for grounding calls",
    )


def _extractor_line() -> Line:
    source = str(EXP2_CONTROL_SUMMARY.relative_to(common.REPO_ROOT))
    data = _load_json(EXP2_CONTROL_SUMMARY)
    if data is None:
        return Line("extractor pass 1", "NOT FOUND", source, 0, note="summary missing or unreadable")
    records = [r for r in data.get("records", []) if r.get("variant") == "control"]
    papers = {r.get("paper_id") for r in records}
    if not records:
        return Line("extractor pass 1", "NOT FOUND", source, 1, note="no control records")
    n = len(papers)
    usd26 = sum(core.record_usd(r, 2026) for r in records)
    usd27 = sum(core.record_usd(r, 2027) for r in records)
    return Line(
        "extractor pass 1", "MEASURED", source, 1, calls=len(records) / n,
        prompt=sum(r.get("prompt_tokens") or 0 for r in records) / n, cached=None,
        out_thought=sum((r.get("output_tokens") or 0) + (r.get("thought_tokens") or 0) for r in records) / n,
        inr_2026=core.usd_to_inr(usd26) / n, inr_2027=core.usd_to_inr(usd27) / n,
        note=f"proxy (exp2 control: loader fix on, shapes off), {len(records)} calls over {n} papers; "
             "cached tokens are not saved, so all input is priced uncached (an upper bound)",
    )


def _metadata_line() -> Line:
    count = len(list(METADATA_LOG_DIR.glob("*.json"))) if METADATA_LOG_DIR.is_dir() else 0
    return Line(
        "metadata", "NOT FOUND", str(METADATA_LOG_DIR.relative_to(common.REPO_ROOT)), count,
        note="the metadata logs carry no usage key (checked 2026-11-11 by counting keys; file contents are not read here)",
    )


def _embedding_line() -> Line:
    return Line(
        "embedding", "NOT FOUND", "Prism.PythonService/RAGService.py:21", 0,
        note="local fastembed model (BAAI/bge-small-en-v1.5): no usage saved and no API price in pricing.py",
    )


def _explicit_cache_lines(cpp: float) -> tuple[list[Line], dict]:
    """Auditor with explicit caching, from A0. Two lines: cache creation billed (Vertex) and not billed (AI Studio,
    observed once). Per-paper figures are ESTIMATED: A0 served 1-3 claims per cache, a product paper has about cpp."""
    source = str(A0_SUMMARY.relative_to(common.REPO_ROOT))
    data = _load_json(A0_SUMMARY)
    if data is None:
        return [Line("auditor, explicit cache", "NOT FOUND", source, 0, note="A0 summary missing or unreadable")], {}
    stats = core.summarize_records([data.get("records") or []], want_audit=True)
    papers = (data.get("cache") or {}).get("papers") or []
    tokens = [p.get("token_count") for p in papers if isinstance(p.get("token_count"), (int, float))]
    if not stats.claims or not tokens:
        return [Line("auditor, explicit cache", "NOT FOUND", source, 1, note="no audit records or cache sizes")], {}
    cache_tokens = sum(tokens) / len(tokens)
    lines = []
    detail = {"cache_tokens_mean": cache_tokens, "caches": len(tokens), "audit_calls": stats.calls}
    for billed, name in ((True, "creation billed (Vertex)"), (False, "creation not billed (AI Studio, observed once)")):
        inr = {}
        for year in (2026, 2027):
            rates = pricing.rates_for_model(AUDITOR_MODEL) if year == 2026 else core.rates_2027(AUDITOR_MODEL)
            storage_rate = pricing.storage_rate_for_model(AUDITOR_MODEL) if year == 2026 else core.storage_rate_2027(AUDITOR_MODEL)
            creation, storage = core.cache_overhead_usd(cache_tokens, cpp, PER_CLAIM_SECONDS, rates, storage_rate, billed)
            claim_usd = (stats.usd_2026 if year == 2026 else stats.usd_2027) / stats.claims
            inr[year] = core.usd_to_inr(claim_usd * cpp + creation + storage)
        lines.append(Line(
            f"auditor, explicit cache, {name}", "ESTIMATED", source, 1, calls=cpp, prompt=stats.per_claim("prompt") * cpp,
            cached=stats.per_claim("cached") * cpp,
            out_thought=(stats.per_claim("output") + stats.per_claim("thought")) * cpp, inr_2026=inr[2026], inr_2027=inr[2027],
            note=f"A0 per-claim means x {cpp:.2f} claims + one cache of {cache_tokens:,.0f} tokens (mean of {len(tokens)}), "
                 f"storage for {cpp:.2f} x {PER_CLAIM_SECONDS} s; A0 ran only {stats.claims} claims on {len(tokens)} caches",
        ))
    return lines, detail


def build() -> tuple[list[Line], dict, list[str]]:
    notes: list[str] = []
    cpp, cpp_note = claims_per_paper()
    notes.append(f"claims per paper: {'NOT FOUND' if cpp is None else f'{cpp:.2f}'} ({cpp_note})")
    summaries = [(d, _load_json(d / "_summary.json")) for d in B_DEV_DIRS]
    loaded = [s for _, s in summaries if s is not None]
    lines = [_metadata_line(), _extractor_line(), _embedding_line()]
    detail: dict = {"claims_per_paper": cpp}
    audit_src = f"{common.full_check_dirs(common.ARM_B, 'dev')[0].parent.relative_to(common.REPO_ROOT)}/exp1_{common.ARM_B.folder}-vertex_1..3/_summary.json"
    if cpp is None or len(loaded) != len(B_DEV_DIRS):
        for stage in ("auditor, no explicit cache", "structurer", "grounding"):
            lines.append(Line(stage, "NOT FOUND", audit_src, len(loaded), note="claims per paper or B dev summaries missing"))
    else:
        records = [s.get("records") or [] for s in loaded]
        audit = core.summarize_records(records, want_audit=True)
        structure = core.summarize_records(records, want_audit=False)
        lines.append(_per_paper_from_claim_stats(
            "auditor, no explicit cache", audit, cpp, audit_src, len(loaded),
            f"product today; per-claim means MEASURED over {audit.claims} claim audits ({audit.calls} calls), "
            "cached tokens are the implicit cache hits the API reported",
        ))
        lines.append(_per_paper_from_claim_stats(
            "structurer", structure, cpp, audit_src, len(loaded),
            f"per-claim means MEASURED over {structure.claims} claims ({structure.calls} calls)",
        ))
        lines.append(_grounding_line(loaded, cpp, audit_src))
        detail["per_claim"] = {
            "audit": audit.__dict__, "structure": structure.__dict__,
        }
    if cpp is not None:
        cache_lines, cache_detail = _explicit_cache_lines(cpp)
        lines += cache_lines
        detail["explicit_cache"] = cache_detail
    return lines, detail, notes


def _sum(lines: list[Line], names: list[str]) -> tuple[float | None, float | None, list[str]]:
    """Sum of the named stages' INR; None when one of them has no figure. Returns (2026, 2027, missing names)."""
    by_name = {ln.stage: ln for ln in lines}
    missing = [n for n in names if n not in by_name or by_name[n].inr_2026 is None]
    if missing:
        return None, None, missing
    return (
        sum(by_name[n].inr_2026 or 0.0 for n in names), sum(by_name[n].inr_2027 or 0.0 for n in names), [],
    )


def _fmt(v: float | None, digits: int = 1) -> str:
    return "-" if v is None else f"{v:,.{digits}f}"


def render(lines: list[Line], notes: list[str]) -> tuple[list[str], dict]:
    out = [
        "Real cost per stage, per paper, from saved usage data. INR 100 per USD.",
        "Run-date price = eval/pricing.py (3.6-flash USD 0.75 in / 3.75 out / 0.075 cached per 1M; storage 0.50 per 1M-hour).",
        ("2027 price = gemini-3.6-flash rates x 2 (in 1.50 / out 7.50 / cached 0.15 / storage 1.00); gemini-3.8-flash x2 as well "
        "(pricing.py comment); all other models unchanged because pricing.py says nothing else."),
        ("Tags: MEASURED = saved usage, ESTIMATED = measured per-claim means scaled by claims per paper (or a proxy), "
        "NOT FOUND = no usage saved; a NOT FOUND stage has no figure and is left out of the sums."),
    ] + notes + [""]
    out.append(f"{'stage':<54} {'tag':<9} {'calls':>6} {'input':>9} {'cached':>9} {'out+thought':>11} {'INR 2026':>9} {'INR 2027':>9}")
    for ln in lines:
        out.append(
            f"{ln.stage:<54} {ln.tag:<9} {_fmt(ln.calls):>6} {_fmt(ln.prompt, 0):>9} {_fmt(ln.cached, 0):>9} "
            f"{_fmt(ln.out_thought, 0):>11} {_fmt(ln.inr_2026):>9} {_fmt(ln.inr_2027):>9}"
        )
    out.append("(tokens per paper; input includes cached; '-' = not found or not saved)")
    out.append("")
    for ln in lines:
        out.append(f"- {ln.stage}: source {ln.source}; files {ln.files}. {ln.note}".rstrip())

    base = ["extractor pass 1", "structurer", "grounding"]
    scenarios = (
        ("today: no explicit caching", ["auditor, no explicit cache"]),
        ("explicit caching, creation billed (Vertex)", ["auditor, explicit cache, creation billed (Vertex)"]),
        ("explicit caching, creation not billed (AI Studio, observed once)",
         ["auditor, explicit cache, creation not billed (AI Studio, observed once)"]),
    )
    out += ["", "Per-paper total of the stages that have a figure (metadata and embedding are NOT FOUND and are not in it):"]
    totals = {}
    for name, auditor in scenarios:
        t26, t27, missing = _sum(lines, base + auditor)
        totals[name] = {"inr_2026": t26, "inr_2027": t27, "missing": missing}
        if t26 is None or t27 is None:
            out.append(f"  {name}: no total (missing figure for {', '.join(missing)})")
            continue
        out.append(
            f"  {name}: INR {t26:,.1f} at run-date price, INR {t27:,.1f} at 2027 price; "
            f"recorded INR {RECORDED_INR_PER_PAPER:g} -> gap INR {RECORDED_INR_PER_PAPER - t26:+,.1f} "
            f"({100 * (RECORDED_INR_PER_PAPER - t26) / RECORDED_INR_PER_PAPER:+.0f}% of the recorded figure); "
            f"against the recorded figure doubled (INR {2 * RECORDED_INR_PER_PAPER:g}) the 2027 gap is INR {2 * RECORDED_INR_PER_PAPER - t27:+,.1f}"
        )
    out.append(f"  Recorded: {RECORDED_NOTE}. A positive gap = recorded is higher than the sum of the stages found "
               "(metadata, embedding, retries and failed calls are not in the saved usage).")
    out.append(f"  INR {GATE_INR:g} gate, for reference only (no pass or fail is applied here).")
    return out, totals


def run(out_dir: Path) -> int:
    lines, detail, notes = build()
    text_lines, totals = render(lines, notes)
    text = "\n".join(text_lines) + "\n"
    print(text)
    payload = {"lines": [ln.__dict__ for ln in lines], "totals": totals, "detail": detail}
    for path in common.write_outputs(out_dir, "1d_cost_per_stage", text, payload):
        print(f"wrote {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=common.DEFAULT_OUT_DIR)
    args = parser.parse_args()
    sys.exit(run(args.out_dir))


if __name__ == "__main__":
    main()
