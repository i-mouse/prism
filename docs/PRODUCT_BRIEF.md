# TenderAI — Product Brief

## The Product

One deliverable: a **Bid Intelligence Brief** generated shortly after a tender is uploaded. It helps a procurement team decide **whether to bid at all** — before they sink days into proposal prep.

### Brief contents
- **Verdict** — Bid / No-Bid / Bid-If, with 3 reasons
- **Hidden Requirements** — deal-breaker clauses that are soft-stated but enforced
- **Five Questions** — what to clarify before committing to bid preparation
- **Compliance Matrix** — every requirement as a cited pass/fail checklist

> All four sections are derivable from the **uploaded tender alone** — no external corpus required. This is the buildable, shippable scope.

> ⚠️ **But the four sections are NOT equally groundable.** This is the central engineering reality of v2 and it drives the build order below. See *Groundability Tiers*.

---

## The Wedge

Competitors (RFPIO, Loopio, Responsive) help teams **respond** to tenders.
TenderAI helps them decide **whether to respond at all** — one step upstream of the entire RFP-tooling market.

---

## What Makes It Trustworthy (and what the hiring artifact actually is)

A bid-decision tool that invents a number is worse than no tool. TenderAI's core engineering bet is **correct refusal**: the grounding checker vetoes any claim not supported by retrieved source text, and the system says "not specified in this document" instead of fabricating.

This is measured by the golden evaluation set (`golden_eval.json`), specifically the grounding-negative cases. **The single most important output of this project is a clean number:**

> **correct-refusal rate: X% across N grounding-negative cases.**

That number — on a slide, in a blog post, reproducible from a committed eval harness — is the artifact that proves the engineering to an interviewer. The eval is not a QA afterthought; it is the deliverable that makes the rest legible. Treat it as first-class.

---

## Groundability Tiers (NEW — drives everything below)

The four Brief sections sit on a spectrum from pure extraction to pure inference. Hallucination risk rises with each tier, and so must eval ruthlessness.

- **Tier 1 — Extraction (highly groundable). Build FIRST.**
  *Compliance Matrix.* Each row is requirement → cited pass/fail with a literal source span. This is near-extraction; it proves the correct-refusal bet cleanly and is the most defensible thing to demo.

- **Tier 2 — Light inference (traceable).**
  *Verdict (Bid / No-Bid / Bid-If + 3 reasons).* Should be derivable from Tier-1 matrix rows — every reason must trace to a cited requirement, not to model opinion. Build second.

- **Tier 3 — Inference-heavy (hallucination-prone). Build LAST; eval hardest.**
  *Hidden Requirements* ("soft-stated but enforced") and *Five Questions*. These require judgment with no single literal source span to ground against — exactly where an LLM invents. The grounding-negative cases here must be the most aggressive in the whole golden set. **If the job deadline gets tight, Tier 1 + Tier 2 alone is an honest, shippable product; Tier 3 follows.**

---

## Current State (ground truth: `AI_HANDOFF.md`)

**Built, running locally under Aspire:** CRAG pipeline, grounding checker, intent + HyDE routing, event-driven ingestion with DLQ, SignalR live updates, PostgreSQL checkpointer, audio-to-text input, 20-case golden eval.

**Not built:** the Brief itself, Compliance Matrix, extraction engine, extended/automated eval harness, tests, and the entire Azure stack. OSS-only today.

---

## Buildable Scope (job-portfolio focus, in BUILD ORDER)

The spine is **test-first extraction**: the eval comes *with* the engine, not after the views. Each item is a concrete interview talking point for an Azure AI Engineer role.

**0. Doc cleanup (parallel, anytime).** Remove false/aspirational claims from README + diagram so the repo is unimpeachable. Do this in spare context-switches; it doesn't block the spine.

**1. Extend the golden set FIRST (test-first).** Before building the engine, write the grounding cases — positive *and* grounding-negative — for the **Compliance Matrix** (Tier 1). Define what "correct extraction" and "correct refusal" mean as concrete, scored assertions. This is the eval-asset seed and it specifies the engine's target.

**2. Build the extraction engine to PASS those cases.** One prompt → structured JSON (requirements, deadlines, amounts, eligibility, clauses), grounding-checked. The JSON is the single source both views render from. Iterate the engine against the golden set until Tier-1 is green.

**3. Render the Compliance Matrix (Tier 1).** First user-visible view, straight off the JSON. Most groundable → demo this first.

**4. Render the Verdict (Tier 2).** Bid / No-Bid / Bid-If + 3 reasons, each reason traceable to a cited matrix row. Extend golden cases to assert traceability.

**5. Add Hidden Requirements + Five Questions (Tier 3) with ruthless grounding-negative eval.** Only after Tiers 1–2 are solid. Defer if the job deadline is close.

**6. Make the eval harness emit the number cleanly.** Automated run → `correct-refusal rate: X% / N cases`, reproducible from a committed command. This is the hiring artifact's evidence.

**7. Azure deploy — AFTER the engine + eval are green locally.** Only the 4 core services: Azure OpenAI, AI Search, Document Intelligence, Container Apps + Managed Identity + Key Vault. Swap RabbitMQ → Service Bus during deploy. Do **not** interleave Azure with the spine — a deployment rabbit-hole must never block the part that proves your engineering.

**8. Ship the proof.** Live URL, recorded walkthrough, the eval number on a slide, and one blog post: *"A RAG system that refuses to hallucinate — and the eval that proves it."* The blog post is distribution; the number is proof; together they are the reputation asset.

---

## Critical-Path Discipline (what must NOT leak in)

- **MCP server wrapper — OFF the critical path.** The valuable substance ("deterministic extraction, not LLM-guessing") is already item 2. MCP is just transport — an afternoon's packaging bolted on *after* the engine exists, as a standalone demo / resume bullet if time allows. Building it first is wrapping an empty box.
- **North-Star architecture is FORBIDDEN until the core works locally** (see below). Foundry Pattern C, Service Bus DLQ, full RBAC, Redis, multi-agent split — none of these are touched until items 1–6 are green.
- **Azure is necessary (role + AI-102 alignment) but is the scope-creep risk.** Hold to the 4 core services. After the spine, not during.

---

## North-Star (Explicitly Deferred — NOT committed scope)

Real ambitions, but corpus-dependent or low-priority for the job goal. Documented so they don't leak into near-term planning.

- **Real Buyer / Real Competition / Win Confidence (N visible)** — requires an indexed Indian procurement corpus (CPPP, GeM, state portals). Long-term moat, earned over months of scraping, not shipped in weeks. Scraper can run as a background task now so data accumulates; the *features* wait.
- **Multi-agent split** (Document Analyst → Buyer Profiler → Competitive Analyst → Verdict Synthesizer → Grounding Checker) — only justified once the corpus exists and sections need genuinely different retrieval. Model switching today is **not** multi-agent.
- **MCP server wrapper** — learning/resume item; standalone demo, off critical path (see discipline note above).
- **Foundry Pattern C agent hosting** — most exam-aligned but least documented and preview-adjacent. Spike a hello-world deploy before trusting it; fallback is plain LangGraph in a Container App calling Azure OpenAI directly.
- **Redis caching, full RBAC** — defer until there's real traffic / a second tenant.

---

## Target Architecture (North-Star — deferred, for reference only)

Frontend: React + TS + Vite
Application: C# .NET API Gateway + Python Worker (Container Apps)
AI orchestration: LangGraph, eventually Foundry-hosted (Pattern C)
Data: Azure PostgreSQL (relational + audit + checkpoints), Azure AI Search (vector + hybrid + corpus), Azure Blob (uploads)
Messaging: Azure Service Bus (async + DLQ)
External AI: Azure OpenAI, Document Intelligence, Content Safety
Identity: Entra ID + Managed Identity + Key Vault
Observability: Application Insights
Local dev: Aspire (mirrors production)

---

## The One-Line "Spine"

> Extend the golden set for the Compliance Matrix → build the extraction engine to pass it → render the Matrix → then Verdict → then (if time) the inference-heavy sections → emit the eval number → deploy 4 Azure services → ship the proof.

Everything not on that line waits.
