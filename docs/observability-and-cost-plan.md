# Observability and Cost Plan

> As of 2026-09-28. Derived from a read-only discovery pass over the codebase
> and a verification pass against pinned package sources and the local logs.
> Every row is tagged VERIFIED (read in source), INFERRED (reasoned from source,
> not observed running), or UNVERIFIED (needs a live check or a manual test).

## 1. Purpose and scope

Prism should be a measurable AI system: what it spends, what it fails at, and
how good its output is should all be visible without guessing. Today none of
the three are. The environment was decommissioned on 2026-09-28 without anyone
being able to say what it had been spending money on, or on which papers — that
is the gap this plan closes.

**Non-goals.** Explicitly out of scope here, so they stop competing for
attention: MCP, Azure AI Foundry, Redis caching, multi-agent architectures,
Content Safety, customer-facing dashboards, database audit tables, third-party
LLM observability platforms, and any change to prompts or to the eval harness.

## 2. Status

The hosted environment is offline (see `docs/decisions.md`, "Live environment
decommissioned — 2026-09-28"). That splits the work cleanly:

| Build step | Needs cloud? | State |
|---|---|---|
| 1 Honest status | No | Ready — testable on the local Aspire stack |
| 2 See the spend | No | Ready — verify against the local Aspire dashboard |
| 3 Protect the budget | No | Ready — enforcement is application-level |
| 4 Alerts and budget | **Yes** | **Paused until relaunch** |
| 5 SignalR ownership check | No | Ready |
| 6 MCP | No (local only) | Gated — see `docs/audit/mcp_readiness.md` |

Four of six need no subscription. Being offline blocks very little of this.

---

## 3. Findings

### A — Cost and abuse protection

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| A1.1 | No inbound rate limiting anywhere — no `AddRateLimiter`, no policies, no partition key | (absent, `Prism.ApiService`) | COST | VERIFIED |
| A1.2 | No `UseForwardedHeaders`; nginx sets `X-Forwarded-For` but nothing consumes it | (absent) / `Prism.Web/nginx.conf:13` | COST | VERIFIED |
| A1.4 | `JoinChat` adds any connection to any chat group with no ownership check | `Hubs/DocumentHub.cs:21-25` | SAFETY | VERIFIED |
| A2.1 | Only quota is 2 papers per guest session; authenticated users uncapped | `SubmitPaperEndPoint.cs:63-68` | COST | VERIFIED |
| A2.2 | That cap resets on demand — the guest-session endpoint is anonymous and uncapped | `Features/Auth/GuestAuthEndpoint.cs:17-36` | COST | VERIFIED |
| A2.4 | No page-count, text-length, token-estimate or max-claims guard before LLM spend | (absent) | COST | VERIFIED |
| A2.7 | Re-run bypasses dedupe with no quota or cooldown | `SubmitPaperEndPoint.cs:163-222` | COST | VERIFIED |
| A3.1 | No explicit timeout on any LLM call, google-genai or LiteLLM | `engine.py:92,160`; `grounding.py:162` | COST | VERIFIED |
| A3.6 | No jitter anywhere; `Retry-After` never read on the Python LLM paths | `engine.py:48`; `grounding.py:44`; `main.py:461` | COST | VERIFIED |
| A4 | No token usage or cost read or logged on any LLM call | `engine.py:127-128`; `grounding.py:170`; `agent.py:205,216,613` | COST | VERIFIED |

### B — Silent failures and status honesty

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| B1.1 | Claims dropped when audit or structure fails; no counter, no record | `engine.py:456,461-466` | VISIBILITY | VERIFIED + measured |
| B1.5 | A failed summary returns an error string and the paper is still marked `Completed` | `ai_service.py:30-35` → `main.py:246,368` | VISIBILITY | VERIFIED |
| B1.6-8 | Postgres/Qdrant failure returns `[]`, which the graph renders as "out of scope for this paper" | `tools.py:276-278,348-350` → `agent.py:340-341` | VISIBILITY | VERIFIED |
| B1.10 | Bare `catch` with no log at all on summary injection | `Services/ChatSummaryInjector.cs:27-32` | VISIBILITY | VERIFIED |
| B1.12 | Malformed completion message is acked and discarded; paper stays `InProgress` forever | `RabbitMqListenerService.cs:79-86` | VISIBILITY | VERIFIED |
| B1.14 | Extracted-vs-persisted claim counts never recorded together per run | `engine.py:419`; `writer.py:159` | VISIBILITY | VERIFIED |
| B2.3 | Password-protected PDF raises `ValueError`, which `except fitz.FileDataError` does not catch | `pymupdf/__init__.py:5775-5776`; `main.py:382,433` | VISIBILITY | **UNVERIFIED** — see §6 |
| B2.4 | Scanned/image-only PDF yields empty text and completes successfully with zero claims | (no guard) `main.py:212` | VISIBILITY | VERIFIED |
| B2.5 | Every unhandled exception reports as 500, including oversize-body rejections | `Middleware/GlobalExceptionHandler.cs:22` | VISIBILITY | VERIFIED |
| B3.2 | `Completed` with zero claims renders identically to a genuine zero-claim paper | `PaperActivityView.tsx:278-282`; `ClaimList.tsx:148` | VISIBILITY | VERIFIED |
| B4.1 | No React error boundary anywhere | (absent, `Prism.Web/src`) | VISIBILITY | VERIFIED |
| B4.2 | No browser telemetry of any kind | `Prism.Web/package.json` | VISIBILITY | VERIFIED |
| B4.3 | After 5 failed reconnects SignalR dies with only a `console.warn` | `services/signalRService.ts:5,37-40` | VISIBILITY | VERIFIED |

### C — Telemetry

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| C1.3 | Python telemetry sets its provider after `configure_azure_monitor` has already set one, so the OTLP exporter and the `SERVICE_NAME` resource are discarded | `Prism.PythonService/telemetry.py:27-35` | VISIBILITY | **INFERRED** — mechanism VERIFIED in package source, effect not observed live |
| C1.6 | No sampler configured in either language, so the distro default (rate-limited, 5 traces/s) is in effect | (absent) | VISIBILITY | VERIFIED (default); effect UNVERIFIED |
| C2.1 | No GenAI semantic conventions, no `gen_ai.*` attributes, no LiteLLM OTel callback | (absent) | VISIBILITY | VERIFIED |
| C3.2 | `prompt_version` is on no span and no metric — only in the DB and in file logs | `writer.py:161`; `engine.py:125` | VISIBILITY | VERIFIED |
| C3.5 | The entire chat graph is unspanned — three LLM calls per turn, no per-node timing | `paper_chat/agent.py` | VISIBILITY | VERIFIED |
| C4.1 | Zero stdlib logging in Python; 70 in-scope `print()` calls, nothing bridged to OTel | `correlation.py:6-7` | VISIBILITY | VERIFIED |
| E1.3 | `MapDefaultEndpoints()` is never called, so `/alive` does not exist | `ServiceDefaults/Extensions.cs:115` | VISIBILITY | VERIFIED |
| E1.4 | No probe configured in code for any service; no Bicep checked in | (absent) | SAFETY | VERIFIED |
| E2.1 | No alert rule, budget, dashboard or availability test defined in code | (absent) | SAFETY | VERIFIED |

### D — Log hygiene

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| D1.2 | `response_raw` is the model's full output, so paper text lands in the log files | `engine.py:113,129` | SAFETY | VERIFIED |
| D1.5 | `logs/chat/` stores the user's raw question text verbatim | `paper_chat/tools.py:53-60` | SAFETY | VERIFIED |
| D1.6 | Paper text also leaves via stdout on the dropped-claim and malformed-response lines | `engine.py:207,270,462-464` | SAFETY | VERIFIED |
| D1.7 | Logs write to ephemeral container disk, never shipped anywhere | `engine.py:44`; `Dockerfile.worker:13-14` | VISIBILITY | VERIFIED |
| D1.8 | No rotation, no pruning, no size cap — one file per LLM call, forever | (absent) | SAFETY | VERIFIED |

### Measured evidence for B1.1

From the local logs, correlated by `chat_id` + `correlation_id` (counts only):

| Measure | Value |
|---|---|
| Complete runs (extraction log and writer log both present) | 84 |
| Runs where extracted > persisted | **15** |
| Claims extracted / persisted | 1,358 / 1,282 — **76 lost** |
| Lost with no audit log written (audit call failed outright) | 54 |
| Lost after audit, before structure | 22 |
| Lost after the structurer | **0** |
| Complete runs with zero extracted and zero persisted | 2 |

The loss is entirely at one call site. Grounding and the writer lose nothing.
Drops cluster by `prompt_version`: one version accounts for 60 of the 76.

## 4. Already good — do not regress

| Behaviour | file:line |
|---|---|
| Real W3C trace context crosses RabbitMQ, not just a correlation ID | `main.py:163-170`; `ServiceDefaults/Extensions.cs:69` |
| `GroundingStatus.SKIPPED` is persisted and rendered end-to-end | `writer.py:138`; `GroundingStatusConverter.cs:16`; `claim-display.ts:82-88` |
| Corrupt-PDF handling is terminal, honest, and reaches the user | `main.py:382-402` |
| Content-hash cache hit skips the pipeline entirely — never re-bills | `SubmitPaperEndPoint.cs:100-105,489-491` |
| `ExtractionStatus.Failed` is set after retry exhaustion | `main.py:444-458` → `RabbitMqListenerService.cs:92-93` |
| No prompt or paper text on any span | span attributes are IDs and counts only |

## 5. Build sequence

Ordered, not parallel. Each step is only worth doing once the one before it
makes its effect visible.

### 1 — Honest status *(code-only)*

A failed run must stop reporting itself as a completed one.

* **Problem IDs:** B1.5, B1.6-8, B2.3, B2.4, B2.5, B3.2
* **Done when:** a failed summary no longer marks a paper `Completed`; an
  empty, scanned or password-protected PDF reaches a real `Failed` state with a
  message that names the cause; a retrieval failure in chat surfaces as an
  error rather than "out of scope for this paper"; `Completed` with zero claims
  is distinguishable in the UI from a genuine zero-claim paper.
* **Files likely touched:** `ai_service.py`, `main.py`, `paper_chat/tools.py`,
  `paper_chat/agent.py`, `Middleware/GlobalExceptionHandler.cs`,
  `components/matrix/PaperActivityView.tsx`
* **Eval impact:** none expected — no extraction logic changes. Prompt files
  stay untouched, so the prompt hash must not change. Confirm with
  `get_prompt_version()` before and after.
* **Status:** [ ] not started

### 2 — See the spend *(code-only; verify on the local Aspire dashboard)*

* **Problem IDs:** A4, C1.3, C2.1, C3.2, C3.5, C4.1, B1.1, B1.14, D1.2, D1.5, D1.6, D1.8, A3.1
* **Done when:**
  * One structured log line per LLM call carrying stage, model,
    `prompt_version`, tokens in/out, computed cost, latency and
    `correlation_id` — across extraction, grounding, and chat including the
    streaming path.
  * One structured log line per HTTP request carrying user, route, status and
    duration.
  * Counters exist for: fallback model fired, claims extracted vs persisted,
    and `SKIPPED`.
  * `prompt_version` is attached to spans, not only to rows and files.
  * Every LLM call has an explicit timeout.
  * Log hygiene: raw model output and user question text stop being written to
    disk and stdout; rotation is in place.
  * The Python telemetry provider ordering is fixed — **after** the live check
    in §7 confirms the effect, not before.
* **Files likely touched:** `extraction/engine.py`, `extraction/grounding.py`,
  `paper_chat/agent.py`, `paper_chat/tools.py`, `telemetry.py`, `main.py`,
  `api.py`, `Prism.ApiService/Program.cs`
* **Eval impact:** none if confined to instrumentation. If any extraction code
  path is touched, run `matrix_runner` before and after and compare.
* **Status:** [ ] not started

### 3 — Protect the budget *(code-only)*

Ordered deliberately: the global cap lands first because it does not depend on
per-user accounting being correct.

* **Problem IDs:** A1.1, A1.2, A2.1, A2.2, A2.4, A2.7, A3.6
* **Done when:**
  1. A global daily extraction cap enforced by a single database count.
  2. Per-user caps on top of it.
  3. A re-run cooldown.
  4. A rate limiter returning **429** — partitioned by `oid` for authenticated
     users; by IP for guests **only after** forwarded headers are verified to
     arrive (see §7), since without that every guest shares one partition.
  5. Input-size guards: page count, extracted-text length, max claims.
* **Files likely touched:** `Prism.ApiService/Program.cs`,
  `Features/PaperSubmission/SubmitPaperEndPoint.cs`,
  `Features/Auth/GuestAuthEndpoint.cs`, `main.py`, `extraction/engine.py`
* **Eval impact:** a max-claims guard changes extraction output. Run
  `matrix_runner` before and after; set the cap above the observed maximum
  (33 claims in the local logs) so it does not truncate real papers. Prompt
  files untouched — the hash must not change.
* **Status:** [ ] not started

### 4 — Alerts and budget *(cloud — deferred to relaunch)*

* **Problem IDs:** E2.1, E1.4, C1.6
* **Done when:** a failed-request spike alert, a worker-exception alert, an
  LLM call-count or spend-threshold alert, and an Azure budget scoped to the
  resource group with forecasted and 100% thresholds — all defined before the
  first deploy, not after. Probes declared in code rather than left to
  platform defaults.
* **Files likely touched:** `Prism.AppHost/AppHost.cs`
* **Eval impact:** none.
* **Status:** [ ] deferred — no subscription

### 5 — SignalR `JoinChat` ownership check *(code-only)*

* **Problem IDs:** A1.4
* **Done when:** `JoinChat` verifies the caller owns the chat before adding the
  connection to its group, using the same `ResolveUserId` ownership join the
  REST endpoints already use.
* **Files likely touched:** `Hubs/DocumentHub.cs`
* **Eval impact:** none.
* **Status:** [ ] not started

### 6 — MCP *(local only; gated)*

* **Done when:** not before the REST API readiness blocker, the extractor
  `by_omission` gap, and the proof pack are all closed. See
  `docs/audit/mcp_readiness.md` (standing recommendation: do not build now) and
  `docs/mcp-integration-plan.md` (scope and tenancy, design intent only).
* **Eval impact:** none — read-only tools over already-audited data.
* **Status:** [ ] gated

---

## 6. Doubts to verify

| Doubt | Current best answer | How to settle it |
|---|---|---|
| Retry ceiling | ~409 provider calls for one pass at N=20 claims / S=40 spans; ~1,227 with consumer redelivery. A redelivery path does exist — republish-and-ack with an incremented `x-attempt`. | Confirm the mechanism at `main.py:444` and `:466-476`. The bound depends on the broker not supplying `x-delivery-count`; because the retry publishes a *new* message, a quorum-queue migration would reset the counter and remove the bound. Inspect a redelivered message's headers in the RabbitMQ management UI. |
| `AUDIT_CONCURRENCY` | **1**, a module literal with no env override | `grounding.py:41` is authoritative. `docs/decisions.md:429` (2026-08-27) says it was raised to 10 via an env var — no such variable exists in `config.py`, `AppHost.cs`, either Dockerfile, or CI. `docs/extraction-audit-grounding-architecture.md:72` agrees with the code. Doc is wrong; not corrected here because `decisions.md` is append-only. |
| Encrypted-PDF behaviour | `fitz.open` does not raise; `load_page` raises `ValueError`, which `except fitz.FileDataError` does not catch — so it falls to the transient handler and ends `Failed` after 3 attempts. **But** if MuPDF reports 0 pages for an unauthenticated document, `IndexError` is raised instead and iteration silently ends, producing empty text and a `Completed` paper. | Manual test, both branches: `python -c "import fitz; d=fitz.open('enc.pdf'); print(d.needs_pass, d.page_count)"`, then upload the same file and record whether it lands `Failed` or `Completed` with zero claims. |
| Worker scaling | **Resolved 2026-09-28 (portal): 1 min / 10 max, no scale rules.** The worker was the one app container never pinned. `prefetch_count=1` only bounds concurrent papers while exactly one replica exists. | Settled. Pin the maximum before relaunch. |

## 7. Live checks

Deferred — there is no environment to run them against. Results left blank
deliberately; fill in at relaunch.

| Check | How | Result |
|---|---|---|
| Python service role name in Application Insights | KQL: `traces \| summarize by cloud_RoleName` | |
| Sampling retained percentage | KQL: `requests \| summarize sum(itemCount), count()` | |
| Worker replica range after relaunch | `az containerapp show --query "properties.template.scale"` | |
| Azure budget exists and alerts | `az consumption budget list` | |
| `X-Forwarded-For` reaches apiservice | log the header on one request | |
| Aspire dashboard login in a private window | open the managed component URL | |
| Log disk usage on worker and API containers | `du -sh /app/logs` in an exec session | |
| Probe configuration per Container App | `az containerapp show --query "...containers[0].probes"` | |
| Encrypted PDF, end to end | upload a password-protected file | |
| Scanned PDF, end to end | upload an image-only file | |

---

## 8. Currency notes, 2026

* **OTel GenAI semantic conventions are still Development status.** Pin
  versions, adopt nothing that is still moving, and keep message-content
  capture off — the content-capture switch would put paper text and user
  questions onto spans, which is exactly what §3 D flags as a problem.
  <https://learn.microsoft.com/python/api/overview/azure/monitor-opentelemetry-readme>
* **Azure Monitor distros default to rate-limited sampling at 5 traces/second**
  in both pinned versions. Verified in package source; nothing in this repo
  overrides it, so it is in effect for all three services. Verify the retained
  percentage before trusting any count taken from Application Insights.
* **The ASP.NET Core rate limiter rejects with 503 by default**, which reads as
  a server fault rather than a client-side limit. Set 429 explicitly and send
  `Retry-After`. Behind Container Apps ingress, forwarded headers must be
  configured before any IP-based partitioning means anything.
  <https://learn.microsoft.com/en-us/aspnet/core/performance/rate-limit?view=aspnetcore-10.0>
* **Aspire dashboard vs Application Insights.** The dashboard's data is
  in-memory and disappears with the container; the deployed one is a managed
  component behind Entra login requiring Contributor or Owner. It is the right
  tool while iterating locally. Application Insights is the tool for history
  and alerting — the dashboard cannot serve that role.
  <https://learn.microsoft.com/en-us/azure/container-apps/aspire-dashboard> ·
  <https://aspire.dev/dashboard/telemetry-after-deployment/> ·
  <https://aspire.dev/dashboard/explore/>
* **Native OTLP ingestion into Application Insights:** documentation still
  mixes Preview and GA language. Not adopting it; the distro path is enough.

---

## 9. Status tracker

| ID | Item | Status | Evidence / PR | Last verified |
|---|---|---|---|---|
| 1 | Honest status | Not started | — | 2026-09-28 |
| 2 | See the spend | Not started | — | 2026-09-28 |
| 3 | Protect the budget | Not started | — | 2026-09-28 |
| 4 | Alerts and budget | Deferred — no subscription | — | 2026-09-28 |
| 5 | SignalR `JoinChat` ownership check | Not started | — | 2026-09-28 |
| 6 | MCP | Gated — see `docs/audit/mcp_readiness.md` | — | 2026-09-28 |
