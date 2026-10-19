"""CLI: builds the clean-extraction attempt's K6/K7 blind label packs
(docs/decisions.md, "Clean-extraction attempt: K6/K7 labelling method,
caching dropped, K4 path - 2026-10-19"), replacing the bare-claim-text K6/K7
sheets from eval/build_clean_sheets.py (2026-10-17 method) with a pack that
shows each sampled sentence inside its surrounding paragraph, with the
nearest preceding heading, taken from the raw pipeline paper text.

  K6  30 kept cleaned pass-2 claims per run (seed 20261017), deduped across
      runs by (paper, normalized text). Human labels: A claim / B limitation
      or caveat / C setup or description / D other / unsure.
  K7  30 "same" drops per run (all if fewer, seed 20261017) - each shown
      next to the claim it was judged the same as, A/B order shuffled.
      Human labels: same / broader / narrower / different / unsure.

No LLM calls, no paid calls, no network. Reads one or more cleaned-run
--run-dirs (docs/evals/fixtures/dev/clean/<run_id>/, written by
eval/replay_clean.py: "<paper>_merged.json", "<paper>_clean.json"). The
C{i}/P{j} id scheme is reconstructed via eval.build_clean_sheets's own
_id_to_text_map (imported, not duplicated).

Usage:
  uv run python -m eval.build_label_pack --mode k6 \\
      --run-dirs docs/evals/fixtures/dev/clean/clean_r1 docs/evals/fixtures/dev/clean/clean_r2 \\
      --out-dir docs/evals/clean_k6k7_pack/k6
"""
import argparse
import html
import json
import random
import re
from pathlib import Path
from typing import Optional

from eval.blind_review import provenance, sha256_file
from eval.build_clean_sheets import _id_to_text_map
from extraction.grounding import (
    PARAGRAPH_SEPARATORS,
    _extract_span_context,
    _normalized_alignment,
    normalize_for_match,
)

REPO_ROOT = Path(__file__).parent.parent.parent
RESEARCH_PAPERS_DIR = REPO_ROOT / "docs" / "research_papers"

DEFAULT_SEED = 20261017
DEFAULT_N = 30

K6_LABELS = ["A", "B", "C", "D", "unsure"]
K7_LABELS = ["same", "broader", "narrower", "different", "unsure"]

# Forbidden in the pack's template/metadata (title, instructions, item
# chrome, footer) - never in the quoted paper text itself, which may
# legitimately contain e.g. "Figure C3" or the word "pass".
FORBIDDEN_SUBSTRINGS = ["pass1", "pass2", "reason_code", "neighbour_id"]
_ID_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])[CP]\d+(?![A-Za-z0-9_])")

_HEADING_VOCAB = {
    "abstract", "introduction", "related work", "background", "method", "methods",
    "methodology", "experiments", "experimental setup", "experimental results",
    "results", "discussion", "conclusion", "conclusions", "limitations",
    "appendix", "references", "acknowledgments", "acknowledgements",
}
_NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s+\S")
_HEADING_MAX_CHARS = 80
_HEADING_SCAN_LINES = 15

CLAIM_DEFINITION_V2 = """A claim is a sentence in which the authors assert something about THEIR OWN
work that a reader would take away as a finding, result or contribution,
and that could be stronger than the paper's evidence: (a) measured results
and comparisons; (b) positioning: beats or avoids a class of methods,
generalizes, is robust, efficient, cheap or simple; (c) contribution
statements ("we show / prove / demonstrate / contribute"); (d) premises the
method relies on, stated as fact. Hedged claims count; keep the hedge. A
sentence that states a result AND adds a caveat is still a claim.
NOT a claim: limitations, caveats and disclaimers whose main point is what
the work does NOT show, cannot conclude or does not guarantee (these are
evidence for the auditor, not claims to audit); background and prior work;
future work; setup or implementation description with no result;
definitions; headings; fragments; bare table rows."""


def _id_sort_key(candidate_id: str) -> tuple[str, int]:
    return (candidate_id[0], int(candidate_id[1:]))


def _paper_id_to_pdf(paper_id: str) -> Path:
    stem = paper_id[len("arxiv-"):] if paper_id.startswith("arxiv-") else paper_id
    return RESEARCH_PAPERS_DIR / f"{stem}.pdf"


def _paper_ids(run_dir: Path) -> list[str]:
    return sorted(p.stem[: -len("_merged")] for p in run_dir.glob("*_merged.json"))


def _load_run(run_dir: Path) -> tuple[dict[str, dict], dict[str, dict[str, str]]]:
    """Returns (decisions_by_paper, id_to_text_by_paper)."""
    decisions_by_paper: dict[str, dict] = {}
    id_to_text_by_paper: dict[str, dict[str, str]] = {}
    for paper_id in _paper_ids(run_dir):
        merged = json.loads((run_dir / f"{paper_id}_merged.json").read_text(encoding="utf-8"))["claims"]
        id_to_text_by_paper[paper_id] = _id_to_text_map(merged)
        clean_path = run_dir / f"{paper_id}_clean.json"
        decisions_by_paper[paper_id] = (
            json.loads(clean_path.read_text(encoding="utf-8"))["decisions"] if clean_path.exists() else {}
        )
    return decisions_by_paper, id_to_text_by_paper


def k6_pool(run_dir: Path) -> list[dict]:
    """Kept pass-2 candidates, sorted by (paper_id, candidate position)."""
    decisions_by_paper, id_to_text_by_paper = _load_run(run_dir)
    pool = []
    for paper_id, decisions in decisions_by_paper.items():
        id_to_text = id_to_text_by_paper[paper_id]
        for cid, decision in decisions.items():
            if decision["decision"] == "kept" and cid.startswith("P"):
                pool.append({"paper_id": paper_id, "candidate_id": cid, "claim_text": id_to_text[cid]})
    pool.sort(key=lambda item: (item["paper_id"], _id_sort_key(item["candidate_id"])))
    return pool


def k7_pool(run_dir: Path) -> tuple[list[dict], int]:
    """Dropped pass-2 candidates with a "same" relation, sorted by
    (paper_id, candidate position). Returns (pool, is_paper_claim_false_count)
    - the second value is informational only (not used for sampling or the
    gate): how many pool items were ALSO judged not a paper claim at all."""
    decisions_by_paper, id_to_text_by_paper = _load_run(run_dir)
    pool = []
    not_a_claim_count = 0
    for paper_id, decisions in decisions_by_paper.items():
        id_to_text = id_to_text_by_paper[paper_id]
        for cid, decision in decisions.items():
            if decision["decision"] != "dropped" or not cid.startswith("P"):
                continue
            same_relations = sorted(
                (r for r in decision.get("relations", []) if r["relation"] == "same"),
                key=lambda r: _id_sort_key(r["neighbour_id"]),
            )
            if not same_relations:
                continue
            neighbour_id = same_relations[0]["neighbour_id"]
            if cid not in id_to_text or neighbour_id not in id_to_text:
                continue
            if decision.get("is_paper_claim") is False:
                not_a_claim_count += 1
            pool.append({
                "paper_id": paper_id, "candidate_id": cid, "claim_text": id_to_text[cid],
                "neighbour_id": neighbour_id, "neighbour_text": id_to_text[neighbour_id],
                "is_paper_claim": decision.get("is_paper_claim"),
            })
    pool.sort(key=lambda item: (item["paper_id"], _id_sort_key(item["candidate_id"])))
    return pool, not_a_claim_count


def sample_run_pool(pool: list[dict], n: int, seed: int) -> list[dict]:
    """random.Random(seed).sample(pool, min(n, len(pool))) - deterministic
    for a fixed seed, independent of the caller's own iteration order since
    pool is already sorted by its own stable key before this is called."""
    if len(pool) <= n:
        return list(pool)
    return random.Random(seed).sample(pool, n)


def dedupe_k6_items(per_run_samples: list[tuple[str, list[dict]]]) -> list[dict]:
    """per_run_samples: [(run_id, sampled_items), ...]. Merges items across
    runs that share (paper_id, normalize_for_match(claim_text)); each output
    item carries every (run, candidate_id) pair that mapped to it, and the
    representative claim_text of the first occurrence seen."""
    groups: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for run_id, items in per_run_samples:
        for item in items:
            key = (item["paper_id"], normalize_for_match(item["claim_text"]))
            if key not in groups:
                groups[key] = {
                    "paper_id": item["paper_id"],
                    "claim_text": item["claim_text"],
                    "occurrences": [],
                }
                order.append(key)
            groups[key]["occurrences"].append({"run": run_id, "candidate_id": item["candidate_id"]})
    return [groups[key] for key in order]


def _paragraph_start(paper_text: str, match_start: int) -> int:
    """Mirrors the paragraph-start half of extraction/grounding.py's private
    _extract_span_context - needed separately here because that function
    only returns the final context string, not the boundary offset the
    heading scan needs to walk back from."""
    best = 0
    for sep in PARAGRAPH_SEPARATORS:
        idx = paper_text.rfind(sep, 0, match_start)
        if idx != -1:
            best = max(best, idx + len(sep))
    return best


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _HEADING_MAX_CHARS:
        return False
    if _NUMBERED_HEADING_RE.match(stripped):
        return True
    if stripped.endswith((".", ",", ";")):
        return False
    bare = stripped.rstrip(".:").lower()
    if bare in _HEADING_VOCAB:
        return True
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) >= 3 and all(c.isupper() for c in letters):
        return True
    return False


def nearest_preceding_heading(paper_text: str, paragraph_start: int) -> str:
    preceding = paper_text[:paragraph_start]
    lines = preceding.splitlines()
    for line in reversed(lines[-_HEADING_SCAN_LINES:]):
        if _looks_like_heading(line):
            return line.strip()
    return ""


def locate_and_render(claim_text: str, paper_text: Optional[str]) -> dict:
    """Returns {"not_found": bool, "heading": str, "before": str,
    "sentence": str, "after": str}. not_found=True (bare sentence, empty
    paragraph fields) when paper_text is unavailable or the sentence cannot
    be aligned above threshold."""
    if paper_text is None:
        return {"not_found": True, "heading": "", "before": "", "sentence": claim_text, "after": ""}
    span = _normalized_alignment(claim_text, paper_text)
    if span is None:
        return {"not_found": True, "heading": "", "before": "", "sentence": claim_text, "after": ""}
    start, end = span
    context = _extract_span_context(paper_text, start, end)
    matched = paper_text[start:end]
    pos = context.find(matched)
    if pos == -1:
        before, sentence, after = "", matched, ""
    else:
        before, sentence, after = context[:pos], matched, context[pos + len(matched):]
    heading = nearest_preceding_heading(paper_text, _paragraph_start(paper_text, start))
    return {"not_found": False, "heading": heading, "before": before, "sentence": sentence, "after": after}


def check_forbidden(metadata_text: str, extra_tokens: list[str]) -> list[str]:
    """Checks metadata_text (title/instructions/item chrome/footer - never
    quoted paper text) for forbidden tokens. Returns the list of violations
    found (empty if clean)."""
    lowered = metadata_text.lower()
    violations = []
    for token in FORBIDDEN_SUBSTRINGS:
        if token in lowered:
            violations.append(token)
    for token in extra_tokens:
        if token and token.lower() in lowered:
            violations.append(token)
    if _ID_TOKEN_RE.search(metadata_text):
        violations.append("bare C<n>/P<n> id token")
    return violations


def _render_block(block: dict) -> str:
    heading_html = f'<p class="heading">{html.escape(block["heading"])}</p>' if block["heading"] else ""
    if block["not_found"]:
        return (
            heading_html
            + '<p class="not-found">NOT FOUND IN PAPER TEXT</p>'
            + f'<p class="sentence">{html.escape(block["sentence"])}</p>'
        )
    return (
        heading_html
        + f'<p class="before">{html.escape(block["before"])}</p>'
        + f'<p class="sentence"><mark>{html.escape(block["sentence"])}</mark></p>'
        + f'<p class="after">{html.escape(block["after"])}</p>'
    )


def _build_k6_html(items: list[dict]) -> tuple[str, list[str]]:
    metadata_parts = ["K6 junk-rate labelling pack", CLAIM_DEFINITION_V2,
                       "Label each item A (claim) / B (limitation or caveat) / "
                       "C (setup or description) / D (other) / unsure in the labels CSV."]
    body = []
    for item in items:
        metadata_parts.append(item["item_id"])
        body.append(f'<section id="{item["item_id"]}"><h2>{item["item_id"]}</h2>'
                     + _render_block(item["render"]) + "</section>")
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>K6 label pack</title>"
        "<style>body{font-family:sans-serif;max-width:800px;margin:2rem auto;}"
        "mark{background:#ffe08a;} .heading{font-weight:bold;color:#555;}"
        ".not-found{color:#b00020;font-weight:bold;}</style></head><body>"
        f"<h1>{metadata_parts[0]}</h1><pre>{html.escape(metadata_parts[1])}</pre>"
        f"<p>{metadata_parts[2]}</p>" + "".join(body) + "</body></html>"
    )
    return page, metadata_parts


def _build_k7_html(items: list[dict]) -> tuple[str, list[str]]:
    metadata_parts = ["K7 dedup-safety labelling pack", CLAIM_DEFINITION_V2,
                       "Label each item same / broader / narrower / different / unsure "
                       "in the labels CSV: is A really the same claim as B?"]
    body = []
    for item in items:
        metadata_parts.extend([item["item_id"], "A", "B"])
        body.append(
            f'<section id="{item["item_id"]}"><h2>{item["item_id"]}</h2>'
            f'<div class="side"><h3>A</h3>{_render_block(item["a"])}</div>'
            f'<div class="side"><h3>B</h3>{_render_block(item["b"])}</div>'
            "</section>"
        )
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>K7 label pack</title>"
        "<style>body{font-family:sans-serif;max-width:800px;margin:2rem auto;}"
        "mark{background:#ffe08a;} .heading{font-weight:bold;color:#555;}"
        ".not-found{color:#b00020;font-weight:bold;} .side{border-top:1px solid #ccc;padding:0.5rem 0;}"
        "</style></head><body>"
        f"<h1>{metadata_parts[0]}</h1><pre>{html.escape(metadata_parts[1])}</pre>"
        f"<p>{metadata_parts[2]}</p>" + "".join(body) + "</body></html>"
    )
    return page, metadata_parts


def build_k6(run_dirs: list[Path], seed: int, n: int) -> tuple[list[dict], list[dict], dict, list[Path]]:
    """Returns (final_items, sample_manifest_rows, key, input_files)."""
    import hashlib

    per_run_samples = []
    manifest_rows = []
    input_files = []
    for run_dir in run_dirs:
        run_id = run_dir.name
        pool = k6_pool(run_dir)
        sample = sample_run_pool(pool, n, seed)
        per_run_samples.append((run_id, sample))
        for item in sample:
            digest = hashlib.sha256(normalize_for_match(item["claim_text"]).encode("utf-8")).hexdigest()
            manifest_rows.append({
                "run": run_id, "paper_id": item["paper_id"], "candidate_id": item["candidate_id"],
                "normalized_text_sha256": digest,
            })
        input_files.extend(sorted(run_dir.glob("*_merged.json")) + sorted(run_dir.glob("*_clean.json")))

    deduped = dedupe_k6_items(per_run_samples)
    rng = random.Random(seed)
    rng.shuffle(deduped)

    paper_cache: dict[str, Optional[str]] = {}
    final_items = []
    key: dict[str, dict] = {}
    for i, group in enumerate(deduped):
        item_id = f"L{i + 1:03d}"
        paper_id = group["paper_id"]
        if paper_id not in paper_cache:
            paper_cache[paper_id] = _load_paper_text(paper_id)
        render = locate_and_render(group["claim_text"], paper_cache[paper_id])
        final_items.append({"item_id": item_id, "render": render})
        key[item_id] = {
            "paper_id": paper_id, "occurrences": group["occurrences"], "not_found": render["not_found"],
        }

    return final_items, manifest_rows, key, input_files


def build_k7(run_dirs: list[Path], seed: int, n: int) -> tuple[list[dict], dict, list[Path], int]:
    """Returns (final_items, key, input_files, is_paper_claim_false_total)."""
    all_items = []
    input_files = []
    not_a_claim_total = 0
    for run_dir in run_dirs:
        run_id = run_dir.name
        pool, not_a_claim_count = k7_pool(run_dir)
        not_a_claim_total += not_a_claim_count
        sample = sample_run_pool(pool, n, seed)
        for item in sample:
            all_items.append((run_id, item))
        input_files.extend(sorted(run_dir.glob("*_clean.json")))

    rng = random.Random(seed)
    rng.shuffle(all_items)

    paper_cache: dict[str, Optional[str]] = {}
    final_items = []
    key: dict[str, dict] = {}
    for i, (run_id, item) in enumerate(all_items):
        item_id = f"L{i + 1:03d}"
        paper_id = item["paper_id"]
        if paper_id not in paper_cache:
            paper_cache[paper_id] = _load_paper_text(paper_id)
        paper_text = paper_cache[paper_id]
        candidate_render = locate_and_render(item["claim_text"], paper_text)
        neighbour_render = locate_and_render(item["neighbour_text"], paper_text)

        order = ["candidate", "neighbour"]
        if random.Random(f"{seed}-{item_id}-order").random() < 0.5:
            order = ["neighbour", "candidate"]
        sides = {"candidate": candidate_render, "neighbour": neighbour_render}
        a, b = sides[order[0]], sides[order[1]]

        final_items.append({"item_id": item_id, "a": a, "b": b})
        key[item_id] = {
            "paper_id": paper_id, "run": run_id, "candidate_id": item["candidate_id"],
            "neighbour_id": item["neighbour_id"], "is_paper_claim": item["is_paper_claim"],
            "order": order,
            "not_found": {"candidate": candidate_render["not_found"], "neighbour": neighbour_render["not_found"]},
        }

    return final_items, key, input_files, not_a_claim_total


def _load_paper_text(paper_id: str) -> Optional[str]:
    pdf_path = _paper_id_to_pdf(paper_id)
    if not pdf_path.exists():
        return None
    import os

    for env_key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(env_key, None)
    from main import extract_pdf_text_sync

    text, _ = extract_pdf_text_sync(str(pdf_path))
    return text


def _write_csv(path: Path, item_ids: list[str]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["item_id", "label", "note"])
        for item_id in item_ids:
            writer.writerow([item_id, "", ""])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["k6", "k7"], required=True)
    parser.add_argument("--run-dirs", type=Path, nargs="+", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    return parser


def _check_run_dirs(run_dirs: list[Path]) -> None:
    problems = []
    for run_dir in run_dirs:
        if not run_dir.is_dir():
            problems.append(f"{run_dir}: not a directory")
        elif not _paper_ids(run_dir):
            problems.append(f"{run_dir}: no *_merged.json files found")
    if problems:
        raise SystemExit("invalid --run-dirs:\n" + "\n".join(f"  {p}" for p in problems))


def main() -> None:
    args = _build_parser().parse_args()
    _check_run_dirs(args.run_dirs)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    key_dir = args.out_dir / "_key"
    key_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "k6":
        items, manifest_rows, key, input_files = build_k6(args.run_dirs, args.seed, args.n)
        page, metadata_parts = _build_k6_html(items)
        violations = check_forbidden(
            "".join(metadata_parts),
            [str(d) for d in args.run_dirs] + [d.name for d in args.run_dirs],
        )
        if violations:
            raise ValueError(f"forbidden content in k6 pack metadata: {violations}")

        manifest_path = args.out_dir / "sample_manifest.json"
        manifest_path.write_text(json.dumps(manifest_rows, indent=2), encoding="utf-8")
        print(f"wrote {manifest_path} sha256={sha256_file(manifest_path)}")

        pack_path = args.out_dir / "k6_pack.html"
        pack_path.write_text(page, encoding="utf-8")
        labels_path = args.out_dir / "k6_labels.csv"
        _write_csv(labels_path, [item["item_id"] for item in items])
        key_path = key_dir / "k6_key.json"
        key_path.write_text(
            json.dumps({"seed": args.seed, "n": args.n, "provenance": provenance(input_files), "items": key}, indent=2),
            encoding="utf-8",
        )

        not_found = sum(1 for v in key.values() if v["not_found"])
        print(f"k6: {len(items)} items after dedup, {not_found} NOT_FOUND")
        for p in (pack_path, labels_path, key_path):
            print(f"wrote {p} sha256={sha256_file(p)}")
    else:
        items, key, input_files, not_a_claim_total = build_k7(args.run_dirs, args.seed, args.n)
        page, metadata_parts = _build_k7_html(items)
        violations = check_forbidden(
            "".join(metadata_parts),
            [str(d) for d in args.run_dirs] + [d.name for d in args.run_dirs],
        )
        if violations:
            raise ValueError(f"forbidden content in k7 pack metadata: {violations}")

        pack_path = args.out_dir / "k7_pack.html"
        pack_path.write_text(page, encoding="utf-8")
        labels_path = args.out_dir / "k7_labels.csv"
        _write_csv(labels_path, [item["item_id"] for item in items])
        key_path = key_dir / "k7_key.json"
        key_path.write_text(
            json.dumps({"seed": args.seed, "n": args.n, "provenance": provenance(input_files), "items": key}, indent=2),
            encoding="utf-8",
        )

        not_found = sum(1 for v in key.values() if v["not_found"]["candidate"] or v["not_found"]["neighbour"])
        print(f"k7: {len(items)} items, {not_found} NOT_FOUND, "
              f"{not_a_claim_total} pool items also is_paper_claim=false (info only)")
        for p in (pack_path, labels_path, key_path):
            print(f"wrote {p} sha256={sha256_file(p)}")


if __name__ == "__main__":
    main()
