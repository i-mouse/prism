# Observability and Cost Plan

> As of 2026-09-29. Derived from a read-only discovery pass over the codebase
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
LLM observability platforms, and any change to prompts.
* Improving the eval (matcher adjudication, scorer reporting) is allowed; tuning prompts to move a score is not.
* Azure-hosted alerting, until a relaunch.

## 2. Status

The hosted environment is offline (see `docs/decisions.md`, "Live environment
decommissioned — 2026-09-28"). That splits the work cleanly:

| Build step | Needs cloud? | State |
|---|---|---|
| 1 Honest status | No | Ready — testable on the local Aspire stack |
| 2 Eval honesty | No | Needs your 14-row hand-check for the match map |
| 3 Caps and 429 | No | Ready |
| 4 See the spend | No | Ready — verify against the local Aspire dashboard |
| 5 Guards | No | Ready (golden page counts measured 2026-09-29) |
| 6 Demo mode | No | Blocked (PR 6 must not start until log hygiene issues are closed in PR 4) |
| 7 Local alerts | No | Ready |
| 8 MCP | No (local only) | Gated — see `docs/audit/mcp_readiness.md` |

None of the eight steps needs a subscription; the cloud alerts block in Section 5 is deferred. Being offline blocks very little of this.

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
| A2.8 | The guest quota (A2.1) is consumed at upload time - `FileRecord`/`ChatFile` rows are created (`:710,719`) and counted toward `guestFileCount >= 2` (`:63-68`) before the pipeline has run at all, let alone before it's known whether the file will fail cheaply (corrupt/password-protected/scanned - fails before any LLM call, near-zero cost) or expensively (fails deep into extraction, after real LLM spend). A cheap pre-LLM failure consumes a guest session slot identically to an expensive one, even though A2.1/A2.2's stated purpose is protecting against LLM spend specifically, not upload volume. | `SubmitPaperEndPoint.cs:63-68,710-719` | COST | VERIFIED |
| A3.1 | No explicit timeout on any LLM call, google-genai or LiteLLM | `engine.py:92,160`; `grounding.py:162` | COST | VERIFIED |
| A3.6 | No jitter anywhere; `Retry-After` never read on the Python LLM paths | `engine.py:48`; `grounding.py:44`; `main.py:461` | COST | VERIFIED |
| A4 | No token usage or cost read or logged on any LLM call | `engine.py:127-128`; `grounding.py:170`; `agent.py:205,216,613` | COST | VERIFIED |
| A5 | Every provider 429 (rate limit, quota or spend cap) is treated as transient and retried; nothing stops a run when a cap is hit | `engine.py:46-58; grounding.py:46-56` | COST | VERIFIED |

### B — Silent failures and status honesty

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| B1.1 | Claims dropped when audit or structure fails; no counter, no record. 60 of the 76 lost claims belong to prompt version 5acbc4f65ac1 (an earlier window). At the current prompt hash 0bcf9d44e619: 284 extracted, 284 persisted, 0 lost, across 10 runs that reached the writer, on the 3 golden papers. One current-hash run died pre-writer and falls outside the 84-run denominator. | `engine.py:456,461-466` | VISIBILITY | VERIFIED + measured |
| B1.5 | A failed summary returns an error string and the paper is still marked `Completed` | `ai_service.py:30-35` → `main.py:246,368` | VISIBILITY | VERIFIED |
| B1.6-8 | Postgres/Qdrant failure returns `[]`, which the graph renders as "out of scope for this paper" | `tools.py:276-278,348-350` → `agent.py:340-341` | VISIBILITY | VERIFIED |
| B1.10 | Bare `catch` with no log at all on summary injection | `Services/ChatSummaryInjector.cs:27-32` | VISIBILITY | VERIFIED |
| B1.12 | Malformed completion message is acked and discarded; paper stays `InProgress` forever | `RabbitMqListenerService.cs:79-86` | VISIBILITY | VERIFIED |
| B1.14 | Extracted-vs-persisted claim counts never recorded together per run | `engine.py:419`; `writer.py:159` | VISIBILITY | VERIFIED |
| B1.15 | A dead-lettered message (any `message.reject(requeue=False)` in main.py) produces no log line, no metric, and no user-visible signal beyond the paper's own status; there is no documented replay path for the DLQ. Assigned to step 4 (structured log line on dead-letter) and step 7 (DLQ depth monitor). No DLQ code changed in this PR. | `main.py` (every `requeue=False` site: `:445,476,507,538,575`); `dlx_prism_exchange`/`prism_failed` declared at `main.py:176-177` with nothing consuming them | VISIBILITY | VERIFIED |
| B2.3 | Password-protected PDF raises `ValueError`, which `except fitz.FileDataError` does not catch | `pymupdf/__init__.py:5775-5776`; `main.py:382,433` | VISIBILITY | **UNVERIFIED** — see §6 |
| B2.4 | Scanned/image-only PDF yields empty text and completes successfully with zero claims | (no guard) `main.py:212` | VISIBILITY | VERIFIED |
| B2.5 | Every unhandled exception reports as 500, including oversize-body rejections | `Middleware/GlobalExceptionHandler.cs:22` | VISIBILITY | VERIFIED |
| B3.2 | `Completed` with zero claims renders identically to a genuine zero-claim paper | `PaperActivityView.tsx:278-282`; `ClaimList.tsx:148` | VISIBILITY | VERIFIED |
| B3.3 | A terminal failure updates `FileRecord.Status` to `Failed` (sidebar shows it correctly) but the main-pane stepper never leaves its in-progress state: 4 of 5 terminal branches in `main.py` never emitted a `stage="failed"` event, the "Working on your paper..." card ignored `hasFailed` entirely, and no failure reason ever reached the screen. Fixed in this PR (see B3.4 for the deeper root cause found during the fix). | `main.py` (all `except` branches, pre-fix); `PaperActivityView.tsx:466-475` (unconditional card, pre-fix) | VISIBILITY | VERIFIED + FIXED |
| B3.4 | Root cause underneath B3.3: `GET /api/papers/{paperId}/claims` hardcoded `extractionStatus: "Pending"` whenever no `DocumentExtractors` row exists yet — true for every paper before the writer runs, not just failed ones — instead of reading the already-selected `file.Status`. `GET /api/chats` reads the real column two lines away and was never affected. Fixed in this PR. | `SubmitPaperEndPoint.cs:267-276` (pre-fix) vs. `:379` (already correct) | VISIBILITY | VERIFIED + FIXED |
| B3.5 | **Regression introduced and closed within this same PR sequence — not a pre-existing finding.** B3.3's own fix (the malformed-completion-message branch, B1.12) wrote `FileRecord.Status = Failed` and overwrote `Summary` keyed only by `fileId`, with no check on the record's current state. A duplicate or late completion message — plausible in production: the retry path is republish-and-ack and RabbitMQ has no persistent volume — for an already-`Completed` file would silently flip it to `Failed` and destroy its real summary, an audit-data-loss bug worse than the stuck-`InProgress` bug B1.12 fixed. The normal (non-malformed) completion branch had the identical hole independently of B1.12, predating this PR sequence entirely. Both writes are now guarded by `RabbitMqListenerService.ShouldApplyStatusTransition`: a transition is applied only from `Pending`/`InProgress`; any message for an already-terminal (`Completed` or `Failed`) file is logged and ignored, including the SignalR broadcast. | `Services/RabbitMqListenerService.cs` (malformed branch and normal completion branch, both pre-guard) | SAFETY | **INTRODUCED AND FIXED WITHIN THIS PR** |
| B3.6 | Stale `paperClaims` data from the previously-viewed paper was passed as initial props into a freshly-mounted `PaperActivityView`, during the render where `activePaperId` had already moved on (e.g. to `null` at the start of a new upload) but `paperClaims` hadn't caught up yet (`usePaperClaims` resets it via an effect, one render behind). This permanently committed a wrong, borrowed failure line into the new paper's own log strip (plus a one-frame flash of false "Failed" on its header/stepper) — found via manual smoke test (uploading a healthy file immediately after a failed one), not automated. Fixed by deriving `extractionStatus`/`failureReason` only when `paperClaims.paperId === activePaperId` (`selectActivityViewFailureProps`), and by making the synthesized-line effect idempotent against React 18 StrictMode's dev-only double-invoke (a ref-based guard, `shouldSynthesizeFailureLine`) as an independent correctness property of the effect itself. | `MatrixView.tsx` (pre-fix, ~261-262); `PaperActivityView.tsx` (synthesis effect, pre-fix) | VISIBILITY | **FOUND VIA MANUAL TEST — FIXED WITHIN THIS PR** |
| B3.7 | The fetched-only failed-stage fallback (no live `ExtractionProgress` event this mount) defaulted to a hardcoded stage index, showing a specific wrong step as failed - e.g. a corrupt PDF that live-failed at "Preparing" instead showed "Extracting" as failed after a page refresh. Found via the same manual smoke test as B3.6. Fixed by rendering an unknown-stage failure as neutral (every stepper row "pending") instead of guessing (`stepperRowStatus`, `failedIndex === -1`). **Known limitation, not fixed here:** the true `failedStage` is not persisted anywhere the fetched path can read it back - only the live event carries it. This only affects the fallback (no-live-event) rendering path; worth persisting only if it becomes a recurring point of confusion. | `PaperActivityView.tsx` (pre-fix, `failedIndex` fallback and `getStatus`) | VISIBILITY | **FOUND VIA MANUAL TEST — FIXED WITHIN THIS PR** |
| B4.1 | No React error boundary anywhere | (absent, `Prism.Web/src`) | VISIBILITY | VERIFIED |
| B4.2 | No browser telemetry of any kind | `Prism.Web/package.json` | VISIBILITY | VERIFIED |
| B4.3 | After 5 failed reconnects SignalR dies with only a `console.warn` | `services/signalRService.ts:5,37-40` | VISIBILITY | VERIFIED |

**Known gap under B3.3, not fixed here:** if the worker process itself dies mid-job (killed, OOM, crashes) rather than raising a handled exception, no failure event and no completion message of any kind is ever published — the paper remains `InProgress` indefinitely, on both the fetched and live paths, since neither ever fires. A dead process cannot announce its own death; closing this needs a stale-job detector (e.g. a max-age check against `FileRecord.UploadedAt` while `Status == InProgress`), which is out of scope for this PR. Recorded here so it isn't mistaken for something this PR already covers.

### C — Telemetry

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| C1.3 | Python telemetry sets its provider after `configure_azure_monitor` has already set one, so the OTLP exporter and the `SERVICE_NAME` resource are discarded | `Prism.PythonService/telemetry.py:27-35` | VISIBILITY | **INFERRED.** Mechanism verified in package source. Cannot run locally: configure_azure_monitor is guarded by the connection-string env var (telemetry.py:24-26). Observe at relaunch. |
| C1.6 | No sampler configured in either language, so the distro default (rate-limited, 5 traces/s) is in effect | (absent) | VISIBILITY | VERIFIED (default); effect UNVERIFIED |
| C2.1 | No GenAI semantic conventions, no `gen_ai.*` attributes, no LiteLLM OTel callback | (absent) | VISIBILITY | VERIFIED |
| C3.2 | `prompt_version` is on no span and no metric — only in the DB and in file logs | `writer.py:161`; `engine.py:125` | VISIBILITY | VERIFIED |
| C3.5 | The entire chat graph is unspanned — three LLM calls per turn, no per-node timing | `paper_chat/agent.py` | VISIBILITY | VERIFIED |
| C4.1 | Zero stdlib logging in Python; 70 in-scope `print()` calls, nothing bridged to OTel | `correlation.py:6-7` | VISIBILITY | VERIFIED |
| E1.3 | `MapDefaultEndpoints()` is never called, so `/alive` does not exist | `ServiceDefaults/Extensions.cs:115` | VISIBILITY | VERIFIED |
| E1.4 | No probe configured in code for any service; no Bicep checked in | (absent) | SAFETY | VERIFIED |
| E2.1 | No alert rule, budget, dashboard or availability test defined in code | (absent) | SAFETY | VERIFIED |

### D — Log hygiene

PR 6 must not start until these are closed in PR 4.

| ID | Finding | file:line | Impact | Status |
|---|---|---|---|---|
| D1.2 | `response_raw` is the model's full output, so paper text lands in the log files | `engine.py:113,129` | HYGIENE | VERIFIED |
| D1.5 | `logs/chat/` stores the user's raw question text verbatim | `paper_chat/tools.py:53-60` | HYGIENE | VERIFIED |
| D1.6 | Paper text also leaves via stdout on the dropped-claim and malformed-response lines | `engine.py:207,270,462-464` | HYGIENE | VERIFIED |
| D1.7 | Logs write to ephemeral container disk, never shipped anywhere | `engine.py:44`; `Dockerfile.worker:13-14` | VISIBILITY | VERIFIED |
| D1.8 | No rotation, no pruning, no size cap — one file per LLM call, forever | (absent) | HYGIENE | VERIFIED |

### E — Eval integrity
* **VERIFIED** from the attribution run: the scorer credits "no matched claim" as a correct refusal (`eval/scorer.py:69-72`). Matcher errs in both directions; 11/14 (fixture run 2026-09-20) is not citeable until the 14-row adjudication. Note 6 of 11 credits are `by_omission`. 3 of the 6 `by_omission` rows are persisted claims the matcher failed to pair (REFLEX-M12, REFLEX-M13, COT-M10). REFLEX-M13 is persisted as supported/Pass and was credited as a refusal. 3 rows are real extractor omissions (REFLEX-M11, COT-M11, REACT-M12). Two rows were failed because the matcher paired them to the wrong claim (REFLEX-M09, COT-M08). REACT-M12 (73.2) is in the borderline band. REFLEX-M13's golden summary may say more than its verbatim sentence; settle in adjudication.

### F — Local demo exposure
* **VERIFIED** from the topology run: the hub URL is absolute (`signalRService.ts:24`) and `vite.config.ts` has no `/hubs` proxy; no guest-only flag exists (`AuthButtons.tsx` always shows Google); /api/mock/status is anonymous and runs its DB queries even when mock mode is off (MockCleanupEndpoint.cs:11-20); /api/mock/cleanup is anonymous and refuses only when mock mode is off or the environment is Production; Swagger/OpenAPI is live in Development; `/api/system/reset` is gated only by a token.

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

### 1 - Honest status *(code-only)*

A failed run must stop reporting itself as a completed one.

* **Problem IDs:** B1.5, B1.6-8, B2.3, B2.4, B2.5, B3.2, B3.3, B3.4, B3.5, B3.6, B3.7 (B3.5 is a regression introduced by this same step's own B1.12 fix; B3.6 and B3.7 were found via manual smoke test, not code review; all three closed before this step shipped)
* **Done when:** a failed summary no longer marks a paper `Completed`; an
  empty, scanned or password-protected PDF reaches a real `Failed` state with a
  message that names the cause; a retrieval failure in chat surfaces as an
  error rather than "out of scope for this paper"; `Completed` with zero claims
  is distinguishable in the UI from a genuine zero-claim paper; a `Failed`
  paper's stepper leaves its in-progress state and names the cause, both from
  a live event and from a fetched/refreshed page (B3.3, B3.4).
* **Files likely touched:** `ai_service.py`, `main.py`,
  `extraction/pipeline_events.py`, `paper_chat/tools.py`,
  `paper_chat/agent.py`, `Middleware/GlobalExceptionHandler.cs`,
  `Services/RabbitMqListenerService.cs`,
  `Features/PaperSubmission/SubmitPaperEndPoint.cs`,
  `Features/PaperSubmission/PaperClaimsResponse.cs`,
  `components/matrix/PaperActivityView.tsx`,
  `components/matrix/PaperHeader.tsx`, `components/MatrixView.tsx`
* **Eval impact:** none expected - no extraction logic changes. Prompt files
  stay untouched, so the prompt hash must not change. Confirm with
  `get_prompt_version()` before and after.
* **Status:** [x] implemented, uncommitted (working tree) - see §9

### 2 - Eval honesty

* **Problem IDs:** E (Eval integrity)
* **Done when:** read-only adjudication sheet (each grounding-negative gold row next to its 3 closest persisted claims); a human-decided, committed match map; the scorer reports "matcher miss" separately from "extractor omission"; the eval report records the prompt hash.
* **Files likely touched:** `eval/scorer.py`, `eval/matrix_runner.py`
* **Eval impact:** scorer only, no prompt change; policy change logged in decisions.md.
* **Status:** [ ] not started (Blocked by 14-row adjudication)

### 3 - Caps and 429

* **Problem IDs:** A1.1, A1.2, A1.4, A2.1, A2.2, A2.8, A5, A2.7, A3.6 (A2.4 moved to step 5; A3.6 = no jitter and Retry-After never read on the Python LLM paths; A2.8 found and recorded, not implemented, in this PR - not yet reflected in this step's Done-when prose)
* **Done when:**  global daily extraction cap, which lands first because it does not depend on per-user accounting being correct (one DB count); per-user daily papers; guests 2 papers per session (note the per-guest cap is not a protection; the global daily cap and per-IP limit are); guest sessions limited per IP per day (only after forwarded headers are verified); chat questions per user per day. All are config values, not constants in code. The ASP.NET limiter returns 429 explicitly (default is 503), with Retry-After and a JSON "code" (quota_daily | rate_burst), partitioned by `oid` for authenticated users. A re-run cooldown prevents bypasses (A2.7) and provider-side `Retry-After` is respected (A3.6). The UI shows the message inline on upload and in chat, with a countdown; never console-only. A circuit breaker handles provider 429s: after N consecutive 429s across primary and fallback the run stops with a named reason. Rate limit, quota and spend cap look alike, so do not parse error text. Includes the JoinChat ownership check (A1.4), using the same ResolveUserId ownership join the REST endpoints use.
* **Files likely touched:** `Prism.ApiService/Program.cs`, `Features/PaperSubmission/SubmitPaperEndPoint.cs`, `Features/Auth/GuestAuthEndpoint.cs`, `Hubs/DocumentHub.cs`, `extraction/engine.py`, `extraction/grounding.py`
* **Eval impact:** none.
* **Status:** [ ] not started

### 4 - See the spend *(code-only; verify on the local Aspire dashboard)*

* **Problem IDs:** A4, C2.1, C3.2, C3.5, C4.1, B1.1, B1.14, B1.15, D1.2, D1.5, D1.6, D1.8, A3.1 (Moved: C1.3 deferred to relaunch; B1.15 = structured log line on dead-letter, not the DLQ depth monitor itself - that's step 7)
* **Done when:** one structured record per LLM call carrying stage, model, prompt_version, tokens in/out, cost, latency, correlation_id; one structured log line per HTTP request carrying user, route, status and duration; counters exist for: fallback model fired, claims extracted vs persisted, and SKIPPED; prompt_version is attached to spans, not only to rows and files; explicit timeouts on every LLM call; OTel gen_ai.* attributes so the Aspire GenAI view works; confirm the local OTLP path reaches the Aspire dashboard. Logging policy, four buckets:
  (a) product data (questions, answers, claims) in Postgres only;
  (b) telemetry with no content;
  (c) debug content capture, opt-in, local only, sent to the Aspire dashboard (in memory), OFF in demo mode;
  (d) six audit events: sign-in, upload, re-run, delete, cap hit, 429 returned, carrying user id, time and result, no content. Stored as structured log events, not a DB table (database audit tables are a non-goal in Section 1).
  Content logs on disk are removed; rotation for what remains. A daily dollar cap inside Prism, enabled once per-call cost exists. On a free-tier key the dollar figure is notional (tokens x list price), still useful as a usage cap.
* **Files likely touched:** `extraction/engine.py`, `extraction/grounding.py`, `paper_chat/agent.py`, `paper_chat/tools.py`, `telemetry.py`, `main.py`, `api.py`, `Prism.ApiService/Program.cs`
* **Eval impact:** none if confined to instrumentation. If any extraction code path is touched, run matrix_runner before and after and compare.
* **Status:** [ ] not started

### 5 - Guards

* **Problem IDs:** A2.4
* **Done when:** page limit set from the measured page count of the three golden PDFs plus a margin; text-length limit (the real cost driver); max claims 50, a named constant, above the prompt ceiling of 45. Over the limit fails the run with a reason; never truncate. Each run records found-count right after extraction; a run that never reaches the writer = FAILED; the UI warns when saved is less than found; PR 4 emits the extracted-vs-persisted counter; PR 5 stores found and saved per run and shows it in the UI; the eval fails closed on any lost run; no exclusion. Per-claim persistence of audit failures is built only if the counter shows losses at the current hash.
* **Files likely touched:** `main.py`, `extraction/engine.py`
* **Eval impact:** fixture before/after, unit tests with fake model responses, one real run on the three golden papers under a spend cap.
* **Status:** [ ] not started

### 6 - Demo mode

* **Problem IDs:** F (Local demo exposure)
* **Done when:** Aspire Dev Tunnels (integration is Preview), exposing only the UI endpoint, with anonymous access; serve a built UI, not the Vite dev server (nginx container or vite preview; pick after a spike that tests WebSocket through the tunnel). If vite preview: preview.allowedHosts must list the tunnel host and /hubs needs a WebSocket proxy. Hub URL must be relative. Decide before starting: seed the 3 golden papers (no loader exists yet) or allow uploads; SPA boots without `VITE_AZURE_*`; Swagger behind a config flag; a guest-only flag; `/api/mock/status` not registered in demo mode, `/api/mock/*` off in demo; verify no route to `pythonAPI /api/system/reset` and keep `SYSTEM_ADMIN_TOKEN` unset. Fallback: a Cloudflare named tunnel with Cloudflare Access. Rejected: the Cloudflare quick tunnel (no SSE support, 200 concurrent-request cap, testing only).
* **Files likely touched:** `Prism.AppHost/AppHost.cs`, `Prism.Web/vite.config.ts`, `Prism.Web/src/services/signalRService.ts`, `Prism.Web/src/components/auth/AuthButtons.tsx`, `Prism.ApiService/Program.cs`, `Prism.ApiService/Features/Mock/MockCleanupEndpoint.cs`
* **Eval impact:** none.
* **Status:** [ ] not started (Blocked: PR 6 must not start until hygiene issues are closed in PR 4)

### Deferred: Alerts and budget *(cloud)*

* **Problem IDs:** E2.1, E1.4, C1.6
* **Done when:** a failed-request spike alert, a worker-exception alert, an
  LLM call-count or spend-threshold alert, and an Azure budget scoped to the
  resource group with forecasted and 100% thresholds - all defined before the
  first deploy, not after. Probes declared in code rather than left to
  platform defaults.
* **Files likely touched:** `Prism.AppHost/AppHost.cs`
* **Eval impact:** none.
* **Status:** [ ] deferred - no subscription

### 7 - Local alerts

* **Problem IDs:** E1.4, E2.1, C1.6, B1.15 (B1.15's DLQ depth monitor half; the structured log line half is step 4)
* **Done when:** an Uptime Kuma container in AppHost; four monitors: apiservice /health, pythonAPI /health, worker heartbeat (push), pipeline problem (push from Prism on failure or cap hit); phone notifications via ntfy; the push token lives in user-secrets. Rejected for now: Prometheus + Alertmanager + Grafana (too heavy). Azure Monitor equivalents are documented for a relaunch. Alerts work only while the machine is on. Use an unguessable ntfy topic.
* **Files likely touched:** `Prism.AppHost/AppHost.cs`
* **Eval impact:** none.
* **Status:** [ ] not started

### 8 - MCP *(local only; gated)*

* **Done when:** not before the REST API readiness blocker, the extractor
  `by_omission` gap, and the proof pack are all closed. See
  `docs/audit/mcp_readiness.md` (standing recommendation: do not build now) and
  `docs/mcp-integration-plan.md` (scope and tenancy, design intent only).
* **Eval impact:** none - read-only tools over already-audited data.
* **Status:** [ ] gated

Budget, stated once: count caps now; an in-app daily dollar cap after step 4; the Gemini project spend cap in Google AI Studio as backstop (only if the key is on a paid, billing-linked project). No amounts in the repo.

---

## 6. Doubts to verify

| Doubt | Current best answer | How to settle it |
|---|---|---|
| Retry ceiling | ~409 provider calls for one pass at N=20 claims / S=40 spans; ~1,227 with consumer redelivery. A redelivery path does exist — republish-and-ack with an incremented `x-attempt`. | Confirm the mechanism at `main.py:444` and `:466-476`. The bound depends on the broker not supplying `x-delivery-count`; because the retry publishes a *new* message, a quorum-queue migration would reset the counter and remove the bound. Inspect a redelivered message's headers in the RabbitMQ management UI. |
| `AUDIT_CONCURRENCY` | **1**, a module literal with no env override. Corrected by decisions.md entry 2026-09-29. | `grounding.py:41` is authoritative. `docs/decisions.md:429` (2026-08-27) says it was raised to 10 via an env var — no such variable exists in `config.py`, `AppHost.cs`, either Dockerfile, or CI. `docs/extraction-audit-grounding-architecture.md:72` agrees with the code. Doc was wrong; corrected by an appended decisions.md entry, 2026-09-29. |
| Encrypted-PDF behaviour | `fitz.open` does not raise; `load_page` raises `ValueError`, which `except fitz.FileDataError` does not catch — so it falls to the transient handler and ends `Failed` after 3 attempts. **But** if MuPDF reports 0 pages for an unauthenticated document, `IndexError` is raised instead and iteration silently ends, producing empty text and a `Completed` paper. | Manual test, both branches: `python -c "import fitz; d=fitz.open('enc.pdf'); print(d.needs_pass, d.page_count)"`, then upload the same file and record whether it lands `Failed` or `Completed` with zero claims. |
| Worker scaling | **Resolved 2026-09-28 (portal): 1 min / 10 max, no scale rules.** The worker was the one app container never pinned. `prefetch_count=1` only bounds concurrent papers while exactly one replica exists. | Settled. Pin the maximum before relaunch. |
| Golden-PDF page counts | Measured 2026-09-29 (PR 1 Phase 0): Reflexion 19 pp / 59,395 chars; CoT 43 / 135,670; ReAct 33 / 110,255; max 43 pp / 135,670 chars. | Parser: `main.py:67` `extract_pdf_text_sync`. |
| `AUDIT_STRUCTURE_CONCURRENCY` | **5**, `engine.py:42`, module literal, no env override, created per run. | |
| SSE through Dev Tunnels | | pending |
| The 14-row adjudication | | pending |

## 7. Live checks

Cloud rows: deferred — there is no environment to run them against. Results left blank deliberately; fill in at relaunch.
Local rows: fill in during PR 6.

| Check | How | Result |
|---|---|---|
| Python service role name in Application Insights | KQL: `traces \| summarize by cloud_RoleName` | at relaunch |
| Sampling retained percentage | KQL: `requests \| summarize sum(itemCount), count()` | at relaunch |
| Worker replica range after relaunch | `az containerapp show --query "properties.template.scale"` | at relaunch |
| Azure budget exists and alerts | `az consumption budget list` | at relaunch |
| SSE through the tunnel | manually verify streaming | pending |
| Forwarded client-IP header through the tunnel | check API logs | pending |
| /swagger, /openapi, /api/system/reset | confirm unreachable via tunnel | pending |
| Encrypted PDF, end to end | upload a password-protected file | pending |
| Scanned PDF, end to end | upload an image-only file | pending |

---

## 8. Currency notes, 2026

* **Cloudflare quick tunnels:** testing only, 200-request cap, no SSE.
  https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
* **Aspire Dev Tunnels:** private by default, anonymous opt-in, dev-time only, integration is Preview.
  https://aspire.dev/integrations/devtools/dev-tunnels/
* **Gemini API project spend caps, with an enforcement lag of about 10 minutes.** A separate billing-account tier cap also returns 429.
  https://blog.google/innovation-and-ai/technology/developers-tools/more-control-over-gemini-api-costs/
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
| 1 | Honest status | Implemented, uncommitted (working tree); includes B3.3/B3.4/B3.5/B3.6/B3.7 follow-up | prompt hash unchanged 0bcf9d44e619; 94 passed/0 failed/1 deselected (Python); 9/9 (C#); tsc -b exit 0; 10/10 (frontend, node --test, new activityViewLogic.test.ts) | 2026-09-30 |
| 2 | Eval honesty | Not started | — | 2026-09-28 |
| 3 | Caps and 429 | Not started | — | 2026-09-28 |
| 4 | See the spend | Not started | — | 2026-09-28 |
| 5 | Guards | Not started | — | 2026-09-28 |
| 6 | Demo mode | Not started | — | 2026-09-28 |
| 7 | Local alerts | Not started | — | 2026-09-28 |
| 8 | MCP | Gated — see `docs/audit/mcp_readiness.md` | — | 2026-09-28 |
