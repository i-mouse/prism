# Audit: Auditor Scope & Trap Claim Labeling (2026-09-09)

## Q1 — Verbatim Auditor Reasoning for the 4 Traps

The auditor's free-text reasoning shows it is grading the *truth of the literal statement* (did the authors say this?) rather than *scope-vs-evidence* (did they prove the full breadth of what they said?).

*   **REFLEX-M13** (Expected `not_supported`, Actual `supported`):
    > "The claim asserts that the authors propose Reflexion, a framework designed to reinforce language agents using linguistic feedback rather than model weight updates. The paper directly presents and describes this exact concept throughout the text... the Abstract contains the verbatim assertion of this contribution. VERDICT: supported"
*   **COT-M09** (Expected `partially_supported`, Actual `supported`):
    > "The claim states that experiments on three large language models show chain-of-thought prompting improves performance across arithmetic, commonsense, and symbolic reasoning tasks. This sentence appears verbatim in the Abstract. The paper's experimental sections... empirically demonstrate these gains. VERDICT: supported"
*   **COT-M10** (Expected `partially_supported`, Actual `supported`):
    > "The claim asserts that chain-of-thought reasoning can be elicited in sufficiently large off-the-shelf language models simply by adding chain-of-thought examples to few-shot prompting exemplars. This statement appears verbatim in Section 2... The paper validates this across multiple off-the-shelf models... VERDICT: supported"
*   **REACT-M14** (Expected `not_supported`, Actual `supported`):
    > "The claim asserts the presentation of ReAct as a general paradigm combining reasoning and acting with language models for solving diverse language reasoning and decision-making tasks. The paper explicitly defines and evaluates ReAct across two distinct language reasoning benchmarks... and two interactive decision-making benchmarks... VERDICT: supported"

In all cases, the auditor points to the fact that the statement appears verbatim in the text (usually the Abstract) as its primary justification for "supported."

## Q2 — Prompt Clauses Causing "Supported"

In `prompts/audit_claim_system.md`, two specific clauses cause this failure mode:

1.  **Step 4 (`supported` definition):**
    > `- VERDICT: supported — the paper contains a direct verbatim quote matching the claim's exact scope.`
2.  **Step 3 (The hard requirement):**
    > `This is a hard requirement: you may only conclude "supported" if you can produce a verbatim quote from the paper that directly backs the claim.`

Because trap claims are literally extracted from the Abstract or Introduction, the auditor easily finds a "direct verbatim quote" (the claim itself). The prompt incorrectly equates *finding a quote of the claim* with *finding evidence for the claim*.

## Q3 — Why the "broader language" Clause Isn't Firing

The auditor operates sequentially. When it evaluates the `supported` definition, it asks: "does the paper contain a direct verbatim quote matching the claim?" Yes, the abstract contains it. This satisfies the `supported` condition immediately. 

Because `supported` is satisfied by the mere existence of the sentence in the paper, the auditor stops reasoning and never reaches the `partially_supported` check for "broader language than the experimental scope justifies."

## Q4 — `not_supported` vs `partially_supported` Rule

*(Correction: The user prompt mistakenly listed COT-M09 and COT-M10 as expecting `not_supported`. `matrix_eval.json` confirms they expect `partially_supported`.)*

The rule distinguishing them in the golden set is the **presence vs. absence of underlying evidence**:

*   **`not_supported` (e.g., REFLEX-M13, REACT-M14):** The claimed scope was completely untested. The generalization domain is untested (Pattern A) or the comparative baseline class is missing (Pattern B). There is NO experimental evidence for the broad claim.
*   **`partially_supported` (e.g., COT-M09, COT-M10, REFLEX-M08):** The paper *did* test the domain or method, but the evidence is noisy, has major caveats, or only applies to a subset. (e.g., COT-M09 improves commonsense answers but has incorrect reasoning paths; COT-M10 works but the appendix admits it requires heavy prompt engineering).

## Q5 — Minimum Viable Prompt Change

To fix this, we must tighten Step 3 and Step 4 to explicitly forbid treating Abstract assertions as evidence, and clarify the separation between `partially_supported` and Pattern A/B traps.

**Proposed Rewrite for Step 3:**
```markdown
**Step 3 — Find the verbatim quote of the EVIDENCE.**
If the paper does support the claim, find the exact sentence (or short passage) in the paper that *proves* it. This is a hard requirement: you may only conclude "supported" if you can produce a verbatim quote from the paper's experimental results, data, or proofs that directly backs the claim. Quoting the Abstract or Introduction where the authors simply assert the claim is NOT sufficient; you must quote the underlying evidence.
```

**Proposed Rewrite for Step 4:**
```markdown
**Step 4 — State your verdict in plain prose.**
Write 2-5 sentences explaining what you found. Then state one of these three verdicts explicitly, in these exact words:

- VERDICT: supported — the paper's experimental results, data, or proofs fully back the claim's exact scope. (Note: A verbatim quote of the claim from the Abstract or Introduction is NOT evidence. You must find the results that prove it.)
- VERDICT: partially_supported — the paper's experiments support part of the claim but not all of it, OR the experiments support it but the results are caveated, noisy, or only apply to a subset.
- VERDICT: not_supported — the paper's evidence for the claim's specific scope is completely absent. Comparative gap (claimed class not in baselines), generalization gap (broad domain not tested), or missing measurement (property claimed but not measured). Use this, NOT partially_supported, for Pattern A and Pattern B claims.
```

## Q6 — Risk Assessment

*   **False Rejections Risk:** Moderate. If a paper genuinely proves a claim in the Abstract but the proof isn't in a traditional "Results" section (e.g., a purely theoretical/mathematical paper), the auditor might struggle to find "experimental results" and reject it. The prompt rewrite explicitly includes "data, or proofs" to mitigate this.
*   **Scope Reliability:** Gemini 3.6-flash handles scope-checking well when explicitly instructed to do so. The current failure is a definitional loophole (equating the Abstract quote with evidence), not a failure of reasoning capacity.
*   **Fallback Acceptability:** If the 4 traps flip from `supported` to `partially_supported` instead of `not_supported`, this is still a major win. The family eval metric treats `partially_supported` as a correct refusal (a PASS), meaning the system correctly identified that the claim was overstated. While strict `not_supported` is ideal for Pattern A/B, a hedge is infinitely better than waving it through as fully `supported`.
