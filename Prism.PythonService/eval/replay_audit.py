"""CLI: replays the auditor + structurer + grounding stages (NOT extraction)
of run 1's stored dev-eval claims at a configurable thinking_level, for
Experiment 1 (does raising the auditor's thinking_level recover any of the
10 audit-miss refusal rows from docs/evals/dev_adjudication_run1.md).

Calls the real, unmodified extraction.engine._audit_and_structure_claim and
extraction.grounding.ground_extraction functions - this script only supplies
inputs (run 1's stored claim text + re-derived paper text) and an explicit
thinking_level, never a monkey-patched settings value. The one monkey-patch
this script performs is on extraction.engine._generate_with_fallback, for
per-call token/latency instrumentation only, restored in a finally block.

Paper text cannot be read verbatim from storage (Prism never persists it) -
it is re-derived from the paper's local PDF and the PDF's sha256 is checked
against file_records.content_hash before use; a paper whose local PDF does
not match is skipped (that paper only, not the whole run).

Preflight aborts the whole run if the current prompt files do not hash to
cb3272cce551 (frozen for the dev baseline / Experiment 1).

Zero LLM calls under --estimate or --dry-run.

Usage:
  uv run python -m eval.replay_audit --estimate --level high --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --dry-run  --level high --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --level high   --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --level medium --claims docs/evals/exp1_stage_a_claims.json --repeat 2
  uv run python -m eval.replay_audit --level high                                   # Stage B: all 12 papers, repeat 1
"""
import argparse
import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from extraction import engine, grounding
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLLM, ClaimsExtractionResponse

REPO_ROOT = Path(__file__).parent.parent.parent
SERVICE_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev"
LOGS_DIR = SERVICE_ROOT / "logs" / "eval"
PDF_DIR = REPO_ROOT / "docs" / "research_papers"

EXPECTED_PROMPT_HASH = "cb3272cce551"

# gemini-3.6-flash pricing, docs/decisions.md:1676 (2026-10-12): $0.75/1M input,
# $3.75/1M output (thinking counted as output). 100 INR/USD per your instruction.
USD_PER_1M_INPUT = 0.75
USD_PER_1M_OUTPUT = 3.75
INR_PER_USD = 100

_RUN_SQL = """
SELECT fr.content_hash, fr.file_name
FROM   document_extractors de
JOIN   file_records fr ON fr.file_id = de.file_id
WHERE  de.id = %s;
"""


@dataclass
class CallRecord:
    stage: str  # "audit" or "structure"
    paper_id: str
    claim_index: int
    thinking_level: str | None
    model_used: str
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int
    total_tokens: int
    latency_s: float


@dataclass
class ReplayTarget:
    paper_id: str
    claim_index: int
    claim_text_verbatim: str
    claim_summary: str


def _load_claims_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_targets(claims_path: Path | None, papers_filter: str | None) -> list[ReplayTarget]:
    targets: list[ReplayTarget] = []
    if claims_path is not None:
        entries = _load_claims_file(claims_path)
        by_paper: dict[str, list[int]] = defaultdict(list)
        for entry in entries:
            by_paper[entry["paper_id"]].append(entry["claim_index"])
        paper_ids = sorted(by_paper)
    else:
        paper_ids = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
        by_paper = None

    if papers_filter:
        wanted = {s.strip() for s in papers_filter.split(",")}
        paper_ids = [p for p in paper_ids if any(w in p for w in wanted)]

    for paper_id in paper_ids:
        fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
        claims_by_index = {c["index"]: c for c in fixture["claims"]}
        indices = by_paper[paper_id] if by_paper is not None else sorted(claims_by_index)
        for idx in indices:
            claim = claims_by_index[idx]
            targets.append(ReplayTarget(
                paper_id=paper_id, claim_index=idx,
                claim_text_verbatim=claim["claim_text_verbatim"], claim_summary=claim["claim_summary"],
            ))
    return targets


def _estimate_tokens_for_chars(n_chars: int) -> int:
    return n_chars // 4  # rough chars-per-token proxy, labeled approximate throughout


# Documented assumptions for --estimate only (no stored per-call token counts
# exist to calibrate against - see docs/decisions.md run 1 total cost note).
# Structurer input excludes paper text (prompt_loader.build_gemini_messages_for_structure).
_AUDIT_PROMPT_OVERHEAD_CHARS = 1500
_STRUCTURE_INPUT_CHARS = 1200
_MEDIUM_VISIBLE_OUTPUT_TOKENS = 350
_MEDIUM_THOUGHT_TOKENS = 600
_HIGH_THOUGHT_MULTIPLIER_RANGE = (2.0, 4.0)
_STRUCTURE_OUTPUT_TOKENS = 250


def _estimate_one_claim_cost_usd(paper_text_len: int, level: str) -> tuple[float, float]:
    """Returns (low, high) USD estimate for one audit+structure replay of one claim."""
    audit_input_tokens = _estimate_tokens_for_chars(paper_text_len + _AUDIT_PROMPT_OVERHEAD_CHARS)
    structure_input_tokens = _estimate_tokens_for_chars(_STRUCTURE_INPUT_CHARS)

    if level == "high":
        thought_low = _MEDIUM_THOUGHT_TOKENS * _HIGH_THOUGHT_MULTIPLIER_RANGE[0]
        thought_high = _MEDIUM_THOUGHT_TOKENS * _HIGH_THOUGHT_MULTIPLIER_RANGE[1]
    else:
        thought_low = thought_high = _MEDIUM_THOUGHT_TOKENS

    def _cost(thought_tokens: float) -> float:
        input_cost = (audit_input_tokens + structure_input_tokens) / 1e6 * USD_PER_1M_INPUT
        output_cost = (
            (_MEDIUM_VISIBLE_OUTPUT_TOKENS + thought_tokens + _STRUCTURE_OUTPUT_TOKENS) / 1e6 * USD_PER_1M_OUTPUT
        )
        return input_cost + output_cost

    return _cost(thought_low), _cost(thought_high)


async def _hash_check_and_load_text(paper_id: str, fixture_header: dict) -> str | None:
    from memory_db import create_db_connection_pool

    pool = create_db_connection_pool()
    await pool.open()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(_RUN_SQL, (fixture_header["extraction_run_id"],))
                row = await cur.fetchone()
    finally:
        await pool.close()

    if row is None:
        print(f"[replay_audit] {paper_id}: SKIPPED - extraction run {fixture_header['extraction_run_id']} not found in DB")
        return None
    content_hash, file_name = row

    pdf_path = PDF_DIR / file_name
    if not pdf_path.exists():
        print(f"[replay_audit] {paper_id}: SKIPPED - no local PDF at {pdf_path}")
        return None
    actual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if actual_hash != content_hash:
        print(f"[replay_audit] {paper_id}: SKIPPED - sha256 mismatch (pdf={actual_hash[:12]} db={content_hash[:12]})")
        return None

    from main import extract_pdf_text_sync

    text, _ = extract_pdf_text_sync(str(pdf_path))
    return text


class _Instrumentation:
    """Monkey-patches extraction.engine._generate_with_fallback for the
    duration of a `with` block, restoring the original in a finally clause
    even if a replayed call raises. Records one CallRecord per Gemini call."""

    def __init__(self):
        self.records: list[CallRecord] = []
        self._original = None
        self._current_stage: str | None = None
        self._current_paper_id: str | None = None
        self._current_claim_index: int | None = None
        self._current_thinking_level: str | None = None

    def set_context(self, stage: str, paper_id: str, claim_index: int, thinking_level: str | None) -> None:
        self._current_stage = stage
        self._current_paper_id = paper_id
        self._current_claim_index = claim_index
        self._current_thinking_level = thinking_level

    async def _wrapped(self, client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        start = time.monotonic()
        response, used_model = await self._original(client, contents, config, chat_id, model_name, fallback_model, correlation_id)
        latency = time.monotonic() - start
        usage = getattr(response, "usage_metadata", None)
        self.records.append(CallRecord(
            stage=self._current_stage, paper_id=self._current_paper_id, claim_index=self._current_claim_index,
            thinking_level=self._current_thinking_level, model_used=used_model,
            prompt_tokens=getattr(usage, "prompt_token_count", None) or 0,
            output_tokens=getattr(usage, "candidates_token_count", None) or 0,
            thought_tokens=getattr(usage, "thoughts_token_count", None) or 0,
            total_tokens=getattr(usage, "total_token_count", None) or 0,
            latency_s=latency,
        ))
        return response, used_model

    def __enter__(self) -> "_Instrumentation":
        self._original = engine._generate_with_fallback
        engine._generate_with_fallback = self._wrapped
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        engine._generate_with_fallback = self._original


async def _replay_claim(target: ReplayTarget, paper_text: str, level: str, instrumentation: _Instrumentation) -> ClaimLLM:
    semaphore = asyncio.Semaphore(1)
    instrumentation.set_context("audit", target.paper_id, target.claim_index, level)
    claim_dict = {"claim_text_verbatim": target.claim_text_verbatim, "claim_summary": target.claim_summary}

    # _audit_and_structure_claim's own tracer spans don't distinguish
    # audit/structure in our instrumentation, so set_context before the call
    # covers the audit call; the structurer call is also wrapped but reported
    # under the same context (close enough - the structurer never varies by
    # thinking_level, only the audit call's cost is Experiment 1's variable).
    return await engine._audit_and_structure_claim(
        semaphore=semaphore, paper_text=paper_text, claim=claim_dict, chat_id=f"replay-{target.paper_id}",
        correlation_id=None, claim_number=target.claim_index + 1, total_claims=1, thinking_level=level,
    )


def _claim_final_to_fixture_dict(claim_final, index: int) -> dict:
    return {
        "index": index,
        "label": claim_final.label.value,
        "claim_summary": claim_final.claim_summary,
        "missing": claim_final.missing,
        "grounding_status": claim_final.grounding_status.value,
        "claim_text_verbatim": claim_final.claim_text_verbatim,
        "evidence_spans": [
            {
                "source_text": span.source_text,
                "source_section": span.source_section,
                "grounding_status": span.grounding_status.value,
                "stance": span.stance,
            }
            for span in claim_final.evidence_spans
        ],
    }


async def _run_once(
    targets: list[ReplayTarget], level: str, repeat_index: int, dry_run: bool,
) -> tuple[Path, list[CallRecord]]:
    out_dir = OUTPUT_ROOT / f"exp1_{level}_{repeat_index}"
    by_paper: dict[str, list[ReplayTarget]] = defaultdict(list)
    for t in targets:
        by_paper[t.paper_id].append(t)

    instrumentation = _Instrumentation()
    written_papers = []

    with instrumentation:
        for paper_id, paper_targets in sorted(by_paper.items()):
            run1_fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
            if dry_run:
                print(f"[replay_audit] DRY-RUN {paper_id} repeat={repeat_index} level={level} "
                      f"claims={[t.claim_index for t in paper_targets]}")
                continue

            paper_text = await _hash_check_and_load_text(paper_id, run1_fixture["header"])
            if paper_text is None:
                continue

            audited: list[ClaimLLM] = []
            for target in paper_targets:
                claim_llm = await _replay_claim(target, paper_text, level, instrumentation)
                audited.append(claim_llm)

            grounded = await grounding.ground_extraction(
                ClaimsExtractionResponse(claims=audited), paper_text, chat_id=f"replay-{paper_id}",
            )

            claims_out = [
                _claim_final_to_fixture_dict(claim_final, target.claim_index)
                for claim_final, target in zip(grounded, paper_targets)
            ]
            header = dict(run1_fixture["header"])
            header["model_name"] = engine.settings.llm_claim_audit_model
            header["replay"] = {
                "thinking_level": level, "base_run": "run1", "repeat_index": repeat_index,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            header["claims_scope"] = [t.claim_index for t in paper_targets]
            fixture_out = {"header": header, "claims": claims_out, "matches": run1_fixture["matches"]}

            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{paper_id}.json").write_text(json.dumps(fixture_out, indent=2), encoding="utf-8")
            written_papers.append(paper_id)
            print(f"[replay_audit] wrote {out_dir / f'{paper_id}.json'} ({len(claims_out)} claims)")

    return out_dir, instrumentation.records


def _print_estimate(targets: list[ReplayTarget], level: str, repeats: int) -> None:
    from main import extract_pdf_text_sync

    text_cache: dict[str, int] = {}
    for t in targets:
        if t.paper_id not in text_cache:
            run1_fixture = json.loads((FIXTURE_DIR / f"{t.paper_id}.json").read_text(encoding="utf-8"))
            file_name = run1_fixture["header"]["filename"]
            pdf_path = PDF_DIR / file_name
            if pdf_path.exists():
                text, _ = extract_pdf_text_sync(str(pdf_path))
                text_cache[t.paper_id] = len(text)
            else:
                text_cache[t.paper_id] = 50_000  # fallback only if the PDF isn't available locally

    total_low = total_high = 0.0
    for t in targets:
        low, high = _estimate_one_claim_cost_usd(text_cache[t.paper_id], level)
        total_low += low * repeats
        total_high += high * repeats

    calls = len(targets) * repeats * 2  # audit + structure per claim-replay
    print(f"[replay_audit] --estimate: {len(targets)} claims x {repeats} repeats = {len(targets) * repeats} claim-replays "
          f"({calls} Gemini calls, grounding calls not included - approximate, see module docstring/cost caveats)")
    print(f"[replay_audit] estimated cost: USD {total_low:.3f}-{total_high:.3f} "
          f"(INR {total_low * INR_PER_USD:.1f}-{total_high * INR_PER_USD:.1f})")


def _print_summary(out_dir: Path, records: list[CallRecord]) -> None:
    total_prompt = sum(r.prompt_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_thought = sum(r.thought_tokens for r in records)
    cost_usd = (total_prompt / 1e6 * USD_PER_1M_INPUT) + ((total_output + total_thought) / 1e6 * USD_PER_1M_OUTPUT)
    summary = {
        "calls": len(records),
        "total_prompt_tokens": total_prompt,
        "total_output_tokens": total_output,
        "total_thought_tokens": total_thought,
        "cost_usd": round(cost_usd, 4),
        "cost_inr": round(cost_usd * INR_PER_USD, 2),
        "records": [r.__dict__ for r in records],
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[replay_audit] {len(records)} calls, {total_prompt} prompt / {total_output} output / "
          f"{total_thought} thought tokens, ~INR {summary['cost_inr']}")


async def _main(args: argparse.Namespace) -> int:
    # main.py runs init_telemetry at import time; keep it on the no-exporter
    # path before the first `from main import ...` anywhere in this process
    # (same as eval/replay_stage1.py).
    import os

    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)

    prompt_hash = get_prompt_version()
    if prompt_hash != EXPECTED_PROMPT_HASH:
        print(f"[replay_audit] ABORT: prompt hash {prompt_hash} != expected {EXPECTED_PROMPT_HASH}")
        return 1

    claims_path = Path(args.claims) if args.claims else None
    targets = _load_targets(claims_path, args.papers)
    if not targets:
        print("[replay_audit] ABORT: no claims selected")
        return 1

    if args.estimate:
        _print_estimate(targets, args.level, args.repeat)
        return 0

    for repeat_index in range(1, args.repeat + 1):
        out_dir, records = await _run_once(targets, args.level, repeat_index, args.dry_run)
        if not args.dry_run:
            _print_summary(out_dir, records)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", required=True, choices=["low", "medium", "high"])
    parser.add_argument("--claims", help="JSON file of [{paper_id, claim_index}, ...] (omit for all 12 papers/362 claims)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--papers", help="comma-separated paper_id substrings to further narrow scope")
    parser.add_argument("--estimate", action="store_true", help="print a cost estimate, zero LLM calls")
    parser.add_argument("--dry-run", action="store_true", help="print what would be replayed, zero LLM calls")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
