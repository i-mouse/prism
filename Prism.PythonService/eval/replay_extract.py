"""CLI: replays the extractor stage (Call #2 ONLY - not audit/structure) for
Experiment 2 (redesigned) (do 8 new claim-shape few-shot examples recover any
of the 13 extraction-miss refusal rows from run 1, on top of the loader "note"
field fix, which is the base for BOTH arms here - not the thing under test).

Calls the real, unmodified extraction.engine._call_gemini_json function with
messages built by extraction.prompt_loader.build_gemini_messages_for_extractor,
passing fewshot_fix/fewshot_shapes explicitly per --variant (control:
fix=True, shapes=False; treatment: fix=True, shapes=True) - never a
monkey-patched settings value. The one monkey-patch this script performs is on
extraction.engine._generate_with_fallback, for per-call token/latency
instrumentation only, restored in a finally block - identical convention to
eval/replay_audit.py.

Paper text cannot be read verbatim from storage (Prism never persists it) -
it is re-derived from the paper's local PDF and the PDF's sha256 is checked
against file_records.content_hash before use (eval.replay_audit's
_hash_check_and_load_text, reused here); a paper whose local PDF does not
match is skipped (that paper only, not the whole run).

Three ways to estimate cost, cheapest first:
  --estimate       Zero network calls. Rough chars/4 proxy on the fixed
                    few-shot prompt + paper text, output estimated from run
                    1's stored claim sizes. No thinking-token estimate -
                    extractor calls have no thinking_config, but Gemini may
                    still emit some; this mode cannot see that.
  --count-tokens    Free network calls to Gemini's countTokens endpoint (no
                    generateContent, no charge) for the EXACT input-token
                    count of the real assembled request, per paper x variant.
                    Output still estimated from run 1's claim sizes.
  (a real run)      Actual generateContent calls - billed. Use --max-inr to
                    cap spend; the pilot (one paper, control, --max-inr 30)
                    is the only way to measure real thinking-token usage.

Preflight aborts the whole run if the selected --variant's prompt hash does
not match EXPECTED_PROMPT_HASH[variant] (control=0e07bb0f2680, i.e. the
already-registered loader fix's hash; treatment=da3a1ab6b587 - both computed
from the real prompt files, not asserted blind). --count-tokens with no
--variant checks every variant in VARIANT_CONFIG.

Zero LLM calls under --estimate, --count-tokens, or --dry-run.

Usage:
  uv run python -m eval.replay_extract --estimate --variant control --papers P1,P2
  uv run python -m eval.replay_extract --count-tokens --variant treatment --papers P7
  uv run python -m eval.replay_extract --dry-run --variant control --papers P7
  uv run python -m eval.replay_extract --variant control --papers P7 --max-inr 30   # pilot
  uv run python -m eval.replay_extract --variant treatment --repeat 2 --max-inr 250
"""
import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

from eval.pricing import cost_inr
from eval.replay_audit import FIXTURE_DIR, PDF_DIR, _hash_check_and_load_text
from extraction import engine
from extraction.prompt_loader import build_gemini_messages_for_extractor
from extraction.prompt_version import get_prompt_version

REPO_ROOT = Path(__file__).parent.parent.parent
OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp2"

# Experiment 2 (redesigned): control = loader fix on, shapes off (the base for
# both arms); treatment = loader fix on, shapes on (the 8 new examples under
# test). Both hashes computed from the real prompt files via get_prompt_version,
# not asserted blind - see tests/test_extractor_fewshot_shapes.py's
# test_three_reachable_hash_states_are_pairwise_distinct for how they were
# derived.
VARIANT_CONFIG = {
    "control": {"fewshot_fix": True, "fewshot_shapes": False},
    "treatment": {"fewshot_fix": True, "fewshot_shapes": True},
}
EXPECTED_PROMPT_HASH = {
    "control": "0e07bb0f2680",
    "treatment": "da3a1ab6b587",
}

# Rough chars/4 proxy for --estimate (zero network calls). Measured directly
# from build_gemini_messages_for_extractor with paper_text="": fixed system
# prompt + few-shot envelope chars, per variant - unblanking the loader-fix
# examples (control) and then adding the 8 shapes examples + addendum
# (treatment) both change this size, unlike the old both-flags-off baseline
# (13,629 chars) this used to share across variants.
_FIXED_PROMPT_CHARS = {"control": 17_473, "treatment": 22_941}


@dataclass
class CallRecord:
    paper_id: str
    variant: str
    model_used: str
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int
    total_tokens: int
    latency_s: float


def _load_paper_ids(papers_filter: str | None) -> list[str]:
    paper_ids = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
    if papers_filter:
        wanted = {s.strip() for s in papers_filter.split(",")}
        paper_ids = [p for p in paper_ids if any(w in p for w in wanted)]
    return paper_ids


def _run1_claim_output_chars(paper_id: str) -> int:
    """Sum of claim_text_verbatim + claim_summary chars across run 1's stored
    claims for this paper - the output proxy for both --estimate and
    --count-tokens, since a fresh extraction's output is assumed similarly
    sized."""
    fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
    return sum(len(c["claim_text_verbatim"]) + len(c["claim_summary"]) for c in fixture["claims"])


class _Instrumentation:
    """Monkey-patches extraction.engine._generate_with_fallback for the
    duration of a `with` block, restoring the original in a finally clause
    even if a replayed call raises. Identical convention to
    eval/replay_audit.py's _Instrumentation."""

    def __init__(self):
        self.records: list[CallRecord] = []
        self._original = None
        self._current_paper_id: str | None = None
        self._current_variant: str | None = None

    def set_context(self, paper_id: str, variant: str) -> None:
        self._current_paper_id = paper_id
        self._current_variant = variant

    async def _wrapped(self, client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        start = time.monotonic()
        response, used_model = await self._original(client, contents, config, chat_id, model_name, fallback_model, correlation_id)
        latency = time.monotonic() - start
        usage = getattr(response, "usage_metadata", None)
        self.records.append(CallRecord(
            paper_id=self._current_paper_id, variant=self._current_variant, model_used=used_model,
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


async def _extract_one_paper(paper_text: str, fewshot_fix: bool, fewshot_shapes: bool) -> dict:
    """Calls the real, unmodified engine._call_gemini_json with the
    extractor's messages - the same call extraction.engine.extract_claims
    makes for Call #2, in isolation (no audit/structure)."""
    from config import settings

    return await engine._call_gemini_json(
        messages=build_gemini_messages_for_extractor(paper_text, fewshot_fix=fewshot_fix, fewshot_shapes=fewshot_shapes),
        chat_id=f"replay-extract-{fewshot_fix}-{fewshot_shapes}",
        correlation_id=None,
        log_subdir="extraction",
        model_name=settings.llm_extraction_model,
        fallback_model=settings.llm_extraction_fallback_model,
    )


def _print_rough_estimate(paper_ids: list[str], variant: str, repeats: int) -> None:
    fixed_tokens = _FIXED_PROMPT_CHARS[variant] / 4
    total_low = total_high = 0.0
    for paper_id in paper_ids:
        # Paper text size isn't available without a DB+PDF read; fall back to
        # the Phase 0 measured average (93,283 chars) when we can't see the
        # real PDF without a DB round-trip. --count-tokens (below) gives an
        # exact figure instead of this proxy.
        avg_paper_chars = 93_283
        input_tokens = fixed_tokens + avg_paper_chars / 4
        output_tokens = _run1_claim_output_chars(paper_id) / 4 if (FIXTURE_DIR / f"{paper_id}.json").exists() else 2_000
        low = cost_inr(input_tokens, output_tokens)
        high = cost_inr(input_tokens * 1.8, output_tokens * 1.8)
        total_low += low
        total_high += high
    total_low *= repeats
    total_high *= repeats
    print(f"[replay_extract] --estimate (rough chars/4 proxy, zero network calls): {len(paper_ids)} papers x {repeats} "
          f"repeats, variant={variant}")
    print(f"[replay_extract] estimated cost: INR {total_low:.1f}-{total_high:.1f} "
          "(no thinking-token estimate - see --count-tokens and the pilot for a grounded figure)")


async def _print_count_tokens_estimate(paper_ids: list[str], variants: list[str]) -> None:
    from config import settings
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.ai_api_key)
    total_input_tokens = 0
    total_output_tokens_est = 0.0

    for paper_id in paper_ids:
        run1_fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
        paper_text = await _hash_check_and_load_text(paper_id, run1_fixture["header"])
        if paper_text is None:
            continue
        output_chars = _run1_claim_output_chars(paper_id)
        output_tokens_est = output_chars / 4 * 1.15  # +15% JSON structural overhead

        for variant in variants:
            config = VARIANT_CONFIG[variant]
            messages = build_gemini_messages_for_extractor(
                paper_text, fewshot_fix=config["fewshot_fix"], fewshot_shapes=config["fewshot_shapes"]
            )
            system_prompt = next(m["content"] for m in messages if m["role"] == "system")
            contents = [
                types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])])
                for m in messages if m["role"] != "system"
            ]
            response = await client.aio.models.count_tokens(
                model=settings.llm_extraction_model,
                contents=contents,
                config=types.CountTokensConfig(system_instruction=system_prompt),
            )
            input_tokens = response.total_tokens
            total_input_tokens += input_tokens
            total_output_tokens_est += output_tokens_est
            print(f"[replay_extract] --count-tokens {paper_id} variant={variant}: "
                  f"input={input_tokens} output(est)={output_tokens_est:.0f}")

    low = cost_inr(total_input_tokens, total_output_tokens_est)
    print(f"\n[replay_extract] --count-tokens totals: input={total_input_tokens} output(est)={total_output_tokens_est:.0f}")
    print(f"[replay_extract] estimated cost (no thinking tokens - unknown until the pilot): INR {low:.1f}+")


async def _run_once(
    paper_ids: list[str], variant: str, repeat_index: int, dry_run: bool, max_inr: float | None,
) -> tuple[Path, list[CallRecord]]:
    config = VARIANT_CONFIG[variant]
    fewshot_fix, fewshot_shapes = config["fewshot_fix"], config["fewshot_shapes"]
    out_dir = OUTPUT_ROOT / f"{variant}_r{repeat_index}"
    instrumentation = _Instrumentation()

    with instrumentation:
        for paper_id in paper_ids:
            if dry_run:
                print(f"[replay_extract] DRY-RUN {paper_id} variant={variant} repeat={repeat_index}")
                continue

            spent_so_far = sum(cost_inr(r.prompt_tokens, r.output_tokens, r.thought_tokens) for r in instrumentation.records)
            if max_inr is not None and spent_so_far >= max_inr:
                print(f"[replay_extract] ABORT before {paper_id}: spend so far INR {spent_so_far:.2f} >= --max-inr {max_inr}")
                break

            run1_fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
            paper_text = await _hash_check_and_load_text(paper_id, run1_fixture["header"])
            if paper_text is None:
                continue

            instrumentation.set_context(paper_id, variant)
            extracted = await _extract_one_paper(paper_text, fewshot_fix, fewshot_shapes)
            claims = extracted.get("claims", [])

            header = {
                "paper_id": paper_id,
                "variant": variant,
                "fewshot_fix": fewshot_fix,
                "fewshot_shapes": fewshot_shapes,
                "prompt_hash": get_prompt_version(fewshot_fix=fewshot_fix, fewshot_shapes=fewshot_shapes),
                "model_name": engine.settings.llm_extraction_model,
                "extraction_run_id": run1_fixture["header"]["extraction_run_id"],
                "replay": {
                    "base_run": "run1", "repeat_index": repeat_index,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            }
            claims_out = [
                {"index": i, "claim_text_verbatim": c.get("claim_text_verbatim", ""), "claim_summary": c.get("claim_summary", "")}
                for i, c in enumerate(claims)
            ]
            fixture_out = {"header": header, "claims": claims_out}

            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{paper_id}.json").write_text(json.dumps(fixture_out, indent=2), encoding="utf-8")
            print(f"[replay_extract] wrote {out_dir / f'{paper_id}.json'} ({len(claims_out)} claims)")

    return out_dir, instrumentation.records


def _print_summary(out_dir: Path, records: list[CallRecord]) -> None:
    total_prompt = sum(r.prompt_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_thought = sum(r.thought_tokens for r in records)
    cost = cost_inr(total_prompt, total_output, total_thought)
    summary = {
        "calls": len(records),
        "total_prompt_tokens": total_prompt,
        "total_output_tokens": total_output,
        "total_thought_tokens": total_thought,
        "cost_inr": round(cost, 2),
        "records": [r.__dict__ for r in records],
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[replay_extract] {len(records)} calls, {total_prompt} prompt / {total_output} output / "
          f"{total_thought} thought tokens, ~INR {summary['cost_inr']}")


async def _main(args: argparse.Namespace) -> int:
    import os

    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)

    variants_to_check = [args.variant] if args.variant else list(VARIANT_CONFIG)
    for variant in variants_to_check:
        config = VARIANT_CONFIG[variant]
        prompt_hash = get_prompt_version(fewshot_fix=config["fewshot_fix"], fewshot_shapes=config["fewshot_shapes"])
        if prompt_hash != EXPECTED_PROMPT_HASH[variant]:
            print(f"[replay_extract] ABORT: {variant} prompt hash {prompt_hash} != expected {EXPECTED_PROMPT_HASH[variant]}")
            return 1

    paper_ids = _load_paper_ids(args.papers)
    if not paper_ids:
        print("[replay_extract] ABORT: no papers selected")
        return 1

    if args.count_tokens:
        variants = [args.variant] if args.variant else list(VARIANT_CONFIG)
        await _print_count_tokens_estimate(paper_ids, variants)
        return 0

    if not args.variant:
        print("[replay_extract] ABORT: --variant is required for --estimate, --dry-run, and real runs")
        return 1

    if args.estimate:
        _print_rough_estimate(paper_ids, args.variant, args.repeat)
        return 0

    for repeat_index in range(1, args.repeat + 1):
        out_dir, records = await _run_once(paper_ids, args.variant, repeat_index, args.dry_run, args.max_inr)
        if not args.dry_run:
            _print_summary(out_dir, records)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", choices=["control", "treatment"])
    parser.add_argument("--papers", help="comma-separated paper_id substrings (omit for all run1 fixture papers)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--estimate", action="store_true", help="rough chars/4 proxy, zero network calls")
    parser.add_argument("--count-tokens", action="store_true", help="free countTokens calls for exact input tokens")
    parser.add_argument("--dry-run", action="store_true", help="print what would be replayed, zero LLM calls")
    parser.add_argument("--max-inr", type=float, default=None, help="abort before any call once spend so far reaches this cap")
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
