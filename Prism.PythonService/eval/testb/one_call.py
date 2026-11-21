"""CLI: test B - one gemini-4-carbon call per whole dev paper (docs/evals/dev_eval.json,
12 papers), model pinned, never falling back to another model. Calls
client.models.generate_content directly (no extraction/engine.py helpers, which fall
back to a different model on retryable failure) with response_schema=OneCallResult
and thinking_level=MEDIUM. Cost is priced with eval.replay_audit._gemini_record_cost_usd
(reused, not reimplemented), so cached tokens are never double-counted.

Backend: build_genai_client is always called with the active backend left at its
default (AI Studio). This module never calls eval.backend_options.set_backend. The
client's own `.vertexai` flag is checked right after it is built; if it is ever True,
the run stops immediately with status WRONG_BACKEND before anything is written.

Errors per call: a 403 aborts the whole run at once (status ACCESS_DENIED). A 429, a
5xx, a timeout/connection error, an unparseable/invalid JSON response, or
finish_reason == MAX_TOKENS waits 30s and retries once; a second such failure marks
that paper FAILED for this run and the run continues with the next paper. Any other
4xx (e.g. 400) aborts the whole run at once (status API_ERROR).

Usage (from Prism.PythonService):
  uv run python -m eval.testb.one_call --estimate --out DIR
  uv run python -m eval.testb.one_call --smoke
  uv run python -m eval.testb.one_call --run-index 1 --out DIR --max-inr 50

--out DIR (run-index mode only) must be OUTSIDE the git repo; DIR itself may already
exist (runs 2 and 3 reuse the same DIR as run 1), but DIR/run_K must not - refused
otherwise. Writes DIR/run_K/<paper_id>.json and DIR/run_K/_summary.json.
--estimate makes no generate call (client.models.count_tokens only); --smoke makes one
real generate call on a made-up 3-sentence string held in this file (never a real
paper) and writes nothing anywhere. Console output never holds paper or claim text:
only ids, counts, tokens and INR.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from google.genai import errors, types
from pydantic import ValidationError

from config import settings
from eval import pricing
from eval.exp3_b4 import _extract_pdf_text, _resolve_pdf
from eval.matrix_loader import load_matrix
from eval.replay_audit import CallRecord, _gemini_record_cost_usd
from eval.testb.one_call_schemas import PROMPT_PATH, OneCallResult, prompt_hash
from extraction import llm_backend

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"

MODEL = "gemini-4-carbon"
THINKING_LEVEL = "medium"
MAX_OUTPUT_TOKENS = 32768
RETRY_WAIT_SECONDS = 30
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

LOW_ASSUMED_OUTPUT_TOKENS = 8000
HIGH_ASSUMED_OUTPUT_TOKENS = 24000
ESTIMATE_CALLS_PER_RUN = 12
ESTIMATE_RUNS = 3

# Held in code, never a real paper (--smoke must never touch a research PDF).
SMOKE_PAPER_TEXT = (
    "This is a made-up test paper for a smoke test. "
    "It claims in its introduction that the method improves accuracy by 10 points. "
    "The results section reports only a 2-point improvement on one of three benchmarks."
)


class WrongBackendError(Exception):
    """The genai client is on Vertex, not AI Studio."""


class RunAborted(Exception):
    """Stops the whole run immediately. .status is the _summary.json status."""

    def __init__(self, status: str, message: str = ""):
        super().__init__(message or status)
        self.status = status


class _RetryableFailure(Exception):
    """Invalid/unparseable JSON or finish_reason MAX_TOKENS - same retry path as 429/5xx."""


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _ensure_aistudio(client) -> None:
    if client.vertexai:
        raise WrongBackendError(
            "genai client is on Vertex (vertexai=True), not AI Studio; eval.testb never calls set_backend"
        )


def _build_client():
    client = llm_backend.build_genai_client(settings.ai_api_key)
    _ensure_aistudio(client)
    return client


def _dev_papers():
    """PaperSpec list from dev_eval.json, in the file's own order."""
    return load_matrix(DEFAULT_DEV_EVAL_PATH).papers


def _paper_text(paper_id: str) -> str:
    return _extract_pdf_text(_resolve_pdf(paper_id))


def _prompt_prefix() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _prompt_text_for_paper(paper_text: str) -> str:
    return _prompt_prefix() + paper_text


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=OneCallResult,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel(THINKING_LEVEL.upper())),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def _contents(prompt_text: str) -> list[types.Content]:
    return [types.Content(role="user", parts=[types.Part.from_text(text=prompt_text)])]


def _usage_fields(response) -> dict:
    usage = getattr(response, "usage_metadata", None)
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None) or 0,
        "output_tokens": getattr(usage, "candidates_token_count", None) or 0,
        "thought_tokens": getattr(usage, "thoughts_token_count", None) or 0,
        "cached_tokens": getattr(usage, "cached_content_token_count", None) or 0,
    }


def _finish_reason(response) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    raw = getattr(candidates[0], "finish_reason", None)
    if raw is None:
        return None
    return getattr(raw, "value", None) or str(raw)


def _cost_inr(usage: dict, model: str = MODEL) -> float:
    """Mirrors eval.replay_audit._gemini_record_cost_usd exactly (reused, not
    reimplemented): prompt includes cached tokens, so cached is never billed twice."""
    record = CallRecord(
        stage="testb_one_call",
        paper_id="",
        claim_index=0,
        thinking_level=THINKING_LEVEL,
        model_used=model,
        prompt_tokens=usage["prompt_tokens"],
        output_tokens=usage["output_tokens"],
        thought_tokens=usage["thought_tokens"],
        total_tokens=usage["prompt_tokens"] + usage["output_tokens"] + usage["thought_tokens"],
        latency_s=0.0,
        cached_tokens=usage["cached_tokens"],
    )
    usd, _priced_at_own_rate = _gemini_record_cost_usd(record)
    return usd * pricing.INR_PER_USD


def _classify_api_error(exc: errors.APIError) -> str:
    code = getattr(exc, "code", None) or 0
    if code == 403:
        return "ACCESS_DENIED"
    if code in RETRYABLE_STATUS_CODES:
        return "RETRY"
    return "API_ERROR"


def _call_once(client, prompt_text: str):
    response = client.models.generate_content(model=MODEL, contents=_contents(prompt_text), config=_config())
    finish_reason = _finish_reason(response)
    if finish_reason == "MAX_TOKENS":
        raise _RetryableFailure(f"finish_reason={finish_reason}")
    try:
        parsed = getattr(response, "parsed", None)
    except TypeError as exc:
        # response.parsed can itself raise (e.g. the SDK's own parse-on-access failing
        # on a blocked/empty response) instead of just returning None.
        raise _RetryableFailure(f"response.parsed raised: {exc!r}") from exc
    if parsed is None:
        raw_text = getattr(response, "text", None)
        if not raw_text:
            # Blocked, empty or cut-off answer: response.text is None or "". Treated
            # exactly like invalid JSON - never passed to json.loads, which would
            # otherwise raise TypeError (None) or JSONDecodeError ("").
            raise _RetryableFailure(f"empty response text (raw_text={raw_text!r})")
        try:
            parsed = OneCallResult.model_validate(json.loads(raw_text, strict=False))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise _RetryableFailure(f"invalid JSON: {exc!r}") from exc
    return response, parsed, finish_reason


def _call_paper_with_retry(client, prompt_text: str) -> dict:
    """{status: OK, response, parsed, finish_reason, attempts} or {status: FAILED,
    attempts, error}. Raises RunAborted (ACCESS_DENIED / API_ERROR) for a 403 or any
    other non-retryable 4xx - the caller must not catch per-paper failures for those."""
    last_error = None
    for attempt in (1, 2):
        try:
            response, parsed, finish_reason = _call_once(client, prompt_text)
            return {"status": "OK", "response": response, "parsed": parsed, "finish_reason": finish_reason, "attempts": attempt}
        except errors.APIError as exc:
            kind = _classify_api_error(exc)
            if kind in ("ACCESS_DENIED", "API_ERROR"):
                raise RunAborted(kind, str(exc)) from exc
            last_error = repr(exc)
        except (TimeoutError, ConnectionError) as exc:
            last_error = repr(exc)
        except _RetryableFailure as exc:
            last_error = str(exc)
        if attempt == 1:
            _sleep(RETRY_WAIT_SECONDS)
    return {"status": "FAILED", "attempts": 2, "error": last_error}


def _validate_out_dir(out_dir: Path) -> None:
    """DIR itself may already exist - run 2 and run 3 reuse the same DIR as run 1.
    Only DIR/run_K (checked separately, by _validate_run_dir) must not exist."""
    repo_root = REPO_ROOT.resolve()
    resolved = out_dir.resolve()
    if resolved == repo_root or resolved.is_relative_to(repo_root):
        raise ValueError(f"--out {out_dir} is inside the git repo ({repo_root}); refusing")


def _validate_run_dir(run_dir: Path) -> None:
    if run_dir.exists():
        raise ValueError(f"{run_dir} already exists; refusing to overwrite")


def _write_summary(run_dir: Path, run_index: int, phash: str, papers_ok: int, papers_failed: int, total_inr: float, status: str) -> None:
    summary = {
        "run_index": run_index,
        "model": MODEL,
        "thinking_level": THINKING_LEVEL,
        "prompt_hash": phash,
        "papers_ok": papers_ok,
        "papers_failed": papers_failed,
        "total_inr": total_inr,
        "status": status,
    }
    (run_dir / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def run_index_cmd(run_index: int, out_dir: Path, max_inr: float) -> str:
    client = _build_client()
    _validate_out_dir(out_dir)
    run_dir = out_dir / f"run_{run_index}"
    _validate_run_dir(run_dir)
    run_dir.mkdir(parents=True)

    phash = prompt_hash()
    total_inr = 0.0
    papers_ok = 0
    papers_failed = 0
    status = "OK"
    try:
        for paper in _dev_papers():
            started = datetime.now(timezone.utc).isoformat()
            prompt_text = _prompt_text_for_paper(_paper_text(paper.paper_id))
            result = _call_paper_with_retry(client, prompt_text)
            finished = datetime.now(timezone.utc).isoformat()

            if result["status"] == "OK":
                response = result["response"]
                usage = _usage_fields(response)
                cost_inr = _cost_inr(usage)
                total_inr += cost_inr
                papers_ok += 1
                parsed = result["parsed"]
                record = {
                    "status": "OK",
                    "raw_text": getattr(response, "text", None),
                    "parsed": parsed.model_dump() if parsed is not None else None,
                    "usage": usage,
                    "cost_inr": cost_inr,
                    "model_version": getattr(response, "model_version", None),
                    "finish_reason": result["finish_reason"],
                    "attempts": result["attempts"],
                    "started": started,
                    "finished": finished,
                }
                claim_count = len(parsed.claims) if parsed is not None else 0
                print(f"{paper.paper_id} status=OK claims={claim_count} cost_inr={cost_inr:.4f} total_inr={total_inr:.4f}")
            else:
                papers_failed += 1
                record = {
                    "status": "FAILED",
                    "raw_text": None,
                    "parsed": None,
                    "usage": None,
                    "cost_inr": 0.0,
                    "model_version": None,
                    "finish_reason": None,
                    "attempts": result["attempts"],
                    "started": started,
                    "finished": finished,
                    "error": result.get("error"),
                }
                print(f"{paper.paper_id} status=FAILED attempts={result['attempts']}")

            (run_dir / f"{paper.paper_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

            if total_inr > max_inr:
                status = "CAPPED"
                break
    except RunAborted as exc:
        status = exc.status

    _write_summary(run_dir, run_index, phash, papers_ok, papers_failed, total_inr, status)
    print(f"status={status} papers_ok={papers_ok} papers_failed={papers_failed} total_inr={total_inr:.4f}")
    return status


def run_estimate_cmd() -> str:
    client = _build_client()
    papers = _dev_papers()
    phash = prompt_hash()
    per_paper_tokens = []
    total_input = 0
    for paper in papers:
        prompt_text = _prompt_text_for_paper(_paper_text(paper.paper_id))
        # list[types.Content] is a valid ContentListUnion member at runtime, but
        # pyright's invariant list typing rejects it without this cast; the SDK
        # receives the exact same list either way.
        result = client.models.count_tokens(model=MODEL, contents=cast(types.ContentListUnion, _contents(prompt_text)))
        tokens = getattr(result, "total_tokens", None) or 0
        per_paper_tokens.append(tokens)
        total_input += tokens
        print(f"{paper.paper_id} input_tokens={tokens}")
    print(f"total_input_tokens_{ESTIMATE_CALLS_PER_RUN}_calls={total_input}")

    suggested_max_inr = 0.0
    for label, assumed_output in (("LOW", LOW_ASSUMED_OUTPUT_TOKENS), ("HIGH", HIGH_ASSUMED_OUTPUT_TOKENS)):
        print(f"ASSUMPTION {label}_output_plus_thought_tokens_per_call={assumed_output}")
        inr_per_run = sum(
            (pricing.cost_usd_for_model(MODEL, tokens, assumed_output, thought=0.0, cached=0.0) or 0.0)
            for tokens in per_paper_tokens
        ) * pricing.INR_PER_USD
        print(f"inr_{label.lower()}_{ESTIMATE_CALLS_PER_RUN}_calls={inr_per_run:.2f}")
        print(f"inr_{label.lower()}_{ESTIMATE_CALLS_PER_RUN * ESTIMATE_RUNS}_calls={inr_per_run * ESTIMATE_RUNS:.2f}")
        if label == "HIGH":
            suggested_max_inr = 1.3 * inr_per_run

    print(f"suggested run-1 --max-inr = {suggested_max_inr:.2f} (1.3 x HIGH, {ESTIMATE_CALLS_PER_RUN} calls)")
    print(f"prompt_hash={phash}")
    return "OK"


def run_smoke_cmd() -> str:
    client = _build_client()
    prompt_text = _prompt_prefix() + SMOKE_PAPER_TEXT
    try:
        result = _call_paper_with_retry(client, prompt_text)
    except RunAborted as exc:
        print(f"status={exc.status}")
        return exc.status

    if result["status"] == "FAILED":
        print(f"status=FAILED attempts={result['attempts']}")
        return "FAILED"

    response = result["response"]
    parsed = result["parsed"]
    usage = _usage_fields(response)
    cost_inr = _cost_inr(usage)
    claim_count = len(parsed.claims) if parsed is not None else 0
    print(
        f"status=OK claims={claim_count} prompt_tokens={usage['prompt_tokens']} "
        f"thought_tokens={usage['thought_tokens']} output_tokens={usage['output_tokens']} "
        f"cost_inr={cost_inr:.4f} finish_reason={result['finish_reason']} "
        f"model_version={getattr(response, 'model_version', None)}"
    )
    return "OK"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-index", type=int, choices=(1, 2, 3))
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-inr", type=float)
    args = parser.parse_args(argv)

    modes_set = sum(1 for m in (args.run_index is not None, args.estimate, args.smoke) if m)
    if modes_set != 1:
        parser.error("exactly one of --run-index, --estimate or --smoke is required")
    if args.run_index is not None:
        if args.out is None:
            parser.error("--run-index requires --out")
        if args.max_inr is None:
            parser.error("--run-index requires --max-inr")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.estimate:
            status = run_estimate_cmd()
        elif args.smoke:
            status = run_smoke_cmd()
        else:
            status = run_index_cmd(args.run_index, args.out, args.max_inr)
    except WrongBackendError as exc:
        print(f"status=WRONG_BACKEND ({exc})")
        return 1
    except ValueError as exc:
        print(f"status=REFUSED ({exc})")
        return 1
    return 0 if status == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
