"""Loads extraction prompts and assembles Gemini-compatible messages.

Reads the system prompt and few-shot examples from Prism.PythonService/prompts/
and turns them into the message list Gemini's structured output API expects.
Contains no LLM-calling code - assembly only.

Four call kinds are supported:
  - "metadata": Prompt 1, paper-level metadata extraction (build_gemini_messages_for_metadata)
  - extractor: Prompt 2 Call #2, claim-only extraction, no labels (build_gemini_messages_for_extractor)
  - audit: Prompt 2 Call #3, per-claim free-text audit (build_gemini_messages_for_audit)
  - structure: Prompt 2 Call #4, structures the audit into ClaimLLM JSON (build_gemini_messages_for_structure)
"""
import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_system_prompt(prompt_kind: str) -> str:
    """Reads and returns the contents of the extract_{prompt_kind}_system.md prompt.

    Args:
        prompt_kind: "claims" or "metadata".

    Raises:
        FileNotFoundError: if extract_{prompt_kind}_system.md is missing.
    """
    system_path = PROMPTS_DIR / f"extract_{prompt_kind}_system.md"
    if not system_path.exists():
        raise FileNotFoundError(f"System prompt not found at {system_path}")
    return system_path.read_text(encoding="utf-8")


def load_fewshot_examples(prompt_kind: str) -> list[dict]:
    """Reads and parses the extract_{prompt_kind}_fewshot.json examples.

    Args:
        prompt_kind: "claims" or "metadata".

    Raises:
        FileNotFoundError: if extract_{prompt_kind}_fewshot.json is missing.
        json.JSONDecodeError: if the file contents are not valid JSON.
    """
    fewshot_path = PROMPTS_DIR / f"extract_{prompt_kind}_fewshot.json"
    if not fewshot_path.exists():
        raise FileNotFoundError(f"Few-shot examples not found at {fewshot_path}")
    return json.loads(fewshot_path.read_text(encoding="utf-8"))


def _is_negative_example(example: dict) -> bool:
    """Returns True if a claims example is the negative (do-not-extract) case.

    Detected by example_type, a top-level "note" field, or a "note" field
    nested inside "output" in place of a real claim payload.
    """
    if example.get("example_type") == "negative_do_not_extract":
        return True
    if "note" in example:
        return True
    output = example.get("output")
    if isinstance(output, dict) and "note" in output and "claim_text_verbatim" not in output:
        return True
    return False


def build_gemini_messages_for_extractor(paper_text: str) -> list[dict]:
    """Assembles the full Gemini message list for the extractor call (Call #2).

    Order: system prompt, then for each few-shot example a user message
    (input_excerpt) followed by a model message (its output as a JSON
    string - an empty claims array for the negative example), then a
    final user message containing the paper text to extract from.
    """
    messages: list[dict] = [
        {"role": "system", "content": load_system_prompt("claims")},
    ]

    for example in load_fewshot_examples("claims"):
        messages.append({"role": "user", "content": example["input_excerpt"]})
        if _is_negative_example(example):
            model_content = json.dumps({"claims": []})
        else:
            model_content = json.dumps(example["output"])
        messages.append({"role": "model", "content": model_content})

    messages.append({"role": "user", "content": paper_text})
    return messages


def _read_prompt_file(filename: str) -> str:
    """Reads a prompt file by its exact filename (no extract_{kind}_ convention)."""
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found at {path}")
    return path.read_text(encoding="utf-8")


def build_gemini_messages_for_audit(
    paper_text: str,
    claim_text_verbatim: str,
    claim_summary: str,
) -> list[dict]:
    """Assembles the Gemini message list for the auditor call (Call #3).

    No few-shot examples. The user message carries the full paper text
    plus the single claim to audit, clearly labeled so the auditor's
    reasoning stays scoped to that one claim.
    """
    user_content = (
        f"PAPER TEXT:\n{paper_text}\n\n"
        "CLAIM TO AUDIT:\n"
        f"CLAIM_TEXT_VERBATIM: {claim_text_verbatim}\n"
        f"CLAIM_SUMMARY: {claim_summary}"
    )
    return [
        {"role": "system", "content": _read_prompt_file("audit_claim_system.md")},
        {"role": "user", "content": user_content},
    ]


def _format_span_audit_user_message(claim_text: str, claim_label: str, quote: str, context: str) -> str:
    """Formats the claim/label/quote/context envelope shared by the real
    span-audit call and its few-shot examples, so the model sees an
    identical shape. claim_label is the auditor's already-decided verdict
    for the claim (supported/partially_supported/not_supported) - the
    span audit only judges whether this quote justifies that label."""
    return (
        f"Claim: {claim_text}\n\n"
        f"Auditor's label for this claim: {claim_label}\n\n"
        f'Evidence quote:\n"{quote}"\n\n'
        f'Surrounding paper context:\n"...{context}..."'
    )


def build_gemini_messages_for_span_audit(
    claim_text: str,
    claim_label: str,
    quote: str,
    context: str,
) -> list[dict]:
    """Assembles the Gemini message list for the span-level grounding audit
    (Stage 2 of extraction/grounding.py).

    claim_label is the auditor's claim-level verdict (Call #3/#4's output),
    passed through as a plain string so this module stays free of the
    schemas.py ClaimLabel enum - the caller (extraction/grounding.py) owns
    that type and passes claim_label.value.

    Mirrors build_gemini_messages_for_extractor's few-shot envelope pattern:
    system prompt, then for each few-shot example a user message (the same
    claim/label/quote/context envelope the real call uses) followed by a
    model message (its stance/verdict/reason as a JSON string - reasoning
    is in the example dict for the prompt file's own readability but isn't
    replayed here, matching the pre-existing convention), then the final
    user message for the span actually being audited.
    """
    messages: list[dict] = [
        {"role": "system", "content": _read_prompt_file("audit_system.txt")},
    ]

    fewshot = json.loads(_read_prompt_file("audit_fewshot.json"))
    for example in fewshot.get("examples", []):
        messages.append(
            {
                "role": "user",
                "content": _format_span_audit_user_message(
                    example["claim"], example["claim_label"], example["quote"], example["context"]
                ),
            }
        )
        messages.append(
            {
                "role": "model",
                "content": json.dumps(
                    {"stance": example["stance"], "verdict": example["verdict"], "reason": example["reason"]}
                ),
            }
        )

    messages.append(
        {"role": "user", "content": _format_span_audit_user_message(claim_text, claim_label, quote, context)}
    )
    return messages


def build_gemini_messages_for_structure(
    claim_text_verbatim: str,
    claim_summary: str,
    audit_text: str,
) -> list[dict]:
    """Assembles the Gemini message list for the structurer call (Call #4).

    No few-shot examples. The user message carries the three labeled
    blocks the structurer expects: the claim's verbatim text, its
    summary, and the auditor's full free-text audit from Call #3.
    """
    user_content = (
        f"CLAIM_TEXT_VERBATIM: {claim_text_verbatim}\n"
        f"CLAIM_SUMMARY: {claim_summary}\n"
        f"AUDIT:\n{audit_text}"
    )
    return [
        {"role": "system", "content": _read_prompt_file("structure_verdict_system.md")},
        {"role": "user", "content": user_content},
    ]


def build_gemini_messages_for_metadata(paper_text: str) -> list[dict]:
    """Assembles the full Gemini message list for a metadata extraction call.

    Order: system prompt, then for each few-shot example a user message
    (input_excerpt) followed by a model message (its output as a JSON
    string), then a final user message containing the paper text to
    extract from. Unlike claims, metadata has no negative example - the
    LLM always returns all 9 fields.
    """
    messages: list[dict] = [
        {"role": "system", "content": load_system_prompt("metadata")},
    ]

    for example in load_fewshot_examples("metadata"):
        messages.append({"role": "user", "content": example["input_excerpt"]})
        messages.append({"role": "model", "content": json.dumps(example["output"])})

    messages.append({"role": "user", "content": paper_text})
    return messages
