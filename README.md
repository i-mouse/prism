# Prism

> **Autonomous Empirical Claim-Auditing Engine for Research Papers**

> **Status — live demo offline since 2026-09-28.** The hosted Azure environment has been decommissioned. The demo now runs locally (Aspire). Run Prism locally with the [Quick Start](#quick-start-local-dev) below. Walkthrough video: coming soon. Demo on request. Relaunch path: [Decommissioned state and relaunch](docs/RUNBOOK.md#decommissioned-state-and-relaunch).

Prism extracts empirical claims from academic papers and audits whether each claim is supported by evidence in that same paper. Unlike literature discovery tools (Elicit, Consensus, Scite) that find and summarize across papers, Prism performs a peer-reviewer's core job: auditing a single paper's headline findings against its own data and text.

## Live Demo — offline

The hosted demo ran at `https://prism-ai-reactui.nicesky-c6f0b846.centralindia.azurecontainerapps.io/` until 2026-09-28, when the Azure environment was decommissioned. That URL no longer resolves and is kept here only as a record of what was deployed. To see the product now, run it locally via the [Quick Start](#quick-start-local-dev), or ask for a demo.

While it was up, Prism could be tried directly in the browser using **Guest Access** — no account required. Guest sessions were for demo use only, so reviewers could try the product without creating an account.

> **Google Sign-In:** was fully functional at decommission — name and email claims were correctly mapped for new sign-ups and re-registrations, and legacy accounts had to re-register to see their name instead of a placeholder. The sign-in setup (Entra External ID, the Google identity provider, and the app registrations) has to be re-created before any relaunch.

Upload a paper. Prism extracts claims, audits each claim against the paper's own evidence, and presents the results in a claim-support matrix.

![Prism Claim-Support Matrix](docs/diagrams/matrix-view-edited.png)

## Evaluation

Prism's core engineering bet is correct refusal: vetoing any assessment not supported by the paper's own text.

**Golden set (3 papers, 37 rows, 16 grounding-negative), de-leaked prompts `cb3272cce551`:** refusal-family 5/16 (31%), gate 0.30; strict 5/16; wrongly affirmed 4; not extracted 7; positive hits 11/21 (floor 10); false rejection 1/21; match-map coverage 37/37.

**Held-out paper (arXiv 2609.20812v3, 12 rows):** refusal-family 1/2, positive hits 7/10, false rejections 0/10, coverage 12/12.

**Reproduce (fixture mode, no LLM/DB calls but requires environment setup):**
```powershell
cd Prism.PythonService
$env:PRISM_DB_HOST="localhost"; $env:PRISM_DB_DATABASENAME="test"
$env:PRISM_DB_USERNAME="test"; $env:PRISM_DB_PASSWORD="test"
$env:ConnectionStrings__messaging="amqp://test:test@localhost:5672/"
$env:ConnectionStrings__blobs="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=test;BlobEndpoint=http://localhost:9000;"
$env:AI_API_KEY="dummy"; $env:GROQ_API_KEY="dummy"
$env:LLM_EXTRACTION_MODEL="gemini-3.6-flash"; $env:LLM_EXTRACTION_FALLBACK_MODEL="gemini-3.1-flash-lite"
$env:LLM_CLAIM_AUDIT_MODEL="gemini-3.6-flash"; $env:LLM_CLAIM_AUDIT_FALLBACK_MODEL="gemini-3.1-flash-lite"
$env:LLM_GROUNDING_MODEL="groq/openai/gpt-oss-20b"; $env:LLM_GROUNDING_FALLBACK_MODEL="gemini/gemini-3.1-flash-lite"
$env:LLM_CHAT_MODEL="gemini-3.6-flash"; $env:LLM_ROUTER_MODEL="gemini-3.5-flash-lite"
$env:LLM_SUMMARY_MODEL="gemini-3.5-flash-lite"; $env:LLM_EVAL_MATCHER_MODEL="gemini-3.6-flash"
$env:LLM_EVAL_MATCHER_FALLBACK_MODEL="gemini-3.1-flash-lite"
uv run python -m eval.matrix_runner --source fixture
```

**Known limitations:**
- Prompts were de-leaked; the old baseline (golden 6/16, 12/21; held-out 1/2, 8/10) was measured with golden text in the prompts and is shown only as history.
- Extractor is the weakest stage (7 golden claims never extracted)
- Claim bundling: 9 held-out rows rest on 4 distinct claims (the 7 hits rest on those)
- Groq primary grounding model fails on its 512-token cap and rate limits; the Gemini fallback carries all audits
- Single runs, no variance measured yet
- Held-out refusal sample is n=2

**Notes:**
1. The old 86% refusal rate came from a scorer that credited claims never extracted; it was replaced. The old 79% refusal rate is also dead.
2. Stage-1 text normalisation (2026-10-05) fixed 20 table-row quotes that failed fuzzy matching on post-reset runs, flipping 2 golden false rejections to hits with 0 regressions; held-out unchanged; the frozen fixture numbers above are unaffected.

## Limits and honest reading

- Single runs, noise not measured; one row decides the gate.
- No detectable change from removing the prompt leak.
- The extractor is the weakest stage: it misses claims, and the auditor cannot refuse a claim it never sees.
- Maps are human-adjudicated; the matcher accuracy rate (93.3%) was carried over, not re-measured.
- Azure deployment is decommissioned; the demo is local (Aspire).

## How it works

The pipeline is orchestrated asynchronously via RabbitMQ and broken into specific stages to avoid context collapse. First, a Python worker extracts empirical and methodological positioning claims from the full text. Next, a claim auditor (Gemini 3.6 Flash) evaluates each claim individually against the full paper text to assign a label (supported, partially supported, or not supported) — tightened to require evidence from experimental results, data, or proofs, not just a verbatim quote from the Abstract or Introduction. Finally, a grounding checker validates the auditor's exact quote spans using fuzzy string matching (RapidFuzz, after quote and paper text are normalised for ligatures, line breaks, quotes/dashes, and whitespace) and a secondary LLM judge (Groq/LiteLLM), adjusting the rubric based on the quote's stance toward the claim (supports, refutes, or neutral). The pipeline is strictly acyclic: the grounder validates the auditor, but never overrides its label.

## Architecture

![Prism architecture — extraction pipeline, Azure Container Apps stack, deferred work](docs/diagrams/architecture.png)

## Tech Stack

| Layer | Technologies |
|---|---|
| **Orchestration** | .NET Aspire 13.4 |
| **API Gateway** | ASP.NET Core (.NET 10), EF Core 10 |
| **Worker & Agent** | Python 3.13 (`uv`), FastAPI, LangGraph |
| **LLMs** | Gemini 3.6 Flash, Gemini 3.5 Flash Lite, Gemini 3.1 Flash Lite, Groq (gpt-oss-20b) |
| **Vector & Search** | Qdrant 1.18, fastembed (BAAI/bge-small-en-v1.5) |
| **Data & Messaging**| PostgreSQL 18, RabbitMQ 4.3, Azure Blob Storage (Azurite locally) |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS |

## Quick Start (Local Dev)

**Prerequisites:** .NET 10 SDK, Docker Desktop, `uv`, Node.js 20+, Google Gemini API Key, Groq API Key.

1. Set keys in .NET user-secrets:
```powershell
cd Prism.AppHost
dotnet user-secrets set "Parameters:GoogleApiKey" "your_key"
dotnet user-secrets set "Parameters:GroqApiKey"   "your_key"
dotnet user-secrets set "Parameters:rabbitmquser" "admin"
dotnet user-secrets set "Parameters:rabbitmqpass" "any-strong-string"
dotnet user-secrets set "Parameters:QdrantApiKey" "any-strong-string"
```

2. Run the stack:
```powershell
dotnet run --project Prism.AppHost
```
This launches the Aspire Dashboard. The Web UI will be available at `http://localhost:7000`.

Hit a local-dev snag? Check the [Developer Runbook](docs/RUNBOOK.md) first — it covers the recurring ones (Postgres volume password drift, Gemini quota limits, dynamic Aspire ports, PowerShell curl escaping, eval fixture regeneration, common deploy failure modes).

## Deployment

Nothing is deployed right now — the environment was decommissioned on 2026-09-28 and the demo now runs locally (Aspire). Backend services deploy via `aspire deploy`, while the React frontend requires a manual push via `Prism.Web/deploy.ps1`. Before redeploying, work through [Decommissioned state and relaunch](docs/RUNBOOK.md#decommissioned-state-and-relaunch), which lists the cost and safety prerequisites that must land first.

## Architecture & Decisions

Prism's architecture and design choices are documented in detail:
* **[Decisions Log](docs/decisions.md)** — Append-only record of architecture, schema, and prompt design decisions.
* **[Developer Runbook](docs/RUNBOOK.md)** — Local dev gotchas, deployment failure modes, eval fixture regeneration.
* **[Deployment & Environment Architecture](docs/deployment-and-environment-architecture.md)** — Deployment topology, environment configuration, deploy workflow, running live evals, and known issues.
* **[Extraction, Audit & Grounding Architecture](docs/extraction-audit-grounding-architecture.md)** — The extractor → auditor → structurer pipeline, grounding checker, eval harness, and known limitations.
* **[Architecture Review (2026-09-05)](docs/pipeline_architecture_review_2026-09-05.md)**

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
