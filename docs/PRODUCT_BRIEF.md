# Prism — Product Brief

## The Product

One deliverable: a **Paper Intelligence Brief** generated shortly after a paper is uploaded. It helps a reader/reviewer decide **whether to trust the paper's headline claims** — before they cite it or build on it.

### Brief contents
- **Verdict** — Supported / Not-Supported / Partially-Supported, with 3 reasons — are the headline claims backed by the paper's own evidence?
- **Claim-Support Matrix** — every stated claim as a cited supported / unsupported checklist
- **Paper-scoped chat** — an embedded chat strip at the bottom of the Matrix view. Grounded on the paper's extracted claims and content. Answers rollup questions ('should I trust this paper?'), overstatement questions ('what's the paper claiming beyond its evidence?'), and scrutiny questions ('what should a careful reviewer probe?') on demand — not as pre-computed cards.

> All four sections are derivable from the **uploaded paper alone** — no external corpus required. (Cross-paper / literature comparison is deferred North-Star; it needs a corpus.)

---

## The Wedge

Tools like Elicit, Consensus, and Scite help you **find and summarize** papers.
Prism audits **whether a single paper's claims are supported by its own evidence** — the reviewer's job, not the searcher's. One step more rigorous than summarization.

---

## What Makes It Trustworthy (and what the hiring artifact actually is)

A claim-auditing tool that invents support is worse than no tool. The core engineering bet is **correct refusal**: the grounding checker vetoes any assessment not supported by the paper's own text, and the system says "the paper provides no evidence for this" instead of fabricating support.

This is measured by the golden evaluation set (`docs/golden_eval.json`), specifically the grounding-negative cases (claims the system must refuse to affirm). **The single most important output of this project is a clean number:**

> **correct-refusal rate: X% across N grounding-negative cases.**

That number — on a slide, in a blog post, reproducible from a committed eval harness — is the artifact that proves the engineering to an interviewer. The eval is the deliverable that makes the rest legible. First-class, not QA afterthought.

---

## Groundability Tiers

The tiers represent the transition from deterministic extraction to conversational reasoning:

- **Tier 1 — Claim-Support Matrix & Paper-scoped Chat.**
  - *Claim-Support Matrix (Extraction):* Stated claim → cited evidence span → verdict. Evaluates the core "correct refusal" capability.
  - *Paper-scoped Chat:* Inline conversational strip answering questions grounded on paper claims + vector chunks. Refuses loudly on out-of-scope prompts.

- **Tier 2 — Multi-paper Chat (North-Star).**
  Cross-paper retrieval and synthesis across multiple files, requiring an indexed corpus and literature search capabilities.

- **Tier 3 — Web-grounded Chat (North-Star).**
  Chat with web search engine tool routing to cross-reference paper claims against the broader scientific literature.
