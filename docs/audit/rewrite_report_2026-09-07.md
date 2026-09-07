# Documentation Rewrite Report

## 1. Files Modified (Line Counts)
- **`README.md`**: ~223 lines → 56 lines
- **`docs/PRODUCT_BRIEF.md`**: 195 lines → 33 lines
- **`docs/decisions.md`**: 657 lines → 657 lines (added glossary, replaced TBDs, updated deferred lists)

## 2. Assessment of `PRODUCT_BRIEF.md`
**Value Assessment:** Yes, it earns its place alongside the `README.md` and `decisions.md`.
**Reasoning:** While the `README.md` targets the "what" and "how" (eval metrics, tech stack, architecture), `PRODUCT_BRIEF.md` answers the critical "why". The sections on "The Wedge" (contrasting with Elicit/Consensus) and "What Makes It Trustworthy" (the correct-refusal thesis) provide essential context for why the system is built with a strictly acyclic, refusal-heavy pipeline. This demonstrates product judgment and restraint to a reviewer. 
**Action Taken:** Trimmed out all internal planning scaffolding (Build Order, Current State, UI Design Decisions, North-Star, Target Architecture, The One-Line Spine). Retained only the core product philosophy and the Groundability Tiers.

## 3. Factual Claims in Old Docs That Were Wrong or Unverifiable
- **Unverifiable Metrics:** `docs/decisions.md` had "TBD" placeholders for Refusal rate, False rejections, and Positive hits for the 2026-09-05 entries. These were unverifiable until matched against the live eval output. Replaced with the true ground metrics (11/14 refusal, 0/23 false rejections, 13/23 positive hits).
- **Terminology Drift (Wrong/Confusing):** `docs/decisions.md` frequently conflated the "auditor" (Call 3 claim labeler) with the "grounding checker" (Stage 2 span validator). Added a Glossary to clearly define Extractor, Claim Auditor, Structurer, and Grounding Checker with their respective prompts.
- **Stale Deferred Item:** The "Next PR should target the auditor prompt... for Pattern A/B reasoning" note was listed as pending but was already resolved in the "Auditor prompt v2" commit. Marked as resolved.
- **Missing Deferred Items:** The Deferred / Won't Do section was missing known pending items from the audit reports (retry loop fix, AppHost PublishAsDockerFile, positioning claims scope). These were added to the list.

## 4. Load-Bearing Cuts (Flagged for Review)
- **`README.md` Roadmap & Mermaid Diagram:** Completely excised to fit the 60-second reviewer constraint. If the diagram was heavily referenced by other internal onboarding docs, those links are now dead.
- **`PRODUCT_BRIEF.md` UI Design Decisions:** Cut the section detailing the label vocabulary (`supported`, `partially_supported`, `not_supported`) and the "Honesty over polish" UI principles (e.g., why there is no overall confidence score). While it was scaffolding, this might be load-bearing for a frontend engineer trying to understand the rationale behind the UI's constraints.
