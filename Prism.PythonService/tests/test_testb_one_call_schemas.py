"""eval/testb/one_call_schemas.py: OneCallClaim/OneCallResult validation and prompt_hash()."""
import pytest
from pydantic import ValidationError

from eval.testb.one_call_schemas import OneCallClaim, OneCallResult, prompt_hash


def test_prompt_hash_is_12_hex_chars_and_deterministic():
    h1 = prompt_hash()
    h2 = prompt_hash()
    assert h1 == h2
    assert len(h1) == 12
    int(h1, 16)  # does not raise


def test_prompt_hash_changes_with_prompt_bytes(tmp_path):
    from eval.testb.one_call_schemas import SCHEMA_PATH

    prompt_a = tmp_path / "a.md"
    prompt_a.write_text("prompt A", encoding="utf-8")
    prompt_b = tmp_path / "b.md"
    prompt_b.write_text("prompt B", encoding="utf-8")
    assert prompt_hash(prompt_a, SCHEMA_PATH) != prompt_hash(prompt_b, SCHEMA_PATH)


def test_claim_rejects_unknown_verdict():
    with pytest.raises(ValidationError):
        OneCallClaim.model_validate({"claim_quote": "q", "location": "l", "evidence": "e", "verdict": "maybe", "reason": "r"})


def test_result_parses_claims_list():
    result = OneCallResult.model_validate({
        "claims": [{"claim_quote": "q", "location": "l", "evidence": "e", "verdict": "not_supported", "reason": "r"}]
    })
    assert len(result.claims) == 1
    assert result.claims[0].verdict == "not_supported"
