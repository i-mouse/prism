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
