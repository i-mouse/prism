# Audit of Claim Pipeline Defects (2026-09-04)

This read-only audit investigates two specific defects in the Prism claim pipeline: the grounding checker's inability to handle refuting evidence, and the extractor's omission of non-empirical positioning claims.

## 1. Grounding checker — current behaviour

**The span-audit prompt and rubric (`prompts/audit_system.txt`):**
```text
ROLE
You are an evidence auditor for research paper claims. Given a claim, a quoted passage from the paper, and the passage's surrounding context, you judge whether the passage supports the claim.

VERDICT OPTIONS
You return one of three verdicts:

- Pass: the passage directly supports the claim. The reader could cite this passage as evidence for the claim without needing additional supporting text.
- Partial: the passage is topically relevant and offers some support for the claim, but is incomplete on its own. It may reference numbers, results, or conclusions that back the claim, but a reader would need to consult adjacent tables, figures, or paragraphs to fully verify.
- Fail: the passage is unrelated to the claim, or contradicts it, or is genuinely insufficient support even in context.
```

**What exactly is the question posed to the audit LLM per span?**
The prompt explicitly asks the LLM to judge "whether the passage supports the claim."

**Possible verdicts and their current meanings:**
- **Pass:** The passage directly supports the claim on its own.
- **Partial:** The passage is topically relevant and offers some support, but is incomplete.
- **Fail:** The passage is unrelated, provides insufficient support, or *contradicts* the claim.

**Per-claim rollup logic (`extraction/grounding.py`):**
```python
        if passes:
            claims_passed += 1
            final_claims.append(
                ClaimFinal(
                    claim_text_verbatim=claim.claim_text_verbatim,
                    claim_summary=claim.claim_summary,
                    label=claim.label,
                    evidence_spans=spans,
                    grounding_status=GroundingStatus.PASS,
                    missing=False,
                    reason=None,
                )
            )
        elif partials:
            claims_partial += 1
            noun = "passage" if len(partials) == 1 else "passages"
            reason = (
                "The auditor accepted the cited evidence as partial support: "
                f"{len(partials)} {noun} provided partial support to the claim."
            )
            final_claims.append(
                ClaimFinal(
                    claim_text_verbatim=claim.claim_text_verbatim,
                    claim_summary=claim.claim_summary,
                    label=claim.label,
                    evidence_spans=spans,
                    grounding_status=GroundingStatus.PARTIAL,
                    missing=False,
                    reason=reason,
                )
            )
        else:
            claims_failed += 1
            reason = (
                f"all evidence spans failed grounding: "
                f"{claims_rapidfuzz_failed[claim_idx]} spans failed RapidFuzz check; "
                f"{claims_audit_failed[claim_idx]} spans failed LLM audit"
            )
            final_claims.append(
                ClaimFinal(
                    claim_text_verbatim=claim.claim_text_verbatim,
                    claim_summary=claim.claim_summary,
                    label=claim.label,
                    evidence_spans=spans,
                    grounding_status=GroundingStatus.FAIL,
                    missing=True,
                    reason=reason,
                )
            )
```

**Where the auditor's LABEL is available:**
The auditor's label (`claim.label` which is `supported`, `partially_supported`, or `not_supported`) is fully available in `ground_extraction` within the `extraction.claims` list. 
However, it is currently **not** passed down. It is completely isolated from the grounding call. To thread it through, we would need to pass it into `_ground_span_tracked`, `_ground_span`, `_audit_span_with_llm`, and finally `build_gemini_messages_for_span_audit` so it can be interpolated into the prompt string.

## 2. Grounding checker — what a REFUTES verdict would require

Adding a new "Refutes" verdict requires changes across all layers of the stack:

1. **Python enum (`extraction/schemas.py`)**: Add `REFUTES` to the `GroundingStatus` class.
2. **Prompt/rubric (`prompts/audit_system.txt`)**: Add `Refutes` to the `VERDICT OPTIONS` and explain its meaning.
3. **Few-shot (`prompts/audit_fewshot.json`)**: Add a new JSON example demonstrating a `Refutes` verdict.
4. **Rollup logic (`extraction/grounding.py`)**: Modify the `if passes: ... elif partials: ... else:` loop in `ground_extraction` to handle `refutes` spans and set the claim's `grounding_status`.
5. **C# enum (`Prism.ApiService/Data/Schemas/GroundingStatus.cs`)**: Add `Refutes`.
6. **C# ValueConverter (`Prism.ApiService/Data/Converters/GroundingStatusConverter.cs`)**: Map `Refutes` in the `ToDb` and `FromDb` dictionaries. **Flag:** This is a strict dictionary lookup. Missing this map will cause the API to throw a `KeyNotFoundException` and 500 when it attempts to load any paper containing a refutes claim.
7. **Frontend types (`Prism.Web/src/types/api.ts`)**: Add `"Refutes"` to the `GroundingStatus` union type.
8. **Frontend badge metadata (`Prism.Web/src/lib/claimMeta.tsx`)**: Add to `groundingStatusMeta` and `groundingStatusToVerdict`.
9. **Evidence drawer rendering (`Prism.Web/src/components/VerdictPill.tsx`)**: Depending on the visual design, this may require a new styling variant if "Refutes" should be colored differently than "NOT SUPPORTED".

**Migration implications:** Existing rows in `paper_claims` with `Fail` statuses that should semantically be `Refutes` will not update automatically. They will remain as `Fail`, requiring a backfill script or re-extraction of all papers.

**Assessment:** Adding a fourth verdict is the **wrong shape**. It introduces sweeping changes across three languages, risks API crashes due to serialization mismatches, and fractures the data model. 
Instead, it is much better to **pass the claim label into the grounding call** and conditionally reinterpret the prompt. If the claim is `not_supported`, the grounding instruction should ask: "Does this quote *refute* the claim or justify why it is not supported?". In this paradigm, a `Pass` verdict simply means "Yes, this quote successfully grounds the claim's label." This keeps the 3-tier enum intact, requires no C# or frontend changes, and correctly treats the grounder as a verifier of the auditor's label.

## 3. The reason string bug

The bug occurs in the rollup logic of `ground_extraction` (`extraction/grounding.py`):
```python
        elif partials:
            claims_partial += 1
            noun = "passage" if len(partials) == 1 else "passages"
            reason = (
                "The auditor accepted the cited evidence as partial support: "
                f"{len(partials)} {noun} provided partial support to the claim."
            )
```
**Why it misdescribes:** The logic checks `elif partials:`. If *any* span in the claim scores `Partial` (and there are no `Pass` spans), it blindly applies this positive-sounding reason string to the entire claim. It completely ignores any `Fail` spans. In the defect record, one span (from the abstract) was topically relevant and marked `Partial`, but the other two spans were `Fail` because they directly contradicted the claim. The reason string generation ignored the refutations and painted the claim as partially supported, fundamentally misdescribing the auditor's findings.

## 4. Extractor scope — current behaviour

**Exact instruction (`prompts/extract_claims_system.md`):**
```markdown
# What you must extract

Extract every empirical assertion the paper makes about what its method achieved, measured, or demonstrated. Include:

- Quantitative results ("achieves 91.0% pass@1 on HumanEval")
- Benchmark comparisons ("outperforms GPT-4 by 11 points")
- Ablation findings ("removing X drops performance by 8 points")
- Broad or overreaching claims ("outperforms state-of-the-art", "generalizes to any language task", "robust to prompt selection", "sample-efficient compared to traditional RL")
- Efficiency, cost, latency, robustness, or sample-efficiency claims
- Generalization claims that assert broad applicability without the experiments necessarily covering that breadth (Pattern A below)
- Superiority claims made against a whole category of prior methods rather than a specific tested baseline (Pattern B below)
```

**Few-shot examples classification (`prompts/extract_claims_fewshot.json`):**
1. `positive_extraction`: "Reflexion achieves 91.0% pass@1 accuracy..." → **Empirical (number / benchmark)**
2. `abstract_broad_and_narrow_together`: "We introduce PromptAgent, a general framework..." → **Positioning (scope / generality)** AND "PromptAgent achieves 82.1%..." → **Empirical (number / benchmark)**
3. `abstract_sweep_with_multiple_broad_claims`: "ReAct, a general paradigm..." / "outperforms imitation..." / "robust to prompt selection" → **Mixed (positioning and empirical)**
4. `pattern_A_generalization_without_test`: "We present AutoFix, a general-purpose repair paradigm applicable to any programming task..." → **Positioning (scope / generality)**
5. `pattern_B_superiority_vs_class_not_tested`: "PromptWeave... avoiding the retraining overhead..." → **Positioning (superiority / efficiency)** AND "PromptWeave with 8 demonstrations reaches 74.2%..." → **Empirical (number / benchmark)**

**Prompt Steering:** The prompt's first instruction is to "Extract every *empirical assertion*...". This heavy emphasis on the word "empirical", combined with explicit examples of quantitative results, creates a strong implicit bias. Despite Patterns A and B existing in the prompt, purely non-empirical positioning claims (like REACT-M14) are dropped because the LLM interprets them as architectural descriptions or background context, rather than "empirical assertions".

## 5. Extractor scope — what would change

**New claim category shape:**
The overarching command should be broadened from "empirical assertion" to "assertions about the method's capabilities, scope, or empirical results."
A new bullet point should be added:
- Methodological positioning ("We present a general paradigm to...", "Our framework is capable of solving diverse tasks") — extract broad claims about what the proposed system is structurally designed to achieve, even if no quantitative experiments follow.

**Golden rows that would be emitted:**
Cross-referencing `docs/evals/matrix_eval.json`, the following would likely be extracted:
- `REFLEX-M13` ("We propose Reflexion, a novel framework to reinforce language agents not by updating weights, but instead through linguistic feedback.")
- `COT-M12` ("is potentially applicable (at least in principle) to any task that humans can solve via language.")
- `REACT-M14` ("we present ReAct, a general paradigm to combine reasoning and acting with language models for solving diverse language reasoning and decision making tasks")

**Risk of false positives:**
Broadening the scope sweeps in sentences that are purely descriptive or background. For example:
- "We use a transformer with 12 layers."
- "ReAct is a language agent."
- "We implement the standard self-reflection step as a final pass." (Reflexion)
These are statements of architectural fact, not refutable claims.

**Impact on `positive_total`:**
Extracting these non-empirical statements increases the total claim denominator. Since these claims are either unmeasurable (and thus `not_supported`) or simple architectural facts, they will dilute the `positive_hits` ratio. The raw number of positive hits will remain the same, but the percentage will artificially drop.

## 6. Interaction between the two defects

**Defect 1 must be fixed before (or concurrently with) Defect 2.**

If Defect 2 is fixed first, the extractor will start emitting non-empirical positioning claims (like REACT-M14). The auditor will correctly label these as `not_supported` (as they are unsupported generalizations). 
However, because Defect 1 exists, the grounding checker only knows how to verify if a passage *supports* a claim. The passages that explicitly *refute* these newly surfaced claims will be marked `Fail`. The rollup logic will see all `Fail` spans and mark the entire claim as `missing=true` ("all evidence spans failed grounding").
Visually, the UI will display these correctly refused claims with red "Fail" badges or as "Missing Evidence," degrading the user experience and making the system look broken.

## 7. Ranked recommendation

### 1. Fix Defect 1 (Grounding Checker)
* **Proposed fix:** Pass the `claim.label` into the grounding call. Modify the prompt to condition the instruction on the label (e.g., if `not_supported`, ask if the quote justifies the refusal). Retain the 3-tier Pass/Partial/Fail enum.
* **Files touched:** `extraction/grounding.py`, `extraction/prompt_loader.py`, `prompts/audit_system.txt`, `prompts/audit_fewshot.json`.
* **Estimated effort:** Low (Pure Python and prompt logic; no DB/C# updates).
* **Risk:** Low (Isolated to grounding logic).
* **Needs decisions.md entry:** Yes.

### 2. Fix Defect 2 (Extractor Scope)
* **Proposed fix:** Broaden the instruction in `extract_claims_system.md` from "empirical assertion" to include "methodological positioning".
* **Files touched:** `prompts/extract_claims_system.md`.
* **Estimated effort:** Low (Prompt tuning only).
* **Risk:** Medium (Risk of extracting pure architectural descriptions, diluting `positive_hits`).
* **Needs decisions.md entry:** Yes.

**Ship Order:** Defect 1 must ship first. Fixing Defect 2 without Defect 1 will cause a cascade of false "Missing Evidence" badges for correctly refused claims.
