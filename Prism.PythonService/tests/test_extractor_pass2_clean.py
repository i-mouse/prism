"""Unit tests for the clean-extraction attempt's EXTRACTOR_PASS2_CLEAN flag
(docs/decisions.md, "Clean-extraction attempt amended: new pass-2 prompt +
filter - 2026-10-17").

Covers: the flag defaults off; it has zero effect on the prompt hash or on
extract_claims when extractor_second_pass is off (a true no-op); with both
flags on it changes the hash to a third, distinct value and the live
pass-2 call path switches to the new prompt file; extraction/merge.py is
never touched by this attempt (pinned by sha256, equivalent to an empty
git diff). No LLM calls - extraction.engine's _call_gemini_json/
_call_gemini_freetext/_call_gemini_structured are faked.
"""
import asyncio
import hashlib
from pathlib import Path

from config import settings
from extraction import engine, pass2
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLabel, ClaimLLM, EvidenceSpanLLM

MERGE_PY_SHA256 = "98a9410cecf55c368ac766758e2132c616f64f64661ad53f382eaccebd11b8d2"


def test_clean_flag_defaults_off():
    assert settings.extractor_pass2_clean is False


def test_merge_py_is_byte_identical_to_the_pre_clean_attempt_snapshot():
    """Regression lock equivalent to `git diff --exit-code extraction/merge.py`
    (this repo's sandbox refuses git commands run by the agent itself) - the
    clean-extraction attempt must never edit merge.py, since its grounding/
    dedup/merge logic is shared, unmodified, with pass 1 and the plain
    EXTRACTOR_SECOND_PASS path."""
    merge_path = Path(__file__).parent.parent / "extraction" / "merge.py"
    assert hashlib.sha256(merge_path.read_bytes()).hexdigest() == MERGE_PY_SHA256


def test_clean_flag_alone_with_second_pass_off_does_not_change_the_hash():
    assert get_prompt_version(extractor_second_pass=False, extractor_pass2_clean=False) == "cb3272cce551"
    assert get_prompt_version(extractor_second_pass=False, extractor_pass2_clean=True) == "cb3272cce551"


def test_second_pass_only_hash_is_unaffected_by_the_clean_flag_param_default():
    assert get_prompt_version(extractor_second_pass=True, extractor_pass2_clean=False) == "d03695c495ff"


def test_both_flags_on_produces_a_third_distinct_hash():
    off_hash = get_prompt_version(extractor_second_pass=False, extractor_pass2_clean=False)
    second_pass_only_hash = get_prompt_version(extractor_second_pass=True, extractor_pass2_clean=False)
    both_on_hash = get_prompt_version(extractor_second_pass=True, extractor_pass2_clean=True)
    assert len({off_hash, second_pass_only_hash, both_on_hash}) == 3


def test_live_pass2_window_uses_v2_prompt_when_both_flags_on(monkeypatch):
    monkeypatch.setattr(settings, "extractor_pass2_clean", True)
    captured = {}

    def fake_build(window_text, prompt_filename=None):
        captured["prompt_filename"] = prompt_filename
        return [{"role": "system", "content": "sys"}, {"role": "user", "content": window_text}]

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        from extraction.pass2 import SentenceListLLM
        return SentenceListLLM(sentences=[])

    monkeypatch.setattr(pass2, "build_gemini_messages_for_pass2", fake_build)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)

    asyncio.run(pass2._call_pass2_window("window text", chat_id="c1", correlation_id=None))

    assert captured["prompt_filename"] == "extract_claims_pass2_v2_system.md"


def test_live_pass2_window_uses_default_prompt_when_clean_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "extractor_pass2_clean", False)
    captured = {}

    def fake_build(window_text, prompt_filename=None):
        captured["prompt_filename"] = prompt_filename
        return [{"role": "system", "content": "sys"}, {"role": "user", "content": window_text}]

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        from extraction.pass2 import SentenceListLLM
        return SentenceListLLM(sentences=[])

    monkeypatch.setattr(pass2, "build_gemini_messages_for_pass2", fake_build)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)

    asyncio.run(pass2._call_pass2_window("window text", chat_id="c1", correlation_id=None))

    assert captured["prompt_filename"] is None


def test_clean_flag_on_with_second_pass_off_is_a_true_noop(monkeypatch):
    """extractor_pass2_clean=True alone (extractor_second_pass=False) must
    behave exactly like both-off: no pass-2 call, no filter call, pass-1
    claims pass through untouched."""
    monkeypatch.setattr(settings, "extractor_second_pass", False)
    monkeypatch.setattr(settings, "extractor_pass2_clean", True)
    filter_called = False
    pass2_called = False

    async def fake_filter(*args, **kwargs):
        nonlocal filter_called
        filter_called = True
        return {
            "filtered_claims": [], "decisions": {}, "incomplete": False,
            "failed_batch_count": 0, "pre_filter_pass2_count": 0, "post_filter_pass2_count": 0,
        }

    async def fake_run_pass2(*args, **kwargs):
        nonlocal pass2_called
        pass2_called = True
        return [], 0

    async def fake_call_gemini_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return {"claims": [{"claim_text_verbatim": "X.", "claim_summary": "x"}]}

    async def fake_call_gemini_freetext(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        return "Reasoning.\n\nVERDICT: supported\n\nQUOTE: X.\nSECTION: Section 1"

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return ClaimLLM(
            claim_text_verbatim="X.", claim_summary="x", label=ClaimLabel.SUPPORTED,
            evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="S1")],
        )

    monkeypatch.setattr(engine, "_call_gemini_json", fake_call_gemini_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_call_gemini_freetext)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)
    monkeypatch.setattr("extraction.pass2.run_pass2", fake_run_pass2)
    monkeypatch.setattr("extraction.pass2_clean.filter_merged_claims", fake_filter)

    result = asyncio.run(engine.extract_claims(paper_text="the full paper text", chat_id="chat-1"))

    assert pass2_called is False
    assert filter_called is False
    assert len(result.claims) == 1
    assert result.claims[0].claim_text_verbatim == "X."
