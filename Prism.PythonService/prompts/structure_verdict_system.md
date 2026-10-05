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

CLAIM_TEXT_VERBATIM: Across every catchment we study, Rivulet delivers flood warnings that are earlier and more reliable than those of state-of-the-art forecasting systems
CLAIM_SUMMARY: Rivulet outperforms state-of-the-art forecasting systems on flood warnings
AUDIT:
The claim asserts that Rivulet beats state-of-the-art forecasting systems. Scanning Table 2, the baselines listed are Persistence, Linear Regression, Gradient-Boosted Trees, and Rivulet-NoRoute — all lightweight statistical models. No operational forecasting system is run. Table 2 also prints a published Operational Ensemble score of 0.78 against Rivulet's 0.61 — a large gap in the wrong direction.
VERDICT: not_supported
QUOTE: Across every catchment we study, Rivulet delivers flood warnings that are earlier and more reliable than those of state-of-the-art forecasting systems
SECTION: Abstract
QUOTE: Operational Ensemble 0.78
SECTION: Table 2

Example output (raw JSON, no fences):

{"claim_text_verbatim":"Across every catchment we study, Rivulet delivers flood warnings that are earlier and more reliable than those of state-of-the-art forecasting systems","claim_summary":"Rivulet outperforms state-of-the-art forecasting systems on flood warnings","label":"not_supported","evidence_spans":[{"source_text":"Across every catchment we study, Rivulet delivers flood warnings that are earlier and more reliable than those of state-of-the-art forecasting systems","source_section":"Abstract","section_header":null,"page_number":null},{"source_text":"Operational Ensemble 0.78","source_section":"Table 2","section_header":null,"page_number":null}]}