# Prism

> **Autonomous Empirical Claim-Auditing Engine for Research Papers**

Prism extracts empirical claims from academic papers and rigorously audits whether each claim is supported by evidence in that same paper. Unlike literature discovery tools (Elicit, Consensus, Scite) that find and summarize across papers, Prism performs a peer-reviewer's core job: auditing a single paper's headline findings against its own data and text.

## Live Demo

🔗 **[Prism on Azure](https://prism-ai-reactui.nicesky-c6f0b846.centralindia.azurecontainerapps.io/)**

Upload any arXiv PDF and watch the extraction and audit pipeline run in real time. (Requires no login).

## Evaluation

Prism's core engineering bet is correct refusal: vetoing any assessment not supported by the paper's own text.

**Current Eval: 11/14 refusal (79%)**
- 4 by_label (the auditor correctly reasoned to a refusal)
- 7 by_omission (the claim was safely dropped before being falsely affirmed)
- 13/23 positive hits
- 0 false rejections

A by_label refusal means the auditor read the paper and reasoned to a refusal — that's the product working. A `by_omission` refusal means the extractor dropped the claim before it was ever audited, so the user never sees it flagged. Converting omissions into visible refusals is the current work.

## How it works

The pipeline is orchestrated asynchronously via RabbitMQ and broken into specific stages to avoid context collapse. First, a Python worker extracts empirical and methodological positioning claims from the full text. Next, a claim auditor (Gemini 3.6 Flash) evaluates each claim individually against the full paper text to assign a label (supported, partially supported, or not supported). Finally, a grounding checker validates the auditor's exact quote spans using semantic matching (RapidFuzz) and a secondary LLM judge (Groq/LiteLLM), adjusting the rubric based on the claim's stance (supports, refutes, or neutral). The pipeline is strictly acyclic: the grounder validates the auditor, but never overrides its label.

## Tech Stack

| Layer | Technologies |
|---|---|
| **Orchestration** | .NET Aspire 13.4 |
| **API Gateway** | ASP.NET Core (.NET 10), EF Core 10 |
| **Worker & Agent** | Python 3.13 (`uv`), FastAPI, LangGraph |
| **LLMs** | Gemini 3.6 Flash, LiteLLM (Groq / Gemini Flash Lite) |
| **Vector & Search** | Qdrant 1.18 |
| **Data & Messaging**| PostgreSQL 18, RabbitMQ 4.3, MinIO |
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

## Deployment

Deployed to Azure Container Apps via `aspire deploy`, with Postgres 
Flexible Server, Blob Storage, Key Vault, and per-service managed 
identities. Secrets flow from Key Vault to containers as `secretref:` 
values, never as plaintext env vars.

The React frontend is pushed separately via `Prism.Web/deploy.ps1` — 
Aspire's auto-generated container overwrites the custom nginx config, 
so it ships as a manual step. Tracked as deferred debt in decisions.md.

Deploy secrets are templated in `Prism.AppHost/.deploy.env.template`; 
the real `.deploy.env` is gitignored.

2. Run the stack:
```powershell
dotnet run --project Prism.AppHost
```
This launches the Aspire Dashboard. The Web UI will be available at `http://localhost:7000`.

## Architecture & Decisions

Prism's architecture and design choices are documented in detail:
* **[Decisions Log](docs/decisions.md)** — Append-only record of architecture, schema, and prompt design decisions.
* **[Pipeline Audit (2026-09-04)](docs/audit/pipeline_audit_2026-09-04.md)**
* **[Defects Audit (2026-09-04)](docs/audit/two_defects_2026-09-04.md)**
* **[Architecture Review (2026-09-05)](docs/audit/pipeline_architecture_review_2026-09-05.md)**
* **[Pending Bugs (2026-09-05)](docs/audit/upload_pending_bugs_2026-09-05.md)**

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
