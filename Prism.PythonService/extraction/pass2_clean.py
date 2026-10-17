"""Clean-extraction attempt's pass-2 filter (S2 + S3).

docs/decisions.md, "Clean-extraction attempt revised: extraction-only
marks - 2026-10-17" and its amendment "...new pass-2 prompt + filter -
2026-10-17". Behind config.settings.extractor_pass2_clean (default off),
active only when config.settings.extractor_second_pass is also on - see
extraction/engine.py::extract_claims, which calls filter_merged_claims after
extraction/merge.py::merge_pass2_claims, never instead of it.

S1 (the References/Bibliography/Acknowledgments-heading section cut) was
tried and removed per the amendment's section-check result - it is not
implemented here at all.

S2 (free, no LLM): for each pass-2 candidate, the top
NEIGHBOUR_TOP_N neighbours by rapidfuzz.fuzz.token_set_ratio on
normalize_for_match text, drawn from the paper's pass-1 claims plus every
pass-2 candidate earlier in the merged list. "Earlier" is positional, not
decision-dependent: by the time this filter runs, extraction/merge.py has
already self-deduplicated the pass-2 subset against itself (see its own
docstring), so there are no near-duplicate pass-2 candidates left for S3's
own "same" decision on one candidate to change what an earlier-position
candidate's neighbour pool should have been. This also lets every
candidate's neighbour pool be computed up front, before any S3 call, so S3
can run as one (or a few, if > BATCH_SIZE candidates) concurrent batched
call per paper, rather than a strictly sequential one-candidate-at-a-time
loop.

S3 (one or more batched structured-output calls per paper, via
extraction.engine._call_gemini_structured, same model/fallback as pass 2):
each candidate is judged is_paper_claim + its relation (same/broader/
narrower/different) to each of its S2 neighbours. A candidate is dropped
only if is_paper_claim is false OR any relation is "same" - broader and
narrower relations never cause a drop. A batch whose call raises (after
extraction/engine.py's own retry/fallback is exhausted), or whose response
item count does not match the batch size sent, is never fatal: every item
in that batch is kept (not dropped - an undecided item must not silently
disappear) and the paper is marked incomplete.

Hard rules (never violated by this module): pass-1 claims are never
mutated, reordered, or dropped; a kept pass-2 candidate's text is never
rewritten; no two claims are ever merged into one. The output is always
exactly pass-1's claims (unchanged, in their original order) followed by
the kept pass-2 subset (in its original order).
"""
import asyncio
import re
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz

from config import settings
from extraction.grounding import RAPIDFUZZ_THRESHOLD, normalize_for_match, normalize_with_map
from extraction.prompt_loader import build_gemini_messages_for_pass2_clean_filter

BATCH_SIZE = 60
NEIGHBOUR_TOP_N = 3

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


class RelationLLM(BaseModel):
    """One candidate-to-neighbour relation judgment."""

    neighbour_id: str
    relation: Literal["same", "broader", "narrower", "different"]


class CleanFilterItemLLM(BaseModel):
    """S3's structured-output schema for one candidate - deliberately kept
    outside extraction/schemas.py: that module's bytes are hashed by
    extraction/prompt_version.py even when extractor_pass2_clean is off, so
    adding anything there would move the flag-off hash. Lives here instead,
    same convention as extraction/pass2.py's SentenceListLLM - though in
    this module's case it's moot either way, since this file is never in
    any of prompt_version.py's hashed-file lists."""

    reasoning: str
    is_paper_claim: bool
    reason_code: Literal[
        "own_claim", "positioning", "premise", "setup_or_method_detail",
        "other_work", "future_work", "definition", "heading_or_fragment", "other",
    ]
    relations: list[RelationLLM]


class CleanFilterBatchLLM(BaseModel):
    """One batch's worth of CleanFilterItemLLM, in request order."""

    items: list[CleanFilterItemLLM]


def _sentence_bounds(text: str) -> list[tuple[int, int]]:
    """Returns [(start, end)] for every sentence in text, split on
    whitespace following a sentence-ending punctuation mark. A regex
    heuristic only - never used for grounding, only to size a +/-1-sentence
    context window for the filter's LLM call."""
    bounds = []
    start = 0
    for m in _SENTENCE_BOUNDARY_RE.finditer(text):
        bounds.append((start, m.start()))
        start = m.end()
    bounds.append((start, len(text)))
    return bounds


def locate_context(candidate_text: str, paper_text: str) -> str | None:
    """Locates candidate_text in paper_text (raw alignment first, NFKC-
    normalized alignment as fallback - the same two-stage approach
    extraction/grounding.py's own span-audit context lookup and
    eval/exp3_b4.py::_locate_context use, reimplemented locally here rather
    than imported from eval/ - extraction/ code must not import from eval/),
    then returns the sentence containing the match plus one full sentence
    immediately before and after it.

    Returns None if the candidate cannot be located above
    RAPIDFUZZ_THRESHOLD by either alignment. Per the amended decision, a
    None here must never cause a drop - the caller sends the candidate to
    S3 without context rather than skipping or failing it.
    """
    alignment = fuzz.partial_ratio_alignment(candidate_text, paper_text)
    span: tuple[int, int] | None = None
    if alignment.score >= RAPIDFUZZ_THRESHOLD and alignment.dest_end > alignment.dest_start:
        span = (alignment.dest_start, alignment.dest_end)
    else:
        norm_paper, idx_map = normalize_with_map(paper_text)
        if norm_paper == normalize_for_match(paper_text):
            norm_alignment = fuzz.partial_ratio_alignment(normalize_for_match(candidate_text), norm_paper)
            if norm_alignment.score >= RAPIDFUZZ_THRESHOLD and norm_alignment.dest_end > norm_alignment.dest_start:
                span = (idx_map[norm_alignment.dest_start], idx_map[norm_alignment.dest_end - 1] + 1)
    if span is None:
        return None

    bounds = _sentence_bounds(paper_text)
    match_start, match_end = span
    idx = next(
        (i for i, (s, e) in enumerate(bounds) if s <= match_start < e or s < match_end <= e),
        None,
    )
    if idx is None:
        # The match straddles a boundary this regex heuristic missed - fall
        # back to the raw matched span alone rather than guessing an index.
        return paper_text[match_start:match_end].strip()
    lo = max(0, idx - 1)
    hi = min(len(bounds) - 1, idx + 1)
    return paper_text[bounds[lo][0]:bounds[hi][1]].strip()


def _top_neighbours(candidate_norm_text: str, pool: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """pool: [(id, text)]. Returns the top NEIGHBOUR_TOP_N by
    fuzz.token_set_ratio against candidate_norm_text (already normalized),
    normalizing each pool text at comparison time."""
    scored = sorted(pool, key=lambda pair: -fuzz.token_set_ratio(candidate_norm_text, normalize_for_match(pair[1])))
    return scored[:NEIGHBOUR_TOP_N]


async def _call_filter_batch(
    batch_items: list[dict], chat_id: str, correlation_id: str | None, thinking_level: str | None,
) -> list[CleanFilterItemLLM]:
    # Local import: avoids a circular import at module load, same
    # convention as extraction/pass2.py's own local `from extraction import
    # engine` inside its call functions.
    from extraction import engine

    result = await engine._call_gemini_structured(
        messages=build_gemini_messages_for_pass2_clean_filter(batch_items),
        response_schema=CleanFilterBatchLLM,
        chat_id=chat_id,
        correlation_id=correlation_id,
        log_subdir="pass2_clean",
        model_name=settings.llm_extraction_model,
        fallback_model=settings.llm_extraction_fallback_model,
        thinking_level=thinking_level,
    )
    return result.items


def _build_items(merged_claims: list[dict], paper_text: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Splits merged_claims into (pass1_claims, pass2_claims, items), where
    items[j] is {"id", "candidate", "context", "neighbours", "claim"} for
    pass2_claims[j], built in order so each candidate's neighbour pool only
    ever contains pass-1 claims plus pass-2 candidates positioned earlier in
    this same list (see this module's docstring on why "earlier" is
    positional, not S3-decision-dependent)."""
    pass1_claims = [c for c in merged_claims if c.get("pass") != "pass2"]
    pass2_claims = [c for c in merged_claims if c.get("pass") == "pass2"]

    pool: list[tuple[str, str]] = [(f"C{i}", c["claim_text_verbatim"]) for i, c in enumerate(pass1_claims)]
    items: list[dict] = []
    for j, claim in enumerate(pass2_claims):
        candidate_id = f"P{j}"
        text = claim["claim_text_verbatim"]
        neighbours = _top_neighbours(normalize_for_match(text), pool)
        items.append({
            "id": candidate_id,
            "candidate": text,
            "context": locate_context(text, paper_text),
            "neighbours": [{"id": nid, "text": ntext} for nid, ntext in neighbours],
            "claim": claim,
        })
        pool.append((candidate_id, text))
    return pass1_claims, pass2_claims, items


async def filter_merged_claims(
    merged_claims: list[dict],
    paper_text: str,
    chat_id: str,
    correlation_id: str | None = None,
    thinking_level: str | None = None,
) -> dict:
    """Runs S2 + S3 over merged_claims' pass-2 subset and returns:

        filtered_claims: pass1_claims (unchanged, original order) + the
            kept pass-2 subset (original order).
        decisions: {candidate_id: {"decision", "reason_code", "relations",
            "is_paper_claim"}} for every pass-2 candidate - "decision" is
            one of "kept", "dropped", or "kept_undecided_failed_batch".
        incomplete: True if any batch failed (call error, or a response
            item count mismatch).
        failed_batch_count: number of batches that failed.
        pre_filter_pass2_count / post_filter_pass2_count: sizes for
            reporting pre- vs. post-filter counts (the amended decision's
            --no-filter report requirement).

    thinking_level mirrors whatever pass 2 itself used for this run (the
    amended decision's "same model and thinking LOW as pass 2") - passed
    through explicitly by the caller, never read from settings directly
    here (matching extraction/pass2.py's own convention).
    """
    pass1_claims, pass2_claims, items = _build_items(merged_claims, paper_text)

    decisions: dict[str, dict] = {}
    incomplete = False
    failed_batch_count = 0

    if items:
        from extraction.engine import AUDIT_STRUCTURE_CONCURRENCY

        semaphore = asyncio.Semaphore(AUDIT_STRUCTURE_CONCURRENCY)
        batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]

        async def _run_batch(batch: list[dict]) -> None:
            nonlocal incomplete, failed_batch_count
            try:
                async with semaphore:
                    results = await _call_filter_batch(batch, chat_id, correlation_id, thinking_level)
                if len(results) != len(batch):
                    raise ValueError(f"batch size mismatch: sent {len(batch)}, got {len(results)}")
            except Exception as exc:
                print(
                    f"[pass2_clean] chat_id={chat_id} correlation_id={correlation_id} "
                    f"batch of {len(batch)} failed, keeping all its items: {type(exc).__name__}: {exc}"
                )
                failed_batch_count += 1
                incomplete = True
                for item in batch:
                    decisions[item["id"]] = {
                        "decision": "kept_undecided_failed_batch",
                        "reason_code": None,
                        "relations": [],
                        "is_paper_claim": None,
                    }
                return

            for item, result in zip(batch, results):
                relations = [{"neighbour_id": r.neighbour_id, "relation": r.relation} for r in result.relations]
                is_same = any(r.relation == "same" for r in result.relations)
                drop = (not result.is_paper_claim) or is_same
                decisions[item["id"]] = {
                    "decision": "dropped" if drop else "kept",
                    "reason_code": result.reason_code,
                    "relations": relations,
                    "is_paper_claim": result.is_paper_claim,
                }

        await asyncio.gather(*(_run_batch(batch) for batch in batches))

    kept_claims = [item["claim"] for item in items if decisions[item["id"]]["decision"] != "dropped"]
    filtered_claims = pass1_claims + kept_claims

    return {
        "filtered_claims": filtered_claims,
        "decisions": decisions,
        "incomplete": incomplete,
        "failed_batch_count": failed_batch_count,
        "pre_filter_pass2_count": len(pass2_claims),
        "post_filter_pass2_count": len(kept_claims),
    }
