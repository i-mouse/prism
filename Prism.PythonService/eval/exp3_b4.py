"""CLI: Experiment 3 B4 - scoring + blind labelling packs.

Computes the deterministic marks (c2/c3/c4/c7 + diagnostics) with zero LLM
calls, builds two blind, opaque-id packs for hand adjudication (c1 target-row
matching, c8 claim-quality sample), and - once a human has filled and locked
the answer files - scores c1/c5/c6/c8 and every REPORT-only item defined in
docs/decisions.md's "Experiment 3 pre-registration - 2026-10-15" and its
amendments. eval/score_exp3.py is never imported or edited: that scorer
needs a `pass1_only` fixture directory this experiment never created (see
the pre-registration's own "Scorer/B4 mismatch" note), so this module
implements the pre-registered c1-c8 definitions directly.

No LLM calls, no network, no DB. main.py is never imported (it has real
import-time side effects - telemetry init, Psycopg instrumentation); PDF
text extraction is reimplemented locally from the same PyMuPDF loop. Only
the 12 dev papers named in DEV_PAPER_PDFS below are ever opened, each
behind a pinned sha256 check - no held-out or sealed path is read, directly
or indirectly.

Usage:
  uv run python -m eval.exp3_b4 deterministic
  uv run python -m eval.exp3_b4 build-c1
  uv run python -m eval.exp3_b4 build-c8
  uv run python -m eval.exp3_b4 lock
  uv run python -m eval.exp3_b4 score
"""
import argparse
import copy
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import fitz
from pydantic import ValidationError
from rapidfuzz import fuzz

from eval.blind_review import (
    C1Answer,
    C8Answer,
    assign_opaque_ids,
    dedup_by_normalized_text,
    provenance,
    seeded_sample,
    sha256_file,
    verify_lock,
    wilson_interval,
    write_lock,
)
from eval.match_map import fingerprint_claim_text, load_match_map
from eval.matrix_loader import load_matrix
from eval.score_replay import resolve_adjudicated_rows
from extraction.grounding import RAPIDFUZZ_THRESHOLD, normalize_for_match, normalize_with_map

REPO_ROOT = Path(__file__).parent.parent.parent
DOCS = REPO_ROOT / "docs"
DEFAULT_DEV_EVAL_PATH = DOCS / "evals" / "dev_eval.json"
DEFAULT_MATCH_MAP_PATH = DOCS / "evals" / "dev_match_map.json"
DEFAULT_RUN1_FIXTURE_DIR = DOCS / "evals" / "fixtures" / "dev" / "run1"
DEFAULT_REPLAY_ROOT = DOCS / "evals" / "fixtures" / "dev" / "exp3"
DEFAULT_TARGETS_PATH = DOCS / "evals" / "exp3_targets.json"
DEFAULT_RESEARCH_PAPERS_DIR = DOCS / "research_papers"
DEFAULT_OUTPUT_DIR = DOCS / "evals" / "exp3_b4"

TARGETS_SHA256 = "69c60127cdf1d7130311b11b615e1e4490cf85ca637418d1c73ca6a3c18917b3"

# Only these 12 dev papers are ever opened. filename is under
# DEFAULT_RESEARCH_PAPERS_DIR; sha256 is pinned and checked before every
# read - never the held-out/golden replay_stage1.py path table, which may
# reference sealed PDFs this script must never touch.
DEV_PAPER_PDFS: dict[str, tuple[str, str]] = {
    "arxiv-2610.10590v1": ("2610.10590v1.pdf", "57c54f3e0f7ff2b60e0c427d1f12c533c270a368d1ffbb74561796c98be28e1c"),
    "arxiv-2610.10871v1": ("2610.10871v1.pdf", "cf251ab4f08d31b555af41214038c8da181c50cbd7f33c74c3cb495a71d455c5"),
    "arxiv-2610.11132v1": ("2610.11132v1.pdf", "b946a45229a50663fd17c9fea249510ebc5919f710a63ff7ab78806129b8a928"),
    "arxiv-2610.11135v1": ("2610.11135v1.pdf", "daafc8cbc5025756edce1b5886fc673f50f04432490fa8973117b0121d670889"),
    "arxiv-2610.11291v1": ("2610.11291v1.pdf", "4c7d5b6e8b1aeb2928e6f7e564d0b665c2d32d2a2897578645d2c89d2ae28c68"),
    "arxiv-2610.11312v1": ("2610.11312v1.pdf", "af4898a093b1eaf518a0e4b54841af9ae3231d04ec7d2fb917921862f90f9edb"),
    "arxiv-2610.11519v1": ("2610.11519v1.pdf", "ef065805c7f55bc0f62bf855877d50a475ae2f4167b9aca7e719e4e43404ea80"),
    "arxiv-2610.12114v1": ("2610.12114v1.pdf", "d5df24079afcfb2e0d13fbeaa0832371873d0eca042aea8731af070aa6fb8e49"),
    "arxiv-2610.12124v1": ("2610.12124v1.pdf", "af67d571046eed321621b072fa81b0bd04cd9cb13954db450040eee32b3d4f9b"),
    "arxiv-2610.12168v1": ("2610.12168v1.pdf", "0daa369e5876153748c0804025cf93429df6d69fcc698b9edf3f839f75a66bb8"),
    "arxiv-2610.12176v1": ("2610.12176v1.pdf", "9018fa312c4dac659426fab2b304357593f5f4ad7886d73589f34dd06012f282"),
    "arxiv-2610.12375v1": ("2610.12375v1.pdf", "be7545815b5ea7f6845361a37b618de7dfd68ed677ba570e69cea224bcea5b23"),
}
DEV_PAPERS = sorted(DEV_PAPER_PDFS)

PASS2_RUNS = ["pass2_r1", "pass2_r2"]
C4_COST_PER_PAPER_FACTOR = 87
C4_MAX_INR = 130

SEED_C1 = 20261015
SEED_C8_SAMPLE = 20261015
SEED_C8_CONTROL = 20261016
SEED_C8_REPEAT = 20261017
SHORTLIST_TOP_N = 10
C8_SAMPLE_K = 30
C8_CONTROL_K = 30
C8_REPEAT_K = 5
C8_REPEAT_MIN_GAP = 20
CONTEXT_WINDOW_CHARS = 300


class PdfPasswordProtectedError(Exception):
    pass


# --------------------------------------------------------------------------
# Frozen-input loaders
# --------------------------------------------------------------------------

def _verify_hash(path: Path, expected_sha256: str) -> None:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"{path}: sha256 mismatch - expected {expected_sha256}, got {actual}")


def _load_targets(targets_path: Path) -> dict[str, str]:
    _verify_hash(targets_path, TARGETS_SHA256)
    data = json.loads(targets_path.read_text(encoding="utf-8"))
    return data["row_id_to_shape"]


def _target_rows(dev_eval_path: Path, targets_path: Path) -> list[dict]:
    """[{row_id, paper_id, claim_text_verbatim, shape}], one per target row."""
    row_id_to_shape = _load_targets(targets_path)
    matrix = load_matrix(dev_eval_path)
    rows = []
    for paper in matrix.papers:
        for row in paper.expected_rows:
            if row.id in row_id_to_shape:
                rows.append(
                    {
                        "row_id": row.id,
                        "paper_id": paper.paper_id,
                        "claim_text_verbatim": row.claim_text_verbatim,
                        "shape": row_id_to_shape[row.id],
                    }
                )
    missing = set(row_id_to_shape) - {r["row_id"] for r in rows}
    if missing:
        raise ValueError(f"target rows not found in dev_eval.json: {sorted(missing)}")
    return rows


def _resolve_pdf(paper_id: str) -> Path:
    if paper_id not in DEV_PAPER_PDFS:
        raise ValueError(f"{paper_id}: not a listed dev paper - refusing to load an unlisted PDF")
    filename, expected_sha256 = DEV_PAPER_PDFS[paper_id]
    path = DEFAULT_RESEARCH_PAPERS_DIR / filename
    _verify_hash(path, expected_sha256)
    return path


def _extract_pdf_text(path: Path) -> str:
    """Mirrors main.py's extract_pdf_text_sync (main.py:102-115) exactly,
    without importing main.py (which has import-time telemetry/DB side
    effects - see docstring)."""
    final_text = ""
    with fitz.open(path) as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise PdfPasswordProtectedError(f"{path}: password-protected PDF")
        for page in doc:
            final_text += page.get_text()
    return final_text


def _merged_path(replay_root: Path, run: str, paper_id: str) -> Path:
    return replay_root / run / f"{paper_id}_merged.json"


def _load_merged_claims(replay_root: Path, run: str, paper_id: str) -> list[dict]:
    return json.loads(_merged_path(replay_root, run, paper_id).read_text(encoding="utf-8"))["claims"]


def _load_pass1_claims(replay_root: Path, run: str, paper_id: str) -> list[dict]:
    path = replay_root / run / f"{paper_id}_pass1.json"
    return json.loads(path.read_text(encoding="utf-8"))["claims"]


def _load_pass2_sentences(replay_root: Path, run: str, paper_id: str) -> list[str]:
    path = replay_root / run / f"{paper_id}_pass2.json"
    return json.loads(path.read_text(encoding="utf-8"))["sentences"]


def _load_buckets(replay_root: Path, run: str, paper_id: str) -> dict:
    path = replay_root / run / f"{paper_id}_buckets.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_summary(replay_root: Path, run: str) -> dict:
    path = replay_root / run / "_summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _input_files_for_run(replay_root: Path, run: str) -> list[Path]:
    files = [replay_root / run / "_summary.json"]
    for paper_id in DEV_PAPERS:
        files.append(_merged_path(replay_root, run, paper_id))
        files.append(replay_root / run / f"{paper_id}_pass1.json")
        files.append(replay_root / run / f"{paper_id}_pass2.json")
        files.append(replay_root / run / f"{paper_id}_buckets.json")
    return files


# --------------------------------------------------------------------------
# deterministic
# --------------------------------------------------------------------------

def _c2(dev_eval_path: Path, match_map_path: Path, run1_fixture_dir: Path, replay_root: Path) -> dict:
    matrix = load_matrix(dev_eval_path)
    golden_ids = {row.id for paper in matrix.papers for row in paper.expected_rows}
    match_map = load_match_map(match_map_path, golden_ids)
    rows = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir)
    matched_ids = {row.row_id for row in rows if row.claim_index is not None}

    scoped_fingerprints = {
        row_id: match_map.rows[row_id].claim_fingerprint
        for row_id in matched_ids
        if match_map.rows[row_id].claim_fingerprint is not None
    }
    scope = len(scoped_fingerprints)

    result = {}
    for run in PASS2_RUNS:
        merged_fingerprints = {
            fingerprint_claim_text(c["claim_text_verbatim"])
            for paper_id in DEV_PAPERS
            for c in _load_merged_claims(replay_root, run, paper_id)
        }
        retained = sum(1 for fp in scoped_fingerprints.values() if fp in merged_fingerprints)
        result[run] = {"retained": retained, "scope": scope, "ratio": (retained / scope) if scope else None}
    return result


def _c3_and_c4(replay_root: Path) -> dict:
    per_run = {}
    for run in PASS2_RUNS:
        per_paper_ratio = []
        total_merged = 0
        total_pass1 = 0
        summary = _load_summary(replay_root, run)
        for rec in summary.get("records", []):
            if rec.get("call_kind") != "pass2":
                raise ValueError(
                    f"{run}: _summary.json has a non-pass-2 record (paper_id={rec.get('paper_id')!r}, "
                    f"call_kind={rec.get('call_kind')!r}) - p2 cannot be computed as cost_inr / 12 "
                    "without accounting for it"
                )
        p2 = summary.get("cost_inr", 0.0) / len(DEV_PAPERS)

        for paper_id in DEV_PAPERS:
            merged_n = len(_load_merged_claims(replay_root, run, paper_id))
            pass1_n = len(_load_pass1_claims(replay_root, run, paper_id))
            total_merged += merged_n
            total_pass1 += pass1_n
            if pass1_n:
                per_paper_ratio.append(merged_n / pass1_n)

        r_mean = sum(per_paper_ratio) / len(per_paper_ratio) if per_paper_ratio else None
        r_pooled = (total_merged / total_pass1) if total_pass1 else None
        per_run[run] = {"r_mean": r_mean, "r_pooled": r_pooled, "p2": p2}

    def _c4_for_reading(key: str) -> dict:
        values = [per_run[run][key] for run in PASS2_RUNS]
        p2_values = [per_run[run]["p2"] for run in PASS2_RUNS]
        r = sum(values) / len(values)
        p2 = sum(p2_values) / len(p2_values)
        projected = C4_COST_PER_PAPER_FACTOR * r + p2
        return {"r": r, "p2": p2, "projected_inr": projected, "pass": projected <= C4_MAX_INR}

    return {
        "c3_per_run": per_run,
        "c4_mean_reading": _c4_for_reading("r_mean"),
        "c4_pooled_reading": _c4_for_reading("r_pooled"),
    }


def _c7(replay_root: Path) -> dict:
    per_run = {}
    for run in PASS2_RUNS:
        total_sentences = 0
        total_ungrounded = 0
        mismatches = []
        for paper_id in DEV_PAPERS:
            sentences_n = len(_load_pass2_sentences(replay_root, run, paper_id))
            buckets = _load_buckets(replay_root, run, paper_id)
            bucket_n = (
                buckets["dropped_ungrounded"]
                + len(buckets["dropped_duplicate"])
                + len(buckets["kept_but_contained"])
                + len(buckets["kept_new"])
            )
            if sentences_n != bucket_n:
                mismatches.append({"paper_id": paper_id, "pass2_sentences": sentences_n, "bucket_total": bucket_n})
                continue
            total_sentences += sentences_n
            total_ungrounded += buckets["dropped_ungrounded"]

        if mismatches:
            raise SystemExit(
                f"c7 abort: {run} has {len(mismatches)} paper(s) where pass2.sentences count "
                f"disagrees with buckets.json's bucket-count sum: {mismatches}"
            )

        rate = (total_sentences - total_ungrounded) / total_sentences if total_sentences else None
        per_run[run] = {
            "sentences": total_sentences,
            "dropped_ungrounded": total_ungrounded,
            "rate": rate,
            "pass": (rate is not None and rate >= 0.95),
        }
    return per_run


def _diagnostics(replay_root: Path) -> dict:
    per_run = {}
    for run in PASS2_RUNS:
        summary = _load_summary(replay_root, run)
        incomplete_papers = []
        for paper_id in DEV_PAPERS:
            header = json.loads(_merged_path(replay_root, run, paper_id).read_text(encoding="utf-8"))["header"]
            if header.get("incomplete"):
                incomplete_papers.append(paper_id)
        per_run[run] = {
            "fallback_calls": summary.get("fallback_calls", 0),
            "incomplete_papers": incomplete_papers,
            "not_supported_count": "N/A - pass-2 claims not audited",
        }
    return per_run


def cmd_deterministic(args: argparse.Namespace) -> None:
    replay_root = args.replay_root
    c2 = _c2(args.dev_eval_path, args.match_map_path, args.run1_fixture_dir, replay_root)
    c3_c4 = _c3_and_c4(replay_root)
    c7 = _c7(replay_root)
    diagnostics = _diagnostics(replay_root)
    target_rows = _target_rows(args.dev_eval_path, args.targets_path)
    outlier_count = sum(1 for row in target_rows if row["paper_id"] == "arxiv-2610.12168v1")

    input_files = [args.targets_path, args.dev_eval_path, args.match_map_path]
    for run in PASS2_RUNS:
        input_files.extend(_input_files_for_run(replay_root, run))

    result = {
        "provenance": provenance(input_files),
        "c2_report_only": c2,
        "c3_c4": c3_c4,
        "c7": c7,
        "diagnostics": diagnostics,
        "arxiv_2610_12168v1_target_row_count": outlier_count,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / "deterministic.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"wrote {out_path}")
    print(f"c4 (mean-r reading): {c3_c4['c4_mean_reading']}")
    print(f"c4 (pooled-r reading): {c3_c4['c4_pooled_reading']}")
    print(f"c7: {c7}")
    print(f"c2 (report-only): {c2}")
    print(f"diagnostics: {diagnostics}")
    print(f"arxiv-2610.12168v1 target rows: {outlier_count}")


# --------------------------------------------------------------------------
# build-c1
# --------------------------------------------------------------------------

def cmd_build_c1(args: argparse.Namespace) -> None:
    replay_root = args.replay_root
    rows = _target_rows(args.dev_eval_path, args.targets_path)
    papers_with_targets = sorted({row["paper_id"] for row in rows})

    input_files = [args.targets_path, args.dev_eval_path]

    # raw_claims[paper_id]: every merged claim from both runs, tagged with
    # its own run/index/pass - needed later to build c1_key.json's per-run
    # presence lookup, even after dedup picks one representative text.
    raw_claims: dict[str, list[dict]] = {}
    for paper_id in papers_with_targets:
        entries = []
        for run in PASS2_RUNS:
            path = _merged_path(replay_root, run, paper_id)
            input_files.append(path)
            for idx, c in enumerate(_load_merged_claims(replay_root, run, paper_id)):
                entries.append({"run": run, "index": idx, "pass": c["pass"], "text": c["claim_text_verbatim"]})
        raw_claims[paper_id] = entries

    by_norm_text: dict[str, dict[str, list[dict]]] = {}
    for paper_id, entries in raw_claims.items():
        grouped: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            grouped[normalize_for_match(e["text"])].append(e)
        by_norm_text[paper_id] = grouped

    pool_candidates = []  # [{"paper_id", "claim_text_verbatim"}], global, pre-id
    for paper_id in papers_with_targets:
        deduped = dedup_by_normalized_text(raw_claims[paper_id], text_of=lambda e: e["text"])
        for e in deduped:
            pool_candidates.append({"paper_id": paper_id, "claim_text_verbatim": e["text"]})

    id_pairs = assign_opaque_ids(pool_candidates, prefix="C", seed=SEED_C1)
    id_to_candidate = {cid: cand for cid, cand in id_pairs}
    paper_to_ids: dict[str, list[str]] = defaultdict(list)
    for cid, cand in id_pairs:
        paper_to_ids[cand["paper_id"]].append(cid)

    # c1_key.json: per-candidate, per-run presence/pass/merged_index.
    c1_key: dict[str, dict] = {}
    for cid, cand in id_pairs:
        paper_id = cand["paper_id"]
        norm_text = normalize_for_match(cand["claim_text_verbatim"])
        entry: dict = {"paper_id": paper_id}
        for run in PASS2_RUNS:
            occurrences = [e for e in by_norm_text[paper_id].get(norm_text, []) if e["run"] == run]
            if occurrences:
                occ = occurrences[0]
                entry[run] = {"present": True, "pass": 1 if occ["pass"] == "pass1" else 2, "merged_index": occ["index"]}
            else:
                entry[run] = {"present": False, "pass": None, "merged_index": None}
        c1_key[cid] = entry

    # shortlist per row: top-10 token_sort_ratio UNION top-10 partial_ratio,
    # scored on normalize_for_match text, shuffled per row.
    pack_rows = []
    for row in rows:
        candidates = [(cid, id_to_candidate[cid]["claim_text_verbatim"]) for cid in paper_to_ids[row["paper_id"]]]
        golden_norm = normalize_for_match(row["claim_text_verbatim"])
        by_tsr = sorted(candidates, key=lambda pair: -fuzz.token_sort_ratio(golden_norm, normalize_for_match(pair[1])))
        by_pr = sorted(candidates, key=lambda pair: -fuzz.partial_ratio(golden_norm, normalize_for_match(pair[1])))
        shortlist_ids = {cid for cid, _ in by_tsr[:SHORTLIST_TOP_N]} | {cid for cid, _ in by_pr[:SHORTLIST_TOP_N]}
        shortlist = [(cid, text) for cid, text in candidates if cid in shortlist_ids]
        random.Random(f"{SEED_C1}-{row['row_id']}-shortlist").shuffle(shortlist)
        pack_rows.append({"row": row, "shortlist": shortlist})

    # markdown pack
    lines = [
        "# Experiment 3 B4 - C1 blind target-row matching pack",
        "",
        "Do not open c1_key.json before scoring.",
        "",
        "## Rules (from docs/decisions.md, 2026-10-12 run-1 rules)",
        "",
        '- "Same claim, other sentence" = match.',
        '- A "safe half only" sibling claim = no match.',
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

    for paper_id in papers_with_targets:
        lines.append(f"## Appendix - {paper_id} - full candidate pool")
        appendix_ids = list(paper_to_ids[paper_id])
        random.Random(f"{SEED_C1}-{paper_id}-appendix").shuffle(appendix_ids)
        for cid in appendix_ids:
            lines.append(f"- **{cid}**: {id_to_candidate[cid]['claim_text_verbatim']}")
        lines.append("")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pack_path = args.output_dir / "c1_review_pack.md"
    pack_path.write_text("\n".join(lines), encoding="utf-8")

    adjudication_path = args.output_dir / "c1_adjudication.csv"
    with open(adjudication_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["row_id", "paper_id", "row_text", "match_ids", "note"])
        for row in rows:
            writer.writerow([row["row_id"], row["paper_id"], row["claim_text_verbatim"], "", ""])

    key_path = args.output_dir / "c1_key.json"
    key_path.write_text(json.dumps({"provenance": provenance(input_files), "candidates": c1_key}, indent=2), encoding="utf-8")

    pool_sizes = {paper_id: len(paper_to_ids[paper_id]) for paper_id in papers_with_targets}
    shortlist_sizes = {entry["row"]["row_id"]: len(entry["shortlist"]) for entry in pack_rows}
    print(f"wrote {pack_path} sha256={sha256_file(pack_path)}")
    print(f"wrote {adjudication_path} sha256={sha256_file(adjudication_path)}")
    print(f"wrote {key_path} sha256={sha256_file(key_path)}")
    print(f"pool size per paper: {pool_sizes}")
    print(f"shortlist size per row: {shortlist_sizes}")


# --------------------------------------------------------------------------
# build-c8
# --------------------------------------------------------------------------

def _locate_context(claim_text: str, paper_text: str) -> str:
    """Locates claim_text in paper_text the same way grounding does (raw
    alignment first, normalized alignment as fallback), then returns a
    ~CONTEXT_WINDOW_CHARS window centered on the match. "" if not locatable."""
    alignment = fuzz.partial_ratio_alignment(claim_text, paper_text)
    span: Optional[tuple[int, int]] = None
    if alignment.score >= RAPIDFUZZ_THRESHOLD and alignment.dest_end > alignment.dest_start:
        span = (alignment.dest_start, alignment.dest_end)
    else:
        norm_paper, idx_map = normalize_with_map(paper_text)
        if norm_paper == normalize_for_match(paper_text):
            norm_alignment = fuzz.partial_ratio_alignment(normalize_for_match(claim_text), norm_paper)
            if norm_alignment.score >= RAPIDFUZZ_THRESHOLD and norm_alignment.dest_end > norm_alignment.dest_start:
                span = (idx_map[norm_alignment.dest_start], idx_map[norm_alignment.dest_end - 1] + 1)
    if span is None:
        return ""
    start, end = span
    mid = (start + end) // 2
    half = CONTEXT_WINDOW_CHARS // 2
    ctx_start = max(0, mid - half)
    ctx_end = min(len(paper_text), ctx_start + CONTEXT_WINDOW_CHARS)
    return paper_text[ctx_start:ctx_end]


def _similar_claims(claim_text: str, pool: list[str], n: int = 3) -> list[str]:
    norm_claim = normalize_for_match(claim_text)
    scored = []
    for other in pool:
        norm_other = normalize_for_match(other)
        if norm_other == norm_claim:
            continue
        scored.append((fuzz.token_sort_ratio(norm_claim, norm_other), other))
    scored.sort(key=lambda pair: -pair[0])
    return [text for _, text in scored[:n]]


def _insert_repeats(items: list[dict], k: int, seed, min_gap: int) -> list[dict]:
    n = len(items)
    eligible = [i for i in range(n) if n - i >= min_gap]
    chosen = sorted(seeded_sample(eligible, min(k, len(eligible)), seed))
    result = list(items)
    for idx in chosen:
        dup = copy.deepcopy(items[idx])
        dup["repeat_of_index"] = idx
        result.append(dup)
    return result


def cmd_build_c8(args: argparse.Namespace) -> None:
    replay_root = args.replay_root
    input_files: list[Path] = []

    # per-paper kept_new sentences in deterministic (paper, position) order,
    # per run - this is the pre-registered c8 sampling frame.
    kept_new_by_run: dict[str, list[dict]] = {}
    paper_pool_by_run: dict[str, dict[str, list[str]]] = {}
    for run in PASS2_RUNS:
        items = []
        pools: dict[str, list[str]] = {}
        for paper_id in DEV_PAPERS:
            path = replay_root / run / f"{paper_id}_buckets.json"
            input_files.append(path)
            buckets = _load_buckets(replay_root, run, paper_id)
            sentences = [entry["sentence"] for entry in buckets["kept_new"]]
            pools[paper_id] = sentences
            for position, sentence in enumerate(sentences):
                items.append({"paper_id": paper_id, "claim_text": sentence, "position": position, "run": run})
        kept_new_by_run[run] = items
        paper_pool_by_run[run] = pools

    samples_by_run = {
        run: seeded_sample(kept_new_by_run[run], C8_SAMPLE_K, SEED_C8_SAMPLE) for run in PASS2_RUNS
    }

    # merge samples across runs, tagging group membership; dedup by
    # normalized text for labelling only (the drawn-indices record above
    # keeps each run's own sample intact for scoring).
    merged: dict[str, dict] = {}
    for run in PASS2_RUNS:
        for item in samples_by_run[run]:
            norm = normalize_for_match(item["claim_text"])
            if norm not in merged:
                merged[norm] = {**item, "groups": {run}}
            else:
                merged[norm]["groups"].add(run)
    pass2_items = list(merged.values())

    # pass-1 controls: frozen, identical across runs - read from pass2_r1.
    pass1_items = []
    for paper_id in DEV_PAPERS:
        path = replay_root / "pass2_r1" / f"{paper_id}_pass1.json"
        input_files.append(path)
        for position, c in enumerate(_load_pass1_claims(replay_root, "pass2_r1", paper_id)):
            pass1_items.append({"paper_id": paper_id, "claim_text": c["claim_text_verbatim"], "position": position})

    pass2_norm_texts = {normalize_for_match(item["claim_text"]) for item in pass2_items}
    pass1_eligible = [item for item in pass1_items if normalize_for_match(item["claim_text"]) not in pass2_norm_texts]
    control_items = seeded_sample(pass1_eligible, C8_CONTROL_K, SEED_C8_CONTROL)
    for item in control_items:
        item["groups"] = {"pass1_control"}

    all_items = dedup_by_normalized_text(pass2_items + control_items, text_of=lambda i: i["claim_text"])

    shuffled = list(all_items)
    random.Random(SEED_C8_SAMPLE).shuffle(shuffled)
    with_repeats = _insert_repeats(shuffled, C8_REPEAT_K, SEED_C8_REPEAT, C8_REPEAT_MIN_GAP)

    ids = [f"K{i + 1:03d}" for i in range(len(with_repeats))]

    sheet_rows = []
    c8_key: dict[str, dict] = {}
    for kid, item in zip(ids, with_repeats):
        paper_id = item["paper_id"]
        pdf_path = _resolve_pdf(paper_id)
        paper_text = _extract_pdf_text(pdf_path)
        pool = paper_pool_by_run["pass2_r1"].get(paper_id, []) + paper_pool_by_run["pass2_r2"].get(paper_id, [])
        similar = _similar_claims(item["claim_text"], pool, 3)
        similar = similar + [""] * (3 - len(similar))
        context = _locate_context(item["claim_text"], paper_text)

        sheet_rows.append(
            {
                "id": kid,
                "paper_id": paper_id,
                "claim_text": item["claim_text"],
                "context": context,
                "similar_1": similar[0],
                "similar_2": similar[1],
                "similar_3": similar[2],
            }
        )

        groups = item.get("groups", set())
        if groups == {"pass2_r1"}:
            group_label = "pass2_r1"
        elif groups == {"pass2_r2"}:
            group_label = "pass2_r2"
        elif groups == {"pass1_control"}:
            group_label = "pass1_control"
        else:
            group_label = "pass2_both"

        repeat_of_index = item.get("repeat_of_index")
        c8_key[kid] = {
            "group": group_label,
            "run_memberships": sorted(groups & {"pass2_r1", "pass2_r2"}),
            "position": item.get("position"),
            "repeat_of": ids[repeat_of_index] if repeat_of_index is not None else None,
        }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = args.output_dir / "c8_sheet.csv"
    with open(sheet_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(
            ["id", "paper_id", "claim_text", "context", "similar_1", "similar_2", "similar_3", "label", "reason", "duplicate", "note"]
        )
        for row in sheet_rows:
            writer.writerow(
                [
                    row["id"], row["paper_id"], row["claim_text"], row["context"],
                    row["similar_1"], row["similar_2"], row["similar_3"], "", "", "", "",
                ]
            )

    readme_path = args.output_dir / "c8_README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Experiment 3 B4 - C8 claim-quality sheet",
                "",
                "Columns:",
                "- `id`: opaque row id.",
                "- `paper_id`: which dev paper this row's sentence came from.",
                "- `claim_text`: the pass-2 (or pass-1 control) sentence to label.",
                "- `context`: ~300 chars of surrounding paper text, located the same way grounding does.",
                "- `similar_1..3`: the 3 most similar other claims from the same paper's pool (text only).",
                "- `label`: claim | not_claim | unsure.",
                "- `reason` (only when label is not_claim or unsure): method_setup | background_related_work | number_no_assertion | other.",
                "- `duplicate` (only when label is claim): yes | no - yes means same claim as one of similar_1..3.",
                "- `note`: free text.",
                "",
                "Label against the claim definition recorded in the B4 method entry in docs/decisions.md.",
                "`unsure` counts as `not_claim` for c8.",
            ]
        ),
        encoding="utf-8",
    )

    key_path = args.output_dir / "c8_key.json"
    key_path.write_text(json.dumps({"provenance": provenance(input_files), "items": c8_key}, indent=2), encoding="utf-8")

    group_counts = Counter(v["group"] for v in c8_key.values())
    print(f"wrote {sheet_path} sha256={sha256_file(sheet_path)}")
    print(f"wrote {readme_path} sha256={sha256_file(readme_path)}")
    print(f"wrote {key_path} sha256={sha256_file(key_path)}")
    print(f"c8 item counts per group: {dict(group_counts)}")
    print(f"total rows on sheet: {len(sheet_rows)}")


# --------------------------------------------------------------------------
# lock
# --------------------------------------------------------------------------

def _read_csv_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cmd_lock(args: argparse.Namespace) -> None:
    output_dir = args.output_dir
    c1_csv = output_dir / "c1_adjudication.csv"
    c8_csv = output_dir / "c8_sheet.csv"
    c1_key = json.loads((output_dir / "c1_key.json").read_text(encoding="utf-8"))["candidates"]
    c8_key = json.loads((output_dir / "c8_key.json").read_text(encoding="utf-8"))["items"]

    errors = []

    for raw_row in _read_csv_rows(c1_csv):
        row_id = raw_row.get("row_id", "?")
        try:
            answer = C1Answer.model_validate(raw_row)
        except ValidationError as exc:
            errors.append(f"c1 {row_id}: {exc}")
            continue
        for match_id in answer.match_ids:
            info = c1_key.get(match_id)
            if info is None:
                errors.append(f"c1 {row_id}: unknown candidate id {match_id!r}")
            elif info["paper_id"] != answer.paper_id:
                errors.append(f"c1 {row_id}: {match_id!r} belongs to paper {info['paper_id']!r}, not {answer.paper_id!r}")

    for raw_row in _read_csv_rows(c8_csv):
        kid = raw_row.get("id", "?")
        if kid not in c8_key:
            errors.append(f"c8 {kid}: unknown id")
            continue
        try:
            C8Answer.model_validate(raw_row)
        except ValidationError as exc:
            errors.append(f"c8 {kid}: {exc}")

    if errors:
        print("lock FAILED:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)

    write_lock({"c1_adjudication.csv": c1_csv, "c8_sheet.csv": c8_csv}, output_dir / "lock.json")
    print(f"lock OK - wrote {output_dir / 'lock.json'}")


# --------------------------------------------------------------------------
# score
# --------------------------------------------------------------------------

def cmd_score(args: argparse.Namespace) -> None:
    output_dir = args.output_dir
    c1_csv = output_dir / "c1_adjudication.csv"
    c8_csv = output_dir / "c8_sheet.csv"
    verify_lock(output_dir / "lock.json", {"c1_adjudication.csv": c1_csv, "c8_sheet.csv": c8_csv})

    c1_key = json.loads((output_dir / "c1_key.json").read_text(encoding="utf-8"))["candidates"]
    c8_key = json.loads((output_dir / "c8_key.json").read_text(encoding="utf-8"))["items"]
    deterministic = json.loads((output_dir / "deterministic.json").read_text(encoding="utf-8"))

    c1_answers = {row["row_id"]: C1Answer.model_validate(row) for row in _read_csv_rows(c1_csv)}
    c8_answers = {row["id"]: C8Answer.model_validate(row) for row in _read_csv_rows(c8_csv)}

    target_rows = _target_rows(args.dev_eval_path, args.targets_path)
    row_by_id = {row["row_id"]: row for row in target_rows}

    c1_recovered: dict[str, list[str]] = {run: [] for run in PASS2_RUNS}
    c6_credited: dict[str, list[str]] = {run: [] for run in PASS2_RUNS}
    run1_disagreements: dict[str, list[str]] = {run: [] for run in PASS2_RUNS}
    stability: dict[str, set[str]] = defaultdict(set)
    c5_by_shape: dict[str, Counter] = {run: Counter() for run in PASS2_RUNS}

    for row_id, answer in c1_answers.items():
        row = row_by_id.get(row_id)
        if row is None:
            continue
        for run in PASS2_RUNS:
            present_entries = [c1_key[mid][run] for mid in answer.match_ids if mid in c1_key and c1_key[mid][run]["present"]]
            if not present_entries:
                continue
            c1_recovered[run].append(row_id)
            stability[row_id].add(run)
            c5_by_shape[run][row["shape"]] += 1
            if any(e["pass"] == 1 for e in present_entries):
                run1_disagreements[run].append(row_id)
            else:
                c6_credited[run].append(row_id)

    row_stability = {
        row_id: ("both" if runs == set(PASS2_RUNS) else ("r1 only" if runs == {"pass2_r1"} else ("r2 only" if runs == {"pass2_r2"} else "neither")))
        for row_id in row_by_id
        for runs in [stability.get(row_id, set())]
    }

    # c8: per run, which K-ids belong to that run's own 30-sample.
    c8_per_run = {}
    reason_counts: dict[str, Counter] = defaultdict(Counter)
    useful_by_group: dict[str, list[bool]] = defaultdict(list)
    for run in PASS2_RUNS:
        run_ids = [kid for kid, info in c8_key.items() if run in info.get("run_memberships", [])]
        claims = 0
        for kid in run_ids:
            answer = c8_answers.get(kid)
            if answer is None:
                continue
            is_claim = answer.label == "claim"
            claims += is_claim
            if not is_claim:
                reason_counts[c8_key[kid]["group"]][answer.reason or "unspecified"] += 1
            useful_by_group[c8_key[kid]["group"]].append(is_claim and answer.duplicate == "no")
        n = len(run_ids)
        low, high = wilson_interval(claims, n)
        c8_per_run[run] = {"claims": claims, "n": n, "rate": (claims / n if n else None), "wilson": (low, high), "pass": (n > 0 and claims / n >= 0.70)}

    control_ids = [kid for kid, info in c8_key.items() if info["group"] == "pass1_control"]
    control_claims = sum(1 for kid in control_ids if kid in c8_answers and c8_answers[kid].label == "claim")
    control_n = len(control_ids)
    control_wilson = wilson_interval(control_claims, control_n)

    useful_rates = {}
    for group in ("pass2_r1", "pass2_r2", "pass1_control"):
        flags = useful_by_group.get(group, [])
        useful_count = sum(flags)
        n = len(flags)
        useful_rates[group] = {"useful": useful_count, "n": n, "rate": (useful_count / n if n else None), "wilson": wilson_interval(useful_count, n)}

    repeat_pairs = [(info["repeat_of"], kid) for kid, info in c8_key.items() if info.get("repeat_of")]
    agree_label = 0
    agree_duplicate = 0
    both_claim_pairs = 0
    for original_id, repeat_id in repeat_pairs:
        a, b = c8_answers.get(original_id), c8_answers.get(repeat_id)
        if a is None or b is None:
            continue
        if a.label == b.label:
            agree_label += 1
        if a.label == "claim" and b.label == "claim":
            both_claim_pairs += 1
            if a.duplicate == b.duplicate:
                agree_duplicate += 1

    false_dedup_lines = ["# False-dedup shortlist", ""]
    false_dedup_counts = {}
    for run in PASS2_RUNS:
        non_recovered = [row_id for row_id in row_by_id if row_id not in c1_recovered[run]]
        false_dedup_counts[run] = 0
        for row_id in non_recovered:
            row = row_by_id[row_id]
            buckets = _load_buckets(args.replay_root, run, row["paper_id"])
            scored = sorted(
                buckets["dropped_duplicate"],
                key=lambda e: -fuzz.token_sort_ratio(normalize_for_match(row["claim_text_verbatim"]), normalize_for_match(e["sentence"])),
            )[:3]
            if scored:
                false_dedup_counts[run] += 1
                false_dedup_lines.append(f"## {run} / {row_id} ({row['paper_id']})")
                for entry in scored:
                    false_dedup_lines.append(f"- {entry['sentence']}")
                false_dedup_lines.append("")

    (output_dir / "false_dedup_shortlist.md").write_text("\n".join(false_dedup_lines), encoding="utf-8")

    gate_table = {
        "c1_min_recovered": {"threshold": 5, **{run: len(c1_recovered[run]) for run in PASS2_RUNS}},
        "c6_min_own_pass1_miss_adds": {"threshold": 3, **{run: len(c6_credited[run]) for run in PASS2_RUNS}},
        "c4_projected_full_cost_max_inr": {"threshold": C4_MAX_INR, **deterministic["c3_c4"]["c4_mean_reading"]},
        "c7_min_pass2_grounding_rate": {"threshold": 0.95, **deterministic["c7"]},
        "c8_min_pass2_precision": {"threshold": 0.70, **c8_per_run},
    }

    result = {
        "gate_table": gate_table,
        "c1_recovered": {run: len(c1_recovered[run]) for run in PASS2_RUNS},
        "c6_credited": {run: len(c6_credited[run]) for run in PASS2_RUNS},
        "run1_adjudication_disagreements": run1_disagreements,
        "row_stability": row_stability,
        "c5_by_shape": {run: dict(c5_by_shape[run]) for run in PASS2_RUNS},
        "c8_per_run": c8_per_run,
        "pass1_control_precision": {"claims": control_claims, "n": control_n, "wilson": control_wilson},
        "useful_claim_rate": useful_rates,
        "not_claim_reason_counts": {group: dict(counts) for group, counts in reason_counts.items()},
        "self_consistency": {
            "label_agreement": f"{agree_label}/{len(repeat_pairs)}",
            "duplicate_agreement_when_both_claim": f"{agree_duplicate}/{both_claim_pairs}",
        },
        "false_dedup_shortlist_counts": false_dedup_counts,
        "deterministic": deterministic,
    }

    (output_dir / "b4_result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print("GATE TABLE")
    print(f"{'key':<32}{'threshold':<12}{'run1':<10}{'run2':<10}verdict")
    for key, c1 in (("c1_min_recovered", c1_recovered), ("c6_min_own_pass1_miss_adds", c6_credited)):
        r1, r2 = len(c1["pass2_r1"]), len(c1["pass2_r2"])
        threshold = 5 if key == "c1_min_recovered" else 3
        verdict = "PASS" if r1 >= threshold and r2 >= threshold else "FAIL"
        print(f"{key:<32}{threshold:<12}{r1:<10}{r2:<10}{verdict}")
    for key, reading in (("c4_projected_full_cost_max_inr", deterministic["c3_c4"]["c4_mean_reading"]),):
        verdict = "PASS" if reading["pass"] else "FAIL"
        print(f"{key:<32}{C4_MAX_INR:<12}{reading['projected_inr']:<10.1f}{'':<10}{verdict}")
    for run in PASS2_RUNS:
        c7run = deterministic["c7"][run]
        print(f"c7_min_pass2_grounding_rate/{run:<10}>=0.95{'':<6}{c7run['rate']}{'':<10}{'PASS' if c7run['pass'] else 'FAIL'}")
        c8run = c8_per_run[run]
        print(f"c8_min_pass2_precision/{run:<13}>=0.70{'':<6}{c8run['rate']}{'':<10}{'PASS' if c8run['pass'] else 'FAIL'}")
    print(f"wrote {output_dir / 'b4_result.json'}")
    print(f"false_dedup_shortlist counts: {false_dedup_counts}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--replay-root", type=Path, default=DEFAULT_REPLAY_ROOT)
    parser.add_argument("--targets-path", type=Path, default=DEFAULT_TARGETS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, func in (
        ("deterministic", cmd_deterministic),
        ("build-c1", cmd_build_c1),
        ("build-c8", cmd_build_c8),
        ("lock", cmd_lock),
        ("score", cmd_score),
    ):
        sub = subparsers.add_parser(name)
        _add_common_args(sub)
        sub.set_defaults(func=func)

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
