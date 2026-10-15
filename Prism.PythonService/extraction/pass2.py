"""Experiment 3's pass-2 windowed "copy-only" extractor calls.

One structured-output call per window (extraction/windowing.py), using the
same Gemini call path as the pass-1 extractor (_call_gemini_structured) but
asking only for a plain JSON list of verbatim sentences, not full claim
objects.

SentenceListLLM lives here, not in extraction/schemas.py: schemas.py's bytes
are part of the prompt hash (extraction/prompt_version.py), so adding
anything there - even an unrelated class - would change get_prompt_version()
even with EXTRACTOR_SECOND_PASS off.

Behind config.settings.extractor_second_pass (default off); see
extraction/engine.py::extract_claims for how this wires into the pipeline,
and extraction/merge.py for how pass-2 sentences are grounded, deduplicated
against pass-1 claims, and merged in.
"""
import asyncio

from pydantic import BaseModel

from config import settings
from extraction.prompt_loader import build_gemini_messages_for_pass2
from extraction.windowing import make_windows


class SentenceListLLM(BaseModel):
    """Pass-2's structured-output schema: a plain list of verbatim sentences,
    deliberately far simpler than ClaimLLM - pass 2 only copies, it never
    judges grounding strength or selects evidence spans."""
    sentences: list[str]


async def _call_pass2_window(window_text: str, chat_id: str, correlation_id: str | None) -> list[str]:
    # Local import: extraction.engine imports this module at call time
    # (inside extract_claims), not at module load time, so importing engine
    # here at call time avoids a circular import at module load.
    from extraction import engine

    result = await engine._call_gemini_structured(
        messages=build_gemini_messages_for_pass2(window_text),
        response_schema=SentenceListLLM,
        chat_id=chat_id,
        correlation_id=correlation_id,
        log_subdir="pass2",
        model_name=settings.llm_extraction_model,
        fallback_model=settings.llm_extraction_fallback_model,
    )
    return result.sentences


async def _call_pass2_window_bounded(
    semaphore: asyncio.Semaphore, window_text: str, chat_id: str, correlation_id: str | None
) -> list[str]:
    async with semaphore:
        return await _call_pass2_window(window_text, chat_id, correlation_id)


async def run_pass2(paper_text: str, chat_id: str, correlation_id: str | None = None) -> tuple[list[str], int]:
    """Runs one pass-2 call per window over paper_text, concurrently (bounded
    by the same concurrency cap extraction/engine.py uses for audit/structure
    calls), and returns every raw sentence from every window - unfiltered and
    not yet deduplicated against pass-1 claims or against each other. See
    extraction/merge.py::merge_pass2_claims for the grounding/dedup step.

    Returns (sentences, failed_window_count): a window whose call raises
    (after extraction/engine.py's own retry/fallback is exhausted) is logged
    and skipped rather than failing the whole paper - its sentences are
    simply missing from the result, counted in failed_window_count.
    """
    # Local import: extraction.engine imports this module at call time
    # (inside extract_claims), not at module load time - importing engine
    # here (rather than at this module's top level) avoids a circular import
    # at module load, same convention as _call_pass2_window below.
    from extraction.engine import AUDIT_STRUCTURE_CONCURRENCY

    windows = make_windows(paper_text)
    if not windows:
        return [], 0

    semaphore = asyncio.Semaphore(AUDIT_STRUCTURE_CONCURRENCY)
    results = await asyncio.gather(
        *(_call_pass2_window_bounded(semaphore, window, chat_id, correlation_id) for window in windows),
        return_exceptions=True,
    )
    sentences: list[str] = []
    failed_window_count = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[pass2] window {i} failed: {type(result).__name__}: {result}")
            failed_window_count += 1
            continue
        sentences.extend(result)
    return sentences, failed_window_count
