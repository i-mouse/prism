"""Unit tests for extraction/pass2_clean.py - the clean-extraction
attempt's S2 (neighbour) + S3 (LLM filter) logic. No LLM calls -
extraction.engine._call_gemini_structured is faked throughout."""
import asyncio
import json

from extraction import engine, pass2_clean
from extraction.pass2_clean import CleanFilterBatchLLM, CleanFilterItemLLM, RelationLLM, filter_merged_claims

PAPER_TEXT = (
    "Intro sentence sets the scene. Our method achieves 90% accuracy on the benchmark. "
    "In principle, the method generalizes to any similar benchmark, though we only tested one. "
    "This is unrelated filler text that pads the paper out so sentence boundaries behave normally. "
    "This is merely a definition of a term used elsewhere in the paper."
)


def _merged(pass1_texts: list[str], pass2_texts: list[str]) -> list[dict]:
    merged = [{"claim_text_verbatim": t, "claim_summary": t, "pass": "pass1"} for t in pass1_texts]
    merged += [{"claim_text_verbatim": t, "claim_summary": t, "pass": "pass2"} for t in pass2_texts]
    return merged


def _decision_fake(decision_map: dict[str, dict]):
    """decision_map: {candidate_text: {"is_paper_claim", "reason_code", "relations"}}."""

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        payload = json.loads(user_msg)["candidates"]
        items = []
        for entry in payload:
            spec = decision_map[entry["candidate"]]
            items.append(CleanFilterItemLLM(
                reasoning="because",
                is_paper_claim=spec.get("is_paper_claim", True),
                reason_code=spec.get("reason_code", "own_claim"),
                relations=[
                    RelationLLM(neighbour_id=r["neighbour_id"], relation=r["relation"])
                    for r in spec.get("relations", [])
                ],
            ))
        return CleanFilterBatchLLM(items=items)

    return fake_call_gemini_structured


def test_not_a_claim_is_dropped(monkeypatch):
    merged = _merged(
        ["Our method achieves 90% accuracy on the benchmark."],
        ["This is merely a definition of a term used elsewhere in the paper."],
    )
    decision_map = {
        "This is merely a definition of a term used elsewhere in the paper.": {
            "is_paper_claim": False, "reason_code": "definition",
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["post_filter_pass2_count"] == 0
    assert [c["claim_text_verbatim"] for c in result["filtered_claims"]] == [
        "Our method achieves 90% accuracy on the benchmark."
    ]
    assert result["decisions"]["P0"]["decision"] == "dropped"


def test_same_relation_is_dropped_even_when_is_paper_claim_true(monkeypatch):
    merged = _merged(
        ["Our method achieves 90% accuracy on the benchmark."],
        ["Our method achieves 90% accuracy on the benchmark, confirmed."],
    )
    decision_map = {
        "Our method achieves 90% accuracy on the benchmark, confirmed.": {
            "is_paper_claim": True, "reason_code": "own_claim",
            "relations": [{"neighbour_id": "C0", "relation": "same"}],
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["post_filter_pass2_count"] == 0
    assert result["decisions"]["P0"]["decision"] == "dropped"


def test_broader_relation_is_never_dropped(monkeypatch):
    merged = _merged(
        ["Our method achieves 90% accuracy on the benchmark."],
        ["In principle, the method generalizes to any similar benchmark, though we only tested one."],
    )
    decision_map = {
        "In principle, the method generalizes to any similar benchmark, though we only tested one.": {
            "is_paper_claim": True, "reason_code": "positioning",
            "relations": [{"neighbour_id": "C0", "relation": "broader"}],
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["post_filter_pass2_count"] == 1
    assert result["decisions"]["P0"]["decision"] == "kept"


def test_narrower_relation_is_never_dropped(monkeypatch):
    merged = _merged(
        ["In principle, the method generalizes to any similar benchmark, though we only tested one."],
        ["Our method achieves 90% accuracy on the benchmark."],
    )
    decision_map = {
        "Our method achieves 90% accuracy on the benchmark.": {
            "is_paper_claim": True, "reason_code": "own_claim",
            "relations": [{"neighbour_id": "C0", "relation": "narrower"}],
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["post_filter_pass2_count"] == 1
    assert result["decisions"]["P0"]["decision"] == "kept"


def test_pass1_claims_never_mutated_reordered_or_dropped(monkeypatch):
    pass1_texts = ["First pass1 claim stays.", "Second pass1 claim stays."]
    merged = _merged(pass1_texts, ["This is merely a definition of a term used elsewhere in the paper."])
    decision_map = {
        "This is merely a definition of a term used elsewhere in the paper.": {
            "is_paper_claim": False, "reason_code": "definition",
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    pass1_out = [c for c in result["filtered_claims"] if c.get("pass") != "pass2"]
    assert [c["claim_text_verbatim"] for c in pass1_out] == pass1_texts


def test_order_preserved_for_kept_pass2_subset(monkeypatch):
    pass2_texts = [
        "Our method achieves 90% accuracy on the benchmark.",
        "In principle, the method generalizes to any similar benchmark, though we only tested one.",
    ]
    merged = _merged([], pass2_texts)
    decision_map = {
        pass2_texts[0]: {"is_paper_claim": True, "reason_code": "own_claim"},
        pass2_texts[1]: {"is_paper_claim": True, "reason_code": "positioning"},
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert [c["claim_text_verbatim"] for c in result["filtered_claims"]] == pass2_texts


def test_failed_batch_keeps_its_items_and_marks_incomplete(monkeypatch):
    merged = _merged([], ["Our method achieves 90% accuracy on the benchmark."])

    async def fake_fail(*args, **kwargs):
        raise RuntimeError("simulated batch failure")

    monkeypatch.setattr(engine, "_call_gemini_structured", fake_fail)

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["incomplete"] is True
    assert result["failed_batch_count"] == 1
    assert result["post_filter_pass2_count"] == 1
    assert result["decisions"]["P0"]["decision"] == "kept_undecided_failed_batch"


def test_batch_size_mismatch_keeps_its_items_and_marks_incomplete(monkeypatch):
    merged = _merged([], ["Our method achieves 90% accuracy on the benchmark."])

    async def fake_short_response(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        return CleanFilterBatchLLM(items=[])  # one item sent, zero returned

    monkeypatch.setattr(engine, "_call_gemini_structured", fake_short_response)

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["incomplete"] is True
    assert result["failed_batch_count"] == 1
    assert result["decisions"]["P0"]["decision"] == "kept_undecided_failed_batch"


def test_candidate_with_no_locatable_context_is_still_judged_not_auto_dropped(monkeypatch):
    unlocatable = "A sentence never written anywhere in the paper text at all."
    merged = _merged([], [unlocatable])
    decision_map = {unlocatable: {"is_paper_claim": True, "reason_code": "own_claim"}}
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["decisions"]["P0"]["decision"] == "kept"


def test_batching_splits_into_multiple_calls_when_over_batch_size(monkeypatch):
    pass2_texts = [f"Candidate sentence number {i} appears in the paper." for i in range(pass2_clean.BATCH_SIZE + 5)]
    paper_text = " ".join(pass2_texts)
    merged = _merged([], pass2_texts)
    decision_map = {t: {"is_paper_claim": True, "reason_code": "own_claim"} for t in pass2_texts}
    fake = _decision_fake(decision_map)
    call_sizes: list[int] = []

    async def counting_fake(messages, *args, **kwargs):
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        call_sizes.append(len(json.loads(user_msg)["candidates"]))
        return await fake(messages, *args, **kwargs)

    monkeypatch.setattr(engine, "_call_gemini_structured", counting_fake)

    result = asyncio.run(filter_merged_claims(merged, paper_text, chat_id="c1"))

    assert len(call_sizes) == 2
    assert sum(call_sizes) == len(pass2_texts)
    assert all(size <= pass2_clean.BATCH_SIZE for size in call_sizes)
    assert result["post_filter_pass2_count"] == len(pass2_texts)


def test_locate_context_returns_sentence_plus_one_each_side():
    text = "First sentence here. Our method achieves 90% accuracy on the benchmark. Third sentence follows."
    ctx = pass2_clean.locate_context("Our method achieves 90% accuracy on the benchmark.", text)
    assert ctx is not None
    assert "First sentence here." in ctx
    assert "Third sentence follows." in ctx


def test_locate_context_returns_none_when_candidate_not_in_paper_text():
    assert pass2_clean.locate_context("Not present anywhere.", "Completely different text here.") is None


def test_limitation_or_caveat_reason_code_is_dropped(monkeypatch):
    merged = _merged(
        ["Our method achieves 90% accuracy on the benchmark."],
        ["This does not establish that the method generalizes beyond the benchmark tested."],
    )
    decision_map = {
        "This does not establish that the method generalizes beyond the benchmark tested.": {
            "is_paper_claim": False, "reason_code": "limitation_or_caveat",
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["post_filter_pass2_count"] == 0
    assert result["decisions"]["P0"]["decision"] == "dropped"
    assert result["decisions"]["P0"]["reason_code"] == "limitation_or_caveat"


def test_contribution_reason_code_is_kept(monkeypatch):
    merged = _merged(
        [],
        ["We show that the benchmark admits a closed-form solution for this class of inputs."],
    )
    decision_map = {
        "We show that the benchmark admits a closed-form solution for this class of inputs.": {
            "is_paper_claim": True, "reason_code": "contribution",
        },
    }
    monkeypatch.setattr(engine, "_call_gemini_structured", _decision_fake(decision_map))

    result = asyncio.run(filter_merged_claims(merged, PAPER_TEXT, chat_id="c1"))

    assert result["post_filter_pass2_count"] == 1
    assert result["decisions"]["P0"]["decision"] == "kept"
    assert result["decisions"]["P0"]["reason_code"] == "contribution"


def test_neighbour_pool_grows_positionally_across_pass2_candidates(monkeypatch):
    """The second pass-2 candidate's neighbour pool must be able to include
    the first pass-2 candidate's text (positional "earlier", per this
    module's own docstring) - captured here by inspecting the built items
    directly rather than through a full filter_merged_claims run."""
    pass2_texts = ["Candidate A appears in the paper.", "Candidate A appears in the paper, basically."]
    merged = _merged([], pass2_texts)

    _, _, items = pass2_clean._build_items(merged, " ".join(pass2_texts))

    assert items[0]["neighbours"] == []
    neighbour_ids = {n["id"] for n in items[1]["neighbours"]}
    assert "P0" in neighbour_ids
