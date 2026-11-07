"""CLI: resolves docs/evals/dev_match_map.json's claim-fingerprint rows back to
{paper_id, claim_index} pairs and writes docs/evals/exp1_stage_a_claims.json -
the claim set eval/replay_audit.py --claims consumes for Experiment 1 Stage A.

Only rows with claim_fingerprint set are included (a real claim exists to
re-audit) - rows with only confirmed_no_match (extraction misses) are excluded,
since there is nothing to re-audit. Prints the resolved list for review before
anything is spent on it. Zero LLM calls.

Usage:
  uv run python -m eval.build_stage_a_claims

--full-check builds the claims index for the full no-regression check instead: the 18
refusal-row claims plus the 67 matched S rows, deduped by (paper_id, claim_index), each
entry carrying a row_ids list. It requires an explicit --output-path, refuses the Stage A
file and refuses to overwrite any existing file, prints the final count and every claim
shared by more than one row, and raises (no file written) unless there are exactly 18
refusal rows and 67 S rows. The 21 NO_MATCH S rows have no claim and are not listed.
Without the flag nothing below changes.

  uv run python -m eval.build_stage_a_claims --full-check --output-path docs/evals/exp1_full_check_claims.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from eval.match_map import fingerprint_claim_text, load_match_map
from eval.matrix_loader import load_matrix

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "evals" / "exp1_stage_a_claims.json"

# --full-check: what the match map must hold (apply_s_row_decisions.FULL_EXPECTATIONS["int"] = 67).
FULL_CHECK_EXPECTED_R_ROWS = 18
FULL_CHECK_EXPECTED_S_ROWS = 67
_R_ROW_RE = re.compile(r"P\d+-R\d+")
_S_ROW_RE = re.compile(r"P\d+-S\d+")


def _resolve(fixture_dir: Path, paper_ids: list[str]) -> dict[str, int]:
    """Returns {claim_fingerprint: claim_index} across all given papers' run1
    fixtures, keyed only by papers that actually contain that fingerprint."""
    by_fingerprint: dict[str, tuple[str, int]] = {}
    for paper_id in paper_ids:
        claims = json.loads((fixture_dir / f"{paper_id}.json").read_text(encoding="utf-8"))["claims"]
        for claim in claims:
            fp = fingerprint_claim_text(claim["claim_text_verbatim"])
            by_fingerprint[fp] = (paper_id, claim["index"])
    return by_fingerprint


def build(dev_eval_path: Path, match_map_path: Path, fixture_dir: Path) -> list[dict]:
    matrix = load_matrix(dev_eval_path)
    golden_ids = {row.id for paper in matrix.papers for row in paper.expected_rows}
    match_map = load_match_map(match_map_path, golden_ids)
    paper_ids = [paper.paper_id for paper in matrix.papers]

    by_fingerprint = _resolve(fixture_dir, paper_ids)

    selected = []
    for row_id, row in sorted(match_map.rows.items()):
        if row.claim_fingerprint is None:
            continue
        resolved = by_fingerprint.get(row.claim_fingerprint)
        if resolved is None:
            raise ValueError(f"{row_id}: claim_fingerprint {row.claim_fingerprint[:12]} not found in any run1 fixture")
        paper_id, claim_index = resolved
        selected.append({"row_id": row_id, "paper_id": paper_id, "claim_index": claim_index})
    return selected


def build_full_check(dev_eval_path: Path, match_map_path: Path, fixture_dir: Path) -> tuple[list[dict], list[dict]]:
    """Returns (entries, shared) for the full no-regression check. entries is one dict per distinct
    (paper_id, claim_index), {"row_ids": [sorted], "paper_id", "claim_index"}, sorted by paper then index;
    shared is the entries that more than one row points at.

    Raises ValueError for a row id that is neither P<n>-R<n> nor P<n>-S<n>, or unless the match map holds
    exactly FULL_CHECK_EXPECTED_R_ROWS refusal rows and FULL_CHECK_EXPECTED_S_ROWS S rows with a claim."""
    selected = build(dev_eval_path, match_map_path, fixture_dir)

    r_rows = [e["row_id"] for e in selected if _R_ROW_RE.fullmatch(e["row_id"])]
    s_rows = [e["row_id"] for e in selected if _S_ROW_RE.fullmatch(e["row_id"])]
    unknown = [e["row_id"] for e in selected if e["row_id"] not in r_rows and e["row_id"] not in s_rows]
    if unknown:
        raise ValueError(f"row ids that are neither refusal (P<n>-R<n>) nor S (P<n>-S<n>) rows: {unknown}")
    if len(r_rows) != FULL_CHECK_EXPECTED_R_ROWS:
        raise ValueError(f"expected {FULL_CHECK_EXPECTED_R_ROWS} refusal rows with a claim, found {len(r_rows)}")
    if len(s_rows) != FULL_CHECK_EXPECTED_S_ROWS:
        raise ValueError(f"expected {FULL_CHECK_EXPECTED_S_ROWS} S rows with a claim, found {len(s_rows)}")

    return group_by_claim(selected)


def group_by_claim(selected: list[dict]) -> tuple[list[dict], list[dict]]:
    """selected: dicts with row_id, paper_id, claim_index. Returns (entries, shared): one entry per distinct
    (paper_id, claim_index), {"row_ids": [sorted], "paper_id", "claim_index"}, sorted by paper then index;
    shared = the entries more than one row points at. Shared with eval/build_golden_claims.py."""
    row_ids_by_claim: dict[tuple[str, int], list[str]] = {}
    for entry in selected:
        row_ids_by_claim.setdefault((entry["paper_id"], entry["claim_index"]), []).append(entry["row_id"])
    entries = [
        {"row_ids": sorted(row_ids), "paper_id": paper_id, "claim_index": claim_index}
        for (paper_id, claim_index), row_ids in sorted(row_ids_by_claim.items())
    ]
    shared = [e for e in entries if len(e["row_ids"]) > 1]
    return entries, shared


def check_new_output_path(output_path: Path | None, flag: str = "--full-check") -> str | None:
    """Why a claims-index builder may not write `output_path`, or None. It must be given explicitly, must not be
    the Stage A file (exp1_stage_a_claims.json) and must not exist yet."""
    if output_path is None:
        return f"{flag} requires an explicit --output-path (it never writes the Stage A file)"
    output_path = Path(output_path)
    if output_path.resolve() == DEFAULT_OUTPUT_PATH.resolve():
        return f"{flag} must not write the Stage A file {DEFAULT_OUTPUT_PATH}"
    if output_path.exists():
        return f"{output_path} already exists, refusing to overwrite it"
    return None


def _run_full_check(args: argparse.Namespace) -> int:
    problem = check_new_output_path(args.output_path)
    if problem is not None:
        print(f"ERROR: {problem}")
        return 1
    output_path = Path(args.output_path)

    try:
        entries, shared = build_full_check(args.dev_eval_path, args.match_map_path, args.fixture_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Full-check set: {len(entries)} claims "
          f"({FULL_CHECK_EXPECTED_R_ROWS} refusal rows + {FULL_CHECK_EXPECTED_S_ROWS} S rows, {len(shared)} shared claims)")
    for entry in shared:
        print(f"  shared: {entry['paper_id']} claim #{entry['claim_index']}: {', '.join(entry['row_ids'])}")

    try:
        with output_path.open("x", encoding="utf-8") as handle:  # "x": never overwrites
            handle.write(json.dumps(entries, indent=2))
    except FileExistsError:
        print(f"ERROR: {output_path} already exists, refusing to overwrite it")
        return 1
    print(f"\nwrote {output_path} ({len(entries)} claims)")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    # None = not given: the legacy mode then uses DEFAULT_OUTPUT_PATH, --full-check refuses to run.
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument(
        "--full-check", action="store_true",
        help="build the full no-regression check set (18 refusal-row + 67 S-row claims, deduped, with row_ids); "
             "requires an explicit --output-path",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.full_check:
        sys.exit(_run_full_check(args))

    output_path = args.output_path if args.output_path is not None else DEFAULT_OUTPUT_PATH
    selected = build(args.dev_eval_path, args.match_map_path, args.fixture_dir)

    print(f"Resolved {len(selected)} Stage A claims:")
    for entry in selected:
        print(f"  {entry['row_id']:<8} -> {entry['paper_id']} claim #{entry['claim_index']}")

    # replay_audit.py --claims consumes only paper_id/claim_index; row_id is kept
    # in the file purely for human review/debugging.
    output_path.write_text(json.dumps(selected, indent=2), encoding="utf-8")
    print(f"\nwrote {output_path} ({len(selected)} claims)")


if __name__ == "__main__":
    main()
