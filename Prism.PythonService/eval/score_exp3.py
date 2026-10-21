"""CLI: scores a filled-in Experiment 3 hand-adjudication file against marks
C1-C5. Zero LLM calls.

Reads the human-filled adjudication JSON (same shape as Experiment 2's: one
entry per {run, row_id, matched_claim_index, miss_cause}). Classifies each
row_id as a "target" row (run 1 extraction miss) or a "matched" row (run 1
already matched a claim to it) by reusing eval.score_replay.
resolve_adjudicated_rows - identical convention to eval/score_exp2.py, which
this file does not read from or write to.

Target rows and their claim-shape labels come ONLY from
docs/evals/exp3_targets.json (a straight copy of score_exp2.py's
ROW_ID_TO_SHAPE, made for this task so score_exp2.py stays untouched).

Marks (provisional - thresholds are all null in docs/evals/exp3_thresholds.json
until Experiment 3's pre-registration, Task B3; a null threshold means the raw
value is reported with pass=None, never a fabricated PASS/FAIL):
  C1  Target rows recovered (pass-2 windowed run vs the pass-1-only baseline).
  C2  Matched rows retained (regression check against the pass-1-only
      baseline, analogous to score_exp2.py's A3).
  C3  Total claim count ratio vs the pass-1-only baseline (analogous to
      score_exp2.py's A4).
  C4  Projected cost per paper (INR), from the run's measured tokens via
      eval.pricing.cost_inr - not computed from the adjudication file.
  C5  Recovered target rows broken down by claim shape (E1/E2/E3/E4/E5),
      informational by default (gated only if c5_min_by_shape is set).

Also reports, in every output: not_supported_count per run - the count of
target rows NOT recovered in that run (target_rows_total - recovered), i.e.
rows extraction still leaves unsupported.

Usage:
  uv run python -m eval.score_exp3 --adjudication-path docs/evals/fixtures/dev/exp3/adjudication_filled.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from eval.pricing import cost_inr
from eval.score_replay import resolve_adjudicated_rows

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_REPLAY_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp3"
DEFAULT_TARGETS_PATH = REPO_ROOT / "docs" / "evals" / "exp3_targets.json"
DEFAULT_THRESHOLDS_PATH = REPO_ROOT / "docs" / "evals" / "exp3_thresholds.json"


def _load_targets(targets_path: Path) -> dict[str, str]:
    data = json.loads(targets_path.read_text(encoding="utf-8"))
    return data["row_id_to_shape"]


def _load_thresholds(thresholds_path: Path) -> dict:
    return json.loads(thresholds_path.read_text(encoding="utf-8"))


def _classify_rows(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path) -> tuple[set[str], set[str]]:
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    target_ids = {row.row_id for row in rows if row.claim_index is None}
    matched_ids = {row.row_id for row in rows if row.claim_index is not None}
    return target_ids, matched_ids


def _count_recovered(adjudication: list[dict], run_name: str, row_ids: set[str]) -> int:
    return sum(
        1 for entry in adjudication
        if entry["run"] == run_name and entry["row_id"] in row_ids and entry["matched_claim_index"] is not None
    )


def _recovered_by_shape(adjudication: list[dict], run_name: str, target_ids: set[str], row_id_to_shape: dict[str, str]) -> dict[str, int]:
    counts = {shape: 0 for shape in ("E1", "E2", "E3", "E4", "E5")}
    for entry in adjudication:
        if entry["run"] != run_name or entry["row_id"] not in target_ids:
            continue
        if entry["matched_claim_index"] is None:
            continue
        shape = row_id_to_shape.get(entry["row_id"], "unknown")
        counts[shape] = counts.get(shape, 0) + 1
    return counts


def _miss_causes(adjudication: list[dict], run_name: str, target_ids: set[str]) -> Counter:
    counts: Counter = Counter()
    for entry in adjudication:
        if entry["run"] != run_name or entry["row_id"] not in target_ids:
            continue
        if entry["matched_claim_index"] is not None:
            continue
        counts[entry.get("miss_cause") or "unspecified"] += 1
    return counts


def _total_claims(replay_root: Path, run_name: str) -> int:
    run_dir = replay_root / run_name
    if not run_dir.exists():
        raise FileNotFoundError(f"replay fixture directory not found: {run_dir}")
    total = 0
    for path in run_dir.glob("*_merged.json"):
        total += len(json.loads(path.read_text(encoding="utf-8"))["claims"])
    return total


def _papers_replayed(replay_root: Path, run_name: str) -> int:
    run_dir = replay_root / run_name
    if not run_dir.exists():
        raise FileNotFoundError(f"replay fixture directory not found: {run_dir}")
    return len(list(run_dir.glob("*_merged.json")))


def _run_cost_inr(replay_root: Path, run_name: str) -> float:
    summary_path = replay_root / run_name / "_summary.json"
    if not summary_path.exists():
        return 0.0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return summary.get("cost_inr", 0.0)


def score(
    adjudication_path: Path, dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
    replay_root: Path, targets_path: Path, thresholds_path: Path,
    baseline_run: str, pass2_runs: list[str],
) -> dict:
    adjudication = json.loads(adjudication_path.read_text(encoding="utf-8"))
    row_id_to_shape = _load_targets(targets_path)
    thresholds = _load_thresholds(thresholds_path)
    target_ids, matched_ids = _classify_rows(dev_eval_path, match_map_path, run1_fixture_dir)

    baseline_recovered = _count_recovered(adjudication, baseline_run, target_ids)
    pass2_recovered = {run: _count_recovered(adjudication, run, target_ids) for run in pass2_runs}
    pass2_matched_retained = {run: _count_recovered(adjudication, run, matched_ids) for run in pass2_runs}

    baseline_claims = _total_claims(replay_root, baseline_run)
    pass2_claims = {run: _total_claims(replay_root, run) for run in pass2_runs}

    not_supported_count = {
        baseline_run: len(target_ids) - baseline_recovered,
        **{run: len(target_ids) - pass2_recovered[run] for run in pass2_runs},
    }

    def _pass(threshold, actual_ge) -> bool | None:
        return None if threshold is None else actual_ge >= threshold

    c1_values = pass2_recovered
    c1_pass = {run: _pass(thresholds.get("c1_min_recovered"), c1_values[run]) for run in pass2_runs}

    c2_values = pass2_matched_retained
    c2_pass = {run: _pass(thresholds.get("c2_min_matched_retained"), c2_values[run]) for run in pass2_runs}

    c3_max_ratio = thresholds.get("c3_max_claim_ratio")
    c3_ratio = {run: (pass2_claims[run] / baseline_claims if baseline_claims else None) for run in pass2_runs}
    c3_pass = {
        run: (None if c3_max_ratio is None or c3_ratio[run] is None else c3_ratio[run] <= c3_max_ratio)
        for run in pass2_runs
    }

    c4_max_cost = thresholds.get("c4_max_cost_inr_per_paper")
    c4_papers_replayed = {run: _papers_replayed(replay_root, run) for run in pass2_runs}
    c4_cost_per_paper = {
        run: (_run_cost_inr(replay_root, run) / c4_papers_replayed[run] if c4_papers_replayed[run] else 0.0)
        for run in pass2_runs
    }
    c4_pass = {
        run: (None if c4_max_cost is None else c4_cost_per_paper[run] <= c4_max_cost)
        for run in pass2_runs
    }

    c5_by_shape = {baseline_run: _recovered_by_shape(adjudication, baseline_run, target_ids, row_id_to_shape)}
    c5_by_shape.update({run: _recovered_by_shape(adjudication, run, target_ids, row_id_to_shape) for run in pass2_runs})
    c5_min_by_shape = thresholds.get("c5_min_by_shape")
    c5_pass = (
        None if c5_min_by_shape is None
        else {run: all(c5_by_shape[run].get(s, 0) >= v for s, v in c5_min_by_shape.items()) for run in pass2_runs}
    )

    miss_causes = {baseline_run: _miss_causes(adjudication, baseline_run, target_ids)}
    miss_causes.update({run: _miss_causes(adjudication, run, target_ids) for run in pass2_runs})

    return {
        "target_rows_total": len(target_ids),
        "matched_rows_total": len(matched_ids),
        "baseline_recovered": baseline_recovered,
        "c1_recovered": c1_values, "c1_pass": c1_pass,
        "c2_matched_retained": c2_values, "c2_pass": c2_pass,
        "c3_claim_ratio": c3_ratio, "c3_pass": c3_pass,
        "c4_cost_inr_per_paper": c4_cost_per_paper, "c4_pass": c4_pass,
        "c5_recovered_by_shape": c5_by_shape, "c5_pass": c5_pass,
        "not_supported_count": not_supported_count,
        "miss_causes": miss_causes,
        "baseline_claims": baseline_claims,
        "pass2_claims": pass2_claims,
    }


def _fmt_pass(value: bool | None) -> str:
    if value is None:
        return "UNDETERMINED (threshold not set until B3 pre-registration)"
    return "PASS" if value else "FAIL"


def _print_report(result: dict, baseline_run: str, pass2_runs: list[str]) -> None:
    print(f"target rows: {result['target_rows_total']}, matched rows: {result['matched_rows_total']}")
    print(f"baseline ({baseline_run}) recovered: {result['baseline_recovered']}/{result['target_rows_total']}")
    for run in pass2_runs:
        print(f"  {run}: C1 recovered={result['c1_recovered'][run]}/{result['target_rows_total']} [{_fmt_pass(result['c1_pass'][run])}]")
        print(f"  {run}: C2 matched_retained={result['c2_matched_retained'][run]}/{result['matched_rows_total']} [{_fmt_pass(result['c2_pass'][run])}]")
        print(f"  {run}: C3 claim_ratio={result['c3_claim_ratio'][run]} [{_fmt_pass(result['c3_pass'][run])}]")
        print(f"  {run}: C4 cost_inr_per_paper={result['c4_cost_inr_per_paper'][run]:.2f} [{_fmt_pass(result['c4_pass'][run])}]")
        c5_status = result['c5_pass'] if result['c5_pass'] is None else result['c5_pass'].get(run)
        print(f"  {run}: C5 recovered_by_shape={result['c5_recovered_by_shape'][run]} [{_fmt_pass(c5_status)}]")
    print()
    print("not_supported_count (target rows still unsupported, per run):")
    for run_name, count in result["not_supported_count"].items():
        print(f"  {run_name}: {count}/{result['target_rows_total']}")
    print()
    print("miss_cause counts per run, for target rows NOT recovered (informational):")
    for run_name in (baseline_run, *pass2_runs):
        causes = result["miss_causes"][run_name]
        if not causes:
            print(f"  {run_name}: no un-recovered target rows in this adjudication")
            continue
        breakdown = ", ".join(f"{cause}={count}" for cause, count in sorted(causes.items()))
        print(f"  {run_name}: {breakdown}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adjudication-path", type=Path, required=True)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--replay-root", type=Path, default=DEFAULT_REPLAY_ROOT)
    parser.add_argument("--targets-path", type=Path, default=DEFAULT_TARGETS_PATH)
    parser.add_argument("--thresholds-path", type=Path, default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--baseline-run", default="pass1_only", help="pass-1-only baseline run name")
    parser.add_argument("--pass2-runs", default="pass2_r1", help="comma-separated pass-1+pass-2 run names")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    pass2_runs = [r.strip() for r in args.pass2_runs.split(",")]
    result = score(
        args.adjudication_path, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir,
        args.replay_root, args.targets_path, args.thresholds_path,
        args.baseline_run, pass2_runs,
    )
    _print_report(result, args.baseline_run, pass2_runs)


if __name__ == "__main__":
    main()
