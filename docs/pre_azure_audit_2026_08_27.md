# Prism Pre-Azure Deployment Audit Report
**Date:** August 27, 2026  
**Auditor:** Antigravity AI (Pair Programmer)  
**Scope:** `Prism.PythonService/`, `Prism.ApiService/`, `Prism.Web/`, `Prism.AppHost/`, `docs/`  
**Mode:** Deep Read-Only Audit (No Code Edits, No Dependency Changes)  
**Status:** Resolved in PR 1 (`feat/azure-pre-deploy-foundation`) on 2026-08-29. Kept for historical audit trail.

---

## Executive Summary

Prism has completed V1 engineering across its core extraction pipeline, grounding tuning (Slice 2.8), Matrix UI, paper activity view, and paper-scoped chat. Before deploying to Azure Container Apps, this audit evaluated code quality, architecture, folder structure, dependency hygiene, and cloud deployment readiness against August 2026 production standards (Python 3.13 + `uv`, .NET 10 Minimal APIs, React 19 + Vite, FastAPI, and LangGraph).

A total of **29 findings** were identified across 4 ranked categories:
- **BLOCKERS (8):** Issues that will cause container startup failures, routing crashes, cross-origin blocks, or critical security vulnerabilities in Azure Container Apps.
- **HIGH IMPACT (9):** Significant quality, performance, or hygiene issues that would fail portfolio/code reviews.
- **NICE TO HAVE (9):** Post-V1 cleanup items and minor structural refinements.
- **FALSE POSITIVES / DELIBERATE CHOICES (3):** Code patterns that appear flawed at first glance but are documented architectural decisions or transition states.

---

## 1. BLOCKERS — Must Fix Before Azure

Things that would break in production, cause deployment failures, or introduce severe security flaws.

### [B1] Hardcoded Localhost CORS Policy
- **File:Line:** [Prism.ApiService/Program.cs:L80](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L80)
- **Current State:**
  ```csharp
  policy.WithOrigins("http://localhost:7000")
  ```
- **What's Wrong:** All web client requests originating from the production Azure Container Apps domain will be rejected by browser CORS checks.
- **Suggested Fix:** Bind CORS allowed origins to a configurable environment variable (`AllowedOrigins`) or Azure Container Apps frontend domain.

### [B2] Hardcoded Aspire Internal Service Config Index
- **File:Line:** [Prism.ApiService/Program.cs:L73](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L73)
- **Current State:**
  ```csharp
  client.BaseAddress = new Uri(builder.Configuration["services:prism-ai-pythonAPI:pythonapi:0"]!);
  ```
- **What's Wrong:** Direct lookup of Aspire's local `:0` endpoint index fails outside the local Aspire orchestrator.
- **Suggested Fix:** Read the Python service URL from a standard environment variable (e.g. `PYTHON_API_URL`) with fallback to `IConfiguration`.

### [B3] Hardcoded Aspire Environment Keys in Vite Proxy
- **File:Line:** [Prism.Web/vite.config.ts:L11](file:///H:/Work%20projects/Prism/Prism.Web/vite.config.ts#L11)
- **Current State:**
  ```typescript
  const target = env.services__apiservice__https__0 || env.services__apiservice__http__0;
  ```
- **What's Wrong:** Vite proxy configuration breaks during standalone production builds or preview modes when Aspire internal env keys are absent.
- **Suggested Fix:** Fall back to a standard `VITE_API_BASE_URL` environment variable.

### [B4] Missing Health Check Endpoints
- **File:Line:** [Prism.ApiService/Program.cs:L16](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L16) & [Prism.PythonService/api.py:L40](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L40)
- **Current State:** Neither backend service registers a dedicated health check endpoint.
- **What's Wrong:** Azure Container Apps liveness and readiness probes will fail, causing container deployment timeouts or infinite restart loops.
- **Suggested Fix:** Register `/health` GET endpoints returning HTTP 200 in both C# ApiService and FastAPI `api.py`.

### [B5] Unauthenticated System Reset Endpoint Exposed
- **File:Line:** [Prism.ApiService/Features/System/SystemEndPoint.cs:L15](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/System/SystemEndPoint.cs#L15) & [Prism.PythonService/api.py:L205](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L205)
- **Current State:**
  ```csharp
  app.MapDelete("/api/system/reset", async (PrismDBContext db...) => { await db.Database.ExecuteSqlRawAsync("TRUNCATE TABLE \"prism_documents\" CASCADE;"); ... })
  ```
- **What's Wrong:** Anyone on the public internet can send a `DELETE /api/system/reset` request to wipe all Postgres tables, Qdrant vectors, and LangGraph memory without authentication.
- **Suggested Fix:** Disable this nuclear endpoint in production or protect it behind an administrative authorization guard.

### [B6] Database Startup Migration Execution
- **File:Line:** [Prism.ApiService/Program.cs:L97](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L97)
- **Current State:**
  ```csharp
  await service.Database.MigrateAsync();
  ```
- **What's Wrong:** Running EF Core migrations directly on application startup causes database lock contention and failures when multiple Container App replicas launch simultaneously.
- **Suggested Fix:** Remove `MigrateAsync()` from process startup and execute migrations via a deployment pipeline task or init container.

### [B7] Python Dockerfile Missing Lockfile Validation and Dockerignore
- **File:Line:** [Prism.PythonService/Dockerfile:L5](file:///H:/Work%20projects/Prism/Prism.PythonService/Dockerfile#L5)
- **Current State:**
  ```dockerfile
  RUN uv pip install --system .
  ```
- **What's Wrong:** Installs un-frozen package versions, lacks `.dockerignore` (baking local `downloads/`, `logs/`, and `.pytest_cache` into the image), and fails to define a container entrypoint for `main.py` worker.
- **Suggested Fix:** Add a `.dockerignore` file, use `uv sync --frozen` for locked builds, and create container entrypoints for both API and worker processes.

### [B8] Missing Dockerfiles for ApiService and Web UI
- **File:Line:** `Prism.ApiService/` & `Prism.Web/`
- **Current State:** No `Dockerfile` exists for either `Prism.ApiService` or `Prism.Web`.
- **What's Wrong:** Azure Container Apps cannot deploy `Prism.ApiService` or `Prism.Web` without container build manifests.
- **Suggested Fix:** Add multi-stage Dockerfiles for `Prism.ApiService` (.NET 10 ASP.NET Runtime) and `Prism.Web` (Nginx static content host).

---

## 2. HIGH IMPACT — Should Fix Before Azure

Real quality, performance, and hygiene issues visible in code review that degrade stability or operational observability.

### [H1] Synchronous Vector Search Blocking Async Loop
- **File:Line:** [Prism.PythonService/paper_chat/tools.py:L146](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L146) & [Prism.PythonService/agent_service.py:L126](file:///H:/Work%20projects/Prism/Prism.PythonService/agent_service.py#L126)
- **Current State:**
  ```python
  hits = ragservice.search_db(user_query=query, limit=limit, file_id=active_file_id)
  ```
- **What's Wrong:** Synchronous embedding generation and HTTP calls run directly on FastAPI's main asyncio event loop, blocking concurrent request handling.
- **Suggested Fix:** Wrap calls to `ragservice.search_db` in `asyncio.to_thread(...)` or switch to an asynchronous Qdrant client.

### [H2] Synchronous EF Core Query in Async Handler
- **File:Line:** [Prism.ApiService/Features/Chat/ChatEndPoint.cs:L124](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/Chat/ChatEndPoint.cs#L124)
- **Current State:**
  ```csharp
  var existingRecord = prismDBContext.PrismDocuments.FirstOrDefault(a=>a.ChatId==Guid.Parse(request.chatId));
  ```
- **What's Wrong:** Synchronous `.FirstOrDefault(...)` blocks the ASP.NET Core thread pool during async endpoint execution.
- **Suggested Fix:** Replace `.FirstOrDefault` with `await ... FirstOrDefaultAsync(...)`.

### [H3] Qdrant Collection Name Mismatch
- **File:Line:** [Prism.PythonService/RAGService.py:L16](file:///H:/Work%20projects/Prism/Prism.PythonService/RAGService.py#L16) vs [Prism.PythonService/api.py:L210](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L210)
- **Current State:**
  `RAGService.py` uses `self.collection_name = "prism_docs"`, while `api.py` attempts to delete `collection_name="prism_collection"`.
- **What's Wrong:** Reset operations target a non-existent collection while leaving active vectors intact in `prism_docs`.
- **Suggested Fix:** Define collection name as a single shared constant across all Python modules.

### [H4] Rogue Print Statements and Missing Structured Logging
- **File:Line:** [Prism.PythonService/main.py:L75](file:///H:/Work%20projects/Prism/Prism.PythonService/main.py#L75) & [Prism.PythonService/api.py:L17](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L17)
- **Current State:**
  ```python
  print("[...] Initializing Database and AI Agent...", flush=True)
  ```
- **What's Wrong:** Console `print()` outputs lack log levels, timestamps, and structured JSON formatting required for Azure Application Insights aggregation.
- **Suggested Fix:** Standardize on Python's built-in `logging` module with structured JSON formatting.

### [H5] Unhandled Guid.Parse Exceptions on API Inputs
- **File:Line:** [Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs:L191](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs#L191) & [Prism.ApiService/Features/Chat/ChatEndPoint.cs:L124](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/Chat/ChatEndPoint.cs#L124)
- **Current State:**
  ```csharp
  var chatGuid = Guid.Parse(chatId);
  ```
- **What's Wrong:** Malformed `chatId` input strings throw unhandled `FormatException` 500 errors instead of clean 400 Bad Request responses.
- **Suggested Fix:** Use `Guid.TryParse` and return `Results.BadRequest("Invalid chatId format")` when parsing fails.

### [H6] Fragile Manual MinIO Connection String Parsing
- **File:Line:** [Prism.ApiService/Program.cs:L47](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L47)
- **Current State:**
  ```csharp
  var settings = connectionString!.Split(";").Select(part=> part.Split("=")).ToDictionary(split => split[0], split => split[1]);
  ```
- **What's Wrong:** Throws `IndexOutOfRangeException` or `NullReferenceException` if Azure storage connection strings alter key ordering or format.
- **Suggested Fix:** Use `DbConnectionStringBuilder` or standard `IConfiguration` binding to parse connection string parameters safely.

### [H7] Missing React Error Boundary
- **File:Line:** [Prism.Web/src/App.tsx:L9](file:///H:/Work%20projects/Prism/Prism.Web/src/App.tsx#L9)
- **Current State:** `<AppShell />` is rendered directly without an Error Boundary wrapper.
- **What's Wrong:** Any unhandled UI error or SSE parsing failure crashes the entire React application into a blank screen.
- **Suggested Fix:** Wrap `AppShell` with a top-level `<ErrorBoundary>` component showing a user-friendly recovery UI.

### [H8] Multiple Uncoordinated Postgres Connection Pools
- **File:Line:** [Prism.PythonService/memory_db.py:L14](file:///H:/Work%20projects/Prism/Prism.PythonService/memory_db.py#L14), `writer.py`, `paper_chat/tools.py`, `main.py`, `api.py`
- **Current State:** `create_db_connection_pool()` is called independently across multiple modules, creating separate `AsyncConnectionPool` instances.
- **What's Wrong:** Creates redundant database connection pools per process, exhausting Postgres connection limits in production environments.
- **Suggested Fix:** Instantiate a single shared connection pool and inject it via FastAPI `app.state` or central module singleton.

### [H9] Duplicate OpenAPI Package References in C#
- **File:Line:** [Prism.ApiService/Prism.ApiService.csproj:L15](file:///H:/Work%20projects/Prism/Prism.ApiService/Prism.ApiService.csproj#L15) & [Prism.ApiService/Prism.ApiService.csproj:L22](file:///H:/Work%20projects/Prism/Prism.ApiService/Prism.ApiService.csproj#L22)
- **Current State:** References both `Microsoft.AspNetCore.OpenApi` (10.0.1) and `Swashbuckle.AspNetCore` (10.1.0).
- **What's Wrong:** Swashbuckle is deprecated in .NET 9/10 minimal APIs, creating duplicate OpenAPI routes and unnecessary dependency bloat.
- **Suggested Fix:** Remove `Swashbuckle.AspNetCore` and use `Microsoft.AspNetCore.OpenApi` exclusively.

---

## 3. NICE TO HAVE — Post-V1 Cleanup

Minor improvements, dependency cleanup, and code organization refinements.

### [N1] Unused Dependencies in Python `pyproject.toml`
- **File:Line:** [Prism.PythonService/pyproject.toml:L22-L25](file:///H:/Work%20projects/Prism/Prism.PythonService/pyproject.toml#L22-L25)
- **Current State:** Declares `"pika>=1.3.2"`, `"psycopg-binary>=3.3.3"`, and `"psycopg-pool>=3.3.0"`.
- **What's Wrong:** Dependencies are redundant (`psycopg[binary,pool]` already covers pool and binary, and `pika` is unused in favor of `aio-pika`).
- **Suggested Fix:** Remove duplicate package specifications from `pyproject.toml`.

### [N2] Unused Redis Provisioning in AppHost
- **File:Line:** [Prism.AppHost/AppHost.cs:L6](file:///H:/Work%20projects/Prism/Prism.AppHost/AppHost.cs#L6) & [Prism.ApiService/Prism.ApiService.csproj:L11](file:///H:/Work%20projects/Prism/Prism.ApiService/Prism.ApiService.csproj#L11)
- **Current State:** `var cache = builder.AddRedis("redis-cache");` provisions Redis without any active caching logic in ApiService.
- **What's Wrong:** Consumes container memory and resources for unused infrastructure.
- **Suggested Fix:** Remove Redis container definition until caching logic is actively implemented.

### [N3] Unused FakeFileUploader DI Registration
- **File:Line:** [Prism.ApiService/Program.cs:L37](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L37) & [Services/FakeFileUploader.cs:L3](file:///H:/Work%20projects/Prism/Prism.ApiService/Services/FakeFileUploader.cs#L3)
- **Current State:** `builder.Services.AddScoped<IfileUploader,FakeFileUploader>();`
- **What's Wrong:** Registers a mock file uploader service that is never injected by any API endpoint.
- **Suggested Fix:** Remove `FakeFileUploader.cs` and its DI registration.

### [N4] Empty `IChatDatabaseService` Interface
- **File:Line:** [Prism.ApiService/Services/IAddChatDataBaseService.cs:L3](file:///H:/Work%20projects/Prism/Prism.ApiService/Services/IAddChatDataBaseService.cs#L3)
- **Current State:** `public interface IChatDatabaseService { }` (0 members)
- **What's Wrong:** Dead, empty interface file left in the project.
- **Suggested Fix:** Delete `IAddChatDataBaseService.cs`.

### [N5] Oversized `ChatMode.tsx` Component (>500 lines)
- **File:Line:** [Prism.Web/src/components/ChatMode.tsx:L1-L533](file:///H:/Work%20projects/Prism/Prism.Web/src/components/ChatMode.tsx#L1-L533)
- **Current State:** 533-line single file component.
- **What's Wrong:** Exceeds React component size conventions (>300 lines).
- **Suggested Fix:** Remove or decompose `ChatMode.tsx` into smaller modules.

### [N6] Oversized `PaperChatStrip.tsx` Component (>400 lines)
- **File:Line:** [Prism.Web/src/components/matrix/PaperChatStrip.tsx:L1-L407](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L1-L407)
- **Current State:** 407-line component file combining turn rendering, scroll logic, and input fields.
- **What's Wrong:** Exceeds recommended React component length.
- **Suggested Fix:** Extract `ChatInput` and `AssistantTurn` into standalone files in `src/components/matrix/chat/`.

### [N7] Hardcoded User ID `"demo-user-01"`
- **File:Line:** [Prism.Web/src/components/AppShell.tsx:L15](file:///H:/Work%20projects/Prism/Prism.Web/src/components/AppShell.tsx#L15)
- **Current State:** `const USER_ID = "demo-user-01";`
- **What's Wrong:** Hardcodes a static demo user ID in the UI shell.
- **Suggested Fix:** Inject user identity through an authentication context or prop provider.

### [N8] Redundant `requirements.txt` in Python Service
- **File:Line:** `Prism.PythonService/requirements.txt`
- **Current State:** File exists alongside `pyproject.toml` and `uv.lock`.
- **What's Wrong:** Duplicates dependency definitions in a `uv`-managed workspace.
- **Suggested Fix:** Remove `requirements.txt` and rely solely on `pyproject.toml` and `uv.lock`.

### [N9] Conflicting `pnpm-workspace.yaml` in npm Project
- **File:Line:** `Prism.Web/pnpm-workspace.yaml`
- **Current State:** `package.json` specifies `"packageManager": "npm@11.16.0"` while `pnpm-workspace.yaml` remains in the directory.
- **What's Wrong:** Conflicting package manager configuration files in the web project.
- **Suggested Fix:** Delete `pnpm-workspace.yaml`.

---

## 4. FALSE POSITIVES / DELIBERATE CHOICES

Things that look wrong at first inspection but are deliberate architectural choices or documented transition states. **Do not add these to fix lists.**

### [FP1] Legacy Chat Code Scheduled for Slice 3c Deletion
- **Files:** `Prism.PythonService/ai_service.py`, `Prism.PythonService/agent_service.py`, `Prism.ApiService/Features/Chat/ChatEndPoint.cs` (`/api/chat/ask`), `Prism.Web/src/components/ChatMode.tsx`
- **Why It Looks Wrong:** Contains deprecated `google-generativeai` imports, un-routed endpoints, and unreachable UI components.
- **Why It's Deliberate:** Retained intentionally for backwards compatibility until the scheduled Slice 3c deletion PR, as explicitly noted in codebase docstrings and user context.

### [FP2] Dual Gemini Model Usage (`LLM_EXTRACTION_MODEL` vs `LLM_AUDIT_MODEL`)
- **File:** `Prism.PythonService/extraction/engine.py:L153-L168`
- **Why It Looks Wrong:** Appears to be inconsistent model configuration (`gemini-3.6-flash` vs `gemini-3.1-flash-lite`).
- **Why It's Deliberate:** Intentional tiered model fallback strategy designed to optimize API quota management and execution speed across extraction steps.

### [FP3] Direct `litellm` Usage for Groq Audit Calls
- **File:** `Prism.PythonService/extraction/grounding.py:L344`
- **Why It Looks Wrong:** Uses `litellm.acompletion` alongside direct `google-genai` SDK calls.
- **Why It's Deliberate:** Documented decision in `docs/decisions.md` (August 25, 2026) offloading high-volume span auditing to Groq's 30 RPM free tier with automatic Gemini Flash Lite fallback.

---

## Summary & Action Plan

### 1. Total Findings by Bucket
| Category | Count |
| :--- | :--- |
| **BLOCKERS** | 8 |
| **HIGH IMPACT** | 9 |
| **NICE TO HAVE** | 9 |
| **FALSE POSITIVES** | 3 |
| **TOTAL** | **29** |

### 2. Top 5 Items Overall to Fix First
1. **[B1] Fix CORS Policy in C# ApiService:** Replace hardcoded `http://localhost:7000` with configurable environment variable origin binding ([Program.cs:L80](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L80)).
2. **[B2 & B3] Replace Aspire Internal Index Lookups:** Replace `:0` config key lookups in ApiService and Vite proxy with standard environment variables ([Program.cs:L73](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L73) & [vite.config.ts:L11](file:///H:/Work%20projects/Prism/Prism.Web/vite.config.ts#L11)).
3. **[B4] Add Liveness/Readiness Health Checks:** Add `/health` GET endpoints to `Prism.ApiService` and `Prism.PythonService/api.py`.
4. **[B5] Secure Nuclear System Reset Endpoint:** Protect or disable `/api/system/reset` in production to prevent unauthenticated data wipes ([SystemEndPoint.cs:L15](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/System/SystemEndPoint.cs#L15) & [api.py:L205](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L205)).
5. **[B6] Remove Startup Database Migration:** Move `MigrateAsync()` out of process startup to prevent multi-replica lock deadlocks ([Program.cs:L97](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L97)).

### 3. Estimated Cleanup Effort
- **Blockers Cleanup:** ~6–8 hours
- **High Impact Cleanup:** ~6–8 hours
- **Total Estimated Work:** **~12–16 developer hours (approx. 2 working days)**
