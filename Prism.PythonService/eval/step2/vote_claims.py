"""Step 2: per-claim labels and 2-of-3 votes over three replay_audit folders, for any --claims file.

For every claim of the claims file it reads the three replay folders (the 3 repeats of one arm) and prints

  - the RAW label of runs 1-3 (the claim's final label, grounding ignored),
  - the EFFECTIVE label of runs 1-3 (not_supported when the claim is missing, i.e. grounding rejected it),
  - the model that served each audit call,
  - two votes, each by the same rule: "flagged >= 2/3" (partially_supported or not_supported, as
    step1.core.is_flagged) else "supported >= 2/3" else "split".

The RAW vote is the primary result (the pre-registered "caught" rule): it is printed first and the totals line
"caught k of N" counts RAW. The EFFECTIVE vote is printed beside it, report-only, with its own totals. Fallback-served
audits (a claim whose audit_model_served is not the folder's run_config.auditor_model) are counted.

Read-only; no LLM call; no candidate arm. Anything wrong with the inputs is listed as INVALID and the exit code is 1:
a folder missing or without an OK _summary.json or run_config, run_configs or prompt hashes that differ between the
folders, a claim missing from a folder, a header.claims_scope that is not the claims file's, an unknown label.

Usage (from Prism.PythonService):
  uv run python -m eval.step2.vote_claims --claims ..\\docs\\evals\\exp3_pass2_7_claims.json `
      --fixture-dir <folder1> --fixture-dir <folder2> --fixture-dir <folder3> [--json-out out.json]
"""
import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from eval import score_a1
from eval.score_full_check import _load_meta
from eval.step1 import common, core

REPEATS = common.REPEATS                  # 3 folders
VOTES_NEEDED = score_a1.VOTES_NEEDED      # 2
VOTE_FLAGGED = "flagged >= 2/3"
VOTE_SUPPORTED = "supported >= 2/3"
VOTE_SPLIT = "split"


def vote(labels: Sequence[str]) -> str:
    """The 2-of-3 vote of one claim's three labels."""
    if score_a1._votes(list(labels), core.FLAG_LABELS) >= VOTES_NEEDED:
        return VOTE_FLAGGED
    if score_a1._votes(list(labels), "supported") >= VOTES_NEEDED:
        return VOTE_SUPPORTED
    return VOTE_SPLIT


def collect(claims_path: Path, folders: Sequence[Path]) -> tuple[dict, list[str]]:
    """({claims: [...], totals: {...}, folders: [...]}, invalid). The payload is complete only when invalid is empty."""
    invalid: list[str] = []
    if len(folders) != REPEATS:
        invalid.append(f"expected exactly {REPEATS} --fixture-dir folders, got {len(folders)}")
        return {}, invalid
    entries = common.load_claims_file(claims_path)
    metas = _load_meta(list(folders), invalid)
    auditor_models = [m.config["auditor_model"] if m.config else None for m in metas]

    for folder in folders:
        common.check_claims_present(folder, entries, invalid)
    paper_ids = sorted({paper_id for paper_id, _, _ in entries})
    hashes = {str(f): common.prompt_hashes(f, paper_ids) for f in folders}
    hashes = {folder: found for folder, found in hashes.items() if found}   # a missing folder is reported above
    if len({frozenset(found) for found in hashes.values()}) > 1 or any(len(found) > 1 for found in hashes.values()):
        shown = {folder: sorted(found) for folder, found in hashes.items()}
        invalid.append(f"prompt_hash differs between or inside the folders: {shown}")

    cache = common.FixtureCache()
    claims = []
    for paper_id, index, row_ids in entries:
        reads = [cache.read(folder, paper_id, index, invalid) for folder in folders]
        if any(r is None for r in reads):
            continue
        raw = [r.raw for r in reads]
        effective = [r.effective for r in reads]
        served = [r.served for r in reads]
        fallback = [s is not None and a is not None and s != a for s, a in zip(served, auditor_models)]
        claims.append({
            "paper_id": paper_id, "claim_index": index, "row_ids": list(row_ids),
            "raw": raw, "effective": effective, "served": served, "fallback": fallback,
            "raw_vote": vote(raw), "effective_vote": vote(effective),
        })
    total = len(claims)
    totals = {
        "claims": total,
        "raw": {"caught": sum(c["raw_vote"] == VOTE_FLAGGED for c in claims),
                "supported": sum(c["raw_vote"] == VOTE_SUPPORTED for c in claims),
                "split": sum(c["raw_vote"] == VOTE_SPLIT for c in claims)},
        "effective": {"caught": sum(c["effective_vote"] == VOTE_FLAGGED for c in claims),
                      "supported": sum(c["effective_vote"] == VOTE_SUPPORTED for c in claims),
                      "split": sum(c["effective_vote"] == VOTE_SPLIT for c in claims)},
        "fallback_served_audits": sum(sum(c["fallback"]) for c in claims),
        "audits": total * REPEATS,
    }
    payload = {
        "claims_file": str(claims_path), "folders": [str(f) for f in folders],
        "auditor_models": auditor_models, "claims": claims, "totals": totals,
    }
    return payload, invalid


def _short(label: str | None) -> str:
    return {"supported": "S", "partially_supported": "P", "not_supported": "N"}.get(label or "", str(label))


def format_report(payload: dict) -> str:
    lines = ["RAW = the claim's own label (primary, pre-registered). EFFECTIVE = not_supported when grounding rejected the claim (report-only).",
             "labels per run 1-3: S supported, P partially_supported, N not_supported; * = served by a fallback model", ""]
    for c in payload["claims"]:
        star = ["*" if f else "" for f in c["fallback"]]
        raw = " ".join(_short(x) for x in c["raw"])
        eff = " ".join(_short(x) for x in c["effective"])
        lines.append(f"{'/'.join(c['row_ids']) or '-':<10} {c['paper_id']}#{c['claim_index']}")
        lines.append(f"    RAW       {raw:<8} -> {c['raw_vote']}")
        lines.append(f"    EFFECTIVE {eff:<8} -> {c['effective_vote']}")
        lines.append(f"    served    {' | '.join(f'{s}{m}' for s, m in zip(c['served'], star))}")
    t = payload["totals"]
    lines += [
        "",
        f"RAW       caught {t['raw']['caught']} of {t['claims']} (supported {t['raw']['supported']}, split {t['raw']['split']})",
        (
            f"EFFECTIVE caught {t['effective']['caught']} of {t['claims']} (supported {t['effective']['supported']}, "
            f"split {t['effective']['split']})  [report-only]"
        ),
        f"fallback-served audits: {t['fallback_served_audits']} of {t['audits']}",
    ]
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, action="append", default=[], help="give exactly 3 times, repeat 1 to 3")
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload, invalid = collect(args.claims, args.fixture_dir)
    if invalid:
        print("INVALID - no result:")
        for reason in dict.fromkeys(invalid):
            print(f"  - {reason}")
        return 1
    print(format_report(payload))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
