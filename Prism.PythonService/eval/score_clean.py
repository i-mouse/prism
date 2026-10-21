"""CLI: scores the clean-extraction attempt's marks K1-K8 (docs/decisions.md,
"Clean-extraction attempt revised: extraction-only marks - 2026-10-17" and
its amendment "...new pass-2 prompt + filter - 2026-10-17") against one or
more clean runs (docs/evals/fixtures/dev/clean/<run_id>/, written by
eval/replay_clean.py).

  K2, K3, K4, K5, K8  computed directly from each run's own output files -
      no human input needed.
  K1                  read from a LOCKED, hand-filled sheet (see
      eval/build_clean_review_pack.py) - verify_lock refuses to score an
      unlocked or since-edited sheet.
  K6, K7              read from eval/score_label_pack.py's <mode>_score.json
      output (eval/build_label_pack.py builds the pack and key that
      produces it). The older sheet-based --k6k7-run path is removed.

Also reports pre-filter vs. post-filter pass-2 claim counts per paper, and
reason_code counts across every dropped candidate (informational, not
gating) - the amended decision's "report pre-filter counts" item.

No LLM calls. main.py is never imported.

Usage:
  uv run python -m eval.score_clean --run clean_r1:docs/evals/fixtures/dev/clean/clean_r1 \\
      --run clean_r2:docs/evals/fixtures/dev/clean/clean_r2 \\
      --k1-run clean_r1:docs/evals/clean_k1/clean_r1 --k1-run clean_r2:docs/evals/clean_k1/clean_r2 \\
      --k6-score clean_r1:docs/evals/clean_k6k7_pack/clean_r1/k6_score.json \\
      --k6-score clean_r2:docs/evals/clean_k6k7_pack/clean_r2/k6_score.json \\
      --k7-score clean_r1:docs/evals/clean_k6k7_pack/clean_r1/k7_score.json \\
      --k7-score clean_r2:docs/evals/clean_k6k7_pack/clean_r2/k7_score.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from eval.blind_review import C1Answer, verify_lock
from eval.match_map import fingerprint_claim_text, load_match_map
from eval.matrix_loader import load_matrix

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"

K1_STABLE_ROWS = {"P2-R3", "P2-R4", "P3-R1", "P5-R3", "P8-R3", "P9-R1", "P11-R3"}
K1_FLOOR = 7

C4_COST_PER_PAPER_FACTOR = 87
C4_MAX_INR = 130
K3_MAX_R = 1.40
K5_MIN_RATE = 0.95
K6_MIN_PRECISION = 0.70
K6_SAMPLE_K = 30
K7_MAX_NOT_SAME = 1
K8_FILTER_MAX_INR = 40
K8_ATTEMPT_MAX_INR = 350


def _paper_ids(run_dir: Path) -> list[str]:
    return sorted(p.stem[: -len("_merged")] for p in run_dir.glob("*_merged.json"))


def _load(run_dir: Path, paper_id: str, suffix: str) -> dict:
    return json.loads((run_dir / f"{paper_id}_{suffix}.json").read_text(encoding="utf-8"))


def _final_claims(run_dir: Path, paper_id: str) -> list[dict]:
    filtered_path = run_dir / f"{paper_id}_filtered.json"
    if filtered_path.exists():
        return json.loads(filtered_path.read_text(encoding="utf-8"))["claims"]
    return _load(run_dir, paper_id, "merged")["claims"]


# --------------------------------------------------------------------------
# K2: filter never touches pass 1 (18 matched-row fingerprints retained)
# --------------------------------------------------------------------------

def score_k2(run_dir: Path, dev_eval_path: Path, match_map_path: Path) -> dict:
    matrix = load_matrix(dev_eval_path)
    golden_ids = {row.id for paper in matrix.papers for row in paper.expected_rows}
    match_map = load_match_map(match_map_path, golden_ids)
    scoped_fingerprints = {
        row_id: mm_row.claim_fingerprint
        for row_id, mm_row in match_map.rows.items()
        if mm_row.is_adjudicated and mm_row.claim_fingerprint is not None
    }
    scope = len(scoped_fingerprints)

    final_fingerprints = set()
    pass1_identical = True
    for paper_id in _paper_ids(run_dir):
        pass1_fixture = _load(run_dir, paper_id, "pass1")["claims"]
        merged = _load(run_dir, paper_id, "merged")["claims"]
        merged_pass1 = [c for c in merged if c.get("pass") != "pass2"]
        if [c["claim_text_verbatim"] for c in merged_pass1] != [c["claim_text_verbatim"] for c in pass1_fixture]:
            pass1_identical = False
        final = _final_claims(run_dir, paper_id)
        final_pass1 = [c for c in final if c.get("pass") != "pass2"]
        if [c["claim_text_verbatim"] for c in final_pass1] != [c["claim_text_verbatim"] for c in pass1_fixture]:
            pass1_identical = False
        for c in final_pass1:
            final_fingerprints.add(fingerprint_claim_text(c["claim_text_verbatim"]))

    retained = sum(1 for fp in scoped_fingerprints.values() if fp in final_fingerprints)
    return {
        "retained": retained, "scope": scope,
        "pass1_byte_identical_pre_and_post_filter": pass1_identical,
        "pass": pass1_identical and retained == scope,
    }


# --------------------------------------------------------------------------
# K3 / K4: r (post-filter claims / pass-1 claims) and projected cost
# --------------------------------------------------------------------------

def score_k3_k4(run_dirs: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, run_dir in run_dirs.items():
        per_paper_ratio = []
        total_final = 0
        total_pass1 = 0
        for paper_id in _paper_ids(run_dir):
            pass1_n = len(_load(run_dir, paper_id, "pass1")["claims"])
            final_n = len(_final_claims(run_dir, paper_id))
            total_final += final_n
            total_pass1 += pass1_n
            if pass1_n:
                per_paper_ratio.append(final_n / pass1_n)

        summary = json.loads((run_dir / "_summary.json").read_text(encoding="utf-8"))
        n_papers = len(_paper_ids(run_dir))
        p2 = summary.get("pass2_cost_inr", 0.0) / n_papers if n_papers else 0.0
        f = summary.get("filter_cost_inr", 0.0) / n_papers if n_papers else 0.0

        r_mean = sum(per_paper_ratio) / len(per_paper_ratio) if per_paper_ratio else None
        r_pooled = (total_final / total_pass1) if total_pass1 else None
        per_run[run_name] = {"r_mean": r_mean, "r_pooled": r_pooled, "p2": p2, "f": f}

    def _reading(key: str) -> dict:
        values = [per_run[run][key] for run in run_dirs]
        p2_values = [per_run[run]["p2"] for run in run_dirs]
        f_values = [per_run[run]["f"] for run in run_dirs]
        r = sum(values) / len(values)
        p2 = sum(p2_values) / len(p2_values)
        f = sum(f_values) / len(f_values)
        projected = C4_COST_PER_PAPER_FACTOR * r + p2 + f
        return {"r": r, "p2": p2, "f": f, "projected_inr": projected,
                "k3_pass": r <= K3_MAX_R, "k4_pass": projected <= C4_MAX_INR}

    return {
        "per_run": per_run,
        "k3_k4_mean_reading": _reading("r_mean"),
        "k3_k4_pooled_reading": _reading("r_pooled"),
    }


# --------------------------------------------------------------------------
# K5: pass-2 Stage-1 grounding rate on the cleaned set
# --------------------------------------------------------------------------

def score_k5(run_dirs: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, run_dir in run_dirs.items():
        total_sentences = 0
        total_ungrounded = 0
        for paper_id in _paper_ids(run_dir):
            buckets = _load(run_dir, paper_id, "buckets")
            pass2 = _load(run_dir, paper_id, "pass2")
            total_sentences += len(pass2["sentences"])
            total_ungrounded += buckets["dropped_ungrounded"]
        rate = (total_sentences - total_ungrounded) / total_sentences if total_sentences else None
        per_run[run_name] = {
            "sentences": total_sentences, "dropped_ungrounded": total_ungrounded, "rate": rate,
            "pass": rate is not None and rate >= K5_MIN_RATE,
        }
    return per_run


# --------------------------------------------------------------------------
# K8: spend
# --------------------------------------------------------------------------

def score_k8(run_dirs: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, run_dir in run_dirs.items():
        summary = json.loads((run_dir / "_summary.json").read_text(encoding="utf-8"))
        filter_cost = summary.get("filter_cost_inr", 0.0)
        per_run[run_name] = {"filter_cost_inr": filter_cost, "pass": filter_cost <= K8_FILTER_MAX_INR}
    return {
        "per_run": per_run,
        "note": f"attempt-total cap (INR {K8_ATTEMPT_MAX_INR}) is not computed here - "
                "it spans every call this attempt has made, not just the runs given to this invocation. "
                "Sum this run's cost_inr against the running total tracked in docs/decisions.md by hand.",
    }


# --------------------------------------------------------------------------
# Pre-filter vs post-filter counts + reason_code counts (informational)
# --------------------------------------------------------------------------

def report_filter_effect(run_dirs: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, run_dir in run_dirs.items():
        pre_total = 0
        post_total = 0
        reason_counts: Counter = Counter()
        for paper_id in _paper_ids(run_dir):
            merged = _load(run_dir, paper_id, "merged")["claims"]
            pre_total += sum(1 for c in merged if c.get("pass") == "pass2")
            post_total += sum(1 for c in _final_claims(run_dir, paper_id) if c.get("pass") == "pass2")
            clean_path = run_dir / f"{paper_id}_clean.json"
            if clean_path.exists():
                decisions = json.loads(clean_path.read_text(encoding="utf-8"))["decisions"]
                for d in decisions.values():
                    if d["decision"] == "dropped" and d.get("reason_code"):
                        reason_counts[d["reason_code"]] += 1
                    elif d["decision"] == "dropped":
                        reason_counts["same_relation_only"] += 1
        per_run[run_name] = {"pre_filter_pass2": pre_total, "post_filter_pass2": post_total, "reason_code_counts": dict(reason_counts)}
    return per_run


# --------------------------------------------------------------------------
# K1: blind adjudication, locked
# --------------------------------------------------------------------------

def score_k1(k1_dirs: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, k1_dir in k1_dirs.items():
        csv_path = k1_dir / "k1_adjudication.csv"
        key_path = k1_dir / "k1_key.json"
        verify_lock(k1_dir / "lock.json", {"k1_adjudication.csv": csv_path})
        key = json.loads(key_path.read_text(encoding="utf-8"))["candidates"]

        import csv as csv_module

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv_module.DictReader(f))

        recovered_rows = []
        errors = []
        for raw_row in rows:
            try:
                answer = C1Answer.model_validate(raw_row)
            except ValidationError as exc:
                errors.append(f"{raw_row.get('row_id', '?')}: {exc}")
                continue
            for match_id in answer.match_ids:
                if match_id not in key:
                    errors.append(f"{answer.row_id}: unknown candidate id {match_id!r}")
            if answer.match_ids:
                recovered_rows.append(answer.row_id)

        recovered_set = set(recovered_rows)
        stable_recovered = recovered_set & K1_STABLE_ROWS
        per_run[run_name] = {
            "recovered_total": len(recovered_set),
            "recovered_row_ids": sorted(recovered_set),
            "stable_rows_recovered": sorted(stable_recovered),
            "stable_rows_missing": sorted(K1_STABLE_ROWS - stable_recovered),
            "errors": errors,
            "pass": len(errors) == 0 and len(recovered_set) >= K1_FLOOR,
        }
    return per_run


# --------------------------------------------------------------------------
# K6 / K7: read from eval/score_label_pack.py's <mode>_score.json output
# (eval/build_label_pack.py + eval/score_label_pack.py - 2026-10-19 method,
# replacing the old sheet-based build_clean_sheets.py scoring this used to
# do inline). Gate thresholds are recomputed here from the raw counts
# rather than trusting the input file's own "pass" field, so this scorer
# stays the single source of truth for the K6/K7 gate.
# --------------------------------------------------------------------------

def score_k6(k6_score_paths: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, score_path in k6_score_paths.items():
        data = json.loads(score_path.read_text(encoding="utf-8"))
        n = data["n"]
        claims = data["counts"]["A"]
        precision = claims / n if n else None
        per_run[run_name] = {
            "n": n, "counts": data["counts"], "not_found_count": data.get("not_found_count", 0),
            "precision_unsure_not_claim": precision,
            "precision_unsure_claim": data.get("precision_unsure_claim"),
            "pass": n == K6_SAMPLE_K and precision is not None and precision >= K6_MIN_PRECISION,
        }
    return per_run


def score_k7(k7_score_paths: dict[str, Path]) -> dict:
    per_run = {}
    for run_name, score_path in k7_score_paths.items():
        data = json.loads(score_path.read_text(encoding="utf-8"))
        n = data["n"]
        not_same = n - data["counts"]["same"]
        per_run[run_name] = {
            "n": n, "counts": data["counts"], "not_same": not_same,
            "pass": n > 0 and not_same <= K7_MAX_NOT_SAME,
        }
    return per_run


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _parse_named_paths(values: Optional[list[str]]) -> dict[str, Path]:
    out = {}
    for value in values or []:
        name, path = value.split(":", 1)
        out[name] = Path(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", dest="runs", required=True,
                         help="name:path, repeatable, e.g. clean_r1:docs/evals/fixtures/dev/clean/clean_r1")
    parser.add_argument("--k1-run", action="append", dest="k1_runs",
                         help="name:path to a k1 output dir (eval.build_clean_review_pack --output-dir), repeatable")
    parser.add_argument("--k6-score", action="append", dest="k6_scores",
                         help="name:path to a k6_score.json (eval.score_label_pack --mode k6 output), repeatable")
    parser.add_argument("--k7-score", action="append", dest="k7_scores",
                         help="name:path to a k7_score.json (eval.score_label_pack --mode k7 output), repeatable")
    parser.add_argument("--k6k7-run", action="append", dest="k6k7_runs", help=argparse.SUPPRESS)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--output-path", type=Path, default=None)
    args = parser.parse_args()

    if args.k6k7_runs:
        parser.error(
            "--k6k7-run was removed: the K6/K7 gate now reads eval.score_label_pack output. "
            "Use --k6-score name:path/to/k6_score.json and --k7-score name:path/to/k7_score.json "
            "(built via eval.build_label_pack + eval.score_label_pack)."
        )

    run_dirs = _parse_named_paths(args.runs)
    k1_dirs = _parse_named_paths(args.k1_runs)
    k6_scores = _parse_named_paths(args.k6_scores)
    k7_scores = _parse_named_paths(args.k7_scores)

    result = {
        "k2": {run: score_k2(run_dir, args.dev_eval_path, args.match_map_path) for run, run_dir in run_dirs.items()},
        "k3_k4": score_k3_k4(run_dirs),
        "k5": score_k5(run_dirs),
        "k8": score_k8(run_dirs),
        "filter_effect_report_only": report_filter_effect(run_dirs),
    }
    if k1_dirs:
        result["k1"] = score_k1(k1_dirs)
    if k6_scores:
        result["k6"] = score_k6(k6_scores)
    if k7_scores:
        result["k7"] = score_k7(k7_scores)

    print(json.dumps(result, indent=2, default=str))
    if args.output_path:
        args.output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"wrote {args.output_path}")


if __name__ == "__main__":
    main()
