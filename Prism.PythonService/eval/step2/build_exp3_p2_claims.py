"""Step 2: builds the --claims file for auditing 7 saved pass-2 claims with eval/replay_audit.py.

For each of the fixed rows P2-R3, P2-R4, P3-R1, P5-R3, P8-R3, P9-R1, P11-R3 it takes the row's hand-matched
candidates from docs/evals/exp3_b4/c1_adjudication.csv, maps them through c1_key.json to the two pass-2 replay runs
(docs/evals/fixtures/dev/exp3/pass2_r1 and pass2_r2) and picks ONE claim per row:

  1. only candidates attributed to pass 2 count (a candidate that is pass 1 in a run where it is present is out);
  2. the pick is a candidate present in BOTH runs; more than one -> the lowest candidate id;
  3. none in both runs -> the lowest-id candidate present in pass2_r1, with flag = true.

The picked text must be the same in r1 and r2 after normalize_for_match, else the build aborts. Each output entry is
an inline replay_audit claim: claim_index = 1000 + the r1 merged index, plus claim_text_verbatim and claim_summary
exactly as stored in the r1 fixture.

--check-text then looks for each claim in the paper text replay_audit would send (replay_audit._load_paper_text),
with normalize_for_match and fuzz.partial_ratio >= RAPIDFUZZ_THRESHOLD, and prints found yes/no and the score
(never any paper text). Exit 1 if a claim is not found.

Reads only the three inputs above (and, with --check-text, the cached paper text of the papers involved). It does not
lock or score anything and opens none of the held-out, sealed or rubric files. No LLM call.

Usage (from Prism.PythonService):
  uv run python -m eval.step2.build_exp3_p2_claims
  uv run python -m eval.step2.build_exp3_p2_claims --check-text
"""
import argparse
import csv
import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from rapidfuzz import fuzz

from eval import exp3_b4
from eval.blind_review import C1Answer
from extraction.grounding import RAPIDFUZZ_THRESHOLD, normalize_for_match

ROW_IDS = ("P2-R3", "P2-R4", "P3-R1", "P5-R3", "P8-R3", "P9-R1", "P11-R3")
INLINE_INDEX_BASE = 1000
RUN_1, RUN_2 = exp3_b4.PASS2_RUNS            # "pass2_r1", "pass2_r2"
DEFAULT_ADJUDICATION = exp3_b4.DEFAULT_OUTPUT_DIR / "c1_adjudication.csv"
DEFAULT_KEY = exp3_b4.DEFAULT_OUTPUT_DIR / "c1_key.json"
DEFAULT_OUT = exp3_b4.DOCS / "evals" / "exp3_pass2_7_claims.json"

LoadClaims = Callable[[str, str], list[dict]]    # (run, paper_id) -> the run's merged claims
LoadText = Callable[[str], str]                  # paper_id -> paper text


class BuildError(Exception):
    """The inputs do not allow the rule to be applied; nothing is written."""


# --- selection -----------------------------------------------------------------------------------------

def _runs_present(info: Mapping) -> list[str]:
    return [run for run in exp3_b4.PASS2_RUNS if info[run]["present"]]


def _attributed_to_pass2(info: Mapping) -> bool:
    """Present in at least one run, and pass 2 in every run where it is present."""
    present = _runs_present(info)
    return bool(present) and all(info[run]["pass"] == 2 for run in present)


def select_pick(row_id: str, match_ids: Sequence[str], key: Mapping[str, Mapping]) -> tuple[str, bool]:
    """(candidate id, flag) for one row. flag is True only for the fallback (no usable candidate in both runs)."""
    unknown = sorted(cid for cid in match_ids if cid not in key)
    if unknown:
        raise BuildError(f"{row_id}: candidate id(s) {unknown} are not in c1_key.json")
    usable = sorted(cid for cid in set(match_ids) if _attributed_to_pass2(key[cid]))
    in_both = [cid for cid in usable if all(key[cid][run]["present"] for run in exp3_b4.PASS2_RUNS)]
    if in_both:
        return in_both[0], False
    in_r1 = [cid for cid in usable if key[cid][RUN_1]["present"]]
    if in_r1:
        return in_r1[0], True
    raise BuildError(f"{row_id}: no matched candidate is a pass-2 claim of {RUN_1} (matches: {sorted(match_ids)})")


def build_entries(
    rows: Mapping[str, tuple[str, Sequence[str]]], key: Mapping[str, Mapping], load_claims: LoadClaims,
    row_ids: Sequence[str] = ROW_IDS,
) -> list[dict]:
    """rows = {row_id: (paper_id, match_ids)}. One entry per picked candidate, in row order; a candidate picked by
    two rows is listed once with both row ids."""
    entries: dict[str, dict] = {}
    for row_id in row_ids:
        if row_id not in rows:
            raise BuildError(f"{row_id}: not in the adjudication file")
        paper_id, match_ids = rows[row_id]
        if not match_ids:
            raise BuildError(f"{row_id}: the adjudication file has no match for this row")
        cid, flag = select_pick(row_id, match_ids, key)
        info = key[cid]
        if info["paper_id"] != paper_id:
            raise BuildError(f"{row_id}: {cid} belongs to {info['paper_id']}, not {paper_id}")
        if cid in entries:
            entries[cid]["row_ids"].append(row_id)
            continue
        r1_index = info[RUN_1]["merged_index"]
        r2_index = info[RUN_2]["merged_index"] if info[RUN_2]["present"] else None
        claim_r1 = load_claims(RUN_1, paper_id)[r1_index]
        if r2_index is not None:
            claim_r2 = load_claims(RUN_2, paper_id)[r2_index]
            if normalize_for_match(claim_r1["claim_text_verbatim"]) != normalize_for_match(claim_r2["claim_text_verbatim"]):
                raise BuildError(f"{row_id}: {cid} has different text in {RUN_1} (index {r1_index}) and {RUN_2} (index {r2_index})")
        entries[cid] = {
            "row_ids": [row_id],
            "paper_id": paper_id,
            "claim_index": INLINE_INDEX_BASE + r1_index,
            "claim_text_verbatim": claim_r1["claim_text_verbatim"],
            "claim_summary": claim_r1["claim_summary"],
            "candidate_id": cid,
            "r1_index": r1_index,
            "r2_index": r2_index,
            "flag": flag,
        }
    return list(entries.values())


# --- inputs --------------------------------------------------------------------------------------------

def read_adjudication(path: Path) -> dict[str, tuple[str, list[str]]]:
    """{row_id: (paper_id, match_ids)}, parsed like exp3_b4 lock does (C1Answer: "none" or blank = no match)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        answers = [C1Answer.model_validate(raw) for raw in csv.DictReader(f)]
    return {a.row_id: (a.paper_id, list(a.match_ids)) for a in answers}


def read_key(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))["candidates"]


# --- text check ----------------------------------------------------------------------------------------

def check_text(entries: Sequence[Mapping], load_text: LoadText) -> list[dict]:
    """[{row_ids, paper_id, candidate_id, score, found}]. Paper text is loaded and normalized once per paper."""
    normalized: dict[str, str] = {}
    results = []
    for entry in entries:
        paper_id = entry["paper_id"]
        if paper_id not in normalized:
            normalized[paper_id] = normalize_for_match(load_text(paper_id))
        score = float(fuzz.partial_ratio(normalize_for_match(entry["claim_text_verbatim"]), normalized[paper_id]))
        results.append({
            "row_ids": list(entry["row_ids"]), "paper_id": paper_id, "candidate_id": entry["candidate_id"],
            "score": score, "found": score >= RAPIDFUZZ_THRESHOLD,
        })
    return results


def format_check(results: Sequence[Mapping]) -> str:
    lines = [f"text check: partial_ratio >= {RAPIDFUZZ_THRESHOLD} on normalize_for_match text"]
    for r in results:
        lines.append(
            f"  {'/'.join(r['row_ids']):<10} {r['paper_id']} {r['candidate_id']} "
            f"found={'yes' if r['found'] else 'NO'} score={r['score']:.1f}"
        )
    missing = sum(1 for r in results if not r["found"])
    lines.append(f"{len(results) - missing} of {len(results)} found" + (f", {missing} NOT FOUND" if missing else ""))
    return "\n".join(lines)


# --- CLI -----------------------------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adjudication", type=Path, default=DEFAULT_ADJUDICATION)
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY)
    parser.add_argument("--replay-root", type=Path, default=exp3_b4.DEFAULT_REPLAY_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true", help="overwrite an existing, different output file")
    parser.add_argument(
        "--check-text", action="store_true",
        help="look for each claim in the paper text replay_audit would send; exit 1 if one is not found",
    )
    return parser


def main(argv: Sequence[str] | None = None, load_text: LoadText | None = None) -> int:
    """load_text is for tests; by default replay_audit._load_paper_text (imported only for --check-text)."""
    args = _parser().parse_args(argv)
    try:
        entries = build_entries(
            read_adjudication(args.adjudication), read_key(args.key),
            lambda run, paper_id: exp3_b4._load_merged_claims(args.replay_root, run, paper_id),
        )
    except BuildError as exc:
        print(f"ABORT: {exc}")
        return 1

    text = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
    if args.out.exists() and args.out.read_text(encoding="utf-8") != text and not args.force:
        print(f"ABORT: {args.out} exists and differs; use --force to overwrite it")
        return 1
    if not args.out.exists() or args.force:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(f"{len(entries)} claims in {args.out}")
    for e in entries:
        print(f"  {'/'.join(e['row_ids']):<10} {e['paper_id']} {e['candidate_id']} claim_index={e['claim_index']} "
              f"r1={e['r1_index']} r2={e['r2_index']} flag={str(e['flag']).lower()}")

    if not args.check_text:
        return 0
    if load_text is None:
        from eval import replay_audit
        load_text = replay_audit._load_paper_text
        text_errors: tuple = (replay_audit.PaperTextError,)
    else:
        text_errors = (OSError, ValueError)
    try:
        results = check_text(entries, load_text)
    except text_errors as exc:
        print(f"ABORT: cannot load paper text: {exc}")
        return 1
    print(format_check(results))
    return 0 if all(r["found"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
