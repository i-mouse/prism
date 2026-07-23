# Extraction Engine Design: Paper Domain

## 1. Extraction Schema

**The Envelope Pattern**
Every field extracted from the paper will be wrapped in a strict envelope to guarantee traceability and support graceful refusal.
```json
{
  "value": "extracted content (string or array)",
  "source_text": "exact quote from the paper",
  "source_section": "section name (e.g., '3. Methodology')",
  "missing": false,
  "reason": "Populated only if missing=true (e.g., 'No ablation studies found')"
}
```

**Array-valued fields use array-of-envelopes, not envelope-with-array.**
Fields that are lists (`stated_claims`, `empirical_results`,
`baselines_compared`, `ablation_studies`, `experimental_confounds`,
`author_acknowledged_limitations`, `extrapolated_implications`) are
represented as arrays of individual envelopes rather than a single
envelope wrapping an array. This lets grounding checks run per-item
(each claim has its own source_text and passes/fails independently)
and makes correct refusal work at claim level rather than field level.
The Claim-Support Matrix also renders 1:1 from this shape.

**The Fields (Derived from First Principles)**
Instead of extracting the final views, we extract the *ground facts* required to render the four Product Brief sections. 

*Supporting the Claim-Support Matrix (Tier 1):*
1. `stated_claims`: (Array) The discrete, testable claims made by the authors in the abstract or introduction.
2. `empirical_results`: (Array) The specific quantitative or qualitative findings observed in the experiments.

*Supporting the Verdict (Tier 2):*
3. `primary_research_objective`: The overarching problem the paper attempts to solve. (Provides context for the verdict).
4. `headline_conclusion`: The final summary claim presented in the conclusion. (This is what the Verdict evaluates against `empirical_results`).

*Supporting Questions to Scrutinize (Tier 3):*
5. `sample_characteristics`: Details on sample size, demographics, or dataset composition.
6. `baselines_compared`: The control groups or prior state-of-the-art models used for comparison.
7. `ablation_studies`: Any tests performed to isolate the impact of specific components.
8. `experimental_confounds`: Variables or conditions mentioned that could skew results.

*Supporting Overstated Claims (Tier 3):*
9. `author_acknowledged_limitations`: What the authors explicitly admit their study does not cover.
10. `extrapolated_implications`: Broad generalizations made by the authors that extend beyond their specific test environment.

---

## 2. Where It Lives

**Placement: LangGraph Node (Python Worker)**
The extraction engine should be implemented as a dedicated node (or linear subgraph) within the existing LangGraph pipeline hosted on the Python Worker. 

**State Flow & Domain Inference:**
- **Explicit at Upload:** The Domain must be explicit at ingestion. Inferring the domain post-OCR is fragile, wastes tokens, and breaks deterministic routing. When the user uploads a paper, the `domain_id` is passed via the message bus (RabbitMQ locally today, Azure Service Bus in the deployed architecture).
- **Read/Write:** The LangGraph state initializes with `document_id` and `domain_id`. The node fetches the `PromptSchema` from the `Domain` table via the .NET API (or directly from the PostgreSQL checkpointer if shared). Post-extraction and grounding validation, the node writes the finalized JSON back to the `DocumentExtractor` table. 

---

## 3. Grounding for Structured Output

I strongly confirm the three-stage pipeline. It perfectly operationalizes the "correct refusal" engineering bet.

**The Pipeline:**
1. **Prompt Constraints:** The LLM is instructed to populate `source_text` and `source_section` for every extracted field, and to set `missing: true` if the paper lacks the information.
2. **Deterministic Check (RapidFuzz):** A fast, cheap fuzzy match to verify that `source_text` actually exists in the source document (threshold ~0.90 to account for whitespace/OCR artifacts). 
3. **LLM Audit (Batched):** A smaller, secondary prompt takes the surviving fields and asks: *"Does the quote [source_text] actually provide evidence for [value]?"* returning `PASS`/`FAIL`.

**Failure Semantics (Crucial):**
If a field fails Stage 2 (hallucinated quote) or Stage 3 (quote doesn't support the value), **do not fail the entire extraction.** Instead, mutate the field: set `value = null`, `missing = true`, and `reason = "Failed grounding audit: [Reason]"`. This localizes the failure and surfaces it honestly to the UI, transforming a hallucination into a successful "correct refusal."

---

## 4. Token Model

**Whole-Doc vs. Section Routing:**
For standard arXiv papers (15-20 pages), the text is approximately 15,000 to 20,000 tokens.
- **Recommendation:** Use **whole-doc scanning** for anything under ~40,000 tokens (roughly 30-40 pages). The LLM needs global context to evaluate claims (Abstract/Conclusion) against evidence (Methodology/Results), which are located at opposite ends of the document.
- **Section-Routing:** Only kicks in above 40,000 tokens to prevent needle-in-a-haystack degradation and latency spikes.

**Cost Estimates (Typical 20k token paper):**
- **GPT-4o-mini:** ~$0.15 per 1M input tokens ≈ **$0.003** per paper.
- **Gemini 1.5 Flash:** ~$0.075 per 1M input tokens ≈ **$0.0015** per paper.
Both models are trivially cheap for this context window. Latency, not cost, will be the primary constraint.

---

## 5. Eval Harness Shape

The eval harness must assert against the extracted JSON, not the UI views. It needs to test both extraction accuracy and correct refusals.

**Shape (`pytest` + `rapidfuzz`):**
```python
import pytest
from eval_core import load_golden_cases, run_extraction

@pytest.mark.parametrize("case", load_golden_cases("docs/golden_eval.json"))
def test_extraction_grounding(case):
    # 1. Execute extraction pipeline on the source document
    result = run_extraction(case.document_text, case.domain_schema)
    
    # 2. Iterate through expected field assertions
    for assertion in case.assertions:
        field = result.get_field(assertion.field_name)
        
        if assertion.is_grounding_negative:
            # The core engineering bet: Did we successfully refuse?
            assert field.missing is True, f"Failed refusal on {assertion.field_name}"
            assert field.reason is not None
        else:
            # Positive extraction: Did we get the right value and source?
            assert field.missing is False
            assert fuzzy_match(field.value, assertion.expected_value) >= 0.85
            assert fuzzy_match(field.source_text, assertion.expected_source) >= 0.90
```

---

## Deliberately Deferred (Not doing today)
- Azure deployment mechanics (Container Apps, Managed Identity).
- Multi-agent workflows (Methodology Analyst vs. Results Verifier).
- Cross-paper literature consistency.
- UI View rendering (Verdict, Matrix). *We are only building the JSON extraction engine and the eval harness to prove it works.*
