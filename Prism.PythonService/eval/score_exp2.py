"""CLI: scores a filled-in Experiment 2 (redesigned) adjudication file
against marks A1-A4 from the decisions.md pre-registration entry.

Reads the human-filled adjudication JSON (eval/build_exp2_review_pack.py
writes the all-null template, now with a miss_cause: null field per entry; a
human fills in matched_claim_index or confirms null, and - for a target row
still null (not recovered) - a miss_cause). Classifies each row_id as a
"target" row (run 1 extraction miss, confirmed_no_match in
dev_match_map.json) or a "matched" row (run 1 already matched a claim to it)
by reusing eval.score_replay.resolve_adjudicated_rows. Zero LLM calls.

Marks (from the Experiment 2 pre-registration entry):
  A1  At least 5/13 target rows recovered in BOTH treatment runs independently.
  A2  min(treatment recovered) - control recovered >= 3.
  A3  Each treatment run keeps at least 17/18 matched rows (no regression).
  A4  Treatment's total claim count is at most 1.5x control's, in every
      treatment run (checked against the replay fixtures under --replay-root,
      not the adjudication file).
Accept only if all four pass.

Also reports, informationally (not gating):
  - recovered rows broken down by claim-shape (E1/E2/E3/E4/E5), for control and
    every treatment run separately. E3 is the one to watch: control (loader
    fix on, shapes off) already un-blanks a note-bearing base example
    (abstract_broad_and_narrow_together) that teaches nearly the same lesson
    as the E3 shape, so a high E3 recovery in control alone - not just
    treatment - points to the loader fix as the cause rather than the new
    shape-specific examples (see docs/decisions.md's Experiment 2
    (redesigned) pre-registration, "E3 attribution check").
  - miss_cause counts per run, for target rows NOT recovered (shape_not_taught
    | saw_example_still_skipped | split_or_merged_differently | other |
    unspecified).

Usage:
  uv run python -m eval.score_exp2 --adjudication-path docs/evals/fixtures/dev/exp2/adjudication_filled.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from eval.score_replay import resolve_adjudicated_rows

MISS_CAUSES = ("shape_not_taught", "saw_example_still_skipped", "split_or_merged_differently", "other")

# The 13 confirmed run-1 extraction-miss target rows, by claim shape (E4's
# P11-R1 is out of scope for the new examples - overlaps the existing "do not
# extract implementation details" rule - but still counts toward A1/A2/A3's
# combined totals since it's still one of the 13 target rows).
ROW_ID_TO_SHAPE = {
    "P7-R2": "E1", "P2-R1": "E1", "P1-R2": "E1", "P12-R1": "E1",
    "P2-R3": "E2", "P2-R4": "E2", "P9-R1": "E2",
    "P4-R3": "E3", "P3-R1": "E3", "P5-R3": "E3", "P8-R3": "E3",
    "P11-R1": "E4",
    "P11-R3": "E5",
}

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_REPLAY_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp2"

A1_FLOOR = 5
A2_MIN_GAIN = 3
A3_FLOOR = 17
A4_MAX_RATIO = 1.5


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


def _recovered_by_shape(adjudication: list[dict], run_name: str, target_ids: set[str]) -> dict[str, int]:
    counts = {shape: 0 for shape in ("E1", "E2", "E3", "E4", "E5")}
    for entry in adjudication:
        if entry["run"] != run_name or entry["row_id"] not in target_ids:
            continue
        if entry["matched_claim_index"] is None:
            continue
        shape = ROW_ID_TO_SHAPE.get(entry["row_id"], "unknown")
        counts[shape] = counts.get(shape, 0) + 1
    return counts


def _miss_causes(adjudication: list[dict], run_name: str, target_ids: set[str]) -> Counter:
    counts: Counter = Counter()
    for entry in adjudication:
        if entry["run"] != run_name or entry["row_id"] not in target_ids:
            continue
        if entry["matched_claim_index"] is not None:
            continue  # recovered, not a miss
        cause = entry.get("miss_cause") or "unspecified"
        counts[cause] += 1
    return counts


def _total_claims(replay_root: Path, run_name: str) -> int:
    run_dir = replay_root / run_name
    if not run_dir.exists():
        raise FileNotFoundError(f"replay fixture directory not found: {run_dir}")
    total = 0
    for path in run_dir.glob("*.json"):
        if path.name == "_summary.json":
            continue
        total += len(json.loads(path.read_text(encoding="utf-8"))["claims"])
    return total


def score(
    adjudication_path: Path, dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
    replay_root: Path, control_run: str, treatment_runs: list[str],
) -> dict:
    adjudication = json.loads(adjudication_path.read_text(encoding="utf-8"))
    target_ids, matched_ids = _classify_rows(dev_eval_path, match_map_path, run1_fixture_dir)

    control_recovered = _count_recovered(adjudication, control_run, target_ids)
    treatment_recovered = {run: _count_recovered(adjudication, run, target_ids) for run in treatment_runs}
    treatment_matched_retained = {run: _count_recovered(adjudication, run, matched_ids) for run in treatment_runs}

    control_claims = _total_claims(replay_root, control_run)
    treatment_claims = {run: _total_claims(replay_root, run) for run in treatment_runs}

    a1_pass = all(treatment_recovered[run] >= A1_FLOOR for run in treatment_runs)
    a2_pass = (min(treatment_recovered.values()) - control_recovered) >= A2_MIN_GAIN if treatment_recovered else False
    a3_pass = all(treatment_matched_retained[run] >= A3_FLOOR for run in treatment_runs)
    a4_pass = all(treatment_claims[run] <= A4_MAX_RATIO * control_claims for run in treatment_runs)

    recovered_by_shape = {control_run: _recovered_by_shape(adjudication, control_run, target_ids)}
    recovered_by_shape.update({run: _recovered_by_shape(adjudication, run, target_ids) for run in treatment_runs})

    miss_causes = {control_run: _miss_causes(adjudication, control_run, target_ids)}
    miss_causes.update({run: _miss_causes(adjudication, run, target_ids) for run in treatment_runs})

    return {
        "target_rows_total": len(target_ids),
        "matched_rows_total": len(matched_ids),
        "control_recovered": control_recovered,
        "treatment_recovered": treatment_recovered,
        "treatment_matched_retained": treatment_matched_retained,
        "control_claims": control_claims,
        "treatment_claims": treatment_claims,
        "recovered_by_shape": recovered_by_shape,
        "miss_causes": miss_causes,
        "a1_pass": a1_pass,
        "a2_pass": a2_pass,
        "a3_pass": a3_pass,
        "a4_pass": a4_pass,
        "overall_pass": a1_pass and a2_pass and a3_pass and a4_pass,
    }


def _print_report(result: dict, control_run: str, treatment_runs: list[str]) -> None:
    def _mark(name: str, passed: bool) -> str:
        return f"{name}: {'PASS' if passed else 'FAIL'}"

    print(f"target rows: {result['target_rows_total']}, matched rows: {result['matched_rows_total']}")
    print(f"control ({control_run}) recovered: {result['control_recovered']}/{result['target_rows_total']}")
    for run in treatment_runs:
        print(f"treatment ({run}) recovered: {result['treatment_recovered'][run]}/{result['target_rows_total']}, "
              f"matched retained: {result['treatment_matched_retained'][run]}/{result['matched_rows_total']}")
    print()
    print(_mark(f"A1 (>= {A1_FLOOR}/{result['target_rows_total']} recovered in both treatment runs)", result["a1_pass"]))
    print(_mark(f"A2 (min(treatment) - control >= {A2_MIN_GAIN})", result["a2_pass"]))
    print(_mark(f"A3 (>= {A3_FLOOR}/{result['matched_rows_total']} matched rows kept in every treatment run)", result["a3_pass"]))
    print(_mark(f"A4 (treatment claims <= {A4_MAX_RATIO}x control claims, control={result['control_claims']}, "
                f"treatment={result['treatment_claims']})", result["a4_pass"]))
    print()
    print("OVERALL:", "PASS" if result["overall_pass"] else "FAIL")

    print()
    print("recovered rows by claim shape (informational, not gating):")
    shapes = ("E1", "E2", "E3", "E4", "E5")
    header_row = "  ".join(f"{s:>4s}" for s in shapes)
    print(f"  run{' ' * 14}{header_row}")
    for run_name in (control_run, *treatment_runs):
        counts = result["recovered_by_shape"][run_name]
        row = "  ".join(f"{counts.get(s, 0):>4d}" for s in shapes)
        print(f"  {run_name:<16s}{row}")
    control_e3 = result["recovered_by_shape"][control_run]["E3"]
    treatment_e3 = {run: result["recovered_by_shape"][run]["E3"] for run in treatment_runs}
    print(f"  E3 attribution check: control recovered {control_e3}/4 E3 rows on the loader fix alone "
          f"(before any new shape example); treatment recovered {treatment_e3} - if control's E3 count is "
          "already high, the E3 cause was the loader bug, not the new examples (see decisions.md).")

    print()
    print("miss_cause counts per run, for target rows NOT recovered (informational, not gating):")
    for run_name in (control_run, *treatment_runs):
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
    parser.add_argument("--control-run", default="control_r1")
    parser.add_argument("--treatment-runs", default="treatment_r1,treatment_r2")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    treatment_runs = [r.strip() for r in args.treatment_runs.split(",")]
    result = score(
        args.adjudication_path, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir,
        args.replay_root, args.control_run, treatment_runs,
    )
    _print_report(result, args.control_run, treatment_runs)


if __name__ == "__main__":
    main()
