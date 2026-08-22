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

The four sections run from pure extraction to pure inference. Hallucination risk rises with each tier; so must eval ruthlessness.

- **Tier 1 — Extraction (highly groundable). Build FIRST.**
  *Claim-Support Matrix.* Each stated claim → cited evidence span in the paper → supported / unsupported. Near-extraction; proves the correct-refusal bet cleanly; the most defensible thing to demo.

**Tier 2 — Paper-scoped chat (deferred, own eval).**
Everything the old Tier 2 Verdict and Tier 3 Overstated Claims surfaces would have shown is answered by the embedded chat strip on demand, grounded on paper_claims rows for the active paper. Chat surface has its own eval concern (does the agent faithfully cite the Matrix vs invent claims not in it) that lands with Slice 3, not as a Tier 1 blocker.

---

## Current State (ground truth: `docs/decisions.md`)

**Built, running locally under Aspire:** CRAG pipeline, grounding checker, intent + HyDE routing, event-driven ingestion with DLQ, SignalR live updates, PostgreSQL checkpointer, audio-to-text input, golden eval scaffold.

**Extraction engine: DONE.** Prompt 1 (paper-level metadata, 9 fields) + a three-call claim extraction pipeline (extractor → auditor → structurer, decoupling claim finding from label judging) + two-stage grounding pipeline (RapidFuzz + Flash Lite audit) + DB writer (`document_extractors` + `paper_claims` tables) + worker integration. Retry cap and Qdrant idempotency also complete.

**Not built (views + cloud):** the Brief itself (Verdict card, Overstated Claims, Claim-Support Matrix UI), tests, and the entire Azure stack.

**In progress this branch (feat/matrix-backend):**
- Slice 1 backend shipped: GET /api/papers/{paperId}/claims endpoint, GET /api/chats/{userId} paper-primary rebrand, POST /api/papers 1-file-per-chat guard, AddPositionToPaperClaims migration + writer.py enumerate() update, EF Core value converters for ClaimLabel + GroundingStatus, HasJsonPropertyName for EvidenceSpan owned entity.
- Slice 1 frontend NEXT: shadcn + Tailwind install, App.tsx split into AppShell/Sidebar/MatrixView/EvidenceDrawer, three-panel layout, absence-branch rendering.

The golden evals are committed against three agent papers (21 chat Qs, 37 matrix rows, 17 combined grounding-negative). **Next milestone:** iterating the extractor prompt to improve trap-claim coverage on Reflexion and CoT papers (by_omission reduction), or building the Claim-Support Matrix UI (Tier 1), whichever comes first per the build order.

---

## Build Order

The spine is **test-first extraction**: the eval comes *with* the engine, not after the views.

**0. Doc cleanup (parallel, anytime).** Keep README and diagrams accurate to the codebase. Remove any false or aspirational claims so the repo stays unimpeachable.

**1. Extend the golden set FIRST (test-first).** Before the engine, write grounding cases — positive *and* grounding-negative — for the **Claim-Support Matrix** (Tier 1). Define what "correct claim extraction" and "correct refusal" mean as concrete, scored assertions over real papers. This is the eval-asset seed and the engine's spec. (DONE — committed as `docs/evals/matrix_eval.json`)

**2. Build the extraction engine to PASS those cases.** Multi-call pipeline → structured JSON (metadata + claims with evidence spans), grounding-checked via two-stage RapidFuzz + LLM audit, written to `document_extractors` + `paper_claims`. (DONE — see `docs/decisions.md`)

**3. Render the Claim-Support Matrix (Tier 1).** DONE — this PR.

**4. Emit extraction progress events.** Slice 2 — Python worker emits typed status events at each pipeline stage (extraction started, metadata done, claims done, grounding done, complete). C# forwards via SignalR. Sidebar row shows a progress strip instead of a spinner.

**5. Paper-scoped chat.** Slice 3 — LangGraph agent output becomes a typed block array (text | claim_reference | ui_action). C# gateway switches /api/chat/ask to SSE. Frontend renders block list, clicking claim_reference scrolls Matrix + opens drawer. Agent retrieval queries both Postgres paper_claims AND Qdrant chunks, both filtered by active_file_id, refuses loudly on empty.

**6. Emit the eval number cleanly.** DONE (PR #22).

**7. Azure deploy — AFTER the engine + eval + Slice 3 are green locally.** Core services only. Do not interleave Azure with the spine.

**8. Ship the proof.** Live URL, recorded walkthrough, eval number on a slide, one blog post.

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
