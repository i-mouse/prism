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

--cache (default off) turns on explicit context caching of the system prompt +
paper for the audit calls (extraction/context_cache.py, BETA): one cache per
paper, created before its first claim and deleted after its last. The cap
counts cache creation (0.0 while eval.pricing.CACHE_CREATION_BILLED is False:
observed once on A0, undocumented) and storage (cached tokens x the actual
lifetime, create to delete, on a monotonic clock: observed on A0, inferred from
one run: 3,980 token-hours, about 35 s average lifetime; Google docs still say
storage is billed on the TTL) as well as the cached audit calls. Storage is
only known once the cache is deleted, so it is charged then. The run stops at the FIRST cache creation
failure or cached-call API error: status VOID_CACHE_FAILED, summary written,
exit code 2. With --estimate, --cache prints the cached estimate (still free:
no network, no cache read).

Usage:
  uv run python -m eval.replay_audit --estimate --level high --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --dry-run  --level high --claims docs/evals/exp1_stage_a_claims.json --repeat 3
  uv run python -m eval.replay_audit --level high   --claims docs/evals/exp1_stage_a_claims.json --repeat 3 --max-inr 100
  uv run python -m eval.replay_audit --level medium --claims docs/evals/exp1_stage_a_claims.json --repeat 2
  uv run python -m eval.replay_audit --estimate --cache --level medium --claims docs/evals/exp1_stage_a_claims.json
  uv run python -m eval.replay_audit --level high                                   # Stage B: all 12 papers, repeat 1
  uv run python -m eval.replay_audit --level medium --claims ... --backend vertex --vertex-project <id> --auditor-model gemini-3.8-flash
  uv run python -m eval.replay_audit --level high --claims ... --backend vertex --vertex-project <id> --auditor-model gemini-3.8-flash --repeat-index 2   # only folder _2
  uv run python -m eval.replay_audit --set golden --level high --claims docs/evals/exp1_golden_claims.json --backend vertex --vertex-project <id> --auditor-model gemini-3.8-flash

--backend {aistudio,vertex} (default aistudio), --vertex-project (required with vertex, no default) and
--vertex-location (default global) send EVERY Gemini call of the process to Vertex AI (Application Default
Credentials): auditor, structurer, cache create/use/delete, scope lister/checker, and the Gemini routes of the
LiteLLM grounding calls (a groq/ primary is not a Gemini call and is left as it is). --auditor-model (default: the
configured auditor model) changes the model of the audit call and of the --cache cache only. With both options unset
nothing changes: same requests, same files, same folders. With either set, the run goes to its own folder
(exp1_{level}_{model}[-vertex][_scope]_{n}, never an existing one), every claim records audit_model_served, and
_summary.json has a "run_config" block. Every Google model the run can call must have a price in eval/pricing.py
or the run stops before the first request; "minimal" thinking with gemini-3.8-flash is refused.

--scope-check (default off, requires --cache; any other combination is a
ValueError) adds the scope lister and scope checker (extraction/scope_check.py,
extraction/scope_combine.py): per claim, inside the paper's claim loop and while
its cache is alive, audit -> structure -> lister -> checker (only if the lister
found items), sequential; after the loop, grounding, then the combine step, which
may lower a "supported" label to "partially_supported". The lister and checker
never see the auditor's verdict, reasoning or quotes, and the audit, structure and
grounding inputs are the same as without the flag. The cache TTL is 3600 s (the
clamp maximum) because the extra calls lengthen each claim; storage is still
charged on the actual lifetime. Lister and checker calls are priced, counted in
the summary and against --max-inr like the audit calls. With the flag on, the
output goes to exp1_{level}_scope_{n} (never over the exp1_{level}_{n} baselines),
each claim carries the scope trace fields (auditor_label, label, scope_lowered,
scope_item, scope_item_kind, scope_quote, scope_items), the replay header records
the flag-on prompt hash, and _summary.json has a "scope_check" block. With the flag
off none of that exists and the output is byte-identical to before the flag.
"""
import argparse
import asyncio
import contextlib
import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from eval import backend_options, pricing
from eval.legacy_paper_text import PDF_DIR, _hash_check_and_load_text  # noqa: F401 - re-exported for replay_exp3/replay_clean/replay_extract; unused here
from eval.matrix_loader import load_matrix
from eval.pricing import (
    INR_PER_USD,
    USD_PER_1M_CACHED_INPUT,
    USD_PER_1M_INPUT,
    USD_PER_1M_OUTPUT,
    cache_creation_cost_usd,
    cost_usd,
    cost_usd_for_model,
    storage_cost_usd,
)
from extraction import engine, grounding, llm_backend, scope_check, scope_combine
from extraction.context_cache import (
    MAX_TTL_S,
    PER_CLAIM_SECONDS,
    CacheFailed,
    ContextCacheStats,
    PaperCache,
    paper_context_cache,
    ttl_for_claims,
)
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLLM, ClaimsExtractionResponse

REPO_ROOT = Path(__file__).parent.parent.parent
SERVICE_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "run1"
OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "fixtures" / "dev"
LOGS_DIR = SERVICE_ROOT / "logs" / "eval"
RAW_TEXT_CACHE_DIR = SERVICE_ROOT / "scratch" / "auditor_rd" / "raw_text_cache"

# --set golden: the golden matrix's papers (frozen claims + frozen matches in GOLDEN_FIXTURE_DIR), their
# paper text (eval/build_golden_text_cache.py), and a separate output root.
SET_DEV = "dev"
SET_GOLDEN = "golden"
GOLDEN_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"
GOLDEN_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
GOLDEN_OUTPUT_ROOT = REPO_ROOT / "docs" / "evals" / "golden_replay"
GOLDEN_TEXT_CACHE_DIR = SERVICE_ROOT / "scratch" / "auditor_rd" / "golden_text_cache"

EXPECTED_PROMPT_HASH = "cb3272cce551"

_ARXIV_PREFIX = "arxiv-"
STATUS_OK = "OK"
STATUS_VOID_CAP_HIT = "VOID_CAP_HIT"
STATUS_VOID_CACHE_FAILED = "VOID_CACHE_FAILED"
EXIT_CAP_HIT = 2

# --estimate --cache: the part of an audit prompt that is NOT cached (the claim
# turn). An ASSUMPTION - not measured; the measured audit prompt average minus
# this is treated as the cached part.
ASSUMED_UNCACHED_TOKENS_PER_CLAIM = 500

# --estimate --scope-check: no lister or checker run has been measured at scale
# (docs/decisions.md 2026-10-27 probe: one request, thoughts not reported), so
# every figure below is an ASSUMPTION and is printed as one.
ASSUMED_LISTER_INPUT_TOKENS = 700  # scope_list_system.md + the claim
ASSUMED_LISTER_OUTPUT_TOKENS = 150
ASSUMED_LISTER_THOUGHT_TOKENS = 200
ASSUMED_CHECKER_UNCACHED_TOKENS = 900  # scope_check_user.md + the claim + its items
ASSUMED_CHECKER_OUTPUT_TOKENS = 700  # verbatim quotes per item
ASSUMED_CHECKER_THOUGHT_TOKENS = 800
ASSUMED_SCOPE_SECONDS_PER_CLAIM = 25  # lister + checker latency added to the cache's lifetime

_STORAGE_NOTE = (
    "observed on A0 (inferred from one run: 3,980 token-hours, about 35 s average lifetime); "
    "Google docs still say storage is billed on the TTL"
)


def _creation_note() -> str:
    if pricing.CACHE_CREATION_BILLED:
        return "creation: ASSUMPTION: billed at the normal input rate (not stated in the pricing docs)"
    return "creation: not billed (observed on A0)"


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
    stage: str  # "audit" or "structure"; "lister" / "checker" for the scope calls (their call_kind tag)
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
    # True for the auditor call, False for the structurer (told apart by the
    # structurer's response_schema) and for a call tagged with another kind;
    # None when unknown.
    is_audit: bool | None = None


@dataclass
class CachePaperRecord:
    """One paper's cache, with its creation cost (0.0 while creation is not billed) and
    its storage cost over the actual lifetime. storage_usd and lifetime_s are filled
    in once the cache is deleted (_finalize_cache_storage)."""
    paper_id: str
    cache_name: str
    claims: int
    token_count: int | None
    tokens_assumed: bool  # token_count was missing, the measured audit-prompt average was charged instead
    tokens_charged: float
    ttl_s: int
    creation_usd: float
    storage_usd: float = 0.0
    lifetime_s: float | None = None


@dataclass
class _CacheLedger:
    """Cache bookkeeping for one --cache run: SDK-side counters (stats), one
    CachePaperRecord per created cache, and why the run stopped, if it did."""
    stats: ContextCacheStats
    assumed_tokens: float
    papers: list[CachePaperRecord] = field(default_factory=list)
    stop_reason: str | None = None

    @property
    def overhead_usd(self) -> float:
        return sum(p.creation_usd + p.storage_usd for p in self.papers)


@dataclass
class _ScopeLedger:
    """Scope-check bookkeeping for one --scope-check run: the counters and the
    flag-on prompt hash recorded in the replay header."""
    stats: scope_check.ScopeStats
    prompt_hash: str


@dataclass(frozen=True)
class _Dataset:
    """The paper set of one invocation. The dev set is not a _Dataset: while none is active the accessors
    below return the module's FIXTURE_DIR / RAW_TEXT_CACHE_DIR / OUTPUT_ROOT as they are at call time, so a
    default run is exactly what it was before --set existed. allowed_ids is the only list of paper ids the
    set may load - never a listing of its fixture folder, which may hold files of other sets."""
    name: str
    fixture_dir: Path
    text_dir: Path
    output_root: Path
    allowed_ids: frozenset[str]


_ACTIVE_DATASET: _Dataset | None = None


@contextlib.contextmanager
def active_dataset(dataset: _Dataset | None):
    """Makes `dataset` the one the loaders read, and restores the previous one (None = dev)."""
    global _ACTIVE_DATASET
    previous, _ACTIVE_DATASET = _ACTIVE_DATASET, dataset
    try:
        yield dataset
    finally:
        _ACTIVE_DATASET = previous


def _fixture_dir() -> Path:
    return _ACTIVE_DATASET.fixture_dir if _ACTIVE_DATASET is not None else FIXTURE_DIR


def _text_dir() -> Path:
    return _ACTIVE_DATASET.text_dir if _ACTIVE_DATASET is not None else RAW_TEXT_CACHE_DIR


def _output_root() -> Path:
    return _ACTIVE_DATASET.output_root if _ACTIVE_DATASET is not None else OUTPUT_ROOT


def _golden_dataset() -> _Dataset:
    """The golden set: exactly the papers of the golden matrix (matrix_loader.load_matrix)."""
    matrix = load_matrix(GOLDEN_MATRIX_PATH)
    return _Dataset(
        name=SET_GOLDEN, fixture_dir=GOLDEN_FIXTURE_DIR, text_dir=GOLDEN_TEXT_CACHE_DIR,
        output_root=GOLDEN_OUTPUT_ROOT, allowed_ids=frozenset(paper.paper_id for paper in matrix.papers),
    )


def _dataset_from_args(args: argparse.Namespace) -> _Dataset | None:
    """None for the dev set (nothing is swapped, the default path is untouched)."""
    name = getattr(args, "dataset", SET_DEV)
    if name == SET_DEV:
        return None
    if name == SET_GOLDEN:
        return _golden_dataset()
    raise ValueError(f"unknown --set {name!r}")


@dataclass
class _RunOptions:
    """The eval-only backend / auditor-model options of one invocation. With both at their
    default (AI Studio, no --auditor-model) a run uses none of this: the output folders,
    files, summary and request bytes are the ones from before the options existed.

    auditor_model None = engine.settings.llm_claim_audit_model. tag is the folder-name part
    of a non-default run (with --out-tag it ends in "-<out_tag>"); run_config is the block
    written to its _summary.json."""
    backend: backend_options.Backend
    auditor_model: str | None = None
    tag: str | None = None
    run_config: dict | None = None
    out_tag: str | None = None

    @property
    def non_default(self) -> bool:
        return self.tag is not None

    def out_dir(self, level: str, repeat_index: int, scope: bool) -> Path:
        scope_part = "_scope" if scope else ""
        if self.tag is None:
            return _output_root() / f"exp1_{level}{scope_part}_{repeat_index}"
        return _output_root() / f"exp1_{level}_{self.tag}{scope_part}_{repeat_index}"


def _validate_scope_flags(scope_check_on: bool, cache: bool) -> None:
    if scope_check_on and not cache:
        raise ValueError(
            "scope_check=True requires cache=True (--scope-check needs --cache): the scope checker reads the "
            "paper from the context cache and has no other copy of it"
        )


def _stop_on_cache_failure(reason: str) -> None:
    raise CacheFailed(reason)


def _new_cache_ledger() -> _CacheLedger:
    """A ledger whose stats stop the run at the first cache failure."""
    return _CacheLedger(
        stats=ContextCacheStats(on_cache_failure=_stop_on_cache_failure),
        assumed_tokens=_load_measured_token_stats()["audit_prompt"],
    )


INLINE_MIN_INDEX = 1000   # an inline claim's index must be above every run-1 index, so the two can never collide
_OUT_TAG_RE = re.compile(r"[A-Za-z0-9-]+")


@dataclass
class ReplayTarget:
    paper_id: str
    claim_index: int
    claim_text_verbatim: str
    claim_summary: str
    inline: bool = False   # True: text and summary came from the claims file, not from the run-1 fixture


def _load_claims_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_fixture(paper_id: str) -> dict:
    """The active set's stored fixture of one paper. Under --set golden its shape is checked (a dict with
    header, claims and matches, as dump_fixture writes them), so a legacy bare-array fixture stops the run
    before any request; the dev set reads the file as it always did."""
    fixture = json.loads((_fixture_dir() / f"{paper_id}.json").read_text(encoding="utf-8"))
    if _ACTIVE_DATASET is not None:
        missing = [key for key in ("header", "claims", "matches") if not isinstance(fixture, dict) or key not in fixture]
        if missing:
            raise PaperTextError(
                f"{paper_id}: {_ACTIVE_DATASET.name} fixture lacks {', '.join(missing)} (a legacy fixture? regenerate it)"
            )
    return fixture


def _inline_target(entry: dict) -> ReplayTarget | None:
    """The target of a claims-file entry that carries its own claim_text_verbatim and claim_summary (an
    "inline" claim, one that is not in the run-1 fixture), or None for an ordinary {paper_id, claim_index}
    entry. Only one of the two texts, a non-string or empty text, or a claim_index below INLINE_MIN_INDEX is a
    ValueError naming the entry."""
    has_text, has_summary = "claim_text_verbatim" in entry, "claim_summary" in entry
    if not has_text and not has_summary:
        return None
    ref = f"claims-file entry paper_id={entry.get('paper_id')!r} claim_index={entry.get('claim_index')!r}"
    if has_text != has_summary:
        raise ValueError(f"{ref}: an inline claim needs both claim_text_verbatim and claim_summary, got only one")
    for key in ("claim_text_verbatim", "claim_summary"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise ValueError(f"{ref}: {key} must be a non-empty string")
    index = entry["claim_index"]
    if isinstance(index, bool) or not isinstance(index, int) or index < INLINE_MIN_INDEX:
        raise ValueError(f"{ref}: an inline claim needs an integer claim_index >= {INLINE_MIN_INDEX}")
    return ReplayTarget(
        paper_id=entry["paper_id"], claim_index=index,
        claim_text_verbatim=entry["claim_text_verbatim"], claim_summary=entry["claim_summary"], inline=True,
    )


def _load_targets(claims_path: Path | None, papers_filter: str | None) -> list[ReplayTarget]:
    targets: list[ReplayTarget] = []
    if claims_path is not None:
        entries = _load_claims_file(claims_path)
        # (claim_index, inline target or None) per paper, in file order.
        by_paper: dict[str, list[tuple[int, ReplayTarget | None]]] = defaultdict(list)
        inline_seen = False
        for entry in entries:
            inline = _inline_target(entry)
            inline_seen = inline_seen or inline is not None
            by_paper[entry["paper_id"]].append((entry["claim_index"], inline))
        if inline_seen:
            # Only a file with inline claims is checked for repeats; an indexed-only file loads as it always did.
            seen: set[tuple[str, int]] = set()
            for paper_id, items in by_paper.items():
                for idx, _ in items:
                    if (paper_id, idx) in seen:
                        raise ValueError(f"claims file lists {paper_id} claim_index {idx} more than once")
                    seen.add((paper_id, idx))
        paper_ids = sorted(by_paper)
        if _ACTIVE_DATASET is not None:
            # Every id is checked before any fixture is read.
            for paper_id in paper_ids:
                _check_paper_id(paper_id)
    else:
        if _ACTIVE_DATASET is not None:
            paper_ids = sorted(_ACTIVE_DATASET.allowed_ids)
        else:
            paper_ids = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
        by_paper = None

    if papers_filter:
        wanted = {s.strip() for s in papers_filter.split(",")}
        paper_ids = [p for p in paper_ids if any(w in p for w in wanted)]

    if _ACTIVE_DATASET is not None:
        for paper_id in paper_ids:
            _check_paper_id(paper_id)

    for paper_id in paper_ids:
        items = by_paper[paper_id] if by_paper is not None else None
        if items is not None and all(inline is not None for _, inline in items):
            targets.extend(inline for _, inline in items)   # no indexed entry: the run-1 fixture is not read
            continue
        fixture = _read_fixture(paper_id)
        claims_by_index = {c["index"]: c for c in fixture["claims"]}
        if items is None:
            items = [(idx, None) for idx in sorted(claims_by_index)]
        for idx, inline in items:
            if inline is not None:
                targets.append(inline)
                continue
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


def _estimate_rates(model: str | None) -> tuple[float, float, float]:
    """(input, output, cached) USD per 1M for the estimate. None = the module's
    gemini-3.6-flash constants (today's estimate); a model name must be priced
    (pricing.UnpricedModelError otherwise)."""
    if model is None:
        return USD_PER_1M_INPUT, USD_PER_1M_OUTPUT, USD_PER_1M_CACHED_INPUT
    rates = pricing.rates_for_model(model)
    return rates.in_usd, rates.out_usd, rates.cached_rate


def _estimate_one_claim_cost_usd(
    stats: dict[str, float], level: str, cached_audit_tokens: float = 0.0,
    audit_model: str | None = None, struct_model: str | None = None,
) -> tuple[float, float]:
    """Returns (low, high) USD estimate for one audit+structure replay of one
    claim, using measured token averages. Only the audit call's thought
    tokens vary with thinking_level (scaled by _HIGH_THOUGHT_MULTIPLIER_RANGE
    for "high"); the structurer call never receives a thinking_config, so its
    thought tokens (the API's own default) are held at the measured medium
    average regardless of level - that assumption is unverified for "high"
    and could itself be an underestimate.

    cached_audit_tokens (default 0, the uncached estimate) is the part of the
    audit prompt billed at the cached rate; the rest of the audit prompt is
    billed at the normal input rate. Cache creation and storage are NOT
    included here (see _print_cache_estimate).

    audit_model / struct_model (default None = the gemini-3.6-flash constants,
    today's numbers) price the audit tokens and the structure tokens at each
    call's own model."""
    if level == "high":
        thought_low = stats["audit_thought_medium"] * _HIGH_THOUGHT_MULTIPLIER_RANGE[0]
        thought_high = stats["audit_thought_medium"] * _HIGH_THOUGHT_MULTIPLIER_RANGE[1]
    else:
        thought_low = thought_high = stats["audit_thought_medium"]

    audit_in, audit_out, audit_cached = _estimate_rates(audit_model)
    struct_in, struct_out, _ = _estimate_rates(struct_model)

    def _cost(audit_thought_tokens: float) -> float:
        if (audit_in, audit_out) == (struct_in, struct_out):
            input_cost = (
                (stats["audit_prompt"] - cached_audit_tokens + stats["struct_prompt"]) / 1e6 * audit_in
                + cached_audit_tokens / 1e6 * audit_cached
            )
            output_cost = (
                (stats["audit_output"] + audit_thought_tokens + stats["struct_output"] + stats["struct_thought"])
                / 1e6 * audit_out
            )
            return input_cost + output_cost
        input_cost = (
            (stats["audit_prompt"] - cached_audit_tokens) / 1e6 * audit_in + cached_audit_tokens / 1e6 * audit_cached
            + stats["struct_prompt"] / 1e6 * struct_in
        )
        output_cost = (
            (stats["audit_output"] + audit_thought_tokens) / 1e6 * audit_out
            + (stats["struct_output"] + stats["struct_thought"]) / 1e6 * struct_out
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


def _check_paper_id(paper_id: str) -> None:
    """The id check of the active set. Dev (no active set): _check_dev_paper_id, as ever. A named set: a
    plain id that is one of the set's allowed ids and has a fixture file there - so neither a path nor any
    other set's paper (held-out and sealed ones included) can reach the text lookup or a fixture read."""
    if _ACTIVE_DATASET is None:
        _check_dev_paper_id(paper_id)
        return
    if not paper_id or paper_id in {".", ".."} or "/" in paper_id or "\\" in paper_id:
        raise PaperTextError(f"{paper_id!r} is not a plain paper id")
    if paper_id not in _ACTIVE_DATASET.allowed_ids:
        raise PaperTextError(f"{paper_id}: not a paper of the {_ACTIVE_DATASET.name} set, refusing to load it")
    if not (_ACTIVE_DATASET.fixture_dir / f"{paper_id}.json").is_file():
        raise PaperTextError(f"{paper_id}: no {_ACTIVE_DATASET.name} fixture file in {_ACTIVE_DATASET.fixture_dir}")


def _load_paper_text(paper_id: str) -> str:
    _check_paper_id(paper_id)
    path = _text_dir() / _cache_file_name(paper_id)
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

    async def _wrapped(
        self, client, contents, config, chat_id, model_name, fallback_model, correlation_id=None, **fallback_kwargs,
    ):
        # fallback_kwargs (fallback_config / fallback_contents) are only ever
        # passed by a cached auditor call; they are forwarded untouched.
        self.raise_if_capped()
        # call_kind (a tag only the scope lister/checker pass) is forwarded
        # untouched with the rest; without it, today's rules apply.
        call_kind = fallback_kwargs.get("call_kind")
        start = time.monotonic()
        response, used_model = await self._original(
            client, contents, config, chat_id, model_name, fallback_model, correlation_id, **fallback_kwargs,
        )
        latency = time.monotonic() - start
        usage = getattr(response, "usage_metadata", None)
        record = CallRecord(
            stage=call_kind or self._current_stage, paper_id=self._current_paper_id, claim_index=self._current_claim_index,
            thinking_level=self._current_thinking_level, model_used=used_model,
            prompt_tokens=getattr(usage, "prompt_token_count", None) or 0,
            output_tokens=getattr(usage, "candidates_token_count", None) or 0,
            thought_tokens=getattr(usage, "thoughts_token_count", None) or 0,
            total_tokens=getattr(usage, "total_token_count", None) or 0,
            latency_s=latency,
            cached_tokens=getattr(usage, "cached_content_token_count", None) or 0,
            tool_use_tokens=getattr(usage, "tool_use_prompt_token_count", None) or 0,
            is_audit=(
                call_kind == "audit" if call_kind is not None
                else getattr(config, "response_schema", None) is None
            ),
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


async def _replay_claim(
    target: ReplayTarget, paper_text: str, level: str, instrumentation: _Instrumentation,
    paper_cache: PaperCache | None = None, audit_model: str | None = None,
) -> ClaimLLM:
    semaphore = asyncio.Semaphore(1)
    instrumentation.set_context("audit", target.paper_id, target.claim_index, level)
    claim_dict = {"claim_text_verbatim": target.claim_text_verbatim, "claim_summary": target.claim_summary}

    # _audit_and_structure_claim's own tracer spans don't distinguish
    # audit/structure in our instrumentation, so set_context before the call
    # covers the audit call; the structurer call is also wrapped but reported
    # under the same context (close enough - the structurer never varies by
    # thinking_level, only the audit call's cost is Experiment 1's variable).
    cache_kwargs = {"paper_cache": paper_cache} if paper_cache is not None else {}
    # Passed on only when --auditor-model is set, so the default call is unchanged.
    if audit_model is not None:
        cache_kwargs["audit_model"] = audit_model
    return await engine._audit_and_structure_claim(
        semaphore=semaphore, paper_text=paper_text, claim=claim_dict, chat_id=f"replay-{target.paper_id}",
        correlation_id=None, claim_number=target.claim_index + 1, total_claims=1, thinking_level=level,
        **cache_kwargs,
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


def _record_and_charge_cache(
    cache_ledger: _CacheLedger, guard: _CostGuard | None, paper_id: str, claims: int, paper_cache: PaperCache,
) -> None:
    """Books one paper's cache at creation: the creation cost (0.0 while
    pricing.CACHE_CREATION_BILLED is False). Storage is booked later, once the
    lifetime is known (_finalize_cache_storage). The record is appended before
    the charge so the summary has it even if the charge trips the cap. When the
    create response carried no token count, the measured audit-prompt average
    is charged instead and the record says so."""
    assumed = paper_cache.token_count is None
    tokens = cache_ledger.assumed_tokens if assumed else float(paper_cache.token_count)
    record = CachePaperRecord(
        paper_id=paper_id, cache_name=paper_cache.name, claims=claims, token_count=paper_cache.token_count,
        tokens_assumed=assumed, tokens_charged=tokens, ttl_s=paper_cache.ttl_s,
        creation_usd=cache_creation_cost_usd(tokens),
    )
    cache_ledger.papers.append(record)
    if guard is not None:
        guard.charge(record.creation_usd)


def _finalize_cache_storage(cache_ledger: _CacheLedger | None, model: str | None = None) -> float:
    """Books storage (tokens x actual lifetime, as recorded in the ledger's
    ContextCacheStats once the cache is deleted) on every record that has none
    yet, and returns the USD newly booked. Does not touch the guard, so it is
    safe in a finally clause. model (the auditor model of a non-default run)
    selects that model's storage rate; None is today's rate."""
    if cache_ledger is None:
        return 0.0
    booked = 0.0
    for record in cache_ledger.papers:
        lifetime_s = cache_ledger.stats.lifetimes_s.get(record.cache_name)
        if record.lifetime_s is not None or lifetime_s is None:
            continue
        record.lifetime_s = lifetime_s
        record.storage_usd = storage_cost_usd(record.tokens_charged, lifetime_s / 3600, model=model)
        booked += record.storage_usd
    return booked


async def _run_once(
    targets: list[ReplayTarget], level: str, repeat_index: int, dry_run: bool,
    paper_texts: dict[str, str] | None = None, guard: _CostGuard | None = None,
    cache_ledger: _CacheLedger | None = None, scope_ledger: _ScopeLedger | None = None,
    run_options: _RunOptions | None = None,
) -> tuple[Path, list[CallRecord], list[dict], str]:
    """Returns (out_dir, gemini records, grounding records, status). status is
    STATUS_VOID_CAP_HIT when the guard's cap stopped the run, or
    STATUS_VOID_CACHE_FAILED when the first cache failure did (cache_ledger
    given); the run is then void and nothing further is issued.

    A cache_ledger turns context caching on: one cache per paper, created
    before its first claim and deleted when its claim loop exits, however it
    exits. Its creation cost is charged to the guard when the cache is created
    and its storage cost (actual lifetime) once the cache is deleted.

    A scope_ledger (requires cache_ledger, else ValueError) turns the scope check
    on: per claim, inside the cache scope, lister -> checker follow the audit and
    structure calls; after grounding, the combine step runs last. The cache TTL is
    MAX_TTL_S. Output goes to exp1_{level}_scope_{n}.

    run_options (None = a default run) carries --auditor-model: the audit call and
    the cache then use that model, a non-default run writes to its own
    exp1_{level}_{tag}[_scope]_{n} folder, and each claim records the model that
    actually served its audit call (audit_model_served)."""
    _validate_scope_flags(scope_ledger is not None, cache_ledger is not None)
    run_options = run_options or _RunOptions(backend=llm_backend.AISTUDIO)
    out_dir = run_options.out_dir(level, repeat_index, scope_ledger is not None)
    audit_model = run_options.auditor_model
    cache_model = audit_model or engine.settings.llm_claim_audit_model
    by_paper: dict[str, list[ReplayTarget]] = defaultdict(list)
    for t in targets:
        by_paper[t.paper_id].append(t)

    instrumentation = _Instrumentation(guard)
    preexisting_tasks = asyncio.all_tasks()
    status = STATUS_OK

    with instrumentation:
        try:
            for paper_id, paper_targets in sorted(by_paper.items()):
                run1_fixture = json.loads((_fixture_dir() / f"{paper_id}.json").read_text(encoding="utf-8"))
                if dry_run:
                    print(f"[replay_audit] DRY-RUN {paper_id} repeat={repeat_index} level={level} "
                          f"claims={[t.claim_index for t in paper_targets]}")
                    continue

                paper_text = paper_texts[paper_id]

                audited: list[ClaimLLM] = []
                audit_models_served: list[str | None] = []
                scope_results: list[scope_check.ClaimScope] = []
                ttl_kwargs = {"ttl_s": MAX_TTL_S} if scope_ledger is not None else {}
                cache_scope = (
                    paper_context_cache(
                        engine._build_client(), cache_model, paper_text,
                        len(paper_targets), cache_ledger.stats, **ttl_kwargs,
                    )
                    if cache_ledger is not None
                    else contextlib.nullcontext()
                )
                storage_usd = 0.0
                try:
                    async with cache_scope as paper_cache:
                        cache_kwargs: dict = {}
                        if paper_cache is not None:
                            _record_and_charge_cache(cache_ledger, guard, paper_id, len(paper_targets), paper_cache)
                            cache_kwargs = {"paper_cache": paper_cache}
                        for target in paper_targets:
                            instrumentation.raise_if_capped()
                            # audit_model is passed only when --auditor-model is set (default call unchanged).
                            audit_kwargs = {"audit_model": audit_model} if audit_model is not None else {}
                            claim_llm = await _replay_claim(
                                target, paper_text, level, instrumentation, **cache_kwargs, **audit_kwargs,
                            )
                            audited.append(claim_llm)
                            audit_models_served.append(next((
                                r.model_used for r in reversed(instrumentation.records)
                                if r.is_audit and r.paper_id == paper_id and r.claim_index == target.claim_index
                            ), None))
                            if scope_ledger is not None:
                                # Lister + checker see the claim text and the cache, never claim_llm.
                                instrumentation.raise_if_capped()
                                scope_results.append(await scope_check.scope_for_claim(
                                    paper_cache, target.claim_text_verbatim, f"replay-{paper_id}", scope_ledger.stats,
                                    claim_ref=f"{paper_id}#{target.claim_index}",
                                ))
                finally:
                    # The cache is deleted by now, whichever way the block exited.
                    storage_usd = _finalize_cache_storage(cache_ledger, model=audit_model)
                if guard is not None and storage_usd:
                    guard.charge(storage_usd)

                instrumentation.raise_if_capped()
                grounded = await grounding.ground_extraction(
                    ClaimsExtractionResponse(claims=audited), paper_text, chat_id=f"replay-{paper_id}",
                )

                claims_out = [
                    _claim_final_to_fixture_dict(claim_final, target.claim_index)
                    for claim_final, target in zip(grounded, paper_targets)
                ]
                if run_options.non_default:
                    # The model that actually served each audit call (the fallback model after a primary
                    # failure). Default runs do not carry the field, so their files are unchanged.
                    for claim_dict, served in zip(claims_out, audit_models_served):
                        claim_dict["audit_model_served"] = served
                if scope_ledger is not None:
                    # Last step, paper level: the scope result may lower a "supported" label.
                    for claim_dict, claim_final, target, scope in zip(claims_out, grounded, paper_targets, scope_results):
                        trace = scope_combine.combine_scope(
                            claim_final.label.value, scope, paper_text, scope_ledger.stats,
                            claim_ref=f"{paper_id}#{target.claim_index}",
                        )
                        claim_dict.update(trace.to_fields())
                header = dict(run1_fixture["header"])
                header["model_name"] = cache_model
                header["replay"] = {
                    "thinking_level": level, "base_run": "run1", "repeat_index": repeat_index,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                if scope_ledger is not None:
                    header["replay"]["scope_check_prompt_hash"] = scope_ledger.prompt_hash
                if any(t.inline for t in targets):
                    # Claims given in the claims file, not in the run-1 fixture; "matches" below is still run 1's.
                    header["replay"]["inline_claims"] = True
                if _ACTIVE_DATASET is not None:
                    header["replay"]["set"] = _ACTIVE_DATASET.name  # a named set marks its files; dev files do not change
                header["claims_scope"] = [t.claim_index for t in paper_targets]
                fixture_out = {"header": header, "claims": claims_out, "matches": run1_fixture["matches"]}

                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / f"{paper_id}.json").write_text(json.dumps(fixture_out, indent=2), encoding="utf-8")
                print(f"[replay_audit] wrote {out_dir / f'{paper_id}.json'} ({len(claims_out)} claims)")
        except (CapExceeded, CacheFailed) as stop:
            if isinstance(stop, CacheFailed):
                status = STATUS_VOID_CACHE_FAILED
                if cache_ledger is not None:
                    cache_ledger.stop_reason = str(stop)
            else:
                status = STATUS_VOID_CAP_HIT
            await _cancel_stray_tasks(preexisting_tasks)

    return out_dir, instrumentation.records, instrumentation.grounding_records, status


def _print_cache_estimate(
    targets: list[ReplayTarget], level: str, repeats: int, stats: dict[str, float],
    uncached_total_usd: tuple[float, float], ttl_s: int | None = None,
    audit_model: str | None = None, struct_model: str | None = None,
) -> tuple[float, float]:
    """The --estimate --cache section: per paper, creation (0.0 while not
    billed) + storage for claims x PER_CLAIM_SECONDS (an upper bound on the
    actual lifetime) + each claim's audit with the cached part billed at the
    cached rate. Returns the (low, high) cached total in USD.
    Free: no network, no cache read. The cached part is the measured audit
    prompt average minus an ASSUMED uncached part per claim, so every paper
    is treated as an average-sized paper."""
    cached_tokens = max(0.0, stats["audit_prompt"] - ASSUMED_UNCACHED_TOKENS_PER_CLAIM)
    claim_low, claim_high = _estimate_one_claim_cost_usd(
        stats, level, cached_audit_tokens=cached_tokens, audit_model=audit_model, struct_model=struct_model,
    )
    claims_per_paper: dict[str, int] = defaultdict(int)
    for t in targets:
        claims_per_paper[t.paper_id] += 1

    total_low = total_high = overhead_total = 0.0
    for n in claims_per_paper.values():
        overhead = cache_creation_cost_usd(cached_tokens) + storage_cost_usd(
            cached_tokens, n * PER_CLAIM_SECONDS / 3600, model=audit_model,
        )
        overhead_total += overhead * repeats
        total_low += (overhead + claim_low * n) * repeats
        total_high += (overhead + claim_high * n) * repeats

    print(f"[replay_audit] --estimate --cache: {len(claims_per_paper)} papers, claims per paper "
          f"{dict(sorted(claims_per_paper.items()))}, TTL per paper (s) "
          f"{ {p: (ttl_s if ttl_s is not None else ttl_for_claims(n)) for p, n in sorted(claims_per_paper.items())} }")
    print(f"[replay_audit] ASSUMPTION: {ASSUMED_UNCACHED_TOKENS_PER_CLAIM} uncached tokens per claim (the claim turn); "
          f"the other {cached_tokens:.0f} of the measured {stats['audit_prompt']:.0f}-token audit prompt are cached "
          f"and billed at the cached rate")
    print(f"[replay_audit] {_creation_note()}")
    print(f"[replay_audit] storage: cached tokens x claims x {PER_CLAIM_SECONDS} s per paper, an UPPER BOUND on the actual "
          f"lifetime; {_STORAGE_NOTE}")
    print(f"[replay_audit] cache creation + storage (upper bound): USD {overhead_total:.3f} (INR {overhead_total * INR_PER_USD:.1f})")
    print(f"[replay_audit] uncached total: USD {uncached_total_usd[0]:.3f}-{uncached_total_usd[1]:.3f} "
          f"(INR {uncached_total_usd[0] * INR_PER_USD:.1f}-{uncached_total_usd[1] * INR_PER_USD:.1f})")
    print(f"[replay_audit] cached total:   USD {total_low:.3f}-{total_high:.3f} "
          f"(INR {total_low * INR_PER_USD:.1f}-{total_high * INR_PER_USD:.1f})")
    print(f"[replay_audit] suggested --max-inr with --cache (1.3x the high end): {total_high * INR_PER_USD * 1.3:.1f} "
          f"(the estimate excludes grounding calls)")
    return total_low, total_high


def _print_scope_estimate(
    targets: list[ReplayTarget], repeats: int, stats: dict[str, float], cached_total_usd: tuple[float, float],
) -> None:
    """The --estimate --scope-check section, added on top of the --cache estimate.
    No lister or checker run has been measured at scale (the 2026-10-27 probe was
    one request, thoughts not reported), so every figure below that is not from
    the audit averages is printed as an ASSUMPTION. Free: no network.

    Per claim-replay: one lister call (uncached, no paper) and one checker call
    (cached part billed at the cached rate) - the checker is assumed to run for
    every claim, the upper bound. Extra storage: the TTL is MAX_TTL_S but storage
    follows the actual lifetime, which the extra calls lengthen by
    ASSUMED_SCOPE_SECONDS_PER_CLAIM per claim (upper-bound style, like the cache
    estimate)."""
    cached_tokens = max(0.0, stats["audit_prompt"] - ASSUMED_UNCACHED_TOKENS_PER_CLAIM)
    lister_usd = cost_usd(ASSUMED_LISTER_INPUT_TOKENS, ASSUMED_LISTER_OUTPUT_TOKENS, ASSUMED_LISTER_THOUGHT_TOKENS)
    checker_usd = cost_usd(
        cached_tokens + ASSUMED_CHECKER_UNCACHED_TOKENS, ASSUMED_CHECKER_OUTPUT_TOKENS,
        ASSUMED_CHECKER_THOUGHT_TOKENS, cached_tokens=cached_tokens,
    )
    claim_replays = len(targets) * repeats
    calls_usd = (lister_usd + checker_usd) * claim_replays
    storage_usd = storage_cost_usd(cached_tokens, claim_replays * ASSUMED_SCOPE_SECONDS_PER_CLAIM / 3600)
    scope_usd = calls_usd + storage_usd
    total_low, total_high = cached_total_usd[0] + scope_usd, cached_total_usd[1] + scope_usd

    print(f"[replay_audit] --estimate --scope-check: cache TTL {MAX_TTL_S} s per paper (the clamp maximum; storage is "
          f"still charged on the actual lifetime)")
    print(f"[replay_audit] ASSUMPTION (lister, uncached, thinking low): {ASSUMED_LISTER_INPUT_TOKENS} input / "
          f"{ASSUMED_LISTER_OUTPUT_TOKENS} output / {ASSUMED_LISTER_THOUGHT_TOKENS} thought tokens per claim")
    print(f"[replay_audit] ASSUMPTION (checker, cached, thinking low, run for every claim = upper bound): "
          f"{cached_tokens:.0f} cached (the audit estimate's cached part) + {ASSUMED_CHECKER_UNCACHED_TOKENS} uncached input / "
          f"{ASSUMED_CHECKER_OUTPUT_TOKENS} output / {ASSUMED_CHECKER_THOUGHT_TOKENS} thought tokens per claim")
    print(f"[replay_audit] ASSUMPTION: the lister + checker add {ASSUMED_SCOPE_SECONDS_PER_CLAIM} s per claim to the cache's lifetime")
    print(f"[replay_audit] scope calls: lister USD {lister_usd * claim_replays:.3f} + checker USD {checker_usd * claim_replays:.3f} "
          f"+ extra storage USD {storage_usd:.3f} = USD {scope_usd:.3f} (INR {scope_usd * INR_PER_USD:.1f})")
    print(f"[replay_audit] cached total + scope check: USD {total_low:.3f}-{total_high:.3f} "
          f"(INR {total_low * INR_PER_USD:.1f}-{total_high * INR_PER_USD:.1f})")
    print(f"[replay_audit] suggested --max-inr with --cache --scope-check (1.3x the high end): "
          f"{total_high * INR_PER_USD * 1.3:.1f} (the estimate excludes grounding calls)")


def _print_estimate(
    targets: list[ReplayTarget], level: str, repeats: int, cache: bool = False, scope_check: bool = False,
    audit_model: str | None = None, struct_model: str | None = None,
) -> None:
    """audit_model / struct_model: None (default) prices every token at the
    gemini-3.6-flash constants, as before. When --auditor-model is set both are
    given: audit tokens are priced at the auditor model, structure tokens at the
    structurer's model (pricing.UnpricedModelError for a model with no price)."""
    _validate_scope_flags(scope_check, cache)
    stats = _load_measured_token_stats()
    low, high = _estimate_one_claim_cost_usd(stats, level, audit_model=audit_model, struct_model=struct_model)
    if audit_model is not None:
        print(f"[replay_audit] --estimate: audit calls priced at {audit_model}, structure calls at {struct_model}; "
              f"ASSUMPTION: the token averages below were measured on the configured models, "
              f"{audit_model}'s thinking and output tokens may differ")
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
    if cache:
        cached_total = _print_cache_estimate(
            targets, level, repeats, stats, (total_low, total_high), ttl_s=MAX_TTL_S if scope_check else None,
            audit_model=audit_model, struct_model=struct_model,
        )
        if scope_check:
            _print_scope_estimate(targets, repeats, stats, cached_total)


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


def _cache_summary(cache_ledger: _CacheLedger, records: list[CallRecord], total_cached: int) -> dict:
    """The summary's "cache" block. Audit calls are the records flagged
    is_audit; per paper it lists the audit calls that billed no cached tokens
    (the Stage A0 mark) and audit cost per claim with and without the cache's
    creation + storage overhead."""
    stats = cache_ledger.stats
    audit_records = [r for r in records if r.is_audit]
    audit_usd = sum(_gemini_record_cost_usd(r)[0] for r in audit_records)
    overhead_usd = cache_ledger.overhead_usd
    n_audit = len(audit_records)

    papers = []
    for p in cache_ledger.papers:
        paper_audits = [r for r in audit_records if r.paper_id == p.paper_id]
        papers.append({
            **p.__dict__,
            "audit_calls": len(paper_audits),
            "audit_calls_zero_cached": sum(1 for r in paper_audits if not r.cached_tokens),
        })

    def _per_claim_inr(usd: float) -> float | None:
        return round(usd / n_audit * INR_PER_USD, 2) if n_audit else None

    return {
        "papers_cached": stats.papers_cached,
        "creation_failures": stats.creation_failures,
        "cached_call_api_failures": stats.cached_call_failures,
        "cache_fallbacks": stats.cache_fallbacks,
        "total_cached_tokens": total_cached,
        "tokens_created_total": stats.tokens_created_total,
        "token_count_missing": stats.token_count_missing,
        "claims_per_paper": {p.paper_id: p.claims for p in cache_ledger.papers},
        "creation_billed": pricing.CACHE_CREATION_BILLED,
        "creation_usd": round(sum(p.creation_usd for p in cache_ledger.papers), 4),
        "storage_usd_actual_lifetime": round(sum(p.storage_usd for p in cache_ledger.papers), 4),
        "overhead_usd": round(overhead_usd, 4),
        "audit_calls": n_audit,
        "audit_calls_zero_cached": sum(1 for r in audit_records if not r.cached_tokens),
        "audit_cost_per_claim_inr_excl_cache_overhead": _per_claim_inr(audit_usd),
        "audit_cost_per_claim_inr_incl_cache_overhead": _per_claim_inr(audit_usd + overhead_usd),
        "stop_reason": cache_ledger.stop_reason,
        "papers": papers,
    }


def _print_cache_summary(cache: dict) -> None:
    print(f"[replay_audit] cache: {cache['papers_cached']} papers cached, {cache['creation_failures']} creation failures, "
          f"{cache['cached_call_api_failures']} cached-call API failures, {cache['cache_fallbacks']} cache fallbacks, "
          f"{cache['total_cached_tokens']} cached tokens billed at the cached rate")
    print(f"[replay_audit] cache claims per paper: {cache['claims_per_paper']}")
    print(f"[replay_audit] cache overhead USD {cache['overhead_usd']}: {_creation_note()} (USD {cache['creation_usd']}) "
          f"+ storage USD {cache['storage_usd_actual_lifetime']} (actual lifetime, create to delete; {_STORAGE_NOTE})")
    if cache["token_count_missing"]:
        print(f"[replay_audit] ASSUMED: {cache['token_count_missing']} cache(s) returned no token count; "
              f"the measured audit-prompt average was charged for them")
    print(f"[replay_audit] audit calls {cache['audit_calls']}, with zero cached tokens {cache['audit_calls_zero_cached']}; "
          f"audit cost per claim INR {cache['audit_cost_per_claim_inr_excl_cache_overhead']} excl. / "
          f"{cache['audit_cost_per_claim_inr_incl_cache_overhead']} incl. cache creation + storage")


def _scope_summary(scope_ledger: _ScopeLedger, records: list[CallRecord]) -> dict:
    """The summary's "scope_check" block: the combine counters, and usage + cost
    (cached tokens included) of the two scope calls, priced like the audit calls."""
    by_call: dict[str, dict] = {}
    for kind in (scope_check.LISTER_CALL_KIND, scope_check.CHECKER_CALL_KIND):
        kind_records = [r for r in records if r.stage == kind]
        by_call[kind] = {
            "calls": len(kind_records),
            "prompt_tokens": sum(r.prompt_tokens for r in kind_records),
            "cached_tokens": sum(r.cached_tokens for r in kind_records),
            "output_tokens": sum(r.output_tokens for r in kind_records),
            "thought_tokens": sum(r.thought_tokens for r in kind_records),
            "cost_usd": round(sum(_gemini_record_cost_usd(r)[0] for r in kind_records), 4),
        }
    return {"prompt_hash": scope_ledger.prompt_hash, **asdict(scope_ledger.stats), "by_call": by_call}


def _print_scope_summary(block: dict) -> None:
    counts = {k: v for k, v in block.items() if k not in ("prompt_hash", "by_call")}
    print(f"[replay_audit] scope check (prompt hash {block['prompt_hash']}): {counts}")
    for kind, usage in block["by_call"].items():
        print(f"[replay_audit] scope {kind}: {usage['calls']} calls, {usage['prompt_tokens']} prompt "
              f"({usage['cached_tokens']} cached) / {usage['output_tokens']} output / {usage['thought_tokens']} thought "
              f"tokens, USD {usage['cost_usd']}")
    if block["lister_failures"] or block["checker_failures"]:
        print(f"[replay_audit] *** SCOPE CHECK FAILURES: {block['lister_failures']} lister, {block['checker_failures']} "
              f"checker; those claims' verdicts were left unchanged ***")


def _print_summary(
    out_dir: Path, records: list[CallRecord], grounding_records: list[dict] | None = None,
    status: str = STATUS_OK, guard: _CostGuard | None = None,
    cache_ledger: _CacheLedger | None = None, scope_ledger: _ScopeLedger | None = None,
    run_options: _RunOptions | None = None,
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
    cache_usd = cache_ledger.overhead_usd if cache_ledger is not None else 0.0
    total_usd = gemini_usd + grounding_usd + cache_usd

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
    if cache_ledger is not None:
        summary["cache"] = _cache_summary(cache_ledger, records, total_cached)
    if scope_ledger is not None:
        summary["scope_check"] = _scope_summary(scope_ledger, records)
    if guard is not None and guard.max_inr is not None:
        summary["cap"] = {
            "max_inr": guard.max_inr,
            "running_inr_at_stop": round(guard.running_inr, 2),
            "overshoot_inr": round(guard.overshoot_inr, 2),
            # Calls run one at a time, so the overshoot can never exceed the
            # single call that crossed the cap; this is the largest call so far.
            "max_single_call_inr": round(guard.max_single_call_inr, 2),
        }
    if run_options is not None and run_options.non_default:
        summary["run_config"] = run_options.run_config
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
    if cache_ledger is not None:
        _print_cache_summary(summary["cache"])
    if scope_ledger is not None:
        _print_scope_summary(summary["scope_check"])
    if "run_config" in summary:
        print(f"[replay_audit] run config: {summary['run_config']}")
    if status == STATUS_VOID_CACHE_FAILED:
        bar = "*" * 78
        print(bar)
        print(f"[replay_audit] *** {STATUS_VOID_CACHE_FAILED}: first cache failure stopped the run - THIS RUN IS VOID ***")
        print(f"[replay_audit] *** reason: {cache_ledger.stop_reason if cache_ledger is not None else 'unknown'} ***")
        print(f"[replay_audit] *** no further calls issued; partial summary: {out_dir / '_summary.json'} ***")
        print(bar)
    if status == STATUS_VOID_CAP_HIT and guard is not None:
        bar = "*" * 78
        print(bar)
        print(f"[replay_audit] *** {STATUS_VOID_CAP_HIT}: cost cap of INR {guard.max_inr} exceeded - THIS RUN IS VOID ***")
        print(f"[replay_audit] *** running cost at stop INR {guard.running_inr:.2f} (overshoot INR {guard.overshoot_inr:.2f}; "
              f"largest single call so far INR {guard.max_single_call_inr:.2f}) ***")
        print(f"[replay_audit] *** no further calls issued; partial summary: {out_dir / '_summary.json'} ***")
        print(bar)


def _prepare_run_options(args: argparse.Namespace, scope_check_on: bool) -> _RunOptions:
    """Reads --backend / --vertex-project / --vertex-location / --auditor-model and checks
    them before any request. Raises ValueError (bad option combination, thinking level the
    model rejects, a Google model with no price) or backend_options.BackendRoutingError (a
    Gemini route that cannot be sent to the backend). Both options at their default returns
    a default _RunOptions and checks nothing beyond the thinking level."""
    backend = backend_options.backend_from_args(args)
    auditor_model = getattr(args, "auditor_model", None)
    out_tag = getattr(args, "out_tag", None)
    if out_tag is not None and not _OUT_TAG_RE.fullmatch(out_tag):
        raise ValueError(f"--out-tag {out_tag!r}: use only letters, digits and '-'")
    structurer_model = engine.settings.llm_claim_audit_model
    effective_auditor = auditor_model or structurer_model
    backend_options.validate_thinking(effective_auditor, getattr(args, "level", None))
    if backend.name == llm_backend.BACKEND_AISTUDIO and auditor_model is None:
        if out_tag is not None:
            raise ValueError("--out-tag needs a non-default run (--backend vertex or --auditor-model): "
                             "a default run's folders are not tagged")
        return _RunOptions(backend=backend)

    if (
        scope_check_on and auditor_model is not None
        and pricing.normalise_model_name(auditor_model) != pricing.normalise_model_name(scope_check.SCOPE_MODEL)
    ):
        raise ValueError(
            f"--scope-check cannot be combined with --auditor-model {auditor_model}: the scope lister and checker "
            f"stay on {scope_check.SCOPE_MODEL}, and the checker reads the paper from a cache created with that model"
        )
    other_models = {
        "structurer": structurer_model,
        "audit_fallback": engine.settings.llm_claim_audit_fallback_model,
        "grounding_primary": engine.settings.llm_grounding_model,
        "grounding_fallback": engine.settings.llm_grounding_fallback_model,
    }
    if scope_check_on:
        other_models["scope_lister"] = scope_check.SCOPE_MODEL
        other_models["scope_checker"] = scope_check.SCOPE_MODEL
    backend_options.require_priced({"auditor": effective_auditor, **other_models})
    if getattr(args, "cache", False):
        pricing.storage_rate_for_model(effective_auditor)
    backend_options.check_grounding_routes(
        backend, engine.settings.llm_grounding_model, engine.settings.llm_grounding_fallback_model,
    )
    tag = backend_options.output_slug(auditor_model, backend, structurer_model)
    if out_tag is not None:
        tag = f"{tag}-{out_tag}"
    return _RunOptions(
        backend=backend, auditor_model=auditor_model, tag=tag, out_tag=out_tag,
        run_config=backend_options.run_config(backend, effective_auditor, other_models, getattr(args, "level", None)),
    )


async def _main(args: argparse.Namespace) -> int:
    # main.py runs init_telemetry at import time; keep it on the no-exporter
    # path before the first `from main import ...` anywhere in this process
    # (same as eval/replay_stage1.py).
    import os

    for key in ("OTEL_EXPORTER_OTLP_ENDPOINT", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ.pop(key, None)

    scope_check_on = getattr(args, "scope_check", False)
    _validate_scope_flags(scope_check_on, getattr(args, "cache", False))

    if getattr(args, "repeat_index", None) is not None and getattr(args, "repeat", 1) > 1:
        print("[replay_audit] ABORT: --repeat-index runs exactly one repeat; it cannot be combined with --repeat > 1")
        return 1

    prompt_hash = get_prompt_version()
    if prompt_hash != EXPECTED_PROMPT_HASH:
        print(f"[replay_audit] ABORT: prompt hash {prompt_hash} != expected {EXPECTED_PROMPT_HASH}")
        return 1
    # The flag-on hash (base prompts + scope prompts + scope schemas + marker) is
    # recorded in the replay header; the base hash above must still be the frozen one.
    scope_prompt_hash = get_prompt_version(scope_check=True) if scope_check_on else None

    # --backend / --vertex-project / --auditor-model: every check here runs before any request.
    try:
        run_options = _prepare_run_options(args, scope_check_on)
    except (ValueError, backend_options.BackendRoutingError) as exc:
        print(f"[replay_audit] ABORT: {exc}")
        return 1

    # --set golden: the golden matrix's papers and its own text / output folders. Dev (the default) is None.
    try:
        dataset = _dataset_from_args(args)
    except (ValueError, OSError) as exc:
        print(f"[replay_audit] ABORT: cannot load the {getattr(args, 'dataset', SET_DEV)} set: {exc}")
        return 1

    # Under --backend vertex every genai client and every Gemini LiteLLM route goes to Vertex for
    # the whole run; under the default AI Studio backend neither context changes anything.
    with backend_options.active_backend(run_options.backend), backend_options.routed_litellm(run_options.backend), \
            active_dataset(dataset):
        return await _run_replay(args, scope_check_on, scope_prompt_hash, run_options)


def _repeat_indices(args: argparse.Namespace) -> list[int]:
    """The repeat numbers this invocation runs: [K] under --repeat-index K, else 1..--repeat (as before)."""
    repeat_index = getattr(args, "repeat_index", None)
    if repeat_index is not None:
        return [repeat_index]
    return list(range(1, args.repeat + 1))


def _existing_out_dirs(run_options: _RunOptions, args: argparse.Namespace, scope_check_on: bool) -> list[str]:
    """The output folders of this invocation's repeats that already exist."""
    return [
        str(run_options.out_dir(args.level, n, scope_check_on)) for n in _repeat_indices(args)
        if run_options.out_dir(args.level, n, scope_check_on).exists()
    ]


async def _run_replay(
    args: argparse.Namespace, scope_check_on: bool, scope_prompt_hash: str | None, run_options: _RunOptions,
) -> int:
    claims_path = Path(args.claims) if args.claims else None
    try:
        targets = _load_targets(claims_path, args.papers)
    except (PaperTextError, ValueError) as exc:  # PaperTextError: a named set only; ValueError: a bad inline claim
        print(f"[replay_audit] ABORT: {exc}")
        return 1
    if not targets:
        print("[replay_audit] ABORT: no claims selected")
        return 1

    if run_options.non_default:
        print(f"[replay_audit] run config: {run_options.run_config}")

    if args.estimate and run_options.out_tag is not None:
        # A tagged run names its own folders up front, so --estimate also refuses when they exist.
        existing = _existing_out_dirs(run_options, args, scope_check_on)
        if existing:
            print(f"[replay_audit] ABORT: output folder(s) already exist, refusing to overwrite: {existing}")
            return 1

    if args.estimate:
        estimate_kwargs = {"scope_check": True} if scope_check_on else {}
        if run_options.auditor_model is not None:
            estimate_kwargs["audit_model"] = run_options.auditor_model
            estimate_kwargs["struct_model"] = engine.settings.llm_claim_audit_model
        _print_estimate(targets, args.level, args.repeat, cache=getattr(args, "cache", False), **estimate_kwargs)
        if scope_check_on:
            print(f"[replay_audit] scope-check prompt hash (recorded in the replay header): {scope_prompt_hash}")
        return 0

    if run_options.non_default and not args.dry_run:
        # A non-default run never overwrites an existing folder (the baselines included).
        existing = _existing_out_dirs(run_options, args, scope_check_on)
        if existing:
            print(f"[replay_audit] ABORT: output folder(s) already exist, refusing to overwrite: {existing}")
            return 1

    paper_ids = sorted({t.paper_id for t in targets})
    paper_texts: dict[str, str] = {}
    if args.dry_run:
        for paper_id in paper_ids:
            path = _text_dir() / _cache_file_name(paper_id)
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
    use_cache = getattr(args, "cache", False) and not args.dry_run
    for repeat_index in _repeat_indices(args):
        # A fresh ledger per repeat: each repeat has its own summary.
        cache_ledger = _new_cache_ledger() if use_cache else None
        run_kwargs = {"cache_ledger": cache_ledger} if cache_ledger is not None else {}
        scope_ledger = None
        if scope_check_on and not args.dry_run:
            scope_ledger = _ScopeLedger(stats=scope_check.ScopeStats(), prompt_hash=scope_prompt_hash)
            run_kwargs["scope_ledger"] = scope_ledger
        if run_options.non_default:
            run_kwargs["run_options"] = run_options
        out_dir, records, grounding_records, status = await _run_once(
            targets, args.level, repeat_index, args.dry_run, paper_texts, guard, **run_kwargs,
        )
        if args.dry_run:
            continue
        summary_kwargs = {"scope_ledger": scope_ledger} if scope_ledger is not None else {}
        if run_options.non_default:
            summary_kwargs["run_options"] = run_options
        _print_summary(out_dir, records, grounding_records, status, guard, cache_ledger, **summary_kwargs)
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
    parser.add_argument(
        "--claims",
        help="JSON file of [{paper_id, claim_index}, ...] (omit for all 12 papers/362 claims). An entry may also carry "
             "claim_text_verbatim + claim_summary (an inline claim, not in the run-1 fixture): its claim_index must "
             "then be >= 1000",
    )
    parser.add_argument(
        "--set", dest="dataset", choices=[SET_DEV, SET_GOLDEN], default=SET_DEV,
        help="which papers: dev (default, the run1 dev fixtures and raw_text_cache - nothing changes) or golden "
             "(the golden matrix's papers: fixtures in docs/evals/fixtures, text in scratch/auditor_rd/golden_text_cache, "
             "output under docs/evals/golden_replay)",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--repeat-index", type=int, choices=[1, 2, 3], default=None,
        help="run only repeat K (folder _K) and write only that folder, so a crashed repeat can be re-run alone. "
             "Cannot be combined with --repeat > 1. The existing-folder guard of a non-default run still applies",
    )
    parser.add_argument("--papers", help="comma-separated paper_id substrings to further narrow scope")
    parser.add_argument("--estimate", action="store_true", help="print a cost estimate, zero LLM calls")
    parser.add_argument("--dry-run", action="store_true", help="print what would be replayed, zero LLM calls")
    parser.add_argument(
        "--cache", action="store_true",
        help="explicit context caching of the system prompt + paper for the audit calls (BETA, default off). "
             "Stops the run (VOID_CACHE_FAILED, exit 2) at the first cache creation failure or cached-call API error",
    )
    parser.add_argument(
        "--scope-check", action="store_true",
        help="add the scope lister + checker and the combine step (default off; requires --cache, else ValueError). "
             "Cache TTL becomes 3600 s; output goes to exp1_{level}_scope_{n}",
    )
    parser.add_argument(
        "--max-inr", type=_positive_float, default=None,
        help="stop (status VOID_CAP_HIT, exit 2) once the running cost passes this many INR; default no cap",
    )
    parser.add_argument(
        "--auditor-model", default=None,
        help="model of the auditor call ONLY (default: the configured llm_claim_audit_model). The structurer, the "
             "fallback models and every other call keep their configured models; with --cache the cache is created "
             "with this model. Not valid with --scope-check. Output goes to exp1_{level}_{model}[-vertex]_{n}",
    )
    parser.add_argument(
        "--out-tag", default=None, metavar="TAG",
        help="non-default runs only (--backend vertex / --auditor-model): add -TAG to the output folder names, "
             "exp1_{level}_{model}[-vertex]-TAG_{n}, so a run never meets an earlier run's folders. Letters, digits "
             "and '-'. With the tag, --estimate also refuses when the tagged folders exist",
    )
    backend_options.add_backend_args(parser)
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
