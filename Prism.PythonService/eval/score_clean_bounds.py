"""CLI: scores the clean-extraction attempt's marks K1-K8 under the bounded
method logged in docs/decisions.md, "Clean-extraction attempt: spot-check
result, diagnostic, bounded scoring - 2026-10-20".

  K2, K4, K5, K8  computed directly from each run's own output files, same
      as eval/score_clean.py - no AI-judged bound, one value.
  K3              report-only (docs/decisions.md, 2026-10-18): r is printed,
      no PASS/FAIL verdict, excluded from the overall line.
  K6, K7          scored twice each (low/high bound labels) against the
      same sealed key, via eval/score_label_pack.py's score_k6/score_k7.
      This is the only place a key file (k6/_key, k7/_key) is opened.
  K1              NEW method, no key/adjudication file involved: each of
      the 13 target rows (from eval.score_replay.resolve_adjudicated_rows +
      eval.score_exp2.ROW_ID_TO_SHAPE) is fuzzy-matched against every claim
      in the run's final cleaned claim list, on normalize_for_match text
      (eval.inventory_compare, which avoids extraction.grounding's .env
      read). fuzz.ratio >= 90 -> found in both bounds. fuzz.ratio in
      [60, 89] or fuzz.partial_ratio >= 90 -> found only in the high bound.
      Otherwise not found.

Per-mark verdict (K1, K6, K7 - the AI/bound-dependent marks): both bounds
pass -> PASS; both fail -> FAIL; otherwise -> INCONCLUSIVE (counts as not
passed). K2/K4/K5/K8 have a single PASS/FAIL (no bound). K3 has no verdict.
Overall: FAIL if any mark FAILs; else INCONCLUSIVE if any mark is
INCONCLUSIVE; else PASS. K3 excluded.

No LLM calls. No git. Writes one report file with the sha256 of every
labels file used; does not touch docs/decisions.md.

Usage:
  uv run python -m eval.score_clean_bounds \\
      --run clean_r1:docs/evals/fixtures/dev/clean/clean_r1 \\
      --run clean_r2:docs/evals/fixtures/dev/clean/clean_r2 \\
      --k6-key docs/evals/clean_labels/k6/_key/k6_key.json \\
      --k6-labels-low docs/evals/clean_labels/k6/k6_labels_low.csv \\
      --k6-labels-high docs/evals/clean_labels/k6/k6_labels_high.csv \\
      --k7-key docs/evals/clean_labels/k7/_key/k7_key.json \\
      --k7-labels-low docs/evals/clean_labels/k7/k7_labels_low.csv \\
      --k7-labels-high docs/evals/clean_labels/k7/k7_labels_high.csv \\
      --output-path docs/evals/clean_labels/clean_attempt_score.md
"""
import argparse
import json
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from eval.blind_review import sha256_file
from eval.inventory_compare import normalize_for_match
from eval.score_clean import (
    C4_MAX_INR,
    K1_STABLE_ROWS,
    K3_MAX_R,
    K5_MIN_RATE,
    K8_ATTEMPT_MAX_INR,
    K8_FILTER_MAX_INR,
    _final_claims,
    _paper_ids,
    score_k2,
    score_k3_k4,
    score_k5,
    score_k8,
)
from eval.score_exp2 import ROW_ID_TO_SHAPE
from eval.score_label_pack import (
    K6_LABELS,
    K7_LABELS,
    K6_MIN_PRECISION,
    K7_MAX_NOT_SAME,
    load_labels,
    score_k6,
    score_k7,
    validate_against_key,
)
from eval.score_replay import resolve_adjudicated_rows

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"

K1_TARGET_TOTAL = 13
# docs/decisions.md 2026-10-19 "about INR 6.4 spent so far" (pilot, before run 1/run 2).
PRE_FULL_RUN_PILOT_COST_INR = 6.4


# --------------------------------------------------------------------------
# K1: 13 target rows vs every claim in the run's final cleaned claim list
# --------------------------------------------------------------------------

def _k1_target_rows(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path) -> list[dict]:
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    return [
        {"row_id": row.row_id, "paper_id": row.paper_id, "claim_text_verbatim": row.expected_row.claim_text_verbatim}
        for row in rows if row.claim_index is None and row.row_id in ROW_ID_TO_SHAPE
    ]


def _k1_band(ratio: float, partial: float) -> str:
    """"both" -> found in low and high bound. "high" -> found only in the
    high (best-case) bound. "none" -> not found in either."""
    if ratio >= 90:
        return "both"
    if ratio >= 60 or partial >= 90:
        return "high"
    return "none"


def _best_match(row_norm: str, run_dir: Path) -> tuple[float, float]:
    best_ratio = 0.0
    best_partial = 0.0
    for paper_id in _paper_ids(run_dir):
        for claim in _final_claims(run_dir, paper_id):
            claim_norm = normalize_for_match(claim["claim_text_verbatim"])
            ratio = fuzz.ratio(row_norm, claim_norm)
            partial = fuzz.partial_ratio(row_norm, claim_norm)
            if ratio > best_ratio:
                best_ratio = ratio
            if partial > best_partial:
                best_partial = partial
    return best_ratio, best_partial


def score_k1_bounds(
    run_dirs: dict[str, Path], dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
) -> dict:
    target_rows = _k1_target_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    per_run = {}
    for run_name, run_dir in run_dirs.items():
        found_low: set[str] = set()
        found_high: set[str] = set()
        for row in target_rows:
            row_norm = normalize_for_match(row["claim_text_verbatim"])
            ratio, partial = _best_match(row_norm, run_dir)
            band = _k1_band(ratio, partial)
            if band == "both":
                found_low.add(row["row_id"])
                found_high.add(row["row_id"])
            elif band == "high":
                found_high.add(row["row_id"])
        per_run[run_name] = {
            "found_low": sorted(found_low), "found_high": sorted(found_high),
            "found_low_count": len(found_low), "found_high_count": len(found_high),
            "stable_found_low": sorted(found_low & K1_STABLE_ROWS),
            "stable_found_high": sorted(found_high & K1_STABLE_ROWS),
        }

    stable_both_low = set(K1_STABLE_ROWS)
    stable_both_high = set(K1_STABLE_ROWS)
    for run_data in per_run.values():
        stable_both_low &= set(run_data["stable_found_low"])
        stable_both_high &= set(run_data["stable_found_high"])

    target_total = len(target_rows)
    return {
        "target_total": target_total,
        "per_run": per_run,
        "stable_both_runs_low": sorted(stable_both_low),
        "stable_both_runs_high": sorted(stable_both_high),
        "stable_both_runs_low_count": len(stable_both_low),
        "stable_both_runs_high_count": len(stable_both_high),
        "pass_low": len(stable_both_low) >= len(K1_STABLE_ROWS),
        "pass_high": len(stable_both_high) >= len(K1_STABLE_ROWS),
    }


# --------------------------------------------------------------------------
# K6 / K7 bounds
# --------------------------------------------------------------------------

def _score_label_bound(mode: str, labels_path: Path, key_path: Path) -> dict:
    allowed = K6_LABELS if mode == "k6" else K7_LABELS
    key_doc = json.loads(key_path.read_text(encoding="utf-8"))
    key_items = key_doc["items"]

    labels, errors = load_labels(labels_path, allowed)
    errors = validate_against_key(labels, list(key_items.keys()), errors)
    if errors:
        raise SystemExit(f"refusing to score {labels_path}: {len(errors)} invalid/missing label(s): {errors}")

    result = score_k6(labels, key_items) if mode == "k6" else score_k7(labels, key_items)
    result["labels_sha256"] = sha256_file(labels_path)
    return result


# --------------------------------------------------------------------------
# Verdict combination
# --------------------------------------------------------------------------

def _bound_verdict(low_pass: bool, high_pass: bool) -> str:
    if low_pass and high_pass:
        return "PASS"
    if not low_pass and not high_pass:
        return "FAIL"
    return "INCONCLUSIVE"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _parse_named_paths(values: Optional[list[str]]) -> dict[str, Path]:
    out = {}
    for value in values or []:
        name, path = value.split(":", 1)
        out[name] = Path(path)
    return out


def _render_report(result: dict) -> str:
    lines = ["# Clean-extraction attempt - bounded score (2026-10-20)", ""]

    lines.append("## K1 (13 target rows, 7 stable rows; no key, no human judgement)")
    for run_name, data in result["k1"]["per_run"].items():
        lines.append(
            f"- {run_name}: found {data['found_low_count']}/{result['k1']['target_total']} (low), "
            f"{data['found_high_count']}/{result['k1']['target_total']} (high)"
        )
    lines.append(
        f"- 7 stable rows found in BOTH runs: "
        f"{result['k1']['stable_both_runs_low_count']}/7 (low), "
        f"{result['k1']['stable_both_runs_high_count']}/7 (high)"
    )
    lines.append(f"- verdict: {result['verdicts']['k1']}")
    lines.append("")

    lines.append("## K2 (filter never touches pass 1)")
    for run_name, data in result["k2"].items():
        lines.append(f"- {run_name}: retained {data['retained']}/{data['scope']}, pass={data['pass']}")
    lines.append(f"- verdict: {result['verdicts']['k2']}")
    lines.append("")

    lines.append(f"## K3 (report only, docs/decisions.md 2026-10-18 - threshold r <= {K3_MAX_R})")
    lines.append(f"- mean reading: r={result['k3_k4']['k3_k4_mean_reading']['r']:.4f}")
    lines.append(f"- pooled reading: r={result['k3_k4']['k3_k4_pooled_reading']['r']:.4f}")
    lines.append("- no verdict (report only)")
    lines.append("")

    lines.append(f"## K4 (projected cost per paper <= INR {C4_MAX_INR})")
    lines.append(f"- mean reading: projected=INR {result['k3_k4']['k3_k4_mean_reading']['projected_inr']:.2f}, "
                  f"pass={result['k3_k4']['k3_k4_mean_reading']['k4_pass']}")
    lines.append(f"- pooled reading: projected=INR {result['k3_k4']['k3_k4_pooled_reading']['projected_inr']:.2f}, "
                  f"pass={result['k3_k4']['k3_k4_pooled_reading']['k4_pass']}")
    lines.append(f"- verdict: {result['verdicts']['k4']}")
    lines.append("")

    lines.append(f"## K5 (pass-2 Stage-1 grounding rate >= {K5_MIN_RATE})")
    for run_name, data in result["k5"].items():
        rate = f"{data['rate']:.4f}" if data["rate"] is not None else "n/a"
        lines.append(f"- {run_name}: rate={rate}, pass={data['pass']}")
    lines.append(f"- verdict: {result['verdicts']['k5']}")
    lines.append("")

    lines.append(f"## K6 (precision, unsure as not-claim, >= {K6_MIN_PRECISION})")
    lines.append(f"- low: n={result['k6']['low']['n']}, precision={result['k6']['low']['precision_unsure_not_claim']:.4f}, "
                 f"pass={result['k6']['low']['pass']}")
    lines.append(f"- high: n={result['k6']['high']['n']}, precision={result['k6']['high']['precision_unsure_not_claim']:.4f}, "
                 f"pass={result['k6']['high']['pass']}")
    lines.append(f"- verdict: {result['verdicts']['k6']}")
    lines.append("")

    lines.append(f"## K7 (not-same count, unsure as not-same, <= {K7_MAX_NOT_SAME})")
    lines.append(f"- low: n={result['k7']['low']['n']}, not_same={result['k7']['low']['not_same_count']}, "
                 f"pass={result['k7']['low']['pass']}")
    lines.append(f"- high: n={result['k7']['high']['n']}, not_same={result['k7']['high']['not_same_count']}, "
                 f"pass={result['k7']['high']['pass']}")
    lines.append(f"- verdict: {result['verdicts']['k7']}")
    lines.append("")

    lines.append(f"## K8 (filter spend; per-run <= INR {K8_FILTER_MAX_INR}, attempt total <= INR {K8_ATTEMPT_MAX_INR})")
    for run_name, data in result["k8"]["per_run"].items():
        lines.append(f"- {run_name}: filter_cost_inr={data['filter_cost_inr']:.2f}, pass={data['pass']}")
    lines.append(
        f"- attempt total: pilot INR {PRE_FULL_RUN_PILOT_COST_INR:.2f} (docs/decisions.md 2026-10-19) + "
        f"this attempt's two full runs INR {result['k8']['attempt_total_this_runs_inr']:.2f} = "
        f"INR {result['k8']['attempt_total_inr']:.2f}, pass={result['k8']['attempt_total_pass']}"
    )
    lines.append(f"- verdict: {result['verdicts']['k8']}")
    lines.append("")

    lines.append(f"## Overall: {result['overall']}")
    lines.append("")

    lines.append("## Labels files used (sha256)")
    for key, sha in result["labels_sha256"].items():
        lines.append(f"- {key}: {sha}")
    lines.append("- k1: none (new method reads no labels/key file)")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", dest="runs", required=True,
                         help="name:path, repeatable, e.g. clean_r1:docs/evals/fixtures/dev/clean/clean_r1")
    parser.add_argument("--k6-key", type=Path, required=True)
    parser.add_argument("--k6-labels-low", type=Path, required=True)
    parser.add_argument("--k6-labels-high", type=Path, required=True)
    parser.add_argument("--k7-key", type=Path, required=True)
    parser.add_argument("--k7-labels-low", type=Path, required=True)
    parser.add_argument("--k7-labels-high", type=Path, required=True)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--output-path", type=Path, required=True)
    args = parser.parse_args()

    run_dirs = _parse_named_paths(args.runs)

    k2 = {run: score_k2(run_dir, args.dev_eval_path, args.match_map_path) for run, run_dir in run_dirs.items()}
    k3_k4 = score_k3_k4(run_dirs)
    k5 = score_k5(run_dirs)
    k8 = score_k8(run_dirs)
    k1 = score_k1_bounds(run_dirs, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir)

    k6_low = _score_label_bound("k6", args.k6_labels_low, args.k6_key)
    k6_high = _score_label_bound("k6", args.k6_labels_high, args.k6_key)
    k7_low = _score_label_bound("k7", args.k7_labels_low, args.k7_key)
    k7_high = _score_label_bound("k7", args.k7_labels_high, args.k7_key)

    attempt_total_this_runs = sum(
        json.loads((run_dir / "_summary.json").read_text(encoding="utf-8")).get("pass2_cost_inr", 0.0)
        + json.loads((run_dir / "_summary.json").read_text(encoding="utf-8")).get("filter_cost_inr", 0.0)
        for run_dir in run_dirs.values()
    )
    attempt_total_inr = PRE_FULL_RUN_PILOT_COST_INR + attempt_total_this_runs
    k8["attempt_total_this_runs_inr"] = attempt_total_this_runs
    k8["attempt_total_inr"] = attempt_total_inr
    k8["attempt_total_pass"] = attempt_total_inr <= K8_ATTEMPT_MAX_INR

    verdicts = {
        "k1": _bound_verdict(k1["pass_low"], k1["pass_high"]),
        "k2": "PASS" if all(d["pass"] for d in k2.values()) else "FAIL",
        "k4": "PASS" if (k3_k4["k3_k4_mean_reading"]["k4_pass"] and k3_k4["k3_k4_pooled_reading"]["k4_pass"]) else "FAIL",
        "k5": "PASS" if all(d["pass"] for d in k5.values()) else "FAIL",
        "k6": _bound_verdict(k6_low["pass"], k6_high["pass"]),
        "k7": _bound_verdict(k7_low["pass"], k7_high["pass"]),
        "k8": "PASS" if (all(d["pass"] for d in k8["per_run"].values()) and k8["attempt_total_pass"]) else "FAIL",
    }
    if any(v == "FAIL" for v in verdicts.values()):
        overall = "FAIL"
    elif any(v == "INCONCLUSIVE" for v in verdicts.values()):
        overall = "INCONCLUSIVE"
    else:
        overall = "PASS"

    result = {
        "k1": k1, "k2": k2, "k3_k4": k3_k4, "k5": k5, "k8": k8,
        "k6": {"low": k6_low, "high": k6_high},
        "k7": {"low": k7_low, "high": k7_high},
        "verdicts": verdicts,
        "overall": overall,
        "labels_sha256": {
            "k6_low": k6_low["labels_sha256"], "k6_high": k6_high["labels_sha256"],
            "k7_low": k7_low["labels_sha256"], "k7_high": k7_high["labels_sha256"],
        },
    }

    print(f"K1 (13 target rows): " + ", ".join(
        f"{run}={d['found_low_count']}/{result['k1']['target_total']} low, "
        f"{d['found_high_count']}/{result['k1']['target_total']} high"
        for run, d in k1["per_run"].items()
    ))
    print(f"K1 (7 stable, found in both runs): {k1['stable_both_runs_low_count']}/7 low, "
          f"{k1['stable_both_runs_high_count']}/7 high -> {verdicts['k1']}")
    print("K2: " + ", ".join(f"{run}={d['pass']}" for run, d in k2.items()) + f" -> {verdicts['k2']}")
    print(f"K3 (report only): r_mean={k3_k4['k3_k4_mean_reading']['r']:.4f}, "
          f"r_pooled={k3_k4['k3_k4_pooled_reading']['r']:.4f}")
    print(f"K4: projected_mean=INR {k3_k4['k3_k4_mean_reading']['projected_inr']:.2f}, "
          f"projected_pooled=INR {k3_k4['k3_k4_pooled_reading']['projected_inr']:.2f} -> {verdicts['k4']}")
    print("K5: " + ", ".join(f"{run}={d['pass']}" for run, d in k5.items()) + f" -> {verdicts['k5']}")
    print(f"K6: low precision={k6_low['precision_unsure_not_claim']:.4f}, "
          f"high precision={k6_high['precision_unsure_not_claim']:.4f} (gate {K6_MIN_PRECISION}) -> {verdicts['k6']}")
    print(f"K7: low not_same={k7_low['not_same_count']}, high not_same={k7_high['not_same_count']} "
          f"(gate <= {K7_MAX_NOT_SAME}) -> {verdicts['k7']}")
    print(f"K8: attempt total=INR {attempt_total_inr:.2f} (gate <= {K8_ATTEMPT_MAX_INR}) -> {verdicts['k8']}")
    print(f"OVERALL: {overall}")

    args.output_path.write_text(_render_report(result), encoding="utf-8")
    print(f"wrote {args.output_path}")


if __name__ == "__main__":
    main()
