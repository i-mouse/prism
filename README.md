# Prism

Prism extracts empirical claims from a research paper and audits whether each claim is supported by evidence in that same paper. Unlike literature-discovery tools (Elicit, Consensus, Scite) that find and summarize across papers, Prism does a peer-reviewer's core job on one paper: checking its headline findings against its own data and text. The engineering bet is correct refusal — vetoing any assessment the paper's own text doesn't support.

## Status — 2026-10-21

- **Runs locally only.** The hosted Azure demo was decommissioned 2026-09-28 (subscription cancellation initiated same day, not yet confirmed complete) to stop uncapped container spend. There is no live URL. Run it with [Quick Start](#quick-start-local-dev) below.
- **Release bar not yet met.** Release bar (replaces "mean of 3 runs"): dev: one full 12-paper run reaches >= 22/31 refusal-family rows with false rejections <= 8/88, and Stage A1 shows the fixes stable (>= 2 of 3 repeats). Release number: one sealed-set run only, never dev or golden numbers. The current single-run dev baseline is 26% (8/31). Of the 23 missed refusal rows, 10 are auditor misses (claim extracted, wrongly judged supported) and 13 are extraction misses — both stages need work (auditor-only ceiling 18/31, extraction-only ceiling 21/31; neither alone reaches the floor).
- Four experiments aimed at closing that gap have been tried and rejected on pre-registered marks. Work continues on the extractor/auditor; see [Roadmap](#roadmap).

## Results

All numbers below are frozen, fixture-replayed runs — reproducible offline, no live LLM calls needed to re-score them. Source: `docs/decisions.md`.

| Set | Date | Refusal-family | Positive hits | False rejections | Coverage |
|---|---|---|---|---|---|
| **Dev baseline** (internal progress number — *not the release number*; single run, n=31 refusal rows) | 2026-10-12 | 8/31 (26%) | — | - | — |
| **Golden** (3 papers, 16 refusal rows / 37 total, de-leaked prompts) | 2026-10-07 | 5/16 (31%), gate 0.30 | 11/21 (floor 10) | 1/21 | 37/37 |
| **Held-out** (1 paper, 2 refusal rows — small sample, near-burnt: used 6 times) | 2026-10-07 | 1/2 | 7/10 | 0/10 | 12/12 |

*(decisions.md:1474-1479 for golden/held-out; decisions.md:1750, 2212 for dev refusal.)*

Dev false-rejection count is left blank: `docs/evals/dev_adjudication_run1.md` reports it as a draft figure (line 125 "Draft false rejections", confirmed still draft at line 135), not a final adjudicated count.

**Release bar (restated 2026-10-22, replaces "mean of 3 runs"):** dev: one full 12-paper run reaches >= 22/31 refusal-family rows with false rejections <= 8/88, and Stage A1 shows the fixes stable (>= 2 of 3 repeats). Release number: one sealed-set run only, never dev or golden numbers (decisions.md:1636-1640, 'Auditor redesign agreed... - 2026-10-22').

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

Upload triggers an async pipeline over RabbitMQ. A Python worker extracts empirical and positioning claims from the full text; a claim auditor (Gemini 3.6 Flash) judges each claim individually against the full paper (supported / partially supported / not supported) — the auditor sends the full paper text per claim, not a retrieved excerpt. A structurer then parses the auditor's free-text reasoning into JSON. Finally a grounding checker validates the auditor's quoted spans with fuzzy matching (RapidFuzz) plus a second LLM judge, stance-aware (supports / refutes / neutral); it can veto the auditor's label, never override it upward. Results land in Postgres (claims, audits) and Qdrant (vector store); the React UI reads them and supports paper-scoped chat.

```mermaid
flowchart LR
    U[Upload PDF] --> W[Python worker]
    W --> E[Extractor\nGemini 3.6 Flash]
    E --> A[Claim auditor\nGemini 3.6 Flash]
    A --> S[Structurer\nparses audit to JSON]
    S --> G[Grounding checker\nRapidFuzz + Groq/Gemini]
    G --> DB[(Postgres + Qdrant)]
    DB --> UI[React UI / chat]
```

This is what runs today, locally. The full architecture, including the decommissioned Azure design, is below.

## Architecture

![Prism architecture — local stack and decommissioned Azure design](docs/diagrams/architecture.png)

Solid boxes run today (local, .NET Aspire). The dashed grey band is the Azure deployment design, built 2026-09 and decommissioned 2026-09-28 to control cost. The pipeline diagram above shows the request flow in short.

## Evaluation method

Prism's eval harness is the centerpiece, not an afterthought:
- **Pre-registered marks.** Every experiment (model/prompt/pipeline change) is scored against pass/fail marks written down *before* the run, with a spend cap — see `docs/decisions.md`.
- **Blind / AI-assisted labelling, human-checked.** Dev rows were hand-labelled under a written rubric before any Prism output was seen; golden rows were hand-audited against the PDFs and corrected only where the paper contradicted them (decisions.md 2026-10-01/02, 2026-10-03). For the clean-extraction attempt, two AI labellers (ChatGPT, Gemini) labelled first; a blind human spot-check disagreed on 6/10 (K6) and 4/10 (K7), which rejected the AI labels under the pre-registered rule. A follow-up diagnostic found the human reference had applied a narrower "headline claim" notion than the written definition, so — logged as a deviation before any scoring — AI-agreed labels were used and AI disagreements were scored as bounds.
- **Bounded (worst/best) scoring.** Items where the two AI labellers disagreed were scored both ways (worst case and best case); a mark passes only if both pass, fails if both fail, otherwise inconclusive (decisions.md, 2026-10-20).
- **No rescue runs.** A failing required mark rejects the change outright — no partial credit, no re-running, no threshold edits to save a result (e.g. Experiment 3's cost gate, decisions.md:2600-2606).
- **Scripts halt on unreproducible numbers.** If a script can't reproduce an already-logged number, it stops rather than silently drifting (eval harness design, decisions.md).
- **Prompt-leak CI check.** Prompts are de-leaked of eval-paper text and answer-key wording, and CI enforces this stays true (decisions.md:1342).
- **Golden vs dev vs held-out** serve different jobs: golden (37 adjudicated rows, 3 papers) is the fast regression gate; dev (119 rows, 12 papers) is where experiments are judged against the 70% release floor; held-out (1 sealed paper, small sample, already used 6 times — near-burnt for measuring further gains) is a last look before trusting a change generalizes.

## What I tried and why it failed

- **Experiment 1 — auditor `thinking_level=high`:** fixed only 1 of 10 target rows (needed >=3). Auditor is non-deterministic run-to-run at the default setting (+/-3 rows of noise). REJECTED. ([decisions.md:1807-1831](docs/decisions.md))
- **Experiment 2 — extractor few-shot claim-shape repair:** all 4 required marks failed; evidence leans toward (not proven) a task-design problem (one list-all-claims call), not a teaching/example problem. REJECTED. ([decisions.md](docs/decisions.md), "Experiment 2 - Stage A result - 2026-10-14")
- **Experiment 3 — windowed pass-2 re-extraction:** rejected on the cost gate (projected INR 237.59/paper vs 130 cap); recall was measured only exploratorily afterward (AI-proposed, human-verified — not the pre-registered blind adjudication), so no recall claim is made. REJECTED. ([decisions.md:2600-2606, 2607-2616](docs/decisions.md))
- **Clean-extraction attempt — claim-cleaning filter on top of Exp 3:** real claims came through (precision 0.81-0.95) but recall on the target rows was low (5-6/13), the filter over-dropped real claims as duplicates, and cost still exceeded the cap. REJECTED; flag stays off. ([decisions.md:3005-3018](docs/decisions.md))

Three known risks remain in the (currently flag-gated, off-by-default) clean-extraction code, documented but not fixed: a "same"-relation chain-drop that depends on upstream dedup already having run (`pass2_clean.py:267-270`), an LLM-returned neighbour id used without a membership check against the ids actually offered (`pass2_clean.py:62-66,199,268-269`), and a response format with no id field of its own — correspondence is positional `zip()`, with only a length-mismatch guard, so a same-length reordered response would go undetected (`prompt_loader.py:291-296`). None of this runs in the default pipeline. (`docs/premerge_review_2026-10-20.md` section 3)

## Cost

Per-paper cost today is about **INR 87-101**, measured two ways: INR ~101/paper from the 2026-10-11 baseline spend (4 papers, INR 1,250.00 -> 1,655.55; decisions.md:1706-1707), and INR ~87/paper from the full 12-paper run-1 ingestion (INR 1,048.40 / 12 papers; `docs/evals/dev_adjudication_run1.md:17`), also the base figure used in the clean-extraction cost formula (decisions.md:2670, 3011-3012). Most of that is the auditor: it sends the full paper text once per claim, about 75% of total input tokens, with thinking left at the Gemini 3.6 Flash default (decisions.md:1677).

Planned fix (design agreed: caching + scope check, marks and caps written first): a 2026-10-22 diagnostic found the auditor has the evidence but does not check the claim's full scope; the next design forces a full-scope check and uses explicit caching to cut the full-paper-per-claim cost. Marks and budget are written before any run. (decisions.md, 'Auditor redesign agreed... - 2026-10-22')

## Roadmap

Next 3 steps, in order (decisions.md, "K1 diagnostics and filter status - 2026-10-20"):
1. Auditor phase - design a structural full-scope check plus explicit caching, with marks and budget written first; targets the 10 auditor misses and per-paper cost.
2. Re-test pass-2 / sentence-level extraction end to end with the new auditor; the parked K7 filter fix (validate neighbour ids, never resolve "same" against a dropped neighbour) stays parked until then.
3. Claim-scope decision (headline claims only vs whole-paper) and a new sealed set, then one sealed run for the release number.

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

- [Decisions Log](docs/decisions.md) — append-only record this file is synced to.
- [PRISM Status](docs/PRISM_STATUS.md) — detailed current-state snapshot.
- [Premerge Review (2026-10-20)](docs/premerge_review_2026-10-20.md) — code-level review, known risks.
- [Developer Runbook](docs/RUNBOOK.md) — local dev gotchas, relaunch checklist.
- Eval reports: `docs/evals/dev_adjudication_run1.md`, `docs/evals/clean_labels/clean_attempt_score.md`.

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
