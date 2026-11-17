"""Scorer parts for a --table-check candidate arm (decisions.md "Pre-registration: step 4 - table checker for table
claims (text only), Vertex, 3 runs - 2026-11-15": M7, ruling 8, V6). Used by eval/score_full_check.py only when the
candidate folders are flagged runs; an unflagged arm never reaches this module. Read-only, zero LLM calls.

- folder_cost (M7): audit INR per claim of a flagged folder = every audit call (unrouted claims and fallback
  audits), every lister call and every table-checker call, each priced at the model that served it, divided by the
  folder's claim count. As for an unflagged folder, the structurer, grounding and cache creation / storage are not
  in it; the cache overhead is reported beside it.
- m7: projected INR per paper at 2027 prices = 196 + (D - Bc) x 2 x 30.17, pass if <= 200.
- row_report (ruling 8, report only): per refusal row found -> routed -> checker failed >= 1 piece -> caught, per
  run and 2-of-3 voted; S rows routed -> lowered.
- totals (ruling 8, V6): counters from each folder's _summary.json; V6 = lister + checker failures after retry
  over routed claims across all candidate folders, void above 5%.

Everything printed is ids, counts and y/n: never claim text, cell values or paper text.
"""
from pathlib import Path

from eval import pricing, score_a1

SUMMARY_KEY = "table_check"
# The call kinds of eval/replay_audit.py and eval/step4/table_check_calls.py (a test pins them to those modules;
# they are repeated here so the scorer does not import the replay's model-calling code).
KIND_AUDIT = "audit"
KIND_AUDIT_FALLBACK = "audit_fallback"
KIND_LISTER = "lister"
KIND_CHECKER = "table_checker"
COUNTED_KINDS = (KIND_AUDIT, KIND_AUDIT_FALLBACK, KIND_LISTER, KIND_CHECKER)

# M7 (constants of the entry, never parameters).
M7_BASE_INR_PER_PAPER = 196.0     # step 1d estimate at 2027 prices
M7_PRICE_FACTOR = 2.0             # 2027 price doubling
M7_CLAIMS_PER_PAPER = 30.17
M7_MAX_INR_PER_PAPER = 200.0
# V6
V6_MAX_FAILURE_SHARE = 0.05

TOTAL_COUNTERS = (
    "claims", "routed_claims", "pieces", "failed_pieces", "guard_failures", "fallback_claims", "lister_failures",
    "checker_failures",
)
TOTAL_DICTS = ("answers", "could_not_check", "guard_reasons", "fallback_reasons", "checker_labels", "unrouted")


def is_flagged(summary: dict | None) -> bool:
    return isinstance(summary, dict) and isinstance(summary.get(SUMMARY_KEY), dict)


def record_kind(record: dict) -> str | None:
    """The counted call kind of one _summary.json record; None for a call that is not counted (the structurer)."""
    stage = record.get("stage")
    if stage in (KIND_LISTER, KIND_CHECKER):
        return stage
    if record.get("is_audit"):
        return KIND_AUDIT_FALLBACK if stage == KIND_AUDIT_FALLBACK else KIND_AUDIT
    return None


# --- cost (M7) ------------------------------------------------------------------------------------------------

def folder_cost(path: Path, summary: dict, invalid: list[str]) -> dict | None:
    """A flagged folder's cost block: the keys of score_full_check._folder_cost (means are per claim here) plus
    the per-kind split and the cache overhead."""
    records = summary.get("records")
    if not isinstance(records, list):
        invalid.append(f"{path}: _summary.json has no records")
        return None
    claims = summary[SUMMARY_KEY].get("claims")
    if isinstance(claims, bool) or not isinstance(claims, int) or claims <= 0:
        invalid.append(f"{path}: _summary.json table_check block has no claim count")
        return None
    counted = [(record_kind(r), r) for r in records if isinstance(r, dict)]
    counted = [(kind, r) for kind, r in counted if kind is not None]
    usd_by_kind = {kind: 0.0 for kind in COUNTED_KINDS}
    calls_by_kind = {kind: 0 for kind in COUNTED_KINDS}
    for kind, record in counted:
        model = record.get("model_used")
        if not isinstance(model, str):
            invalid.append(f"{path}: a {kind} record has no model_used")
            return None
        try:
            usd_by_kind[kind] += pricing.strict_cost_usd_for_model(
                model, record.get("prompt_tokens") or 0, record.get("output_tokens") or 0,
                record.get("thought_tokens") or 0, record.get("cached_tokens") or 0, record.get("tool_use_tokens") or 0,
            )
        except pricing.UnpricedModelError as exc:
            invalid.append(f"{path}: {exc}")
            return None
        calls_by_kind[kind] += 1

    def mean(field: str) -> float:
        return sum((r.get(field) or 0) for _, r in counted) / claims

    total_inr = sum(usd_by_kind.values()) * pricing.INR_PER_USD
    cache_block = summary.get("cache")
    cache: dict = cache_block if isinstance(cache_block, dict) else {}
    overhead_inr = float(cache.get("overhead_usd") or 0.0) * pricing.INR_PER_USD
    return {
        "folder": str(path), "audit_calls": calls_by_kind[KIND_AUDIT] + calls_by_kind[KIND_AUDIT_FALLBACK],
        "mean_prompt_tokens": round(mean("prompt_tokens"), 1), "mean_cached_tokens": round(mean("cached_tokens"), 1),
        "mean_output_tokens": round(mean("output_tokens"), 1), "mean_thought_tokens": round(mean("thought_tokens"), 1),
        "audit_inr_per_claim": round(total_inr / claims, 4), "audit_inr_total": round(total_inr, 2),
        "table_check": True, "claims": claims, "calls_by_kind": calls_by_kind,
        "inr_by_kind": {kind: round(usd * pricing.INR_PER_USD, 2) for kind, usd in usd_by_kind.items()},
        "cache_overhead_inr": round(overhead_inr, 2),
        "audit_inr_per_claim_incl_cache_overhead": round((total_inr + overhead_inr) / claims, 4),
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def m7(dev_candidate_costs: list[dict], dev_baseline_costs: list[dict]) -> dict:
    """D and Bc are the mean dev audit INR per claim over each arm's folders. The mark uses the per-claim cost
    without cache creation / storage; the same projection with that overhead is reported beside it."""
    d = _mean([c["audit_inr_per_claim"] for c in dev_candidate_costs])
    d_incl = _mean([c.get("audit_inr_per_claim_incl_cache_overhead", c["audit_inr_per_claim"]) for c in dev_candidate_costs])
    bc = _mean([c["audit_inr_per_claim"] for c in dev_baseline_costs])

    def projected(candidate: float) -> float:
        return M7_BASE_INR_PER_PAPER + (candidate - bc) * M7_PRICE_FACTOR * M7_CLAIMS_PER_PAPER

    value = projected(d)
    return {
        "D_inr_per_claim": round(d, 4), "Bc_inr_per_claim": round(bc, 4),
        "projected_inr_per_paper": round(value, 2), "max_inr_per_paper": M7_MAX_INR_PER_PAPER,
        "pass": value <= M7_MAX_INR_PER_PAPER,
        "D_inr_per_claim_incl_cache_overhead": round(d_incl, 4),
        "projected_inr_per_paper_incl_cache_overhead": round(projected(d_incl), 2),
    }


# --- rows (ruling 8) ------------------------------------------------------------------------------------------

def _voted(flags: list[bool]) -> bool:
    return sum(1 for f in flags if f) >= score_a1.VOTES_NEEDED


def _claim_flags(claim: dict | None) -> dict:
    """found / routed / failed (the checker failed >= 1 piece) / caught (label lowered) for one claim in one run."""
    if claim is None:
        return {"found": False, "routed": False, "failed": False, "caught": False, "by_checker": False}
    trace_block = claim.get(SUMMARY_KEY)
    trace: dict = trace_block if isinstance(trace_block, dict) else {}
    routed = bool(trace.get("routed"))
    return {
        "found": True, "routed": routed,
        "failed": routed and (trace.get("n_failed") or 0) >= 1,
        "caught": claim.get("label") in score_a1.FIXED_LABELS,
        "by_checker": routed and trace.get("source") == "checker",
    }


def row_report(refusal_rows: list, s_rows: list, dirs: list[Path]) -> dict:
    """refusal_rows / s_rows: AdjudicatedRow lists (the caller picks which rows). dirs: the candidate's dev folders.
    Per refusal row: the four steps per run and voted. S rows: routed and lowered-by-the-checker ids, per run and
    voted."""
    stages = ("found", "routed", "failed", "caught")
    refusal = []
    for row in refusal_rows:
        per_run = [_claim_flags(score_a1._row_claim(row, d)) if row.claim_index is not None else _claim_flags(None)
                   for d in dirs]
        refusal.append({
            "row_id": row.row_id,
            "per_run": [{s: flags[s] for s in stages} for flags in per_run],
            "voted": {s: _voted([flags[s] for flags in per_run]) for s in stages},
        })
    s_routed_runs: list[list[str]] = [[] for _ in dirs]
    s_lowered_runs: list[list[str]] = [[] for _ in dirs]
    s_routed_voted: list[str] = []
    s_lowered_voted: list[str] = []
    for row in s_rows:
        if row.claim_index is None:
            continue
        per_run = [_claim_flags(score_a1._row_claim(row, d)) for d in dirs]
        lowered = [f["by_checker"] and f["caught"] for f in per_run]
        for i, flags in enumerate(per_run):
            if flags["routed"]:
                s_routed_runs[i].append(row.row_id)
            if lowered[i]:
                s_lowered_runs[i].append(row.row_id)
        if _voted([f["routed"] for f in per_run]):
            s_routed_voted.append(row.row_id)
        if _voted(lowered):
            s_lowered_voted.append(row.row_id)
    return {
        "folders": [str(d) for d in dirs], "refusal_rows": refusal,
        "s_rows": {
            "routed_per_run": s_routed_runs, "lowered_per_run": s_lowered_runs,
            "routed_voted": s_routed_voted, "lowered_voted": s_lowered_voted,
        },
    }


# --- totals and V6 --------------------------------------------------------------------------------------------

def folder_totals(path: Path, summary: dict) -> dict:
    block = summary[SUMMARY_KEY]
    out: dict = {"folder": str(path)}
    for key in TOTAL_COUNTERS:
        out[key] = int(block.get(key) or 0)
    for key in TOTAL_DICTS:
        out[key] = dict(block.get(key) or {})
    config = block.get("config") if isinstance(block.get("config"), dict) else {}
    out["config"] = {key: config.get(key) for key in ("lister_hash", "checker_hash", "finder_commit", "block_cap_hits")}
    return out


def totals(per_folder: list[dict]) -> dict:
    """Sums over the given folders plus the V6 line."""
    out: dict = {key: sum(f[key] for f in per_folder) for key in TOTAL_COUNTERS}
    for key in TOTAL_DICTS:
        merged: dict[str, int] = {}
        for f in per_folder:
            for name, count in f[key].items():
                merged[name] = merged.get(name, 0) + count
        out[key] = dict(sorted(merged.items()))
    failures = out["lister_failures"] + out["checker_failures"]
    routed = out["routed_claims"]
    share = failures / routed if routed else 0.0
    out["v6"] = {
        "failures_after_retry": failures, "routed_claims": routed, "share": round(share, 4),
        "max_share": V6_MAX_FAILURE_SHARE, "void": share > V6_MAX_FAILURE_SHARE,
    }
    return out


def config_differences(per_folder: list[dict]) -> list[str]:
    """INVALID reasons when the candidate folders were not run with the same lister, checker and finder."""
    reasons = []
    for key in ("lister_hash", "checker_hash", "finder_commit"):
        values = {f["config"].get(key) for f in per_folder}
        if len(values) > 1:
            reasons.append(f"table_check.{key} differs across the candidate folders: {sorted(map(str, values))}")
    return reasons


# --- printout -------------------------------------------------------------------------------------------------

def _yn(flag: bool) -> str:
    return "y" if flag else "n"


def print_report(report: dict) -> None:
    """report = {"m7": ..., "rows": ..., "per_folder": [...], "totals": ...} (score_full_check builds it)."""
    m = report["m7"]
    print("\nM7 cost gate (step 4): projected INR per paper at 2027 prices = "
          f"{M7_BASE_INR_PER_PAPER:g} + (D - Bc) x {M7_PRICE_FACTOR:g} x {M7_CLAIMS_PER_PAPER}")
    print(f"  D {m['D_inr_per_claim']} (audit + fallback audit + lister + table checker, per claim, dev mean); "
          f"Bc {m['Bc_inr_per_claim']}")
    print(f"  projected INR {m['projected_inr_per_paper']} (need <= {m['max_inr_per_paper']:g}): "
          f"{'PASS' if m['pass'] else 'FAIL'}")
    print(f"  reported only, with cache creation + storage: D {m['D_inr_per_claim_incl_cache_overhead']}, "
          f"projected INR {m['projected_inr_per_paper_incl_cache_overhead']}")

    rows = report["rows"]
    print("\nTable check, report only (no mark): refusal rows, found -> routed -> checker failed >= 1 piece -> caught")
    print("  row        " + "  ".join(f"run {i + 1}  " for i in range(len(rows["folders"]))) + "  voted")
    for row in rows["refusal_rows"]:
        runs = "  ".join("".join(_yn(run[s]) for s in ("found", "routed", "failed", "caught")) + "   " for run in row["per_run"])
        voted = "".join(_yn(row["voted"][s]) for s in ("found", "routed", "failed", "caught"))
        print(f"  {row['row_id']:<10} {runs}  {voted}")
    print("  (each group of four letters: found, routed, failed, caught)")
    s = rows["s_rows"]
    print(f"  S rows routed: per run {[len(x) for x in s['routed_per_run']]}, voted {len(s['routed_voted'])}")
    print(f"  S rows lowered by the checker: per run {[len(x) for x in s['lowered_per_run']]}, "
          f"voted {len(s['lowered_voted'])} {s['lowered_voted']}")

    print("\nTable check counts per candidate folder:")
    for f in report["per_folder"]:
        print(f"  {f['folder']}: claims {f['claims']}, routed {f['routed_claims']}, pieces {f['pieces']}, "
              f"answers {f['answers']}, failed pieces {f['failed_pieces']}, guard failures {f['guard_failures']} "
              f"{f['guard_reasons']}, fallback audits {f['fallback_claims']} {f['fallback_reasons']}, "
              f"lister failures {f['lister_failures']}, checker failures {f['checker_failures']}")
    t = report["totals"]
    print(f"  all candidate folders: claims {t['claims']}, routed {t['routed_claims']}, pieces {t['pieces']}, "
          f"answers {t['answers']}, guard failures {t['guard_failures']}, fallback audits {t['fallback_claims']}, "
          f"checker labels {t['checker_labels']}")
    v6 = t["v6"]
    print(f"  V6: lister + checker failures after retry {v6['failures_after_retry']} of {v6['routed_claims']} routed "
          f"claims = {v6['share'] * 100:.2f}% (void above {v6['max_share'] * 100:g}%): "
          f"{'VOID - THIS ARM GIVES NO RESULT' if v6['void'] else 'ok'}")
