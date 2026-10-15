"""CLI: replays pass 1 + pass 2 + merge (extraction only - no audit, no
structure) for Experiment 3 (does windowed "copy-only" pass-2 extraction
recover quiet claims pass 1 alone misses?).

Calls the real, unmodified extraction.engine._call_gemini_json (the same
pass-1 extractor call extraction.engine.extract_claims makes) and
extraction.merge.merge_pass2_claims. Pass 2 is replayed with the same
building blocks extraction.pass2.run_pass2 uses - the same
extraction.prompt_loader.build_gemini_messages_for_pass2 prompt,
extraction.engine._call_gemini_structured call, SentenceListLLM schema, and
model settings - but with its own sequential, one-window-at-a-time loop
instead of run_pass2's concurrent gather, since this script must check
--max-inr between every window call. EXTRACTOR_SECOND_PASS is forced on for
this script's own pass-2 calls regardless of the live
settings.extractor_second_pass value - this script decides per call which
stage to run, it never flips the global flag.

A window call that raises (after extraction.engine's own retry/fallback is
exhausted) is logged and skipped, not fatal to the paper - the paper's
failed_window_count is recorded in its output header and it is marked
"incomplete" when that count is greater than zero. If --max-inr stops a run
mid-paper (budget exhausted partway through that paper's windows), that
paper's output files are not written at all - its pass-1 and partial pass-2
results would misrepresent a paper this run never actually finished.

Monkey-patches extraction.engine._generate_with_fallback for per-call
token/finish_reason/latency instrumentation only, restored in a finally
block - identical convention to eval/replay_audit.py and eval/replay_extract.py,
extended here to also capture finish_reason (via
extraction.engine._extract_usage_and_finish_reason) so a silent output-token
cutoff on any call, pass 1 or pass 2, is visible in this run's output.

Paper text is re-derived from the paper's local PDF via
eval.replay_audit._hash_check_and_load_text (Prism never persists paper
text) - same reuse as eval/replay_extract.py.

--estimate is a character-count-based proxy with ZERO network calls: pass-1
input/output chars from eval.replay_extract's measured constants and run-1
claim sizes, pass-2 input chars from the number of windows x (fixed pass-2
prompt chars + window size), pass-2 output chars from a flat per-window
assumption (stated in the printed output, since there is no prior pass-2 run
to measure it from).

A real run requires --max-inr; it is a hard stop driven by REAL measured
tokens (via cost_inr on this run's own instrumentation), not an estimate,
checked before every call (pass 1, then each pass-2 window call). The script
refuses to make any paid call without --max-inr.

Usage:
  uv run python -m eval.replay_exp3 --estimate --run-id dryrun1 --papers P1,P2
  uv run python -m eval.replay_exp3 --dry-run --run-id dryrun1 --papers P7
  uv run python -m eval.replay_exp3 --run-id pass2_r1 --papers P7 --max-inr 30   # pilot
  uv run python -m eval.replay_exp3 --run-id pilot2 --papers 2610.11135 --max-inr 30 \\
      --pass2-thinking-level low --pass1-from-fixture   # Experiment 3 amendment 1
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
from extraction.merge import merge_pass2_claims
from extraction.prompt_loader import build_gemini_messages_for_extractor
from extraction.prompt_version import get_prompt_version
from extraction.windowing import make_windows

REPO_ROOT = Path(__file__).parent.parent.parent
OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp3"

# Rough chars/4 proxy for --estimate's pass-1 leg (zero network calls) -
# measured the same way eval/replay_extract.py's _FIXED_PROMPT_CHARS was,
# for today's live settings.extractor_fewshot_fix/extractor_fewshot_shapes
# (both False in production today; this script does not override them for
# the pass-1 leg, only for enabling pass 2 itself).
_PASS1_FIXED_PROMPT_CHARS = 13_629
_PASS2_FIXED_PROMPT_CHARS_PER_WINDOW = 900  # system prompt chars, measured separately
# No pass-2 run exists yet to measure real output size from, so --estimate
# assumes a flat per-window output guess, stated explicitly in the printed
# estimate rather than silently baked in.
_PASS2_ASSUMED_OUTPUT_CHARS_PER_WINDOW = 450


@dataclass
class CallRecord:
    paper_id: str
    call_kind: str  # "pass1" or "pass2"
    model_used: str
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int
    total_tokens: int
    finish_reason: str | None
    latency_s: float


def _load_paper_ids(papers_filter: str | None) -> list[str]:
    paper_ids = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
    if papers_filter:
        wanted = {s.strip() for s in papers_filter.split(",")}
        paper_ids = [p for p in paper_ids if any(w in p for w in wanted)]
    return paper_ids


def _run1_claim_output_chars(paper_id: str) -> int:
    fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
    return sum(len(c["claim_text_verbatim"]) + len(c["claim_summary"]) for c in fixture["claims"])


class _Instrumentation:
    """Monkey-patches extraction.engine._generate_with_fallback for the
    duration of a `with` block, restoring the original in a finally clause
    even if a replayed call raises. Identical convention to
    eval/replay_audit.py's and eval/replay_extract.py's _Instrumentation,
    extended to also capture finish_reason via
    extraction.engine._extract_usage_and_finish_reason."""

    def __init__(self, out_dir: Path):
        self.records: list[CallRecord] = []
        self._original = None
        self._current_paper_id: str | None = None
        self._current_call_kind: str | None = None
        # Experiment 3 amendment 1: out_dir must already exist by the time
        # this is constructed (see _run_once's mkdir-at-top ordering) -
        # every call's record is appended here as it happens, so an abort or
        # crash mid-run (like the pilot 1 crash, docs/decisions.md) never
        # loses what was already spent.
        self._ndjson_path = out_dir / "_calls.ndjson"

    def set_context(self, paper_id: str, call_kind: str) -> None:
        self._current_paper_id = paper_id
        self._current_call_kind = call_kind

    async def _wrapped(self, client, contents, config, chat_id, model_name, fallback_model, correlation_id=None, fallback_config=None):
        start = time.monotonic()
        extra_kwargs = {"fallback_config": fallback_config} if fallback_config is not None else {}
        response, used_model = await self._original(
            client, contents, config, chat_id, model_name, fallback_model, correlation_id, **extra_kwargs,
        )
        latency = time.monotonic() - start
        usage, finish_reason = engine._extract_usage_and_finish_reason(response)
        record = CallRecord(
            paper_id=self._current_paper_id, call_kind=self._current_call_kind, model_used=used_model,
            prompt_tokens=(usage or {}).get("prompt_tokens") or 0,
            output_tokens=(usage or {}).get("output_tokens") or 0,
            thought_tokens=(usage or {}).get("thought_tokens") or 0,
            total_tokens=(usage or {}).get("total_tokens") or 0,
            finish_reason=finish_reason,
            latency_s=latency,
        )
        self.records.append(record)
        try:
            with self._ndjson_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.__dict__) + "\n")
        except OSError as exc:
            # A paid response must never be lost over a disk-write problem -
            # the in-memory record (self.records, above) already has it, and
            # _print_summary still writes it at the end of the run. This is
            # a visibility gap for a crash mid-run, not a lost call.
            print(f"[replay_exp3] WARNING: failed to append to {self._ndjson_path}: {exc!r}")
        return response, used_model

    def __enter__(self) -> "_Instrumentation":
        self._original = engine._generate_with_fallback
        engine._generate_with_fallback = self._wrapped
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        engine._generate_with_fallback = self._original


def _spent_so_far(instrumentation: "_Instrumentation") -> float:
    return sum(cost_inr(r.prompt_tokens, r.output_tokens, r.thought_tokens) for r in instrumentation.records)


async def _extract_pass1(paper_text: str) -> dict:
    from config import settings

    return await engine._call_gemini_json(
        messages=build_gemini_messages_for_extractor(paper_text),
        chat_id="replay-exp3-pass1",
        correlation_id=None,
        log_subdir="extraction",
        model_name=settings.llm_extraction_model,
        fallback_model=settings.llm_extraction_fallback_model,
    )


def _pass1_claims_from_fixture(run1_fixture: dict) -> list[dict]:
    """Experiment 3 amendment 1: reshapes dev run-1's own post-pipeline
    claims down to the plain {claim_text_verbatim, claim_summary} shape
    _extract_pass1's output is reduced to above - the shape merge.py and the
    rest of this script expect. Makes no LLM call. Config parity with
    today's flag-off path is a precondition, not checked here - see
    docs/decisions.md's "Experiment 3 amendment 1 - 2026-10-15" (run-1
    fixtures: prompt_hash cb3272cce551, model gemini-3.6-flash, matching
    today's flag-off path exactly)."""
    return [
        {"claim_text_verbatim": c["claim_text_verbatim"], "claim_summary": c["claim_summary"]}
        for c in run1_fixture["claims"]
    ]


def _print_rough_estimate(paper_ids: list[str]) -> None:
    total_low = total_high = 0.0
    for paper_id in paper_ids:
        avg_paper_chars = 93_283  # same Phase-0 measured average replay_extract.py uses
        pass1_input_tokens = _PASS1_FIXED_PROMPT_CHARS / 4 + avg_paper_chars / 4
        pass1_output_tokens = (
            _run1_claim_output_chars(paper_id) / 4 if (FIXTURE_DIR / f"{paper_id}.json").exists() else 2_000
        )

        n_windows = len(make_windows("x" * avg_paper_chars))
        pass2_input_tokens = n_windows * (_PASS2_FIXED_PROMPT_CHARS_PER_WINDOW + 6000) / 4
        pass2_output_tokens = n_windows * _PASS2_ASSUMED_OUTPUT_CHARS_PER_WINDOW / 4

        input_tokens = pass1_input_tokens + pass2_input_tokens
        output_tokens = pass1_output_tokens + pass2_output_tokens
        total_low += cost_inr(input_tokens, output_tokens)
        total_high += cost_inr(input_tokens * 1.8, output_tokens * 1.8)

    print(f"[replay_exp3] --estimate (character-count proxy, ZERO network calls): {len(paper_ids)} papers, "
          f"~{n_windows if paper_ids else 0} windows/paper assumed from a {avg_paper_chars}-char average paper")
    print(f"[replay_exp3] pass-2 output per window is an UNMEASURED ASSUMPTION "
          f"({_PASS2_ASSUMED_OUTPUT_CHARS_PER_WINDOW} chars/window) - no real pass-2 run exists yet to measure from")
    print(f"[replay_exp3] estimated cost: INR {total_low:.1f}-{total_high:.1f} (pass 1 + pass 2 combined, no thinking-token estimate)")


async def _run_once(
    paper_ids: list[str], run_id: str, dry_run: bool, max_inr: float | None,
    pass2_thinking_level: str | None = None, pass1_from_fixture: bool = False,
) -> tuple[Path, list[CallRecord]]:
    from config import settings

    out_dir = OUTPUT_ROOT / run_id
    # Experiment 3 amendment 1 (crash fix): out_dir must exist before
    # anything else, not only once a paper succeeds - the pilot 1 crash
    # (docs/decisions.md) happened because out_dir was never created when
    # every paper in the run was skipped, so _print_summary's write failed.
    out_dir.mkdir(parents=True, exist_ok=True)
    instrumentation = _Instrumentation(out_dir)

    with instrumentation:
        for paper_id in paper_ids:
            if dry_run:
                print(f"[replay_exp3] DRY-RUN {paper_id} run_id={run_id}")
                continue

            spent_so_far = _spent_so_far(instrumentation)
            if max_inr is not None and spent_so_far >= max_inr:
                print(f"[replay_exp3] ABORT before {paper_id}: spend so far INR {spent_so_far:.2f} >= --max-inr {max_inr}")
                break

            run1_fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
            paper_text = await _hash_check_and_load_text(paper_id, run1_fixture["header"])
            if paper_text is None:
                continue

            if pass1_from_fixture:
                pass1_claims = _pass1_claims_from_fixture(run1_fixture)
            else:
                instrumentation.set_context(paper_id, "pass1")
                extracted = await _extract_pass1(paper_text)
                pass1_claims = [
                    {"claim_text_verbatim": c.get("claim_text_verbatim", ""), "claim_summary": c.get("claim_summary", "")}
                    for c in extracted.get("claims", [])
                ]

            pass2_sentences: list[str] = []
            windows = make_windows(paper_text)
            failed_window_count = 0
            paper_incomplete = False
            for window in windows:
                spent_so_far = _spent_so_far(instrumentation)
                if max_inr is not None and spent_so_far >= max_inr:
                    print(f"[replay_exp3] ABORT mid-paper {paper_id}: spend so far INR {spent_so_far:.2f} >= --max-inr {max_inr}")
                    paper_incomplete = True
                    break
                instrumentation.set_context(paper_id, "pass2")
                from extraction.pass2 import SentenceListLLM
                from extraction.prompt_loader import build_gemini_messages_for_pass2

                try:
                    result = await engine._call_gemini_structured(
                        messages=build_gemini_messages_for_pass2(window),
                        response_schema=SentenceListLLM,
                        chat_id="replay-exp3-pass2",
                        correlation_id=None,
                        log_subdir="pass2",
                        model_name=settings.llm_extraction_model,
                        fallback_model=settings.llm_extraction_fallback_model,
                        thinking_level=pass2_thinking_level,
                    )
                except Exception as exc:
                    print(f"[replay_exp3] window failed for {paper_id}: {type(exc).__name__}: {exc}")
                    failed_window_count += 1
                    continue
                pass2_sentences.extend(result.sentences)

            if paper_incomplete:
                print(f"[replay_exp3] SKIPPED writing output for {paper_id}: stopped mid-paper by --max-inr")
                continue

            merge_result = merge_pass2_claims(pass1_claims, pass2_sentences, paper_text)

            header = {
                "paper_id": paper_id,
                "run_id": run_id,
                "prompt_hash": get_prompt_version(extractor_second_pass=True),
                "model_name": settings.llm_extraction_model,
                "extraction_run_id": run1_fixture["header"]["extraction_run_id"],
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "failed_window_count": failed_window_count,
                "incomplete": failed_window_count > 0,
            }
            (out_dir / f"{paper_id}_pass1.json").write_text(
                json.dumps({"header": header, "claims": pass1_claims}, indent=2), encoding="utf-8"
            )
            (out_dir / f"{paper_id}_pass2.json").write_text(
                json.dumps({"header": header, "sentences": pass2_sentences}, indent=2), encoding="utf-8"
            )
            (out_dir / f"{paper_id}_merged.json").write_text(
                json.dumps({"header": header, "claims": merge_result["merged_claims"]}, indent=2), encoding="utf-8"
            )
            (out_dir / f"{paper_id}_buckets.json").write_text(
                json.dumps({
                    "header": header,
                    "dropped_ungrounded": merge_result["dropped_ungrounded"],
                    "dropped_duplicate": merge_result["dropped_duplicate"],
                    "kept_but_contained": merge_result["kept_but_contained"],
                    "kept_new": merge_result["kept_new"],
                }, indent=2), encoding="utf-8"
            )
            print(f"[replay_exp3] wrote {paper_id} ({len(pass1_claims)} pass1, {len(pass2_sentences)} pass2 raw, "
                  f"{len(merge_result['merged_claims']) - len(pass1_claims)} pass2 kept, "
                  f"{failed_window_count} failed_window_count)")

    return out_dir, instrumentation.records


def _print_summary(out_dir: Path, records: list[CallRecord]) -> None:
    from config import settings

    total_prompt = sum(r.prompt_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_thought = sum(r.thought_tokens for r in records)
    cost = cost_inr(total_prompt, total_output, total_thought)
    non_stop_finish_reasons = [r.__dict__ for r in records if r.finish_reason not in (None, "STOP")]
    fallback_calls = sum(1 for r in records if r.model_used != settings.llm_extraction_model)
    summary = {
        "calls": len(records),
        "total_prompt_tokens": total_prompt,
        "total_output_tokens": total_output,
        "total_thought_tokens": total_thought,
        "cost_inr": round(cost, 2),
        "fallback_calls": fallback_calls,
        "non_stop_finish_reasons": non_stop_finish_reasons,
        "records": [r.__dict__ for r in records],
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[replay_exp3] {len(records)} calls, {total_prompt} prompt / {total_output} output / "
          f"{total_thought} thought tokens, ~INR {summary['cost_inr']}")
    print(f"[replay_exp3] {fallback_calls} call(s) used the fallback model")
    if non_stop_finish_reasons:
        print(f"[replay_exp3] WARNING: {len(non_stop_finish_reasons)} call(s) had a non-STOP finish_reason "
              "(possible truncation) - see _summary.json::non_stop_finish_reasons")


async def _main(args: argparse.Namespace) -> int:
    import os

    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)

    paper_ids = _load_paper_ids(args.papers)
    if not paper_ids:
        print("[replay_exp3] ABORT: no papers selected")
        return 1

    if args.estimate:
        _print_rough_estimate(paper_ids)
        return 0

    if not args.run_id:
        print("[replay_exp3] ABORT: --run-id is required for --dry-run and real runs")
        return 1

    if not args.dry_run and args.max_inr is None:
        print("[replay_exp3] ABORT: refuses to make paid calls without --max-inr")
        return 1

    out_dir, records = await _run_once(
        paper_ids, args.run_id, args.dry_run, args.max_inr,
        pass2_thinking_level=args.pass2_thinking_level, pass1_from_fixture=args.pass1_from_fixture,
    )
    if not args.dry_run:
        _print_summary(out_dir, records)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", help="output subdirectory name under docs/evals/fixtures/dev/exp3/")
    parser.add_argument("--papers", help="comma-separated paper_id substrings (omit for all run1 fixture papers)")
    parser.add_argument("--estimate", action="store_true", help="character-count proxy, zero network calls")
    parser.add_argument("--dry-run", action="store_true", help="print what would be replayed, zero LLM calls")
    parser.add_argument("--max-inr", type=float, default=None, help="REQUIRED for a real run: hard stop on real measured spend")
    from config import PASS2_THINKING_LEVELS

    parser.add_argument(
        "--pass2-thinking-level", default=None, choices=sorted(PASS2_THINKING_LEVELS),
        help="Experiment 3 amendment 1: thinking_level for pass-2 window calls, primary model only "
             "(minimal unverified for gemini-3.6-flash). Unset = no thinking_config, today's default.",
    )
    parser.add_argument(
        "--pass1-from-fixture", action="store_true",
        help="Experiment 3 amendment 1: load dev run-1's own pass-1 claims instead of making a fresh pass-1 call.",
    )
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
