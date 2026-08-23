# Label Grounding Audit

## 1. Schema semantics — what label MEANS in the pipeline

In `Prism.PythonService/extraction/schemas.py`, the schemas are documented as follows:

- `ClaimLLM.label` field description:
```python
    label: ClaimLabel = Field(
        ...,
        description="LLM's assessment of grounding strength based on visible evidence"
    )
```

- `ClaimFinal` has no separate field description for `label`; it inherits its meaning but explicitly states:
```python
class ClaimFinal(BaseModel):
    """Claim with pipeline-appended grounding fields.
    This is the shape written to paper_claims table.
    """
```

- The `ClaimLabel` enum explicitly refers to the extractor, not the final pipeline output:
```python
class ClaimLabel(str, Enum):
    """Claim grounding strength as judged by the LLM extractor."""
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NOT_SUPPORTED = "not_supported"
```

The schema treats `label` strictly as the **"extractor's judgment"** (the initial optimistic LLM output). The grounding outcome is modeled orthogonally via the `grounding_status` and `missing` fields added in the `ClaimFinal` layer, rather than by mutating the `label` itself.

## 2. Pipeline flow — how does label get set and does anything change it?

- **Does the grounding pipeline MODIFY claim.label based on span outcomes?**
  **No.** In `Prism.PythonService/extraction/grounding.py` (Stage 3 rollup), the `label` is passed through verbatim into the `ClaimFinal` object, regardless of whether grounding passes or fails.
  ```python
          if any_pass:
              # ...
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
          else:
              # ...
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

- **Does the writer see the pre-grounding or post-grounding value?**
  The writer sees the exact pre-grounding value for `label` preserved alongside the post-grounding fields. In `main.py`, the pipeline passes `extraction` into `ground_extraction`, which returns a list of `ClaimFinal` objects. These are passed to `write_extraction_result`. In `writer.py`:
  ```python
                          INSERT INTO paper_claims
                              (id, document_extractor_id, extraction_run_id, claim_text_verbatim,
                               claim_summary, label, grounding_status, missing, reason,
                               evidence_spans, position, created_at, updated_at)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                          """,
                          (
                              # ...
                              claim.label.value,
                              claim.grounding_status.value,
                              claim.missing,
  ```

- **If grounding writes back to the claim, is that update persisted before the writer runs?**
  Grounding does not write back to the claim's `label` property; it only wraps the claim into a `ClaimFinal` with `missing=True` and `grounding_status="Fail"`. This object is returned to `main.py` and then passed into the DB transaction in `writer.py`.

## 3. Actual DB state — what's really in there right now

**Query A — label distribution across all rows:**
```text
('partially_supported', True, 'Fail', 2)
('supported', True, 'Fail', 11)
```

**Query B — for every row where missing=true, show the label distribution:**
```text
('supported', 11)
('partially_supported', 2)
```

**Query C — one full row inspection for a claim where label='supported' AND missing=true:**
```text
('ReAct outperforms imitation and RL baselines by 34% and 10% on ALFWorld and WebShop.', 'supported', 'Fail', True, 'all evidence spans failed grounding: 0 spans failed RapidFuzz check; 4 spans failed LLM audit', 4, 'Fail', 'Fail', 'Fail')
('ReAct outperforms action-only models and competes with CoT on HotpotQA and Fever.', 'supported', 'Fail', True, 'all evidence spans failed grounding: 0 spans failed RapidFuzz check; 2 spans failed LLM audit', 2, 'Fail', 'Fail', None)
('Combining ReAct and CoT achieves the best overall performance by leveraging internal and external knowledge.', 'supported', 'Fail', True, 'all evidence spans failed grounding: 0 spans failed RapidFuzz check; 2 spans failed LLM audit', 2, 'Fail', 'Fail', None)
```

**Query D — sanity check: any rows where all spans passed but label is not_supported (the inverse case)?**
```text
(0 rows returned)
```

**Query E — sanity check: any rows where at least one span passed AND missing=false but label is still not_supported?**
```text
(0 rows returned)
```

## 4. Contradictions between design intent and actual behavior

- **Does the schema/decisions.md/PRODUCT_BRIEF documentation describe an intended behavior?**
  Yes. `PRODUCT_BRIEF.md` describes the mechanism as "extractor optimism overridden by grounder verdict" and emphasizes that correct-refusal relies on the grounding checker acting as a veto. `schemas.py` defines `label` explicitly as "Claim grounding strength as judged by the LLM extractor."

- **Does the actual pipeline match that intent?**
  Yes. The python pipeline preserves the LLM's raw label (optimism) and sets `missing=True` when the grounder vetoes it.

- **Does the actual DB state match what the pipeline produces?**
  Yes. Query C shows that even when every single evidence span fails audit (`reason: 'all evidence spans failed grounding...'`), the `label` column remains what the extractor originally emitted (`'supported'`).

- **Flagged discrepancy:** The only contradiction is in the *UI rendering*, not the backend data. The Matrix UI relies purely on the `label` pill to convey status, displaying SUPPORTED for rows where the grounder has set `missing=True`. It fails to apply the grounder's veto when drawing the UI.

## 5. Recommendation

**(b) The pipeline correctly writes extractor optimism — bug is in UI reading, fix frontend to render grounder verdict.**

**Defense:**
1. The backend pipeline is behaving exactly as designed. `schemas.py` documents `label` as the "LLM's assessment" and `grounding_status` as the "pipeline verdict". 
2. The `PRODUCT_BRIEF.md` explicitly calls this design the "correct-refusal thesis (extractor optimism overridden by grounder verdict)". By keeping the raw label and the grounder verdict separate, the system can measure how often the LLM hallucinates support vs how often the system successfully refuses (the core product eval).
3. If the pipeline downgraded the `label` to `NOT_SUPPORTED` upon grounding failure, we would lose the data about what the extractor *tried* to claim, destroying the ability to evaluate hallucination vs. omission rates. 
4. Therefore, the bug is purely in the frontend React code (the Matrix UI), which is incorrectly reading only the optimistic `label` pill instead of checking `missing === true` first to render a "No Evidence" state.

## 6. What decisions.md is missing

The intended semantic separation between `label` (LLM's initial guess) and `missing`/`grounding_status` (the final veto) is critical to the product's design, but it lacks a clear, standalone decision entry in `decisions.md` to prevent downstream developers (like the frontend engineer) from misinterpreting `label` as the final verdict.

**Draft Decision Entry:**

```markdown
## Label represents extractor optimism, not final verdict — 2026-08-22

**Context:** The Matrix UI was rendering "SUPPORTED" for claims that had entirely failed grounding because it was reading the `label` column directly, assuming it represented the system's final judgment.
**Decision:** `paper_claims.label` must strictly store the LLM extractor's initial judgment (often optimistic). It is never mutated or downgraded by the grounding pipeline. Grounding failures are recorded orthogonally via `missing=True` and `grounding_status='Fail'`.
**Alternatives:** (a) overwrite `label` to `not_supported` when grounding fails — rejected; destroys the record of the LLM's hallucination, making it impossible to evaluate the extractor's error rate vs the grounder's catch rate. (b) add an `insufficient_evidence` enum value — rejected; conflates the initial extraction schema with the pipeline's verification layer.
**Consequences:** The backend retains a perfect record of "extractor optimism overridden by grounder verdict." The UI layer is burdened with the logic to reconcile these fields (it must check `missing == true` before deciding what pill to render).
```
