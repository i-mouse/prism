"""Shared helpers for the Experiment 1 replay and checks (offline).

Golden papers only. Paths are explicit; nothing held-out is referenced.
"""
import json
import re
from pathlib import Path

from eval.match_map import fingerprint_claim_text
from eval.matrix_loader import load_matrix

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SERVICE_DIR.parent
EVALS = REPO_DIR / "docs" / "evals"
MATRIX_PATH = EVALS / "matrix_eval.json"
AUDIT_LOG_DIR = SERVICE_DIR / "logs" / "audit"
OUT_DIR = SERVICE_DIR / "scratch" / "exp1_replay" / "out"

ARCHIVE = EVALS / "archive" / "2026-10-07_pre-cb3272cce551"
SETS = {
    "A": {"hash": "cb3272cce551", "fixtures": EVALS / "fixtures", "match_map": EVALS / "match_map.json"},
    "B": {"hash": "0bcf9d44e619", "fixtures": ARCHIVE / "fixtures", "match_map": ARCHIVE / "match_map.json"},
}

_VERDICT_RE = re.compile(r"^\W*VERDICT:\s*\W*(not_supported|partially_supported|supported)\b", re.IGNORECASE | re.MULTILINE)


def parse_verdict(text: str) -> str | None:
    """Last VERDICT: line in a free-text audit, or None ("unparsed")."""
    matches = _VERDICT_RE.findall(text or "")
    return matches[-1].lower() if matches else None


def golden_selection(set_id: str) -> dict[str, dict]:
    """paper_id -> {"claims": [fixture claims that are golden-matched],
    "rows": {claim_index: [golden row ids]}} for set A or B.

    Selection = match-map fingerprint hits (same method as the B5.1 replay),
    unioned with the fixture's frozen matches."""
    cfg = SETS[set_id]
    spec = load_matrix(MATRIX_PATH)
    match_map = json.loads(cfg["match_map"].read_text(encoding="utf-8"))["rows"]
    out: dict[str, dict] = {}
    for paper in spec.papers:
        fixture = json.loads((cfg["fixtures"] / f"{paper.paper_id}.json").read_text(encoding="utf-8"))
        fp_to_idx: dict[str, list[int]] = {}
        for c in fixture["claims"]:
            fp_to_idx.setdefault(fingerprint_claim_text(c["claim_text_verbatim"]), []).append(c["index"])
        rows: dict[int, list[str]] = {}
        for row in paper.expected_rows:
            fp = match_map.get(row.id, {}).get("claim_fingerprint")
            for idx in fp_to_idx.get(fp, []) if fp else []:
                rows.setdefault(idx, []).append(row.id)
        for m in fixture["matches"]:
            if m["actual_index"] is not None:
                rows.setdefault(m["actual_index"], [])
        claims = [c for c in fixture["claims"] if c["index"] in rows]
        for c in claims:
            c["fingerprint"] = fingerprint_claim_text(c["claim_text_verbatim"])
        out[paper.paper_id] = {"claims": claims, "rows": rows, "all_claims": fixture["claims"], "filename": paper.filename, "header": fixture["header"]}
    return out
