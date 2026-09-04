# Architectural Audit: Extraction & Grounding Pipeline
**Date**: 2026-09-04

This report traces the claim extraction and grounding pipeline to answer one core question: *When the auditor judges a claim, what text is actually in its context window?*

## 1. Ingestion path

The pipeline begins in `main.py`, where RabbitMQ messages trigger `process_document`:
1. The PDF is downloaded and passed to `extract_pdf_text_sync`.
2. PyMuPDF (`fitz`) extracts the text page-by-page into a single string:
   ```python
   final_text = ''
   with fitz.open(local_path) as doc:
       page_count = doc.page_count
       for page in doc:
           final_text += page.get_text()
   ```
3. `final_text` is passed untouched to Qdrant (for chat) and the extraction engine.

**What fitz produces:**
Because `fitz.get_text()` merely dumps character streams, table grids and column alignments are completely flattened into newline-separated tokens. Page and section structures are not preserved as semantic markers (e.g., Markdown).

*Sample of `react.pdf` (Table 1) as seen by the pipeline:*
```text
Prompt Methoda
HotpotQA
Fever
(EM)
(Acc)
Standard
28.7
57.1
CoT (Wei et al., 2022)
29.4
56.3
CoT-SC (Wang et al., 2022a)
33.4
60.4
Act
25.7
58.9
ReAct
27.4
60.9
```
**Word-fusion/Destruction Prevalence:** Extremely high for tabular data. Column relationships (e.g., matching "27.4" to "ReAct" under the "HotpotQA" header) are severed, appearing as disjointed lines.

## 2. Chunking and embedding

While extraction operates on the full text, chunking is performed separately for chat endpoints (`RAGService.py`):
- **Strategy:** `RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200, separators=["\n\n", "\n", r"(?<=\. )", " ", ""])`.
- **Model:** `BAAI/bge-small-en-v1.5` (Dimensionality: 384).
- **Table Handling:** There is no specific logic for tables. Tables are treated as standard strings and arbitrarily split mid-row if the chunk size ceiling is hit.
- **Qdrant Payload:**
  ```json
  {
      "filename": "...",
      "text": "chunk content...",
      "chunk_index": 0,
      "file_id": "uuid"
  }
  ```

## 3. Context assembly per LLM call

The extraction engine (`extraction/engine.py`) makes four distinct LLM calls. **None of these calls use retrieval (RAG)**; they act directly on the full document text.

1. **Metadata Extractor (Prompt 1)**
   - **Input:** System prompt + Few-shot examples + FULL `paper_text`.
   - **Model:** `settings.llm_extraction_model` (`gemini-3.6-flash`).
   - **Token Count:** ~20k-30k tokens.
2. **Claim Extractor (Prompt 2, Call 2)**
   - **Input:** System prompt + Few-shot examples + FULL `paper_text`.
   - **Model:** `settings.llm_extraction_model` (`gemini-3.6-flash`).
   - **Token Count:** ~20k-30k tokens.
3. **Claim Auditor (Prompt 2, Call 3 - Per Claim)**
   - **Input:** System prompt + FULL `paper_text` + 1 claim's verbatim/summary.
   - **Model:** `settings.llm_audit_model` (`gemini-3.1-flash-lite`).
   - **Token Count:** ~20k-30k tokens.
4. **Claim Structurer (Prompt 2, Call 4 - Per Claim)**
   - **Input:** System prompt + claim verbatim/summary + auditor's free-text reasoning.
   - **Model:** `settings.llm_extraction_model` (`gemini-3.6-flash`).
   - **Token Count:** < 1k tokens (no paper text).

## 4. The auditor's context — deepest section

The auditor constructs its prompt in `extraction/prompt_loader.py` via `build_gemini_messages_for_audit`:

```python
def build_gemini_messages_for_audit(
    paper_text: str,
    claim_text_verbatim: str,
    claim_summary: str,
) -> list[dict]:
    # ...
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
```

- **Does the auditor see the full paper?** Yes. `paper_text` is the complete string extracted by `fitz`.
- **Could a contradicting passage ever be included?** Yes, it is explicitly in the context. There is no chunk filtering.
- **Estimate for `react.pdf`:** Table 1 **is** firmly in the auditor's context when judging the abstract's SoTA claim. The failure is not a retrieval gap; it is an LLM comprehension gap caused by the flattened table layout.

## 5. Grounding checker

The grounding module (`extraction/grounding.py`) acts on the LLM's extracted spans to apply a deterministic check:
- **RapidFuzz Stage:** Filters the LLM's cited `source_text` against the full `paper_text` using `fuzz.partial_ratio >= 88`.
- **LLM Span Audit:** Surviving spans are fed into an audit model (`groq/openai/gpt-oss-20b` with `gemini-3.1-flash-lite` fallback). It extracts 500–1500 chars of surrounding context snapped to paragraph boundaries. The LLM judges if the quote supports the claim via a `Pass`, `Partial`, or `Fail` rubric.
- **DTO Override Check:** In `Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs`, the API maps the extractor's label directly to `ClaimDto.Label` and the grounder's status to `ClaimDto.GroundingStatus`. 
  ```csharp
  labelConverter.ConvertToProvider(c.Label) as string ?? "",
  c.Missing,
  c.Reason,
  statusConverter.ConvertToProvider(c.GroundingStatus) as string ?? "",
  ```
  `grounding_status` is returned orthogonally and does **not** override the `Label` property in the payload.

## 6. Eval coverage

The eval matrix (`eval/matrix_runner.py`) aggregates the following metrics:
- `correct_refusals`, `refusal_rate`
- `refused_by_label`, `refused_by_omission`, `refused_by_grounding`
- `positive_hits`, `positive_total`
- `false_rejections`, `false_rejection_rate`, `positive_hit_floor`

**Missing Metrics:** There are absolutely no retrieval-stage metrics (Context Precision, Context Recall), which is expected since the extraction pipeline bypasses RAG entirely. There is also no judge-calibration metric evaluated within the standard run.

**Gold Matcher Check:** `docs/evals/matcher_gold.json` is wired into a runnable test (`eval/tests/test_matcher.py` -> `test_matcher_gold_set_accuracy()`), but it is tagged with `@pytest.mark.integration` and skipped by default in standard local runs unless explicitly invoked.

## 7. Findings and ranked hypotheses

Why do trap claims (like ReAct's SoTA claim vs. Table 1 results) land `supported`?

1. **Hypothesis: Table Layout Destruction (Highest Probability)**
   - **Evidence:** We confirmed the auditor receives the full paper text, including Table 1. However, `fitz` destroys tabular alignments, interleaving headers and values into a meaningless linear string of tokens. The auditor cannot visually align "Supervised SoTAb" with "67.5".
   - **Confirmation:** Hardcode a markdown-formatted version of Table 1 into the `react.pdf` text string right before the auditor call, and observe if it catches the contradiction.
   - **Fix Effort:** Medium. Requires swapping `fitz` for a vision-based layout parser (e.g., Azure Document Intelligence, LlamaParse) that retains tables as Markdown.

2. **Hypothesis: Flash-Lite Capacity Limit (Medium Probability)**
   - **Evidence:** The auditor uses `gemini-3.1-flash-lite` (`config.py` & `.env`). Finding a contradiction embedded deep inside a 20,000+ token context requires high 'needle-in-a-haystack' reasoning, which smaller lite models struggle with.
   - **Confirmation:** Change `LLM_AUDIT_MODEL` to `gemini-3.6-flash` or a `pro` model and re-run the matrix eval.
   - **Fix Effort:** Trivial. Change a single environment variable.

3. **Hypothesis: Over-weighting Abstract Claims (Lower Probability)**
   - **Evidence:** The auditor's prompt (`audit_claim_system.md`) might lack strong instructions to prioritize downstream empirical tables over the authors' own introductory assertions.
   - **Confirmation:** Update the prompt to explicitly weight "results, tables, and charts" over "abstracts and introductions."
   - **Fix Effort:** Low.

## 8. Experimental inventory readiness

- **Format:** `PaperMetadataLLM` (`schemas.py`) strictly types fields like `baselines_compared` and `ablation_studies` as `str` (free prose), instructing the LLM to write a sentence or two.
- **Sample Value:** Because it is free prose, it reads like: *"Datasets, benchmarks, tasks, or subjects evaluated on, with sizes if reported"*.
- **Assessment:** As currently constructed, this field **cannot** support a deterministic check like "is RL in the baselines list?". It would require parsing the free prose. To support deterministic checks, `schemas.py` must be updated to output a `list[str]` array.
- **Downstream Usage:** The metadata output is strictly routed to the database (`write_extraction_result`). It is **not** injected into the context of the claims extractor, auditor, or grounder.
