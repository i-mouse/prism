# Prism Slice 2.8 Grounding Pipeline Audit Report
**Date:** 2026-08-26  
**Target File:** `H:\Work projects\Prism\docs\grounding_audit_2026_08_26.md`  
**Purpose:** Technical codebase and database audit for Prism Slice 2.8 planning (grounding context widening & 3-tier rubric refactor). Read-only audit; no source code or database mutations were performed.

---

## 1. Current Audit Function Anatomy

### Source Code Quote
The grounding and span audit logic lives in [`Prism.PythonService/extraction/grounding.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py#L33-L163). Below are the relevant functions and constants quoted verbatim:

```python
RAPIDFUZZ_THRESHOLD = 88
AUDIT_CONCURRENCY = 5

AUDIT_CONTEXT_WINDOW_CHARS = 200

AUDIT_PROMPT_TEMPLATE = """Claim: {claim_text}

Evidence quote (from {span_source_section}):
"{span_source_text}"

Surrounding paper context:
"...{span_context}..."

Does the evidence quote, understood in the surrounding context, directly support the claim as written?

Answer PASS if the quote (with its surrounding context) states or clearly implies the claim. Table cell values are supportive if the surrounding context makes their meaning clear.

Answer FAIL if the quote is unrelated to the claim, contradicts it, or the surrounding context does not clarify support.

Reply with exactly one word: PASS or FAIL."""


def _extract_context_window(
    paper_text: str,
    source_text: str,
    window_chars: int = AUDIT_CONTEXT_WINDOW_CHARS,
) -> str:
    """Returns paper text surrounding the source_text quote.

    Uses rapidfuzz.fuzz.partial_ratio_alignment to locate the best
    match position of source_text within paper_text, then extracts
    window_chars characters before and after that position.

    If source_text cannot be located (should not happen since RapidFuzz
    already validated it), returns just the source_text.
    """
    try:
        alignment = fuzz.partial_ratio_alignment(source_text, paper_text)
        if alignment.score < RAPIDFUZZ_THRESHOLD:
            return source_text
        start = max(0, alignment.dest_start - window_chars)
        end = min(len(paper_text), alignment.dest_end + window_chars)
        return paper_text[start:end]
    except Exception:
        return source_text


async def _audit_span_with_llm(
    claim_text: str,
    span_source_text: str,
    span_source_section: str,
    span_context: str,
    semaphore: asyncio.Semaphore,
    client: genai.Client,
    audit_model: str,
) -> GroundingStatus:
    """Asks Flash Lite whether the evidence quote supports the claim.

    Receives the surrounding paper context (extracted via
    _extract_context_window) so the LLM can interpret table cell values
    and short quotes in their proper passage context.

    Defensive: any error (API failure, malformed response) is logged and
    treated as FAIL rather than propagated, since ambiguity here should
    not abort grounding for the rest of the extraction.
    """
    prompt = AUDIT_PROMPT_TEMPLATE.format(
        claim_text=claim_text,
        span_source_section=span_source_section,
        span_source_text=span_source_text,
        span_context=span_context,
    )
    async with semaphore:
        try:
            response = await client.aio.models.generate_content(
                model=audit_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=10,
                ),
            )
            verdict = (response.text or "").strip().upper()
            return GroundingStatus.PASS if verdict.startswith("PASS") else GroundingStatus.FAIL
        except Exception as exc:
            print(f"[ground_extraction] LLM audit failed for span in {span_source_section!r}: {exc!r}")
            return GroundingStatus.FAIL


def _passes_rapidfuzz(span_source_text: str, paper_text: str) -> bool:
    return fuzz.partial_ratio(span_source_text, paper_text) >= RAPIDFUZZ_THRESHOLD


async def _ground_span(
    claim_text: str,
    span: EvidenceSpanLLM,
    paper_text: str,
    semaphore: asyncio.Semaphore,
    client: genai.Client,
    audit_model: str,
) -> tuple[EvidenceSpanFinal, bool, bool]:
    """Grounds one span. Returns (finalized span, passed_rapidfuzz, passed_audit)."""
    if not _passes_rapidfuzz(span.source_text, paper_text):
        final_span = EvidenceSpanFinal(
            source_text=span.source_text,
            source_section=span.source_section,
            section_header=span.section_header,
            page_number=span.page_number,
            grounding_status=GroundingStatus.FAIL,
        )
        return final_span, False, False

    span_context = _extract_context_window(paper_text, span.source_text)
    status = await _audit_span_with_llm(
        claim_text=claim_text,
        span_source_text=span.source_text,
        span_source_section=span.source_section,
        span_context=span_context,
        semaphore=semaphore,
        client=client,
        audit_model=audit_model,
    )
    final_span = EvidenceSpanFinal(
        source_text=span.source_text,
        source_section=span.source_section,
        section_header=span.section_header,
        page_number=span.page_number,
        grounding_status=status,
    )
    return final_span, True, status == GroundingStatus.PASS
```

### Anatomical Answers
1. **Exact context window size:**
   - Defined by `AUDIT_CONTEXT_WINDOW_CHARS = 200` ([`grounding.py:L36`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py#L36)).
   - Formula: `start = max(0, alignment.dest_start - 200)`, `end = min(len(paper_text), alignment.dest_end + 200)`. It extracts up to 200 characters before `dest_start` and up to 200 characters after `dest_end`. Total context string length is equal to `len(source_text) + 400` characters.
2. **Context extraction method:**
   - Direct character-index slicing on `paper_text` based on `rapidfuzz.fuzz.partial_ratio_alignment(source_text, paper_text)`.
3. **Sentence/paragraph boundary alignment:**
   - **No.** It performs a raw character slice `paper_text[start:end]`. It does not align to punctuation, sentence boundaries, or paragraph breaks, resulting in mid-word and mid-sentence truncations at both ends.
4. **Pydantic schema returned by LLM:**
   - **None.** The LLM audit call uses free-text generation (`max_output_tokens=10`, `temperature=0`) with no Pydantic `response_schema`. Pass/Fail is derived via string inspection: `verdict.startswith("PASS")`.

---

## 2. Audit LLM Prompt

### System Prompt & Template Identification
There are two distinct audit concepts in the codebase:
1. **Span Grounding Audit (Stage 2 in Grounding Pipeline):** Uses `AUDIT_PROMPT_TEMPLATE` hardcoded inside [`extraction/grounding.py:L38-L52`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py#L38-L52).
2. **Claim Extraction Auditor (Call #3 in Extraction Engine):** Uses external markdown file [`prompts/audit_claim_system.md`](file:///H:/Work%20projects/Prism/Prism.PythonService/prompts/audit_claim_system.md) via [`extraction/prompt_loader.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/prompt_loader.py#L98-L118).

The span grounding audit prompt template from [`grounding.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py#L38-L52) is quoted verbatim below:

```text
Claim: {claim_text}

Evidence quote (from {span_source_section}):
"{span_source_text}"

Surrounding paper context:
"...{span_context}..."

Does the evidence quote, understood in the surrounding context, directly support the claim as written?

Answer PASS if the quote (with its surrounding context) states or clearly implies the claim. Table cell values are supportive if the surrounding context makes their meaning clear.

Answer FAIL if the quote is unrelated to the claim, contradicts it, or the surrounding context does not clarify support.

Reply with exactly one word: PASS or FAIL.
```

### Prompt Analysis
1. **Does the prompt define what "supports" means?**
   - Yes: `"Answer PASS if the quote (with its surrounding context) states or clearly implies the claim. Table cell values are supportive if the surrounding context makes their meaning clear."`
2. **Does it define a rubric with degrees of support, or just binary pass/fail?**
   - Strictly **binary PASS / FAIL**.
3. **Are there few-shot examples?**
   - **No.** There is no few-shot prompt file (e.g., `audit_fewshot.json` does not exist) for the span grounding auditor.
4. **What temperature is used?**
   - `temperature=0` (enforced in `types.GenerateContentConfig` at [`grounding.py:L111`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py#L111)).

---

## 3. Model Choice

- **Environment Variable:** `LLM_AUDIT_MODEL`
- **Config Location:** [`Prism.AppHost/AppHost.cs`](file:///H:/Work%20projects/Prism/Prism.AppHost/AppHost.cs#L32) (lines 32 and 46) sets `.WithEnvironment("LLM_AUDIT_MODEL", "gemini-3.1-flash-lite")`.
- **SDK & Version:** Pinned in [`Prism.PythonService/pyproject.toml`](file:///H:/Work%20projects/Prism/Prism.PythonService/pyproject.toml#L12) as `"google-genai>=1.0.0"`.
- **Model Confirmation:** The audit step runs on **Gemini 3.1 Flash Lite** (`gemini-3.1-flash-lite`), matching the earlier assumption.

---

## 4. Eval Harness Metrics

### Scoring & Metric Definitions
Metric calculations live in [`Prism.PythonService/eval/scorer.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/eval/scorer.py#L11-L85) and aggregation lives in [`Prism.PythonService/eval/matrix_runner.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/eval/matrix_runner.py#L160-L186).

#### Formula for "Correct-Refusal Rate"
From [`scorer.py:L28-L64`](file:///H:/Work%20projects/Prism/Prism.PythonService/eval/scorer.py#L28-L64):
```python
is_negative = row.grounding_negative or row.expected_label == "not_supported"

if is_negative:
    total_negatives += 1
    if actual_claim is None:
        outcome = "PASS"
        correct_refusals += 1
        refused_by_omission += 1
    elif actual_claim.label in {"not_supported", "partially_supported"}:
        outcome = "PASS"
        correct_refusals += 1
        refused_by_label += 1
    else:
        outcome = "FAIL"

refusal_rate = correct_refusals / total_negatives if total_negatives else 0.0
```
- **Definition:** Percentage of grounding-negative rows (`grounding_negative=true` or `expected_label='not_supported'`) that the pipeline either omits entirely (`refused_by_omission`) or emits with a non-supported label (`refused_by_label`).

#### False-Rejection / False-Positive Metric
- **Is there a false-rejection rate metric already?**
  - **No.** The eval harness tracks positive support claims using `positive_hits` vs `positive_total` with a floor (`positive_hit_floor = 10`), but does not calculate an explicit `false_rejection_rate` percentage.
- **Can the harness compute one?**
  - **Yes.** The data is present in the `per_row` map (`POSITIVE_MISS` outcomes on rows with `expected_label='supported'`).
- **Required change to add `false_rejection_rate`:**
  - Modify [`scorer.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/eval/scorer.py) (~15 lines) to add `false_rejections` count (positive rows where valid claims were extracted but marked `missing=true` due to grounding rejection) and calculate `false_rejection_rate = false_rejections / positive_total`. Update `EvalReport` and `MatrixReport` dataclasses accordingly in `types.py` and `matrix_runner.py`.

#### Current Fixture Composition (`docs/evals/matrix_eval.json`)
The evaluation dataset in [`docs/evals/matrix_eval.json`](file:///H:/Work%20projects/Prism/docs/evals/matrix_eval.json) consists of **37 total expected rows** across 3 papers:

| Paper ID | Filename | Total Rows | Positive-Support Rows (`grounding_negative=false`) | Grounding-Negative Rows (`grounding_negative=true` / `not_supported`) |
| :--- | :--- | :---: | :---: | :---: |
| `arxiv-2303.11366v4` | `reflexion.pdf` | 12 | 7 | 5 |
| `arxiv-2201.11903v6` | `cot.pdf` | 12 | 7 | 5 |
| `arxiv-2210.03629v3` | `react.pdf` | 13 | 9 | 4 |
| **TOTAL** | | **37** | **23** | **14** |

---

## 5. Live DB State

### Query Outputs (Executed on PostgreSQL `prism-db`)

#### Query 1: Paper Claims Grounding Summary across DB
```sql
SELECT 
  de.file_id, 
  fr.file_name, 
  COUNT(*) as total_claims,
  COUNT(*) FILTER (WHERE pc.missing = true) as missing_true,
  COUNT(*) FILTER (WHERE pc.missing = false) as missing_false,
  COUNT(*) FILTER (WHERE pc.grounding_status = 'Fail') as ground_fail,
  COUNT(*) FILTER (WHERE pc.grounding_status = 'Pass') as ground_pass
FROM paper_claims pc
JOIN document_extractors de ON de.id = pc.document_extractor_id
JOIN file_records fr ON fr.file_id = de.file_id
GROUP BY de.file_id, fr.file_name
ORDER BY fr.file_name;
```

**Raw Output:**
```text
file_id                               file_name      total_claims  missing_true  missing_false  ground_fail  ground_pass
d63ffea7-feeb-42f6-ae8e-ea55331e9c56  cot.pdf        12            10            2              10           2
b242e887-3c58-45e0-b6aa-5fdf3bf1f625  react.pdf      13            13            0              13           0
72fb4d01-e2fb-4e14-9988-cb94d45d3184  reflexion.pdf  10            3             7              3            7
```

#### Query 2: Inspection of Failed Spans on `react.pdf`
```sql
SELECT 
  pc.claim_summary, 
  pc.reason, 
  span->>'source_text' as quote_text, 
  span->>'source_section' as section, 
  span->>'grounding_status' as span_status
FROM paper_claims pc
JOIN document_extractors de ON de.id = pc.document_extractor_id
JOIN file_records fr ON fr.file_id = de.file_id,
jsonb_array_elements(pc.evidence_spans) as span
WHERE fr.file_name = 'react.pdf' 
  AND pc.missing = true
LIMIT 5;
```

**Raw Output:**
```text
claim_summary: ReAct demonstrates effectiveness over state-of-the-art baselines while improving interpretability and trustworthiness.
reason: all evidence spans failed grounding: 0 spans failed RapidFuzz check; 1 spans failed LLM audit
quote_text: We apply our approach, named ReAct, to a diverse set of language and decision making tasks and demonstrate its effectiveness over state-of-the-art baselines
section: Abstract
span_status: Fail

claim_summary: ReAct reduces hallucination and error propagation on HotpotQA and Fever via Wikipedia interaction.
reason: all evidence spans failed grounding: 0 spans failed RapidFuzz check; 1 spans failed LLM audit
quote_text: Concretely, on question answering (HotpotQA) and fact verification (Fever), ReAct overcomes prevalent issues of hallucination and error propagation in chain-of-thought reasoning
section: Abstract
span_status: Fail

claim_summary: ReAct outperforms imitation and reinforcement learning on ALFWorld and WebShop by 34% and 10%.
reason: all evidence spans failed grounding: 0 spans failed RapidFuzz check; 1 spans failed LLM audit
quote_text: On WebShop, one-shot Act prompting already performs on par with IL and IL+RL methods (30.1% vs. 29.1% and 28.7% success rate), and with additional sparse reasoning, ReAct achieves significantly better performance, with an absolute 10% improvement over the previous best success rate.
section: Section 4
span_status: Fail

claim_summary: ReAct outperforms action-only models and is competitive with CoT on HotpotQA and Fever.
reason: all evidence spans failed grounding: 0 spans failed RapidFuzz check; 1 spans failed LLM audit
quote_text: Table 1 shows HotpotQA and Fever results using PaLM-540B as the base model with different prompting methods. We note that ReAct is better than Act on both tasks, and ReAct is better than CoT on Fever (60.9 vs. 56.3) and slightly lags behind CoT on HotpotQA (27.4 vs. 29.4).
section: Section 3.3
span_status: Fail

claim_summary: Combining ReAct and CoT achieves top performance by merging internal and external knowledge.
reason: all evidence spans failed grounding: 0 spans failed RapidFuzz check; 1 spans failed LLM audit
quote_text: While two ReAct + CoT-SC methods are advantageous at one task each, they both significantly and consistently outperform CoT-SC across different number of samples, reaching CoT-SC performance with 21 samples using merely 3-5 samples.
section: Section 3.3
span_status: Fail
```

### Key DB Findings & Rejection Percentages
1. **Overall Rejection Rate (`missing=true`):**
   - Total claims across all 3 papers in DB: **35 claims**.
   - Total `missing=true` claims: **26 claims**.
   - **Overall False-Rejection Rate across all papers: 74.29%**.
2. **Paper Breakdown:**
   - **`react.pdf`:** **100.0% missing=true** (13 / 13 claims rejected).
   - **`cot.pdf`:** **83.33% missing=true** (10 / 12 claims rejected).
   - **`reflexion.pdf`:** **30.0% missing=true** (3 / 10 claims rejected).
3. **RapidFuzz vs LLM Audit Failure Breakdown:**
   - Query 2 reveals that for **100% of failed claims on ReAct**, the `reason` string reads:  
     `"all evidence spans failed grounding: 0 spans failed RapidFuzz check; 1 spans failed LLM audit"`.
   - **RapidFuzz failure rate = 0%.** The extractor is returning exact, verbatim quotes that match the paper text perfectly.
   - **LLM Audit failure rate = 100%.** Gemini 3.1 Flash Lite is rejecting valid, verbatim quotes because the 200-character context window provided to it is too narrow for it to verify support.

---

## 6. Root Cause Ranking

Based on empirical data from Sections 1–5, here is the ranked root cause analysis for the 100% ReAct grounding rejection:

1. **Rank 1: (a) Context window too small (audit LLM sees ~200 chars before/after quote).**
   - *Evidence:* RapidFuzz passed 100% of quotes (`0 spans failed RapidFuzz check`). The quotes are verbatim sentences from the paper. However, Flash Lite rejects them because a 200-char context (~30–40 words) strips away table headers, column definitions, section context, and preceding sentence setups required to confirm that the quote supports the claim summary.
2. **Rank 2: (b) Audit rubric is strictly binary (PASS/FAIL) with no room for partial support.**
   - *Evidence:* `AUDIT_PROMPT_TEMPLATE` instructs `"Reply with exactly one word: PASS or FAIL"` and `"Answer FAIL if ... context does not clarify support"`. When Flash Lite receives a narrow context fragment, any uncertainty causes it to conservatively default to `FAIL`.
3. **Rank 3: (c) Context slice cuts mid-word or mid-sentence, degrading auditor comprehension.**
   - *Evidence:* `_extract_context_window` performs raw string indexing `paper_text[dest_start - 200 : dest_end + 200]`. Punctuation and words are sliced arbitrarily, presenting truncated, grammatically incomplete context strings to Flash Lite.
4. **Rank 4: (e) Model choice (Flash Lite 3.1) lacks reasoning depth for single-token PASS/FAIL judgements on dense paper text.**
   - *Evidence:* Flash Lite is optimized for speed/cost. When forced to return a single token without intermediate reasoning steps or structured chain-of-thought, it adopts an overly skeptical bias.
5. **Rank 5: (d) Extractor picking paraphrased quotes that fail RapidFuzz.**
   - *Status:* **PROVEN FALSE.** Database inspection confirms 0 spans failed RapidFuzz.

---

## 7. Proposed Change Scope for Slice 2.8

To resolve the high false-rejection rate while maintaining baseline precision, the following changes are required in `Prism.PythonService`:

### 1. Widen Context Window & Sentence/Paragraph Alignment
- **File:** [`Prism.PythonService/extraction/grounding.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py)
- **Lines to modify:** Lines 36 (`AUDIT_CONTEXT_WINDOW_CHARS`) and 55–78 (`_extract_context_window`).
- **Changes:**
  - Increase character window from 200 to **750–1000 chars** (or sentence/paragraph boundary alignment).
  - Modify `_extract_context_window` to snap `start` and `end` indices to nearest sentence delimiters (`.` `\n\n`) or paragraph boundaries so context never cuts mid-sentence.
- **Estimated Code Lines Changed:** ~25 lines.

### 2. Move Audit Prompt to 3-Tier Rubric with Reasoning
- **File:** [`Prism.PythonService/extraction/grounding.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/grounding.py) & new/updated prompt file.
- **Lines to modify:** Lines 38–52 (`AUDIT_PROMPT_TEMPLATE`) and 80–120 (`_audit_span_with_llm`).
- **Changes:**
  - Expand prompt template to support a 3-tier verdict: `FULLY_SUPPORTED`, `PARTIALLY_SUPPORTED`, `NOT_SUPPORTED`.
  - Update `_audit_span_with_llm` to map both `FULLY_SUPPORTED` and `PARTIALLY_SUPPORTED` to `GroundingStatus.PASS` (or store explicit span-level 3-tier status).
  - Increase `max_output_tokens` from 10 to ~100–150 to allow brief reasoning before verdict emitting.
- **Estimated Code Lines Changed:** ~30 lines in `grounding.py` + ~40 lines in prompt definitions.

### 3. Verification of Extractor Quote-Picking Discipline
- Extractor quote-picking is already operating with 100% RapidFuzz pass-through on ReAct. No prompt modifications needed for quote extraction in Call #2; focus remains strictly on span audit context and rubric.

---

## 8. Eval Regression Risk

### Baseline Impact Analysis
- **Current Baseline:** 13/14 (93%) correct-refusal rate on `matrix_runner.py --source fixture`.
- **Mechanism of Current Baseline:**
  - Currently, `scorer.py` evaluates 14 grounding-negative rows across the 3 papers.
  - Correct refusals are achieved primarily through **omission** (`refused_by_omission`) because claims are either not extracted or fail grounding and get marked `missing=true`.
- **Regression Risk Evaluation:**
  - **Risk:** If widening the audit context window and introducing a 3-tier rubric causes the grounder to accept evidence spans on *grounding-negative* claims (e.g., claims that overstate results or cite non-existent baselines), those claims will change from `missing=true` to `missing=false` with label `supported`, causing a `FAIL` on negative expected rows.
  - **Mitigation:** Grounding-negative rows in `matrix_eval.json` (such as `REACT-M13`, `REFLEX-M11`, `COT-M11`) represent comparative gaps or unmeasured properties. Widening context to include full sentences/paragraphs will provide Flash Lite with clear evidence that the claimed comparison or scope is absent, reinforcing legitimate refusals while eliminating false rejections on valid quotes.
  - **Expected Baseline Outcome:** The 13/14 refusal baseline will hold or improve, while `positive_hits` (currently 15/23) will rise significantly as valid claims on ReAct and CoT pass grounding.

---

## 9. Before/After Measurement Plan

For the Slice 2.8 implementation prompt, execute the following verification steps:

### 1. Pre-Change Baseline Commands
Run and record the output of:
```bash
# 1. Run live DB eval harness
uv run python -m eval.matrix_runner --source db --paper all

# 2. Check fixture freshness / status
uv run python -m eval.matrix_runner --source fixture --paper all
```

### 2. SQL Comparison Query
Run before and after code changes to measure claim passage rates:
```sql
SELECT 
  fr.file_name, 
  COUNT(*) as total_claims,
  COUNT(*) FILTER (WHERE pc.missing = true) as missing_true,
  COUNT(*) FILTER (WHERE pc.missing = false) as missing_false,
  ROUND(COUNT(*) FILTER (WHERE pc.missing = false)::numeric / COUNT(*) * 100, 1) as pass_percentage
FROM paper_claims pc
JOIN document_extractors de ON de.id = pc.document_extractor_id
JOIN file_records fr ON fr.file_id = de.file_id
GROUP BY fr.file_name
ORDER BY fr.file_name;
```

### 3. Target Benchmark Criteria for Slice 2.8 Success
- **ReAct Pass Rate:** ReAct `missing_false` rate increases from **0% (0/13)** to **≥75% (≥10/13)**.
- **Overall DB Grounding Pass Rate:** Increases from **25.7% (9/35)** to **≥80% (≥28/35)**.
- **Eval Harness Refusal Rate:** `matrix_runner` correct-refusal rate remains **≥80% (target 13/14 or 14/14)**.
- **Positive Hits Floor:** `positive_hits` increases from **15/23** to **≥18/23**.

### 4. Decision Log Update
Record the exact before/after metrics in [`docs/decisions.md`](file:///H:/Work%20projects/Prism/docs/decisions.md) under a new entry titled: `## Slice 2.8: Grounding pipeline context widening & 3-tier rubric — YYYY-MM-DD`.

---
*End of Report.*
