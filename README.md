# Prism

Prism checks whether a research paper's own claims are supported by the evidence in that same paper. Tools like Elicit, Consensus and Scite find and summarize papers; Prism does the reviewer's job on one paper: it flags the claims the paper's own data and text do not support.

![Prism pipeline: current path vs approaches tried](docs/diagrams/prism_hero.drawio.svg)

*Green: what runs today. Amber: earlier versions it replaced, or ideas parked. Red: alternatives tested and rejected.*

## At a glance

| | |
|---|---|
| **What it does** | Upload one paper. Prism extracts its claims, audits each one against the full paper, verifies the quoted evidence, and shows a Claim-Support Matrix with a paper-scoped chat. |
| **Current result** | Dev Run 1 (12 papers): flagged 8 of 31 unsupported claims, wrongly flagged 4 of 88 supported ones. Release bar: at least 22/31 with at most 8/88. **Not met; no release with the current auditor.** |
| **What is notable** | Every change is pre-registered with pass/fail marks and a spend cap before it runs; a failed mark rejects it. 24 alternatives have been tested and measured this way. |
| **Status** | Runs locally on .NET Aspire. The Azure deployment was decommissioned on 2026-09-28 to control cost; there is no live URL. |
| **Stack** | .NET 10 / ASP.NET Core, Python / FastAPI / LangGraph, Gemini 3.6 Flash, PostgreSQL, Qdrant, RabbitMQ, React. |

## Read the report

The full story is in the **[engineering report](docs/PRISM_REPORT.md)**. Every fact in it is traced in the [fact sheet](docs/report/PRISM_FACTS.md).

| Section | What you will find |
|---|---|
| [1. Summary](docs/PRISM_REPORT.md#1-summary) | The result, the gap, the main lesson, key terms |
| [2. What Prism is and is not](docs/PRISM_REPORT.md#2-what-prism-is-and-is-not) | Outputs, shipped features, known gaps |
| [3. Architecture and pipeline](docs/PRISM_REPORT.md#3-architecture-and-pipeline) | Every stage, what runs, what was tried at each stage and why |
| [4. Models](docs/PRISM_REPORT.md#4-models) | Models per role, and models tested but not adopted |
| [5. Evaluation design](docs/PRISM_REPORT.md#5-evaluation-design) | Eval sets, metrics, pre-registration and no-rescue rules |
| [6. Every test and its result](docs/PRISM_REPORT.md#6-every-test-and-its-result) | Each test with its marks, result, verdict and cost |
| [7. Where it fails](docs/PRISM_REPORT.md#7-where-it-fails) | The 10 auditor misses by type, the 13 extraction misses, the lessons |
| [8. Current scores](docs/PRISM_REPORT.md#8-current-scores) | Dev, golden and held-out scores against the release bar |
| [9. Costs](docs/PRISM_REPORT.md#9-costs) | Cost per paper, spend per test, the 2027 price change |
| [10. How others approach this problem](docs/PRISM_REPORT.md#10-how-others-approach-this-problem) | Related tools and benchmarks, and how Prism differs |
| [11. Patterns not yet tried](docs/PRISM_REPORT.md#11-patterns-not-yet-tried) | Recorded ideas, not decided |
| [12. Where Prism stands](docs/PRISM_REPORT.md#12-where-prism-stands) | What is decided next and what is off limits |
| [Appendix: Engineering state](docs/PRISM_REPORT.md#appendix-engineering-state) | Eval tooling, CI checks, branches and tags |

## How it works

1. **Upload:** the React UI sends one PDF to the ASP.NET Core API, which queues the job on RabbitMQ for the Python worker.
2. **Extract:** Gemini 3.6 Flash pulls empirical and positioning claims from the full text.
3. **Audit:** Gemini 3.6 Flash judges each claim against the full paper text (supported / partially supported / not supported); a structurer turns its reasoning into JSON.
4. **Ground:** RapidFuzz plus a second LLM check verify the quoted evidence. Grounding never changes the stored audit label; when quotes fail, the claim is shown as not found in the paper.
5. **Persist and show:** PostgreSQL and Qdrant store the results; the UI shows the Claim-Support Matrix, and a paper-scoped chat answers questions about that one paper.

Stage-by-stage detail: [report section 3](docs/PRISM_REPORT.md#3-architecture-and-pipeline).

## Results

| Set | Date | Refusal-family | Positive hits | False rejections |
|---|---|---|---|---|
| **Dev** (12 papers, single full run; progress number, not the release number) | 2026-10-12 | 8/31 (26%) | not recorded | 4/88 |
| **Golden** (3 papers, fast regression gate) | 2026-10-07 | 5/16 (31%) | 11/21 | 1/21 |
| **Held-out** (1 paper, small sample, used 6 times) | 2026-10-07 | 1/2 | 7/10 | 0/10 |

**Release bar:** one full 12-paper dev run with at least 22/31 refusal-family rows and at most 8/88 false rejections, stable under the auditor no-regression rule; the release number comes from one sealed-set run only. **Not met.** Details: [report section 8](docs/PRISM_REPORT.md#8-current-scores).

## Architecture

![Prism architecture: local stack and decommissioned Azure design](docs/diagrams/architecture.png)

Solid boxes run today (local, .NET Aspire). The dashed grey band is the Azure deployment design (Container Apps, PostgreSQL Flexible Server, Blob Storage, Key Vault, Managed Identity, Application Insights), built 2026-09 and decommissioned 2026-09-28 to control cost.

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
2. Run the stack: `dotnet run --project Prism.AppHost`. This launches the Aspire Dashboard; the Web UI is at `http://localhost:7000`.

See the [Developer Runbook](docs/RUNBOOK.md) for local-dev gotchas (Postgres volume password drift, Gemini quota limits, dynamic Aspire ports, eval fixture regeneration).

<details>
<summary><b>Reproduce the golden numbers offline</b> (fixture mode, no LLM or database calls)</summary>

```powershell
cd Prism.PythonService
$env:PRISM_DB_HOST="localhost"; $env:PRISM_DB_DATABASENAME="test"
$env:PRISM_DB_USERNAME="test"; $env:PRISM_DB_PASSWORD="test"
$env:ConnectionStrings__messaging="amqp://test:test@localhost:5672/"
$env:ConnectionStrings__blobs="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=test;BlobEndpoint=http://localhost:9000;"
$env:AI_API_KEY="dummy"; $env:GROQ_API_KEY="dummy"
uv run python -m eval.matrix_runner --source fixture
```
</details>

<!-- Demo video: TODO — no walkthrough recorded yet -->

## Tech stack

| Layer | Technologies |
|---|---|
| Orchestration | .NET Aspire 13.4.6 |
| API Gateway | ASP.NET Core (.NET 10), EF Core |
| Worker & Agent | Python (`>=3.13`), FastAPI, LangGraph 1.0.9 |
| LLMs | Gemini 3.6 Flash, Gemini 3.1 Flash Lite, Groq (gpt-oss-20b) |
| Vector & Search | Qdrant, fastembed |
| Data & Messaging | PostgreSQL, RabbitMQ, Azurite (local blob emulation) |
| Frontend | React 19.2, TypeScript 5.9, Vite 7.3, Tailwind CSS 4.3 |

## Documents

- [Engineering report](docs/PRISM_REPORT.md): the full story.
- [Fact sheet](docs/report/PRISM_FACTS.md): every fact in the report, traced to its source.
- [Decisions log](docs/decisions.md): append-only record of every decision and test.
- [Status](docs/PRISM_STATUS.md): detailed current-state snapshot.
- [Developer runbook](docs/RUNBOOK.md): local setup and gotchas.

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
