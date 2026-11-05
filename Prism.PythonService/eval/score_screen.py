"""CLI: majority-vote scorer for one arm of the Vertex screen (3 repeat folders of the
18-claim set, docs/evals/exp1_stage_a_claims.json). Read-only, prints only, zero LLM calls.

Unlike eval.score_a1 it needs no scope fields, so it scores plain auditor replays.
Labels are the final claim "label" in RAW mode (grounding ignored), as in score_a1.

Votes (same definitions as score_a1):
  miss row       CAUGHT when its label is partially_supported or not_supported in >= 2 of 3 folders.
  real-hit row   LOST when its label is supported in >= 2 of 3 folders.
  other row      (in the 18-claim set but in neither group) labels printed, verdict "-", in no total.
Totals: misses caught (all miss rows); misses caught excluding the parked rows (the "auditor
targets"); real hits lost. The parked rows' votes are also printed on their own.

INVALID (reason printed, exit 1, no totals, no JSON) if: a folder is missing or has no
_summary.json; any of the 18 rows has no claim in some folder or is not an adjudicated refusal
row; a label is not one of the three replay labels; or the folders' run_config differ in
backend, auditor_model, thinking_level or other_models (a folder whose summary has no
run_config counts as "default", and then all 3 must be default).

Report only (no effect on votes): per folder, the claims whose audit_model_served differs from
run_config.auditor_model (compared by pricing.normalise_model_name), or "n/a".

Usage (from Prism.PythonService):
  uv run python -m eval.score_screen --fixture-dir <arm_1> --fixture-dir <arm_2> --fixture-dir <arm_3> [--json-out PATH]
"""
import argparse
import json
import sys
from pathlib import Path

from eval import pricing
from eval.score_a1 import (
    FIXED_LABELS, LOST_LABEL, MISS_ROWS, REAL_HITS, REPEATS, VOTES_NEEDED, _row_claim, _votes,
)
from eval.score_replay import (
    DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR,
    AdjudicatedRow, _load_fixture, resolve_adjudicated_rows, row_details,
)

# In docs/evals/exp1_stage_a_claims.json but in neither score_a1 group.
OTHER_ROWS = ("P1-R3",)
# Parked: excluded from the "auditor targets" total, still voted and printed.
PARKED_ROWS = ("P5-R1", "P5-R2")
VALID_LABELS = ("supported", "partially_supported", "not_supported")
RUN_CONFIG_KEYS = ("backend", "auditor_model", "thinking_level", "other_models")
DEFAULT_CONFIG = "default"


def _groups() -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (("miss", MISS_ROWS), ("real hit", REAL_HITS), ("other", OTHER_ROWS))


def _scored_ids() -> list[str]:
    return list(dict.fromkeys(rid for _, ids in _groups() for rid in ids))


def _setup_errors() -> list[str]:
    return [f"parked row {rid} is not a miss row" for rid in PARKED_ROWS if rid not in MISS_ROWS]


def _load_run_config(fixture_dir: Path, invalid: list[str]):
    """The summary's run_config dict, DEFAULT_CONFIG when the summary has none, None (and an
    INVALID reason) when the summary is missing or unreadable."""
    path = fixture_dir / "_summary.json"
    if not path.is_file():
        invalid.append(f"{fixture_dir}: no _summary.json")
        return None
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        invalid.append(f"{fixture_dir}: _summary.json unreadable ({exc})")
        return None
    config = summary.get("run_config") if isinstance(summary, dict) else None
    if config is None:
        return DEFAULT_CONFIG
    if not isinstance(config, dict):
        invalid.append(f"{fixture_dir}: run_config is not an object")
        return None
    return config


def _config_differences(fixture_dirs: list[Path], configs: list) -> list[str]:
    defaults = [c == DEFAULT_CONFIG for c in configs]
    if all(defaults):
        return []
    if any(defaults):
        names = ", ".join(str(d) for d, is_default in zip(fixture_dirs, defaults) if is_default)
        return [f"run_config present in some folders but not in: {names} (a folder without it is default)"]
    reasons = []
    for key in RUN_CONFIG_KEYS:
        values = [c.get(key) for c in configs]
        if any(v != values[0] for v in values[1:]):
            detail = "; ".join(f"{d}={v!r}" for d, v in zip(fixture_dirs, values))
            reasons.append(f"run_config.{key} differs: {detail}")
    return reasons


def collect(
    rows: list[AdjudicatedRow], fixture_dirs: list[Path],
) -> tuple[list[str], dict[str, list[str]], dict[str, list[dict]], list]:
    """Returns (invalid reasons, {row_id: [label per folder]}, {row_id: [claim per folder]},
    [run_config per folder]). Labels, claims and configs are only meaningful when there are no
    invalid reasons."""
    invalid: list[str] = []
    by_id = {r.row_id: r for r in rows}
    wanted = _scored_ids()
    absent = [rid for rid in wanted if rid not in by_id]
    if absent:
        invalid.append(f"rows not adjudicated refusal rows: {', '.join(absent)}")
    scored = [by_id[rid] for rid in wanted if rid in by_id]

    labels: dict[str, list[str]] = {r.row_id: [] for r in scored}
    claims: dict[str, list[dict]] = {r.row_id: [] for r in scored}
    configs: list = []
    for fixture_dir in fixture_dirs:
        if not fixture_dir.is_dir():
            invalid.append(f"{fixture_dir}: folder missing")
            configs.append(None)
            continue
        configs.append(_load_run_config(fixture_dir, invalid))
        details = row_details(scored, fixture_dir)
        for row in scored:
            detail = details[row.row_id]
            if detail is None:
                reason = "FIXTURE_MISSING" if _load_fixture(fixture_dir, row.paper_id) is None else "no claim data"
                invalid.append(f"{fixture_dir}: {row.row_id} {reason}")
                continue
            if detail["raw_label"] not in VALID_LABELS:
                invalid.append(f"{fixture_dir}: {row.row_id} label {detail['raw_label']!r} is not a replay label")
                continue
            labels[row.row_id].append(detail["raw_label"])
            claims[row.row_id].append(_row_claim(row, fixture_dir))

    if all(c is not None for c in configs):
        invalid.extend(_config_differences(fixture_dirs, configs))
    return invalid, labels, claims, configs


def verdict(group: str, labels: list[str]) -> str:
    if group == "miss" and _votes(labels, FIXED_LABELS) >= VOTES_NEEDED:
        return "CAUGHT"
    if group == "real hit" and _votes(labels, LOST_LABEL) >= VOTES_NEEDED:
        return "LOST"
    return "-"


def _served_differs(served, auditor_model) -> bool:
    if not isinstance(served, str) or not isinstance(auditor_model, str):
        return True
    return pricing.normalise_model_name(served) != pricing.normalise_model_name(auditor_model)


def backup_report(fixture_dirs: list[Path], claims: dict[str, list[dict]], configs: list) -> list[dict]:
    """Per folder: {"fixture_dir", "count", "row_ids"}; count/row_ids are None ("n/a") for a folder
    without run_config or whose scored claims carry no audit_model_served."""
    report = []
    for i, fixture_dir in enumerate(fixture_dirs):
        config = configs[i]
        carrying = [(rid, per_folder[i]) for rid, per_folder in claims.items() if "audit_model_served" in per_folder[i]]
        if config == DEFAULT_CONFIG or not carrying:
            report.append({"fixture_dir": str(fixture_dir), "count": None, "row_ids": None})
            continue
        ids = [rid for rid, claim in carrying if _served_differs(claim["audit_model_served"], config.get("auditor_model"))]
        report.append({"fixture_dir": str(fixture_dir), "count": len(ids), "row_ids": ids})
    return report


def build_results(
    fixture_dirs: list[Path], labels: dict[str, list[str]], claims: dict[str, list[dict]], configs: list,
) -> dict:
    row_results = [
        {"row_id": rid, "group": group, "labels": labels[rid], "verdict": verdict(group, labels[rid])}
        for group, ids in _groups() for rid in ids
    ]
    by_id = {r["row_id"]: r for r in row_results}
    caught = [r["row_id"] for r in row_results if r["verdict"] == "CAUGHT"]
    targets = [rid for rid in caught if rid not in PARKED_ROWS]
    lost = [r["row_id"] for r in row_results if r["verdict"] == "LOST"]
    return {
        "fixture_dirs": [str(d) for d in fixture_dirs],
        "run_config": configs[0],
        "rows": row_results,
        "totals": {
            "misses_caught": len(caught), "misses_total": len(MISS_ROWS), "misses_caught_ids": caught,
            "auditor_targets_caught": len(targets), "auditor_targets_total": len(MISS_ROWS) - len(PARKED_ROWS),
            "auditor_targets_caught_ids": targets,
            "real_hits_lost": len(lost), "real_hits_total": len(REAL_HITS), "real_hits_lost_ids": lost,
        },
        "parked": [by_id[rid] for rid in PARKED_ROWS],
        "backup": backup_report(fixture_dirs, claims, configs),
    }


def _print_results(results: dict) -> None:
    print(f"run_config: {results['run_config']}")
    print("\nPer-row labels across the 3 folders (in --fixture-dir order):")
    for r in results["rows"]:
        print(f"  {r['row_id']:<8} [{r['group']}] {', '.join(r['labels'])}  {r['verdict']}")
    t = results["totals"]
    print(f"\nMisses caught: {t['misses_caught']}/{t['misses_total']}")
    print(f"Misses caught excluding parked rows (auditor targets): {t['auditor_targets_caught']}/{t['auditor_targets_total']}")
    print(f"Real hits lost: {t['real_hits_lost']}/{t['real_hits_total']}")
    print("\nParked rows (not in the auditor-targets total):")
    for r in results["parked"]:
        print(f"  {r['row_id']:<8} {', '.join(r['labels'])}  {r['verdict']}")
    print("\nReport only - claims whose audit_model_served differs from run_config.auditor_model:")
    for b in results["backup"]:
        detail = "n/a" if b["count"] is None else f"{b['count']} ({', '.join(b['row_ids']) or 'none'})"
        print(f"  {b['fixture_dir']}: {detail}")


def run(
    fixture_dirs: list[Path], dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
    json_out: Path | None = None,
) -> int:
    fixture_dirs = [Path(d).resolve() for d in fixture_dirs]
    print("Fixture folders:")
    for d in fixture_dirs:
        print(f"  {d}")
    errors = _setup_errors()
    if errors:
        for reason in errors:
            print(f"STOP: {reason}")
        return 1
    if json_out is not None and any(Path(json_out).resolve().is_relative_to(d) for d in fixture_dirs):
        print("INVALID: --json-out must not be inside a fixture folder")
        return 1

    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir, row_type="R")
    invalid, labels, claims, configs = collect(rows, fixture_dirs)
    if invalid:
        for reason in invalid:
            print(f"INVALID: {reason}")
        return 1

    results = build_results(fixture_dirs, labels, claims, configs)
    _print_results(results)
    if json_out is not None:
        json_out = Path(json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {json_out.resolve()}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture-dir", action="append", required=True, dest="fixture_dirs", type=Path)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if len(args.fixture_dirs) != REPEATS:
        parser.error(f"--fixture-dir must be given exactly {REPEATS} times, got {len(args.fixture_dirs)}")
    sys.exit(run(args.fixture_dirs, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir, args.json_out))


if __name__ == "__main__":
    main()
