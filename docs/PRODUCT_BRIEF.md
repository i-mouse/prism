# Prism — Product Brief

## The Product

One deliverable: a **Paper Intelligence Brief** generated shortly after a paper is uploaded. It helps a reader/reviewer decide **whether to trust the paper's headline claims** — before they cite it or build on it.

### Brief contents
- **Verdict** — Supported / Not-Supported / Partially-Supported, with 3 reasons — are the headline claims backed by the paper's own evidence?
- **Overstated Claims** — conclusions that exceed what the results actually show
- **Questions to Scrutinize** — what a careful reviewer should check before citing (sample size, baselines, ablations, confounds)
- **Claim-Support Matrix** — every stated claim as a cited supported / unsupported checklist

> All four sections are derivable from the **uploaded paper alone** — no external corpus required. (Cross-paper / literature comparison is deferred North-Star; it needs a corpus.)

> ⚠️ **The four sections are NOT equally groundable.** This drives the build order. See *Groundability Tiers*.

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

## Groundability Tiers (drives the build order)

The four sections run from pure extraction to pure inference. Hallucination risk rises with each tier; so must eval ruthlessness.

- **Tier 1 — Extraction (highly groundable). Build FIRST.**
  *Claim-Support Matrix.* Each stated claim → cited evidence span in the paper → supported / unsupported. Near-extraction; proves the correct-refusal bet cleanly; the most defensible thing to demo.

- **Tier 2 — Light inference (traceable).**
  *Verdict (Supported / Not-Supported / Partially-Supported + 3 reasons).* Must be derivable from Tier-1 matrix rows — every reason traces to a cited claim, not to model opinion. Build second.

- **Tier 3 — Inference-heavy (hallucination-prone). Build LAST; eval hardest.**
  *Overstated Claims* and *Questions to Scrutinize.* These require judgment about what "exceeds the evidence" means, with no single literal source span to ground against — exactly where an LLM invents. Grounding-negative cases here must be the most aggressive in the whole set. **If the deadline tightens, Tier 1 + Tier 2 alone is an honest, shippable product; Tier 3 follows.**

---

## Current State (ground truth: `docs/AI_HANDOFF.md`)

**Built, running locally under Aspire (architecture — carries over unchanged):** CRAG pipeline, grounding checker, intent + HyDE routing, event-driven ingestion with DLQ, SignalR live updates, PostgreSQL checkpointer, audio-to-text input, golden eval scaffold.

**Not built (domain content + views):** the Brief itself, Claim-Support Matrix, the paper-domain extraction schema + prompts, the paper-domain golden cases, automated eval reporting, tests, and the entire Azure stack. OSS-only today.

The golden eval (`docs/golden_eval.json`) currently provides a `regression_gate` scaffold and question-type taxonomy. Full content rebuild against research papers is the prerequisite for Phase 1's extraction engine work.

---

## Build Order

The spine is **test-first extraction**: the eval comes *with* the engine, not after the views.

**0. Doc cleanup (parallel, anytime).** Keep README and diagrams accurate to the codebase. Remove any false or aspirational claims so the repo stays unimpeachable.

**1. Extend the golden set FIRST (test-first).** Before the engine, write grounding cases — positive *and* grounding-negative — for the **Claim-Support Matrix** (Tier 1). Define what "correct claim extraction" and "correct refusal" mean as concrete, scored assertions over real papers. This is the eval-asset seed and the engine's spec.

**2. Build the extraction engine to PASS those cases.** One prompt → structured JSON (claims, methodology, results, limitations, evidence spans), grounding-checked. The JSON is the single source both views render from. Iterate against the golden set until Tier-1 is green.

**3. Render the Claim-Support Matrix (Tier 1).** First user-visible view, straight off the JSON. Most groundable → demo first.

**4. Render the Verdict (Tier 2).** Supported / Not-Supported / Partially-Supported + 3 reasons, each traceable to a cited matrix row. Extend golden cases to assert traceability.

**5. Add Overstated Claims + Questions to Scrutinize (Tier 3) with ruthless grounding-negative eval.** Only after Tiers 1–2 are solid. Defer if the deadline is close.

**6. Make the eval harness emit the number cleanly.** Automated run → `correct-refusal rate: X% / N cases`, reproducible from a committed command.

**7. Azure deploy — AFTER the engine + eval are green locally.** Only the core services: Azure OpenAI, AI Search, Document Intelligence, Container Apps + Managed Identity + Key Vault. Do **not** interleave Azure with the spine.

**8. Ship the proof.** Live URL, recorded walkthrough, eval number on a slide, one blog post: *"A RAG system that refuses to overstate research claims — and the eval that proves it."* Blog = distribution; number = proof; together = the reputation asset.

---

## Critical-Path Discipline (what must NOT leak in)

- **No "platform" / "OS" framing. One engine, one domain (papers), one document at a time.** Multi-domain breadth (exam papers, study material, game docs) is a *later* deployment detail, never the current framing. The clean engine already keeps that option open; naming it broadly only invites building five shallow things instead of one deep one.
- **MCP server wrapper — OFF the critical path.** The valuable substance (deterministic extraction) is already item 2. MCP is afternoon packaging, added later as a standalone demo if time allows.
- **North-Star architecture is FORBIDDEN until the core works locally.** Foundry Pattern C, Service Bus DLQ, full RBAC, Redis, multi-agent split — untouched until items 1–6 are green.
- **Azure is necessary (role + cert alignment) but is the scope-creep risk.** Core services only. After the spine, not during.

---

## North-Star (Explicitly Deferred — NOT committed scope)

Real ambitions, but corpus-dependent or low-priority for the job goal.

- **Cross-paper / literature consistency** — does this claim contradict or replicate prior work? Requires an indexed paper corpus (arXiv, Semantic Scholar, PubMed). Long-term moat, earned over months, not shipped in weeks. A background fetcher can accumulate corpus now; the *features* wait.
- **Citation-graph / venue credibility signals** — corpus- and metadata-dependent. Deferred.
- **Multi-agent split** (Methodology Analyst → Results Verifier → Claim Auditor → Verdict Synthesizer → Grounding Checker) — only justified once the corpus exists and sections need genuinely different retrieval. Model switching today is **not** multi-agent.
- **MCP server wrapper** — learning/resume item; standalone demo, off critical path.
- **Foundry agent hosting** — most cert-aligned (AI-103 2026 objectives include agentic solutions) but preview-adjacent. Spike a hello-world before trusting it; fallback is plain LangGraph in a Container App calling Azure OpenAI directly.
- **Redis caching, full RBAC** — defer until real traffic / a second tenant.

---

## Target Architecture (North-Star — deferred, for reference; unchanged from pre-pivot)

Frontend: React + TS + Vite
Application: C# .NET API Gateway + Python Worker (Container Apps)
AI orchestration: LangGraph, eventually Foundry-hosted (Pattern C)
Data: Azure PostgreSQL (relational + audit + checkpoints), Azure AI Search (vector + hybrid + corpus), Azure Blob (uploads)
Messaging: Azure Service Bus (async + DLQ)
External AI: Azure OpenAI, Document Intelligence, Content Safety
Identity: Entra ID + Managed Identity + Key Vault
Observability: Application Insights
Local dev: Aspire (mirrors production)

> **Domain note:** arXiv PDFs are text-clean and often have LaTeX/HTML source, so Document Intelligence is less load-bearing than for scanned documents — but keep it: results-**table** and figure-caption extraction is exactly where it earns its keep on papers, and it stays cert-relevant.

---

## The One-Line "Spine"

> Extend the golden set for the Claim-Support Matrix → build the extraction engine to pass it → render the Matrix → then Verdict → then (if time) Overstated Claims + Questions → emit the eval number → deploy core Azure services → ship the proof.

Everything not on that line waits.
