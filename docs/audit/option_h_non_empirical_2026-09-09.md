# Audit: Option H - Non-Empirical & Positioning Claim Omission (2026-09-09)

## Q1 — Pattern Taxonomy

The trap rows (grounding_negative: true) fall into the following rhetorical patterns:

| Trap ID | Paper | Rhetorical Pattern | Notes |
| :--- | :--- | :--- | :--- |
| REFLEX-M11 | Reflexion | `comparative-without-comparison` | Claims method is more sample-efficient than traditional RL, but never runs an RL baseline. |
| REFLEX-M12 | Reflexion | `comparative-without-comparison` | Claims advantages over traditional policy/value-based learning without baseline proof. |
| COT-M11 | CoT | `comparative-without-comparison` | Claims CoT avoids costly retraining of finetuning, without cost benchmarks. |
| REFLEX-M13 | Reflexion | `generalization-without-test` | Claims to be a "general framework... for language agents" but only tests 3 specific setups. |
| COT-M12 | CoT | `generalization-without-test` | Claims applicability to "any task humans can solve via language", but tests are limited to toy/math tasks. |
| REACT-M14 | ReAct | `generalization-without-test` | Motivates via physical autonomous systems, but only tests text APIs. |
| REACT-M13 | ReAct | `superiority-vs-untested-class` | Claims effectiveness over SOTA baselines, but the table actually shows it losing to SOTA. |
| REFLEX-M08 | Reflexion | `other` | Broad superiority claim contradicted by a negative result buried in the appendix. |
| REFLEX-M09 | Reflexion | `other` | Overly broad metric reporting (11% boost claimed generally, but only applies to Python). |
| COT-M08 | CoT | `other` | Generalization claim technically supported by toy tasks, but overly broad for the scope. |
| COT-M09 | CoT | `other` | Broad claim on "commonsense reasoning" but appendix admits reasoning paths weren't verified. |
| COT-M10 | CoT | `other` | Marketing claim ("simply by including examples") contradicted by appendix admitting prompt engineering matters. |
| REACT-M11 | ReAct | `other` | Rhetorical framing obscures a performance regression on one benchmark. |
| REACT-M12 | ReAct | `other` | Rhetoric of "robustness" undermined by high variance reported in the table. |

## Q2 — Emitted vs Omitted Traps

By cross-referencing the golden `expected_matrix` against the actual `fixtures` output for the trap rows (`grounding_negative: true`), we see exactly 7 trap rows were omitted during extraction:

**Omitted (The 7 targets):**
- REFLEX-M11
- REFLEX-M13
- COT-M09
- COT-M10
- COT-M11
- REACT-M12
- REACT-M14

**Emitted:**
- REFLEX-M08
- REFLEX-M09
- REFLEX-M12
- COT-M08
- COT-M12
- REACT-M11
- REACT-M13

The omissions heavily index on `comparative-without-comparison`, `generalization-without-test`, and broad positioning claims that read like background or motivation.

## Q3 — Why the Extractor Skips Them

Despite the `extract_claims_system.md` explicitly defining Pattern A and Pattern B to catch these cases, the prompt inherently biases the LLM against them by repeatedly defining the task as extracting **"empirical"** claims.

**Root Causes & Citations:**
1. **The "Empirical" Constraint:** The prompt defines a claim too narrowly.
   - *"Your only job is to surface every **empirical** claim the paper makes about its own results."*
   - *"Extract every **empirical** assertion the paper makes..."*
   - *"Target 10-20 **empirical** claims per paper."*
2. **Filtering instructions misapplied:** Positioning claims naturally resemble motivational or method descriptions. The prompt tells the LLM to actively filter these:
   - *"Do NOT extract: Motivational statements with no assertion about this paper's own method or results"*
   - *"Do NOT extract: Method descriptions with no comparative or generalization claim attached"*
3. **Few-shot bias:** `extract_claims_fewshot.json` explicitly teaches the model that "motivational" statements like *"Language agents are an exciting frontier..."* should yield `[]`. When an LLM reads a positioning claim like *"traditional reinforcement learning methods require extensive training..."* (REFLEX-M11), it heavily pattern-matches it to the rejected motivational few-shot.

The prompt essentially tells the LLM to find numbers ("empirical"), drop background ("motivational"), and somehow magically realize that broad positioning statements aren't background. The "empirical" constraint wins out.

## Q4 — Filter vs Tag

- **FILTER (Current State):** The extractor drops these claims because they don't look "empirical". **What's lost:** The entire product value. The reviewer's primary job is catching overstated positioning claims. If the pipeline silently filters them as "background text", the UI never shows them to the user, falsely implying the paper is perfectly grounded.
- **TAG (Proposed Fix):** Instead of fighting the LLM on whether a positioning statement counts as an "empirical claim", we make it an explicit classification task.
  - **Schema Change:** Add `claim_type: Literal["empirical", "positioning"]` to `ClaimLLM` in `schemas.py`.
  - **Prompt Change:** Explicitly instruct the model: *"You must extract TWO types of claims: empirical (numerical results) and positioning (generalization, superiority, and motivational claims). Tag them accordingly."*
  - **Downstream Flow:** The auditor call evaluates both identically. If a "positioning" claim has no evidence, the auditor will yield `not_supported`. The UI can either display them with a distinct pill/icon or just treat them as standard claims. The existing product assumes positioning claims *will* be surfaced.

## Q5 — The Auditor-Hedging Problem

Some emitted traps get `partially_supported` instead of `not_supported`.
This implies hedging in the system. The `ClaimLLM` schema (`schemas.py`) expects the extractor to output a `label` field (`ClaimLabel`), but the extraction prompt `extract_claims_system.md` explicitly forbids labeling (*"Do not label. Do not audit. Do not judge."*).

If the structured output schema forces the extractor to generate a `label`, the model is placed in a contradictory state where it must label without judging, leading to hedging. Alternatively, if this hedging occurs in the separate auditor step (Call 2), the auditor prompt may be too lenient with positioning claims that lack concrete evidence. **Scope:** Option H should primarily focus on extraction (getting the claims out). However, fixing the schema contradiction (e.g., removing `label` from the extractor LLM schema if it's supposed to be an auditor job, or fixing the prompt) should be a fast-follow or part of this PR.

## Q6 — Minimum Viable Change

**Recommended Change:** **Schema + Prompt (TAG approach)**
Changing the prompt alone isn't enough; LLMs struggle to map non-numerical text to the word "empirical". Adding an explicit enum forces the LLM to actively decide which bucket a sentence falls into, significantly reducing omission rates.

1. **Schema:** Add `claim_type: Literal["empirical", "positioning"]` to `ClaimLLM`.
2. **Prompt:** Remove the strict "empirical only" framing. Add explicit instructions for the `claim_type` field, mapping Pattern A and Pattern B to the `positioning` bucket.
3. **Few-Shot:** Update the few-shots to include `claim_type`.

**Expected Eval Impact:** This should convert most or all of the 7 omitted traps (REFLEX-M11, REFLEX-M13, COT-M09, COT-M10, COT-M11, REACT-M12, REACT-M14) into emitted claims, bringing the primary quality ceiling down.

## Proposed PR Scope

1. **Update `schemas.py`**: Add `claim_type: Literal["empirical", "positioning"]` to `ClaimLLM` and `ClaimFinal`.
2. **Refactor `extract_claims_system.md`**: Replace "empirical only" framing with instructions to extract both types; explain the difference.
3. **Update `extract_claims_fewshot.json`**: Add `claim_type` to all examples, ensuring positioning examples are tagged correctly.
4. **Run Eval Harness**: Run the Matrix Eval before and after to quantify the recovery of the 7 omitted trap rows.
5. **(Optional) Resolve Label Contradiction**: Ensure the extractor prompt's "Do not label" instruction aligns with the `ClaimLLM` schema's `label` requirement.
