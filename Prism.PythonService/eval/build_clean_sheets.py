"""CLI: builds the clean-extraction attempt's K6 and K7 blind hand-label
sheets for ONE clean run (docs/decisions.md, "Clean-extraction attempt
amended: new pass-2 prompt + filter - 2026-10-17"):

  K6  30 kept cleaned pass-2 claims (seed 20261017), label/reason/duplicate/
      note - same shape as Experiment 3 B4's c8_sheet.csv
      (eval.blind_review.K6Answer), scored for precision >= 0.70.
  K7  30 "same" drops (all if fewer, seed 20261017) - each with the
      candidate text and the neighbour text the filter matched it to as
      "same", for a human to re-judge the relation independently
      (eval.blind_review.K7Answer), scored for at most 1 really being
      broader/narrower/different.

No LLM calls, no paid calls. Reads ONE clean run's --run-dir (a
docs/evals/fixtures/dev/clean/<run_id>/ directory eval/replay_clean.py
wrote: "<paper>_merged.json", "<paper>_filtered.json", and
"<paper>_clean.json"). Candidate/neighbour ids ("C{i}"/"P{j}") are
reconstructed from each paper's "<paper>_merged.json" claim order using the
EXACT scheme extraction/pass2_clean.py::_build_items assigns them (pass-1
claims C0, C1, ... in order, then pass-2 claims P0, P1, ... in order) -
"<paper>_clean.json" stores decisions keyed by these ids but not the texts
themselves, so this reconstruction is required to show a human the actual
sentences.

Usage:
  uv run python -m eval.build_clean_sheets --run-dir docs/evals/fixtures/dev/clean/clean_r1 \\
      --output-dir docs/evals/clean_k6k7/clean_r1
"""
import argparse
import csv
import json
from pathlib import Path

from rapidfuzz import fuzz

from eval.blind_review import provenance, seeded_sample, sha256_file
from extraction.grounding import normalize_for_match

REPO_ROOT = Path(__file__).parent.parent.parent

SEED_K6 = 20261017
SEED_K7 = 20261017
K6_SAMPLE_K = 30
K7_SAMPLE_K = 30
SIMILAR_TOP_N = 3


def _paper_ids(run_dir: Path) -> list[str]:
    return sorted(p.stem[: -len("_merged")] for p in run_dir.glob("*_merged.json"))


def _id_to_text_map(merged_claims: list[dict]) -> dict[str, str]:
    """Reconstructs the C{i}/P{j} id scheme extraction/pass2_clean.py's
    _build_items assigns, from one paper's merged (pre-filter) claims."""
    pass1 = [c for c in merged_claims if c.get("pass") != "pass2"]
    pass2 = [c for c in merged_claims if c.get("pass") == "pass2"]
    mapping = {f"C{i}": c["claim_text_verbatim"] for i, c in enumerate(pass1)}
    mapping.update({f"P{j}": c["claim_text_verbatim"] for j, c in enumerate(pass2)})
    return mapping


def _load_run(run_dir: Path) -> tuple[dict[str, list[dict]], dict[str, dict], dict[str, dict[str, str]]]:
    """Returns (pass2_pool_by_paper, decisions_by_paper, id_to_text_by_paper)."""
    pass2_pool: dict[str, list[dict]] = {}
    decisions_by_paper: dict[str, dict] = {}
    id_to_text_by_paper: dict[str, dict[str, str]] = {}

    for paper_id in _paper_ids(run_dir):
        merged = json.loads((run_dir / f"{paper_id}_merged.json").read_text(encoding="utf-8"))["claims"]
        id_to_text_by_paper[paper_id] = _id_to_text_map(merged)
        pass2_pool[paper_id] = [c["claim_text_verbatim"] for c in merged if c.get("pass") == "pass2"]

        clean_path = run_dir / f"{paper_id}_clean.json"
        if clean_path.exists():
            decisions_by_paper[paper_id] = json.loads(clean_path.read_text(encoding="utf-8"))["decisions"]
        else:
            decisions_by_paper[paper_id] = {}

    return pass2_pool, decisions_by_paper, id_to_text_by_paper


def _similar_claims(claim_text: str, pool: list[str], n: int = SIMILAR_TOP_N) -> list[str]:
    norm_claim = normalize_for_match(claim_text)
    scored = []
    for other in pool:
        norm_other = normalize_for_match(other)
        if norm_other == norm_claim:
            continue
        scored.append((fuzz.token_sort_ratio(norm_claim, norm_other), other))
    scored.sort(key=lambda pair: -pair[0])
    return [text for _, text in scored[:n]]


def build_k6(run_dir: Path, run_id: str) -> tuple[list[dict], dict[str, dict], list[Path]]:
    pass2_pool, decisions_by_paper, id_to_text_by_paper = _load_run(run_dir)
    input_files = [run_dir / f"{p}_merged.json" for p in pass2_pool] + \
        [run_dir / f"{p}_clean.json" for p in pass2_pool if (run_dir / f"{p}_clean.json").exists()]

    kept_items = []
    for paper_id, decisions in decisions_by_paper.items():
        id_to_text = id_to_text_by_paper[paper_id]
        for cid, decision in sorted(decisions.items()):
            if decision["decision"] == "kept" and cid.startswith("P"):
                kept_items.append({"paper_id": paper_id, "id": cid, "claim_text": id_to_text[cid]})

    sample = seeded_sample(kept_items, K6_SAMPLE_K, SEED_K6)
    sheet_rows = []
    key: dict[str, dict] = {}
    for i, item in enumerate(sample):
        kid = f"K6-{i + 1:03d}"
        similar = _similar_claims(item["claim_text"], pass2_pool[item["paper_id"]])
        similar = similar + [""] * (SIMILAR_TOP_N - len(similar))
        sheet_rows.append({
            "id": kid, "paper_id": item["paper_id"], "claim_text": item["claim_text"],
            "similar_1": similar[0], "similar_2": similar[1], "similar_3": similar[2],
        })
        key[kid] = {"paper_id": item["paper_id"], "candidate_id": item["id"], "run_id": run_id}

    return sheet_rows, key, input_files


def build_k7(run_dir: Path, run_id: str) -> tuple[list[dict], dict[str, dict], list[Path]]:
    pass2_pool, decisions_by_paper, id_to_text_by_paper = _load_run(run_dir)
    input_files = [run_dir / f"{p}_clean.json" for p in pass2_pool if (run_dir / f"{p}_clean.json").exists()]

    same_drops = []
    for paper_id, decisions in decisions_by_paper.items():
        id_to_text = id_to_text_by_paper[paper_id]
        for cid, decision in sorted(decisions.items()):
            if decision["decision"] != "dropped":
                continue
            same_relations = [r for r in decision.get("relations", []) if r["relation"] == "same"]
            if not same_relations:
                continue  # dropped for is_paper_claim=false, not a "same" drop
            neighbour_id = same_relations[0]["neighbour_id"]
            if cid not in id_to_text or neighbour_id not in id_to_text:
                continue
            same_drops.append({
                "paper_id": paper_id, "id": cid, "candidate_text": id_to_text[cid],
                "neighbour_id": neighbour_id, "neighbour_text": id_to_text[neighbour_id],
            })

    sample = seeded_sample(same_drops, K7_SAMPLE_K, SEED_K7)
    sheet_rows = []
    key: dict[str, dict] = {}
    for i, item in enumerate(sample):
        kid = f"K7-{i + 1:03d}"
        sheet_rows.append({
            "id": kid, "paper_id": item["paper_id"],
            "candidate_text": item["candidate_text"], "neighbour_text": item["neighbour_text"],
        })
        key[kid] = {"paper_id": item["paper_id"], "candidate_id": item["id"], "run_id": run_id}

    return sheet_rows, key, input_files


def _write_k6(output_dir: Path, sheet_rows: list[dict], key: dict, input_files: list[Path]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = output_dir / "k6_sheet.csv"
    with open(sheet_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["id", "paper_id", "claim_text", "similar_1", "similar_2", "similar_3", "label", "reason", "duplicate", "note"])
        for row in sheet_rows:
            writer.writerow([row["id"], row["paper_id"], row["claim_text"], row["similar_1"], row["similar_2"], row["similar_3"], "", "", "", ""])
    key_path = output_dir / "k6_key.json"
    key_path.write_text(json.dumps({"provenance": provenance(input_files), "items": key}, indent=2), encoding="utf-8")
    print(f"wrote {sheet_path} sha256={sha256_file(sheet_path)} ({len(sheet_rows)} rows)")
    print(f"wrote {key_path} sha256={sha256_file(key_path)}")


def _write_k7(output_dir: Path, sheet_rows: list[dict], key: dict, input_files: list[Path]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = output_dir / "k7_sheet.csv"
    with open(sheet_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["id", "paper_id", "candidate_text", "neighbour_text", "verdict", "note"])
        for row in sheet_rows:
            writer.writerow([row["id"], row["paper_id"], row["candidate_text"], row["neighbour_text"], "", ""])
    key_path = output_dir / "k7_key.json"
    key_path.write_text(json.dumps({"provenance": provenance(input_files), "items": key}, indent=2), encoding="utf-8")
    print(f"wrote {sheet_path} sha256={sha256_file(sheet_path)} ({len(sheet_rows)} rows)")
    print(f"wrote {key_path} sha256={sha256_file(key_path)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True, help="label recorded in the key files, e.g. clean_r1")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    k6_rows, k6_key, k6_inputs = build_k6(args.run_dir, args.run_id)
    k7_rows, k7_key, k7_inputs = build_k7(args.run_dir, args.run_id)
    _write_k6(args.output_dir, k6_rows, k6_key, k6_inputs)
    _write_k7(args.output_dir, k7_rows, k7_key, k7_inputs)


if __name__ == "__main__":
    main()
