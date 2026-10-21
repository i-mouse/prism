"""CLI: EXPLORATORY comparison, NOT a mark. Compares K1 recall at the pass-2
stage between Experiment 3's OLD pass-2 prompt (docs/evals/fixtures/dev/exp3/
pass2_r1, pass2_r2) and the clean attempt's NEW v2 prompt (docs/evals/fixtures/
dev/clean/clean_r1, clean_r2), pairing r1-with-r1 and r2-with-r2, using the
exact same fuzzy K1 method as eval/diag_k1_stages.py (reused, not
reimplemented, via its run_diagnostic() function).

INR 0, no new LLM calls (both sides are already-saved fixture output). No
`_key/` file is ever opened. The "old" side is scored with
run_diagnostic(..., no_filter=True) since exp3 has no filter stage; the "new"
side uses the default (no_filter=False) and is additionally checked against
eval.diag_k1_stages.EXPECTED_S3_COUNTS as a REGRESSION HARD STOP - if the new
side's own S3 count has drifted from the already-logged 5/13 (r1) / 6/13 (r2),
this refuses to write anything.

Prints and writes row ids, shapes (from eval.score_exp2.ROW_ID_TO_SHAPE), and
numeric scores only - never claim or sentence text.

Usage:
  uv run python -m eval.compare_k1_prompt \\
      --old-run pass2_r1:docs/evals/fixtures/dev/exp3/pass2_r1 \\
      --old-run pass2_r2:docs/evals/fixtures/dev/exp3/pass2_r2 \\
      --new-run clean_r1:docs/evals/fixtures/dev/clean/clean_r1 \\
      --new-run clean_r2:docs/evals/fixtures/dev/clean/clean_r2 \\
      --output-path docs/evals/clean_labels/k1_prompt_comparison.md
"""
import argparse
import json
from pathlib import Path
from typing import Optional

from eval.diag_k1_stages import (
    DEFAULT_DEV_EVAL_PATH,
    DEFAULT_MATCH_MAP_PATH,
    DEFAULT_RUN1_FIXTURE_DIR,
    K1_STABLE_ROWS,
    _check_hard_stop,
    _parse_named_paths,
    run_diagnostic,
)
from eval.score_exp2 import ROW_ID_TO_SHAPE

# Interpretation rule, fixed before running (low bound is the rule's basis;
# high bound is reported alongside, never changes the rule).
RECALL_LOSS_DELTA = 2


def _stage_count(result: dict, run_name: str, stage: str, bound: str) -> int:
    return result["per_run"][run_name]["counts"][stage][bound]


def _row_found_set(result: dict, run_name: str, stage: str, bound: str) -> set[str]:
    return {
        row["row_id"]
        for row in result["per_run"][run_name]["rows"]
        if row["stages"][stage][f"found_{bound}"]
    }


def _header_field(run_dir: Path, field: str) -> Optional[str]:
    """Reads one field from the first paper's _pass2.json header found in
    run_dir - used only for the confound check (model_name); never reads
    claim/sentence text."""
    for path in sorted(run_dir.glob("*_pass2.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("header", {}).get(field)
    return None


def _summary_has_thinking_level(run_dir: Path) -> bool:
    summary_path = run_dir / "_summary.json"
    if not summary_path.exists():
        return False
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if "thinking_level" in data:
        return True
    return any("thinking_level" in record for record in data.get("records", []))


def compare(
    old_run_dirs: dict[str, Path], new_run_dirs: dict[str, Path],
    dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
) -> dict:
    old_result = run_diagnostic(old_run_dirs, dev_eval_path, match_map_path, run1_fixture_dir, no_filter=True)
    new_result = run_diagnostic(new_run_dirs, dev_eval_path, match_map_path, run1_fixture_dir, no_filter=False)

    mismatches = _check_hard_stop(new_result)
    if mismatches:
        return {"hard_stop_mismatches": mismatches}

    old_names, new_names = list(old_run_dirs), list(new_run_dirs)
    pairings = list(zip(old_names, new_names))

    per_pairing = []
    for old_name, new_name in pairings:
        pairing = {"old_name": old_name, "new_name": new_name, "bounds": {}}
        for bound in ("low", "high"):
            old_counts = {s: _stage_count(old_result, old_name, s, bound) for s in ("s0", "s1", "s2")}
            new_counts = {s: _stage_count(new_result, new_name, s, bound) for s in ("s0", "s1", "s2")}
            old_s1_rows = _row_found_set(old_result, old_name, "s1", bound)
            new_s1_rows = _row_found_set(new_result, new_name, "s1", bound)
            old_not_new = sorted(old_s1_rows - new_s1_rows)
            new_not_old = sorted(new_s1_rows - old_s1_rows)
            pairing["bounds"][bound] = {
                "old_counts": old_counts, "new_counts": new_counts,
                "old_not_new": [{"row_id": r, "shape": ROW_ID_TO_SHAPE.get(r, "?")} for r in old_not_new],
                "new_not_old": [{"row_id": r, "shape": ROW_ID_TO_SHAPE.get(r, "?")} for r in new_not_old],
            }
        per_pairing.append(pairing)

    stable_both = {"old": {}, "new": {}}
    for side, result, names in (("old", old_result, old_names), ("new", new_result, new_names)):
        for bound in ("low", "high"):
            sets = [_row_found_set(result, name, "s1", bound) & K1_STABLE_ROWS for name in names]
            intersection = set.intersection(*sets) if sets else set()
            stable_both[side][bound] = len(intersection)

    rule_outcome = {}
    for bound in ("low", "high"):
        deltas = [
            p["bounds"][bound]["old_counts"]["s1"] - p["bounds"][bound]["new_counts"]["s1"]
            for p in per_pairing
        ]
        triggers = all(d >= RECALL_LOSS_DELTA for d in deltas)
        rule_outcome[bound] = {"deltas": deltas, "triggers": triggers}

    confound = {
        "old_model_name": _header_field(next(iter(old_run_dirs.values())), "model_name"),
        "new_model_name": _header_field(next(iter(new_run_dirs.values())), "model_name"),
        "old_thinking_level_field_present": any(_summary_has_thinking_level(d) for d in old_run_dirs.values()),
        "new_thinking_level_field_present": any(_summary_has_thinking_level(d) for d in new_run_dirs.values()),
    }

    return {
        "confound": confound,
        "per_pairing": per_pairing,
        "stable_both": stable_both,
        "rule_outcome": rule_outcome,
    }


def _render_report(result: dict) -> str:
    lines = ["# K1 recall comparison: exp3 OLD pass-2 prompt vs clean attempt's NEW v2 prompt", ""]
    lines.append("**EXPLORATORY - not a mark.**")
    lines.append("")
    lines.append("## Interpretation rule (fixed before running)")
    lines.append(
        f"The v2 prompt lost recall on these rows if OLD S1 >= NEW S1 + {RECALL_LOSS_DELTA} in BOTH "
        "pairings at the LOW bound. Otherwise, no clear recall loss from the prompt change. The high "
        "bound is reported alongside and never changes this rule."
    )
    lines.append("")

    lines.append("## Confound check")
    c = result["confound"]
    model_note = "SAME" if c["old_model_name"] == c["new_model_name"] else "DIFFERENT - confound"
    lines.append(f"- model_name: old={c['old_model_name']} new={c['new_model_name']} ({model_note})")
    thinking_note = (
        "no explicit thinking_level field on either side (pass-2 has never had one configured; "
        "both use the model's unconfigured default) - no confound found"
        if not c["old_thinking_level_field_present"] and not c["new_thinking_level_field_present"]
        else "thinking_level field present on at least one side - inspect before trusting the comparison"
    )
    lines.append(f"- thinking level: {thinking_note}")
    lines.append("")

    for pairing in result["per_pairing"]:
        lines.append(f"## {pairing['old_name']} (old) vs {pairing['new_name']} (new)")
        for bound in ("low", "high"):
            b = pairing["bounds"][bound]
            lines.append(f"### {bound} bound")
            lines.append("| stage | old | new |")
            lines.append("|---|---|---|")
            for stage in ("s0", "s1", "s2"):
                lines.append(f"| {stage} | {b['old_counts'][stage]} | {b['new_counts'][stage]} |")
            old_not_new = ", ".join(f"{r['row_id']}({r['shape']})" for r in b["old_not_new"]) or "none"
            new_not_old = ", ".join(f"{r['row_id']}({r['shape']})" for r in b["new_not_old"]) or "none"
            lines.append(f"- found by old, not new (S1): {old_not_new}")
            lines.append(f"- found by new, not old (S1): {new_not_old}")
        lines.append("")

    lines.append("## 7 stable rows found in both of each side's own runs (S1)")
    for bound in ("low", "high"):
        lines.append(
            f"- {bound} bound: old={result['stable_both']['old'][bound]}/7, "
            f"new={result['stable_both']['new'][bound]}/7"
        )
    lines.append("")

    lines.append("## Rule outcome")
    for bound in ("low", "high"):
        r = result["rule_outcome"][bound]
        outcome = "the v2 prompt lost recall on these rows" if r["triggers"] else "no clear recall loss from the prompt change"
        lines.append(f"- {bound} bound: deltas={r['deltas']} -> {outcome}")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old-run", action="append", dest="old_runs", required=True,
                         help="name:path, repeatable, paired positionally with --new-run")
    parser.add_argument("--new-run", action="append", dest="new_runs", required=True,
                         help="name:path, repeatable, paired positionally with --old-run")
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--output-path", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if len(args.old_runs) != len(args.new_runs):
        raise SystemExit(
            f"--old-run count ({len(args.old_runs)}) must match --new-run count ({len(args.new_runs)})"
        )

    old_run_dirs = _parse_named_paths(args.old_runs)
    new_run_dirs = _parse_named_paths(args.new_runs)
    result = compare(old_run_dirs, new_run_dirs, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir)

    if "hard_stop_mismatches" in result:
        print("HARD STOP: the 'new' side's S3 recomputation does not match the already-logged K1 FAIL numbers.")
        for m in result["hard_stop_mismatches"]:
            print(f"  MISMATCH {m}")
        raise SystemExit("refusing to write the comparison report: new-side S3 count mismatch (see above)")

    print(f"confound check: {result['confound']}")
    for pairing in result["per_pairing"]:
        print(f"{pairing['old_name']} (old) vs {pairing['new_name']} (new):")
        for bound in ("low", "high"):
            b = pairing["bounds"][bound]
            print(f"  {bound}: S0 old={b['old_counts']['s0']} new={b['new_counts']['s0']}; "
                  f"S1 old={b['old_counts']['s1']} new={b['new_counts']['s1']}; "
                  f"S2 old={b['old_counts']['s2']} new={b['new_counts']['s2']}")
    for bound in ("low", "high"):
        print(f"7 stable (S1, both own runs), {bound}: "
              f"old={result['stable_both']['old'][bound]}/7, new={result['stable_both']['new'][bound]}/7")
        r = result["rule_outcome"][bound]
        outcome = "the v2 prompt lost recall on these rows" if r["triggers"] else "no clear recall loss from the prompt change"
        print(f"rule outcome ({bound}): deltas={r['deltas']} -> {outcome}")

    args.output_path.write_text(_render_report(result), encoding="utf-8")
    print(f"wrote {args.output_path}")


if __name__ == "__main__":
    main()
