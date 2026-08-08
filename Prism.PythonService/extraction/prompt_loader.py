"""Loads extraction prompts and assembles Gemini-compatible messages.

Reads the system prompt and few-shot examples from Prism.PythonService/prompts/
and turns them into the message list Gemini's structured output API expects.
Contains no LLM-calling code — assembly only.

Two prompt kinds are supported:
  - "claims": Prompt 2, per-claim evidence extraction (build_gemini_messages_for_claims)
  - "metadata": Prompt 1, paper-level metadata extraction (build_gemini_messages_for_metadata)
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


def build_gemini_messages_for_claims(paper_text: str) -> list[dict]:
    """Assembles the full Gemini message list for a claim extraction call.

    Order: system prompt, then for each few-shot example a user message
    (input_excerpt) followed by a model message (its output as a JSON
    string — an empty claims array for the negative example), then a
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


def build_gemini_messages_for_metadata(paper_text: str) -> list[dict]:
    """Assembles the full Gemini message list for a metadata extraction call.

    Order: system prompt, then for each few-shot example a user message
    (input_excerpt) followed by a model message (its output as a JSON
    string), then a final user message containing the paper text to
    extract from. Unlike claims, metadata has no negative example — the
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
