"""Unit tests for extraction/merge.py's grounding/dedup/merge logic -
Experiment 3's pass-2 windowed extraction. No LLM calls; pure functions."""
from extraction.merge import DEDUP_THRESHOLD, ground_pass2_sentences, merge_pass2_claims


PAPER_TEXT = (
    "We find that our method achieves state-of-the-art results on all benchmarks. "
    "In principle, the approach should generalize to any tabular dataset, although "
    "we only test on three. We observed a sharp drop in latency after the fix. "
    "This sentence does not appear anywhere in the paper and is fabricated."
)


def test_grounded_sentence_passes_and_ungrounded_sentence_is_dropped():
    sentences = [
        "We find that our method achieves state-of-the-art results on all benchmarks.",
        "This sentence was never written by anyone, anywhere, ever.",
    ]
    grounded, dropped = ground_pass2_sentences(sentences, PAPER_TEXT)
    assert grounded == [sentences[0]]
    assert dropped == 1


def test_pass1_claim_exact_duplicate_is_dropped():
    pass1 = [{"claim_text_verbatim": "We find that our method achieves state-of-the-art results on all benchmarks."}]
    pass2_sentences = ["We find that our method achieves state-of-the-art results on all benchmarks."]
    result = merge_pass2_claims(pass1, pass2_sentences, PAPER_TEXT)
    assert len(result["dropped_duplicate"]) == 1
    assert result["kept_new"] == []
    assert result["kept_but_contained"] == []
    # merged_claims has pass1 (tagged) but no pass-2 addition.
    assert len(result["merged_claims"]) == 1
    assert result["merged_claims"][0]["pass"] == "pass1"


def test_short_claim_nested_in_longer_pass1_sentence_is_kept_not_dropped():
    """The E3 shape this experiment targets: a short pass-2 claim whose text
    is a substring of a much longer pass-1 sentence must survive dedup
    (partial_ratio would drop it; fuzz.ratio must not)."""
    long_sentence = (
        "Although our method is efficient on small inputs, it in principle "
        "generalizes to any tabular dataset of arbitrary size without modification."
    )
    short_nested_claim = "it in principle generalizes to any tabular dataset of arbitrary size"
    paper_text = f"Some preamble. {long_sentence} Some epilogue."

    pass1 = [{"claim_text_verbatim": long_sentence}]
    result = merge_pass2_claims(pass1, [short_nested_claim], paper_text)

    assert len(result["dropped_duplicate"]) == 0
    assert len(result["kept_but_contained"]) == 1
    assert result["kept_but_contained"][0]["sentence"] == short_nested_claim
    merged_texts = [c["claim_text_verbatim"] for c in result["merged_claims"]]
    assert short_nested_claim in merged_texts


def test_self_dedup_across_overlapping_windows():
    """The same sentence appearing twice (window overlap) is kept once."""
    sentence = "We observed a sharp drop in latency after the fix."
    pass1 = []
    result = merge_pass2_claims(pass1, [sentence, sentence], PAPER_TEXT)
    assert len(result["kept_new"]) == 1
    assert len(result["dropped_duplicate"]) == 1
    assert len(result["merged_claims"]) == 1


def test_kept_new_has_no_best_match():
    pass1 = []
    sentence = "We observed a sharp drop in latency after the fix."
    result = merge_pass2_claims(pass1, [sentence], PAPER_TEXT)
    assert len(result["kept_new"]) == 1
    assert result["kept_new"][0]["best_match"] is None


def test_claim_summary_is_filled_with_the_copied_sentence_no_extra_llm_call():
    sentence = "We observed a sharp drop in latency after the fix."
    result = merge_pass2_claims([], [sentence], PAPER_TEXT)
    pass2_claim = next(c for c in result["merged_claims"] if c["pass"] == "pass2")
    assert pass2_claim["claim_summary"] == sentence
    assert pass2_claim["claim_text_verbatim"] == sentence


def test_pass1_claims_without_a_pass_key_still_load_and_get_tagged():
    """Old-shape pass-1 claim dicts (no 'pass' key, as produced by today's
    extractor) must merge cleanly - the pass key is additive, never required
    on input."""
    pass1 = [{"claim_text_verbatim": "Some claim.", "claim_summary": "Some claim summary"}]
    result = merge_pass2_claims(pass1, [], PAPER_TEXT)
    assert len(result["merged_claims"]) == 1
    assert result["merged_claims"][0]["pass"] == "pass1"
    assert result["merged_claims"][0]["claim_text_verbatim"] == "Some claim."


def test_dedup_threshold_is_88():
    assert DEDUP_THRESHOLD == 88


def test_kept_but_contained_checks_partial_ratio_against_all_candidates():
    """Regression test for the single-best-match bug: kept_but_contained must
    report whichever candidate has the highest partial_ratio, even when a
    different candidate wins on fuzz.ratio (and is therefore not the
    candidate _best_match_by_ratio would have reported)."""
    # candidate_a shares a lot of words with the sentence (high fuzz.ratio)
    # but does not contain it verbatim (low partial_ratio).
    candidate_a = "The quick brown fox jumped over the lazy dog near the old barn."
    # candidate_b shares fewer words overall (lower fuzz.ratio than candidate_a)
    # but literally contains the sentence as a substring (high partial_ratio).
    candidate_b = "Some long preamble text. The quick brown fox jumped over the fence. More unrelated text follows here to pad it out."
    sentence = "The quick brown fox jumped over the fence"

    paper_text = f"{candidate_a} {candidate_b} {sentence}"
    pass1 = [{"claim_text_verbatim": candidate_a}, {"claim_text_verbatim": candidate_b}]

    result = merge_pass2_claims(pass1, [sentence], paper_text)

    assert len(result["dropped_duplicate"]) == 0
    assert len(result["kept_but_contained"]) == 1
    assert result["kept_but_contained"][0]["best_match"] == candidate_b


def test_pass1_claim_with_missing_or_empty_claim_text_verbatim_is_skipped_not_crashed():
    sentence = "We observed a sharp drop in latency after the fix."
    pass1 = [
        {"claim_summary": "no claim_text_verbatim key at all"},
        {"claim_text_verbatim": "", "claim_summary": "empty claim_text_verbatim"},
        {"claim_text_verbatim": "Some unrelated claim.", "claim_summary": "fine"},
    ]

    result = merge_pass2_claims(pass1, [sentence], PAPER_TEXT)

    # No crash, and the bad claims are excluded from the dedup candidate pool
    # (the new sentence isn't compared against them and isn't dropped as a
    # false duplicate of an empty string).
    merged_pass1 = [c for c in result["merged_claims"] if c["pass"] == "pass1"]
    assert len(merged_pass1) == 3
    assert merged_pass1[0].get("claim_text_verbatim") is None
    assert merged_pass1[1]["claim_text_verbatim"] == ""
    assert merged_pass1[2]["claim_text_verbatim"] == "Some unrelated claim."
    pass2_claim = next(c for c in result["merged_claims"] if c["pass"] == "pass2")
    assert pass2_claim["claim_text_verbatim"] == sentence
