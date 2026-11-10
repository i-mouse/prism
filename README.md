# Prism

Prism checks whether a research paper's own claims are supported by the evidence in that same paper. Unlike literature-discovery tools (Elicit, Consensus, Scite) that find and summarize across papers, Prism does a peer reviewer's core job on one paper: checking its headline findings against its own data and text. The engineering bet is correct refusal: flagging any claim the paper's own text does not support.

![Prism pipeline: current path vs approaches tried](docs/diagrams/prism_hero.drawio.svg)

**Full engineering report: [docs/PRISM_REPORT.md](docs/PRISM_REPORT.md)** (pipeline, evaluation design, every test and its result, where it fails, costs).

## Status - 2026-11-10

- **Runs locally only** (.NET Aspire). The hosted Azure demo was decommissioned 2026-09-28 to stop uncapped container spend (subscription cancellation initiated the same day, not yet confirmed complete). There is no live URL. Run it with [Quick Start](#quick-start-local-dev) below.
- **Release bar not met.** On the 12-paper dev set, the one full run (dev Run 1) flagged 8 of the 31 claims that their own paper does not fully support (26%), and wrongly flagged 4 of the 88 supported claims (false rejections 4/88). The release bar is one full 12-paper run with at least 22/31 flagged and at most 8/88 false rejections, with the fixes stable under the auditor no-regression rule. There is no release with the current auditor.
- **Both stages need work.** Of the 23 misses, 13 are extraction misses (the claim was never extracted) and 10 are auditor misses (extracted, but wrongly judged supported). Auditor-only ceiling 18/31; extraction-only ceiling 21/31. Neither stage alone reaches the bar.
- **Latest test (2026-11-08/09):** a newer auditor model (gemini-3.8-flash, medium and high thinking) caught more unsupported claims but also rejected more supported ones (4/88 and 7/88, against 1/88 for the baseline in the same check). Both failed their pre-registered marks; the auditor stays gemini-3.6-flash.
- **Next:** one new approach, chosen after the report and pre-registered on its own. See [Next](#next).

## Results

All numbers below are frozen, fixture-replayed runs: reproducible offline, no live LLM calls needed to re-score them. Source: `docs/decisions.md`.

| Set | Date | Refusal-family | Positive hits | False rejections | Coverage |
|---|---|---|---|---|---|
| **Dev baseline** (internal progress number, *not the release number*; single run, n=31 refusal rows) | 2026-10-12 | 8/31 (26%) | not recorded | 4/88 | not recorded |
| **Golden** (3 papers, 16 refusal rows / 37 total, de-leaked prompts) | 2026-10-07 | 5/16 (31%), gate 0.30 | 11/21 (floor 10) | 1/21 | 37/37 |
| **Held-out** (1 paper, 2 refusal rows; small sample, near-burnt: used 6 times) | 2026-10-07 | 1/2 | 7/10 | 0/10 | 12/12 |

*(decisions.md:1474-1479 for golden/held-out; decisions.md:1750, 2212 for dev refusal; dev false rejections: decisions.md 'Corrections - 2026-10-22', re-derived with the filled match map in 'Stage A1 marks and cap re-confirmed - 2026-10-28'.)*

**Release bar (restated 2026-10-22, replaces "mean of 3 runs"):** dev: one full 12-paper run reaches >= 22/31 refusal-family rows with false rejections <= 8/88, and the fixes are stable under the auditor no-regression rule (decisions.md 2026-10-28). Release number: one sealed-set run only, never dev or golden numbers.

**Reproduce the golden numbers (fixture mode, no LLM/DB calls, environment setup required):**
```powershell
cd Prism.PythonService
$env:PRISM_DB_HOST="localhost"; $env:PRISM_DB_DATABASENAME="test"
$env:PRISM_DB_USERNAME="test"; $env:PRISM_DB_PASSWORD="test"
$env:ConnectionStrings__messaging="amqp://test:test@localhost:5672/"
$env:ConnectionStrings__blobs="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=test;BlobEndpoint=http://localhost:9000;"
$env:AI_API_KEY="dummy"; $env:GROQ_API_KEY="dummy"
uv run python -m eval.matrix_runner --source fixture
```

## How it works

Upload triggers an async pipeline over RabbitMQ. A Python worker extracts empirical and positioning claims from the full text; a claim auditor (Gemini 3.6 Flash) judges each claim individually against the full paper (supported / partially supported / not supported). The auditor sends the full paper text per claim, not a retrieved excerpt. A structurer then parses the auditor's free-text reasoning into JSON. Finally a grounding checker verifies the auditor's quoted spans with fuzzy matching (RapidFuzz) plus a second LLM judge, stance-aware (supports / refutes / neutral). Grounding never changes the stored audit label: when the quotes fail, the displayed status shows the claim as not found in the paper, and the eval counts that as a catch. Results land in Postgres (claims, audits) and Qdrant (vector store); the React UI reads them and supports paper-scoped chat.

The diagram at the top shows this path (green) and every alternative tested at each stage (red: tested and rejected; amber: earlier version replaced, or parked). Section 3 of the [report](docs/PRISM_REPORT.md) walks through each stage.

## Architecture

![Prism architecture: local stack and decommissioned Azure design](docs/diagrams/architecture.png)

Solid boxes run today (local, .NET Aspire). The dashed grey band is the Azure deployment design, built 2026-09 and decommissioned 2026-09-28 to control cost.

## Evaluation method

Prism's eval harness is the centerpiece, not an afterthought:
- **Pre-registered marks.** Every experiment (model/prompt/pipeline change) is scored against pass/fail marks written down *before* the run, with a spend cap; see `docs/decisions.md`.
- **Auditor no-regression rule (2026-10-28).** An auditor change is kept only if, over 3 runs, it fixes more misses without losing any current catch, keeps false rejections at or below the baseline and never above 8/88, holds the golden gates, and targets a failure type rather than a named row.
- **Blind / AI-assisted labelling, human-checked.** Dev rows were hand-labelled under a written rubric before any Prism output was seen; golden rows were hand-audited against the PDFs and corrected only where the paper contradicted them (decisions.md 2026-10-01/02, 2026-10-03). For the clean-extraction attempt, two AI labellers (ChatGPT, Gemini) labelled first; a blind human spot-check disagreed on 6/10 (K6) and 4/10 (K7), which rejected the AI labels under the pre-registered rule. A follow-up diagnostic found the human reference had applied a narrower "headline claim" notion than the written definition, so (logged as a deviation before any scoring) AI-agreed labels were used and AI disagreements were scored as bounds.
- **Bounded (worst/best) scoring.** Items where the two AI labellers disagreed were scored both ways (worst case and best case); a mark passes only if both pass, fails if both fail, otherwise inconclusive (decisions.md, 2026-10-20).
- **No rescue runs.** A failing required mark rejects the change outright: no partial credit, no re-running, no threshold edits to save a result (e.g. Experiment 3's cost gate, decisions.md:2600-2606).
- **Scripts halt on unreproducible numbers.** If a script can't reproduce an already-logged number, it stops rather than silently drifting (eval harness design, decisions.md).
- **Prompt-leak CI check.** Prompts are de-leaked of eval-paper text and answer-key wording, and CI enforces this stays true (decisions.md:1342).
- **Golden vs dev vs held-out** serve different jobs: golden (37 adjudicated rows, 3 papers) is the fast regression gate; dev (119 rows, 12 papers) is where experiments are judged against the release bar; held-out (1 paper, small sample, already used 6 times, near-burnt for measuring further gains) is a last look before trusting a change generalizes.

## What I tried

No attempt so far has closed the gap; every one ended failed, rejected, or parked. The full list with marks, results and costs is in [report section 6](docs/PRISM_REPORT.md#6-every-test-and-its-result). Highlights:

- **Auditor thinking level high (Experiment 1):** fixed 1 of 10 target rows (needed >= 3). Rejected.
- **Extractor few-shot claim shapes (Experiment 2):** all 4 required marks failed. Rejected.
- **Second extraction pass over text windows (Experiment 3):** projected INR 237.59/paper against the INR 130 cost gate. Rejected.
- **Second pass plus duplicate filter (clean-extraction attempt):** recall on the target rows 5-6/13 and cost over the gate. Rejected.
- **Separate scope-checking step (Stage A1):** fixed 3 of 10 misses, but only 1 of 6 always-missed rows (needed 4). Failed.
- **Code checks on table numbers (Auditor v2, T1 and T2-R):** off-the-shelf table extractors left only 5 of 8 tables usable; on hand-built reference tables the checks fixed 4 of 10 misses but only 2 of 5 hard rows (needed 3). Failed.
- **Newer auditor model (gemini-3.8-flash):** more catches, but more false rejections; the high-thinking arm also cost INR 194.4/paper against the INR 130 gate. Failed.

The lesson so far: stricter judging catches more unsupported claims but also rejects more supported ones, and the hardest misses are about what a claim means and covers, not about reading tables.

## Cost

Per-paper cost today is about **INR 87-101**, measured two ways: INR ~101/paper from the 2026-10-11 baseline spend (4 papers, INR 1,250.00 -> 1,655.55; decisions.md:1706-1707), and INR ~87/paper from the full 12-paper run-1 ingestion (INR 1,048.40 / 12 papers; `docs/evals/dev_adjudication_run1.md:17`). Most of that is the auditor: it sends the full paper text once per claim (measured partial share about 90-96% of input tokens; an earlier 75% figure was an estimate).

Gemini Flash prices double on 2027-01-01, which takes the per-paper cost from about INR 87 to about INR 174, above the INR 130 cost gate (decisions.md, 'Funding source and model plan for the next auditor tests - 2026-11-02').

## Next

1. Choose one new auditor or extraction approach and pre-register it on its own (marks, cap, tag before the run). Ideas recorded, not decided: a graded severity score with a cut-off instead of three fixed labels; agreement between two auditors before flagging a claim.
2. Claim-scope decision (headline claims only vs whole-paper claims) and a new sealed set, then one sealed run for the release number.

## Run locally

See [Quick Start](#quick-start-local-dev) below for setup, and the [Developer Runbook](docs/RUNBOOK.md) for local-dev gotchas (Postgres volume password drift, Gemini quota limits, dynamic Aspire ports, eval fixture regeneration).

<!-- Demo video: TODO — no walkthrough recorded yet -->

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
2. Run the stack: `dotnet run --project Prism.AppHost` — launches the Aspire Dashboard; Web UI at `http://localhost:7000`.

*(user-secrets parameter names and port confirmed against `Prism.AppHost/AppHost.cs`.)*

## Tech stack

**Built (runs today, local):**

| Layer | Technologies |
|---|---|
| Orchestration | .NET Aspire 13.4.6 |
| API Gateway | ASP.NET Core (.NET 10), EF Core |
| Worker & Agent | Python (`>=3.13`), FastAPI, LangGraph 1.0.9 |
| LLMs | Gemini 3.6 Flash, Gemini 3.1 Flash Lite, Groq (gpt-oss-20b) |
| Vector & Search | Qdrant, fastembed |
| Data & Messaging | PostgreSQL, RabbitMQ, Azurite (local blob emulation) |
| Frontend | React 19.2, TypeScript 5.9, Vite 7.3, Tailwind CSS 4.3 |

*(Versions confirmed against `Prism.AppHost/Prism.AppHost.csproj`, `Prism.PythonService/pyproject.toml`, `Prism.Web/package.json`. Postgres/Qdrant/RabbitMQ server version numbers and EF Core's version are not pinned in `AppHost.cs`, so not confirmable from the repo and left unversioned here.)*

**Azure design (deployed 2026-09, decommissioned 2026-09-28 — [Architecture](#architecture)):** Azure Container Apps for API/worker/frontend, Azure Postgres Flexible Server, Azure Blob Storage, Azure Key Vault, Managed Identity, Application Insights.

## Links

- [Engineering report](docs/PRISM_REPORT.md): the full story, every test and its result.
- [Fact sheet](docs/report/PRISM_FACTS.md): every fact in the report, traced to its source entry.
- [Decisions Log](docs/decisions.md): append-only record this file is synced to.
- [PRISM Status](docs/PRISM_STATUS.md): detailed current-state snapshot.
- [Premerge Review (2026-10-20)](docs/premerge_review_2026-10-20.md): code-level review, known risks.
- [Developer Runbook](docs/RUNBOOK.md): local dev gotchas, relaunch checklist.
- Eval reports: `docs/evals/dev_adjudication_run1.md`, `docs/evals/clean_labels/clean_attempt_score.md`.

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
