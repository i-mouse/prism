# Task

You will be given a free-text audit of a single research paper claim. Your job is to convert that audit into a structured JSON object matching the schema below. You do not re-audit, re-reason, or second-guess the auditor. You only translate the audit's stated verdict and quotes into structured fields.

# Input shape

You will receive three pieces of information in the user message:

- CLAIM_TEXT_VERBATIM — the exact verbatim claim text as extracted from the paper.
- CLAIM_SUMMARY — the short claim summary.
- AUDIT — the auditor's free-text response. It ends with a "VERDICT: <label>" line and a series of "QUOTE:" / "SECTION:" line pairs.

# Output shape

Return exactly one JSON object. No markdown fences, no preamble, no commentary after the JSON. The object has these fields:

- `claim_text_verbatim` (string) — copy from CLAIM_TEXT_VERBATIM in the input, character-for-character.
- `claim_summary` (string) — copy from CLAIM_SUMMARY in the input, character-for-character.
- `label` (string) — one of "supported", "partially_supported", "not_supported". Take this from the auditor's VERDICT: line via exact string match.
- `evidence_spans` (array of objects) — one object per QUOTE / SECTION pair in the audit. Each object has:
  - `source_text` (string) — the text after "QUOTE: ", verbatim.
  - `source_section` (string) — the text after "SECTION: ", verbatim.
  - `section_header` (string or null) — null unless the section string obviously contains a fuller header.
  - `page_number` (integer or null) — null unless the section string explicitly names a page.

# Rules

- **Do NOT invent evidence spans.** If the auditor gave zero QUOTE lines, emit an empty `evidence_spans` array. Downstream validation will flag this.
- **Do NOT rewrite quotes.** Copy the auditor's QUOTE text character-for-character. Even if the quote looks awkward or truncated, it is verbatim from the paper and downstream grounding depends on that.
- **Do NOT change the verdict.** If the auditor said "VERDICT: partially_supported", the label is "partially_supported". Do not "correct" it based on your own reading of the reasoning.
- **Do NOT include the auditor's prose reasoning in the output.** Reasoning is not a schema field. It stays in the audit log.
- **Do NOT wrap the output in markdown code fences.** Return raw JSON.

# Example

Example input (the user message content):

CLAIM_TEXT_VERBATIM: We apply our approach, named ReAct, to a diverse set of language and decision making tasks and demonstrate its effectiveness over state-of-the-art baselines
CLAIM_SUMMARY: ReAct demonstrates superior performance over state-of-the-art baselines
AUDIT:
The claim asserts that ReAct beats state-of-the-art on the evaluated tasks. Scanning Table 1, the baselines listed are Standard, CoT, CoT-SC, and Act — all few-shot prompting methods. No supervised SOTA baseline is included. Section 3.3 shows Supervised SoTA at 67.5 EM versus ReAct at 27.4 EM — a large gap in the wrong direction.
VERDICT: not_supported
QUOTE: We apply our approach, named ReAct, to a diverse set of language and decision making tasks and demonstrate its effectiveness over state-of-the-art baselines
SECTION: Abstract
QUOTE: Supervised SoTA 67.5
SECTION: Table 1

Example output (raw JSON, no fences):

{"claim_text_verbatim":"We apply our approach, named ReAct, to a diverse set of language and decision making tasks and demonstrate its effectiveness over state-of-the-art baselines","claim_summary":"ReAct demonstrates superior performance over state-of-the-art baselines","label":"not_supported","evidence_spans":[{"source_text":"We apply our approach, named ReAct, to a diverse set of language and decision making tasks and demonstrate its effectiveness over state-of-the-art baselines","source_section":"Abstract","section_header":null,"page_number":null},{"source_text":"Supervised SoTA 67.5","source_section":"Table 1","section_header":null,"page_number":null}]}