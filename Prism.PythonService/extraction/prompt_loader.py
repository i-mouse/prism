"""Loads extraction prompts and assembles Gemini-compatible messages.

Reads the system prompt and few-shot examples from Prism.PythonService/prompts/
and turns them into the message list Gemini's structured output API expects.
Contains no LLM-calling code — assembly only.
"""
import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

SYSTEM_PROMPT_FILENAME = "extract_claims_system.md"
FEWSHOT_FILENAME = "extract_claims_fewshot.json"


def load_system_prompt() -> str:
    """Reads and returns the contents of the extraction system prompt.

    Raises:
        FileNotFoundError: if extract_claims_system.md is missing.
    """
    system_path = PROMPTS_DIR / SYSTEM_PROMPT_FILENAME
    if not system_path.exists():
        raise FileNotFoundError(f"System prompt not found at {system_path}")
    return system_path.read_text(encoding="utf-8")


def load_fewshot_examples() -> list[dict]:
    """Reads and parses the extraction few-shot examples.

    Raises:
        FileNotFoundError: if extract_claims_fewshot.json is missing.
        json.JSONDecodeError: if the file contents are not valid JSON.
    """
    fewshot_path = PROMPTS_DIR / FEWSHOT_FILENAME
    if not fewshot_path.exists():
        raise FileNotFoundError(f"Few-shot examples not found at {fewshot_path}")
    return json.loads(fewshot_path.read_text(encoding="utf-8"))


def _is_negative_example(example: dict) -> bool:
    """Returns True if an example is the negative (do-not-extract) case.

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


def build_gemini_messages(paper_text: str) -> list[dict]:
    """Assembles the full Gemini message list for a claim extraction call.

    Order: system prompt, then for each few-shot example a user message
    (input_excerpt) followed by a model message (its output as a JSON
    string — an empty claims array for the negative example), then a
    final user message containing the paper text to extract from.
    """
    messages: list[dict] = [
        {"role": "system", "content": load_system_prompt()},
    ]

    for example in load_fewshot_examples():
        messages.append({"role": "user", "content": example["input_excerpt"]})
        if _is_negative_example(example):
            model_content = json.dumps({"claims": []})
        else:
            model_content = json.dumps(example["output"])
        messages.append({"role": "model", "content": model_content})

    messages.append({"role": "user", "content": paper_text})
    return messages
