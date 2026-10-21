"""Unit tests for Experiment 2's extractor few-shot "note" field fix.

Covers: _is_negative_example's behavior change is scoped to the extractor's
positive note-bearing examples, the two genuine negatives stay negative in
both states, auditor/structurer message assembly is untouched, and
get_prompt_version's flag-off hash equals the pre-Experiment-2 hash exactly
while flag-on produces a different one.
"""
from config import settings
from extraction.prompt_loader import (
    build_gemini_messages_for_audit,
    build_gemini_messages_for_extractor,
    build_gemini_messages_for_structure,
    load_fewshot_examples,
)
from extraction.prompt_version import PROMPT_FILENAMES, EXTRA_HASHED_FILES, get_prompt_version


def _old_hash() -> str:
    """Recomputes the pre-Experiment-2 hash: same files, no flag token appended."""
    import hashlib

    from extraction.prompt_version import PROMPTS_DIR

    combined = b""
    for path in [PROMPTS_DIR / filename for filename in PROMPT_FILENAMES] + list(EXTRA_HASHED_FILES):
        combined += path.read_bytes()
    return hashlib.sha256(combined).hexdigest()[:12]


def test_flag_off_matches_old_hash_computation():
    assert get_prompt_version(fewshot_fix=False) == _old_hash()


def test_flag_on_hash_differs_from_flag_off():
    assert get_prompt_version(fewshot_fix=True) != get_prompt_version(fewshot_fix=False)


def _claim_bearing_note_examples() -> list[dict]:
    examples = load_fewshot_examples("claims")
    return [
        example
        for example in examples
        if "note" in example and example["output"].get("claims")
    ]


def test_eight_of_nine_claim_bearing_examples_carry_a_note():
    examples = load_fewshot_examples("claims")
    claim_bearing = [e for e in examples if e["output"].get("claims")]
    note_bearing_claim_bearing = _claim_bearing_note_examples()
    assert len(claim_bearing) == 9
    assert len(note_bearing_claim_bearing) == 8


def test_flag_off_suppresses_note_bearing_positive_examples():
    messages = build_gemini_messages_for_extractor("paper text", fewshot_fix=False)
    examples = load_fewshot_examples("claims")
    note_bearing_positive = _claim_bearing_note_examples()

    model_messages = [m for m in messages if m["role"] == "model"]
    assert len(model_messages) == len(examples)

    for example, model_message in zip(examples, model_messages):
        if example in note_bearing_positive:
            assert model_message["content"] == '{"claims": []}'


def test_flag_on_renders_note_bearing_positive_examples_intact():
    import json

    messages = build_gemini_messages_for_extractor("paper text", fewshot_fix=True)
    examples = load_fewshot_examples("claims")

    model_messages = [m for m in messages if m["role"] == "model"]
    for example, model_message in zip(examples, model_messages):
        if example["output"].get("claims"):
            assert json.loads(model_message["content"]) == example["output"]
        else:
            assert model_message["content"] == '{"claims": []}'


def test_flag_off_is_byte_identical_to_default_rendering():
    assert build_gemini_messages_for_extractor("paper text", fewshot_fix=False) == build_gemini_messages_for_extractor(
        "paper text"
    )


def test_auditor_rendering_unaffected_by_flag(monkeypatch):
    before = build_gemini_messages_for_audit("paper text", "claim verbatim", "claim summary")
    monkeypatch.setattr(settings, "extractor_fewshot_fix", True)
    after = build_gemini_messages_for_audit("paper text", "claim verbatim", "claim summary")
    assert before == after


def test_structurer_rendering_unaffected_by_flag(monkeypatch):
    before = build_gemini_messages_for_structure("claim verbatim", "claim summary", "audit text")
    monkeypatch.setattr(settings, "extractor_fewshot_fix", True)
    after = build_gemini_messages_for_structure("claim verbatim", "claim summary", "audit text")
    assert before == after
