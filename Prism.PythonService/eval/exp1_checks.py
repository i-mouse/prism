"""Experiment 1 free checks (offline, no LLM calls, golden papers only).

  (a) VERDICT regex over the frozen Call #3 audit logs vs the fixture labels,
      for the golden-matched claims of run A (hash cb3272cce551) and run B
      (hash 0bcf9d44e619).
  (b) Do REFLEX-M02 and REFLEX-M09 map to the same extracted claim, per set?

Only the six named golden log groups are opened (chat ids below); no
directory is scanned and nothing held-out is read.

  uv run python -m eval.exp1_checks
"""
import json
import sys
from pathlib import Path

from rapidfuzz import fuzz

from eval.exp1_common import (
    AUDIT_LOG_DIR,
    SETS,
    golden_selection,
    parse_verdict,
)
from eval.match_map import fingerprint_claim_text

# Frozen Call #3 log groups: (set, paper_id) -> filename suffix after the timestamp.
LOG_GROUPS = {
    ("A", "arxiv-2303.11366v4"): "738ee4f1-edb2-4131-b46e-6806a80372a9_dd020c88-b0f0-4cbf-a188-974f37985c42.json",
    ("A", "arxiv-2210.03629v3"): "cd327513-e38f-4126-96c2-8e3da08e8d7c_manual-rerun-react-20261007T080846Z.json",
    ("A", "arxiv-2201.11903v6"): "265f1dc0-efb4-4c03-8aae-269120db5062_manual-rerun-cot-20261007T081810Z.json",
    ("B", "arxiv-2303.11366v4"): "eval-rerun-2f894cd6-0e9a-46bd-888f-cd05e6341bea_eval-rerun-reflexion.pdf.json",
    ("B", "arxiv-2210.03629v3"): "eval-rerun-a4ccf890-b627-483e-805d-b64385820cf5_eval-rerun-react.pdf.json",
    ("B", "arxiv-2201.11903v6"): "eval-rerun-ed9e3cc6-7645-4fe7-9014-8f5db79d1be1_eval-rerun-cot.pdf.json",
}


def _quote_lines(text: str) -> list[str]:
    return [ln.split("QUOTE:", 1)[1].strip() for ln in text.splitlines() if ln.lstrip().startswith("QUOTE:")]


def _load_group(suffix: str) -> list[dict]:
    entries = []
    for path in sorted(p for p in AUDIT_LOG_DIR.iterdir() if p.name.endswith("_" + suffix)):
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    return entries


def _assign_logs(all_claims: list[dict], entries: list[dict]) -> dict[int, tuple[dict, str]]:
    """One-to-one claim-index -> log assignment over ALL claims of the paper
    (not only the golden-matched ones), so a log that restates two similar
    claims is resolved by the other claim's better fit.

    Score = exact QUOTE-line equality with the fixture's evidence spans when
    present (run A), plus how well the claim text is located in the opening
    of the audit prose (the auditor restates the claim first), via RapidFuzz.
    Greedy by descending score; ties are not broken arbitrarily - a pair is
    only accepted if its score is strictly greater than every competing
    unassigned score for that claim."""
    pairs = []
    for c in all_claims:
        key = tuple(s["source_text"] for s in c.get("evidence_spans") or [])
        for i, e in enumerate(entries):
            exact = bool(key) and tuple(_quote_lines(e["response_raw"])) == key
            head = fuzz.partial_ratio(c["claim_text_verbatim"], e["response_raw"][:700])
            pairs.append((100.0 * exact + head, c["index"], i, "quotes+head" if exact else f"head {head:.0f}"))
    pairs.sort(reverse=True)
    out: dict[int, tuple[dict, str]] = {}
    used: set[int] = set()
    for score, ci, li, how in pairs:
        if ci in out or li in used:
            continue
        rivals = [p[0] for p in pairs if p[1] == ci and p[2] != li and p[2] not in used]
        if rivals and rivals[0] >= score:
            continue  # tied with another candidate for this claim: leave unassigned
        out[ci] = (entries[li], how)
        used.add(li)
    return out


def check_a() -> tuple[int, int, list[str]]:
    ok = total = 0
    lines: list[str] = []
    for set_id in ("A", "B"):
        sel = golden_selection(set_id)
        for paper_id, paper in sel.items():
            entries = _load_group(LOG_GROUPS[(set_id, paper_id)])
            assigned = _assign_logs(paper["all_claims"], entries)
            for claim in paper["claims"]:
                total += 1
                if claim["index"] not in assigned:
                    lines.append(f"  {set_id} {paper_id} idx={claim['index']}: no unambiguous log match (label {claim['label']})")
                    continue
                hit, how = assigned[claim["index"]]
                v = parse_verdict(hit["response_raw"])
                if v == claim["label"]:
                    ok += 1
                else:
                    lines.append(f"  {set_id} {paper_id} idx={claim['index']}: regex={v} fixture={claim['label']} (match: {how})")
            lines.append(f"  [{set_id} {paper_id}] logs={len(entries)} prompt_versions={sorted({e['prompt_version'] for e in entries})}")
    return ok, total, lines


def check_b() -> list[str]:
    out = []
    for set_id, cfg in SETS.items():
        mm = json.loads(cfg["match_map"].read_text(encoding="utf-8"))["rows"]
        fx = json.loads((cfg["fixtures"] / "arxiv-2303.11366v4.json").read_text(encoding="utf-8"))
        fp_to_idx: dict[str, list[int]] = {}
        for c in fx["claims"]:
            fp_to_idx.setdefault(fingerprint_claim_text(c["claim_text_verbatim"]), []).append(c["index"])
        res = {}
        for row in ("REFLEX-M02", "REFLEX-M09"):
            fp = mm[row]["claim_fingerprint"]
            res[row] = (fp, fp_to_idx.get(fp))
        same = res["REFLEX-M02"][0] is not None and res["REFLEX-M02"][0] == res["REFLEX-M09"][0]
        out.append(f"  set {set_id} (hash {cfg['hash']}): same_fingerprint={same}")
        for row, (fp, idx) in res.items():
            out.append(f"    {row}: fingerprint={fp} -> claim index {idx}")
    return out


def main() -> int:
    ok, total, lines = check_a()
    print(f"CHECK (a): regex VERDICT vs fixture label: {ok}/{total}")
    print("\n".join(lines))
    print("CHECK (b): REFLEX-M02 vs REFLEX-M09")
    print("\n".join(check_b()))
    return 0 if ok >= 42 else 1


if __name__ == "__main__":
    sys.exit(main())
