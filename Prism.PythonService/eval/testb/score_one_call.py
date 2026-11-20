"""CLI: scores eval.testb.one_call's run directories against docs/evals/dev_eval.json.

Matching, per paper per run: the row anchor is the longest "..."/"..."-split piece of
claim_text_verbatim if it is >= 30 chars, else the whole text with the gaps removed.
Score(row, claim) = extraction.grounding._stage1_score(anchor, claim_quote,
normalize=True); swapping the two strings gives the same score (see
tests/test_testb_score_one_call.py), so only one call is made. If the shorter of the
two strings is under 30 chars the score is forced to 0. A row is matched if its best
score >= RAPIDFUZZ_THRESHOLD (88); ties keep the earliest claim.

Vote: 3 runs -> flagged in >= 2 of 3; 1 run -> flagged in that run (SINGLE-RUN). Any
other run count is INVALID. More than 2 FAILED paper-runs across all runs -> VOID, no
verdict. caught = R rows voted flagged (/31); false_rejections = S rows voted flagged
(/88); found = rows matched in a majority of runs (/119).

Verdict (checked in order): caught>=12 & FR<=8 -> ONE CALL BETTER; caught>=12 & FR>8 ->
STRICTER, NOT BETTER; caught<=4 or FR>8 -> PRISM BETTER; else NO CLEAR DIFFERENCE.

Report-only fields (never change the verdict): caught split into auditor-miss
(eval.score_a1.MISS_ROWS) / extraction-miss (eval.score_exp2.ROW_ID_TO_SHAPE) /
prism-caught (the complement of the 31 dev R-row ids, reported only when the two named
sets are disjoint, have sizes 10 and 13, and the complement has exactly 8 ids -
otherwise "NOT AVAILABLE"); release-bar check (caught>=22 & FR<=8); unmatched carbon
claims by verdict; rows matched by the same claim; quote grounding rate; mean
tokens/INR per paper (and x2 for the 2026-12-01 price); a per-row table. Every output
holds ids, labels, scores and counts only - never paper or claim text.

Usage (from Prism.PythonService):
  uv run python -m eval.testb.score_one_call --runs DIR/run_1 DIR/run_2 DIR/run_3 \
      --json-out docs/evals/testb_2026-11-19/score.json --md-out docs/evals/testb_2026-11-19/score.md
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from eval import score_a1, score_exp2
from eval.exp3_b4 import _extract_pdf_text, _resolve_pdf
from eval.matrix_loader import MatrixSpec, load_matrix
from extraction.grounding import RAPIDFUZZ_THRESHOLD, _stage1_score

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"

ANCHOR_MIN_CHARS = 30

PRISM_CAUGHT = 8
PRISM_FR = 4
T = 3  # repeat count, carried for parity with docs/decisions.md's existing marks; not a branch condition below
FR_CEILING = 8
RELEASE_BAR_CAUGHT = 22
RELEASE_BAR_FR = 8

_SPLIT_RE = re.compile(r"\.\.\.|…")


def _anchor(claim_text_verbatim: str) -> str:
    pieces = [p.strip() for p in _SPLIT_RE.split(claim_text_verbatim)]
    pieces = [p for p in pieces if p]
    if not pieces:
        return claim_text_verbatim.strip()
    longest = max(pieces, key=len)
    if len(longest) >= ANCHOR_MIN_CHARS:
        return longest
    return " ".join(pieces)


def _match_score(anchor: str, claim_quote: str) -> float:
    if min(len(anchor), len(claim_quote)) < ANCHOR_MIN_CHARS:
        return 0.0
    return _stage1_score(anchor, claim_quote, normalize=True)


def _row_match(row, paper_record: dict | None) -> dict:
    """{"status": not_found|supported|flagged, "score": float, "claim_index": int|None}."""
    if paper_record is None or paper_record.get("status") != "OK":
        return {"status": "not_found", "score": 0.0, "claim_index": None}
    claims = (paper_record.get("parsed") or {}).get("claims") or []
    anchor = _anchor(row.claim_text_verbatim)
    best_score = -1.0
    best_index = None
    for idx, claim in enumerate(claims):
        score = _match_score(anchor, claim.get("claim_quote", ""))
        if score > best_score:
            best_score, best_index = score, idx
    if best_index is None or best_score < RAPIDFUZZ_THRESHOLD:
        return {"status": "not_found", "score": max(best_score, 0.0), "claim_index": None}
    verdict = claims[best_index].get("verdict")
    status = "supported" if verdict == "supported" else "flagged"
    return {"status": status, "score": best_score, "claim_index": best_index}


def _vote(statuses: list[str]) -> tuple[str, str]:
    n = len(statuses)
    if n == 3:
        flagged = sum(1 for s in statuses if s == "flagged")
        return ("flagged" if flagged >= 2 else "not_flagged"), "3-RUN"
    if n == 1:
        return ("flagged" if statuses[0] == "flagged" else "not_flagged"), "SINGLE-RUN"
    raise ValueError(f"INVALID run count: {n}")


def _matched_majority(statuses: list[str]) -> bool:
    n = len(statuses)
    matched = sum(1 for s in statuses if s != "not_found")
    if n == 3:
        return matched >= 2
    if n == 1:
        return matched >= 1
    raise ValueError(f"INVALID run count: {n}")


def _load_run(run_dir: Path) -> dict[str, dict]:
    papers = {}
    for path in run_dir.glob("*.json"):
        if path.name == "_summary.json":
            continue
        papers[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return papers


def _prism_caught_ids(all_r_ids: set[str]) -> set[str] | None:
    """all_r_ids minus score_a1.MISS_ROWS minus score_exp2.ROW_ID_TO_SHAPE keys, only
    if the two named sets are disjoint, sized 10 and 13, and the complement is exactly
    8 ids; otherwise None (caller reports NOT AVAILABLE). Never an invented list."""
    miss = set(score_a1.MISS_ROWS)
    extraction_miss = set(score_exp2.ROW_ID_TO_SHAPE)
    if miss & extraction_miss:
        return None
    if len(miss) != 10 or len(extraction_miss) != 13:
        return None
    result = all_r_ids - miss - extraction_miss
    if len(result) != 8:
        return None
    return result


def _caught_breakdown(caught_ids: list[str], all_r_ids: set[str]) -> dict:
    miss = set(score_a1.MISS_ROWS)
    extraction_miss = set(score_exp2.ROW_ID_TO_SHAPE)
    prism_caught = _prism_caught_ids(all_r_ids)
    auditor_miss_n = extraction_miss_n = prism_caught_n = unclassified_n = 0
    for rid in caught_ids:
        if rid in miss:
            auditor_miss_n += 1
        elif rid in extraction_miss:
            extraction_miss_n += 1
        elif prism_caught is not None and rid in prism_caught:
            prism_caught_n += 1
        else:
            unclassified_n += 1
    return {
        "auditor_miss": auditor_miss_n,
        "extraction_miss": extraction_miss_n,
        "prism_caught": prism_caught_n if prism_caught is not None else "NOT AVAILABLE",
        "unclassified_if_prism_caught_unavailable": unclassified_n,
    }


def _unmatched_claims_by_verdict(matrix: MatrixSpec, runs: list[dict]) -> dict:
    counts: dict = defaultdict(int)
    for paper in matrix.papers:
        anchors = [_anchor(row.claim_text_verbatim) for row in paper.expected_rows]
        for run in runs:
            record = run.get(paper.paper_id)
            if record is None or record.get("status") != "OK":
                continue
            for claim in (record.get("parsed") or {}).get("claims") or []:
                quote = claim.get("claim_quote", "")
                best = max((_match_score(a, quote) for a in anchors), default=0.0)
                if best < RAPIDFUZZ_THRESHOLD:
                    counts[claim.get("verdict", "unknown")] += 1
    return dict(counts)


def _duplicate_claim_matches(matrix: MatrixSpec, runs: list[dict]) -> int:
    collisions = 0
    for paper in matrix.papers:
        for run in runs:
            record = run.get(paper.paper_id)
            if record is None or record.get("status") != "OK":
                continue
            used: dict = defaultdict(int)
            for row in paper.expected_rows:
                m = _row_match(row, record)
                if m["claim_index"] is not None:
                    used[m["claim_index"]] += 1
            collisions += sum(1 for c in used.values() if c > 1)
    return collisions


def _quote_grounding_rate(matrix: MatrixSpec, runs: list[dict]) -> float | None:
    total = grounded = 0
    for paper in matrix.papers:
        paper_text = _extract_pdf_text(_resolve_pdf(paper.paper_id))
        for run in runs:
            record = run.get(paper.paper_id)
            if record is None or record.get("status") != "OK":
                continue
            for claim in (record.get("parsed") or {}).get("claims") or []:
                quote = claim.get("claim_quote", "")
                total += 1
                if len(quote) >= ANCHOR_MIN_CHARS and _stage1_score(quote, paper_text, normalize=True) >= RAPIDFUZZ_THRESHOLD:
                    grounded += 1
    return (grounded / total) if total else None


def _tokens_and_cost_per_paper(runs: list[dict]) -> dict:
    prompt = output = thought = cost = n = 0.0
    for run in runs:
        for record in run.values():
            if record.get("status") != "OK":
                continue
            usage = record.get("usage") or {}
            prompt += usage.get("prompt_tokens", 0)
            output += usage.get("output_tokens", 0)
            thought += usage.get("thought_tokens", 0)
            cost += record.get("cost_inr", 0.0)
            n += 1
    if n == 0:
        return {"n": 0}
    mean_cost = cost / n
    return {
        "n": n,
        "mean_prompt_tokens": prompt / n,
        "mean_output_tokens": output / n,
        "mean_thought_tokens": thought / n,
        "mean_cost_inr": mean_cost,
        "mean_cost_inr_after_2026_12_01": mean_cost * 2,
    }


def score_runs(run_dirs: list[Path], dev_eval_path: Path = DEFAULT_DEV_EVAL_PATH) -> dict:
    n_runs = len(run_dirs)
    if n_runs not in (1, 3):
        return {"status": "INVALID", "reason": f"expected 1 or 3 run dirs, got {n_runs}"}

    matrix = load_matrix(dev_eval_path)
    runs = [_load_run(d) for d in run_dirs]

    failed_paper_runs = sum(1 for run in runs for record in run.values() if record.get("status") != "OK")
    if failed_paper_runs > 2:
        return {"status": "VOID", "failed_paper_runs": failed_paper_runs}

    rows_out = []
    caught_ids: list[str] = []
    fr_ids: list[str] = []
    found = 0
    r_total = s_total = 0
    mode = "SINGLE-RUN" if n_runs == 1 else "3-RUN"

    for paper in matrix.papers:
        paper_runs = [run.get(paper.paper_id) for run in runs]
        for row in paper.expected_rows:
            is_r = "-R" in row.id
            r_total += is_r
            s_total += not is_r
            matches = [_row_match(row, pr) for pr in paper_runs]
            statuses = [m["status"] for m in matches]
            scores = [m["score"] for m in matches]
            flag_vote, mode = _vote(statuses)
            if _matched_majority(statuses):
                found += 1
            if flag_vote == "flagged":
                (caught_ids if is_r else fr_ids).append(row.id)
            rows_out.append({
                "row_id": row.id, "paper_id": paper.paper_id, "is_r": is_r,
                "per_run_status": statuses, "per_run_score": scores,
                "vote": flag_vote,
            })

    caught, fr = len(caught_ids), len(fr_ids)

    if caught >= 12 and fr <= FR_CEILING:
        verdict = "ONE CALL BETTER"
    elif caught >= 12 and fr > FR_CEILING:
        verdict = "STRICTER, NOT BETTER"
    elif caught <= 4 or fr > FR_CEILING:
        verdict = "PRISM BETTER"
    else:
        verdict = "NO CLEAR DIFFERENCE"

    all_r_ids = {row.id for paper in matrix.papers for row in paper.expected_rows if "-R" in row.id}

    return {
        "status": "SCORED",
        "mode": mode,
        "n_runs": n_runs,
        "caught": caught, "caught_of": r_total,
        "false_rejections": fr, "false_rejections_of": s_total,
        "found": found, "found_of": r_total + s_total,
        "verdict": verdict,
        "release_bar_met": caught >= RELEASE_BAR_CAUGHT and fr <= RELEASE_BAR_FR,
        "release_bar": f"caught >= {RELEASE_BAR_CAUGHT} and false_rejections <= {RELEASE_BAR_FR}",
        "caught_breakdown": _caught_breakdown(caught_ids, all_r_ids),
        "failed_paper_runs": failed_paper_runs,
        "rows": rows_out,
    }


def _render_md(result: dict) -> str:
    lines = [
        "# Test B score (one gemini-4-carbon call per dev paper)",
        "",
        f"- status: {result['status']}",
        f"- mode: {result['mode']} (n_runs={result['n_runs']})",
        f"- caught: {result['caught']} / {result['caught_of']}",
        f"- false_rejections: {result['false_rejections']} / {result['false_rejections_of']}",
        f"- found: {result['found']} / {result['found_of']}",
        f"- verdict: {result['verdict']}",
        f"- release bar ({result['release_bar']}): {'yes' if result['release_bar_met'] else 'no'}",
        f"- failed_paper_runs: {result['failed_paper_runs']}",
        "",
        "## Caught breakdown (report only, never changes the verdict)",
        "",
    ]
    for key, value in result["caught_breakdown"].items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Other report-only fields", ""]
    lines.append(f"- unmatched_claims_by_verdict: {result.get('unmatched_claims_by_verdict')}")
    lines.append(f"- duplicate_claim_matches: {result.get('duplicate_claim_matches')}")
    qgr = result.get("quote_grounding_rate")
    lines.append(f"- quote_grounding_rate: {qgr:.4f}" if qgr is not None else "- quote_grounding_rate: NOT AVAILABLE")
    lines.append(f"- tokens_and_cost_per_paper: {result.get('tokens_and_cost_per_paper')}")
    lines += ["", "## Per-row table", "", "| row_id | per_run_status | vote | best_score |", "|---|---|---|---|"]
    for row in result["rows"]:
        best = max(row["per_run_score"]) if row["per_run_score"] else 0.0
        lines.append(f"| {row['row_id']} | {row['per_run_status']} | {row['vote']} | {best:.1f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    args = parser.parse_args(argv)

    result = score_runs(args.runs, args.dev_eval_path)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)

    if result["status"] in ("VOID", "INVALID"):
        args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"status={result['status']}")
        return 1

    matrix = load_matrix(args.dev_eval_path)
    runs = [_load_run(d) for d in args.runs]
    result["unmatched_claims_by_verdict"] = _unmatched_claims_by_verdict(matrix, runs)
    result["duplicate_claim_matches"] = _duplicate_claim_matches(matrix, runs)
    result["quote_grounding_rate"] = _quote_grounding_rate(matrix, runs)
    result["tokens_and_cost_per_paper"] = _tokens_and_cost_per_paper(runs)

    args.json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(_render_md(result), encoding="utf-8")
    print(
        f"status={result['status']} caught={result['caught']}/{result['caught_of']} "
        f"fr={result['false_rejections']}/{result['false_rejections_of']} verdict={result['verdict']}"
    )
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
