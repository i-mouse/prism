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

Paper text is read from the local cache, scratch/auditor_rd/raw_text_cache/
<paper id without a leading "arxiv-">.txt (arxiv-2610.10590v1 ->
2610.10590v1.txt). Only paper ids that have a run1 dev fixture can be loaded.
A missing file aborts the run before the first paid call; there is no
fallback to Postgres or the PDF, and this module never imports memory_db.

Preflight aborts the whole run if the current prompt files do not hash to
cb3272cce551 (frozen for the dev baseline / Experiment 1).

Zero LLM calls under --estimate or --dry-run.

--max-inr N caps the running cost (priced Gemini calls + grounding calls) for
the whole invocation. When it is exceeded no further call is issued, the
partial summary is written with status VOID_CAP_HIT and the exit code is 2.

Usage:
  uv run python -m eval.replay_audit --estimate --level high --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --dry-run  --level high --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --level high   --claims docs/evals/exp1_stage_a_claims.json --repeat 3 --max-inr 100
  uv run python -m eval.replay_audit --level medium --claims docs/evals/exp1_stage_a_claims.json --repeat 2
  uv run python -m eval.replay_audit --level high                                   # Stage B: all 12 papers, repeat 1
"""
import argparse
import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from eval.legacy_paper_text import PDF_DIR, _hash_check_and_load_text  # noqa: F401 - re-exported for replay_exp3/replay_clean/replay_extract; unused here
from eval.pricing import INR_PER_USD, USD_PER_1M_INPUT, USD_PER_1M_OUTPUT, cost_usd, cost_usd_for_model
from extraction import engine, grounding
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLLM, ClaimsExtractionResponse

REPO_ROOT = Path(__file__).parent.parent.parent
SERVICE_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev"
LOGS_DIR = SERVICE_ROOT / "logs" / "eval"
RAW_TEXT_CACHE_DIR = SERVICE_ROOT / "scratch" / "auditor_rd" / "raw_text_cache"

EXPECTED_PROMPT_HASH = "cb3272cce551"

_ARXIV_PREFIX = "arxiv-"
STATUS_OK = "OK"
STATUS_VOID_CAP_HIT = "VOID_CAP_HIT"
EXIT_CAP_HIT = 2


class PaperTextError(Exception):
    """A paper's cached text cannot be loaded (bad id, missing or empty file)."""


class CapExceeded(BaseException):
    """Raised when the running cost passes --max-inr.

    A BaseException on purpose: the retry loops around the instrumented calls
    (engine._call_gemini, grounding._call_litellm_audit and the usage observer
    guard) all use `except Exception`, which a BaseException subclass passes
    straight through, so a cap stop is never retried or swallowed.
    """


@dataclass
class CallRecord:
    stage: str  # "audit" or "structure"
    paper_id: str
    claim_index: int
    thinking_level: str | None
    model_used: str | None  # the served model name returned by _generate_with_fallback
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int
    total_tokens: int
    latency_s: float
    cached_tokens: int = 0
    tool_use_tokens: int = 0


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


_HIGH_THOUGHT_MULTIPLIER_RANGE = (2.0, 4.0)

# Fallback measured averages if the medium-arm summaries below aren't present
# (e.g. a fresh checkout). Measured from Experiment 1 Stage A control
# (exp1_medium_1 + exp1_medium_2, 18 claims x 2 repeats = 36 claim-replays),
# docs/decisions.md 2026-10-12 "amendment after control arm" - chars/4 plus
# flat overhead constants undercounted this academic-PDF content by ~1.8x
# (see that entry), so this --estimate now uses real measured tokens instead.
_FALLBACK_MEASURED_STATS = {
    "audit_prompt": 37389, "audit_output": 345, "audit_thought_medium": 2279,
    "struct_prompt": 1386, "struct_output": 259, "struct_thought": 852,
}
_MEASURED_SUMMARY_DIRS = (
    OUTPUT_ROOT / "exp1_medium_1" / "_summary.json",
    OUTPUT_ROOT / "exp1_medium_2" / "_summary.json",
)


def _load_measured_token_stats() -> dict[str, float]:
    """Averages real per-call token counts from the Stage A medium-arm
    summaries (paired even/odd records = audit/structure calls, per
    _replay_claim's fixed call order). Falls back to _FALLBACK_MEASURED_STATS,
    documented above, if those summary files aren't on disk."""
    audit_prompt = audit_output = audit_thought = 0
    struct_prompt = struct_output = struct_thought = 0
    n = 0

    for summary_path in _MEASURED_SUMMARY_DIRS:
        if not summary_path.exists():
            continue
        records = json.loads(summary_path.read_text(encoding="utf-8"))["records"]
        for i in range(0, len(records) - 1, 2):
            audit, struct = records[i], records[i + 1]
            audit_prompt += audit["prompt_tokens"]; audit_output += audit["output_tokens"]; audit_thought += audit["thought_tokens"]
            struct_prompt += struct["prompt_tokens"]; struct_output += struct["output_tokens"]; struct_thought += struct["thought_tokens"]
            n += 1

    if n == 0:
        print("[replay_audit] --estimate: no Stage A medium-arm summaries found on disk, using documented fallback measured averages")
        return dict(_FALLBACK_MEASURED_STATS)

    return {
        "audit_prompt": audit_prompt / n, "audit_output": audit_output / n, "audit_thought_medium": audit_thought / n,
        "struct_prompt": struct_prompt / n, "struct_output": struct_output / n, "struct_thought": struct_thought / n,
    }


def _estimate_one_claim_cost_usd(stats: dict[str, float], level: str) -> tuple[float, float]:
    """Returns (low, high) USD estimate for one audit+structure replay of one
    claim, using measured token averages. Only the audit call's thought
    tokens vary with thinking_level (scaled by _HIGH_THOUGHT_MULTIPLIER_RANGE
    for "high"); the structurer call never receives a thinking_config, so its
    thought tokens (the API's own default) are held at the measured medium
    average regardless of level - that assumption is unverified for "high"
    and could itself be an underestimate."""
    if level == "high":
        thought_low = stats["audit_thought_medium"] * _HIGH_THOUGHT_MULTIPLIER_RANGE[0]
        thought_high = stats["audit_thought_medium"] * _HIGH_THOUGHT_MULTIPLIER_RANGE[1]
    else:
        thought_low = thought_high = stats["audit_thought_medium"]

    def _cost(audit_thought_tokens: float) -> float:
        input_cost = (stats["audit_prompt"] + stats["struct_prompt"]) / 1e6 * USD_PER_1M_INPUT
        output_cost = (
            (stats["audit_output"] + audit_thought_tokens + stats["struct_output"] + stats["struct_thought"])
            / 1e6 * USD_PER_1M_OUTPUT
        )
        return input_cost + output_cost

    return _cost(thought_low), _cost(thought_high)


def _cache_file_name(paper_id: str) -> str:
    """Fixture stem -> cache file name: one leading "arxiv-" is dropped, ".txt"
    is appended (arxiv-2610.10590v1 -> 2610.10590v1.txt). A stem without the
    prefix is used as is."""
    stem = paper_id[len(_ARXIV_PREFIX):] if paper_id.startswith(_ARXIV_PREFIX) else paper_id
    return f"{stem}.txt"


def _check_dev_paper_id(paper_id: str) -> None:
    """Only a plain id that has a run1 dev fixture may be loaded, so a path or
    a held-out/sealed paper id can never reach the cache lookup."""
    if not paper_id or paper_id in {".", ".."} or "/" in paper_id or "\\" in paper_id:
        raise PaperTextError(f"{paper_id!r} is not a plain paper id")
    if not (FIXTURE_DIR / f"{paper_id}.json").is_file():
        raise PaperTextError(f"{paper_id}: not a run1 dev fixture id, refusing to load its text")


def _load_paper_text(paper_id: str) -> str:
    _check_dev_paper_id(paper_id)
    path = RAW_TEXT_CACHE_DIR / _cache_file_name(paper_id)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PaperTextError(f"{paper_id}: no cached paper text at {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise PaperTextError(f"{paper_id}: cannot read cached paper text at {path}: {exc!r}") from exc
    if not text.strip():
        raise PaperTextError(f"{paper_id}: cached paper text at {path} is empty")
    return text


def _load_paper_texts(paper_ids: list[str]) -> dict[str, str]:
    return {paper_id: _load_paper_text(paper_id) for paper_id in paper_ids}


def _gemini_record_cost_usd(record: CallRecord) -> tuple[float, bool]:
    """Returns (usd, priced_at_own_model_rate). A record whose model is missing
    or not in the rate table is priced at gemini-3.6-flash rates, which is an
    upper bound for the cap, and reported as not priced at its own rate."""
    usd = None
    if record.model_used:
        usd = cost_usd_for_model(
            record.model_used, record.prompt_tokens, record.output_tokens,
            record.thought_tokens, record.cached_tokens, record.tool_use_tokens,
        )
    if usd is not None:
        return usd, True
    flash_usd = cost_usd(
        record.prompt_tokens, record.output_tokens, record.thought_tokens,
        record.cached_tokens, record.tool_use_tokens,
    )
    return flash_usd, False


def _grounding_record_cost_usd(rec: dict) -> float:
    """USD for one grounding usage dict. thought is not passed (LiteLLM's
    completion_tokens already includes reasoning). A model missing from the
    rate table is charged at gemini-3.6-flash rates, an upper bound used only
    for the running cap."""
    prompt, output, cached = rec.get("prompt_tokens") or 0, rec.get("output_tokens") or 0, rec.get("cached_tokens") or 0
    usd = cost_usd_for_model(rec.get("model") or "", prompt, output, thought=0.0, cached=cached)
    return usd if usd is not None else cost_usd(prompt, output, 0.0, cached)


class _CostGuard:
    """Running cost for one invocation (shared by every --repeat run), and the
    --max-inr cap. max_inr None tracks cost but never raises."""

    def __init__(self, max_inr: float | None = None):
        self.max_inr = max_inr
        self.running_usd = 0.0
        self.max_single_call_usd = 0.0
        self.cap_hit = False

    @property
    def running_inr(self) -> float:
        return self.running_usd * INR_PER_USD

    @property
    def overshoot_inr(self) -> float:
        return max(0.0, self.running_inr - self.max_inr) if self.max_inr is not None else 0.0

    @property
    def max_single_call_inr(self) -> float:
        return self.max_single_call_usd * INR_PER_USD

    def check_before_call(self) -> None:
        if self.cap_hit:
            raise CapExceeded(f"cap of INR {self.max_inr} already exceeded; no further calls")

    def charge(self, usd: float) -> None:
        self.running_usd += usd
        self.max_single_call_usd = max(self.max_single_call_usd, usd)
        if self.max_inr is not None and self.running_inr > self.max_inr:
            self.cap_hit = True
            raise CapExceeded(f"running cost INR {self.running_inr:.2f} exceeded the cap of INR {self.max_inr}")


class _Instrumentation:
    """Monkey-patches extraction.engine._generate_with_fallback for the
    duration of a `with` block, restoring the original in a finally clause
    even if a replayed call raises. Records one CallRecord per Gemini call.

    Also sets extraction.grounding._usage_observer for the same duration, to
    collect one usage dict per grounding (LiteLLM) response in
    grounding_records. Kept apart from records: _load_measured_token_stats
    pairs records even/odd as audit/structure calls.

    With a guard, every call is charged as it completes and CapExceeded is
    raised once the cap is passed. A pre-call check on both patched entry
    points (and grounding._call_litellm_audit, patched only when a guard is
    given) stops any further request after that. grounding.py and engine.py
    themselves are untouched."""

    def __init__(self, guard: _CostGuard | None = None):
        self.guard = guard
        self.records: list[CallRecord] = []
        self.grounding_records: list[dict] = []
        self._original = None
        self._original_observer = None
        self._original_audit_call = None
        self._current_stage: str | None = None
        self._current_paper_id: str | None = None
        self._current_claim_index: int | None = None
        self._current_thinking_level: str | None = None

    def set_context(self, stage: str, paper_id: str, claim_index: int, thinking_level: str | None) -> None:
        self._current_stage = stage
        self._current_paper_id = paper_id
        self._current_claim_index = claim_index
        self._current_thinking_level = thinking_level

    def raise_if_capped(self) -> None:
        if self.guard is not None:
            self.guard.check_before_call()

    async def _wrapped(self, client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        self.raise_if_capped()
        start = time.monotonic()
        response, used_model = await self._original(client, contents, config, chat_id, model_name, fallback_model, correlation_id)
        latency = time.monotonic() - start
        usage = getattr(response, "usage_metadata", None)
        record = CallRecord(
            stage=self._current_stage, paper_id=self._current_paper_id, claim_index=self._current_claim_index,
            thinking_level=self._current_thinking_level, model_used=used_model,
            prompt_tokens=getattr(usage, "prompt_token_count", None) or 0,
            output_tokens=getattr(usage, "candidates_token_count", None) or 0,
            thought_tokens=getattr(usage, "thoughts_token_count", None) or 0,
            total_tokens=getattr(usage, "total_token_count", None) or 0,
            latency_s=latency,
            cached_tokens=getattr(usage, "cached_content_token_count", None) or 0,
            tool_use_tokens=getattr(usage, "tool_use_prompt_token_count", None) or 0,
        )
        self.records.append(record)
        if self.guard is not None:
            self.guard.charge(_gemini_record_cost_usd(record)[0])
        return response, used_model

    def _observe_grounding(self, usage: dict) -> None:
        self.grounding_records.append(usage)
        if self.guard is not None:
            self.guard.charge(_grounding_record_cost_usd(usage))

    async def _guarded_audit_call(self, *args, **kwargs):
        self.raise_if_capped()
        return await self._original_audit_call(*args, **kwargs)

    def __enter__(self) -> "_Instrumentation":
        self._original = engine._generate_with_fallback
        self._original_observer = grounding._usage_observer
        self._original_audit_call = grounding._call_litellm_audit
        engine._generate_with_fallback = self._wrapped
        grounding._usage_observer = self._observe_grounding
        if self.guard is not None:
            grounding._call_litellm_audit = self._guarded_audit_call
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        engine._generate_with_fallback = self._original
        grounding._usage_observer = self._original_observer
        grounding._call_litellm_audit = self._original_audit_call


async def _cancel_stray_tasks(preexisting: set[asyncio.Task]) -> None:
    """ground_extraction's gather re-raises the first failure but leaves the
    other span tasks running; cancel and drain them so no request is issued
    after a cap stop."""
    current = asyncio.current_task()
    strays = [t for t in asyncio.all_tasks() if t is not current and t not in preexisting]
    for task in strays:
        task.cancel()
    if strays:
        await asyncio.gather(*strays, return_exceptions=True)


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
    paper_texts: dict[str, str] | None = None, guard: _CostGuard | None = None,
) -> tuple[Path, list[CallRecord], list[dict], str]:
    """Returns (out_dir, gemini records, grounding records, status). status is
    STATUS_VOID_CAP_HIT when the guard's cap stopped the run; the run is then
    void and nothing further is issued."""
    out_dir = OUTPUT_ROOT / f"exp1_{level}_{repeat_index}"
    by_paper: dict[str, list[ReplayTarget]] = defaultdict(list)
    for t in targets:
        by_paper[t.paper_id].append(t)

    instrumentation = _Instrumentation(guard)
    preexisting_tasks = asyncio.all_tasks()
    status = STATUS_OK

    with instrumentation:
        try:
            for paper_id, paper_targets in sorted(by_paper.items()):
                run1_fixture = json.loads((FIXTURE_DIR / f"{paper_id}.json").read_text(encoding="utf-8"))
                if dry_run:
                    print(f"[replay_audit] DRY-RUN {paper_id} repeat={repeat_index} level={level} "
                          f"claims={[t.claim_index for t in paper_targets]}")
                    continue

                paper_text = paper_texts[paper_id]

                audited: list[ClaimLLM] = []
                for target in paper_targets:
                    instrumentation.raise_if_capped()
                    claim_llm = await _replay_claim(target, paper_text, level, instrumentation)
                    audited.append(claim_llm)

                instrumentation.raise_if_capped()
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
                print(f"[replay_audit] wrote {out_dir / f'{paper_id}.json'} ({len(claims_out)} claims)")
        except CapExceeded:
            status = STATUS_VOID_CAP_HIT
            await _cancel_stray_tasks(preexisting_tasks)

    return out_dir, instrumentation.records, instrumentation.grounding_records, status


def _print_estimate(targets: list[ReplayTarget], level: str, repeats: int) -> None:
    stats = _load_measured_token_stats()
    low, high = _estimate_one_claim_cost_usd(stats, level)
    total_low = low * len(targets) * repeats
    total_high = high * len(targets) * repeats

    calls = len(targets) * repeats * 2  # audit + structure per claim-replay
    print(f"[replay_audit] --estimate: {len(targets)} claims x {repeats} repeats = {len(targets) * repeats} claim-replays "
          f"({calls} Gemini calls, grounding calls not included - approximate, see module docstring/cost caveats)")
    print(f"[replay_audit] measured token averages used: audit prompt={stats['audit_prompt']:.0f} "
          f"output={stats['audit_output']:.0f} thought(medium)={stats['audit_thought_medium']:.0f}  "
          f"structure prompt={stats['struct_prompt']:.0f} output={stats['struct_output']:.0f} thought={stats['struct_thought']:.0f}")
    print(f"[replay_audit] estimated cost: USD {total_low:.3f}-{total_high:.3f} "
          f"(INR {total_low * INR_PER_USD:.1f}-{total_high * INR_PER_USD:.1f})")
    print(f"[replay_audit] suggested --max-inr (1.3x estimate): {total_high * INR_PER_USD * 1.3:.1f} "
          f"(1.3x the high end; the estimate excludes grounding calls)")


_UNPRICED = "unpriced"
_GEMINI_PRICED_MODEL = "gemini-3.6-flash"


def _summarize_grounding(grounding_records: list[dict]) -> dict[str, dict]:
    """Aggregates grounding usage dicts per served model (response.model; a
    missing name groups as "unknown"). usd is a float, or "unpriced" when the
    model has no rates in eval.pricing. thought_tokens is deliberately not
    passed to the cost: LiteLLM's completion_tokens already includes
    reasoning, so output_tokens alone is the billed output."""
    by_model: dict[str, dict] = {}
    for rec in grounding_records:
        agg = by_model.setdefault(rec.get("model") or "unknown", {
            "calls": 0, "prompt_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "total_tokens": 0,
        })
        agg["calls"] += 1
        for field in ("prompt_tokens", "cached_tokens", "output_tokens", "total_tokens"):
            agg[field] += rec.get(field) or 0

    for model, agg in by_model.items():
        usd = cost_usd_for_model(
            model, agg["prompt_tokens"], agg["output_tokens"], thought=0.0, cached=agg["cached_tokens"],
        )
        agg["usd"] = _UNPRICED if usd is None else round(usd, 4)
    return by_model


def _print_summary(
    out_dir: Path, records: list[CallRecord], grounding_records: list[dict] | None = None,
    status: str = STATUS_OK, guard: _CostGuard | None = None,
) -> None:
    grounding_records = grounding_records or []
    total_prompt = sum(r.prompt_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_thought = sum(r.thought_tokens for r in records)
    total_cached = sum(r.cached_tokens for r in records)
    total_tool_use = sum(r.tool_use_tokens for r in records)

    # Each Gemini record is priced by the model that served it. A record with a
    # missing or unknown model is priced at gemini-3.6-flash rates (an upper
    # bound) and counted here.
    gemini_usd = 0.0
    other_gemini_models: dict[str, int] = defaultdict(int)
    for r in records:
        usd, at_own_rate = _gemini_record_cost_usd(r)
        gemini_usd += usd
        if not at_own_rate:
            other_gemini_models[r.model_used or "unknown"] += 1

    grounding = _summarize_grounding(grounding_records)
    unpriced_models = sorted(m for m, agg in grounding.items() if agg["usd"] == _UNPRICED)
    grounding_usd = sum(agg["usd"] for agg in grounding.values() if agg["usd"] != _UNPRICED)
    total_usd = gemini_usd + grounding_usd

    summary = {
        "status": status,
        "calls": len(records),
        "total_prompt_tokens": total_prompt,
        "total_output_tokens": total_output,
        "total_thought_tokens": total_thought,
        "total_cached_tokens": total_cached,
        "total_tool_use_tokens": total_tool_use,
        "cost_usd": round(gemini_usd, 4),
        "cost_inr": round(gemini_usd * INR_PER_USD, 2),
        "gemini_calls_not_priced_at_own_model_rate": dict(other_gemini_models),
        "grounding": {"by_model": grounding, "unpriced_models": unpriced_models, "priced_cost_usd": round(grounding_usd, 4)},
        "total_cost_usd": round(total_usd, 4),
        "total_cost_inr": round(total_usd * INR_PER_USD, 2),
        "total_cost_excludes_unpriced_grounding": bool(unpriced_models),
        "records": [r.__dict__ for r in records],
    }
    if guard is not None and guard.max_inr is not None:
        summary["cap"] = {
            "max_inr": guard.max_inr,
            "running_inr_at_stop": round(guard.running_inr, 2),
            "overshoot_inr": round(guard.overshoot_inr, 2),
            # Calls run one at a time, so the overshoot can never exceed the
            # single call that crossed the cap; this is the largest call so far.
            "max_single_call_inr": round(guard.max_single_call_inr, 2),
        }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[replay_audit] {len(records)} Gemini calls, {total_prompt} prompt ({total_cached} cached) / {total_output} output / "
          f"{total_thought} thought tokens, ~INR {summary['cost_inr']}")
    if other_gemini_models:
        print(f"[replay_audit] WARNING: Gemini calls with a missing/unknown model were priced at {_GEMINI_PRICED_MODEL} "
              f"rates (upper bound): {dict(other_gemini_models)}")
    if grounding:
        for model, agg in sorted(grounding.items()):
            print(f"[replay_audit] grounding {model}: {agg['calls']} calls, {agg['prompt_tokens']} prompt "
                  f"({agg['cached_tokens']} cached) / {agg['output_tokens']} output / {agg['total_tokens']} total tokens, "
                  f"USD {agg['usd']}")
    else:
        print("[replay_audit] grounding: 0 LLM calls recorded")
    if unpriced_models:
        print(f"[replay_audit] *** UNPRICED grounding models (no rates on file): {', '.join(unpriced_models)} ***")
    label = " (excl. unpriced grounding)" if unpriced_models else ""
    print(f"[replay_audit] total ~INR {summary['total_cost_inr']}{label}")
    if status == STATUS_VOID_CAP_HIT and guard is not None:
        bar = "*" * 78
        print(bar)
        print(f"[replay_audit] *** {STATUS_VOID_CAP_HIT}: cost cap of INR {guard.max_inr} exceeded - THIS RUN IS VOID ***")
        print(f"[replay_audit] *** running cost at stop INR {guard.running_inr:.2f} (overshoot INR {guard.overshoot_inr:.2f}; "
              f"largest single call so far INR {guard.max_single_call_inr:.2f}) ***")
        print(f"[replay_audit] *** no further calls issued; partial summary: {out_dir / '_summary.json'} ***")
        print(bar)


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

    paper_ids = sorted({t.paper_id for t in targets})
    paper_texts: dict[str, str] = {}
    if args.dry_run:
        for paper_id in paper_ids:
            path = RAW_TEXT_CACHE_DIR / _cache_file_name(paper_id)
            print(f"[replay_audit] DRY-RUN cache {paper_id}: {'found' if path.is_file() else 'MISSING'} ({path.name})")
    else:
        # Load every paper's text before the first paid call, so a missing file
        # fails the run with zero spend.
        try:
            paper_texts = _load_paper_texts(paper_ids)
        except PaperTextError as exc:
            print(f"[replay_audit] ABORT: {exc}")
            return 1

    guard = _CostGuard(getattr(args, "max_inr", None))
    for repeat_index in range(1, args.repeat + 1):
        out_dir, records, grounding_records, status = await _run_once(
            targets, args.level, repeat_index, args.dry_run, paper_texts, guard,
        )
        if args.dry_run:
            continue
        _print_summary(out_dir, records, grounding_records, status, guard)
        if status != STATUS_OK:
            return EXIT_CAP_HIT
    return 0


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {value}")
    return number


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", required=True, choices=["low", "medium", "high"])
    parser.add_argument("--claims", help="JSON file of [{paper_id, claim_index}, ...] (omit for all 12 papers/362 claims)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--papers", help="comma-separated paper_id substrings to further narrow scope")
    parser.add_argument("--estimate", action="store_true", help="print a cost estimate, zero LLM calls")
    parser.add_argument("--dry-run", action="store_true", help="print what would be replayed, zero LLM calls")
    parser.add_argument(
        "--max-inr", type=_positive_float, default=None,
        help="stop (status VOID_CAP_HIT, exit 2) once the running cost passes this many INR; default no cap",
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
