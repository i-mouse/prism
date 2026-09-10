# H1+H2 Positive Hits Diagnosis (2026-09-10)

## 1. Golden Rows Flipped
The `positive_hits` metric dropped from 13/23 to 10/23. The following three claims (expected to be `supported`) were hits previously but failed in the new run:
- **REFLEX-M06** (Reflexion)
- **COT-M02** (Chain-of-Thought)
- **REACT-M10** (ReAct)

## 2. & 3. Claim-by-Claim Analysis

| Claim ID | Paper | Old Status | New Status | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **COT-M02** | CoT | `supported` | `partially_supported` | correctly-now-strict |
| **REFLEX-M06** | Reflexion | `supported` | Not Extracted | real regression |
| **REACT-M10** | ReAct | `supported` | Not Extracted | real regression |

### COT-M02 (Chain-of-Thought)
- **Claim:** Chain-of-thought prompting only yields performance gains when used with models of ~100B parameters.
- **Old reasoning:** Scored as a clean `supported` hit.
- **New reasoning:** The auditor correctly noticed an internal contradiction in the paper. While the text claims CoT *only* helps at ~100B+ scale, the auditor found that "Table 4 shows PaLM 8B improving from 55.1% to 75.2% on Sports Understanding... and UL2 20B improving from 34.2% to 51.4% on CSQA." Therefore, the auditor downgraded it to `partially_supported`. 
- **Judgment:** The new standard is **correct**. The old `supported` credit was too generous.

### REFLEX-M06 (Reflexion) & REACT-M10 (ReAct)
- **New reasoning:** N/A (Not Extracted).
- **Judgment:** This is **collateral damage / a real regression** from the extractor, not the auditor. The extraction fix (#57 "catch positioning claims previously omitted") caused the LLM to completely drop these two perfectly valid, verifiable empirical claims during the extraction phase.

## 4. The `by_grounding_reject` Increase
The `by_grounding_reject` metric went from 0 to 1. 
- **Claim:** **REFLEX-M11** (Reflexion: "Reflexion has several advantages compared to more traditional RL approaches like policy or value-based learning...")
- **Why it flipped:** In the previous run, the extractor completely omitted this claim. Because it wasn't extracted, the auditor never saw it. The recent extraction fix (#57) successfully forced the extractor to emit it. The auditor then analyzed it and correctly rejected it as `not_supported`.
- **Reasoning:** The auditor noted this is a "comparative-class claim" and explicitly pointed out that "No traditional policy-based or value-based reinforcement learning algorithms (such as PPO, A2C, or Q-learning) are implemented, fine-tuned, or benchmarked anywhere in the experiments."
- **Judgment:** **Correct**. This is exactly how the pipeline is supposed to work and not a side effect. 

## 5. Verdict & Recommendation
The drop to 10/23 is a mix of correctly applied strictness and an extraction regression.

**Recommendation:**
- **Accept the auditor changes:** The auditor is performing exceptionally well, catching internal contradictions (COT-M02) and unsupported comparative claims (REFLEX-M11). Accept these changes as honest and correct.
- **Touch the extraction prompt further:** The extraction fix (#57) was a double-edged sword. It successfully caught `REFLEX-M11`, but accidentally dropped `REFLEX-M06` and `REACT-M10`. We need to tune the extraction prompt to recover these empirical claims without losing the positioning claims again.
