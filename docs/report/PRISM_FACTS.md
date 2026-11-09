# PRISM Project Sourced Fact Sheet

*Generated from docs/decisions.md, docs/PRISM_STATUS.md, README.md, plus current-state code facts from Prism.PythonService/main.py, Prism.PythonService/config.py, Prism.PythonService/extraction/engine.py, Prism.PythonService/extraction/grounding.py, and Prism.PythonService/RAGService.py, cited as [C: path:line].*  
*Rules applied: No terminal commands, subagents, or git used; facts taken solely from the authorized documentation files and five authorized code files; decisions.md takes precedence on conflict, followed by PRISM_STATUS.md, then README.md.*  
*Meaning of UNSOURCED: Any item required by the reporting specification that is not stated in the authorized source files is marked UNSOURCED and logged in Section 12.*  
*Note on characters: Broken character sequences such as "â€”" in source headings are normalized to "—" in citations.*

---

## 1. What Prism is

- Prism extracts empirical claims from a research paper and audits whether each claim is supported by evidence in that same paper [R: # Prism].
- Unlike literature-discovery tools (Elicit, Consensus, Scite) that find and summarize across papers, Prism checks a single paper's headline findings against its own data and text [R: # Prism] [D: "One paper per chat, enforced at upload endpoint" - 2026-08-22].
- The engineering bet is correct refusal: vetoing any assessment the paper's own text does not support [R: # Prism].
- What Prism outputs for a paper:
  - **Claim-Support Matrix:** A structured grid of empirical and positioning claims extracted from the paper, paired with their verbatim evidence quotes, source sections, and auditor verdicts (`supported`, `partially_supported`, `not_supported`) displayed alongside grounding verification via `effective_status` [R: ## How it works] [D: "Tier 2 (Verdict view) and Tier 3 (Overstated Claims + Questions to Scrutinize) collapsed into paper-scoped chat" - 2026-08-22] [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20].
  - **Overall verdict, overstated claims, and questions to scrutinize:** Replaced pre-computed static cards by collapsing Tier 2 (Verdict view) and Tier 3 (Overstated Claims + Questions to Scrutinize) into interactive paper-scoped chat embedded in the Matrix view, answered on-demand and grounded on `paper_claims` and Qdrant chunks for the active paper [D: "Tier 2 (Verdict view) and Tier 3 (Overstated Claims + Questions to Scrutinize) collapsed into paper-scoped chat" - 2026-08-22] [D: "Slice 3a: paper-scoped LangGraph chat agent, SSE transport, block output" - 2026-08-25].
- Shipped product features recorded in `docs/decisions.md`:
  - **Paper-scoped chat agent:** LangGraph agent (`paper_chat/agent.py`) scoped to a single paper via `active_file_id`, querying `paper_claims` and Qdrant chunks, with fallback from FTS to claim position and loud refusal on empty retrieval [D: "Slice 3a: paper-scoped LangGraph chat agent, SSE transport, block output" - 2026-08-25] [D: "Slice 3a Bug Fixes: FTS fallback, check_empty OR logic, router tool bypass" - 2026-08-25].
    - Status today: Works in the local Aspire setup (`POST /api/chat/ask/stream` with LangGraph agent querying `paper_claims` and Qdrant chunks) [R: ## How it works, ## Tech stack] [D: "Slice 3c: legacy chat deletion" - 2026-08-30] [S: ## Current state].
  - **Streaming transport:** Server-Sent Events (SSE) token-by-token streaming transport over `POST /api/chat/ask/stream` with explicit `FlushAsync` chunk copying through ASP.NET Core [D: "Slice 3a: paper-scoped LangGraph chat agent, SSE transport, block output" - 2026-08-25].
    - Status today: Works in the local Aspire setup (SSE token-by-token streaming transport over `POST /api/chat/ask/stream` with explicit `FlushAsync`) [R: ## How it works] [D: "Slice 3a: paper-scoped LangGraph chat agent, SSE transport, block output" - 2026-08-25] [D: "Slice 3c: legacy chat deletion" - 2026-08-30].
  - **Chat UI in the matrix view:** Embedded chat strip (`PaperChatStrip.tsx`) in the Matrix workspace featuring streaming prose, clickable inline claim citations that highlight matrix rows and open the evidence drawer, and dynamic follow-up suggestions [D: "Slice 3b: Chat Strip UI in Matrix View" - 2026-08-26] [D: "Slice 3b.1 + 3b.2: Chat Polish & Density Cleanup" - 2026-08-26].
    - Status today: Works in the local Aspire setup (`PaperChatStrip.tsx` in Matrix workspace at `http://localhost:7000`) [R: ## Quick Start (Local Dev), ## Tech stack] [D: "Slice 3b: Chat Strip UI in Matrix View" - 2026-08-26] [S: ## Current state].
  - **Sign-in:** Customer-facing authentication via Microsoft Entra External ID (CIAM) supporting Google identity provider integration, resolving canonical identity through tenant-wide `oid` claims [D: "Entra External ID (CIAM)" - 2026-09-15/16] [D: "oid vs sub decision" - 2026-09-15/16] [D: "Google IdP Name/Email Claims Resolution" - 2026-09-27].
    - Status today: UNSOURCED (Entra External ID and Google IdP were deployed to Azure; no source states whether customer-facing Entra sign-in works in the local Aspire setup; demo strategy offline notes running guests-only so no real sign-in setup is required) [D: "Live environment decommissioned" - 2026-09-28] [D: "Demo strategy while offline" - 2026-09-28].
  - **One paper per chat:** Enforced at the API upload boundary (`POST /api/papers` rejects `Files.Count != 1`), establishing a 1:1 paper-to-chat model for unambiguous sidebar navigation [D: "One paper per chat, enforced at upload endpoint" - 2026-08-22].
    - Status today: Works in the local Aspire setup (enforced at upload endpoint `POST /api/papers` rejecting `Files.Count != 1`) [R: # Prism, ## Quick Start (Local Dev)] [D: "One paper per chat, enforced at upload endpoint" - 2026-08-22].
  - **Ingestion progress events:** 5-stage progress event pipeline (`preparing` → `extracting` → `grounding` → `finalizing` → `done`/`failed`) emitted over RabbitMQ, broadcast to clients via SignalR groups, and rendered in `PaperActivityView` [D: "Slice 2 + 2.5: Ingestion Progress Events & PaperActivityView UI" - 2026-08-23].
    - Status today: Works in the local Aspire setup (5-stage progress emitted over RabbitMQ, broadcast via SignalR groups, rendered in `PaperActivityView`) [R: ## Tech stack] [D: "Slice 2 + 2.5: Ingestion Progress Events & PaperActivityView UI" - 2026-08-23].
- Known product gaps recorded in `docs/decisions.md`:
  - **Google IdP name/email claims empty:** Google IdP name/email claims come back empty from Entra External ID even after scope/mapping fixes (CIAM rough edge); resolved at infrastructure level on 2026-09-27 for new sign-ups/re-registrations (legacy accounts still require re-registration) [D: "Known gap: Google IdP name/email claims empty" - 2026-09-15/16] [D: "Google IdP Name/Email Claims Resolution" - 2026-09-27].
  - **Extraction auto-retry failure state:** When paper extraction exhausts all 3 retries, API reported it as extractionStatus "Completed" with an empty claim list because status was inferred from Summary text; resolved on 2026-09-17 by replacing inferred status with explicit `ExtractionStatus` enum (`Pending`, `InProgress`, `Completed`, `Failed`) [D: "Known gap: extraction auto-retry failure state" - 2026-09-15/16] [D: "ExtractionStatus Cache-Hit Fix" - 2026-09-17].
  - **Router non-determinism:** The same free-text phrasing sometimes routes to different `claim_lookup` modes across identical repeated calls; OPEN/unresolved [D: "Known gap: Router non-determinism" - 2026-09-20].
  - **generate_response hallucination on claim status:** `generate_response` answered incorrectly about claim support status even when correct claim data was in context, falsely stating entry was not provided; OPEN/unresolved [D: "Known gap: generate_response hallucination on claim status" - 2026-09-20].
  - **Bug 4 (tab-switch/streaming state loss):** Live UI testing shows response can appear blank after switching browser tabs mid-stream and returning; leading hypothesis is Chromium suspending IntersectionObserver; OPEN/unresolved [D: "Known gap: Bug 4 (tab-switch/streaming state loss)" - 2026-09-20].
  - **Missing Claims Data (Local Dev Hazard):** Previously-extracted papers' claims data went missing from local dev database; fresh occurrence of documented Postgres volume password drift hazard [D: "Missing Claims Data (Local Dev Hazard)" - 2026-09-20] [D: "Postgres Container Password Drift Workaround" - 2026-08-23].
  - **Streaming top-anchor effect doesn't reliably fire:** `scrollToAnchor()` in `PaperChatStrip.tsx` leaves `scrollRoot.scrollTop` frozen at pre-send value; OPEN/unresolved [D: "Known gap: streaming top-anchor effect doesn't reliably fire" - 2026-09-21].
- What Prism is not: it is not a literature-discovery tool across papers [R: # Prism], not a multi-paper chat tool (it enforces one paper per chat) [D: "One paper per chat, enforced at upload endpoint" - 2026-08-22], and not an arbitrary claim-generation engine without source grounding [R: ## How it works].

---

## 2. Runtime and infrastructure

- Current operational status: Runs locally only (.NET Aspire); live hosted Azure demo was decommissioned 2026-09-28; there is no live URL [R: ## Status — 2026-10-21] [D: "Live environment decommissioned" - 2026-09-28] [S: ## Current state].
- Subscription cancellation initiated 2026-09-28, confirmation of completion has not been confirmed [R: ## Status — 2026-10-21] [D: "Live environment decommissioned" - 2026-09-28] [S: ## Current state].
- Azure design history: Built and deployed 2026-09-01 (PR 5) across 7 Container Apps (pythonWorker, pythonAPI, apiservice, reactUI, and internal containers) with managed Azure Postgres Flexible Server, Azure Blob Storage, Azure Key Vault, Managed Identity, and Application Insights [R: ## Tech stack] [D: "First Azure deploy" - 2026-09-01] [D: "Live environment decommissioned" - 2026-09-28].
- Decommission reason: Decommissioned 2026-09-28 because 7 always-on Container Apps (min replicas >= 1, 0.5 to 4 CPU) ran uncapped spend without scaling down between demos (pythonWorker ~40%, pythonAPI ~25%, 5 smaller containers ~30% including an unused Redis) [D: "Live environment decommissioned" - 2026-09-28].
- Re-launch requirements recorded: Reactivated Azure subscription, re-creating Entra External ID / Google identity provider / app registrations, and full redeploy via `aspire deploy` and `Prism.Web/deploy.ps1` [D: "Live environment decommissioned" - 2026-09-28].

### Component Architecture Table

| Component | Current | Tried / rejected (date, reason) | Source |
|---|---|---|---|
| UI (Frontend) | React 19.2, TypeScript 5.9, Vite 7.3, Tailwind CSS 4.3; runs locally at `http://localhost:7000` | Hosted Azure Container App deployed 2026-09-01, decommissioned 2026-09-28 to stop uncapped spend. AddNpmApp publish deadlock required manual Docker build. | [R: ## Tech stack] [D: "First Azure deploy" - 2026-09-01] [D: "Live environment decommissioned" - 2026-09-28] |
| API Gateway | ASP.NET Core (.NET 10), EF Core; .NET Aspire 13.4.6 orchestration | Azure Container App deployed 2026-09-01, decommissioned 2026-09-28. | [R: ## Tech stack] [D: "First Azure deploy" - 2026-09-01] [D: "Live environment decommissioned" - 2026-09-28] |
| Worker | Python (`>=3.13`), FastAPI, LangGraph 1.0.9 | Azure Container App (2.0 CPU / 4Gi) deployed 2026-09-01, decommissioned 2026-09-28. Undersized 0.5 CPU/1Gi OOM crash-looped 2026-09-01. Wrong entrypoint ran api.py instead of main.py. | [R: ## Tech stack] [D: "First Azure deploy" - 2026-09-01] [D: "PR 5 code port verification + reactUI JS app migration" - 2026-09-02] [D: "Live environment decommissioned" - 2026-09-28] |
| DB | PostgreSQL (local container via Aspire) with `GENERATED ALWAYS AS (...) STORED` column for `effective_status` | Azure Postgres Flexible Server (Entra Managed Identity auth) deployed 2026-09-01, decommissioned 2026-09-28. | [R: ## Tech stack] [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20] [D: "First Azure deploy" - 2026-09-01] [D: "Live environment decommissioned" - 2026-09-28] |
| Vector store | Qdrant (local container), fastembed | Azure AI Search rejected 2026-09-01 (Basic tier ~$250/month idle; Free tier caps at 50MB/3 indexes). Self-hosted Qdrant container in ACA deployed 2026-09-01, decommissioned 2026-09-28. | [R: ## Tech stack] [D: "Managed vs self-hosted service split" - 2026-09-01] [D: "Live environment decommissioned" - 2026-09-28] |
| Queue | RabbitMQ (local container) with `main_prism_queue`, `dlx_prism_exchange`, `dlq_prism_queue` (TTL 60s), `prefetch_count=1` | Azure Service Bus swap attempted 2026-08-31 / 2026-09-01 in PR 4; surfaced 4 bugs in emulator + Python SDK (microsoft/aspire#14041), reverted. ACA Azure Files volume mount failed Erlang cookie permissions (0600), fixed by running without data volume. | [R: ## Tech stack] [D: "RabbitMQ topology: main_prism_queue + DLX + DLQ" - 2026-08-02] [D: "First Azure deploy" - 2026-09-01] [D: "Managed vs self-hosted service split" - 2026-09-01] [D: "Correction: AUDIT_CONCURRENCY is 1, not 10" - 2026-09-29] |
| Cache / Other | Azurite (local blob emulation) | Redis provisioned in AppHost.cs:30 but caching logic never implemented. Decommissioned with Azure stack. | [R: ## Tech stack] [D: "Live environment decommissioned" - 2026-09-28] [D: "Known Limitations"] |

---

## 3. Models

### Model Roles and Configurations

| Role | Model id | Provider / API path | Since | Source |
|---|---|---|---|---|
| Extraction | gemini-3.6-flash | Google Gemini API (paid Tier 1) | 2026-08-27 | [D: "Hybrid Gemini paid Tier 1 + Groq audit" - 2026-08-27] [R: ## Tech stack] |
| Audit | gemini-3.6-flash | Google Gemini API (swapped from gemini-3.1-flash-lite) | 2026-09-04 | [D: "Auditor model swap + eval matcher calibration" - 2026-09-04] [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09] |
| Structurer | gemini-3.6-flash | Google Gemini API | 2026-08-20 | [D: "Three-call claim extraction pipeline" - 2026-08-20] [D: "Auditor model swap + eval matcher calibration" - 2026-09-04] |
| Grounding primary | groq/openai/gpt-oss-20b | Groq API via LiteLLM (concurrency 1, free tier 30 RPM, 8K TPM ceiling) | 2026-08-27 | [D: "LiteLLM provider abstraction for span audit call" - 2026-08-27] [D: "Correction: AUDIT_CONCURRENCY is 1, not 10" - 2026-09-29] |
| Grounding fallback | gemini-3.1-flash-lite (provider route gemini/gemini-3.1-flash-lite; no default defined in [C: Prism.PythonService/config.py:65]; in eval, grounding primary and fallback were both gemini-3.1-flash-lite via $env:LLM_GROUNDING_MODEL) | Google Gemini API via LiteLLM fallback chain | 2026-11-06 | [C: Prism.PythonService/config.py:65] [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] |
| Audit fallback | gemini-3.1-flash-lite | Google Gemini API | 2026-08-27 | [D: "Hybrid Gemini paid Tier 1 + Groq audit" - 2026-08-27] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] |
| Eval backend | Google AI Studio (product/dev); Vertex AI (eval experiments, project gen-lang-client-0520352487, global) | Google Cloud Vertex AI (billed to GCP Free Credit) | 2026-11-02 | [D: "Funding source and model plan for the next auditor tests" - 2026-11-02] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] |

### Tested Models Not Adopted

- **gemini-3.1-flash-lite (as primary auditor):** Replaced on 2026-09-04 because it underperformed on trap claims, scoring 9/14 refusal (FAIL) vs 11/14 for 3.6-flash [D: "Auditor model swap + eval matcher calibration" - 2026-09-04].
- **gemini-2.5-flash-lite (as matcher default):** Retired by Google; calls 404'd; fixed on 2026-09-04 [D: "Auditor model swap + eval matcher calibration" - 2026-09-04].
- **groq/llama-3.1-8b-instant:** Deprecated by Groq 2026-06-17, shut down 2026-08-16; replaced by `groq/openai/gpt-oss-20b` before deployment [D: "LiteLLM provider abstraction for span audit call" - 2026-08-27].
- **Local Ollama:** Tested/evaluated conceptually on 2026-08-27; rejected due to hardware variability and eval confounding [D: "Hybrid Gemini paid Tier 1 + Groq audit" - 2026-08-27] [D: "LiteLLM provider abstraction for span audit call" - 2026-08-27].
- **NLI model fine-tuning:** Evaluated 2026-09-04; rejected because 17 labeled rows were insufficient and NLI pair-classification cannot detect absence [D: "Auditor model swap + eval matcher calibration" - 2026-09-04].
- **gemini-3.8-flash (medium thinking):** Tested in Vertex AI auditor screen (attempt 2 voided 2026-11-07) and Full 3-run no-regression check 2026-11-08/09; REJECTED on M3 (4 false rejections /88 vs baseline 1) [D: "Screen attempt 2: void (V3 -> V4), robustness note, decision to take gemini-3.8-flash high to the full check" - 2026-11-07] [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- **gemini-3.8-flash (high thinking):** Tested in Vertex AI auditor screen (attempt 2 voided 2026-11-07) and Full 3-run no-regression check 2026-11-08/09; REJECTED on M3 (7 false rejections /88), M4 (positives 10/21 < floor 11), and M7 (cost INR 194.4/paper vs 130 cap) [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- **gemini-4-argon:** Ruled out for current evaluation 2026-11-02 due to cost (~2.7x to 5x Flash) and lack of explicit caching support [D: "Stage A0 results" - 2026-10-26] [D: "Funding source and model plan for the next auditor tests" - 2026-11-02].

---

## 4. Pipeline stages

### 4.1 Parse
- **Current:** PyMuPDF (`fitz` v1.26.7) via `page.get_text()` appended per page in `main.py:114` [D: "Held-out eval paper sealed (eval chain step 1)" - 2026-10-03] [D: "Eval chain first; prompt leakage found; gate-port dropped" - 2026-10-03] [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22].
- **Tried and failed or rejected:**
  - Layout-aware PDF parsing via Document Intelligence: rejected 2026-09-04 because raw PyMuPDF text preserved table citations (e.g. "Supervised SoTAb 67.5 89.5") [D: "Auditor model swap + eval matcher calibration" - 2026-09-04].
  - PyMuPDF `find_tables()`: evaluated 2026-10-02; left 2 of 4 tables undetected and merged rows; raw `get_text()` was cleaner [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02].
  - PyMuPDF `TEXT_DEHYPHENATE`: evaluated 2026-10-05; rejected because it alters text globally across extraction, chunking, and embedding simultaneously without fixing ligatures or table breaks [D: "2026-10-05 - Grounding Stage-1 text normalisation" - 2026-10-05].
  - GROBID 0.9.0 & PyMuPDF4LLM: evaluated in Experiment 3 pre-checks Check D/E 2026-10-14; raw ceiling 112/119 vs GROBID 81/119 and PyMuPDF4LLM 77/119; rejected [D: "Experiment 3 pre-checks result" - 2026-10-14].
  - Off-the-shelf table extraction (pymupdf4llm 1.28.2 & Docling 2.144.0): evaluated in Auditor v2 T1 2026-10-29; both FAILED (5/8 usable tables each, lost row-group spans) [D: "Auditor v2 T1 result, Ship-honest removed, new order (T2-R first)" - 2026-10-29].
- **Open issues on record:** PyMuPDF text fusion artifacts across line breaks ("muchhigher", "trustworthiness.") [D: "Deferred / Won't Do (for now)"]; injected headers, line-end hyphen splits, mid-sentence tables, lone numbers [D: "Held-out eval paper sealed (eval chain step 1)" - 2026-10-03]; raw reader loses 7 dev rows before any splitting [D: "Experiment 3 pre-checks result" - 2026-10-14].

### 4.2 Chunk
- **Current:** `RecursiveCharacterTextSplitter` with `chunk_size = 1200`, `chunk_overlap = 200`, separators `["\n\n", "\n", r"(?<=\. )", " ", ""]`, and length function `len` [C: Prism.PythonService/RAGService.py:9, 58-63]; character-based chunking with deterministic `uuid5(NAMESPACE_DNS, f"{file_id}:{i}")` chunk IDs in Qdrant [C: Prism.PythonService/RAGService.py:72] [D: "Deterministic uuid5 chunk IDs in Qdrant with delete-then-insert" - 2026-08-10].
- **Tried and failed or rejected:**
  - Sentence splitting (pysbd and regex): evaluated in Exp 3 pre-checks Check A 2026-10-14; regex gave 75.6% WHOLE; rejected for fixed windowing [D: "Experiment 3 pre-checks result" - 2026-10-14].
  - Windowed pass-2 re-extraction (6,000 char fixed windows, 1,500 overlap): evaluated in Exp 3 2026-10-16; REJECTED on cost gate c4 (projected INR 237.59 pooled / 243.75 mean vs 130 cap); flag `EXTRACTOR_SECOND_PASS` stays default off [D: "Experiment 3 B4 result" - 2026-10-16].
- **Open issues on record:** Page structure is lost when text is concatenated for chunking; `evidence_spans.page_number` and `evidence_spans.section_header` remain null across extracted claims [D: "Deferred / Won't Do (for now)"].

### 4.3 Embed
- **Current:** Fastembed `TextEmbedding(model_name="BAAI/bge-small-en-v1.5")` (vector size 384, cosine distance) [C: Prism.PythonService/RAGService.py:5, 21, 38] [R: ## Tech stack].
- **Tried and failed or rejected:** UNSOURCED [no alternative embedding model attempts recorded in the three files].
- **Open issues on record:** UNSOURCED.

### 4.4 Index
- **Current:** Qdrant vector database (`AsyncQdrantClient`) in single collection `prism_docs` [C: Prism.PythonService/RAGService.py:17-18] [D: "Deterministic uuid5 chunk IDs in Qdrant with delete-then-insert" - 2026-08-10] [D: "Deferred / Won't Do (for now)"]; delete-then-insert by `file_id` filter payload before upsert [C: Prism.PythonService/RAGService.py:50-55] [D: "Deterministic uuid5 chunk IDs in Qdrant with delete-then-insert" - 2026-08-10].
- **Tried and failed or rejected:** Azure AI Search evaluated 2026-09-01; rejected due to cost ($250/mo idle Basic tier) and quota (50MB/3 indexes Free tier) [D: "Managed vs self-hosted service split" - 2026-09-01].
- **Open issues on record:** Cross-file Qdrant isolation not implemented; all papers share `prism_docs` collection [D: "Deferred / Won't Do (for now)"].

### 4.5 Extract
- **Current:** Gemini 3.6 Flash via two-prompt sequential execution (`extract_metadata` Prompt 1, `extract_claims` Prompt 2) in `extraction/engine.py`; claim ceiling 25-45; outputs `claim_text_verbatim` + `claim_summary` [D: "Two-prompt extraction (metadata + claims) with shared engine helper" - 2026-08-08] [D: "Three-call claim extraction pipeline" - 2026-08-20] [D: "Extraction: positioning claims captured and ceiling raised" - 2026-09-10].
- **Tried and failed or rejected:**
  - Single-call extraction: failed to emit refusal labels (0 by_label); short-circuited reasoning; replaced by 3-call pipeline 2026-08-20 [D: "Three-call claim extraction pipeline" - 2026-08-20].
  - Section-by-section extraction: evaluated 2026-10-08; PARKED due to 3.1x cost and miss rows sitting in early sections [D: "Section-by-section extraction: feasibility confirmed, then PARKED" - 2026-10-08].
  - Few-shot claim-shape repair (Exp 2): evaluated 2026-10-14; all 4 required marks FAILED; flags `EXTRACTOR_FEWSHOT_FIX` and `EXTRACTOR_FEWSHOT_SHAPES` stay off [D: "Experiment 2 - Stage A result" - 2026-10-14].
  - Windowed pass-2 re-extraction (Exp 3): evaluated 2026-10-16; REJECTED on cost gate c4 [D: "Experiment 3 B4 result" - 2026-10-16].
  - Clean-extraction attempt (Exp 3 + pass-2 clean filter): evaluated 2026-10-20; REJECTED on K1, K4, K7, K8; `EXTRACTOR_PASS2_CLEAN` stays off [D: "Clean-extraction attempt result: FAIL, pass 2 stays off" - 2026-10-20].
- **Open issues on record:** `prompt_loader.py:58` treats few-shot examples with `"note"` field as negative, blanking 8 of 9 examples (PR #115 unmerged) [D: "prompt_loader few-shot "note" field bug" - 2026-10-06] [D: "PR-1 result (negative): few-shot loader fix, no coverage gain" - 2026-10-08]; extractor misses 13 dev refusal rows [S: ## Scoreboard]; 3 known risks in clean extraction code ("same"-relation chain-drop, unvalidated neighbor ids, positional answer mapping) [R: ## What I tried and why it failed] [S: ## Known risks (code-sourced, `docs/premerge_review_2026-10-20.md` section 3)].

### 4.6 Audit (including Structurer)
- **Current:** Gemini 3.6 Flash free-text reasoning per claim over the full paper text in `prompts/audit_claim_system.md`, ending in `VERDICT: supported|partially_supported|not_supported` + `QUOTE:` / `SECTION:` pairs; followed by Structurer (Gemini 3.6 Flash using Pydantic `response_schema` `ClaimLLM`); audit/structure concurrency capped by `AUDIT_STRUCTURE_CONCURRENCY = 5` [C: Prism.PythonService/extraction/engine.py:53] [D: "Three-call claim extraction pipeline" - 2026-08-20] [D: "Auditor prompt v2 — trap-claim labeling" - 2026-09-03] [D: "Auditor model swap + eval matcher calibration" - 2026-09-04] [D: "Correction: AUDIT_CONCURRENCY is 1, not 10" - 2026-09-29], while span grounding concurrency is capped by `AUDIT_CONCURRENCY = 1` [C: Prism.PythonService/extraction/grounding.py:53] [D: "Correction: AUDIT_CONCURRENCY is 1, not 10" - 2026-09-29].
- **Tried and failed or rejected:**
  - Gemini 3.1 Flash Lite auditor: swapped 2026-09-04 to Gemini 3.6 Flash [D: "Auditor model swap + eval matcher calibration" - 2026-09-04].
  - Scoped-auditor pilot: 1 run, 44 claims, ~INR 204; failed P3 (4 of 11 baseline refusals flipped to supported); negative result; archived on tag `archive/exp1-scoped-auditor` [D: "Backfill: records missing from this log" - 2026-10-15].
  - B5.1 auditor checklist + deterministic verdict cap: evaluated 2026-10-02; FAILED pre-registered marks; net effect neutral (18 vs 18 vs 18); branch unmerged, archived on tag `archive/b5.1-checklist-attempt` [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02].
  - Auditor `thinking_level=high` (Exp 1): evaluated 2026-10-12; fixed only 1 of 10 rows (needed >=3); REJECTED; `AUDITOR_THINKING_LEVEL` stays unset [D: "Experiment 1 result - Stage A FAIL, rejected" - 2026-10-12].
  - Auditor Stage A1 (caching + scope lister + scope checker): evaluated 2026-10-28; FAILED (fixed 3/10 misses, 1/6 always-missed vs 4 needed); flags stay off [D: "Stage A1 results: FAIL" - 2026-10-28].
  - Auditor v2 T1 & T2-R (code checks on tables): T1 FAILED 2026-10-29 (extractor infidelity); T2-R on LaTeX reference tables FAILED 2026-10-31 (fixed 4/10 misses, 2/5 hard vs 3 needed) [D: "Auditor v2 T1 result, Ship-honest removed, new order (T2-R first)" - 2026-10-29] [D: "T2-R result: FAIL (4/10 misses, 2/5 hard, 0 false rejections)" - 2026-10-31].
  - Gemini 3.8 Flash auditor (medium & high): evaluated 2026-11-06/09; Full check FAILED on M3, M4, M7; auditor stays Gemini 3.6 Flash [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- **Open issues on record:** Full-scope checking gap: auditor does not verify claim scope against reported evidence and accepts bold summary averages [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22]; sends full paper text once per claim (~75% to 90-96% of input tokens) [R: ## Cost] [D: "Auditor redesign agreed: caching + scope check, marks and caps" - 2026-10-22]; run-to-run noise at default medium thinking (~±3 rows) [R: ## What I tried and why it failed] [D: "Experiment 1 result - Stage A FAIL, rejected" - 2026-10-12]; full-pipeline token usage not logged in production [S: ## Open items] [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22].

### 4.7 Ground

#### Grounding's role
- **Audit label immutability:** Grounding never changes the stored audit label; `label` is set exclusively by the auditor (Call 3/4) and passed through unmodified, untouched by grounding [D: "Glossary"] [D: "Grounding aggregator: stance-aware labeling" - 2026-09-05].
- **Fields set by grounding:** Grounding sets `grounding_status` (`Pass`/`Partial`/`Fail` rollup on `ClaimFinal`, setting `missing=true` when a claim fails), `stance` (`supports`/`refutes`/`neutral` on `EvidenceSpanFinal`), and `reason` [D: "Grounding aggregator: stance-aware labeling" - 2026-09-05] [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26] [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20].
- **effective_status combination:** In PostgreSQL, `effective_status` is a `GENERATED ALWAYS AS (...) STORED` column (display layer only) that overrides the initial extraction/audit `label` when evidence fails (`missing=true`), while `label`, `missing`, and `grounding_status` remain unchanged [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20].
- **Eval scorer rejection count:** The eval counts a refusal-family catch as `by_grounding` when a claim was emitted and grounding rejected it (`missing=true`), checked before label, on a grounding-negative golden/dev row [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30].

- **Current:** Two-stage verification in `extraction/grounding.py`: Stage 1 RapidFuzz `partial_ratio` (threshold 88) with `GROUNDING_NORMALIZE` (NFKC, de-hyphenation, quote/dash normalization); Stage 2 LiteLLM call (`groq/openai/gpt-oss-20b`, fallback `gemini-3.1-flash-lite`, `AUDIT_CONCURRENCY = 1`) evaluating quoted context (snapped 500-1500 chars) with 3-tier verdict (`Pass`/`Partial`/`Fail`) and required `stance` (`supports`/`refutes`/`neutral`); does not change or lower the stored audit label (effective_status in Postgres overrides for display when missing=true; eval scorer counts by_grounding before label) [R: ## How it works] [D: "Grounding: two-stage RapidFuzz + LLM audit" - 2026-08-07] [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26] [D: "Grounding checker: verdict-aware rubric + reason string fix" - 2026-09-05] [D: "Grounding aggregator: stance-aware labeling" - 2026-09-05] [D: "2026-10-05 - Grounding Stage-1 text normalisation" - 2026-10-05] [D: "Correction: AUDIT_CONCURRENCY is 1, not 10" - 2026-09-29] [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
- **Tried and failed or rejected:**
  - 200-character fixed context window without paragraph snapping: evaluated 2026-08-26; caused ~100% false rejections; replaced by 500-1500 char snapping [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26].
  - Binary Pass/Fail rubric: replaced 2026-08-26 with 3-tier Pass/Partial/Fail [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26].
  - Label-blind rubric: evaluated 2026-09-05; refuting evidence was marked Fail; replaced with label-conditioned rubric [D: "Grounding checker: verdict-aware rubric + reason string fix" - 2026-09-05].
  - Label aggregation feedback loop (`_label_from_verdicts`): rejected 2026-09-05 to preserve acyclic architecture [D: "Grounding aggregator: stance-aware labeling" - 2026-09-05].
- **Open issues on record:** Cell-skipping quotes can pass `partial_ratio` (e.g. `ReAct (best of 6) 71` scores 90.0 against full row) [D: "2026-10-05 - Grounding Stage-1 text normalisation" - 2026-10-05]; Groq free tier 8K TPM / 200K RPD pushes most calls to Gemini Flash Lite fallback [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08]; sends temperature=0 when Google advises 1.0 for Gemini 3 [S: ## Open items] [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22].

### 4.8 Persist
- **Current:** Python extraction writer persists claims, evidence spans, and statuses to PostgreSQL (`paper_claims`, `document_extractors`, `file_records`) via `psycopg3` async pool, and chunk vectors to Qdrant; C# EF Core reads using dedicated `ValueConverter` classes (`ClaimLabelConverter`, `GroundingStatusConverter`) and `HasJsonPropertyName` for JSONB owned entities; Postgres `GENERATED ALWAYS AS (...) STORED` computes `effective_status` [D: "Domain seed via EF Core HasData" - 2026-08-09] [D: "psycopg3 async as the Python Postgres driver" - 2026-08-09] [D: "EF Core enum ↔ string mapping via dedicated ValueConverter classes" - 2026-08-22] [D: "HasJsonPropertyName for jsonb owned-entity snake_case mapping" - 2026-08-22] [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20].
- **Tried and failed or rejected:** Application-computed display status in C#/Python: rejected 2026-09-20 in favor of Postgres generated column to prevent cross-language drift [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20].
- **Open issues on record:** `SubmitPaperEndPoint` commits the DB row before publishing `PrismUploaded` to RabbitMQ with no MassTransit transactional outbox; publish failure leaves rows permanently stuck at `InProgress` [D: "reflexion.pdf stuck rows (DB/RabbitMQ publish sequence)" - 2026-10-06]; Postgres container password drift on local restarts [D: "Postgres Container Password Drift Workaround" - 2026-08-23]; `document_extractors.latest_run_id` is self-referential and misleading [D: "Deferred / Won't Do (for now)"].

---

## 5. Eval design and rules

### Eval Sets

| Set | Papers | Total Rows | Refusal-family Rows | Supported (S) Rows | Times Used | Status | Source |
|---|---|---|---|---|---|---|---|
| Dev | 12 | 119 | 31 (4 not_supported, 27 partially_supported; ~30 independent) | 88 | 1 full pipeline run (plus multiple replays) | Active dev benchmark (frozen 2026-10-11, hash cb3272cce551) | [R: ## Results] [S: ## Scoreboard] [D: "Dev set frozen" - 2026-10-11] |
| Golden | 3 (Reflexion, CoT, ReAct) | 37 | 16 (strict 16) | 21 | Multiple runs; frozen fixtures re-dumped 2026-10-07 | Active fast regression gate (de-leaked, hash cb3272cce551) | [R: ## Results] [S: ## Scoreboard] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] |
| Held-out | 1 (arXiv 2609.20812v3) | 12 | 2 (0 not_supported, 2 partially_supported: M04, M06) | 10 | Used 6 times | Near-burnt; last look before trusting generalization | [R: ## Results] [S: ## Scoreboard] [D: "Held-out eval paper sealed (eval chain step 1)" - 2026-10-03] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] |
| Sealed | 3-4 papers | UNSOURCED | UNSOURCED | UNSOURCED | 0 | Reserve fund allocated (INR 300); unbuilt / unrun | [D: "Release targets, order of work and stop rule amended" - 2026-10-10] [D: "Experiment 3 B1 review" - 2026-10-15] |

### Metric Definitions
- **Refusal-family catch:** Emitted claim whose grounding rejected it (`by_grounding`) OR whose label is `not_supported` / `partially_supported` (`by_label`) on a grounding-negative golden/dev row [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30].
- **Auditor miss:** Claim extracted and matched to a refusal row, but incorrectly labeled `supported` by the auditor and not vetoed by grounding [R: ## Status — 2026-10-21] [S: ## Scoreboard] [D: "Dev run 1 - fixture dump and pre-registered adjudication rules" - 2026-10-12].
- **Extraction miss:** A target row where no matching claim was emitted by the extractor [R: ## Status — 2026-10-21] [D: "Dev run 1 - fixture dump and pre-registered adjudication rules" - 2026-10-12].
- **False rejection:** Supported (S) row where the claim was incorrectly judged unsupported (label lowered or vetoed by grounding) [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26] [D: "Stage A1 marks and cap re-confirmed" - 2026-10-28].
- **Positives (Positive hits):** Supported golden/dev row matched to an emitted claim that passed audit and grounding [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26] [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30].
- **Needs review:** Ambiguous code-check outcome (missing cell, unparsable cell, member in other table, exact tie on strict comparison, or kept caveat); only replaces Supported; never counted as a catch, positive hit, or false rejection [D: "Auditor v2 (D6+D7): design, T1/T2 marks and Needs-review scoring" - 2026-10-28].
- **Coverage:** Share of evaluation set rows with confirmed human adjudication in the match map; coverage below 100% suppresses the headline percentage and forces exit code 1 [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30].

### Rules
- **Pre-registration process:** Every experiment must have written pass/fail marks and an explicit rupee spend cap logged in `docs/decisions.md` before any paid call is made [R: ## Evaluation method] [D: "Cost caps, run procedure and marks for the dev baseline" - 2026-10-11] [S: ## Working rules].
- **No-rescue rule:** A failing required mark rejects the change outright; no partial credit, no re-running, no threshold edits to save a result [R: ## Evaluation method] [D: "Experiment 3 B4 result" - 2026-10-16] [D: "Stage A1 results: FAIL" - 2026-10-28].
- **Auditor no-regression rule:** An auditor change is KEPT only if all of these hold over 3 identical runs: (1) Gain: >= 1 more of the 10 auditor misses fixed in >= 2 of 3 runs vs current floor; (2) No lost catches: each of today's 8 caught refusal rows stays caught in >= 2 of 3 runs; (3) False rejections: no worse than flag-off baseline and never above 8/88; (4) Golden >= 5/16 and positives >= 11/21 in >= 2 of 3 runs; (5) Grounding-negative: any FAIL blocks the change; (6) Not overfit: targets a failure TYPE, no special-casing eval rows [D: "Auditor no-regression rule" - 2026-10-28].
  - **Subsequent amendments and additions (on/after 2026-10-28):**
    - *Needs-review scoring amendments (2026-10-28):* Needs review is never a catch; a refusal row ending in Needs review is not caught (own bucket, no credit, stays in denominator); an auditor miss ending in Needs review is not fixed; a caught refusal row ending in Needs review is a lost catch; Needs review on an S row is not a false rejection but counts toward the ceiling; Needs review is not a positive hit; Ceiling added to no-regression checks: Needs review on dev S rows <= 8/88 in >= 2 of 3 runs, and <= 10% of all audited claims in every run (over ceiling = not kept) [D: "Auditor v2 (D6+D7): design, T1/T2 marks and Needs-review scoring" - 2026-10-28].
    - *Miss targets and noise exclusions (2026-11-02, 2026-11-08):* P1-R3 is excluded from the real caught hits total (M2) as documented run-to-run noise (scored out of 7 real hits); P5-R1 (figure) and P5-R2 (duplicate) are parked, reducing miss targets from 10 to 8 [D: "10-miss analysis: failure types and scope" - 2026-11-02] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
    - *Fresh baseline for false rejections (2026-11-07, 2026-11-08):* M3 false rejections evaluated against fresh parallel baseline measured in the same run (1/88), not run 1's 4/88 [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
    - *Bounded fallback scoring and crash recovery (2026-11-08):* Fallback-served audits are scored bounded as worst-case for candidate and best-case for baseline (D9 rule); arm is void if > 16 fallback-served audits occur (V3); rule V5 permits re-running a single failed repeat $K$ with `--repeat-index K` and `--max-inr` capped at one-third of the run's cap [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
    - *Cost gate addition (2026-11-08):* Mark M7 requires projected full-pipeline cost per paper <= INR 130 [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
- **Release bar (restated 2026-10-22):** Dev: one full 12-paper run reaches >= 22/31 refusal-family rows with false rejections <= 8/88, and the fixes are stable under the auditor no-regression rule. Release number: one sealed-set run only, never dev or golden numbers [R: ## Results] [S: ## Scoreboard] [D: "Auditor redesign agreed: caching + scope check, marks and caps" - 2026-10-22] [D: "Auditor no-regression rule" - 2026-10-28].
- **Cost gate:** Projected full-pipeline cost per paper must be <= INR 130 [D: "Experiment 3 pre-registration" - 2026-10-15] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
- **Paid-run stop rule (1.3x estimate):** Stop any paid run immediately if actual spend exceeds 1.3x its estimate [D: "Experiment 1 pre-registration (auditor thinking_level=high)" - 2026-10-12] [D: "Auditor redesign agreed: caching + scope check, marks and caps" - 2026-10-22].
- **Capped run = void:** A run stopped by a budget cap is void and provides no result; rescue re-runs are prohibited without a new dated entry [D: "Cost caps, run procedure and marks for the dev baseline" - 2026-10-11] [D: "Clean-extraction full runs: settings and run plan" - 2026-10-19].
- **Sealed reserve:** INR 300 reserved exclusively for final evaluation on unseen papers, untouched by development pushes [D: "Experiment 1 pre-registration (auditor thinking_level=high)" - 2026-10-12] [S: ## Budget status].

### Labelling Process
- Dev rows were hand-labelled under a written rubric (`docs/LABEL_RUBRIC.md`) before any Prism output was seen [R: ## Evaluation method] [D: "Label rubric frozen" - 2026-10-10].
- Golden rows were hand-audited against PDFs and corrected only where the paper contradicted them [R: ## Evaluation method] [D: "12 golden-eval corrections after hand-auditing all 3 papers" - 2026-10-01] [D: "2026-10-03 - Eval chain step 0: matrix_eval positive rows re-checked" - 2026-10-03].
- Blind dual-AI judges (ChatGPT, Gemini) produce initial pairings/labels; human (Nitin) adjudicates disagreements and spot-checks [R: ## Evaluation method] [D: "Held-out eval paper sealed (eval chain step 1)" - 2026-10-03] [D: "Clean-extraction attempt: spot-check result, diagnostic, bounded scoring" - 2026-10-20] [D: "S-row match map written; cost-tool fix recorded" - 2026-10-27].
- Splits and adjudications on dev rows and held-out files are decided by Nitin [D: "Held-out eval paper sealed (eval chain step 1)" - 2026-10-03] [D: "S-row match map written; cost-tool fix recorded" - 2026-10-27] [D: "T2-R inputs: form policies, adjudication, findings" - 2026-10-30].

### Eval Tooling
- **Vertex eval backend:** Command-line flags `--backend vertex`, `--vertex-project gen-lang-client-0520352487`, and location `global` enable routing eval experiments to Google Cloud Vertex AI, billed directly to the GCP Free Credit [D: "Funding source and model plan for the next auditor tests" - 2026-11-02] [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
- **score_screen (`eval/score_screen.py`):** Dedicated scoring script for screening runs; scores across exactly 3 repeat folders per arm using a per-claim 2-of-3 majority vote with mandatory absolute paths and `--json-out` directed outside the repo; reports targets fixed (out of 8), real hits lost (out of 7), and flags any fallback-served audits [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06].
- **score_full_check (`eval/score_full_check.py`):** Scoring tool for the full no-regression check; runs pairwise evaluations (C1 vs B, C2 vs B) across 3 dev and 3 golden folders using per-row 2-of-3 votes; evaluates fallback-served audits under bounded scoring as worst-case for candidate and best-case for baseline (D9 rule) [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- **Golden replay with golden text:** Golden replay infrastructure (`scratch/auditor_rd/golden_text_cache`, built 2026-11-07); resolves each fixture's run id via `document_extractors.latest_run_id` lookup to `file_records` sha256 to pick the exact PDF; verified via a two-way Stage-1 guard with the production scorer (threshold 88, `normalize=True`) reproducing all 236 frozen spans (Reflexion 89, CoT 59, ReAct 88) [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
- **--repeat-index:** CLI flag for bounded crash recovery (Rule V5); permits re-running a single failed repeat $K$ that stopped without `_summary.json` once on the same day (using `--repeat-index K` and `--max-inr` capped at one-third of the run's cap) instead of voiding the entire 3-repeat arm [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].

---

## 6. Test and experiment log

*Comparability note: Tests run before 2026-09-30 used an eval scorer with the omission-credit bug (crediting unextracted claims as correct refusals), and tests before 2026-10-05/07 had eval-paper text and answer-key wording leaked into prompts; the scorer fix re-scored the same 14 rows from 11/14 to 5/14, so pre-2026-09-30 refusal numbers are inflated; the de-leak itself showed no detectable change (golden 6/16 to 5/16, one extraction miss), but prompts, match maps and denominators changed, so pre-2026-10-07 numbers are not directly comparable [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05].*

| Date | Test | What changed | Pre-registered marks | Result numbers | Verdict | Comparable to current scores? | Cost | Deviations recorded | Source |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-20 | Three-call pipeline | Split extract_claims into extractor, auditor, structurer | Positive-hit floor >= 10 | Refusal 13/14 (93%), positive hits 15/23, by_label 2 | no verdict recorded | No - omission-credit scorer bug credited omitted claims as refusals [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] | UNSOURCED | None | [D: "Three-call claim extraction pipeline" - 2026-08-20] |
| 2026-08-26 | Slice 2.8 | Grounding context widening (500-1500 chars) + 3-tier rubric | Refusal threshold 80% | Refusal 10/14 (71%), positive hits 16/23, false rejections 1/23 | Shipped below gate | No - omission-credit scorer bug credited omitted claims as refusals [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] | UNSOURCED | Full formal 3-paper re-run not completed due to live environment constraints | [D: "Slice 2.8: Grounding pipeline context widening & 3-tier rubric" - 2026-08-26] [D: "Slice 2.8 baseline — coverage-vs-refusal trade-off" - 2026-08-27] |
| 2026-09-01 | PR 5 (First Azure Deploy) | Azure Container Apps deploy | Deploy live URL | 12 deployment issues encountered and patched via az CLI | no verdict recorded | UNSOURCED | UNSOURCED | 4 manual az CLI patches required on running resources | [D: "First Azure deploy" - 2026-09-01] |
| 2026-09-03 | Extractor v4.1 | Pattern A/B trap claim few-shots in extractor | 70% refusal threshold | Refusal 4/14 (29%), positive hits 17/23, false rejections 0/23 | FAIL vs 70% threshold (shipped below threshold) | No - omission-credit scorer bug credited omitted claims as refusals [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] | UNSOURCED | Extractor recall improved (omissions 9->2), but auditor lacked labeling prompt | [D: "Extractor prompt v4.1 — trap-claim recall + eval row enrichment" - 2026-09-03] |
| 2026-09-03 | Auditor v2 | Inline Pattern A/B examples in auditor prompt | 70% refusal threshold | Refusal 10/14 (71%), positive hits 13/23, false rejections 0/23 | no verdict recorded | No - omission-credit scorer bug credited omitted claims as refusals [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] | UNSOURCED | None | [D: "Auditor prompt v2 — trap-claim labeling" - 2026-09-03] |
| 2026-09-04 | Auditor Model Swap | Swapped auditor from gemini-3.1-flash-lite to gemini-3.6-flash | Regression gate | Refusal 10/14 (71%), positive hits 13/23, false rejections 0/23 | PASS | No - omission-credit scorer bug; matcher was on flash-lite over-matching claims, positive hits not directly comparable [D: "Auditor model swap + eval matcher calibration" - 2026-09-04] [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] | UNSOURCED | None | [D: "Auditor model swap + eval matcher calibration" - 2026-09-04] |
| 2026-09-23 | Azure Live Eval | Live eval runs against Azure Postgres | DB consistency | Run 1: Refusal 12/14 (86%), Pos 14/23, FR 0/23. Run 2: Refusal 12/14 (86%), Pos 15/23, FR 0/23 | no verdict recorded | No - omission-credit scorer bug credited omitted claims as refusals [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30] | UNSOURCED | Positive hits varied from matcher LLM stochasticity | [D: "First two valid live eval runs against Azure Postgres" - 2026-09-23] |
| 2026-10-02 | B5.1 Auditor Checklist | Checklist lines in auditor output + deterministic verdict cap | Wrongly affirmed <= 2, pos hits >= 11/22, FR <= 1, cap-lowered positives = 0, COT-M08/09/10 refused | v3_a: Refusal 9/15, Pos 9/22 (FAIL), FR 2/22 (FAIL). v3_b: Refusal 7/15, Pos 11/22, FR 1/22, wrongly affirmed 3 (FAIL) | FAIL / Not merged | No - first replay on old key had 14 neg / 23 pos denominators, not comparable to v3; prompt leakage not yet de-leaked [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] | UNSOURCED | First replay marks not recorded in saved file on main; tag preserved | [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02] |
| 2026-10-03 | Held-out baseline (eval chain step 2) | Baseline measurement on sealed held-out paper (arXiv 2609.20812v3) against frozen match map before any tuning | UNSOURCED | Coverage 12/12; Refusal-family 1/2, Strict 1/2, Positive hits 8/10, False rejections 0/10, Skipped 0; one claim (pos 1) covers six rows (M01-M05 + M11) | no verdict recorded | No - prompt hash 0bcf9d44e619 predates prompt de-leak [D: "Held-out baseline (eval chain step 2)" - 2026-10-03] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] | INR 0 | None | [D: "Held-out baseline (eval chain step 2)" - 2026-10-03] |
| 2026-10-05 | Grounding Stage-1 Normalization | Added `normalize_for_match` to Stage 1 RapidFuzz | Threshold 88 preserved | 20 spans fail->pass, 0 pass->fail; 2 claim-level Stage-1 flips FAIL->PASS | PASS | No - measured on post-reset runs, not frozen baseline [D: "2026-10-05 - Grounding Stage-1 text normalisation" - 2026-10-05] | UNSOURCED | Measured on post-reset runs, not frozen baseline | [D: "2026-10-05 - Grounding Stage-1 text normalisation" - 2026-10-05] |
| 2026-10-07 | De-leak PR-B | Removed eval paper text & answer keys from prompts | Refusal >= 0.35, N=2 live runs per arm; gate reset rule: if below 0.35, resets to clean baseline (rounded down) [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] | Golden: refusal-family 5/16 (0.3125), strict 5/16, wrongly affirmed 4, not extracted 7, positive hits 11/21 (floor 10), false rejection 1/21, coverage 37/37; Held-out: 1/2, 7/10, 0/10, 12/12; gate reset 0.35 -> 0.30 after result under pre-registered rule | Passes by one row | Yes - de-leaked prompts, frozen fixtures, basis for current golden baseline [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] | UNSOURCED | N=1 run only (deviation from pre-registered N=2) | [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] |
| 2026-10-08 | PR-1 | Few-shot loader "note" fix | M1 min >= 18, M2 GN mean >= 9.60, M3-M5 | Golden FULL mean 20.4->20.6; GN FULL mean 9.6->8.8; M1 FAIL, M2 FAIL | FAIL (kept as correctness fix) | No - extractor-only harness measuring extraction recall, not comparable to end-to-end refusal scores [D: "PR-1 result (negative): few-shot loader fix, no coverage gain" - 2026-10-08] | UNSOURCED | M6 held-out run skipped | [D: "PR-1 result (negative): few-shot loader fix, no coverage gain" - 2026-10-08] |
| 2026-10-08 | Section-by-section extraction | Feasibility check for section-by-section extraction to reach late-paper claims | Reach late-paper claims | Feasibility confirmed; 3 of 4 missed refusal rows sit in sections 1-2; at most 1 row would gain; cost 3.1x extractor input, 48 calls/run | PARKED | No - feasibility check only, not a pipeline eval run [D: "Section-by-section extraction: feasibility confirmed, then PARKED" - 2026-10-08] | INR 0 | `pr2_feasibility_report.md` cited in decisions.md does not exist in repo | [D: "Section-by-section extraction: feasibility confirmed, then PARKED" - 2026-10-08] [D: "Backfill: records missing from this log" - 2026-10-15] |
| 2026-10-11 | Baseline Run 1 Pilot | 4 of 12 dev papers uploaded | INR 800 cap per 12-paper run | 4 papers cost INR 405.55 (~INR 101/paper); 139 claims: 135 S, 4 PS, 0 NS | Paused | UNSOURCED | INR 405.55 | 3-run baseline dropped to 1 run to conserve budget | [D: "Baseline run 1 paused at 4 of 12; diagnose before spend" - 2026-10-11] |
| 2026-10-12 | Dev Baseline Run 1 | Ingested remaining 8 dev papers (12 total) | M1 validity, match map coverage 100% | Refusal 8/31 (26%); 10 audit misses, 13 extraction misses; FR 4/88 effective | PASS (as baseline) | Yes - active dev benchmark run [D: "Dev run 1 - fixture dump and pre-registered adjudication rules" - 2026-10-12] | INR 11.38 matcher calls; ~INR 1,048.40 total | Single run baseline instead of 3 runs | [D: "Dev run 1 - fixture dump and pre-registered adjudication rules" - 2026-10-12] [R: ## Cost] |
| 2026-10-12 | Exp 1 (Control medium x2) | Auditor thinking default (medium) replay | Baseline stability | Hits 8 (run 1), 7, 5; spend 1.79x estimate | Pre-registered stop triggered | UNSOURCED | INR 155.11 | Auditor showed +/-3 rows run-to-run noise | [D: "Experiment 1 Stage A - amendment after control arm, before any high output" - 2026-10-12] |
| 2026-10-12 | Exp 1 (High x3) | Auditor `thinking_level=high` | Fixed >= 3 of 10, lost hits <= 1 of 8 | Fixed 1/10 (P1-R1), lost hits 0/8; raw hits 10, 10, 10 | FAIL | UNSOURCED | INR 256.84 | Stage B not run; switch default left off | [D: "Experiment 1 result - Stage A FAIL, rejected" - 2026-10-12] |
| 2026-10-14 | Exp 2 (Redesigned) | Extractor few-shot claim shapes (8 new examples) | A1 >= 5/13 recovered both runs, A2 min trt - ctrl >= 3, A3 >= 12/13 matched kept, A4 claims <= 1.5x ctrl | A1 FAIL (1/13, 1/13), A2 FAIL (-2), A3 FAIL (11/13, 9/13), A4 PASS (285, 287 vs 463.5) | FAIL | UNSOURCED | INR 177.93 | A3 scope redefined to 13 replayed matched rows before adjudication | [D: "Experiment 2 - Stage A result" - 2026-10-14] |
| 2026-10-14 | Exp 3 pre-checks | Checks A (splitters), B (sentence count), C (union), D (readers), E (failure diagnosis) | Checks A & D >= 95% WHOLE (113/119) | Check A FAILED (best regex 75.6%); Check D FAILED (fixed windows 6000/1500 chars 94.1% WHOLE, 112/119 vs 112 raw ceiling); Check E: 7 NOT_FOUND identical to raw reader loss; ceilings: raw 112/119, GROBID 81/119, PyMuPDF4LLM 77/119 | Both FAILED (Checks A & D) | No - local text split/reader survival check, not an auditor/extraction pipeline score [D: "Experiment 3 pre-checks result" - 2026-10-14] | INR 0 | Check D bar (113/119) set above raw-text ceiling (112/119) recorded as design error in check | [D: "Experiment 3 pre-checks result" - 2026-10-14] |
| 2026-10-15 | Scoped-auditor pilot | Scoped auditor tested on 44 claims (AUDIT_MODE) | P3 (no baseline refusals flipped to supported) | 1 run, 44 claims; Failed P3: 4 of 11 baseline refusals flipped to supported | Negative result | No - unmerged pilot on legacy baseline, predates de-leak and scorer fix [D: "Backfill: records missing from this log" - 2026-10-15] | ~INR 204 | Exact run date not recorded in source files (logged in backfill 2026-10-15) | [D: "Backfill: records missing from this log" - 2026-10-15] |
| 2026-10-15 | Exp 3 Pilot 1 | Pass-2 windowed extraction, default thinking | Windows 1-26 sentence count & cost | 26 windows completed, 128 sentences, crash on mkdir | Aborted / Crashed | UNSOURCED | INR 40.12 (meter) | Run crashed before writing summary; recovered from logs | [D: "Experiment 3 amendment 1" - 2026-10-15] |
| 2026-10-15 | Exp 3 Pilot 2 | Pass-2 thinking LOW, frozen pass 1 | Stop (a) sentences >= 90; Stop (b) INR/window <= 0.60 | 34/34 windows, 124 sentences (windows 1-26), INR 0.37/window | PASS | UNSOURCED | INR 12.52 (meter) | Frozen pass 1 claims loaded from fixture | [D: "Experiment 3 pilot 2 result and Phase 4 cap" - 2026-10-15] |
| 2026-10-15 | Exp 3 pass2_r1 | 12 dev papers, pass 2 thinking LOW | c1 >= 5, c6 >= 3, c4 <= 130, c7 >= 0.95, c8 >= 0.70 | 261 windows, 1,114 sentences, 962 merged claims; c4 projected INR 243 > 130 | Gated run | UNSOURCED | INR 66.75 (meter) | Replay used frozen pass 1 | [D: "Experiment 3 pass2_r1 result" - 2026-10-15] |
| 2026-10-16 | Exp 3 pass2_r2 | 12 dev papers, pass 2 thinking LOW | Same as pass2_r1 | 261 windows, 1,111 sentences, 969 merged claims; c4 projected INR 245 > 130 | Gated run | UNSOURCED | INR 66.40 (meter) | Replay used frozen pass 1 | [D: "Experiment 3 pass2_r2 result" - 2026-10-16] |
| 2026-10-16 | Exp 3 B4 | Scoring pass 2 runs | c1, c6, c4, c7, c8 gates | c4 FAIL (INR 237.59 pooled / 243.75 mean vs 130); c7 PASS (0.987 / 0.989); c2 18/18; c1/c6/c8 not measured | REJECTED | UNSOURCED | INR 0 | Human labeling not done; rejected on c4 deterministic cost gate | [D: "Experiment 3 B4 result" - 2026-10-16] |
| 2026-10-16 | Exp 3 c1/c6 (Exploratory) | AI-proposed, human-verified matching on c1 | Informal check: c1 >= 5, c6 >= 3 | c1: r1 8/13, r2 8/13 (PASS); c6: r1 8/13, r2 8/13 (PASS) | Exploratory only (not a PASS) | UNSOURCED | INR 0 | AI-proposed, human-verified matching instead of pre-registered blind adjudication | [D: "Experiment 3 c1/c6 result (AI-proposed, human-verified)" - 2026-10-16] |
| 2026-10-18 | Clean Attempt Pilot | Single-paper comparison (2610.10590v1) | Recall gain >= 10 pp, precision >= 0.70 | Key B: gain 19.23 pp, prec 0.833; Key A: gain 19.18 pp, prec 0.778 | KEEP | UNSOURCED | INR 4.4 | Tested on single in-sample paper | [D: "Pass-2 comparison result for 2610.10590v1: KEEP" - 2026-10-18] |
| 2026-10-20 | Clean-Extraction Attempt | Pass-2 clean filter on Exp 3 outputs | K1 >= 7/8 stable, K2 18/18, K3 r <= 1.40, K4 <= 130, K5 >= 0.95, K6 >= 0.70, K7 <= 1, K8 <= 40 filter / 350 total | K1 FAIL (5/13, 6/13); K2 PASS (18/18); K3 r 2.50/2.47; K4 FAIL (INR 230.52/227.55); K5 PASS (0.991); K6 PASS (0.81-0.95); K7 FAIL (43/18 not-same); K8 FAIL (INR 64.25/58.31 vs 40) | REJECTED | UNSOURCED | INR 311.04 | Bounded scoring used due to human spot-check divergence on AI labels | [D: "Clean-extraction attempt result: FAIL, pass 2 stays off" - 2026-10-20] |
| 2026-10-26 | Stage A0 | Explicit context caching on 18 frozen claims | M1 cached on all but <= 1 call/paper; M2 audit cost >= 40% below baseline excl. setup; M3 refusal hits 5-8 | M1 PASS (0 failed calls, 414,204 tokens cached); M2 PASS (INR 1.30 vs 3.79, 66% below); M3 PASS (8/31) | PASS | UNSOURCED | INR 36.86 (Google SKU report) | Creation was not billed by Google AI Studio | [D: "Stage A0 results" - 2026-10-26] |
| 2026-10-27 | Cache + Schema Probe | Single cached request with response_schema + thinking low | No API error, schema parsed, cached tokens > 0 | PASS: parsed ProbeOut, 13,125 cached tokens | PASS | UNSOURCED | INR 0.21 | Single test call on single paper | [D: "Cache + schema + low-thinking probe: PASS" - 2026-10-27] |
| 2026-10-28 | Stage A1 | Scope lister + checker (3 repeats, 18 claims) | A1-fixed >= 5/10 (incl. >= 4/6 always-missed); A1-lost <= 1/7; A1-quote 0 violations | A1-fixed FAIL (5/10 miss rows PS/NS, but always-missed 1/6); A1-lost PASS (1/7); A1-quote PASS (0 violations) | FAIL | UNSOURCED | INR 136.16 (tool) | Groq hit free limit, fell back to Flash Lite; Stage B not run | [D: "Stage A1 results: FAIL" - 2026-10-28] |
| 2026-10-28 | A1 diagnosis | Trace diagnosis of 10 miss rows x 3 repeats (30 cells) | One clear cause in >= 4 of 5 unfixed always-missed rows in >= 2 of 3 repeats | Code R in 3 of 5 (P5-R2, P4-R2, P6-R2); S1 in 1 (P11-R2); P3-R2 mixed; 3 < 4 (no single clear cause); checker reading summaries in 9 of 15 cells; lister named breaking element in 13 of 15 cells | Ship-honest (decisions.md option B) | No - trace diagnosis of 30 cells, not a full pipeline run [D: "A1 diagnosis results: Ship-honest (decisions.md option B)" - 2026-10-28] | INR 0 | Option B fallback later superseded/removed 2026-10-29 | [D: "A1 diagnosis results: Ship-honest (decisions.md option B)" - 2026-10-28] |
| 2026-10-29 | Auditor v2 T1 | Table extraction fidelity (pymupdf4llm vs Docling) | >= 7 of 8 gate tables usable per extractor alone; stable output | pymupdf4llm: 5/8 usable, 13/21 breaking cells; Docling: 5/8 usable, 14/21 breaking cells | FAIL, no winner | UNSOURCED | INR 0 | Pre-run label check missed key-column header labels | [D: "Auditor v2 T1 result, Ship-honest removed, new order (T2-R first)" - 2026-10-29] |
| 2026-10-31 | Auditor v2 T2-R | Code checks on LaTeX reference tables | M1 Gain: PS/NS >= 4/10 misses & >= 3/5 hard; M2 Faithful; M3 S rows lowered = 0; M4 S rows Needs review <= 2; M5 tests pass | M1 FAIL (4/10 misses, but 2/5 hard); M2 FAIL (2/5 hard); M3 PASS (0/10 lowered); M4 PASS (2/10 Needs review); M5 PASS (43 tests) | FAIL | No - ceiling measured with hand-written forms on LaTeX reference tables, not a pipeline score [D: "Record: T2-R wording correction and two input notes" - 2026-10-31] | INR 0 | P3 pin resolved from PDF page directly; 3 items assembled from single judge | [D: "T2-R result: FAIL (4/10 misses, 2/5 hard, 0 false rejections)" - 2026-10-31] |
| 2026-11-04 | Vertex Smoke 1 | Probe cache schema on gemini-3.8-flash via Vertex AI | No API error, schema parsed, cache tokens > 0 | CACHE_NOT_CREATED: 403 PERMISSION_DENIED aiplatform.endpoints.predict | FAIL (mechanics) | UNSOURCED | INR 0 | First-use provisioning delay of Vertex AI service agent | [D: "Vertex smoke test, attempt 1: FAIL (mechanics)" - 2026-11-04] |
| 2026-11-06 | Vertex Smoke 2 | Probe cache schema on gemini-3.8-flash via Vertex AI | Same as Smoke 1 | PASS: 13,124 cached tokens read, schema parsed, thinking low accepted | PASS | UNSOURCED | INR 0.24 (list) / INR 1.11 billed | Vertex AI billed cache creation | [D: "Vertex smoke attempt 2 result, billing check, housekeeping" - 2026-11-06] |
| 2026-11-06 | 3.8 Screen (Attempt 1) | Replay audit: 3.6 med (Arm 1), 3.8 med (Arm 2), 3.8 high (Arm 3) | W1 targets fixed >= arm1 + 1, W2 hits lost = 0, W3 not void | Arm 1 completed; Arm 2 crashed in repeat 2 (JSON control char \x10, \x11 in structurer); Arm 3 not started | VOID | No - screen filter numbers are not quoted as a Prism score [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06] | in the combined figure on the Attempt 2 row | Arm 2 voided under V2; code fixed with `strict=False` in json.loads | [D: "Screen attempt 1: arm 2 void (structurer JSON crash), fix, re-run of arms 2 and 3" - 2026-11-06] [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09] |
| 2026-11-06 | 3.8 Screen (Attempt 2) | Re-run Arm 2 & Arm 3 on fixed code vs Arm 1 | Same as Attempt 1 | Arm 1: 0 fixed, 2 lost, 2 fallback audits. Arm 2: 2 fixed, 0 lost. Arm 3: 5 fixed, 0 lost. V3/V4 triggered | VOID | No - screen filter numbers are not quoted as a Prism score [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06] | INR 842.86 billed, both attempts combined [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09] | Arm 1 had 2 fallback-served audits, triggering V3 and voiding screen under V4 | [D: "Screen attempt 2: void (V3 -> V4), robustness note, decision to take gemini-3.8-flash high to the full check" - 2026-11-07] [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09] |
| 2026-11-08/09 | Full No-Regression Check | 106 claims (84 dev, 22 golden) x 3 repeats: B (3.6 med) vs C1 (3.8 med) vs C2 (3.8 high) | M1 fixes >= B + 1; M2 lost = 0; M3 FR <= B & <= 8/88; M4 golden ref >= 5/16, pos >= 11/21; M5 GN; M6 NR = 0; M7 cost <= 130 | B: 0 fixes, 1 lost, 1 FR, golden 6/16 ref, 13/21 pos. C1: 2 fixes (PASS), 0 lost (PASS), 4 FR (FAIL), golden 7/16, 12/21 (PASS), cost INR 104.0 (PASS). C2: 4 fixes (PASS), 0 lost (PASS), 7 FR (FAIL), golden 9/16, 10/21 pos (FAIL), cost INR 194.4 (FAIL) | FAIL (both C1 and C2) | No - eval replay check under 2-of-3 majority vote, product recorded scores unchanged [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09] | INR 4,111.48 billed (INR 3,542.75 counted audit calls at list price) [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09] | Grounding model set to gemini-3.1-flash-lite across all arms | [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09] [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09] |

---

## 7. Current scores

### Latest Scores per Dataset

| Set | Run Date | Run Description | Refusal-family Rate | Positive Hits | False Rejections | Coverage | Source |
|---|---|---|---|---|---|---|---|
| Dev baseline | 2026-10-12 | Single full 12-paper run (Run 1, n=31 refusal rows, 119 total rows) | 8/31 (26%) | UNSOURCED [not adjudicated in Run 1] | 4/88 effective (draft resolved) | not recorded | [R: ## Results] [S: ## Scoreboard] [D: "Dev run 1 - fixture dump and pre-registered adjudication rules" - 2026-10-12] [D: "Corrections" - 2026-10-22] |
| Replay baseline B, 2026-11-09 (3 runs, 2-of-3 vote; not a product score) | 2026-11-09 | Full check baseline B replay (3.6 med, Vertex backend, gemini-3.1-flash-lite grounding) | Golden 6/16 (dev 0/8 targets fixed, 1/7 real hits lost: P6-R1) | 13/21 (golden) | 1/88 (P4-S4) | 106 claims (84 dev, 22 golden) | [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09] |
| Golden | 2026-10-07 | De-leaked prompts, frozen fixtures (PR-B, 3 papers, 37 total rows) | 5/16 (31%), gate 0.30 | 11/21 (floor 10) | 1/21 | 37/37 | [R: ## Results] [S: ## Scoreboard] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] |
| Held-out | 2026-10-07 | arXiv 2609.20812v3 (1 paper, 12 rows, run 4804fc57) | 1/2 (50%) | 7/10 | 0/10 | 12/12 | [R: ## Results] [S: ## Scoreboard] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05] |

- Note on Replay baseline B difference from Run 1: Replay evaluated with `gemini-3.1-flash-lite` grounding across all arms (which decisions.md notes may shift golden outcomes), on Vertex AI backend, and scored by per-row 2-of-3 majority vote across 3 repeats; product recorded scores remain Run 1 [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08] [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].

### Targets and Ceilings
- **Release bar (restated 2026-10-22):** Dev: one full 12-paper run reaches >= 22/31 refusal-family rows with false rejections <= 8/88, and fixes stable under auditor no-regression rule. Release number: one sealed-set run only, never dev or golden numbers [R: ## Results] [S: ## Scoreboard] [D: "Auditor redesign agreed: caching + scope check, marks and caps" - 2026-10-22] [D: "Auditor no-regression rule" - 2026-10-28].
- **Auditor-only ceiling:** 18/31 (below the 22/31 floor) [R: ## Status — 2026-10-21] [S: ## Scoreboard] [D: "Experiment 1 result - Stage A FAIL, rejected" - 2026-10-12] [D: "A1 diagnosis results: Ship-honest (decisions.md option B)" - 2026-10-28].
- **Extraction-only ceiling:** 21/31 (68%, also below the 22/31 floor) [R: ## Status — 2026-10-21] [S: ## Scoreboard] [D: "Experiment 3 B1 review" - 2026-10-15].

---

## 8. Costs and money

### Per-Paper Costs
- Current pipeline per-paper cost: about **INR 87-101**, measured as INR ~101/paper from 2026-10-11 baseline spend (4 papers, INR 1,250.00 -> 1,655.55) and INR ~87/paper from 12-paper run-1 ingestion (INR 1,048.40 / 12 papers) [R: ## Cost] [D: "Baseline run 1 paused at 4 of 12; diagnose before spend" - 2026-10-11] [D: "Experiment 3 B1 review" - 2026-10-15].
- Windowed pass 2 (Exp 3) projected per-paper cost: projected INR 237.59 (pooled) / 243.75 (mean) [D: "Experiment 3 B4 result" - 2026-10-16].
- Clean-extraction attempt projected per-paper cost: projected INR 230.52 (mean) / 227.55 (pooled) [D: "Clean-extraction attempt result: FAIL, pass 2 stays off" - 2026-10-20].
- Full no-regression check projected per-paper cost: C1 (3.8 medium) = INR 104.0; C2 (3.8 high) = INR 194.4 [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].

### Spend per Paid Test
- Experiment 1: INR 411.95 (medium x2 INR 155.11, high x3 INR 256.84) [D: "Experiment 1 result - Stage A FAIL, rejected" - 2026-10-12] [S: ## Experiments and verdicts].
- Experiment 2: INR 177.93 (pilot 2.77 + control 56.58 + treatment_r1 59.63 + treatment_r2 58.95) [D: "Experiment 2 - Stage A result" - 2026-10-14] [S: ## Experiments and verdicts].
- Experiment 3: INR 185.79 (meter; pilot 1 INR 40.12, pilot 2 INR 12.52, pass2_r1 INR 66.75, pass2_r2 INR 66.40, B4 INR 0) [D: "Experiment 3 B4 result" - 2026-10-16] [S: ## Experiments and verdicts].
- Clean-extraction attempt: INR 311.04 [D: "Clean-extraction attempt result: FAIL, pass 2 stays off" - 2026-10-20] [S: ## Experiments and verdicts].
- Stage A0 (caching): INR 36.86 (Google SKU report) [D: "Stage A0 results" - 2026-10-26].
- Cache + schema probe: INR 0.21 [D: "Cache + schema + low-thinking probe: PASS" - 2026-10-27].
- Stage A1 (scope check): INR 136.16 (tool) [D: "Stage A1 results: FAIL" - 2026-10-28].
- Vertex smoke attempt 2: INR 0.24 list price / INR 1.11 charged across both attempts [D: "Vertex smoke attempt 2 result, billing check, housekeeping" - 2026-11-06].
- 3.8 Screen (both attempts, including void arm 2): INR 842.86 billed [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09].
- Full no-regression check: INR 4,111.48 billed (under INR 6,403.3 cap; INR 3,542.75 counted audit calls at list price, difference reflects structurer and grounding calls) [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09] [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09].
- Total eval spend on GCP Free Credit since 2026-11-02: INR 4,955.45 (credit balance INR 28,693.88 -> 23,738.43 on 2026-11-09 at 15:37 IST) [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09].

### Credits and Expiry
- GCP Free Credit: INR 28,693.88 as of 2026-11-02; INR 28,692.77 on 2026-11-05; INR 27,849.91 on 2026-11-07; INR 23,738.43 on 2026-11-09 at 15:37 IST; expires 2026-11-26; applies only to Vertex AI, not Gemini Developer API (AI Studio) [D: "Funding source and model plan for the next auditor tests" - 2026-11-02] [D: "Vertex smoke attempt 2 result, billing check, housekeeping" - 2026-11-06] [D: "Billing check: screen and full-check spend on the GCP Free Credit" - 2026-11-09].
- Google Developer Program monthly credit (Google AI Pro): ~INR 955-960 per grant around 13th of each month; INR 160.94 left on 2026-11-02 [D: "Funding source and model plan for the next auditor tests" - 2026-11-02].
- Prepay balance: INR 341.81 as of 2026-11-02 [D: "Funding source and model plan for the next auditor tests" - 2026-11-02].
- Year-to-date Gemini API usage: INR 7,513.22 list price; INR 981.51 net of credits as of 2026-11-02 [D: "Funding source and model plan for the next auditor tests" - 2026-11-02].

### Billing Paths per Use
- Product / dev: Google AI Studio API key [D: "Funding source and model plan for the next auditor tests" - 2026-11-02].
- Eval and experiments: Vertex AI (`--backend vertex`, project `gen-lang-client-0520352487`, location `global`), billed to GCP Free Credit [D: "Funding source and model plan for the next auditor tests" - 2026-11-02] [D: "Pre-registration: gemini-3.8-flash auditor screen on Vertex AI" - 2026-11-06].

### Known Future Price Changes and Reserves
- Known price change: Gemini Flash prices ($0.75 in / $3.75 out per 1M tokens through 2026-12-31) double on 2027-01-01, about INR 87 -> 174 per paper, which is above the INR 130 cost gate; the release-bar restatement at the end of the auditor phase must cover the cost gate too [D: "Cost caps, run procedure and marks for the dev baseline" - 2026-10-11] [D: "Auditor redesign agreed: caching + scope check, marks and caps" - 2026-10-22] [D: "Auditor v2 (D6+D7): design, T1/T2 marks and Needs-review scoring" - 2026-10-28] [D: "Funding source and model plan for the next auditor tests" - 2026-11-02].
- Sealed reserve: INR 300, untouched throughout all pushes [D: "Experiment 1 pre-registration (auditor thinking_level=high)" - 2026-10-12] [D: "Funding source and model plan for the next auditor tests" - 2026-11-02] [S: ## Budget status].

---

## 9. Failure analysis on record

### The 10 Auditor Misses by Failure Type

*Sources: [D: "10-miss analysis: failure types and scope" - 2026-11-02] [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22] [D: "T2-R result: FAIL (4/10 misses, 2/5 hard, 0 false rejections)" - 2026-10-31]*

| Row ID | Group | Status | Detail / Description |
|---|---|---|---|
| P1-R1 | Type A (Table number breaks claim) | Targeted (Stability group) | Fixed by code in T2-R; caught in Exp 1 high thinking; consistency issue |
| P4-R1 | Type A (Table number breaks claim) | Targeted (Stability group) | Fixed by code in T2-R; caught in A1 scope check; numbers break claim |
| P4-R2 | Type B (Claim wider than cited table) | Targeted (Ability group) | Comparison absent from whole paper; fixed in T2-R only via hand check of absence |
| P11-R2 | Type B (Claim wider than cited table) | Targeted (Ability group) | KD compared only under Pro->Qwen; fixed in T2-R only via hand check of absence |
| P3-R2 | Type B (Claim wider than cited table) | Targeted (Ability group) | Breaking member sits in another table; resulted in Needs review in T2-R |
| P5-R2 | Type C (Claim meaning) | Parked (Ability group) | Counts hold; failure is a semantic duplicate; matches S row P5-S1; moved to extraction phase |
| P6-R2 | Type C (Claim meaning) | Targeted (Ability group) | Qualitative scope; "twelve VLMs" refers to main evaluation; no form in T2-R |
| P7-R1 | Type D (Prose caveat elsewhere) | Targeted (Stability group) | One pair in §7; caught in A1 scope check; prose caveat |
| P8-R2 | Type D (Prose caveat elsewhere) | Targeted (Stability group) | Appendix A.6 causal caveat; caught in Exp 1 high thinking; consistency issue |
| P5-R1 | Type E (Figure-only evidence) | Parked (Stability group) | Evidence is in Fig. 11 curve data not in text; parked from text-auditor phase |

*Stability group summary:* 5 rows (P1-R1, P4-R1, P5-R1, P7-R1, P8-R2) were PS in >= 2 of 3 repeats under earlier LLM setups; problem is consistency [D: "10-miss analysis: failure types and scope" - 2026-11-02].  
*Ability group summary:* 5 rows (P3-R2, P4-R2, P5-R2, P6-R2, P11-R2) never achieved PS in >= 2 of 3 repeats in any LLM run [D: "10-miss analysis: failure types and scope" - 2026-11-02].

### The 13 Extraction Misses
- 13 dev refusal-family rows omitted by the extractor in Run 1: P1-R2, P2-R1, P2-R3, P2-R4, P3-R1, P4-R3, P5-R3, P7-R2, P8-R3, P9-R1, P11-R1, P11-R3, P12-R1 [D: "Experiment 2 (redesigned) pre-registration - few-shot repair (claim-shape pairs)" - 2026-10-13] [D: "Experiment 3 c1/c6 result (AI-proposed, human-verified)" - 2026-10-16].
- 7 stable rows recovered in Exp 3 / Clean extraction: P2-R3, P2-R4, P3-R1, P5-R3, P8-R3, P9-R1, P11-R3 [D: "Experiment 3 c1/c6 result (AI-proposed, human-verified)" - 2026-10-16] [D: "Clean-extraction attempt revised: extraction-only marks" - 2026-10-17].
- 6 remaining hard target rows: P1-R2, P2-R1, P4-R3, P7-R2, P11-R1, P12-R1 [D: "Clean-extraction attempt amended: new pass-2 prompt + filter" - 2026-10-17].

### P1-R3 Noise Ruling
- P1-R3 was a hit in dev Run 1 but was 0/5 in replays and supported in all 9 screen folders [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].
- Ruled on 2026-10-22 and confirmed 2026-11-07/08 as documented run-to-run noise, excluded from screen and full-check totals [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22] [D: "Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex" - 2026-11-08].

### Recorded Lessons from the Auditor Phase
- Model swap strictness vs judgment: Upgrading to gemini-3.8-flash increased target fixes but simultaneously increased false rejections on supported claims; additional thinking widened both effects (C2 fixed 4 misses but created 7 false rejections and lowered golden positives to 10/21) — the gain came from indiscriminate strictness rather than improved judgment [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- Table reading vs claim meaning: Code checks on reference tables are precise but narrow; the hardest misses stem from what a claim means and covers (scope, semantic duplicates, multiple interpretations) rather than table reading mechanics [D: "T2-R result: FAIL (4/10 misses, 2/5 hard, 0 false rejections)" - 2026-10-31].
- Scope-checking LLMs repeat summary bias: Scope checkers and auditors naturally accept author summary framing and bold averages rather than examining individual table rows [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22] [D: "A1 diagnosis results: Ship-honest (decisions.md option B)" - 2026-10-28].

---

## 10. Open decisions and recorded ideas

### Decided as Next
- Write the Prism report (`docs/PRISM_REPORT.md`) and the pipeline diagram [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- Auditor and extraction work continue without new hand labelling; the next approach will be chosen after the report and pre-registered on its own [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].

### Recorded Ideas (Not Decided)
- Graded severity score with a cut-off instead of three fixed categorical labels [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- Two-auditor agreement required before flagging an overclaim [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- Sentence-ID citing (splitting paper into numbered sentences and citing IDs instead of quoting text) [D: "2026-10-05 - Grounding Stage-1 text normalisation" - 2026-10-05].
- Claim-meaning auditing, extraction phase work on the 13 misses, and code checks as a precision add-on [D: "T2-R result: FAIL (4/10 misses, 2/5 hard, 0 false rejections)" - 2026-10-31].
- Claim-scope decision: headline claims only vs whole-paper claims, to be evaluated on a new sealed set [R: ## Roadmap] [D: "Clean-extraction attempt: K6/K7 labelling method, caching dropped, K4 path" - 2026-10-19].
- Parked K7 filter fix: drop as "same" only if candidate adds no new number/content word, never resolve "same" against a dropped neighbor, validate neighbor ids, add id to filter response [R: ## Roadmap] [S: ## Extraction findings (2026-10-20)] [D: "K1 diagnostics and filter status (exploratory)" - 2026-10-20].

### Forbidden Actions Until Core Works
- Ship-honest fallback is removed and forbidden: Prism does not release with the current auditor [D: "Auditor v2 T1 result, Ship-honest removed, new order (T2-R first)" - 2026-10-29].
- Never tune prompts to move numbers or lower thresholds to pass [S: ## Working rules] [D: "Release targets, order of work and stop rule amended" - 2026-10-10].
- Never open or commit held-out text in chat or committed notes (counts only) [S: ## Working rules] [D: "Held-out eval paper sealed (eval chain step 1)" - 2026-10-03].
- Never release below the release floor (dev >= 22/31 refusal-family, false rejections <= 8/88, stable under no-regression rule) [R: ## Status — 2026-10-21] [D: "Auditor redesign agreed: caching + scope check, marks and caps" - 2026-10-22].
- Never build MCP v1 until REST API is refactored, extractor omission gap is closed, and proof pack is ready [D: "MCP v1 scope and tenancy decisions (design intent only)" - 2026-09-28].

---

## 11. Conflicts between sources

| Fact | decisions.md says | PRISM_STATUS.md / README.md says | Value used | Source |
|---|---|---|---|---|
| Auditor thinking tokens | Unset medium ~2,279 thought tokens; high ~3,481 (+53%) in Exp 1 | README says "thinking left at the Gemini 3.6 Flash default" | decisions.md values (unset ~2,279, high ~3,481) | [D: "Experiment 1 Stage A - amendment after control arm, before any high output" - 2026-10-12] [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22] [R: ## Cost] |
| Auditor input token share | Partial shares measured at ~90-91% (auditor+grounding) and ~96% (auditor+structurer); 75% was an unmeasured estimate | README says "about 75% of total input tokens" | ~90-96% measured partial share; note 75% was earlier estimate | [D: "Auditor phase diagnostic (INR 0)" - 2026-10-22] [D: "Corrections" - 2026-10-22] [R: ## Cost] |
| Dev false rejections | 4/88 effective (draft resolved 2026-10-22: weak P5 match confirmed not a match; confirmed in Stage B baseline 2026-10-28) | README:17 leaves blank ("draft figure, not a final adjudicated count"); PRISM_STATUS:17 reports 4/88 S rows | 4/88 effective | [D: "Corrections" - 2026-10-22] [D: "Stage A1 marks and cap re-confirmed" - 2026-10-28] [S: ## Scoreboard] [R: ## Results] |
| Ship-honest fallback | Removed 2026-10-29 ("Prism does not release with the current auditor"); no release with current auditor | PRISM_STATUS:5, 83 notes Ship-honest was removed 2026-10-29; README:90 still refers to fallback "otherwise ship with honest numbers" | Ship-honest removed; no release with current auditor | [D: "Auditor v2 T1 result, Ship-honest removed, new order (T2-R first)" - 2026-10-29] [S: ## Current state] [R: ## Roadmap] |
| Next step / Roadmap | Auditor phase finished 3.8 screen (void) and full check (FAIL on 2026-11-09); next is report and diagram, then next approach | PRISM_STATUS (dated 2026-10-31): Step P and T2-R done; next analyze 10 misses. README (dated 2026-10-21): Step 4/5 done | Full check FAILED 2026-11-09; next is report + diagram, then new approach | [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09] [S: ## Next steps (build order)] [R: ## Roadmap] |
| Dev run-1 positive hits | Left blank in README table; not adjudicated in Run 1 | PRISM_STATUS:15 leaves blank; README:17 leaves blank | Blank / Not adjudicated | [R: ## Results] [S: ## Scoreboard] [D: "Dev run 1 - fixture dump and pre-registered adjudication rules" - 2026-10-12] |
| Grounding role on audit labels | Grounding never changes or lowers stored audit label (`label`); sets `grounding_status.missing` (boolean) and `stance`; Postgres GENERATED column `effective_status` combines them for display (`CASE WHEN g.missing THEN 'not_in_paper' ELSE a.verdict END`); eval scorer counts `by_grounding` before label | README:40 states grounding "can veto the auditor's label, never override it upward" | decisions.md (grounding never modifies stored audit label; PostgreSQL `effective_status` handles display layer; eval scorer checks `by_grounding` before label) | [D: "Glossary"] [D: "Grounding aggregator: stance-aware labeling" - 2026-09-05] [D: "effective_status: Postgres GENERATED ALWAYS AS (...) STORED column" - 2026-09-20] [R: ## How it works] |
| RAG chunking and embedding configuration | decisions.md records 6000/1500 chars for Exp 3 extraction windows, no RAG chunking parameters; README names "fastembed" without chunk size or embedding model id | Code specifies `RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)`, embedding model `BAAI/bge-small-en-v1.5`, and collection `prism_docs` | Current code values from RAGService.py | [C: Prism.PythonService/RAGService.py:5, 9, 17, 21, 38, 58-63] [R: ## Tech stack] |

---

## 12. UNSOURCED and expected-but-not-found

### (a) UNSOURCED Items by Section
- **Section 1 (What Prism is):** Customer-facing Entra External ID sign-in status in local Aspire setup — UNSOURCED (no source states current local status).
- **Section 3 (Models):** Grounding fallback model in-code default — UNSOURCED (no default defined in [C: Prism.PythonService/config.py:65]).
- **Section 3 (Models):** Alternative embedding models tested or rejected — UNSOURCED.
- **Section 4.3 (Embed):** Alternative embedding methods tested or rejected — UNSOURCED.
- **Section 4.3 (Embed):** Open issues on record for embedding — UNSOURCED.
- **Section 5 (Eval design and rules):** Exact row count, refusal count, and S count for the future Sealed set — UNSOURCED (sealed reserve fund exists, but papers and rows are unbuilt).
- **Section 6 (Test log):** Spend for Three-call pipeline (2026-08-20) — UNSOURCED.
- **Section 6 (Test log):** Spend for Slice 2.8 (2026-08-26) — UNSOURCED.
- **Section 6 (Test log):** Spend for PR 5 Azure deploy (2026-09-01) — UNSOURCED.
- **Section 6 (Test log):** Spend for Extractor v4.1 (2026-09-03) — UNSOURCED.
- **Section 6 (Test log):** Spend for Auditor v2 (2026-09-03) — UNSOURCED.
- **Section 6 (Test log):** Spend for Auditor Model Swap (2026-09-04) — UNSOURCED.
- **Section 6 (Test log):** Spend for Azure Live Eval (2026-09-23) — UNSOURCED.
- **Section 6 (Test log):** Spend for B5.1 Auditor Checklist (2026-10-02) — UNSOURCED.
- **Section 6 (Test log):** Spend for Grounding Stage-1 Normalization (2026-10-05) — UNSOURCED.
- **Section 6 (Test log):** Spend for De-leak PR-B (2026-10-07) — UNSOURCED.
- **Section 6 (Test log):** Spend for PR-1 (2026-10-08) — UNSOURCED.
- **Section 7 (Current scores):** Dev baseline positive hits count — UNSOURCED (unadjudicated draft).
- **Section 15 (Engineering state):** Other CI checks (linters, formatters, frontend build workflows) and unrecorded branch/repo status — UNSOURCED.
- **Section 15 (Engineering state):** Git tags and branches not found in source files (`auditor-no-regression-rule`, `t1-pins-frozen`, `auditor-t2r-marks`) — UNSOURCED.

### (b) Expected Checklist Items from Phase 1 Not Found in the Three Files
- All 21 items in the Phase 1 coverage checklist were located and cited in the source files:
  - Azure deployment and its decommission: located in decisions.md (2026-09-01, 2026-09-28), PRISM_STATUS.md, README.md.
  - Service Bus swap revert: located in decisions.md (2026-09-01).
  - Golden eval with de-leaked prompts: located in decisions.md (2026-10-05, 2026-10-07), PRISM_STATUS.md, README.md.
  - Held-out runs: located in decisions.md (2026-10-03, 2026-10-05, 2026-10-07), PRISM_STATUS.md, README.md.
  - Dev baseline run 1: located in decisions.md (2026-10-11, 2026-10-12), PRISM_STATUS.md, README.md.
  - Extraction experiments in PR #122: located in PRISM_STATUS.md, decisions.md, README.md.
  - Auditor no-regression rule: located in decisions.md (2026-10-28), PRISM_STATUS.md.
  - Stage A1 scope checker: located in decisions.md (2026-10-28), PRISM_STATUS.md.
  - Auditor v2 entry: located in decisions.md (2026-10-28), PRISM_STATUS.md.
  - T1 PDF table extraction: located in decisions.md (2026-10-29), PRISM_STATUS.md.
  - Ship-honest removal: located in decisions.md (2026-10-29), PRISM_STATUS.md.
  - T2-R inputs and T2-R run: located in decisions.md (2026-10-30, 2026-10-31), PRISM_STATUS.md.
  - 10-miss analysis by failure type: located in decisions.md (2026-11-02).
  - Caching / scope-check branch: located in PRISM_STATUS.md, decisions.md (2026-10-22, 2026-10-26, 2026-10-28).
  - Vertex eval backend and smoke attempts: located in decisions.md (2026-11-02, 2026-11-04, 2026-11-06).
  - gemini-3.8-flash screen (VOID): located in decisions.md (2026-11-06, 2026-11-07).
  - Full 3-run no-regression check: located in decisions.md (2026-11-08, 2026-11-09).
  - Release bar restatement: located in decisions.md (2026-10-22), PRISM_STATUS.md, README.md.
  - Cost gate per paper: located in decisions.md (2026-10-15, 2026-11-08).
  - P1-R3 run-to-run noise ruling: located in decisions.md (2026-10-22, 2026-11-08).
  - 2026-11-09 decision on next approach: located in decisions.md (2026-11-09).

---

## 13. Entry index

*Every heading in `docs/decisions.md` is indexed below in chronological order (oldest first).*

| Heading in decisions.md | Date | Sections Citing or Reason Not Used |
|---|---|---|
| RabbitMQ topology: main_prism_queue + DLX + DLQ | 2026-08-02 | Cited in Section 2 |
| create_db_connection_pool shared via memory_db.py | 2026-08-04 | not used: Internal database connection pool helper implementation detail |
| Aspire "type": "aspire" launch.json | 2026-08-05 | not used: Local IDE launch configuration detail |
| Two-layer Pydantic schema (LLM vs Final) | 2026-08-06 | not used: Architecture pattern superseded by specific stage schemas |
| SignalR broadcast via chat-scoped Groups | 2026-08-06 | not used: Real-time SignalR group design superseded by Slice 2+2.5 |
| Prompt content in versioned files, not database | 2026-08-07 | not used: Prompt storage design principle |
| Grounding: two-stage RapidFuzz + LLM audit | 2026-08-07 | Cited in Section 4.7 |
| EvidenceSpan section tracking | 2026-08-07 | not used: Internal evidence span model field detail |
| Fewshot JSON envelope wrapping | 2026-08-07 | not used: Prompt formatting implementation detail |
| Two-prompt extraction (metadata + claims) with shared engine helper | 2026-08-08 | Cited in Section 4.5 |
| Single-domain hardcode for MVP | 2026-08-09 | not used: MVP domain scope constraint |
| Domain seed via EF Core HasData | 2026-08-09 | Cited in Section 4.8 |
| psycopg3 async as the Python Postgres driver | 2026-08-09 | Cited in Section 4.8 |
| Grounding audit uses 200-char paper context window | 2026-08-09 | not used: Superseded by Slice 2.8 context widening |
| Tool routing convention | 2026-08-10 | not used: Developer tooling preference (Claude chat vs Claude Code vs Antigravity) |
| Job-atomic message processing with retry cap | 2026-08-10 | not used: RabbitMQ worker retry policy detail |
| Deterministic uuid5 chunk IDs in Qdrant with delete-then-insert | 2026-08-10 | Cited in Section 4.2, 4.4 |
| Eval harness design — baked-in fixes for six known failure modes | 2026-08-11 | not used: Early eval design superseded by later scorer revisions |
| Baseline correct-refusal rate: expected low | 2026-08-11 | not used: Historical baseline expectation superseded by frozen sets |
| Positive-hit floor lowered from 15 to 10 | 2026-08-13 | not used: Early metric threshold adjustment superseded by de-leaked gates |
| Freeze matcher output into fixtures | 2026-08-13 | Cited in Section 15 |
| Three-call claim extraction pipeline | 2026-08-20 | Cited in Section 3, 4.5, 4.6, 6 |
| Tier 2 (Verdict view) and Tier 3 (Overstated Claims + Questions to Scrutinize) collapsed into paper-scoped chat | 2026-08-22 | Cited in Section 1 |
| One paper per chat, enforced at upload endpoint | 2026-08-22 | Cited in Section 1 |
| AddPositionToPaperClaims — explicit sort column instead of timestamp | 2026-08-22 | not used: Database schema migration detail |
| EF Core enum ↔ string mapping via dedicated ValueConverter classes | 2026-08-22 | Cited in Section 4.8 |
| HasJsonPropertyName for jsonb owned-entity snake_case mapping | 2026-08-22 | Cited in Section 4.8 |
| Slice 2 + 2.5: Ingestion Progress Events & PaperActivityView UI | 2026-08-23 | Cited in Section 1 |
| AnimatePresence popLayout Fix for PaperActivityView | 2026-08-23 | not used: Frontend UI animation bug fix |
| Postgres Container Password Drift Workaround | 2026-08-23 | Cited in Section 1, 4.8 |
| Slice 3a Bug Fixes: FTS fallback, check_empty OR logic, router tool bypass | 2026-08-25 | Cited in Section 1 |
| Slice 3a: paper-scoped LangGraph chat agent, SSE transport, block output | 2026-08-25 | Cited in Section 1 |
| Slice 2.8: Grounding pipeline context widening & 3-tier rubric | 2026-08-26 | Cited in Section 4.7, 5, 6 |
| Slice 3b.1 + 3b.2: Chat Polish & Density Cleanup | 2026-08-26 | Cited in Section 1 |
| Slice 3b: Chat Strip UI in Matrix View | 2026-08-26 | Cited in Section 1 |
| Hybrid Gemini paid Tier 1 + Groq audit | 2026-08-27 | Cited in Section 3 |
| Reasoning-first schema pattern for span audit | 2026-08-27 | not used: Early grounding schema prompt pattern |
| Slice 2.8 baseline — coverage-vs-refusal trade-off | 2026-08-27 | Cited in Section 6 |
| LiteLLM provider abstraction for span audit call | 2026-08-27 | Cited in Section 3 |
| Azure pre-deploy foundation (PR 1) | 2026-08-29 | Cited in Section 15 |
| Slice 3c: legacy chat deletion | 2026-08-30 | Cited in Section 1 |
| First Azure deploy (PR 5) | 2026-09-01 | not used: Heading variant of "First Azure deploy" |
| Managed vs self-hosted service split (PR 5) | 2026-09-01 | not used: Heading variant of "Managed vs self-hosted service split" |
| First Azure deploy | 2026-09-01 | Cited in Section 2, 6, 15 |
| Managed vs self-hosted service split | 2026-09-01 | Cited in Section 2, 4.4 |
| PR 5 code port verification + reactUI JS app migration | 2026-09-02 | Cited in Section 2, 15 |
| Extractor prompt v4.1 — trap-claim recall + eval row enrichment | 2026-09-03 | Cited in Section 6 |
| Auditor prompt v2 — trap-claim labeling | 2026-09-03 | Cited in Section 4.6, 6 |
| Auditor model swap + eval matcher calibration | 2026-09-04 | Cited in Section 3, 4.1, 4.6, 6 |
| Grounding aggregator: stance-aware labeling | 2026-09-05 | Cited in Section 4.7, 11 |
| Grounding checker: verdict-aware rubric + reason string fix | 2026-09-05 | Cited in Section 4.7 |
| Scoped reversal: wire matcher gold-set test into CI with a guarded AI_API_KEY secret | 2026-09-08 | not used: Temporary CI experiment superseded by frozen-fixture revert |
| Revert live-matcher CI back to frozen-fixture design | 2026-09-09 | Cited in Section 15 |
| Chat: refusal-query routing and claim-count limit fixes | 2026-09-10 | not used: Chat query routing and limit adjustments |
| Chat: citation rendering structural reconstruction | 2026-09-10 | not used: Chat markdown citation rendering reconstruction |
| Auditor: scope-checking added | 2026-09-10 | not used: Early auditor scope-checking prompt tightening |
| Extraction: positioning claims captured and ceiling raised | 2026-09-10 | Cited in Section 4.5 |
| Matcher gold-set verification moved to frozen-fixture pattern | 2026-09-10 | not used: Re-confirmation of frozen-fixture matcher calibration |
| Eval integrity: SKIPPED status for transient failures | 2026-09-10 | not used: Scorer transient failure exclusion definition |
| Entra External ID (CIAM) | 2026-09-15/16 | Cited in Section 1 |
| MapInboundClaims fix | 2026-09-15/16 | not used: JWT claim mapping bug fix |
| oid vs sub decision | 2026-09-15/16 | Cited in Section 1 |
| apiClient.ts abstraction | 2026-09-15/16 | not used: Frontend API client auth token attachment abstraction |
| Re-run UI removed | 2026-09-15/16 | not used: UI re-run element removal |
| Known gap: Google IdP name/email claims empty | 2026-09-15/16 | Cited in Section 1 |
| Known gap: extraction auto-retry failure state | 2026-09-15/16 | Cited in Section 1 |
| ExtractionStatus Cache-Hit Fix | 2026-09-17 | Cited in Section 1 |
| effective_status: Postgres GENERATED ALWAYS AS (...) STORED column | 2026-09-20 | Cited in Section 1, 2, 4.7, 4.8, 11 |
| Known gap: Router non-determinism | 2026-09-20 | Cited in Section 1 |
| Known gap: generate_response hallucination on claim status | 2026-09-20 | Cited in Section 1 |
| Known gap: Bug 4 (tab-switch/streaming state loss) | 2026-09-20 | Cited in Section 1 |
| Missing Claims Data (Local Dev Hazard) | 2026-09-20 | Cited in Section 1 |
| Resolved: aborted chat leaves an orphaned unanswered question | 2026-09-20 | not used: Background task disconnect decoupling bug fix |
| Known gap: streaming top-anchor effect doesn't reliably fire | 2026-09-21 | Cited in Section 1 |
| First two valid live eval runs against Azure Postgres | 2026-09-23 | Cited in Section 6 |
| Chat: Paper-scoped chat stream ownership moved to MatrixView | 2026-09-26 | not used: React chat stream state lift to MatrixView |
| Cache chat file and completed-paper claims per session | 2026-09-26 | not used: Client-side session claim cache implementation |
| Google IdP Name/Email Claims Resolution | 2026-09-27 | Cited in Section 1 |
| Live environment decommissioned | 2026-09-28 | Cited in Section 1, 2 |
| Cost and observability discovery findings | 2026-09-28 | not used: Pre-audit discovery review of cost and telemetry gaps |
| MCP v1 scope and tenancy decisions (design intent only) | 2026-09-28 | Cited in Section 10 |
| Demo strategy while offline | 2026-09-28 | Cited in Section 1 |
| Correction: AUDIT_CONCURRENCY is 1, not 10 | 2026-09-29 | Cited in Section 2, 3, 4.6, 4.7 |
| Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map | 2026-09-30 | Cited in Section 4.7, 5, 6, 15 |
| Four-bucket scorer replaces omission-credit PASS/FAIL | 2026-10-01 | not used: Companion entry to the 2026-09-30 scorer fix |
| Match-map adjudication gate, fingerprint-keyed | 2026-10-01 | not used: Match-map gating specification details |
| 12 golden-eval corrections after hand-auditing all 3 papers | 2026-10-01 | Cited in Section 5 |
| Golden-key corrections | 2026-10-02 | Cited in Section 15 |
| B5.1 auditor checklist - measured, not merged | 2026-10-02 | Cited in Section 4.1, 4.6, 4.7, 6, 15 |
| Held-out baseline (eval chain step 2) | 2026-10-03 | Cited in Section 6 |
| Held-out eval paper sealed (eval chain step 1) | 2026-10-03 | Cited in Section 4.1, 5, 10 |
| Eval chain first; prompt leakage found; gate-port dropped | 2026-10-03 | Cited in Section 4.1 |
| 2026-10-03 - Eval chain step 0: matrix_eval positive rows re-checked | 2026-10-03 | Cited in Section 5 |
| 2026-10-05 - Grounding Stage-1 text normalisation | 2026-10-05 | Cited in Section 4.1, 4.7, 6, 10 |
| De-leak: eval-paper text and answer-key wording removed from prompts | 2026-10-05 | Cited in Section 5, 6, 7, 15 |
| prompt_loader few-shot "note" field bug | 2026-10-06 | Cited in Section 4.5 |
| reflexion.pdf stuck rows (DB/RabbitMQ publish sequence) | 2026-10-06 | Cited in Section 4.8 |
| Infra findings from PR-B, not fixed | 2026-10-07 | not used: PR-B operational infrastructure findings |
| Direction: improve extractor before shipping | 2026-10-07 | not used: Roadmap sequencing decision |
| Audit routing: read-only audits in Claude Code plan mode | 2026-10-08 | not used: Agent workflow routing preference |
| PR-1 result (negative): few-shot loader fix, no coverage gain | 2026-10-08 | Cited in Section 4.5, 6, 15 |
| Section-by-section extraction: feasibility confirmed, then PARKED | 2026-10-08 | Cited in Section 4.5, 6 |
| Failure map of the frozen official run | 2026-10-08 | not used: Early failure classification of golden run |
| Measurement facts from the audits | 2026-10-08 | not used: Read-only audit observations |
| Golden label quality | 2026-10-08 | not used: Golden label assessment note |
| Plan and stop rule | 2026-10-08 | not used: Superseded by amended stop rules |
| Clarifications to the 2026-10-08 plan | 2026-10-08 | not used: Procedural plan clarifications |
| Design review of auditor and extractor fixes | 2026-10-08 | not used: Design discussion notes |
| COT-M08 mapping check | 2026-10-08 | not used: Single-row mapping diagnosis |
| Next-step decision: label first, then measure, extractor first if forced | 2026-10-08 | not used: Interim sequencing priority decision |
| Status confirmation | 2026-10-08 | not used: Working status checkpoint |
| Label rubric frozen | 2026-10-10 | Cited in Section 5 |
| Dev set size rule amended | 2026-10-10 | not used: Dev set minimum size rule amendment |
| Release targets, order of work and stop rule amended | 2026-10-10 | Cited in Section 5, 10 |
| Dev set frozen | 2026-10-11 | Cited in Section 5 |
| Cost caps, run procedure and marks for the dev baseline | 2026-10-11 | Cited in Section 5, 8 |
| Baseline run 1 paused at 4 of 12; diagnose before spend | 2026-10-11 | Cited in Section 6, 8 |
| Dev run 1 - fixture dump and pre-registered adjudication rules | 2026-10-12 | Cited in Section 5, 6, 7, 11 |
| Experiment 1 pre-registration (auditor thinking_level=high) | 2026-10-12 | Cited in Section 5, 8 |
| Experiment 1 Stage A - amendment after control arm, before any high output | 2026-10-12 | Cited in Section 6, 11 |
| Experiment 1 result - Stage A FAIL, rejected | 2026-10-12 | Cited in Section 4.6, 6, 7, 8 |
| Experiment 2 (redesigned) pre-registration - few-shot repair (claim-shape pairs) | 2026-10-13 | Cited in Section 9 |
| Experiment 2 - Stage A result | 2026-10-14 | Cited in Section 4.5, 6, 8 |
| Push extension past Experiment 2 | 2026-10-14 | not used: Push budget extension authorization |
| Experiment 3 pre-checks result | 2026-10-14 | Cited in Section 4.1, 4.2, 6 |
| Backfill: records missing from this log | 2026-10-15 | Cited in Section 4.6, 6, 15 |
| Experiment 3 B1 review | 2026-10-15 | Cited in Section 5, 7, 8 |
| Experiment 3 build | 2026-10-15 | not used: Implementation build notes for pass 2 |
| B3 Phase 0 discovery: script-run deviations and correction | 2026-10-15 | not used: Pre-run script discovery observations |
| Experiment 3 pre-registration | 2026-10-15 | Cited in Section 5 |
| B3 budget reconciliation | 2026-10-15 | not used: Experiment 3 budget cap reconciliation details |
| Experiment 3 amendment 1 | 2026-10-15 | Cited in Section 6 |
| Experiment 3 amendment 2 (Rule (b) definition) | 2026-10-15 | not used: Stop rule (b) formula amendment |
| Experiment 3 pilot 2 result and Phase 4 cap | 2026-10-15 | Cited in Section 6 |
| Experiment 3 amendment 3 (Incomplete-paper rule) | 2026-10-15 | not used: Incomplete paper re-run procedure rule |
| Experiment 3 pass2_r1 result | 2026-10-15 | Cited in Section 6 |
| Experiment 3 pass2_r2 result | 2026-10-16 | Cited in Section 6 |
| Experiment 3 B4 method | 2026-10-16 | not used: Scorer procedure description for B4 |
| Experiment 3 B4 scorer fix | 2026-10-16 | not used: Bug fix in Exp 3 scoring script |
| Experiment 3 B4 result | 2026-10-16 | Cited in Section 4.2, 4.5, 5, 6, 8 |
| Experiment 3 c1/c6 result (AI-proposed, human-verified) | 2026-10-16 | Cited in Section 6, 9 |
| Clean-extraction attempt, supersedes 2026-10-10 exit rule | 2026-10-16 | not used: Exit rule amendment superseding 2026-10-10 |
| Clean-extraction attempt revised: extraction-only marks | 2026-10-17 | Cited in Section 9 |
| Clean-extraction attempt amended: new pass-2 prompt + filter | 2026-10-17 | Cited in Section 9 |
| Claim definition revised: limitations are evidence, not claims | 2026-10-17 | not used: Rubric clarification on limitations |
| Claim boundary rule (revised): "could it be wrong?" | 2026-10-18 | not used: Rubric clarification on claim boundaries |
| Pass-2 keep/drop rule for the 2610.10590v1 comparison | 2026-10-18 | not used: Single-paper comparison evaluation rule |
| Answer-key labelling and Phase B method for 2610.10590v1 | 2026-10-18 | not used: Single-paper labelling procedure |
| Pass-2 comparison result for 2610.10590v1: KEEP | 2026-10-18 | Cited in Section 6 |
| Clean-extraction attempt: K6/K7 labelling method, caching dropped, K4 path | 2026-10-19 | Cited in Section 10 |
| Clean-extraction full runs: settings and run plan | 2026-10-19 | Cited in Section 5 |
| Clean-extraction attempt: spot-check result, diagnostic, bounded scoring | 2026-10-20 | Cited in Section 5 |
| Clean-extraction attempt result: FAIL, pass 2 stays off | 2026-10-20 | Cited in Section 4.5, 6, 8, 15 |
| K1 diagnostics and filter status (exploratory) | 2026-10-20 | Cited in Section 10 |
| Auditor phase diagnostic (INR 0) | 2026-10-22 | Cited in Section 4.1, 4.6, 4.7, 9, 11 |
| Auditor redesign agreed: caching + scope check, marks and caps | 2026-10-22 | Cited in Section 4.6, 5, 7, 8, 10 |
| Corrections | 2026-10-22 | Cited in Section 7, 11 |
| Stage A0 marks and cap re-confirmed | 2026-10-24 | not used: Procedural re-confirmation of Stage A0 caps |
| Stage A0 results | 2026-10-26 | Cited in Section 3, 6, 8 |
| S-row match map written; cost-tool fix recorded | 2026-10-27 | Cited in Section 5 |
| Cache + schema + low-thinking probe | 2026-10-27 | not used: Probe pre-registration entry |
| Cache + schema + low-thinking probe: PASS | 2026-10-27 | Cited in Section 6, 8 |
| Stage A1 marks and cap re-confirmed | 2026-10-28 | Cited in Section 5, 11 |
| Stage A1 results: FAIL | 2026-10-28 | Cited in Section 4.6, 5, 6, 8 |
| A1 diagnosis plan and reading rule | 2026-10-28 | not used: Diagnostic inspection procedure and reading rules |
| A1 diagnosis results: Ship-honest (decisions.md option B) | 2026-10-28 | Cited in Section 6, 7, 9 |
| Auditor no-regression rule | 2026-10-28 | Cited in Section 5, 7 |
| Auditor v2 (D6+D7): design, T1/T2 marks and Needs-review scoring | 2026-10-28 | Cited in Section 5, 8 |
| Auditor v2 T1 result, Ship-honest removed, new order (T2-R first) | 2026-10-29 | Cited in Section 4.1, 4.6, 6, 10, 11 |
| T2-R inputs: form policies, adjudication, findings | 2026-10-30 | Cited in Section 5 |
| T2-R result: FAIL (4/10 misses, 2/5 hard, 0 false rejections) | 2026-10-31 | Cited in Section 4.6, 6, 9, 10 |
| Record: T2-R wording correction and two input notes | 2026-10-31 | Cited in Section 6, 15 |
| 10-miss analysis: failure types and scope | 2026-11-02 | Cited in Section 5, 9 |
| Funding source and model plan for the next auditor tests | 2026-11-02 | Cited in Section 3, 5, 8 |
| Vertex smoke test, attempt 1: FAIL (mechanics) | 2026-11-04 | Cited in Section 6, 15 |
| Vertex smoke attempt 2 result, billing check, housekeeping | 2026-11-06 | Cited in Section 6, 8, 15 |
| Pre-registration: gemini-3.8-flash auditor screen on Vertex AI | 2026-11-06 | Cited in Section 3, 4.7, 5, 6, 8 |
| Screen attempt 1: arm 2 void (structurer JSON crash), fix, re-run of arms 2 and 3 | 2026-11-06 | Cited in Section 6, 15 |
| Screen attempt 2: void (V3 -> V4), robustness note, decision to take gemini-3.8-flash high to the full check | 2026-11-07 | Cited in Section 3, 6 |
| Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex | 2026-11-08 | Cited in Section 3, 4.6, 4.7, 5, 6, 7, 8, 9 |
| Full no-regression check result: FAIL for both 3.8 candidates; no auditor change | 2026-11-09 | Cited in Section 3, 4.6, 5, 6, 7, 8, 9, 10, 11, 15 |
| Billing check: screen and full-check spend on the GCP Free Credit | 2026-11-09 | Cited in Section 6, 8 |
| PRISM.Web Deployment | Stray heading (undated) | not used: Stray unpopulated heading at line 1 of decisions.md |
| Deferred / Won't Do (for now) | Undated summary section | Cited in Section 4.1, 4.2, 4.4, 4.8 |
| Known Limitations | Undated summary section | Cited in Section 2 |
| Template | Undated template | not used: Structural template for decisions.md entries |

---

## 14. External research (not from the repo)

Source: Claude checked each link on 2026-11-09. Not in the repo.
- CLAIM-BENCH (2025), "Benchmarking LLMs for Accurate Scientific Claim ->
  Evidence Reasoning": annotator agreement (Cohen's kappa, 30-paper subset)
  0.66 for claims, 0.30 for evidence. https://arxiv.org/pdf/2506.08235v1
- SPOT (2025): best model o3, recall 21.1%, precision 6.1%; across 8 runs,
  models rarely find the same errors again. https://arxiv.org/abs/2505.11855
- Verification-gap survey (2026), "Autonomous Research Agents: A Survey of
  AI Scientists and the Verification Gap": argues verifiability is the
  central problem. The figure "LLM judges < 55%, weakest at evidence
  verification" was NOT found in this paper: UNVERIFIED, not for the
  report. https://arxiv.org/pdf/2608.05179
- scite (2021 paper): classifies citation statements from OTHER papers as
  supporting, disputing, or mentioning; over 800 million statements from
  over 23 million publications at the time of that paper. Newer totals:
  UNVERIFIED. https://www.biorxiv.org/content/10.1101/2021.03.15.435418.full.pdf
- PaperQA2 / ContraCrow (FutureHouse, 2024): extracts claims from a paper,
  asks PaperQA2 whether the literature contradicts each claim, scores on a
  0-10 Likert scale (8 or more = contradiction); experts agreed with about
  70% of the reviewed findings. https://arxiv.org/html/2409.13740v2
- Black Spatula (open source): prompts tested with OpenAI o1 and Claude
  3.5; about 500 papers checked; about 10% false alarms; finding expert
  checkers is the bottleneck. Secondary source (news article based on
  Nature reporting). https://heise.de/-10321469
- YesNoError: several o1 agents per paper, trained on synthetic data per
  error type, results merged by an LLM; 37,000+ papers in two months; most
  flags not yet human-reviewed. Same secondary source.
  https://heise.de/-10321469
- statcheck: recomputes p-values from reported test statistics and degrees
  of freedom (deterministic, no LLM); reads about 60% of the significance
  tests in typical psychology papers; 96.2%-99.9% accuracy at classifying
  them consistent or inconsistent (Nuijten et al., 2017). Journal use is
  not stated on this page: UNVERIFIED. https://statcheck.io/
- MiniCheck (2024): 770M Flan-T5 model reaches GPT-4-level accuracy on
  LLM-AggreFact (74.7 vs 75.3 balanced accuracy) at about 400x lower cost;
  trained on synthetic data generated with GPT-4.
  https://arxiv.org/pdf/2404.10774.pdf
- Not yet tried by Prism: graded severity + cut-off; two-auditor agreement.

## 15. Engineering state

### CI Checks
- **Hermetic, secretless CI execution:** The CI workflow (`.github/workflows/eval.yml`) runs offline without external LLM API keys or live network calls (`AI_API_KEY` removed from GitHub secrets); `matrix_runner --source fixture` and `check_fixture_freshness.py` run as deterministic local file reads [R: ## Results] [D: "Freeze matcher output into fixtures" - 2026-08-13] [D: "Revert live-matcher CI back to frozen-fixture design" - 2026-09-09].
- **Prompt leak check (`eval/check_prompt_leak.py`):** Runs in `eval.yml` before freshness verification; fails on any 8-gram shared with the 4 eval papers (Reflexion, ReAct, CoT, held-out) or eval row fields; warns on 5-grams; allowlist contains 4 permitted entries; covered by tests in `eval/tests/test_prompt_leak.py` [R: ## Evaluation method] [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05].
- **Fixture freshness check (`eval/check_fixture_freshness.py`):** Verifies that prompt bytes match fixture `prompt_hash` (`cb3272cce551`), that `matcher_fingerprint` has not drifted, and that `matcher_gold_pass_rate >= 0.90`; failures block merge and output specific remediation commands [D: "Freeze matcher output into fixtures" - 2026-08-13] [D: "Revert live-matcher CI back to frozen-fixture design" - 2026-09-09].
- **Match-map adjudication gate:** `matrix_runner.py` enforces 100% human match-map coverage; unadjudicated rows suppress the headline percentage and force exit code 1 [D: "Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map" - 2026-09-30].
- **Match-map fixture consistency (`eval/tests/test_match_map_fixture_consistency.py`):** Offline test ensuring human `match_map.json` pairings match fixture frozen actual indices [D: "Golden-key corrections" - 2026-10-02].
- **Matcher gold calibration:** 15-pair hand-authored test (`docs/evals/matcher_gold.json`), pass rate (93.3% / 100%) frozen into fixture headers offline via `eval/verify_matcher_gold.py`; live integration test in CI was reverted to prevent quota burn and secrets exposure [D: "Freeze matcher output into fixtures" - 2026-08-13] [D: "Revert live-matcher CI back to frozen-fixture design" - 2026-09-09].
- **Unit test suite:** 187 tests passed at PR-B [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05]; 1006 tests passed at commit `bc2f575` after structurer JSON parse fix [D: "Screen attempt 1: arm 2 void (structurer JSON crash), fix, re-run of arms 2 and 3" - 2026-11-06].
- **Pydantic configuration validation in CI:** Dummy environment variables configured in `eval.yml` so `PrismSettings` BaseSettings validates at process start [D: "Azure pre-deploy foundation (PR 1)" - 2026-08-29].
- **Other CI checks (linters, formatters, frontend build workflows):** UNSOURCED [not recorded in the source files].

### Branch and Merge State
- **`main` branch:** All experimental feature flags default to off or unset (`auditor_thinking_level=None`, `extractor_fewshot_fix=False`, `extractor_fewshot_shapes=False`, `extractor_second_pass=False`, `pass2_thinking_level=None`, `extractor_pass2_clean=False`); shipping extraction path is single-pass only; prompt hash confirmed `cb3272cce551` [S: ## Current state] [S: ## Flags and their defaults] [D: "Clean-extraction attempt result: FAIL, pass 2 stays off" - 2026-10-20].
- **Merged PRs on record:**
  - PR #1: Azure pre-deploy foundation merged 2026-08-29 [D: "Azure pre-deploy foundation (PR 1)" - 2026-08-29].
  - PR #5: First Azure deploy merged 2026-09-01 [D: "First Azure deploy" - 2026-09-01] [D: "PR 5 code port verification + reactUI JS app migration" - 2026-09-02].
  - PR #113 (PR-B): Prompt de-leak merged 2026-10-07 on commit `e0dd56a` [D: "De-leak: eval-paper text and answer-key wording removed from prompts" - 2026-10-05].
  - PR #122: Dev eval baseline + extraction experiments merged to `main` 2026-10-21 on commit `4be1cc4` [S: ## Current state].
- **Unmerged branches and draft PRs:**
  - PR #115 (PR-1): Few-shot loader fix, draft PR, unmerged due to hash mismatch pending fixture re-dump [D: "PR-1 result (negative): few-shot loader fix, no coverage gain" - 2026-10-08].
  - `fix/b5.1-auditor-checklist`: B5.1 auditor checklist attempt; failed marks, unmerged, preserved on tag `archive/b5.1-checklist-attempt` [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02].
  - `archive/exp1-scoped-auditor`: Exp 1 scoped-auditor pilot; failed marks, unmerged, preserved on tag `archive/exp1-scoped-auditor` [D: "Backfill: records missing from this log" - 2026-10-15] [S: ## Flags and their defaults].
  - `auditor/caching-scope-check`: Work branch pushed 2026-10-31, not merged [S: ## Current state].
  - `eval/vertex-auditor-option`: Branch for Vertex AI gemini-3.8-flash probe and smoke testing, recorded 2026-11-04 [D: "Vertex smoke test, attempt 1: FAIL (mechanics)" - 2026-11-04].
- **Pushed Git tags on record:**
  - `archive/b5.1-checklist-attempt` [D: "B5.1 auditor checklist - measured, not merged" - 2026-10-02].
  - `archive/exp1-scoped-auditor` [D: "Backfill: records missing from this log" - 2026-10-15].
  - `auditor-v2-t1t2-marks` [S: ## Next steps (build order)].
  - `t2r-inputs-frozen` [D: "Record: T2-R wording correction and two input notes" - 2026-10-31].
  - `smoke-vertex-38-2026-11-04` [D: "Vertex smoke attempt 2 result, billing check, housekeeping" - 2026-11-06].
  - `screen-vertex-38-2026-11-06` on commit `b62e6af` [D: "Screen attempt 1: arm 2 void (structurer JSON crash), fix, re-run of arms 2 and 3" - 2026-11-06].
  - `fullcheck-38-2026-11-08` on commit `49bae11` [D: "Full no-regression check result: FAIL for both 3.8 candidates; no auditor change" - 2026-11-09].
- **Other branch and repo status:** UNSOURCED [not recorded in the source files].
