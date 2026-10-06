"""Builds eval/leakcheck/index.json for eval/check_prompt_leak.py.

Reads the four eval-paper PDFs, verifies each sha256 against the pinned value
BEFORE reading any text (abort on mismatch), extracts text exactly like the
worker (main.extract_pdf_text_sync: pymupdf page.get_text() concatenated), and
writes ONLY truncated SHA-256 hashes of:
  - every normalised word 8-gram,
  - paper/model/dataset-like names (auto-detected, plus a curated public list
    for the three golden papers; none for the held-out paper),
  - decimals with >= 2 integer digits (results-table numbers).
No paper text is written anywhere. Local only (needs the PDFs); CI reads the
committed index.

  uv run python scripts/build_leak_index.py
  uv run python scripts/build_leak_index.py --pdf heldout=path/to/2609.20812v3.pdf
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

import fitz  # noqa: E402

from eval.check_prompt_leak import (  # noqa: E402
    HASH_BYTES, INDEX_PATH, NGRAM_N, NORMALIZER_VERSION, REPO_DIR,
    hash_key, name_candidates, ngrams, normalize_tokens, pack_hashes, paper_decimals,
)

# source id -> (default PDF path, pinned sha256, held-out?)
SOURCES = {
    "reflexion": (REPO_DIR / "docs/research_papers/reflexion.pdf",
                  "6059b6f89fea9959bd3dab553fbb97756a3dfb1b15e3cbab2fbf3ab6664333bd", False),
    "cot": (REPO_DIR / "docs/research_papers/cot.pdf",
            "7d9f878c23b460e4566aa4ec9201b1abfb3b8faefb2b1356e411cb90fef72a12", False),
    "react": (REPO_DIR / "docs/research_papers/react.pdf",
              "f285b0971ae4a790e402fb93966bed3adde2cf0a04977d08b2b40d6ab0cace69", False),
    # Sealed paper: not stored in the repo (see docs/evals/heldout_eval.json
    # source_paper.pdf_location); same sha256 as source_paper.pdf_sha256.
    "heldout": (SERVICE_DIR / "scratch/heldout/2609.20812v3.pdf",
                "d6741be3aa68bd828642b7f4e362089ccb9f33bb39689e14c95f9bd5db6df783", True),
}

# Public names from the golden papers' titles/abstracts/tables, kept even when
# the auto heuristic would skip them (all-caps acronyms, multi-word names).
CURATED_GOLDEN_NAMES = {
    "reflexion": ["Reflexion", "verbal reinforcement", "episodic memory", "self-reflection", "HumanEval",
                  "AlfWorld", "HotPotQA", "MBPP", "LeetcodeHardGym", "GPT-4", "Self-Refine",
                  "Self-Debugging"],
    "cot": ["chain-of-thought", "chain of thought", "CoT", "GSM8K", "SVAMP", "PaLM", "LaMDA", "MultiArith",
            "StrategyQA", "self-consistency", "CSQA", "MAWPS", "AQuA", "ASDiv", "GPT-3"],
    "react": ["ReAct", "CoT-SC", "WebShop", "ALFWorld", "FEVER", "HotpotQA", "Supervised SoTA", "PaLM-540B",
              "inner monologue", "BUTLER", "Act-only"],
}


def pdf_text(path: Path) -> str:
    out = ""
    with fitz.open(path) as doc:
        for page in doc:
            out += page.get_text()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the hashed leak-check index from the eval PDFs")
    parser.add_argument("--pdf", action="append", default=[], metavar="SOURCE=PATH",
                        help="override a PDF location, e.g. heldout=C:/papers/2609.20812v3.pdf")
    parser.add_argument("--out", type=Path, default=INDEX_PATH)
    args = parser.parse_args()
    overrides = dict(s.split("=", 1) for s in args.pdf)

    # 1. verify every sha256 before reading any text
    paths = {}
    for sid, (default, sha, _) in SOURCES.items():
        path = Path(overrides.get(sid, default))
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != sha:
            print(f"ABORT: {sid} sha256 mismatch for {path}: {got} != pinned {sha}", file=sys.stderr)
            return 1
        paths[sid] = path

    # 2. hash
    index = {
        "header": {
            "normalizer_version": NORMALIZER_VERSION, "ngram_n": NGRAM_N, "hash_bytes": HASH_BYTES,
            "pymupdf_version": fitz.VersionBind, "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Truncated SHA-256 hashes only; no paper text. Built by scripts/build_leak_index.py.",
        },
        "sources": {},
    }
    for sid, path in paths.items():
        _, sha, heldout = SOURCES[sid]
        text = pdf_text(path)
        toks = normalize_tokens(text)
        names = [n for n, c in name_candidates(text).items() if c >= 2] + CURATED_GOLDEN_NAMES.get(sid, [])
        index["sources"][sid] = {
            "heldout": heldout,
            "pdf_sha256": sha,
            "ngrams8": pack_hashes(hash_key(g) for g in ngrams(toks, NGRAM_N)),
            "names": pack_hashes(hash_key(normalize_tokens(n)) for n in names if normalize_tokens(n)),
            "decimals": pack_hashes(hash_key([d]) for d in paper_decimals(text)),
        }
        print(f"{sid}: sha256 ok, {len(set(ngrams(toks, NGRAM_N)))} 8-grams, {len(set(names))} names hashed")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
