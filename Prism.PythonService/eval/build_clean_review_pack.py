"""CLI: builds the clean-extraction attempt's K1 blind review pack - the 13
run-1 extraction-miss target rows, matched by hand against ONE clean run's
cleaned output (docs/decisions.md, "Clean-extraction attempt amended: new
pass-2 prompt + filter - 2026-10-17", K1). Opaque candidate ids, no
pass/run attribution shown in the pack or the adjudication CSV - a human
fills in match_ids blind, the same discipline eval/exp3_b4.py::cmd_build_c1
established for Experiment 3's own c1 pack, reused here rather than
reimplemented differently (same eval.blind_review.C1Answer row shape, so
eval/score_clean.py can reuse it directly).

No LLM calls, no paid calls. Reads docs/evals/dev_eval.json (dev, not
sealed) via eval.score_exp2.ROW_ID_TO_SHAPE and
eval.score_replay.resolve_adjudicated_rows - never docs/evals/exp3_targets.json
(off-limits) or docs/LABEL_RUBRIC.md. Reads ONE clean run's --run-dir, a
docs/evals/fixtures/dev/clean/<run_id>/ directory eval/replay_clean.py
wrote (its "<paper>_filtered.json", or "<paper>_merged.json" when that run
used --no-filter).

Run once per clean run (pass2_r1-equivalent, pass2_r2-equivalent) with a
distinct --output-dir and --seed, per the amended decision's requirement
that K1 be checked independently against each new cleaned run.

Usage:
  uv run python -m eval.build_clean_review_pack --run-dir docs/evals/fixtures/dev/clean/clean_r1 \\
      --output-dir docs/evals/clean_k1/clean_r1 --seed 20261017
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz

from eval.blind_review import assign_opaque_ids, dedup_by_normalized_text, provenance, sha256_file
from eval.score_exp2 import ROW_ID_TO_SHAPE
from eval.score_replay import resolve_adjudicated_rows
from extraction.grounding import normalize_for_match

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"

SHORTLIST_TOP_N = 8


def _target_rows(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path) -> list[dict]:
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    return [
        {
            "row_id": row.row_id, "paper_id": row.paper_id,
            "claim_text_verbatim": row.expected_row.claim_text_verbatim,
            "shape": ROW_ID_TO_SHAPE.get(row.row_id, "unknown"),
        }
        for row in rows if row.claim_index is None and row.row_id in ROW_ID_TO_SHAPE
    ]


def _load_claims(run_dir: Path, paper_id: str) -> tuple[list[dict], str]:
    filtered_path = run_dir / f"{paper_id}_filtered.json"
    path = filtered_path if filtered_path.exists() else run_dir / f"{paper_id}_merged.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["claims"], path.name


def build(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path, run_dir: Path, seed: int):
    rows = _target_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    papers = sorted({row["paper_id"] for row in rows})

    input_files = [dev_eval_path, match_map_path]
    raw_claims: dict[str, list[dict]] = {}
    for paper_id in papers:
        claims, fname = _load_claims(run_dir, paper_id)
        input_files.append(run_dir / fname)
        raw_claims[paper_id] = [
            {"index": i, "pass": c.get("pass", "pass1"), "text": c["claim_text_verbatim"]}
            for i, c in enumerate(claims)
        ]

    pool_candidates = []
    for paper_id in papers:
        deduped = dedup_by_normalized_text(raw_claims[paper_id], text_of=lambda e: e["text"])
        for e in deduped:
            pool_candidates.append({"paper_id": paper_id, **e})

    id_pairs = assign_opaque_ids(pool_candidates, prefix="K1C", seed=seed)
    id_to_candidate = {cid: cand for cid, cand in id_pairs}
    paper_to_ids: dict[str, list[str]] = defaultdict(list)
    for cid, cand in id_pairs:
        paper_to_ids[cand["paper_id"]].append(cid)

    key: dict[str, dict] = {
        cid: {"paper_id": cand["paper_id"], "pass": cand["pass"], "merged_index": cand["index"]}
        for cid, cand in id_pairs
    }

    pack_rows = []
    for row in rows:
        candidates = [(cid, id_to_candidate[cid]["text"]) for cid in paper_to_ids[row["paper_id"]]]
        golden_norm = normalize_for_match(row["claim_text_verbatim"])
        shortlist = sorted(
            candidates, key=lambda pair: -fuzz.token_sort_ratio(golden_norm, normalize_for_match(pair[1]))
        )[:SHORTLIST_TOP_N]
        random.Random(f"{seed}-{row['row_id']}").shuffle(shortlist)
        pack_rows.append({"row": row, "shortlist": shortlist})

    return rows, pack_rows, key, input_files, paper_to_ids, id_to_candidate


def _write_outputs(output_dir: Path, rows: list[dict], pack_rows: list[dict], key: dict,
                    input_files: list[Path], paper_to_ids: dict, id_to_candidate: dict, seed: int) -> None:
    import csv

    output_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Clean-extraction attempt - K1 blind target-row matching pack",
        "",
        "Do not open k1_key.json before scoring.",
        "",
        "## Rules",
        "",
        '- "Same claim, other sentence" = match.',
        '- A "safe half only" sibling claim (broader or narrower version only) = no match.',
        "- Several ids per row are allowed.",
        '- "none" is allowed.',
        "",
    ]
    for entry in pack_rows:
        row = entry["row"]
        lines.append(f"## {row['row_id']} ({row['paper_id']}) - shape: {row['shape']}")
        lines.append(f"**Target claim:** {row['claim_text_verbatim']}")
        lines.append("")
        lines.append("Candidates:")
        for cid, text in entry["shortlist"]:
            lines.append(f"- **{cid}**: {text}")
        lines.append("")

    for paper_id, ids in sorted(paper_to_ids.items()):
        lines.append(f"## Appendix - {paper_id} - full candidate pool")
        appendix_ids = list(ids)
        random.Random(f"{seed}-{paper_id}-appendix").shuffle(appendix_ids)
        for cid in appendix_ids:
            lines.append(f"- **{cid}**: {id_to_candidate[cid]['text']}")
        lines.append("")

    pack_path = output_dir / "k1_review_pack.md"
    pack_path.write_text("\n".join(lines), encoding="utf-8")

    adjudication_path = output_dir / "k1_adjudication.csv"
    with open(adjudication_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["row_id", "paper_id", "row_text", "match_ids", "note"])
        for row in rows:
            writer.writerow([row["row_id"], row["paper_id"], row["claim_text_verbatim"], "", ""])

    key_path = output_dir / "k1_key.json"
    key_path.write_text(json.dumps({"provenance": provenance(input_files), "candidates": key}, indent=2), encoding="utf-8")

    print(f"wrote {pack_path} sha256={sha256_file(pack_path)}")
    print(f"wrote {adjudication_path} sha256={sha256_file(adjudication_path)}")
    print(f"wrote {key_path} sha256={sha256_file(key_path)}")
    print(f"pool size per paper: {{{', '.join(f'{p}: {len(ids)}' for p, ids in sorted(paper_to_ids.items()))}}}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--run-dir", type=Path, required=True, help="one docs/evals/fixtures/dev/clean/<run_id>/ directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    rows, pack_rows, key, input_files, paper_to_ids, id_to_candidate = build(
        args.dev_eval_path, args.match_map_path, args.run1_fixture_dir, args.run_dir, args.seed,
    )
    _write_outputs(args.output_dir, rows, pack_rows, key, input_files, paper_to_ids, id_to_candidate, args.seed)


if __name__ == "__main__":
    main()
