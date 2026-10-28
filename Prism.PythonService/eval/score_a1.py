"""CLI: scores the three A1 repeat folders (flag-on replays, exp1_{level}_scope_{n}/)
against the A1 marks. Read-only, prints only, zero LLM calls.

Labels are the final claim "label" in RAW mode (grounding's missing/grounding_status
ignored), the same way the A0 repeats were scored with eval.score_replay --mode raw.

Marks (thresholds are constants, never parameters):
  A1-fixed  a miss row is fixed when its label is partially_supported or not_supported
            in >= 2 of 3 repeats. PASS if fixed >= 5 of 10 AND always-missed fixed >= 4 of 6.
  A1-lost   a real hit is lost when its label is supported in >= 2 of 3 repeats. PASS if lost <= 1.
  A1-quote  across all claims in all 3 folders, every claim with scope_lowered == true has a
            non-null scope_quote and a matching scope_items entry with guard_passed == true.
            PASS if 0 violations.
A folder or row that cannot be scored prints INVALID and exits 1 with no marks.

Usage (from Prism.PythonService):
  .venv\\Scripts\\python.exe -B -m eval.score_a1 --fixture-dir <scope_1> --fixture-dir <scope_2> --fixture-dir <scope_3>
"""
import argparse
import json
import sys
from pathlib import Path

from eval.score_replay import (
    DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR,
    AdjudicatedRow, _load_fixture, resolve_adjudicated_rows, row_details,
)

# Row sets from docs/decisions.md "Auditor redesign agreed: caching + scope check,
# marks and caps - 2026-10-22".
MISS_ROWS = ("P3-R2", "P4-R1", "P4-R2", "P5-R2", "P6-R2", "P11-R2", "P1-R1", "P5-R1", "P7-R1", "P8-R2")
ALWAYS_MISSED = ("P3-R2", "P4-R1", "P4-R2", "P5-R2", "P6-R2", "P11-R2")
REAL_HITS = ("P2-R5", "P6-R1", "P8-R1", "P10-R1", "P10-R2", "P10-R3", "P12-R2")

REPEATS = 3
VOTES_NEEDED = 2
FIXED_LABELS = ("partially_supported", "not_supported")
LOST_LABEL = "supported"
MIN_FIXED = 5
MIN_ALWAYS_FIXED = 4
MAX_LOST = 1
SCOPE_FIELDS = ("scope_lowered", "scope_items")
SUMMARY_COUNTS = (
    "lister_calls", "lister_failures", "claims_with_items", "checker_calls", "checker_failures",
    "item_count_mismatches", "contradicted_items", "guard_failed", "verdicts_lowered",
)


def _all_scored_rows() -> list[str]:
    return list(dict.fromkeys(MISS_ROWS + ALWAYS_MISSED + REAL_HITS))


def _folder_claims(fixture_dir: Path) -> list[tuple[str, dict]]:
    """Every (paper_id, claim) in the folder's paper fixtures (not _summary.json)."""
    out = []
    if not fixture_dir.is_dir():
        return out
    for path in sorted(fixture_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        for claim in json.loads(path.read_text(encoding="utf-8")).get("claims", []):
            out.append((path.stem, claim))
    return out


def _has_scope_fields(claim: dict) -> bool:
    return any(f in claim for f in SCOPE_FIELDS)


def _row_claim(row: AdjudicatedRow, fixture_dir: Path) -> dict | None:
    fixture = _load_fixture(fixture_dir, row.paper_id)
    if fixture is None:
        return None
    return next((c for c in fixture["claims"] if c["index"] == row.claim_index), None)


def collect(
    rows: list[AdjudicatedRow], fixture_dirs: list[Path],
) -> tuple[list[str], dict[str, list[str]], dict[str, list[dict]]]:
    """Returns (invalid reasons, {row_id: [label per repeat]}, {row_id: [claim dict per repeat]}).
    Labels and claims are only meaningful when there are no invalid reasons."""
    invalid: list[str] = []
    by_id = {r.row_id: r for r in rows}
    wanted = _all_scored_rows()
    absent = [rid for rid in wanted if rid not in by_id]
    if absent:
        invalid.append(f"rows not adjudicated refusal rows: {', '.join(absent)}")
    scored = [by_id[rid] for rid in wanted if rid in by_id]

    labels: dict[str, list[str]] = {r.row_id: [] for r in scored}
    claims: dict[str, list[dict]] = {r.row_id: [] for r in scored}
    for fixture_dir in fixture_dirs:
        folder_claims = _folder_claims(fixture_dir)
        if not any(_has_scope_fields(c) for _, c in folder_claims):
            invalid.append(f"{fixture_dir}: no scope fields (not a flag-on run)")
            continue  # every row would repeat the same cause
        details = row_details(scored, fixture_dir)
        for row in scored:
            detail = details[row.row_id]
            if detail is None:
                reason = "FIXTURE_MISSING" if _load_fixture(fixture_dir, row.paper_id) is None else "no claim data"
                invalid.append(f"{fixture_dir}: {row.row_id} {reason}")
                continue
            claim = _row_claim(row, fixture_dir)
            if claim is None or not all(f in claim for f in SCOPE_FIELDS):
                invalid.append(f"{fixture_dir}: {row.row_id} claim lacks scope fields")
                continue
            labels[row.row_id].append(detail["raw_label"])
            claims[row.row_id].append(claim)
    return invalid, labels, claims


def _votes(labels: list[str], wanted: tuple[str, ...] | str) -> int:
    wanted_set = {wanted} if isinstance(wanted, str) else set(wanted)
    return sum(1 for label in labels if label in wanted_set)


def mark_fixed(labels: dict[str, list[str]]) -> tuple[list[str], list[str], bool]:
    """Returns (fixed miss rows, fixed always-missed rows, PASS)."""
    fixed = [rid for rid in MISS_ROWS if _votes(labels[rid], FIXED_LABELS) >= VOTES_NEEDED]
    always = [rid for rid in ALWAYS_MISSED if rid in fixed]
    return fixed, always, len(fixed) >= MIN_FIXED and len(always) >= MIN_ALWAYS_FIXED


def mark_lost(labels: dict[str, list[str]]) -> tuple[list[str], bool]:
    lost = [rid for rid in REAL_HITS if _votes(labels[rid], LOST_LABEL) >= VOTES_NEEDED]
    return lost, len(lost) <= MAX_LOST


def mark_quote(folder_claims: dict[str, list[tuple[str, dict]]]) -> list[str]:
    """Violations (empty = PASS) over every claim with scope_lowered == true."""
    violations = []
    for folder, claims in folder_claims.items():
        for paper_id, claim in claims:
            if claim.get("scope_lowered") is not True:
                continue
            where = f"{folder} {paper_id}#{claim.get('index')}"
            quote = claim.get("scope_quote")
            if quote is None:
                violations.append(f"{where}: scope_lowered with null scope_quote")
                continue
            matching = [
                e for e in claim.get("scope_items") or []
                if e.get("text") == claim.get("scope_item") and e.get("contradicting_quote") == quote
            ]
            if not any(e.get("guard_passed") is True for e in matching):
                reason = "guard_passed is not true" if matching else "no matching scope_items entry"
                violations.append(f"{where}: scope_lowered but {reason}")
    return violations


def _print_summary_counts(fixture_dir: Path) -> None:
    path = fixture_dir / "_summary.json"
    block = None
    if path.exists():
        block = json.loads(path.read_text(encoding="utf-8")).get("scope_check")
    if not isinstance(block, dict):
        print(f"  {fixture_dir}: summary missing")
        return
    print(f"  {fixture_dir}: " + ", ".join(f"{k}={block.get(k)}" for k in SUMMARY_COUNTS))


def _source(claim: dict) -> str:
    if claim.get("scope_lowered") is True:
        return "scope"
    return "auditor" if claim.get("auditor_label") == claim.get("label") else "auditor?"


def run(
    fixture_dirs: list[Path], dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
) -> int:
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir, row_type="R")
    invalid, labels, claims = collect(rows, fixture_dirs)
    if invalid:
        for reason in invalid:
            print(f"INVALID: {reason}")
        return 1

    print("Per-row label across repeats:")
    for group, ids in (("miss", MISS_ROWS), ("real hit", REAL_HITS)):
        for rid in ids:
            print(f"  [{group}] {rid}: {', '.join(labels[rid])}")

    fixed, always, fixed_pass = mark_fixed(labels)
    lost, lost_pass = mark_lost(labels)
    folder_claims = {str(d): _folder_claims(d) for d in fixture_dirs}
    violations = mark_quote(folder_claims)
    quote_pass = not violations

    print(f"\nA1-fixed: {len(fixed)}/{len(MISS_ROWS)} miss rows fixed (need >= {MIN_FIXED}), "
          f"{len(always)}/{len(ALWAYS_MISSED)} always-missed fixed (need >= {MIN_ALWAYS_FIXED}): "
          f"{'PASS' if fixed_pass else 'FAIL'}  fixed={fixed}")
    print(f"A1-lost: {len(lost)}/{len(REAL_HITS)} real hits lost (need <= {MAX_LOST}): "
          f"{'PASS' if lost_pass else 'FAIL'}  lost={lost}")
    print(f"A1-quote: {len(violations)} violations (need 0): {'PASS' if quote_pass else 'FAIL'}")
    for v in violations:
        print(f"  {v}")

    print("\nReport only - verdicts lowered by scope per repeat:")
    for fixture_dir, claim_list in folder_claims.items():
        print(f"  {fixture_dir}: {sum(1 for _, c in claim_list if c.get('scope_lowered') is True)}")
    print("Report only - source of the final label for fixed miss rows (scope = lowered by scope check, "
          "auditor = auditor_label == label):")
    for rid in fixed:
        per_repeat = [
            f"{_source(claims[rid][i])}" if labels[rid][i] in FIXED_LABELS else "-"
            for i in range(len(fixture_dirs))
        ]
        print(f"  {rid}: {', '.join(per_repeat)}")
    print("Report only - scope_check counts from _summary.json:")
    for fixture_dir in fixture_dirs:
        _print_summary_counts(fixture_dir)

    failed = [name for name, ok in (("A1-fixed", fixed_pass), ("A1-lost", lost_pass), ("A1-quote", quote_pass)) if not ok]
    print("\nA1 PASS" if not failed else f"\nA1 FAIL: {', '.join(failed)}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture-dir", action="append", required=True, dest="fixture_dirs", type=Path)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if len(args.fixture_dirs) != REPEATS:
        parser.error(f"--fixture-dir must be given exactly {REPEATS} times, got {len(args.fixture_dirs)}")
    sys.exit(run(args.fixture_dirs, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir))


if __name__ == "__main__":
    main()
