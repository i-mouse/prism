"""Pure merge/dedup logic for Experiment 3's pass-2 windowed extraction.

No I/O, no LLM calls. Two steps:

1. Verbatim grounding: each pass-2 sentence must independently pass the same
   Stage-1 check real evidence spans are held to in extraction/grounding.py
   (fuzz.partial_ratio >= RAPIDFUZZ_THRESHOLD after normalize_for_match)
   against the raw paper text, or it is dropped as ungrounded.

2. Dedup: a grounded pass-2 sentence is dropped as a duplicate only when
   fuzz.ratio (NOT partial_ratio) after normalize_for_match scores >= 88
   against a pass-1 claim's claim_text_verbatim, or against an already-kept
   pass-2 sentence (self-dedup across overlapping windows). partial_ratio is
   deliberately not used for this decision: it would drop a short claim that
   sits inside a longer sentence, which is exactly the E3 shape this
   experiment targets - see docs/decisions.md's "Experiment 3 B1 review"
   entry. A sentence with a high partial_ratio match but a ratio below the
   dedup threshold is kept and flagged as kept_but_contained for hand review.

pass1_claims is the plain-dict shape extract_claims has before audit/
structure runs (extraction/engine.py:370-371: {"claim_text_verbatim": ...,
"claim_summary": ...}) - evidence_spans do not exist yet at this point in the
pipeline, so dedup compares against claim_text_verbatim only. The merged
output carries a "pass" key ("pass1"/"pass2") on each claim dict for
provenance - this is a plain dict key, never a extraction/schemas.py field,
so it never reaches Pydantic validation and never affects the prompt hash.
"""
from rapidfuzz import fuzz

from extraction.grounding import RAPIDFUZZ_THRESHOLD, _stage1_score, normalize_for_match

DEDUP_THRESHOLD = 88


def ground_pass2_sentences(sentences: list[str], paper_text: str) -> tuple[list[str], int]:
    """Returns (grounded_sentences, dropped_ungrounded_count)."""
    grounded: list[str] = []
    dropped = 0
    for sentence in sentences:
        if _stage1_score(sentence, paper_text, normalize=True) >= RAPIDFUZZ_THRESHOLD:
            grounded.append(sentence)
        else:
            dropped += 1
    return grounded, dropped


def _best_match_by_ratio(sentence: str, candidates: list[str]) -> tuple[str | None, float, float]:
    """Finds the candidate with the highest fuzz.ratio against sentence
    (both normalized), returning (candidate, ratio_score, partial_ratio_score
    against that same candidate). (None, 0.0, 0.0) if candidates is empty.
    """
    norm_sentence = normalize_for_match(sentence)
    best_candidate: str | None = None
    best_ratio = 0.0
    best_partial = 0.0
    for candidate in candidates:
        norm_candidate = normalize_for_match(candidate)
        ratio = fuzz.ratio(norm_sentence, norm_candidate)
        if best_candidate is None or ratio > best_ratio:
            best_candidate = candidate
            best_ratio = ratio
            best_partial = fuzz.partial_ratio(norm_sentence, norm_candidate)
    return best_candidate, best_ratio, best_partial


def _max_partial_ratio(sentence: str, candidates: list[str]) -> tuple[str | None, float]:
    """Finds the candidate with the highest fuzz.partial_ratio against
    sentence (both normalized), independent of which candidate wins on
    fuzz.ratio - a sentence can be nested inside a candidate that is not the
    best overall ratio match. (None, 0.0) if candidates is empty."""
    norm_sentence = normalize_for_match(sentence)
    best_candidate: str | None = None
    best_partial = 0.0
    for candidate in candidates:
        partial = fuzz.partial_ratio(norm_sentence, normalize_for_match(candidate))
        if best_candidate is None or partial > best_partial:
            best_candidate = candidate
            best_partial = partial
    return best_candidate, best_partial


def merge_pass2_claims(pass1_claims: list[dict], pass2_sentences: list[str], paper_text: str) -> dict:
    """Grounds, dedups, and merges Experiment 3's pass-2 sentences into the
    pass-1 claim list.

    Args:
        pass1_claims: plain dicts, each with at least "claim_text_verbatim".
        pass2_sentences: raw sentences from every pass-2 window (see
            extraction/pass2.py::run_pass2), not yet grounded or deduplicated.
        paper_text: the same raw text passed to both pass 1 and pass 2.

    Returns a dict with:
        merged_claims: a copy of pass1_claims (each tagged "pass": "pass1"),
            plus one dict per kept pass-2 sentence
            ({"claim_text_verbatim": s, "claim_summary": s, "pass": "pass2"}).
        dropped_ungrounded: count of pass-2 sentences that failed the
            Stage-1 verbatim check against paper_text.
        dropped_duplicate: list of {"sentence", "best_match", "ratio_score",
            "partial_ratio_score"} for sentences dropped as duplicates.
        kept_but_contained: same shape, for sentences kept despite a high
            partial_ratio match (nested inside a longer sentence) because
            their ratio_score stayed below DEDUP_THRESHOLD.
        kept_new: same shape (best_match may be None), for sentences with no
            close match at all.
    """
    pass1_texts = []
    for c in pass1_claims:
        text = c.get("claim_text_verbatim")
        if not text:
            print(f"[merge] skipping pass-1 claim with missing/empty claim_text_verbatim: {c!r}")
            continue
        pass1_texts.append(text)
    grounded, dropped_ungrounded = ground_pass2_sentences(pass2_sentences, paper_text)

    kept_pass2_texts: list[str] = []
    dropped_duplicate: list[dict] = []
    kept_but_contained: list[dict] = []
    kept_new: list[dict] = []

    for sentence in grounded:
        candidates = pass1_texts + kept_pass2_texts
        best_candidate, ratio_score, partial_score = _best_match_by_ratio(sentence, candidates)
        item = {
            "sentence": sentence,
            "best_match": best_candidate,
            "ratio_score": ratio_score,
            "partial_ratio_score": partial_score,
        }
        if best_candidate is not None and ratio_score >= DEDUP_THRESHOLD:
            dropped_duplicate.append(item)
            continue

        kept_pass2_texts.append(sentence)
        max_partial_candidate, max_partial_score = _max_partial_ratio(sentence, candidates)
        if max_partial_candidate is not None and max_partial_score >= RAPIDFUZZ_THRESHOLD:
            kept_but_contained.append({
                "sentence": sentence,
                "best_match": max_partial_candidate,
                "ratio_score": ratio_score,
                "partial_ratio_score": max_partial_score,
            })
        else:
            kept_new.append(item)

    merged_claims = [{**c, "pass": "pass1"} for c in pass1_claims] + [
        {"claim_text_verbatim": s, "claim_summary": s, "pass": "pass2"} for s in kept_pass2_texts
    ]

    return {
        "merged_claims": merged_claims,
        "dropped_ungrounded": dropped_ungrounded,
        "dropped_duplicate": dropped_duplicate,
        "kept_but_contained": kept_but_contained,
        "kept_new": kept_new,
    }
