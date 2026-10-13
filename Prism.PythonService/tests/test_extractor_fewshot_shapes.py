"""Unit tests for Experiment 2 (redesigned)'s extractor few-shot claim-shape
examples (EXTRACTOR_FEWSHOT_SHAPES).

Covers: shapes-off rendering is byte-identical to fix-on-only behavior, the 8
shapes examples render correctly (real outputs for positives, empty claims
for near-miss negatives) with the addendum present exactly once and the base
11 examples unchanged and in their original order, the three reachable hash
states (both off, fix-on/shapes-off, fix-on/shapes-on) are independently
recomputed and pairwise distinct, and auditor/structurer rendering is
untouched by the flag in every state.
"""
import hashlib
import json

from config import settings
from extraction.prompt_loader import (
    build_gemini_messages_for_audit,
    build_gemini_messages_for_extractor,
    build_gemini_messages_for_structure,
    load_fewshot_examples,
    load_fewshot_shapes_examples,
)
from extraction.prompt_version import (
    EXTRA_HASHED_FILES,
    PROMPT_FILENAMES,
    PROMPTS_DIR,
    SHAPES_PROMPT_FILENAMES,
    get_prompt_version,
)


def _recompute_hash(fewshot_fix: bool, fewshot_shapes: bool) -> str:
    """Independently recomputes the hash get_prompt_version should produce,
    without calling get_prompt_version itself - mirrors
    test_extractor_fewshot_fix.py's _old_hash() helper."""
    combined = b""
    for path in [PROMPTS_DIR / f for f in PROMPT_FILENAMES] + list(EXTRA_HASHED_FILES):
        combined += path.read_bytes()
    if fewshot_fix:
        combined += b"\x00extractor_fewshot_fix=1"
    if fewshot_shapes:
        for f in SHAPES_PROMPT_FILENAMES:
            combined += (PROMPTS_DIR / f).read_bytes()
        combined += b"\x00extractor_fewshot_shapes=1"
    return hashlib.sha256(combined).hexdigest()[:12]


def test_shapes_off_hash_matches_fix_only_hash_in_every_fix_state():
    for fewshot_fix in (False, True):
        assert get_prompt_version(fewshot_fix=fewshot_fix, fewshot_shapes=False) == _recompute_hash(fewshot_fix, False)


def test_three_reachable_hash_states_are_pairwise_distinct():
    both_off = get_prompt_version(fewshot_fix=False, fewshot_shapes=False)
    fix_only = get_prompt_version(fewshot_fix=True, fewshot_shapes=False)
    fix_and_shapes = get_prompt_version(fewshot_fix=True, fewshot_shapes=True)

    assert both_off == _recompute_hash(False, False)
    assert fix_only == _recompute_hash(True, False)
    assert fix_and_shapes == _recompute_hash(True, True)
    assert len({both_off, fix_only, fix_and_shapes}) == 3
    print(f"\n[manual check] both-off={both_off} fix-only(control)={fix_only} fix+shapes(treatment)={fix_and_shapes}")


def test_eight_shapes_examples_load():
    examples = load_fewshot_shapes_examples()
    assert len(examples) == 8
    claim_bearing = [e for e in examples if e["output"].get("claims")]
    empty_claims = [e for e in examples if not e["output"].get("claims")]
    # 4 positives (one per E1/E2/E3/E5) + narrow_claim_with_disclaimer (the E3
    # near-miss, which keeps its narrow claim rather than having empty
    # output.claims - see its rationale) = 5 claim-bearing; the other 3
    # near-misses (E1/E2/E5) are genuinely empty.
    assert len(claim_bearing) == 5
    assert len(empty_claims) == 3
    # Every example uses "rationale", never "note" - a shapes example must
    # never be mistaken for a note-bearing base example by _is_negative_example.
    for example in examples:
        assert "rationale" in example
        assert "note" not in example


def test_shapes_off_is_byte_identical_to_fix_only_rendering():
    for fewshot_fix in (False, True):
        with_explicit_shapes_off = build_gemini_messages_for_extractor(
            "paper text", fewshot_fix=fewshot_fix, fewshot_shapes=False
        )
        without_shapes_param = build_gemini_messages_for_extractor("paper text", fewshot_fix=fewshot_fix)
        assert with_explicit_shapes_off == without_shapes_param


def test_shapes_on_keeps_base_11_examples_unchanged_and_in_order():
    base_examples = load_fewshot_examples("claims")
    messages = build_gemini_messages_for_extractor("paper text", fewshot_fix=True, fewshot_shapes=True)

    # messages: [system, 11 x (user, model), 8 x (user, model), final user]
    user_messages = [m for m in messages if m["role"] == "user"][:-1]
    assert len(user_messages) == 19
    for base_example, user_message in zip(base_examples, user_messages[:11]):
        assert user_message["content"] == base_example["input_excerpt"]


def test_shapes_on_renders_the_8_new_examples_with_correct_claims():
    shapes_examples = load_fewshot_shapes_examples()
    messages = build_gemini_messages_for_extractor("paper text", fewshot_fix=True, fewshot_shapes=True)

    user_messages = [m for m in messages if m["role"] == "user"][:-1]
    model_messages = [m for m in messages if m["role"] == "model"]
    assert len(model_messages) == 19

    shapes_user_messages = user_messages[11:]
    shapes_model_messages = model_messages[11:]
    assert len(shapes_user_messages) == 8
    assert len(shapes_model_messages) == 8

    for example, user_message, model_message in zip(shapes_examples, shapes_user_messages, shapes_model_messages):
        assert user_message["content"] == example["input_excerpt"]
        assert json.loads(model_message["content"]) == example["output"]


def test_shapes_on_appends_addendum_exactly_once():
    addendum = (PROMPTS_DIR / "extract_claims_system_shapes.md").read_text(encoding="utf-8")
    messages_on = build_gemini_messages_for_extractor("paper text", fewshot_fix=True, fewshot_shapes=True)
    messages_off = build_gemini_messages_for_extractor("paper text", fewshot_fix=True, fewshot_shapes=False)

    system_on = next(m["content"] for m in messages_on if m["role"] == "system")
    system_off = next(m["content"] for m in messages_off if m["role"] == "system")

    assert system_on.count(addendum) == 1
    assert addendum not in system_off


def test_auditor_rendering_unaffected_by_shapes_flag(monkeypatch):
    before = build_gemini_messages_for_audit("paper text", "claim verbatim", "claim summary")
    monkeypatch.setattr(settings, "extractor_fewshot_shapes", True)
    after = build_gemini_messages_for_audit("paper text", "claim verbatim", "claim summary")
    assert before == after


def test_structurer_rendering_unaffected_by_shapes_flag(monkeypatch):
    before = build_gemini_messages_for_structure("claim verbatim", "claim summary", "audit text")
    monkeypatch.setattr(settings, "extractor_fewshot_shapes", True)
    after = build_gemini_messages_for_structure("claim verbatim", "claim summary", "audit text")
    assert before == after
