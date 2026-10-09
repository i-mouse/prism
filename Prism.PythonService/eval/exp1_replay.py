"""Experiment 1 replay: auditor-only, legacy vs scoped, on golden-matched claims.

Re-audits the golden-matched claims of run A (hash cb3272cce551 fixtures) and
run B (hash 0bcf9d44e619 fixtures). Both arms are auditor-only, so they are
comparable:
  legacy  one free-text audit call per claim (build_gemini_messages_for_audit);
          verdict = last "VERDICT:" line by regex, else "unparsed". No structurer.
  scoped  inventory (per paper, cached) -> scope (claim + inventory only) ->
          free-text scoped audit; verdict by the same regex; lower-only
          aggregation in code. No structurer.
No grounding Stage 2, no extraction. Nothing held-out is referenced.

  uv run python -m eval.exp1_replay                       # --estimate (default)
  uv run python -m eval.exp1_replay --execute --cap-inr N [--inventory-only]

Outputs go to scratch/exp1_replay/out/ (results.json, token_log.jsonl,
inventories/); production logs are redirected to scratch/exp1_replay/logs/.
"""
import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from eval.exp1_common import MATRIX_PATH, OUT_DIR, SERVICE_DIR, SETS, golden_selection, parse_verdict
from eval.matrix_loader import load_matrix

SCRATCH = SERVICE_DIR / "scratch" / "exp1_replay"
REPLAY_LOGS = SCRATCH / "logs"

PRICE_IN_USD_PER_M = 0.75   # gemini-3.6-flash input
PRICE_OUT_USD_PER_M = 3.75  # output including thinking
DEFAULT_INR_PER_USD = 95.0
STOP_FRACTION = 0.90
CONCURRENCY = 5

# --estimate assumptions where no measured number exists (stated in the output).
EST_SCOPE_SIZE = 6              # mean scope items per claim
EST_INVENTORY_ITEMS = 25        # items in a paper inventory
EST_SCOPE_THINKING = 1000       # thinking tokens, scope call
EST_INVENTORY_THINKING = 3000   # thinking tokens, inventory call
EST_TOKENS_PER_SCOPE_LINE = 25  # scope-list line in the audit input
EST_CHECK_TOKENS_PER_ITEM = 40  # CHECK line in the audit output
B51_USAGE = {"A": SERVICE_DIR / "scratch" / "b51_replay" / "out" / "run_a" / "usage.json",
             "B": SERVICE_DIR / "scratch" / "b51_replay" / "out" / "run_b" / "usage.json"}


def cost_inr(input_tokens: int, output_tokens: int, inr_per_usd: float) -> float:
    return (input_tokens * PRICE_IN_USD_PER_M + output_tokens * PRICE_OUT_USD_PER_M) / 1_000_000 * inr_per_usd


@dataclass
class Tally:
    cap_inr: float
    inr_per_usd: float
    input_tokens: int = 0
    output_tokens: int = 0  # candidates + thinking
    calls: int = 0
    stopped: bool = False

    @property
    def inr(self) -> float:
        return cost_inr(self.input_tokens, self.output_tokens, self.inr_per_usd)

    def add(self, call: dict) -> None:
        self.calls += 1
        self.input_tokens += call.get("input_tokens") or 0
        self.output_tokens += (call.get("output_tokens") or 0) + (call.get("thinking_tokens") or 0)

    def over_budget(self) -> bool:
        if self.inr >= STOP_FRACTION * self.cap_inr:
            self.stopped = True
        return self.stopped


# ------------------------------------------------------------------ inputs
def build_paper_text(pdf_path: Path) -> str:
    """Same loop as main.extract_pdf_text_sync (PyMuPDF page.get_text() concatenated)."""
    import fitz

    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text


def load_papers() -> dict[str, str]:
    spec = load_matrix(MATRIX_PATH)
    out = {}
    for p in spec.papers:
        # downloads/react.pdf is a saved HTTP 404 page; the arXiv-id-named copy is the real paper.
        out[p.paper_id] = build_paper_text(SERVICE_DIR / "downloads" / f"{p.paper_id.removeprefix('arxiv-')}.pdf")
    return out


def expected_labels() -> dict[str, str]:
    return {r.id: r.expected_label for p in load_matrix(MATRIX_PATH).papers for r in p.expected_rows}


# ---------------------------------------------------------------- estimate
def _b51_means(set_id: str) -> dict[str, dict]:
    path = B51_USAGE[set_id]
    if not path.exists():
        return {}
    by: dict[str, list[dict]] = {}
    for c in json.loads(path.read_text(encoding="utf-8")).get("auditor_calls", []):
        by.setdefault("arxiv-" + c["chat_id"].split("arxiv-")[-1], []).append(c)
    out = {}
    for paper_id, calls in by.items():
        out[paper_id] = {
            "n": len(calls),
            "input": statistics.mean(c["prompt_tokens"] for c in calls),
            "output": statistics.mean(c["output_tokens"] or 0 for c in calls),
            "thinking": statistics.mean(c["thought_tokens"] or 0 for c in calls),
        }
    return out


def estimate(args, papers: dict[str, str]) -> None:
    from extraction.prompt_loader import (
        build_gemini_messages_for_audit,
        build_messages_for_inventory,
        build_messages_for_scope,
        build_messages_for_scoped_audit,
    )
    from extraction.scoped_audit import get_scoped_prompt_version
    from extraction.prompt_version import get_prompt_version
    from config import settings

    sets = ["A", "B"] if args.set == "both" else [args.set]
    modes = ["legacy", "scoped"] if args.mode == "both" else [args.mode]
    legacy_sys = len(build_gemini_messages_for_audit("", "", "")[0]["content"])
    scoped_sys = len(build_messages_for_scoped_audit("", "", "", [])[0]["content"])
    scope_sys = len(build_messages_for_scope("", "", [])[0]["content"])
    inv_sys = len(build_messages_for_inventory("")[0]["content"])

    print(f"model: {settings.llm_claim_audit_model} (fallback {settings.llm_claim_audit_fallback_model}); audit_mode setting: {settings.audit_mode}")
    print(f"legacy prompt hash {get_prompt_version()}; scoped prompt hash {get_scoped_prompt_version()}")
    print(f"price: ${PRICE_IN_USD_PER_M}/1M in, ${PRICE_OUT_USD_PER_M}/1M out (incl. thinking); INR/USD {args.inr_per_usd}")
    print("method: measured per-paper token means from the B5.1 replay usage logs (scratch/b51_replay/out/run_{a,b}/usage.json:")
    print("  same model, same paper text, B5.1 checklist-era auditor prompt), NOT chars/4. Production logs/audit has no token data.")
    print("  Scoped-arm additions are ASSUMPTIONS, not measurements:")
    print(f"    scope size {EST_SCOPE_SIZE} items/claim; inventory {EST_INVENTORY_ITEMS} items/paper; scope-call thinking {EST_SCOPE_THINKING};")
    print(f"    inventory-call thinking {EST_INVENTORY_THINKING}; scoped-audit thinking = measured legacy thinking; "
          f"+{EST_TOKENS_PER_SCOPE_LINE} in / +{EST_CHECK_TOKENS_PER_ITEM} out tokens per scope item.")

    total = {"calls": 0, "in": 0.0, "out": 0.0}
    rows = []
    # Inventory: once per paper (cache is keyed by paper content, shared across sets/runs).
    if "scoped" in modes:
        inv_in = inv_out = 0.0
        for pid, text in papers.items():
            tin = len(text) / 4 + inv_sys / 4
            tout = EST_INVENTORY_ITEMS * 15 + EST_INVENTORY_THINKING
            inv_in += tin
            inv_out += tout
        rows.append(("inventory (3 papers, once)", len(papers), inv_in, inv_out))
    for set_id in sets:
        means = _b51_means(set_id)
        sel = golden_selection(set_id)
        for mode in modes:
            c_in = c_out = scope_in = scope_out = 0.0
            n = 0
            for pid, paper in sel.items():
                m = means.get(pid)
                k = len(paper["claims"]) * args.runs
                n += k
                if m:
                    base_in, base_out, think = m["input"], m["output"], m["thinking"]
                else:
                    base_in, base_out, think = len(papers[pid]) / 4 + legacy_sys / 4, 330, 2800
                if mode == "legacy":
                    c_in += k * base_in
                    c_out += k * (base_out + think)
                else:
                    c_in += k * (base_in + (scoped_sys - legacy_sys) / 4 + EST_SCOPE_SIZE * EST_TOKENS_PER_SCOPE_LINE)
                    c_out += k * (base_out + EST_SCOPE_SIZE * EST_CHECK_TOKENS_PER_ITEM + think)
                    scope_in += k * (scope_sys / 4 + EST_INVENTORY_ITEMS * 12 + 80)
                    scope_out += k * (EST_SCOPE_SIZE * 60 + EST_SCOPE_THINKING)
            rows.append((f"set {set_id} {mode} audit ({n} claim-runs)", n, c_in, c_out))
            if mode == "scoped":
                rows.append((f"set {set_id} scoped scope-step ({n} claim-runs)", n, scope_in, scope_out))
    print(f"\nEstimate: set={args.set} mode={args.mode} runs={args.runs}")
    print(f"{'step':<46}{'calls':>7}{'input tok':>13}{'output tok':>13}{'INR':>10}")
    for name, calls, tin, tout in rows:
        print(f"{name:<46}{calls:>7}{int(tin):>13,}{int(tout):>13,}{cost_inr(tin, tout, args.inr_per_usd):>10.1f}")
        total["calls"] += calls
        total["in"] += tin
        total["out"] += tout
    print(f"{'TOTAL':<46}{total['calls']:>7}{int(total['in']):>13,}{int(total['out']):>13,}{cost_inr(total['in'], total['out'], args.inr_per_usd):>10.1f}")
    print("(no calls were made)")


# ----------------------------------------------------------------- execute
REFUSAL = {"not_supported", "partially_supported"}

# Pilot marks (docs/experiments/exp1-marks.md). Slots are (set, golden row).
TARGET_SLOTS = [("A", "REACT-M14"), ("A", "REFLEX-M09"), ("A", "REFLEX-M13"),
                ("B", "COT-M09"), ("B", "COT-M10"), ("B", "REFLEX-M13")]
MUST_STAY_SUPPORTED = ("REFLEX-M02", "COT-M04", "REACT-M10")
MAX_ERRORS = 2


async def primary_only_generate(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
    """Replacement for engine._generate_with_fallback in the replay: retries
    transport errors on the primary model only (engine._call_gemini: 3
    attempts with backoff) and never falls back to another model."""
    from extraction import engine

    response = await engine._call_gemini(client, model_name, contents, config, chat_id, correlation_id)
    engine._record_usage(response, config, model_name, model_name)
    return response, model_name


async def run_one_claim(set_id, run, mode, pid, text, claim, golden_rows, labels, inv_rec) -> dict:
    """Audits one claim in the replay. Errors (including a failed scope step)
    are RECORDED as errors; there is no legacy fallback and no model fallback."""
    from extraction import engine
    from extraction.prompt_loader import build_gemini_messages_for_audit
    from extraction.scoped_schemas import PaperInventory
    from config import settings

    chat_id = f"exp1-{set_id}-{mode}-r{run}-{pid}"
    corr = claim["fingerprint"][:12]
    rec = {
        "set": set_id, "run": run, "mode": mode, "paper_id": pid,
        "claim_index": claim["index"], "fingerprint": claim["fingerprint"],
        "golden_rows": golden_rows, "golden_labels": {r: labels.get(r) for r in golden_rows},
        "fixture_label": claim["label"], "calls": [],
    }
    try:
        if mode == "legacy":
            sink: list[dict] = []
            tok = engine._USAGE_SINK.set(sink)
            try:
                audit_text = await engine._call_gemini_freetext(
                    messages=build_gemini_messages_for_audit(text, claim["claim_text_verbatim"], claim["claim_summary"]),
                    chat_id=chat_id, correlation_id=corr, log_subdir="audit",
                    model_name=settings.llm_claim_audit_model, fallback_model=settings.llm_claim_audit_fallback_model,
                )
            finally:
                engine._USAGE_SINK.reset(tok)
            verdict = parse_verdict(audit_text)
            rec.update({"verdict": verdict or "unparsed", "final": verdict or "unparsed", "lowered": False,
                        "flags": [] if verdict else ["unparsed_verdict"]})
            rec["calls"] = sink
        else:
            if inv_rec is None:
                raise RuntimeError("no inventory for this paper")
            inv = PaperInventory.model_validate({"items": inv_rec["items"]})
            res = await engine.run_scoped_audit(text, claim["claim_text_verbatim"], claim["claim_summary"], inv, chat_id, corr)
            verdict = parse_verdict(res.audit_text)
            agg = engine.finish_scoped_audit(res, verdict, text, claim["claim_text_verbatim"], inv_rec["inventory_hash"], chat_id, corr, claim["index"])
            rec.update({
                "verdict": verdict or "unparsed", "final": agg.final or "unparsed", "lowered": agg.lowered,
                "trigger_id": agg.trigger_id, "dropped_ungrounded": agg.dropped_ungrounded,
                "aggregation_skipped": agg.aggregation_skipped, "flags": agg.flags,
                "scope_size": len(res.scope_items), "scope_truncated": res.scope_truncated,
                "check_lines": res.parsed.raw_lines,
                "n_fails": sum(1 for c in res.parsed.checks.values() if c.status == "fails"),
            })
            rec["calls"] = res.usage
    except Exception as exc:  # transport errors were already retried (primary model only)
        from extraction.engine import ScopeStepError

        rec.update({"error": repr(exc), "error_kind": "scope" if isinstance(exc, ScopeStepError) else "model",
                    "verdict": "error", "final": "error", "lowered": False, "flags": []})
        print(f"[error] {set_id} r{run} {mode} {pid} idx={claim['index']}: {exc!r}")
    return rec


# ------------------------------------------------------------ pilot report
def _rows_table(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        for row in r["golden_rows"]:
            out.append({
                "set": r["set"], "row": row, "golden": r["golden_labels"].get(row), "frozen": r["fixture_label"],
                "model_verdict": r.get("verdict"), "scoped": r["final"], "lowered": bool(r.get("lowered")),
            })
    return sorted(out, key=lambda x: (x["row"], x["set"]))


def evaluate_pilot(records: list[dict], labels: dict[str, str], negatives: set[str]) -> dict:
    """Evaluates marks P1-P4 from scoped records (one run). `negatives` is the
    set of golden-negative row ids (grounding_negative or expected
    not_supported). Refusal = not_supported or partially_supported. A target
    slot with no scoped record counts as not refused."""
    table = _rows_table(records)
    by_slot = {(t["set"], t["row"]): t for t in table}
    refused_slots = [s for s in TARGET_SLOTS if by_slot.get(s, {}).get("scoped") in REFUSAL]
    p2_rows = [t for t in table if t["row"] in MUST_STAY_SUPPORTED]
    p2_bad = [(t["set"], t["row"], t["scoped"]) for t in p2_rows if t["scoped"] != "supported"]
    base_refused = [t for t in table if t["row"] in negatives and t["frozen"] in REFUSAL]
    flips = [(t["set"], t["row"]) for t in base_refused if t["scoped"] == "supported"]
    errors = [r for r in records if r.get("error")]
    return {
        "P1": {"value": len(refused_slots), "slots_refused": refused_slots, "need": ">=2 of 6", "pass": len(refused_slots) >= 2},
        "P2": {"value": f"{len(p2_rows) - len(p2_bad)}/{len(p2_rows)} stay supported", "violations": p2_bad, "pass": not p2_bad and bool(p2_rows)},
        "P3": {"value": len(flips), "baseline_refused_rows": len(base_refused), "flips": flips, "need": "<=1", "pass": len(flips) <= 1},
        "P4": {"value": len(errors), "scope_errors": sum(1 for e in errors if e.get("error_kind") == "scope"),
               "model_errors": sum(1 for e in errors if e.get("error_kind") != "scope"), "need": f"<={MAX_ERRORS}", "pass": len(errors) <= MAX_ERRORS},
        "table": table,
    }


def print_report(records: list[dict], meta: dict, labels: dict[str, str], negatives: set[str]) -> None:
    ev = evaluate_pilot(records, labels, negatives)
    print(f"\n{'row':<12}{'set':<4}{'golden':<22}{'frozen':<22}{'scoped final':<22}{'lowered'}")
    for t in ev["table"]:
        print(f"{t['row']:<12}{t['set']:<4}{str(t['golden']):<22}{t['frozen']:<22}{t['scoped']:<22}{'yes' if t['lowered'] else 'no'}")
    print()
    for k in ("P1", "P2", "P3", "P4"):
        d = {x: y for x, y in ev[k].items() if x != "pass"}
        print(f"{k}: {d} -> {'PASS' if ev[k]['pass'] else 'FAIL'}")
    ok = [r for r in records if not r.get("error")]
    flags = [f for r in ok for f in r.get("flags", [])]
    sizes = [r["scope_size"] for r in ok if "scope_size" in r]
    print("\nDiagnostics:")
    print(f"  claims audited={len(records)} errors={len(records) - len(ok)} unparsed verdicts={sum(1 for r in ok if r.get('verdict') == 'unparsed')}")
    print(f"  lowerings fired={sum(1 for r in ok if r.get('lowered'))}  fails dropped as ungrounded={sum(len(r.get('dropped_ungrounded', [])) for r in ok)}")
    print(f"  missing_check={sum(1 for f in flags if f.startswith('missing_check'))}  aggregation_skipped={sum(1 for r in ok if r.get('aggregation_skipped'))}")
    print(f"  mean scope size={statistics.mean(sizes):.1f}" if sizes else "  mean scope size=n/a")
    print(f"  total spend ~INR {meta.get('spent_inr')} (cap {meta.get('cap_inr')}); stopped_by_cap={meta.get('stopped_by_cap')}")
    print("Pilot verdict:", "CONTINUE to 3-run confirmation" if all(ev[k]["pass"] for k in ("P1", "P2", "P3", "P4")) else "STOP - negative result; AUDIT_MODE stays legacy")


def _negatives() -> set[str]:
    return {r.id for p in load_matrix(MATRIX_PATH).papers for r in p.expected_rows if r.grounding_negative or r.expected_label == "not_supported"}


async def execute(args, papers: dict[str, str]) -> None:
    from extraction import engine, scoped_audit
    from extraction.prompt_version import get_prompt_version
    from config import settings

    engine.LOGS_DIR = REPLAY_LOGS  # keep production logs/ clean
    engine._generate_with_fallback = primary_only_generate  # replay: no model fallback
    sets = ["A", "B"] if args.set == "both" else [args.set]
    modes = ["legacy", "scoped"] if args.mode == "both" else [args.mode]
    tally = Tally(args.cap_inr, args.inr_per_usd)
    out_dir = OUT_DIR / ("pilot" if args.baseline else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    token_log = out_dir / "token_log.jsonl"
    results_path = out_dir / "results.json"
    labels = expected_labels()
    results: list[dict] = []
    inventories: dict[str, dict | None] = {}
    meta = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "legacy_prompt_hash": get_prompt_version(),
        "scoped_prompt_hash": scoped_audit.get_scoped_prompt_version(),
        "model": settings.llm_claim_audit_model, "model_fallback": "disabled",
        "baseline": args.baseline, "runs": args.runs, "cap_inr": args.cap_inr, "inr_per_usd": args.inr_per_usd,
    }

    def flush(done: bool) -> None:
        meta.update({"finished": done, "stopped_by_cap": tally.stopped, "spent_inr": round(tally.inr, 2),
                     "calls": tally.calls, "input_tokens": tally.input_tokens, "output_tokens": tally.output_tokens})
        results_path.write_text(json.dumps({"meta": meta, "inventories": inventories, "rows": results}, indent=2, ensure_ascii=False), encoding="utf-8")

    def log_calls(base: dict, calls: list[dict]) -> None:
        with token_log.open("a", encoding="utf-8") as fh:
            for c in calls:
                tally.add(c)
                fh.write(json.dumps({**base, **c}) + "\n")

    if "scoped" in modes:  # inventories first: one call per paper, cached across everything
        for pid, text in papers.items():
            if tally.over_budget():
                break
            sink: list[dict] = []
            tok = engine._USAGE_SINK.set(sink)
            try:
                inv, inv_hash = await engine.get_inventory(text, f"exp1-inventory-{pid}", f"exp1-inventory-{pid}")
                inventories[pid] = {"inventory_hash": inv_hash, "items": [i.model_dump() for i in inv.items]}
                print(f"[inventory] {pid}: {len(inv.items)} items, hash {inv_hash}, cached={not sink}")
            except Exception as exc:
                inventories[pid] = None
                print(f"[error] inventory {pid}: {exc!r}")
            finally:
                engine._USAGE_SINK.reset(tok)
            log_calls({"phase": "inventory", "paper_id": pid}, sink)
            flush(False)
    if args.inventory_only or args.print_inventories:
        for pid, rec in inventories.items():
            if rec is None:
                continue
            print(f"\n=== INVENTORY {pid} (hash {rec['inventory_hash']}, {len(rec['items'])} items) ===")
            for it in rec["items"]:
                print(f"{it['id']:>5} | {it['kind']:<8} | {it['name']} | group={it['group']}")
    if args.inventory_only:
        flush(True)
        print(f"spent ~INR {tally.inr:.2f} of cap {args.cap_inr}")
        return

    sem = asyncio.Semaphore(CONCURRENCY)

    async def guarded(*a) -> dict:
        async with sem:
            if tally.over_budget():
                return {"skipped_by_cap": True}
            rec = await run_one_claim(*a)
            log_calls({"phase": "claim", "set": rec["set"], "run": rec["run"], "mode": rec["mode"],
                       "paper_id": rec["paper_id"], "claim_index": rec["claim_index"]}, rec["calls"])
            rec["input_tokens"] = sum(c.get("input_tokens") or 0 for c in rec["calls"])
            rec["output_tokens"] = sum((c.get("output_tokens") or 0) + (c.get("thinking_tokens") or 0) for c in rec["calls"])
            return rec

    for run in range(1, args.runs + 1):
        for set_id in sets:
            sel = golden_selection(set_id)
            for pid, paper in sel.items():
                for mode in modes:
                    if tally.over_budget():
                        break
                    recs = await asyncio.gather(*(
                        guarded(set_id, run, mode, pid, papers[pid], c, paper["rows"].get(c["index"], []), labels, inventories.get(pid))
                        for c in paper["claims"]
                    ))
                    results.extend(r for r in recs if not r.get("skipped_by_cap"))
                    flush(False)
                    print(f"[run {run}] set {set_id} {mode} {pid}: {len(recs)} claims; spent ~INR {tally.inr:.1f}/{args.cap_inr}")
    flush(True)
    if tally.stopped:
        print(f"STOPPED at {STOP_FRACTION:.0%} of the cap; partial results written to {results_path}")
    print(f"done. calls={tally.calls} spent ~INR {tally.inr:.2f}")
    if args.baseline == "frozen":
        print_report([r for r in results if r["mode"] == "scoped"], meta, labels, _negatives())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=["A", "B", "both"], default="both")
    ap.add_argument("--mode", choices=["legacy", "scoped", "both"], default=None)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--estimate", action="store_true", help="print the cost estimate and exit (default)")
    ap.add_argument("--execute", action="store_true", help="make PAID LLM calls (requires --cap-inr)")
    ap.add_argument("--cap-inr", type=float, default=None, help="spend cap in INR; the run stops cleanly at 90%%")
    ap.add_argument("--inr-per-usd", type=float, default=DEFAULT_INR_PER_USD)
    ap.add_argument("--inventory-only", action="store_true", help="with --execute: build and print the 3 inventories, then stop")
    ap.add_argument("--print-inventories", action="store_true", help="print every inventory in full before auditing")
    ap.add_argument("--baseline", choices=["frozen"], default=None,
                    help="frozen: scoped arm only; compare per golden row with the frozen fixture labels and evaluate the pilot marks")
    args = ap.parse_args(argv)
    if args.baseline == "frozen":
        if args.mode in ("legacy", "both"):
            ap.error("--baseline frozen is scoped-only; omit --mode or use --mode scoped")
        args.mode = "scoped"
    args.mode = args.mode or "both"
    if args.execute and args.cap_inr is None:
        ap.error("--execute requires --cap-inr")
    papers = load_papers()
    if not args.execute:
        estimate(args, papers)
        return 0
    asyncio.run(execute(args, papers))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(main())
