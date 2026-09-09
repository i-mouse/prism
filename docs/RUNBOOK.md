# Prism Developer Runbook

This guide covers common gotchas, troubleshooting steps, and configurations for running and debugging the Prism development environment.

---

## 1. Aspire Postgres Volume Password Drift
* **Symptom:** On launching Aspire, the Postgres container starts, but backend services fail to connect, throwing database authentication or password validation errors.
* **Gotcha:** Aspire automatically configures the database connection with auto-generated passwords stored in user secrets. However, if the local Docker data volumes persist across environment updates or configuration changes, the container's initialized credentials can drift from what Aspire injects.
* **Workaround:**
  1. Find the active database Docker volume:
     ```powershell
     docker volume ls | Select-String "postgres"
     ```
  2. Remove the drifted volume (this will nuke the local database cache and force the container to initialize with the current password secrets on the next boot):
     ```powershell
     docker volume rm <volume-name>
     ```
  3. Relaunch the Aspire stack (`F5` in VS Code or `dotnet run --project Prism.AppHost`) to spin up a clean database.

---

## 2. Gemini Free Tier Quota Limits
* **Symptom:** Worker logs show `429 ResourceExhausted` errors or extraction runs freeze halfway through.
* **Gotcha:** The Gemini free tier has strict rate limits:
  - **Gemini Flash (Extractor/Auditor):** 15 Requests Per Minute (RPM), 1,500 Requests Per Day (RPD).
  - **Gemini Flash Lite (Grounding/Summary):** 15 RPM, 1,500 RPD.
  Because a single PDF ingestion invokes a three-call claim extraction pipeline (~2 Flash calls) plus per-claim grounding audits (~14 Flash Lite calls), you can easily exhaust the free quota after auditing ~10-15 papers in a day.
* **Quota Check:** 
  - Log in to the [Google AI Studio Console](https://aistudio.google.com/) to view active quota charts and check API keys status.
  - If you hit a hard block, wait for the daily quota reset or configure a paid/pay-as-you-go key.

---

## 3. Dynamic Service Ports
* **Symptom:** API calls to Qdrant, MinIO, or RabbitMQ from PowerShell scripts or external tools fail.
* **Gotcha:** Aspire assigns random, dynamic ports to all containerized services (RabbitMQ management, MinIO console, Qdrant Dashboard, pgAdmin) at startup to prevent local port collisions. Do not hardcode these ports in scratch scripts or client applications.
* **Solution:**
  - Open the **Aspire Dashboard** (at the URL printed in the terminal when launching Aspire).
  - Refer to the **Endpoints** column to inspect active ports for the current run and use those.

---

## 4. PowerShell Curl Escaping
* **Symptom:** Triggering chat or upload endpoints via PowerShell `curl` produces JSON parsing errors or target invocation crashes.
* **Gotcha:** In PowerShell, `curl` is an alias for `Invoke-WebRequest`, which processes quote characters in JSON strings incorrectly when passed using the `-d` flag.
* **Solution:** Use native `curl.exe` to bypass the alias, and feed JSON payloads through standard input to avoid character escaping issues:
  ```powershell
  # Example: Triggering a paper-scoped chat query
  @{
      chat_id = "f42b367b-3c9b-4268-9f33-3a1b61e0e37e"
      active_file_id = "f42b367b-3c9b-4268-9f33-3a1b61e0e37e"
      message = "What is the main contribution of this paper?"
  } | ConvertTo-Json | curl.exe -X POST -H "Content-Type: application/json" -d @- http://localhost:<api-port>/api/chat/ask/stream
  ```

---

## 5. VS Code Breakpoint Binding
* **Symptom:** Breakpoints set in TypeScript frontend files or C# backend files appear greyed out and do not trigger.
* **Gotcha:** Breakpoints require correct source maps and debugging host attachments.
* **Solution:**
  - Launch the stack using the configured Aspire launcher in VS Code (`Ctrl+Shift+D` -> choose the Aspire launch configuration -> press `F5`).
  - Make sure the `C# Dev Kit` extension is installed for C# debugging.
  - For Vite/TypeScript UI debugging, breakpoints bind automatically when debugging via the Aspire launcher on Aspire versions 13.4+. If they fail, verify that `sourceMap: true` is enabled in `tsconfig.json` or debug via Chrome DevTools (`F12` in browser).

## 6. Eval Fixture Regeneration (`check_fixture_freshness` failures)

* **Symptom:** `uv run python -m eval.check_fixture_freshness` (or the "Check fixture freshness" CI step) fails for one or more papers in `docs/evals/fixtures/`.
* **Gotcha:** The failure message tells you exactly which of three independent things went stale — read it before picking a fix, since the three paths are not interchangeable and two of them (full regen, re-match) require a live Postgres connection and `LLM_EXTRACTION_MODEL`/`LLM_EVAL_MATCHER_MODEL` etc. in `.env`, while the third (gold-set verify) only needs `AI_API_KEY`.

| Failure message contains | What changed | Fix |
|---|---|---|
| `prompt_hash ... does not match` / "extraction changed" | The extraction prompt files (`prompts/*.md`, `*.json`) changed | Full regen — re-extracts, re-grounds, re-matches, and freezes everything: `uv run python -m eval.dump_fixture --paper all`, then `uv run python -m eval.verify_matcher_gold` (a full regen doesn't populate `matcher_gold_pass_rate` itself — freshness will still flag it as missing until this runs) |
| `matcher_fingerprint ... does not match` / "matcher changed" | Only `LLM_EVAL_MATCHER_MODEL` / `LLM_EVAL_MATCHER_FALLBACK_MODEL` (or a future matcher prompt file) changed — extraction is untouched | Re-match only, no re-extraction: `uv run python -m eval.rematch_fixture --paper all`, then `uv run python -m eval.verify_matcher_gold` |
| `matcher_gold_pass_rate ... matcher gold check failed or never ran` | The matcher was never calibrated against `docs/evals/matcher_gold.json`, or `rematch_fixture` just cleared a stale pass_rate | `uv run python -m eval.verify_matcher_gold` |

* **Why re-match is separate from full regen:** extraction (claims, grounding) and matching (pairing extracted claims to `matrix_eval.json`'s golden rows) are two independent LLM calls. A matcher-only change (model swap, matcher prompt edit) doesn't invalidate the already-extracted claims — re-running the full extraction pipeline just to refresh matches would burn Gemini quota and risk introducing unrelated extraction drift into what should be a narrow change.
* **Why `verify_matcher_gold` is a separate step from `rematch_fixture`:** `rematch_fixture` refreshes a fixture's matches against *real* extracted claims, but that alone says nothing about whether the new matcher is actually *accurate* — that's what the 15-pair hand-labeled gold set in `docs/evals/matcher_gold.json` checks. `rematch_fixture` deliberately clears `matcher_gold_pass_rate`/`matcher_gold_verified_at` when it updates `matcher_fingerprint`, rather than leaving a pass_rate measured under the *old* matcher in place — so `check_fixture_freshness` will correctly demand a fresh `verify_matcher_gold` run before trusting the fixture again.
* **Gold-set pass floor:** 0.9 (90%). If a real run comes in below that, do not commit the fixture update — the matcher itself needs fixing (model or prompt) first, not the freshness gate.
* **None of this touches CI:** the eval harness is fully offline in CI (see `docs/decisions.md`, "Revert live-matcher CI back to frozen-fixture design") — all three regen commands above are run locally by a developer, and only their *output* (the committed fixture JSON) is what CI reads.

## Common deployment failure modes

### PrismSettings field rename crashes on boot
Two-step deploy required. See "Deploying a PR that changes PrismSettings fields" below.

### ImagePullFailure with MANIFEST_UNKNOWN
Docker Desktop DNS/proxy gets stuck between pushes. Symptoms:
- `docker push` returns success but `az acr repository show-tags` doesn't list the tag
- Container App logs show `MANIFEST_UNKNOWN` on repeated pull attempts

Fix: use `az acr build` instead of local Docker for the affected image.
```powershell
az acr build --registry <acr-name> --image "<repo>:<tag>" --file <Dockerfile> .
```
Slower (~2-3 min, builds in Azure) but bypasses local Docker entirely.

### Worker OOMKilled (exit code 137) under load
Symptoms: worker was Healthy, then Activating. `az containerapp logs show --type system` shows `exit code '137' and reason 'ProcessExited'`.

Cause: embedding model + PDF parsing + concurrent LLM calls exceed memory limit. Two concurrent papers is enough to OOM at 4Gi.

Immediate fix:
```powershell
az containerapp update -n prism-ai-pythonworker -g prism-rg --cpu 4.0 --memory 8Gi
```
ACA rule: memory = 2 × CPU exactly.

Root cause fix: reduce `AUDIT_CONCURRENCY` or prefetch, revisit paper-concurrent processing model.

### Revision Healthy but running old image
`az containerapp show --query "properties.template..."` shows *desired* config.
`az containerapp revision list --query "[?properties.active]"` shows *actual* running state.

Always verify with the second after any deploy. Never trust `properties.template`.