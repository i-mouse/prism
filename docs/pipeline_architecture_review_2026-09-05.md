# Architectural Audit: Prism Extraction & Grounding Pipeline vs. 2026 Practice
**Date**: 2026-09-05

This report provides a read-only architectural diagnosis of Prism's claim extraction and grounding pipeline, evaluated against 2026 published practices in automated scientific claim verification and LLM-as-a-judge frameworks.

## 1. What Prism actually does today (code-truth)

The Prism pipeline operates in a strictly sequential, acyclic flow. It bypasses retrieval (RAG) entirely, operating on the full document text at every stage.

### Stage 1: Extraction (`engine.py`)
1. **Metadata Extractor (Call 1)**: Extracts paper metadata (ignored in this audit).
2. **Claim Extractor (Call 2)**: Receives the full `paper_text` string (flattened by `fitz`). Prompted by `extract_claims_system.md` to extract empirical and methodological positioning claims. Emits a JSON list of `claim_text_verbatim` and `claim_summary`.

### Stage 2: Auditor (`engine.py`)
3. **Claim Auditor (Call 3)**: For *each* extracted claim, a distinct LLM call is made using `prompts/audit_claim_system.md`. It receives the full `paper_text` and the claim. It produces free-text prose ending in a `VERDICT: [supported|partially_supported|not_supported]` and `QUOTE:` / `SECTION:` pairs.
4. **Claim Structurer (Call 4)**: A trivial LLM call using `prompts/structure_verdict_system.md` that converts the free-text audit from Call 3 into a structured `ClaimLLM` JSON object. **The claim's label is irrevocably assigned here.**

### Stage 3: Grounding (`grounding.py`)
5. **RapidFuzz Gate**: Checks if the auditor's `QUOTE` spans actually exist in the `paper_text` (`fuzz.partial_ratio >= 88`). Spans that fail are marked `FAIL` and dropped from LLM auditing.
6. **Span Audit**: Surviving spans are fed to an LLM judge (Groq `gpt-oss-20b` with Gemini fallback) using `prompts/audit_system.txt`. The prompt receives the claim, the quote, 500-1500 chars of surrounding context, and crucially, **the auditor's `claim.label`**. It judges if the quote justifies the label using a `Pass`, `Partial`, `Fail` rubric.
7. **Rollup**: The span verdicts are aggregated into a `grounding_status` and `reason` string for the claim. **The original `label` is never altered.**

### Terminology Mismatches
- `prompts/audit_system.txt` is actually the **span grounder** prompt.
- `prompts/audit_claim_system.md` is the **per-claim auditor** prompt.
- `decisions.md` often conflates "audit" to mean either the claim labeler (Call 3) or the span grounder (Stage 2).

## 2. What 2026 practice recommends for each stage

Current 2026 scientific claim verification literature (e.g., SciFact benchmarks, CheckThat! CLEF 2026, MultiVerS architectures) establishes several canonical patterns:

- **Verdict Schema**: A three-class problem (SUPPORTS, REFUTES, NEI - Not Enough Information) is the industry standard.
- **Selective Escalation**: Rather than stuffing 30k tokens into every call, 2026 systems perform abstract-level reasoning first, escalating to full-text retrieval (RAG) only when uncertainty remains, optimizing cost and reducing "lost-in-the-middle" attention degradation.
- **Verdict-Aware Frameworks**: In LLM-as-a-judge pipelines, evaluation is linked directly to the expected verdict. Absence of failure evidence is treated as specific contributing evidence for NEI, rather than an ambiguous null.
- **Self-Preference Bias Mitigation**: LLM judges favor their own outputs (skewing scores by 10-25%). Best practice mitigates this via cross-family judging (e.g., Groq/Llama judging Gemini).
- **Reasoning-Before-Verdict (Constraint Priority Inversion)**: Forcing an LLM to generate reasoning tokens *before* committing to a verdict in structured output prevents the reasoning from bending to justify a prematurely generated label.
- **Multimodal Verification**: Datasets like SciClaimEval highlight the necessity of layout-aware parsing (vision models) over flattened text, as flattening destroys table alignments critical to empirical claims.

## 3. Alignment analysis — Prism vs 2026 practice

- **Claim Extraction & Context Assembly**: **DIVERGENT-CONCERNING**. Prism feeds the full ~20k-30k token `fitz`-flattened text into every call without chunking or layout retention. While it avoids RAG recall failures, it heavily incurs "lost-in-the-middle" penalties and structural blindness to tables.
- **Verdict Schema & Absence Detection (NEI)**: **ALIGNED**. Prism's `supported` / `not_supported` (with a refuting quote) / `partially_supported` maps cleanly to the canonical SUPPORTS / REFUTES / NEI triad.
- **Span Grounding & Verdict-Awareness**: **ALIGNED**. The 2026-09-05 PR explicitly passed the auditor's label to the grounder, making the grounding rubric "verdict-aware".
- **Reasoning-Before-Verdict**: **ALIGNED**. The 2026-08-27 decision to use free-text prose for Call 3 and the `reasoning` field first in `SpanAuditVerdict` successfully implements Constraint Priority Inversion protection.
- **Self-Preference Bias Mitigation**: **ALIGNED**. Prism naturally implements cross-family judging by using Gemini for extraction and Groq (`gpt-oss-20b`) for primary span auditing.

## 4. Failure mode inventory

| Failure Mode | Hit by Prism? | Protection Type | Description |
| :--- | :--- | :--- | :--- |
| **Answer-before-reasoning collapse** | Yes (historically) | **Structural** | Fixed via 3-call split and reasoning-first schema (`SpanAuditVerdict`). |
| **Silent hallucinated quotes** | Yes (historically) | **Structural** | Blocked entirely by `RapidFuzz` gate before span audit. |
| **Loop instability** | No | **Structural** | The pipeline is strictly acyclic. Grounding does not override labels. |
| **Sycophancy / Self-preference bias** | Unlikely | **Ad-hoc** | Mitigated by using hybrid providers (Gemini extract, Groq ground). |
| **Over-affirmation on ambiguous claims** | Yes (react.pdf) | **Ad-hoc** | Partially mitigated by auditor prompt v2 (Pattern A/B few-shots), but still vulnerable due to zero-shot context limits. |
| **Absence-detection failure (NEI)** | Yes | **None** | Prism relies on the LLM recognizing the *absence* of evidence across 20k tokens, which frequently collapses into false `supported` verdicts. |
| **Table destruction via naive parsing** | Yes (react.pdf) | **None** | `fitz` destroys column alignments, making contradicts in Table 1 invisible to the auditor. |
| **Lost-in-the-middle on long context** | Yes | **None** | Feeding full paper text to Flash-Lite (and even Flash 3.6) degrades reasoning on deeply embedded contradictions. |

## 5. The label-derivation finding — full analysis

Section 4 of the `two_defects` report correctly states the auditor is a distinct stage.
A code trace of `engine.py` confirms that the claim label (`supported`, `partially_supported`, `not_supported`) is exclusively generated by Call 3 (`_call_gemini_freetext` using `audit_claim_system.md`), and formatted into a struct by Call 4.

The recent 2026-09-05 PR passes the `claim.label` into the grounding pipeline (`grounding.py`), but **it does not create a feedback loop**. `grounding.py` strictly uses the label to contextualize its rubric (e.g., if label is `not_supported`, a quote that refutes the claim is marked `PASS`). The grounder returns a `grounding_status` (Pass/Partial/Fail) and a `reason` string, which are stored *alongside* the `label` on the `ClaimFinal` DTO.

**Stability:** The pipeline is completely stable and acyclic. Running the same paper twice with the same outputs will produce identical behavior. The grounder validates the auditor; it never overrides it.

## 6. Options for architectural divergence

### Divergence: Full-context extraction vs. Retrieval (RAG)
Prism passes 20k-30k tokens of flattened text directly to the auditor, causing table destruction and lost-in-the-middle failures.

- **Option A: Keep current architecture, patch parsers.** Swap `fitz` for a vision/layout-aware parser (e.g., Azure Document Intelligence or LlamaParse) to retain tables as Markdown. Keep passing full text.
  - *Fixes:* Table destruction.
  - *Misses:* Lost-in-the-middle, absence-detection on long contexts.
  - *Effort:* Low.
- **Option B: Selective Escalation (2026 Canonical).** Extract claims from the abstract/intro. Use a hybrid RAG retrieval step to pull relevant chunks/tables, and audit *only* against those chunks.
  - *Fixes:* Lost-in-the-middle, table destruction (if chunked correctly).
  - *Misses:* Higher complexity.
  - *Effort:* High. Requires significant rewrite of `engine.py`.

## 7. Ranked recommendation

**Recommendation: Option A (Keep current architecture, swap to layout-aware parser).**

*Rationale based on constraints ($10/mo budget, solo developer, 17 golden rows, hiring artifact):*
1. **The current architecture works and is defensible.** The 3-call split, the RapidFuzz gate, the reasoning-first schema, and the verdict-aware grounding are all closely aligned with 2026 LLM-as-a-judge best practices.
2. **Rewriting to RAG is a massive risk.** Implementing Option B would discard the already-shipped, functioning `RapidFuzz` gate and stable concurrency model. RAG introduces retrieval-miss failures, which are harder to debug than context-window failures.
3. **The highest ROI fix is parsing.** The `two_defects` report proved the auditor *is* looking at the tables, but cannot read them because `fitz` destroys the layout. Swapping to Azure Document Intelligence (Markdown output) directly addresses the trap-claim failures (react.pdf Table 1) without touching the architecture.

**What NOT to change:**
- **Do not merge the auditor and structurer.** The reasoning-first split (Call 3 -> Call 4) is mathematically proven to reduce constraint priority inversion.
- **Do not remove the RapidFuzz gate.** Deterministic scripting for verifiable steps is a core 2026 principle.
- **Do not introduce a feedback loop.** Keep the grounder as a strictly downstream verification step.

## 8. Terminology cleanup

To prevent future confusion, the following renames are proposed:
1. `prompts/audit_system.txt` → `prompts/ground_span_system.txt`
2. `prompts/audit_fewshot.json` → `prompts/ground_span_fewshot.json`
3. `prompts/audit_claim_system.md` → `prompts/audit_system.md`

In documentation (`decisions.md`), strictly use **"Claim Auditor"** to refer to the LLM that assigns the label (`engine.py`), and **"Grounding Checker"** to refer to the LLM/RapidFuzz pipeline that validates the quotes (`grounding.py`).

## 9. Comparison table

| Stage | Prism today | 2026 canonical | Alignment | Effort to align |
| :--- | :--- | :--- | :--- | :--- |
| **Claim Extraction** | Full document text | Full document or Abstract | DIVERGENT-DEFENSIBLE | - |
| **Evidence Retrieval** | None (Full context) | Selective escalation / RAG | DIVERGENT-CONCERNING | High (Redesign) |
| **Verdict Prediction** | Supported/Partially/Not | SUPPORTS/REFUTES/NEI | ALIGNED | - |
| **Judge Calibration** | Reasoning-first | Constraint Priority Inversion | ALIGNED | - |
| **Bias Mitigation** | Groq/Gemini hybrid | Cross-family meta-judge | ALIGNED | - |
| **Document Parsing** | Naive string flatten (`fitz`) | Multimodal / Layout-aware | DIVERGENT-CONCERNING | Low (Swap parser) |
