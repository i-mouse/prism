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

## UI Design Decisions (Tier 1 Matrix)

The Tier 1 view is a single-paper audit rendered in a three-panel layout:
sidebar (workspace + recent papers), main (paper header + audit summary +
claim rows), evidence drawer (verbatim passage + surrounding context +
open paper link). Design references: Scite.ai two-column claim/evidence
table pattern, Linear-style status pills, Perplexity-style evidence cards.

**Label vocabulary — three states, matching the shipped schema:**
- `supported` (green check)
- `partially_supported` (amber tilde)
- `not_supported` (red X)

No fourth "insufficient_evidence" label. Rationale: keep UI in sync with
the shipped `ClaimLabel` enum in schemas.py; if we later distinguish
"no evidence" from "contradicting evidence", that's a schema decision
made from real audit data, not a design guess.

**Honesty over polish — every visible number is defensible:**
- No "N papers analyzed" claim. Prism audits one paper at a time by
  design; cross-paper synthesis is deferred North-Star (needs a corpus).
- No overall "confidence %" score. Prism doesn't compute one. Instead
  show real audit counts: "15 / 18 claims supported · 3 refused".
- No per-claim "High/Medium/Low" confidence badges. Prism computes
  grounding_status (Pass/Fail/Skipped) at the span level and a discrete
  label at the claim level. Nothing per-claim maps to a confidence
  gradient today.

**What ships in Tier 1 v1 (must-ship):**
- Three-panel layout
- Paper header (title, author, venue)
- Audit summary strip (Evidence Strength, Claims, Supported, Partially,
  Not Supported — real counts from paper_claims)
- Claim rows: label pill + claim_summary + verbatim quote + section
  reference + View Evidence
- Right-side evidence drawer: highlighted passage + Open Paper
- Sort by label

**Nice-to-have (v1.1, if time permits):**
- "Show only refused claims" filter chip
- Bookmark per claim (localStorage)
- Share / Export stubs

**Deferred to Tier 2 or later:**
- Follow-up chat box at bottom (chat integration is Tier 2)
- Cross-paper synthesis view (North-Star, needs corpus)
- Per-claim confidence badges (only if we compute real confidence)
- Dark mode toggle

**Component library:** shadcn/ui + Tailwind. Chosen for 2026 default
polish, copy-and-own component ownership, and speed. Rejected: MUI /
Chakra (aesthetic tax, reads as 2021), plain CSS (time-expensive,
inconsistent).

---

## Groundability Tiers (drives the build order)

The tiers represent the transition from deterministic extraction to conversational reasoning:

- **Tier 1 — Claim-Support Matrix & Paper-scoped Chat (V1 Scope).**
  - *Claim-Support Matrix (Extraction):* Stated claim → cited evidence span → verdict. Evaluates the core "correct refusal" capability.
  - *Paper-scoped Chat:* Inline conversational strip answering questions grounded on paper claims + vector chunks, replacing pre-computed verdict cards. Refuses loudly on out-of-scope prompts.

- **Tier 2 — Multi-paper Chat (Post-V1).**
  Cross-paper retrieval and synthesis across multiple files, requiring a reworked Matrix layout and literature search capabilities.

- **Tier 3 — Web-grounded Chat (Post-V1).**
  Chat with web search engine tool routing to cross-reference paper claims against the broader scientific literature.

---

## Current State (ground truth: `docs/decisions.md`)

**Built, running locally under Aspire:** 
- Ingestion pipeline with RabbitMQ job-atomic retries, MinIO upload store, Qdrant vector database, and PostgreSQL rel-db.
- Three-call claim extraction pipeline (extractor → auditor → structurer) and two-stage grounding (RapidFuzz + Gemini Flash Lite).
- Real-time stage-based ingestion events (preparing, extracting, auditing, finalizing, done) broadcasted over C# SignalR.
- React 19 Claim-Support Matrix three-panel UI with collapsible evidence drawer and smooth stage progress tracking.
- Paper-scoped LangGraph chat agent backend (SSE transport) with Postgres checkpoints.
- React Chat Strip with native streaming fetch, claim highlighting hook-ups, dynamic follow-ups, and UX polish.
- Grounding tuning & hybrid LLM architecture (Slice 2.8 shipped): reasoning-first schema pattern for span audit, context widening (500-1500 chars with paragraph snapping), 3-tier Pass/Fail/Partial rubric, and hybrid Gemini 3.6 Flash paid Tier 1 + Groq Developer/free primary audit with Gemini 3.1 Flash Lite paid Tier 1 fallback via LiteLLM.
- Azure pre-deploy foundation (PR 1 shipped): env-driven config (`BaseSettings` / `IOptions`), health endpoints, admin-guarded reset, multi-stage Dockerfiles for all 4 services, single-replica Container Apps topology, and CI env alignment.

**Pending V1 Milestones:**
- PR 2: Concurrency & Observability (OpenTelemetry distributed tracing, cancellation token propagation).
- PR 3: Cleanup & Integration Tests (Slice 3c legacy chat deletion, test coverage).
- Azure Deployment: Provisioning Container Apps, Postgres Flexible Server, AI Search, Key Vault via `azd`.
- V1 Ship: Live demo deployment, walkthrough video, and publication.

---

## Build Order

**1. Extend the golden set (test-first).** Define matrix cases and grounding-negative assertions. (DONE — `docs/evals/matrix_eval.json`)
**2. Build extraction engine to PASS cases.** Multi-call pipeline with structured JSON + RapidFuzz + LLM audit. (DONE)
**3. Render the Claim-Support Matrix (Tier 1).** Layout panels, status pills, and detail drawer. (DONE)
**4. Ingestion progress events (Slice 2 + 2.5).** Granular progress updates and sub-progression logs via SignalR. (DONE)
**5. Paper-scoped chat (Slice 3a + 3b + 3b.1 + 3b.2).** Chat agent with Postgres checkpoints, fetch streaming, citations, dynamic follow-ups, and density cleanup. (DONE)
**6. Eval harness verification.** Running evaluations locally and locking CI on regression. (DONE — PR #22)
**7. Grounding Tuning (Slice 2.8).** Iterating grounding prompt + validation window to reduce false rejections. (DONE — PR #32)
**8. Azure pre-deploy foundation (PR 1).** Typed config, multi-stage Dockerfiles, health probes, single-replica topology. (DONE — PR #33)
**9. Concurrency & Observability (PR 2).** OpenTelemetry tracing, cancellation handling, worker task pool safety. (PENDING V1)
**10. Code cleanup & tests (PR 3 / Slice 3c).** Drop legacy chat python services and add integration test suite. (PENDING V1)
**11. Azure deployment.** Set up cloud infrastructure mirroring local Aspire resources via `azd`. (PENDING V1)
**12. Ship the V1 proof.** Live URL, blog post, recorded walkthrough. (PENDING V1)

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
