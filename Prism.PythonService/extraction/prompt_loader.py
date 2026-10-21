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

from config import settings

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


def load_fewshot_shapes_examples() -> list[dict]:
    """Reads and parses extract_claims_fewshot_shapes.json: Experiment 2
    (redesigned)'s 8 claim-shape few-shot examples (E1/E2/E3/E5), appended
    after the base 11 only when settings.extractor_fewshot_shapes (or an
    explicit override) is on. Each example uses a "rationale" key instead of
    "note" - "rationale" is pure curator commentary and is never read by
    _is_negative_example, so these examples can never be mis-treated as
    negative the way note-bearing base examples are under extractor_fewshot_fix
    off (see _is_negative_example's docstring).

    Raises:
        FileNotFoundError: if extract_claims_fewshot_shapes.json is missing.
    """
    path = PROMPTS_DIR / "extract_claims_fewshot_shapes.json"
    if not path.exists():
        raise FileNotFoundError(f"Few-shot shapes examples not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _is_negative_example(example: dict, fewshot_fix: bool) -> bool:
    """Returns True if a claims example is the negative (do-not-extract) case.

    Detected by example_type, or a "note" field nested inside "output" in
    place of a real claim payload. With fewshot_fix off (default), a
    top-level "note" field also counts - but that check fires on 8 of the
    extractor's 9 claim-bearing examples, since "note" is used there purely
    as curator rationale, not as a negative-example marker (see
    docs/decisions.md, 2026-10-05/06: Experiment 2 fixes this). With
    fewshot_fix on, the top-level "note" check is replaced by the signal
    that actually distinguishes the two genuine negative examples: an empty
    claims list in the real output.
    """
    if example.get("example_type") == "negative_do_not_extract":
        return True
    output = example.get("output")
    if isinstance(output, dict) and "note" in output and "claim_text_verbatim" not in output:
        return True
    if fewshot_fix:
        return isinstance(output, dict) and output.get("claims") == []
    return "note" in example


def build_gemini_messages_for_extractor(
    paper_text: str, fewshot_fix: bool | None = None, fewshot_shapes: bool | None = None,
) -> list[dict]:
    """Assembles the full Gemini message list for the extractor call (Call #2).

    Order: system prompt (plus the shapes addendum, when on), then for each
    few-shot example - base 11, then the 8 shapes examples when on - a user
    message (input_excerpt) followed by a model message (its output as a
    JSON string - an empty claims array for the negative examples), then a
    final user message containing the paper text to extract from.

    fewshot_fix: Experiment 2 override for _is_negative_example. None
    (default) reads settings.extractor_fewshot_fix; pass True/False
    explicitly to force a variant regardless of the live setting (used by
    eval/replay_extract.py to run both control and treatment in one
    process without touching global settings).

    fewshot_shapes: Experiment 2 (redesigned) override - appends the 8
    claim-shape examples and the system-prompt addendum. None (default)
    reads settings.extractor_fewshot_shapes; pass True/False explicitly to
    force a variant, same convention as fewshot_fix.
    """
    if fewshot_fix is None:
        fewshot_fix = settings.extractor_fewshot_fix
    if fewshot_shapes is None:
        fewshot_shapes = settings.extractor_fewshot_shapes

    system_prompt = load_system_prompt("claims")
    if fewshot_shapes:
        system_prompt = system_prompt + "\n\n" + _read_prompt_file("extract_claims_system_shapes.md")

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
    ]

    examples = load_fewshot_examples("claims")
    if fewshot_shapes:
        examples = examples + load_fewshot_shapes_examples()

    for example in examples:
        messages.append({"role": "user", "content": example["input_excerpt"]})
        if _is_negative_example(example, fewshot_fix):
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


def build_gemini_messages_for_pass2(window_text: str, prompt_filename: str | None = None) -> list[dict]:
    """Assembles the Gemini message list for an Experiment 3 pass-2 call
    (one call per window - see extraction/windowing.py).

    No few-shot examples, no paper text beyond the window itself - see
    docs/decisions.md's "Experiment 3 B1 review" entry.

    prompt_filename: None (default) reads extract_claims_pass2_system.md,
    byte-identical to this function's behavior before this parameter
    existed. The clean-extraction attempt (docs/decisions.md, "Clean-
    extraction attempt amended...") passes "extract_claims_pass2_v2_system.md"
    explicitly when settings.extractor_pass2_clean is on - see
    extraction/pass2.py.
    """
    return [
        {"role": "system", "content": _read_prompt_file(prompt_filename or "extract_claims_pass2_system.md")},
        {"role": "user", "content": window_text},
    ]


def build_gemini_messages_for_pass2_clean_filter(items: list[dict]) -> list[dict]:
    """Assembles the Gemini message list for the clean-extraction attempt's
    S3 batched filter call (one call per batch of at most
    extraction.pass2_clean.BATCH_SIZE candidates from one paper - see
    extraction/pass2_clean.py::filter_merged_claims).

    No few-shot examples beyond what the system prompt
    (extract_claims_pass2_clean_system.md) itself carries. The user message
    is a JSON array of candidates in the exact order the response must
    answer them in - the response schema
    (extraction/pass2_clean.py::CleanFilterBatchLLM) carries no id field of
    its own, so position is the only correspondence between request and
    response. Each item's internal bookkeeping (its source claim dict) is
    never sent - only id/candidate/context/neighbours.
    """
    payload = [
        {
            "id": item["id"],
            "candidate": item["candidate"],
            "context": item["context"],
            "neighbours": item["neighbours"],
        }
        for item in items
    ]
    return [
        {"role": "system", "content": _read_prompt_file("extract_claims_pass2_clean_system.md")},
        {"role": "user", "content": json.dumps({"candidates": payload}, indent=2)},
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
