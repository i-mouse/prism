"""CLI: EXPLORATORY diagnostic, NOT a mark. For each of the clean-extraction
attempt's 13 K1 target rows, finds the first stage where the row was lost -
pass-2 prompt miss, merge drop (ungrounded/duplicate), or filter drop - using
the same locked K1 band rule as eval/score_clean_bounds.py (docs/decisions.md,
"Clean-extraction attempt: spot-check result, diagnostic, bounded scoring -
2026-10-20"), reused here read-only.

No LLM/API calls. No `_key/` file is ever opened (not needed: this reads only
the saved stage JSON under docs/evals/fixtures/dev/clean/<run>/). Never
imports extraction.pass2_clean - the C{i}/P{j} candidate-id split is rebuilt
here from `<paper>_merged.json` alone, matching that module's own rule
(extraction/pass2_clean.py:186-192, read-only, quoted in this module's
_split_pass1_pass2 docstring) without importing it or its paper_text/context
machinery. Also avoids eval.score_clean / eval.score_clean_bounds /
eval.blind_review (which import extraction.grounding, reading .env at import
time) by duplicating the three small pure pieces this needs
(K1_STABLE_ROWS, _k1_target_rows, _k1_band) with citation comments.

HARD STOP: before printing any per-row table or writing the report, this
recomputes the S3 (final, post-filter) found-counts and requires them to
exactly match the already-logged K1 FAIL numbers (5/13 low+high for clean_r1,
6/13 low+high for clean_r2 - docs/decisions.md 2026-10-20,
eval/score_clean_bounds.py's score_k1_bounds). A mismatch means this script's
stage-matching logic disagrees with the already-locked score; it prints the
mismatch and exits non-zero without writing anything.

Prints row ids, paper ids, and numeric scores only - never claim or sentence
text, in stdout or in the written report.

Usage:
  uv run python -m eval.diag_k1_stages \\
      --run clean_r1:docs/evals/fixtures/dev/clean/clean_r1 \\
      --run clean_r2:docs/evals/fixtures/dev/clean/clean_r2 \\
      --output-path docs/evals/clean_labels/k1_stage_diagnostic.md
"""
import argparse
import json
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from eval.inventory_compare import normalize_for_match
from eval.score_exp2 import ROW_ID_TO_SHAPE
from eval.score_replay import resolve_adjudicated_rows

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"

# eval/score_clean.py:47 - duplicated here to avoid importing that module
# (which imports eval.blind_review -> extraction.grounding -> reads .env).
K1_STABLE_ROWS = {"P2-R3", "P2-R4", "P3-R1", "P5-R3", "P8-R3", "P9-R1", "P11-R3"}

# docs/decisions.md 2026-10-20 "Clean-extraction attempt result: FAIL..." and
# eval/score_clean_bounds.py's score_k1_bounds output for clean_r1/clean_r2.
# The hard stop below requires this script's own S3 recomputation to match.
EXPECTED_S3_COUNTS = {
    "clean_r1": {"low": 5, "high": 5},
    "clean_r2": {"low": 6, "high": 6},
}


# --------------------------------------------------------------------------
# Duplicated from eval/score_clean_bounds.py (not imported - see module
# docstring for why), cited inline.
# --------------------------------------------------------------------------

def _k1_target_rows(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path) -> list[dict]:
    """eval/score_clean_bounds.py:92-97."""
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    return [
        {"row_id": row.row_id, "paper_id": row.paper_id, "claim_text_verbatim": row.expected_row.claim_text_verbatim}
        for row in rows if row.claim_index is None and row.row_id in ROW_ID_TO_SHAPE
    ]


def _k1_band(ratio: float, partial: float) -> str:
    """eval/score_clean_bounds.py:100-106. "both" -> found low+high. "high"
    -> found only in the high (best-case) bound. "none" -> not found."""
    if ratio >= 90:
        return "both"
    if ratio >= 60 or partial >= 90:
        return "high"
    return "none"


def _found(band: str, bound: str) -> bool:
    if bound == "low":
        return band == "both"
    return band in ("both", "high")


# --------------------------------------------------------------------------
# Stage item loaders - saved JSON only, no paper text, no extraction imports.
# --------------------------------------------------------------------------

def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _paper_ids(run_dir: Path) -> list[str]:
    """Same glob rule as eval/score_clean.py::_paper_ids, duplicated to avoid
    importing that module."""
    return sorted(p.stem[: -len("_merged")] for p in run_dir.glob("*_merged.json"))


def _s0_items(run_dir: Path, paper_ids: list[str]) -> list[dict]:
    items = []
    for paper_id in paper_ids:
        data = _load_json(run_dir / f"{paper_id}_pass1.json")
        if data is None:
            continue
        for c in data["claims"]:
            items.append({"paper_id": paper_id, "text": c["claim_text_verbatim"]})
    return items


def _s1_items(run_dir: Path, paper_ids: list[str]) -> list[dict]:
    items = []
    for paper_id in paper_ids:
        data = _load_json(run_dir / f"{paper_id}_pass2.json")
        if data is None:
            continue
        for sentence in data["sentences"]:
            items.append({"paper_id": paper_id, "text": sentence})
    return items


def _split_pass1_pass2(merged_claims: list[dict]) -> dict:
    """Rebuilds the C{i}/P{j} candidate-id split from `<paper>_merged.json`
    alone - the same rule extraction/pass2_clean.py::_build_items uses
    (read-only citation, never imported):

        # extraction/pass2_clean.py:186-189
        pass1_claims = [c for c in merged_claims if c.get("pass") != "pass2"]
        pass2_claims = [c for c in merged_claims if c.get("pass") == "pass2"]
        pool = [(f"C{i}", c["claim_text_verbatim"]) for i, c in enumerate(pass1_claims)]
        # :191-192
        for j, claim in enumerate(pass2_claims): candidate_id = f"P{j}"

    Returns {id(claim): candidate_id} for every pass-2 claim (pass-1 claims
    are never dropped by the filter, so they need no candidate id here)."""
    pass2_claims = [c for c in merged_claims if c.get("pass") == "pass2"]
    return {id(c): f"P{j}" for j, c in enumerate(pass2_claims)}


def _s2_items(run_dir: Path, paper_ids: list[str]) -> list[dict]:
    items = []
    for paper_id in paper_ids:
        data = _load_json(run_dir / f"{paper_id}_merged.json")
        if data is None:
            continue
        claims = data["claims"]
        candidate_ids = _split_pass1_pass2(claims)
        for c in claims:
            items.append({
                "paper_id": paper_id, "text": c["claim_text_verbatim"],
                "candidate_id": candidate_ids.get(id(c)),
            })
    return items


def _s3_items(run_dir: Path, paper_ids: list[str]) -> list[dict]:
    """Mirrors eval/score_clean.py::_final_claims's --no-filter fallback,
    duplicated to avoid importing that module."""
    items = []
    for paper_id in paper_ids:
        filtered_path = run_dir / f"{paper_id}_filtered.json"
        data = _load_json(filtered_path) or _load_json(run_dir / f"{paper_id}_merged.json")
        if data is None:
            continue
        for c in data["claims"]:
            items.append({"paper_id": paper_id, "text": c["claim_text_verbatim"]})
    return items


# --------------------------------------------------------------------------
# Best match + loss-stage attribution
# --------------------------------------------------------------------------

def _best_match(row_norm: str, items: list[dict]) -> dict:
    best = {"ratio": 0.0, "partial": 0.0, "paper_id": None, "text": None, "candidate_id": None}
    for item in items:
        norm = normalize_for_match(item["text"])
        ratio = fuzz.ratio(row_norm, norm)
        partial = fuzz.partial_ratio(row_norm, norm)
        if (ratio, partial) > (best["ratio"], best["partial"]):
            best = {
                "ratio": ratio, "partial": partial, "paper_id": item["paper_id"],
                "text": item["text"], "candidate_id": item.get("candidate_id"),
            }
    return best


def _merge_drop_bucket(run_dir: Path, paper_id: Optional[str], sentence_text: Optional[str]) -> str:
    if paper_id is None or sentence_text is None:
        return "unknown (no S1 match)"
    buckets = _load_json(run_dir / f"{paper_id}_buckets.json")
    if buckets is None:
        return "unknown (no buckets file)"
    for entry in buckets.get("dropped_duplicate", []):
        if entry["sentence"] == sentence_text:
            return f"dropped_duplicate (ratio={entry['ratio_score']:.1f}, partial={entry['partial_ratio_score']:.1f})"
    return "dropped_ungrounded (inferred by elimination - no per-sentence detail recorded for this bucket)"


def _filter_drop_detail(run_dir: Path, paper_id: Optional[str], candidate_id: Optional[str]) -> Optional[dict]:
    if paper_id is None or candidate_id is None:
        return None
    clean = _load_json(run_dir / f"{paper_id}_clean.json")
    if clean is None:
        return None
    decision = clean["decisions"].get(candidate_id)
    if decision is None:
        return None
    same_neighbours = []
    for rel in decision.get("relations", []):
        if rel.get("relation") != "same":
            continue
        nid = rel["neighbour_id"]
        if nid.startswith("C"):
            status = "kept (pass-1, always retained)"
        else:
            neighbour_decision = clean["decisions"].get(nid)
            status = neighbour_decision["decision"] if neighbour_decision else "unknown"
        same_neighbours.append({"neighbour_id": nid, "status": status})
    return {
        "candidate_id": candidate_id, "decision": decision["decision"],
        "reason_code": decision.get("reason_code"), "is_paper_claim": decision.get("is_paper_claim"),
        "same_neighbours": same_neighbours,
    }


def diagnose_row(run_dir: Path, row: dict, s0: list[dict], s1: list[dict], s2: list[dict], s3: list[dict]) -> dict:
    row_norm = normalize_for_match(row["claim_text_verbatim"])
    best = {
        "s0": _best_match(row_norm, s0), "s1": _best_match(row_norm, s1),
        "s2": _best_match(row_norm, s2), "s3": _best_match(row_norm, s3),
    }
    bands = {stage: _k1_band(b["ratio"], b["partial"]) for stage, b in best.items()}

    stages = {}
    for stage, b in best.items():
        stages[stage] = {
            "paper_id": b["paper_id"], "ratio": b["ratio"], "partial": b["partial"],
            "found_low": _found(bands[stage], "low"), "found_high": _found(bands[stage], "high"),
            "cross_paper": b["paper_id"] is not None and b["paper_id"] != row["paper_id"],
        }

    result = {"row_id": row["row_id"], "paper_id": row["paper_id"], "stages": stages}
    for bound in ("low", "high"):
        if not _found(bands["s1"], bound):
            stage_name, detail = "pass-2 prompt miss", None
        elif not _found(bands["s2"], bound):
            stage_name = "merge drop"
            detail = {"bucket": _merge_drop_bucket(run_dir, best["s1"]["paper_id"], best["s1"]["text"])}
        elif not _found(bands["s3"], bound):
            stage_name = "filter drop"
            detail = _filter_drop_detail(run_dir, best["s2"]["paper_id"], best["s2"]["candidate_id"])
        else:
            stage_name, detail = "found", None
        result[f"loss_stage_{bound}"] = stage_name
        result[f"loss_detail_{bound}"] = detail
    return result


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def run_diagnostic(
    run_dirs: dict[str, Path], dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path,
    no_filter: bool = False,
) -> dict:
    """no_filter=True: S3 is taken as S2 (`_filtered.json`/`_clean.json` are
    never read) - for runs with no filter stage at all, e.g.
    docs/evals/fixtures/dev/exp3/pass2_r1|r2. Default False keeps every
    existing caller's behavior byte-identical."""
    target_rows = _k1_target_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    per_run = {}
    for run_name, run_dir in run_dirs.items():
        paper_ids = _paper_ids(run_dir)
        s0 = _s0_items(run_dir, paper_ids)
        s1 = _s1_items(run_dir, paper_ids)
        s2 = _s2_items(run_dir, paper_ids)
        s3 = s2 if no_filter else _s3_items(run_dir, paper_ids)
        rows = [diagnose_row(run_dir, row, s0, s1, s2, s3) for row in target_rows]

        def count(stage: str, bound: str) -> int:
            return sum(1 for r in rows if r["stages"][stage][f"found_{bound}"])

        def stable_count(stage: str, bound: str) -> int:
            return sum(1 for r in rows if r["row_id"] in K1_STABLE_ROWS and r["stages"][stage][f"found_{bound}"])

        per_run[run_name] = {
            "rows": rows,
            "counts": {
                stage: {bound: count(stage, bound) for bound in ("low", "high")}
                for stage in ("s0", "s1", "s2", "s3")
            },
            "stable_counts": {
                stage: {bound: stable_count(stage, bound) for bound in ("low", "high")}
                for stage in ("s2", "s3")
            },
        }
    return {"target_total": len(target_rows), "per_run": per_run}


def _check_hard_stop(result: dict) -> list[str]:
    mismatches = []
    for run_name, expected in EXPECTED_S3_COUNTS.items():
        if run_name not in result["per_run"]:
            continue
        actual = result["per_run"][run_name]["counts"]["s3"]
        for bound in ("low", "high"):
            if actual[bound] != expected[bound]:
                mismatches.append(
                    f"run={run_name} bound={bound} expected={expected[bound]} actual={actual[bound]}"
                )
    return mismatches


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _format_stage(s: dict) -> str:
    cross = " CROSS-PAPER" if s["cross_paper"] else ""
    band = "both" if s["found_low"] else ("high" if s["found_high"] else "none")
    return f"paper={s['paper_id']} ratio={s['ratio']:.0f} partial={s['partial']:.0f} band={band}{cross}"


def _format_detail(detail: Optional[dict]) -> str:
    if detail is None:
        return "-"
    if "bucket" in detail:
        return f"bucket={detail['bucket']}"
    neighbours = ", ".join(f"{n['neighbour_id']}={n['status']}" for n in detail["same_neighbours"]) or "none"
    return (f"candidate_id={detail['candidate_id']} decision={detail['decision']} "
            f"reason_code={detail['reason_code']} is_paper_claim={detail['is_paper_claim']} "
            f"same_neighbours=[{neighbours}]")


def _render_report(result: dict) -> str:
    lines = ["# K1 stage-loss diagnostic", "", "**EXPLORATORY - not a mark.**", ""]
    for run_name, data in result["per_run"].items():
        lines.append(f"## {run_name}")
        lines.append("")
        lines.append("| row_id | S0 | S1 | S2 | S3 | loss (low) | loss (high) | detail (low) | detail (high) |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for row in data["rows"]:
            s = row["stages"]
            lines.append(
                f"| {row['row_id']} | {_format_stage(s['s0'])} | {_format_stage(s['s1'])} | "
                f"{_format_stage(s['s2'])} | {_format_stage(s['s3'])} | {row['loss_stage_low']} | "
                f"{row['loss_stage_high']} | {_format_detail(row['loss_detail_low'])} | "
                f"{_format_detail(row['loss_detail_high'])} |"
            )
        lines.append("")
        c = data["counts"]
        lines.append(
            f"- S2 (pre-filter) found: {c['s2']['low']}/{result['target_total']} (low), "
            f"{c['s2']['high']}/{result['target_total']} (high)"
        )
        lines.append(
            f"- S3 (final) found: {c['s3']['low']}/{result['target_total']} (low), "
            f"{c['s3']['high']}/{result['target_total']} (high)"
        )
        lines.append(f"- S2 - S3 delta: low={c['s2']['low'] - c['s3']['low']}, high={c['s2']['high'] - c['s3']['high']}")
        lines.append("")

    lines.append("## Interpretation rule (fixed before running)")
    lines.append(
        "Filter is the main cause of K1 loss if S2 (pre-filter) found-count is at least 2 rows "
        "higher than S3 (final) in BOTH runs; otherwise the main cause is pass-2 yield or merge."
    )
    for bound in ("low", "high"):
        deltas = [
            data["counts"]["s2"][bound] - data["counts"]["s3"][bound]
            for data in result["per_run"].values()
        ]
        outcome = "filter is a main cause" if all(d >= 2 for d in deltas) else "pass-2 yield or merge is the main cause"
        lines.append(f"- {bound} bound: deltas={deltas} -> {outcome}")
    lines.append("")
    return "\n".join(lines)


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
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--no-filter", action="store_true",
                         help="S3 is taken as S2; never reads _filtered.json/_clean.json "
                              "(for runs with no filter stage, e.g. exp3/pass2_r1|r2)")
    parser.add_argument("--output-path", type=Path, required=True)
    args = parser.parse_args()

    run_dirs = _parse_named_paths(args.runs)
    result = run_diagnostic(
        run_dirs, args.dev_eval_path, args.match_map_path, args.run1_fixture_dir, no_filter=args.no_filter,
    )

    mismatches = _check_hard_stop(result)
    if mismatches:
        print("HARD STOP: S3 recomputation does not match the already-logged K1 FAIL numbers.")
        for m in mismatches:
            print(f"  MISMATCH {m}")
        raise SystemExit("refusing to write the diagnostic report: S3 count mismatch (see above)")

    for run_name, data in result["per_run"].items():
        c = data["counts"]
        print(f"{run_name}: S3 found {c['s3']['low']}/{result['target_total']} low, "
              f"{c['s3']['high']}/{result['target_total']} high (matches logged score)")
        for row in data["rows"]:
            print(f"  {row['row_id']}: loss_low={row['loss_stage_low']} loss_high={row['loss_stage_high']}")
        print(f"  S2-S3 delta: low={c['s2']['low'] - c['s3']['low']}, high={c['s2']['high'] - c['s3']['high']}")

    for bound in ("low", "high"):
        deltas = [data["counts"]["s2"][bound] - data["counts"]["s3"][bound] for data in result["per_run"].values()]
        outcome = "filter is a main cause" if all(d >= 2 for d in deltas) else "pass-2 yield or merge is the main cause"
        print(f"interpretation ({bound} bound): deltas={deltas} -> {outcome}")

    args.output_path.write_text(_render_report(result), encoding="utf-8")
    print(f"wrote {args.output_path}")


if __name__ == "__main__":
    main()
