"""CLI: writes the 88 hand-reviewed dev S-row match decisions into
docs/evals/dev_match_map.json.

Input is docs/evals/auditor_rd/s_row_match_decisions_2026-10-27.json (final =
0-based run-1 claim index, or "NO_MATCH", under the "subset" match rule). The
default is a dry run: every check runs and the similarity report is written,
but the map is only rewritten with --write. Only S rows are touched, and only
the fields build_dev_match_map.py sets for an adjudicated row; every R row and
the metadata stay byte-identical.

Zero LLM calls. The similarity report reuses suggest_match_map's scorer
(rapidfuzz token_sort_ratio on claim_text_verbatim) and SCORE_FLOOR.

Usage:
  .\\.venv\\Scripts\\python.exe -m eval.apply_s_row_decisions            # dry run
  .\\.venv\\Scripts\\python.exe -m eval.apply_s_row_decisions --write
"""
import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from eval.match_map import MatchMap, fingerprint_claim_text
from eval.matrix_loader import load_matrix
from eval.suggest_match_map import SCORE_FLOOR

REPO_ROOT = Path(__file__).parent.parent.parent
EVALS_DIR = REPO_ROOT / "docs" / "evals"
RD_DIR = EVALS_DIR / "auditor_rd"
DEFAULT_DECISIONS_PATH = RD_DIR / "s_row_match_decisions_2026-10-27.json"
DEFAULT_GEMINI_PATH = RD_DIR / "s_row_judge_gemini_2026-10-27.md"
DEFAULT_CHATGPT_PATH = RD_DIR / "s_row_judge_chatgpt_2026-10-27.md"
DEFAULT_PART_PATHS = [RD_DIR / f"adjudication_s_input_part{n}.md" for n in (1, 2, 3)]
DEFAULT_DEV_EVAL_PATH = EVALS_DIR / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = EVALS_DIR / "dev_match_map.json"
DEFAULT_FIXTURE_DIR = EVALS_DIR / "fixtures" / "dev" / "run1"
DEFAULT_REPORT_PATH = REPO_ROOT / "Prism.PythonService" / "scratch" / "s_row_similarity_2026-10-27.md"

NO_MATCH = "NO_MATCH"
HIGH_BUCKET = 90
NO_MATCH_REASON = "extraction miss - no run-1 claim carries this row's assertion (subset rule)"

P_TO_ARXIV = {
    "P1": "2610.11519", "P2": "2610.11132", "P3": "2610.11135", "P4": "2610.10871",
    "P5": "2610.11291", "P6": "2610.11312", "P7": "2610.10590", "P8": "2610.12124",
    "P9": "2610.12375", "P10": "2610.12176", "P11": "2610.12114", "P12": "2610.12168",
}
EXPECTED_CLAIM_COUNTS = {
    "2610.10590": 37, "2610.10871": 34, "2610.11132": 26, "2610.11135": 42,
    "2610.11291": 39, "2610.11312": 24, "2610.11519": 33, "2610.12114": 31,
    "2610.12124": 32, "2610.12168": 16, "2610.12176": 21, "2610.12375": 27,
}
# What the full 88-row decision set must look like (Phase 1 checks 1 and 1b).
FULL_EXPECTATIONS = {
    "rows": 88, "int": 67, "no_match": 21, "judges_agreed": 68, "nitin_review": 20,
    "agreed_match": 58, "agreed_no_match": 9, "calibration_no_match": 1,
    "disagreement": 2, "low_confidence": 18,
}
CALIBRATION_NO_MATCH_ROW = "P5-S3"


def _paper_id(arxiv: str) -> str:
    return f"arxiv-{arxiv}v1"


def _p_label(row_id: str) -> str:
    return row_id.split("-")[0]


def _is_s_row(row_id: str) -> bool:
    return re.fullmatch(r"P\d+-S\d+", row_id) is not None


# ---------------------------------------------------------------------------
# Validation (Phase 1 items 1 and 1b)
# ---------------------------------------------------------------------------
def validate_decisions(decisions: dict, claim_counts: dict[str, int]) -> None:
    """Structural checks on the decisions file. Raises ValueError on the first
    failing group, listing every problem in it."""
    problems: list[str] = []
    rows = decisions["rows"]
    ids = [r["row_id"] for r in rows]

    if decisions.get("match_rule") != "subset":
        problems.append(f"match_rule is {decisions.get('match_rule')!r}, expected 'subset'")
    if len(set(ids)) != len(ids):
        problems.append(f"duplicate row_ids: {sorted(i for i, n in Counter(ids).items() if n > 1)}")
    for field in ("decided_by", "decided_on"):
        if not decisions.get(field):
            problems.append(f"{field} missing")

    for r in rows:
        rid = r["row_id"]
        if not _is_s_row(rid):
            problems.append(f"{rid}: not an S row id")
            continue
        if r.get("reviewed") is not True:
            problems.append(f"{rid}: reviewed is not true")
        final = r.get("final")
        if final is None:
            problems.append(f"{rid}: final is null")
        arxiv = P_TO_ARXIV.get(_p_label(rid))
        if arxiv is None or r.get("arxiv") != arxiv:
            problems.append(f"{rid}: arxiv {r.get('arxiv')!r} does not match its P-label (expected {arxiv!r})")
            continue
        if isinstance(final, int) and not isinstance(final, bool):
            if arxiv not in claim_counts or not 0 <= final < claim_counts[arxiv]:
                problems.append(f"{rid}: final {final} out of range for {arxiv} ({claim_counts.get(arxiv)} claims)")
        elif final != NO_MATCH and final is not None:
            problems.append(f"{rid}: final {final!r} is neither an int nor {NO_MATCH!r}")
        if r.get("decision_source") not in ("judges_agreed", "nitin_review"):
            problems.append(f"{rid}: unknown decision_source {r.get('decision_source')!r}")

    n_int = sum(1 for r in rows if isinstance(r["final"], int))
    n_nm = sum(1 for r in rows if r["final"] == NO_MATCH)
    exp = decisions.get("expected_totals", {})
    if (exp.get("match"), exp.get("no_match"), exp.get("total")) != (n_int, n_nm, len(rows)):
        problems.append(
            f"expected_totals {exp} disagree with rows (match={n_int}, no_match={n_nm}, total={len(rows)})"
        )
    if problems:
        raise ValueError("decisions file failed validation:\n  " + "\n  ".join(problems))


def parse_judge_table(path: Path, chatgpt: bool) -> dict[str, tuple]:
    """{row_id: (pick, confidence)} from a judge file's main table. Stops at the
    first '#' heading (later hesitation sections would re-parse rows). A
    repeated row id or an unparsable row is an error."""
    out: dict[str, tuple] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        rid = cells[0].replace("*", "").strip()
        if chatgpt and "/" in rid:
            rid = rid.split("/")[-1].strip()
        if not _is_s_row(rid):
            continue
        pick_raw = cells[1].replace("*", "").strip()
        conf = cells[2].replace("*", "").strip().lower()
        if pick_raw.upper().startswith("NO"):
            pick = NO_MATCH
        elif pick_raw.isdigit():
            pick = int(pick_raw)
        else:
            raise ValueError(f"{path.name}: cannot parse pick {pick_raw!r} for {rid}")
        if conf not in ("high", "medium", "low"):
            raise ValueError(f"{path.name}: cannot parse confidence {conf!r} for {rid}")
        if rid in out:
            raise ValueError(f"{path.name}: row id {rid} appears twice in the main table")
        out[rid] = (pick, conf)
    return out


def check_judges(decisions: dict, gemini: dict, chatgpt: dict, expect: Optional[dict]) -> dict[str, int]:
    """Phase 1b: judge files vs decisions file. Returns the recomputed category
    counts; raises ValueError on any mismatch (and, if expect is given, on any
    count that differs from it)."""
    problems: list[str] = []
    rows = decisions["rows"]
    ids = {r["row_id"] for r in rows}
    for name, table in (("gemini", gemini), ("chatgpt", chatgpt)):
        if set(table) != ids:
            problems.append(f"{name}: missing {sorted(ids - set(table))}, extra {sorted(set(table) - ids)}")

    cats: dict[str, list[str]] = {
        k: [] for k in ("agreed_match", "agreed_no_match", "calibration_no_match", "disagreement", "low_confidence")
    }
    for r in rows:
        rid = r["row_id"]
        if rid not in gemini or rid not in chatgpt:
            continue
        (gp, gc), (cp, cc) = gemini[rid], chatgpt[rid]
        if r["gemini"] != [gp, gc] or r["chatgpt"] != [cp, cc]:
            problems.append(f"{rid}: decisions file judge fields {r['gemini']}/{r['chatgpt']} != judge files {[gp, gc]}/{[cp, cc]}")
        if gp != cp:
            cat = "disagreement"
        elif rid == CALIBRATION_NO_MATCH_ROW:
            cat = "calibration_no_match"
        elif gc == "high" and cc == "high":
            cat = "agreed_match" if gp != NO_MATCH else "agreed_no_match"
        else:
            cat = "low_confidence"
        cats[cat].append(rid)
        if cat in ("agreed_match", "agreed_no_match", "calibration_no_match") and r["final"] != gp:
            problems.append(f"{rid}: final {r['final']!r} != agreed pick {gp!r}")

    review = {r["row_id"] for r in rows if r["decision_source"] == "nitin_review"}
    if review != set(cats["disagreement"]) | set(cats["low_confidence"]):
        problems.append("nitin_review rows are not exactly the disagreements plus low-confidence rows")

    counts = {k: len(v) for k, v in cats.items()}
    if expect:
        counts_all = {
            **counts,
            "rows": len(rows),
            "int": sum(1 for r in rows if isinstance(r["final"], int)),
            "no_match": sum(1 for r in rows if r["final"] == NO_MATCH),
            "judges_agreed": sum(1 for r in rows if r["decision_source"] == "judges_agreed"),
            "nitin_review": len(review),
        }
        for key, want in expect.items():
            if counts_all[key] != want:
                problems.append(f"count {key}: got {counts_all[key]}, expected {want}")
    if problems:
        raise ValueError("judge cross-check failed:\n  " + "\n  ".join(problems))
    return counts


def parse_part_claims(paths: list[Path]) -> dict[tuple[str, int], str]:
    """{(paper_id, index): 'text | summary'} from the blind input part files."""
    out: dict[tuple[str, int], str] = {}
    for path in paths:
        paper = None
        in_claims = False
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            m = re.match(r"## (arxiv-\S+)", line)
            if m:
                paper, in_claims = m.group(1), False
                continue
            if line.startswith("### "):
                in_claims = line.strip() == "### CLAIMS"
                continue
            m = re.match(r"(\d+)\. (.*)$", line)
            if in_claims and m and paper:
                out[(paper, int(m.group(1)))] = m.group(2)
    return out


def check_part_alignment(decisions: dict, claims_by_arxiv: dict[str, list[dict]], part_claims: dict) -> None:
    problems = []
    for r in decisions["rows"]:
        if not isinstance(r["final"], int):
            continue
        claim = claims_by_arxiv[r["arxiv"]][r["final"]]
        part = part_claims.get((_paper_id(r["arxiv"]), r["final"]))
        if part is None or not part.startswith(claim["claim_text_verbatim"]):
            problems.append(f"{r['row_id']}: claim {r['final']} text differs between fixture and part files")
    if problems:
        raise ValueError("index alignment failed:\n  " + "\n  ".join(problems))


# ---------------------------------------------------------------------------
# Applying decisions
# ---------------------------------------------------------------------------
def load_fixture_claims(fixture_dir: Path, arxivs: set[str]) -> dict[str, list[dict]]:
    out = {}
    for arxiv in sorted(arxivs):
        claims = json.loads((fixture_dir / f"{_paper_id(arxiv)}.json").read_text(encoding="utf-8"))["claims"]
        if [c["index"] for c in claims] != list(range(len(claims))):
            raise ValueError(f"{_paper_id(arxiv)}: claim indexes are not 0..N-1 contiguous")
        out[arxiv] = claims
    return out


def apply_decisions(map_raw: dict, decisions: dict, claims_by_arxiv: dict[str, list[dict]]) -> dict:
    """Returns a deep copy of map_raw with the decided S rows filled in. Only
    S rows and only the fields below change."""
    new = copy.deepcopy(map_raw)
    for r in decisions["rows"]:
        rid, final = r["row_id"], r["final"]
        if rid not in new["rows"]:
            raise ValueError(f"{rid}: not in the match map")
        row = new["rows"][rid]
        if isinstance(final, int):
            claims = claims_by_arxiv[r["arxiv"]]
            if not 0 <= final < len(claims):
                raise ValueError(f"{rid}: claim index {final} out of range (0..{len(claims) - 1})")
            row["persisted_claim_id"] = None
            row["claim_fingerprint"] = fingerprint_claim_text(claims[final]["claim_text_verbatim"])
            row["reason"] = f"adjudicated match to run1 claim index {final}"
            row["confirmed_no_match"] = False
        else:
            row["claim_fingerprint"] = None
            row["reason"] = NO_MATCH_REASON
            row["confirmed_no_match"] = True
        row["decided_by"] = decisions["decided_by"]
        row["decided_on"] = decisions["decided_on"]
        if isinstance(final, int):
            row["suggested"] = None
    return new


def check_only_s_rows_changed(old: dict, new: dict) -> None:
    if old["metadata"] != new["metadata"] or list(old) != list(new):
        raise ValueError("metadata or top-level keys changed")
    if list(old["rows"]) != list(new["rows"]):
        raise ValueError("row set or order changed")
    changed_non_s = [k for k in old["rows"] if not _is_s_row(k) and old["rows"][k] != new["rows"][k]]
    if changed_non_s:
        raise ValueError(f"non-S rows changed: {changed_non_s}")


def serialize(raw: dict) -> str:
    return json.dumps(raw, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Similarity report
# ---------------------------------------------------------------------------
def _bucket(score: float) -> str:
    if score >= HIGH_BUCKET:
        return f">={HIGH_BUCKET}"
    return f"{SCORE_FLOOR}-{HIGH_BUCKET - 1}" if score >= SCORE_FLOOR else f"<{SCORE_FLOOR}"


def similarity(decisions: dict, row_text: dict[str, str], claims_by_arxiv: dict[str, list[dict]]):
    """(matched, no_match): matched = [(row_id, index, score)]; no_match =
    [(row_id, best_index, score)]. Same scorer as suggest_match_map, no floor."""
    matched, no_match = [], []
    for r in decisions["rows"]:
        text = row_text[r["row_id"]]
        claims = claims_by_arxiv[r["arxiv"]]
        if isinstance(r["final"], int):
            score = fuzz.token_sort_ratio(text, claims[r["final"]]["claim_text_verbatim"])
            matched.append((r["row_id"], r["final"], round(score, 1)))
        else:
            best = max(claims, key=lambda c: (fuzz.token_sort_ratio(text, c["claim_text_verbatim"]), -c["index"]))
            score = fuzz.token_sort_ratio(text, best["claim_text_verbatim"])
            no_match.append((r["row_id"], best["index"], round(score, 1)))
    return matched, no_match


def write_report(path: Path, matched, no_match, row_text, claims_by_arxiv, arxiv_of) -> None:
    def snippet(rid: str, idx: int) -> str:
        return claims_by_arxiv[arxiv_of[rid]][idx]["claim_text_verbatim"][:110].replace("|", "/")

    lines = ["# S-row similarity report, 2026-10-27", "",
             f"Scorer: rapidfuzz token_sort_ratio on claim_text_verbatim (as eval/suggest_match_map.py). "
             f"Buckets: >={HIGH_BUCKET}, {SCORE_FLOOR}-{HIGH_BUCKET - 1}, <{SCORE_FLOOR}. Informational only; no decision changed.", "",
             f"## (a) Matched pairs ({len(matched)})", ""]
    counts = Counter(_bucket(s) for _, _, s in matched)
    lines += [f"Bucket counts: {dict(counts)}", "", "| Row | Claim | Score | Bucket | Claim text |", "|---|---|---|---|---|"]
    for rid, idx, s in sorted(matched, key=lambda t: t[2]):
        lines.append(f"| {rid} | {idx} | {s} | {_bucket(s)} | {snippet(rid, idx)} |")
    lines += ["", f"## (b) NO_MATCH rows ({len(no_match)}): best claim in the paper", "",
              "| Row | Best claim | Score | Bucket | Claim text |", "|---|---|---|---|---|"]
    for rid, idx, s in sorted(no_match, key=lambda t: -t[2]):
        lines.append(f"| {rid} | {idx} | {s} | {_bucket(s)} | {snippet(rid, idx)} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run(
    decisions_path: Path, match_map_path: Path, fixture_dir: Path, dev_eval_path: Path,
    *, write: bool = False, gemini_path: Optional[Path] = None, chatgpt_path: Optional[Path] = None,
    part_paths: Optional[list[Path]] = None, report_path: Optional[Path] = None,
    expect: Optional[dict] = None, expected_claim_counts: Optional[dict] = None,
) -> dict:
    """Runs every check, builds the new map in memory, writes the similarity
    report if report_path is given, and rewrites the map only if write. Any
    failed check raises ValueError before anything is written."""
    decisions = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
    arxivs = {r["arxiv"] for r in decisions["rows"]}
    claims_by_arxiv = load_fixture_claims(fixture_dir, arxivs)
    claim_counts = {a: len(c) for a, c in claims_by_arxiv.items()}
    if expected_claim_counts is not None and any(claim_counts.get(a) != n for a, n in expected_claim_counts.items()):
        raise ValueError(f"fixture claim counts {claim_counts} differ from expected {expected_claim_counts}")

    validate_decisions(decisions, claim_counts)
    if expect and (expect["rows"], expect["int"], expect["no_match"]) != (
        len(decisions["rows"]), sum(isinstance(r["final"], int) for r in decisions["rows"]),
        sum(r["final"] == NO_MATCH for r in decisions["rows"]),
    ):
        raise ValueError(f"decision totals differ from expected {expect}")
    if gemini_path and chatgpt_path:
        check_judges(
            decisions, parse_judge_table(gemini_path, False), parse_judge_table(chatgpt_path, True), expect
        )
    if part_paths:
        check_part_alignment(decisions, claims_by_arxiv, parse_part_claims(part_paths))

    map_text = Path(match_map_path).read_text(encoding="utf-8", newline="")
    map_raw = json.loads(map_text)
    if serialize(map_raw) != map_text:
        raise ValueError(f"{match_map_path}: file is not in the canonical JSON style; refusing to rewrite it")
    s_in_map = {k for k in map_raw["rows"] if _is_s_row(k)}
    s_decided = {r["row_id"] for r in decisions["rows"]}
    if s_in_map != s_decided:
        raise ValueError(f"S rows differ: missing {sorted(s_in_map - s_decided)}, extra {sorted(s_decided - s_in_map)}")

    new_raw = apply_decisions(map_raw, decisions, claims_by_arxiv)
    check_only_s_rows_changed(map_raw, new_raw)
    MatchMap.model_validate(new_raw)

    matrix = load_matrix(dev_eval_path)
    row_text = {row.id: row.claim_text_verbatim for p in matrix.papers for row in p.expected_rows}
    matched, no_match = similarity(decisions, row_text, claims_by_arxiv)
    if report_path:
        write_report(report_path, matched, no_match, row_text, claims_by_arxiv, {r["row_id"]: r["arxiv"] for r in decisions["rows"]})

    changed = [k for k in new_raw["rows"] if new_raw["rows"][k] != map_raw["rows"][k]]
    if write:
        Path(match_map_path).write_text(serialize(new_raw), encoding="utf-8", newline="")
    return {"matched": matched, "no_match": no_match, "changed": changed, "written": write,
            "claims_by_arxiv": claims_by_arxiv, "arxiv_of": {r["row_id"]: r["arxiv"] for r in decisions["rows"]}}


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def _print_summary(result: dict) -> None:
    matched, no_match, claims = result["matched"], result["no_match"], result["claims_by_arxiv"]
    print(f"S rows: {len(matched)} matches / {len(no_match)} NO_MATCH ({len(matched) + len(no_match)} total)")
    low = [m for m in matched if m[2] < SCORE_FLOOR]
    print(f"\nMatched pairs scoring < {SCORE_FLOOR} ({len(low)}):")
    for rid, idx, s in sorted(low, key=lambda t: t[2]):
        print(f"  {rid:7} claim {idx:>2}  {s:5.1f}  {_ascii(claims[result['arxiv_of'][rid]][idx]['claim_text_verbatim'][:90])}")
    high = [n for n in no_match if n[2] >= HIGH_BUCKET]
    print(f"\nNO_MATCH rows whose best claim scores >= {HIGH_BUCKET} ({len(high)}):")
    for rid, idx, s in high:
        print(f"  {rid:7} best claim {idx:>2}  {s:5.1f}  {_ascii(claims[result['arxiv_of'][rid]][idx]['claim_text_verbatim'][:90])}")
    print(f"\nS rows that {'were written' if result['written'] else 'would change'} ({len(result['changed'])}):")
    print("  " + ", ".join(result["changed"]))
    if not result["written"]:
        print("\nDRY RUN: nothing written to the map. Re-run with --write to apply.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="rewrite dev_match_map.json (default: dry run)")
    parser.add_argument("--decisions-path", type=Path, default=DEFAULT_DECISIONS_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        result = run(
            args.decisions_path, args.match_map_path, args.fixture_dir, args.dev_eval_path,
            write=args.write, gemini_path=DEFAULT_GEMINI_PATH, chatgpt_path=DEFAULT_CHATGPT_PATH,
            part_paths=DEFAULT_PART_PATHS, report_path=args.report_path,
            expect=FULL_EXPECTATIONS, expected_claim_counts=EXPECTED_CLAIM_COUNTS,
        )
    except ValueError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1
    _print_summary(result)
    print(f"\nreport: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
