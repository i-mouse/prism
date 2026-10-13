"""CLI: builds a human review pack for Experiment 2 Stage A.

For each of the 13 extraction-miss rows and 18 matched rows in run 1's
hand-adjudicated dev set (resolved via eval.score_replay.resolve_adjudicated_rows,
reused as-is), and for each replay run given (--replay-fixture-dir, repeatable),
lists the top-3 candidate claims from that run scored by RapidFuzz
token_sort_ratio against the golden row's claim text, normalised the same way
Stage-1 grounding does (extraction.grounding.normalize_for_match, gated by
settings.grounding_normalize - read only, never changed here).

Never adjudicates - mirrors eval/suggest_match_map.py's discipline exactly:
this writes a suggestion for a human to review, never a decision. The
adjudication JSON this writes is a template (matched_claim_index: null,
note: "", and - for target rows only - miss_cause: null) for a human to fill
in by hand; eval/score_exp2.py reads the FILLED version, never this one.
miss_cause is filled in only when matched_claim_index stays null (the row was
not recovered), with one of: shape_not_taught | saw_example_still_skipped |
split_or_merged_differently | other. Zero LLM calls, zero DB writes, reads
docs/evals/dev_eval.json and docs/evals/dev_match_map.json (dev files, not
sealed) and the given replay fixture directories only.

Usage:
  uv run python -m eval.build_exp2_review_pack --papers P1,P2,P3,P4,P5,P7,P8,P9,P11,P12 \
      --replay-fixture-dir docs/evals/fixtures/dev/exp2/control_r1 \
      --replay-fixture-dir docs/evals/fixtures/dev/exp2/treatment_r1 \
      --replay-fixture-dir docs/evals/fixtures/dev/exp2/treatment_r2
"""
import argparse
import json
from pathlib import Path

from rapidfuzz import fuzz

from config import settings
from eval.score_replay import resolve_adjudicated_rows
from extraction.grounding import normalize_for_match

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_OUTPUT_MD_PATH = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp2" / "review_pack.md"
DEFAULT_OUTPUT_JSON_PATH = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp2" / "adjudication_template.json"

TOP_N = 3
SNIPPET_LENGTH = 160


def _normalize(text: str) -> str:
    return normalize_for_match(text) if settings.grounding_normalize else text


def _top_candidates(golden_text: str, claims: list[dict]) -> list[tuple[float, dict]]:
    golden_norm = _normalize(golden_text)
    scored = []
    for claim in claims:
        text = claim.get("claim_text_verbatim", "")
        if not text:
            continue
        score = fuzz.token_sort_ratio(golden_norm, _normalize(text))
        scored.append((score, claim))
    scored.sort(key=lambda pair: -pair[0])
    return scored[:TOP_N]


def build(
    dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
    replay_dirs: list[Path], papers_filter: str | None,
) -> tuple[dict, list[dict]]:
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    if papers_filter:
        wanted = {s.strip() for s in papers_filter.split(",")}
        rows = [row for row in rows if any(w in row.paper_id for w in wanted)]

    pack: dict = {"target_rows": [], "matched_rows": []}
    adjudication_template: list[dict] = []

    for row in rows:
        bucket = "target_rows" if row.claim_index is None else "matched_rows"
        for replay_dir in replay_dirs:
            run_name = replay_dir.name
            fixture_path = replay_dir / f"{row.paper_id}.json"

            if not fixture_path.exists():
                entry = {
                    "row_id": row.row_id, "run": run_name, "paper_id": row.paper_id,
                    "candidates": [], "note": "fixture missing for this paper in this run",
                }
            else:
                claims = json.loads(fixture_path.read_text(encoding="utf-8"))["claims"]
                top = _top_candidates(row.expected_row.claim_text_verbatim, claims)
                entry = {
                    "row_id": row.row_id, "run": run_name, "paper_id": row.paper_id,
                    "candidates": [
                        {
                            "claim_index": claim["index"], "score": round(score, 1),
                            "snippet": claim["claim_text_verbatim"][:SNIPPET_LENGTH],
                        }
                        for score, claim in top
                    ],
                }
            pack[bucket].append(entry)
            template_entry = {"row_id": row.row_id, "run": run_name, "matched_claim_index": None, "note": ""}
            if bucket == "target_rows":
                template_entry["miss_cause"] = None
            adjudication_template.append(template_entry)

    return pack, adjudication_template


def _write_markdown(pack: dict, output_path: Path) -> None:
    lines = ["# Experiment 2 Stage A review pack", ""]
    lines.append(
        f"{len({e['row_id'] for e in pack['target_rows']})} target (extraction-miss) rows, "
        f"{len({e['row_id'] for e in pack['matched_rows']})} matched rows. "
        "This is a suggestion for review, not an adjudication - fill in the "
        "adjudication JSON by hand."
    )
    lines.append("")

    for section_title, bucket in (("Target rows (extraction misses)", "target_rows"), ("Matched rows (regression check)", "matched_rows")):
        lines.append(f"## {section_title}")
        lines.append("")
        for entry in pack[bucket]:
            lines.append(f"### {entry['row_id']} — {entry['run']} ({entry['paper_id']})")
            if not entry["candidates"]:
                lines.append(f"- {entry.get('note', 'no candidates above floor')}")
            else:
                for candidate in entry["candidates"]:
                    lines.append(f"- claim #{candidate['claim_index']} score={candidate['score']}: {candidate['snippet']}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--replay-fixture-dir", action="append", required=True, dest="replay_dirs", type=Path)
    parser.add_argument("--papers", help="comma-separated paper_id substrings to scope the review pack to")
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_MD_PATH)
    parser.add_argument("--output-json-path", type=Path, default=DEFAULT_OUTPUT_JSON_PATH)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    pack, adjudication_template = build(
        args.dev_eval_path, args.match_map_path, args.run1_fixture_dir, args.replay_dirs, args.papers,
    )
    _write_markdown(pack, args.output_path)
    args.output_json_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json_path.write_text(json.dumps(adjudication_template, indent=2), encoding="utf-8")

    print(f"wrote {args.output_path} ({len(pack['target_rows'])} target-row entries, {len(pack['matched_rows'])} matched-row entries)")
    print(f"wrote {args.output_json_path} ({len(adjudication_template)} rows to adjudicate by hand)")


if __name__ == "__main__":
    main()
