"""CLI: replays the clean-extraction attempt's new pass-2 prompt + merge +
filter on Experiment 3's own frozen pass-1 outputs (docs/decisions.md's
"Clean-extraction attempt amended: new pass-2 prompt + filter - 2026-10-17").

Pass 1 is never called here: --pass1-run names an existing Experiment 3
replay directory under docs/evals/fixtures/dev/exp3/ (e.g. "pass2_r1"), and
this script reads that directory's own frozen `<paper>_pass1.json` files -
the exact {header, claims} shape eval/replay_exp3.py already wrote. Pass 2
is rerun with the NEW clean prompt (prompts/extract_claims_pass2_v2_system.md,
via extraction.prompt_loader.build_gemini_messages_for_pass2's
prompt_filename override), using the real, unmodified
extraction.engine._call_gemini_structured call path. Merge is the real,
unmodified extraction.merge.merge_pass2_claims - never reimplemented here.
The filter (extraction.pass2_clean.filter_merged_claims) runs after merge
unless --no-filter, which stops after merge so pre-filter counts can be
reported (the amended decision's "report pre-filter counts" requirement).

Paper text is re-derived from each paper's local PDF via
eval.replay_audit._hash_check_and_load_text, reusing the frozen pass-1
fixture's own header (same DB-lookup + sha256-pin convention
eval/replay_exp3.py uses) - this script never persists or re-extracts paper
text any other way.

--estimate makes REAL countTokens calls only (zero generateContent calls,
so zero paid tokens): one per pass-2 window, using the real new prompt and
real window text, plus one filter-batch countTokens call built from one
real candidate - a FROZEN exp3 run's own kept_new sentence, since no new
pass-2 output exists yet to build a real filter batch from. Output tokens
and the number of filter batches a real run will produce are UNMEASURED
ASSUMPTIONS, stated explicitly in the printed estimate, exactly as
eval/replay_exp3.py's own --estimate states its output-token assumption.

A real run (--run-id, no --dry-run) requires --max-inr: checked before
every pass-2 window call, and once more before the filter step starts (the
filter's own batch concurrency is internal to
extraction.pass2_clean.filter_merged_claims, so --max-inr is not re-checked
between individual filter batches within one paper - acceptable here since
a paper's filter batches are few, at most ceil(candidates / 60), and every
real run this script is used for (pilot, then full runs) is pre-registered
with a small --max-inr). A window call that raises (after
extraction.engine's own retry/fallback is exhausted) is logged and skipped,
not fatal to the paper - mirrors extraction/pass2.py's own non-fatal-window
handling. If --max-inr stops a run mid-paper, that paper's output files are
not written at all, matching eval/replay_exp3.py.

Writes <paper>_pass1.json (copied through unchanged from --pass1-run),
<paper>_pass2.json, <paper>_merged.json, <paper>_buckets.json (same shapes
as eval/replay_exp3.py), plus <paper>_clean.json (filter decisions, omitted
when --no-filter) and <paper>_filtered.json (the final claims list) under a
NEW --run-id subdirectory of OUTPUT_ROOT below - never under
docs/evals/fixtures/dev/exp3/, so Experiment 3's own outputs are never
touched or overwritten.

Usage:
  uv run python -m eval.replay_clean --estimate --pass1-run pass2_r1 --papers 2610.10590
  uv run python -m eval.replay_clean --dry-run --run-id dryrun1 --pass1-run pass2_r1
  uv run python -m eval.replay_clean --run-id clean_pilot --pass1-run pass2_r1 \\
      --papers 2610.10590 --max-inr 15
  uv run python -m eval.replay_clean --run-id clean_r1 --pass1-run pass2_r1 --max-inr 85
  uv run python -m eval.replay_clean --run-id clean_r1_nofilter --pass1-run pass2_r1 \\
      --max-inr 85 --no-filter
"""
import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

from eval.pricing import cost_inr
from eval.replay_audit import _hash_check_and_load_text
from extraction import engine
from extraction.merge import merge_pass2_claims
from extraction.pass2_clean import BATCH_SIZE, filter_merged_claims
from extraction.prompt_loader import build_gemini_messages_for_pass2, build_gemini_messages_for_pass2_clean_filter
from extraction.prompt_version import get_prompt_version
from extraction.windowing import make_windows

REPO_ROOT = Path(__file__).parent.parent.parent
EXP3_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp3"
OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "clean"

CLEAN_PASS2_PROMPT_FILENAME = "extract_claims_pass2_v2_system.md"


@dataclass
class CallRecord:
    paper_id: str
    call_kind: str  # "pass2" or "filter"
    model_used: str
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int
    total_tokens: int
    finish_reason: str | None
    latency_s: float


def _load_paper_ids(pass1_run_dir: Path, papers_filter: str | None) -> list[str]:
    paper_ids = sorted(p.stem[: -len("_pass1")] for p in pass1_run_dir.glob("*_pass1.json"))
    if papers_filter:
        wanted = {s.strip() for s in papers_filter.split(",")}
        paper_ids = [p for p in paper_ids if any(w in p for w in wanted)]
    return paper_ids


def _load_pass1_fixture(pass1_run_dir: Path, paper_id: str) -> dict:
    return json.loads((pass1_run_dir / f"{paper_id}_pass1.json").read_text(encoding="utf-8"))


class _Instrumentation:
    """Monkey-patches extraction.engine._generate_with_fallback for the
    duration of a `with` block, restoring the original in a finally clause
    even if a replayed call raises. Same convention as
    eval/replay_exp3.py's own _Instrumentation."""

    def __init__(self, out_dir: Path):
        self.records: list[CallRecord] = []
        self._original = None
        self._current_paper_id: str | None = None
        self._current_call_kind: str | None = None
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
            print(f"[replay_clean] WARNING: failed to append to {self._ndjson_path}: {exc!r}")
        return response, used_model

    def __enter__(self) -> "_Instrumentation":
        self._original = engine._generate_with_fallback
        engine._generate_with_fallback = self._wrapped
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        engine._generate_with_fallback = self._original


def _spent_so_far(instrumentation: "_Instrumentation") -> float:
    return sum(cost_inr(r.prompt_tokens, r.output_tokens, r.thought_tokens) for r in instrumentation.records)


async def _estimate_tokens(messages: list[dict]) -> int:
    """Real countTokens call (zero generateContent calls, zero paid
    tokens) for one message list, mirroring extraction.engine's own
    system/contents translation.

    The Gemini Developer API's countTokens does not accept a system
    instruction in its config (CountTokensConfig's system_instruction is a
    Vertex-only field - raises "system_instruction parameter is not
    supported in Gemini API"). Fold the system prompt in as a plain content
    entry instead, same as eval/replay_extract.py's own
    _print_count_tokens_estimate; countTokens sums all content tokens
    regardless of role, so this is still an accurate count, just not routed
    through the config field the real generateContent call
    (extraction.engine._call_gemini_structured) actually uses."""
    client = engine._build_client()
    system_prompt = engine._extract_system_prompt(messages)
    from config import settings
    from google.genai import types

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=system_prompt)])] + engine._to_gemini_contents(messages)

    result = await client.aio.models.count_tokens(
        model=settings.llm_extraction_model,
        contents=contents,
    )
    return result.total_tokens or 0


async def _print_estimate(pass1_run_dir: Path, paper_ids: list[str]) -> None:
    from config import settings

    _PASS2_ASSUMED_OUTPUT_TOKENS_PER_WINDOW = 150  # unmeasured - no real clean pass-2 run exists yet
    _FILTER_ASSUMED_OUTPUT_TOKENS_PER_ITEM = 80  # unmeasured - no real filter run exists yet

    total_pass2_input = 0
    total_pass2_windows = 0
    sample_filter_input: int | None = None
    sample_filter_items = 0

    for paper_id in paper_ids:
        fixture = _load_pass1_fixture(pass1_run_dir, paper_id)
        paper_text = await _hash_check_and_load_text(paper_id, fixture["header"])
        if paper_text is None:
            print(f"[replay_clean] --estimate: SKIPPED {paper_id} (paper text unavailable)")
            continue
        windows = make_windows(paper_text)
        total_pass2_windows += len(windows)
        for window in windows:
            messages = build_gemini_messages_for_pass2(window, prompt_filename=CLEAN_PASS2_PROMPT_FILENAME)
            total_pass2_input += await _estimate_tokens(messages)

        if sample_filter_input is None:
            buckets_path = EXP3_ROOT / "pass2_r1" / f"{paper_id}_buckets.json"
            if buckets_path.exists():
                buckets = json.loads(buckets_path.read_text(encoding="utf-8"))
                kept_new = buckets.get("kept_new", [])
                if kept_new:
                    sample_items = kept_new[: min(BATCH_SIZE, len(kept_new))]
                    sample_filter_items = len(sample_items)
                    batch_payload = [
                        {"id": f"P{i}", "candidate": item["sentence"], "context": None, "neighbours": []}
                        for i, item in enumerate(sample_items)
                    ]
                    messages = build_gemini_messages_for_pass2_clean_filter(batch_payload)
                    sample_filter_input = await _estimate_tokens(messages)

    pass2_output = total_pass2_windows * _PASS2_ASSUMED_OUTPUT_TOKENS_PER_WINDOW
    pass2_cost = cost_inr(total_pass2_input, pass2_output)

    print(f"[replay_clean] --estimate (REAL countTokens, ZERO generateContent calls): "
          f"{len(paper_ids)} papers, {total_pass2_windows} pass-2 windows")
    print(f"[replay_clean] pass-2: {total_pass2_input} real input tokens, "
          f"{pass2_output} ASSUMED output tokens ({_PASS2_ASSUMED_OUTPUT_TOKENS_PER_WINDOW}/window, unmeasured) "
          f"-> ~INR {pass2_cost:.1f}")

    if sample_filter_input is not None:
        filter_output = sample_filter_items * _FILTER_ASSUMED_OUTPUT_TOKENS_PER_ITEM
        filter_cost_per_batch = cost_inr(sample_filter_input, filter_output)
        print(f"[replay_clean] filter (sample batch of {sample_filter_items} candidates from a frozen "
              f"exp3 kept_new bucket, no context/neighbours - a real batch will cost MORE): "
              f"{sample_filter_input} real input tokens, {filter_output} ASSUMED output tokens "
              f"({_FILTER_ASSUMED_OUTPUT_TOKENS_PER_ITEM}/item, unmeasured) -> ~INR {filter_cost_per_batch:.1f} "
              f"per batch of up to {BATCH_SIZE}")
    else:
        print("[replay_clean] filter: no sample batch available (no frozen exp3 kept_new bucket found) - "
              "filter cost not estimated")

    print(f"[replay_clean] settings.llm_extraction_model={settings.llm_extraction_model}")


async def _run_once(
    pass1_run_dir: Path, paper_ids: list[str], run_id: str, dry_run: bool, max_inr: float | None,
    no_filter: bool, pass2_thinking_level: str | None,
) -> tuple[Path, list[CallRecord]]:
    from config import settings

    out_dir = OUTPUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    instrumentation = _Instrumentation(out_dir)

    with instrumentation:
        for paper_id in paper_ids:
            if dry_run:
                print(f"[replay_clean] DRY-RUN {paper_id} run_id={run_id}")
                continue

            spent_so_far = _spent_so_far(instrumentation)
            if max_inr is not None and spent_so_far >= max_inr:
                print(f"[replay_clean] ABORT before {paper_id}: spend so far INR {spent_so_far:.2f} >= --max-inr {max_inr}")
                break

            pass1_fixture = _load_pass1_fixture(pass1_run_dir, paper_id)
            pass1_claims = pass1_fixture["claims"]
            paper_text = await _hash_check_and_load_text(paper_id, pass1_fixture["header"])
            if paper_text is None:
                continue

            pass2_sentences: list[str] = []
            windows = make_windows(paper_text)
            failed_window_count = 0
            paper_incomplete = False
            for window in windows:
                spent_so_far = _spent_so_far(instrumentation)
                if max_inr is not None and spent_so_far >= max_inr:
                    print(f"[replay_clean] ABORT mid-paper {paper_id}: spend so far INR {spent_so_far:.2f} >= --max-inr {max_inr}")
                    paper_incomplete = True
                    break
                instrumentation.set_context(paper_id, "pass2")
                from extraction.pass2 import SentenceListLLM

                try:
                    result = await engine._call_gemini_structured(
                        messages=build_gemini_messages_for_pass2(window, prompt_filename=CLEAN_PASS2_PROMPT_FILENAME),
                        response_schema=SentenceListLLM,
                        chat_id="replay-clean-pass2",
                        correlation_id=None,
                        log_subdir="pass2",
                        model_name=settings.llm_extraction_model,
                        fallback_model=settings.llm_extraction_fallback_model,
                        thinking_level=pass2_thinking_level,
                    )
                except Exception as exc:
                    print(f"[replay_clean] window failed for {paper_id}: {type(exc).__name__}: {exc}")
                    failed_window_count += 1
                    continue
                pass2_sentences.extend(result.sentences)

            if paper_incomplete:
                print(f"[replay_clean] SKIPPED writing output for {paper_id}: stopped mid-paper by --max-inr")
                continue

            merge_result = merge_pass2_claims(pass1_claims, pass2_sentences, paper_text)
            pre_filter_claims = merge_result["merged_claims"]

            filter_result = None
            if not no_filter:
                spent_so_far = _spent_so_far(instrumentation)
                if max_inr is not None and spent_so_far >= max_inr:
                    print(f"[replay_clean] SKIPPED filter for {paper_id}: spend so far INR {spent_so_far:.2f} >= --max-inr {max_inr}")
                else:
                    instrumentation.set_context(paper_id, "filter")
                    filter_result = await filter_merged_claims(
                        pre_filter_claims, paper_text, "replay-clean-filter", None,
                        thinking_level=pass2_thinking_level,
                    )

            final_claims = filter_result["filtered_claims"] if filter_result is not None else pre_filter_claims

            header = {
                "paper_id": paper_id,
                "run_id": run_id,
                "pass1_run": pass1_run_dir.name,
                "prompt_hash": get_prompt_version(extractor_second_pass=True, extractor_pass2_clean=True),
                "model_name": settings.llm_extraction_model,
                "extraction_run_id": pass1_fixture["header"]["extraction_run_id"],
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "failed_window_count": failed_window_count,
                "no_filter": no_filter,
                "incomplete": failed_window_count > 0 or (filter_result is not None and filter_result["incomplete"]),
            }
            (out_dir / f"{paper_id}_pass1.json").write_text(
                json.dumps({"header": header, "claims": pass1_claims}, indent=2), encoding="utf-8"
            )
            (out_dir / f"{paper_id}_pass2.json").write_text(
                json.dumps({"header": header, "sentences": pass2_sentences}, indent=2), encoding="utf-8"
            )
            (out_dir / f"{paper_id}_merged.json").write_text(
                json.dumps({"header": header, "claims": pre_filter_claims}, indent=2), encoding="utf-8"
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
            (out_dir / f"{paper_id}_filtered.json").write_text(
                json.dumps({"header": header, "claims": final_claims}, indent=2), encoding="utf-8"
            )
            if filter_result is not None:
                (out_dir / f"{paper_id}_clean.json").write_text(
                    json.dumps({"header": header, "decisions": filter_result["decisions"]}, indent=2), encoding="utf-8"
                )
            print(
                f"[replay_clean] wrote {paper_id} ({len(pass1_claims)} pass1, {len(pass2_sentences)} pass2 raw, "
                f"{len(pre_filter_claims) - len(pass1_claims)} pre-filter pass2 kept, "
                f"{len(final_claims) - len(pass1_claims)} post-filter pass2 kept, "
                f"{failed_window_count} failed_window_count)"
            )

    return out_dir, instrumentation.records


def _print_summary(out_dir: Path, records: list[CallRecord]) -> None:
    from config import settings

    total_prompt = sum(r.prompt_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_thought = sum(r.thought_tokens for r in records)
    cost = cost_inr(total_prompt, total_output, total_thought)
    non_stop_finish_reasons = [r.__dict__ for r in records if r.finish_reason not in (None, "STOP")]
    fallback_calls = sum(1 for r in records if r.model_used != settings.llm_extraction_model)
    pass2_cost = cost_inr(
        sum(r.prompt_tokens for r in records if r.call_kind == "pass2"),
        sum(r.output_tokens for r in records if r.call_kind == "pass2"),
        sum(r.thought_tokens for r in records if r.call_kind == "pass2"),
    )
    filter_cost = cost_inr(
        sum(r.prompt_tokens for r in records if r.call_kind == "filter"),
        sum(r.output_tokens for r in records if r.call_kind == "filter"),
        sum(r.thought_tokens for r in records if r.call_kind == "filter"),
    )
    summary = {
        "calls": len(records),
        "total_prompt_tokens": total_prompt,
        "total_output_tokens": total_output,
        "total_thought_tokens": total_thought,
        "cost_inr": round(cost, 2),
        "pass2_cost_inr": round(pass2_cost, 2),
        "filter_cost_inr": round(filter_cost, 2),
        "fallback_calls": fallback_calls,
        "non_stop_finish_reasons": non_stop_finish_reasons,
        "records": [r.__dict__ for r in records],
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[replay_clean] {len(records)} calls, {total_prompt} prompt / {total_output} output / "
          f"{total_thought} thought tokens, ~INR {summary['cost_inr']} "
          f"(pass2 ~INR {summary['pass2_cost_inr']}, filter ~INR {summary['filter_cost_inr']})")
    print(f"[replay_clean] {fallback_calls} call(s) used the fallback model")
    if non_stop_finish_reasons:
        print(f"[replay_clean] WARNING: {len(non_stop_finish_reasons)} call(s) had a non-STOP finish_reason "
              "(possible truncation) - see _summary.json::non_stop_finish_reasons")


async def _main(args: argparse.Namespace) -> int:
    import os

    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)

    pass1_run_dir = EXP3_ROOT / args.pass1_run
    if not pass1_run_dir.exists():
        print(f"[replay_clean] ABORT: --pass1-run directory not found: {pass1_run_dir}")
        return 1

    paper_ids = _load_paper_ids(pass1_run_dir, args.papers)
    if not paper_ids:
        print("[replay_clean] ABORT: no papers selected")
        return 1

    if args.estimate:
        await _print_estimate(pass1_run_dir, paper_ids)
        return 0

    if not args.run_id:
        print("[replay_clean] ABORT: --run-id is required for --dry-run and real runs")
        return 1

    if not args.dry_run and args.max_inr is None:
        print("[replay_clean] ABORT: refuses to make paid calls without --max-inr")
        return 1

    out_dir, records = await _run_once(
        pass1_run_dir, paper_ids, args.run_id, args.dry_run, args.max_inr,
        args.no_filter, args.pass2_thinking_level,
    )
    if not args.dry_run:
        _print_summary(out_dir, records)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pass1-run", required=True,
                         help="Experiment 3 replay subdirectory under docs/evals/fixtures/dev/exp3/ "
                              "to reuse frozen pass-1 claims from (e.g. pass2_r1)")
    parser.add_argument("--run-id", help="output subdirectory name under docs/evals/fixtures/dev/clean/")
    parser.add_argument("--papers", help="comma-separated paper_id substrings (omit for all papers in --pass1-run)")
    parser.add_argument("--estimate", action="store_true", help="real countTokens calls only, zero generateContent calls")
    parser.add_argument("--dry-run", action="store_true", help="print what would be replayed, zero LLM calls")
    parser.add_argument("--max-inr", type=float, default=None, help="REQUIRED for a real run: hard stop on real measured spend")
    parser.add_argument("--no-filter", action="store_true", help="run pass 2 + merge only; skip the filter (report pre-filter counts)")
    from config import PASS2_THINKING_LEVELS

    parser.add_argument(
        "--pass2-thinking-level", default=None, choices=sorted(PASS2_THINKING_LEVELS),
        help="thinking_level for both pass-2 window calls and filter batch calls, primary model only. "
             "Unset = no thinking_config, today's default.",
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
