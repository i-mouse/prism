# Prism Pre-Azure Deployment Audit — Second Pass
**Date:** August 27, 2026  
**Auditor:** Antigravity AI (Pair Programmer)  
**Scope:** Architecture Patterns, Config & Secrets, Observability, Concurrency, Type Safety, Testing, DX, Future-Fit  
**Base Reference:** `docs/pre_azure_audit_2026_08_27.md` (First Pass — No repeat findings)  
**Mode:** Deep Read-Only Audit (No Code Edits, No Dependency Changes)  

---

## Executive Summary

This second-pass audit evaluates Prism's architecture, forward-fit, developer experience, and production-readiness against August 2026 engineering practices. While the first pass targeted immediate cloud deployment blockers (CORS, ports, Dockerfiles, health checks, unauthenticated reset endpoints), this pass focuses on structural integrity, observability, concurrency correctness, type safety, and testing shape.

A total of **21 NEW findings** were identified across 4 ranked categories:
- **BLOCKERS (3):** Critical architectural or security gaps that would break multi-replica deployments or leak sensitive system data in production.
- **HIGH IMPACT (8):** Significant architectural flaws, dead graph nodes, missing OpenTelemetry tracing, lack of test coverage, and unhandled cancellations.
- **NICE TO HAVE (8):** Post-V1 structural polish, DX improvements, and minor code organization refinements.
- **FALSE POSITIVES / DELIBERATE CHOICES (2):** Patterns that appear duplicated or non-standard but are deliberate polyglot or V1 scope choices.

---

## 1. BLOCKERS — Must Fix Before Azure

Critical architectural or security gaps that will fail in multi-replica deployments or expose sensitive internal infrastructure.

### [B1-P2] Missing SignalR Backplane for Multi-Replica Scaling
- **File:Line:** [Prism.ApiService/Program.cs:L56](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L56) & [Prism.ApiService/Services/RabbitMqListenerService.cs:L100](file:///H:/Work%20projects/Prism/Prism.ApiService/Services/RabbitMqListenerService.cs#L100)
- **Current State:**
  ```csharp
  builder.Services.AddSignalR();
  ```
- **Diagnosis:** In-memory SignalR group routing fails in multi-replica Azure Container Apps because progress messages received by worker instance A cannot be dispatched to client sockets connected to instance B.
- **Suggested Fix:** Configure Azure SignalR Service or a Redis Backplane in `Program.cs` for cross-replica message distribution.

### [B2-P2] Unvalidated Startup Environment Variables in Python Service
- **File:Line:** [Prism.PythonService/memory_db.py:L5-L9](file:///H:/Work%20projects/Prism/Prism.PythonService/memory_db.py#L5-L9) & [Prism.PythonService/paper_chat/agent.py:L78-L86](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L78-L86)
- **Current State:**
  ```python
  host = os.environ["PRISM_DB_HOST"]
  ```
- **Diagnosis:** Direct unvalidated `os.environ` indexing causes runtime `KeyError` crashes deep inside request handling rather than failing fast at container startup.
- **Suggested Fix:** Implement a `pydantic-settings` `BaseSettings` class to validate all required environment variables at process launch.

### [B3-P2] Raw Exception Message Leaks in API Errors
- **File:Line:** [Prism.ApiService/Features/Chat/ChatEndPoint.cs:L40](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/Chat/ChatEndPoint.cs#L40) & [Features/System/SystemEndPoint.cs:L33](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/System/SystemEndPoint.cs#L33)
- **Current State:**
  ```csharp
  return Results.InternalServerError(ex.Message);
  ```
- **Diagnosis:** Returning un-sanitized raw exception strings leaks internal database schemas, connection strings, and stack details to external HTTP clients.
- **Suggested Fix:** Sanitize exception messages in production and return standardized RFC 7807 `ProblemDetails` error objects.

---

## 2. HIGH IMPACT — Should Fix Before Azure

Significant quality, performance, and architecture issues visible in code review that degrade observability, testability, or reliability.

### [H1-P2] LangGraph Router Node Executing as Wasted Dead Code
- **File:Line:** [Prism.PythonService/paper_chat/agent.py:L135-L136](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L135-L136)
- **Current State:**
  ```python
  if route != "both":
      print(f" [TOOLS] route_decision={route!r} restricted a tool; calling both anyway")
  ```
- **Diagnosis:** `execute_tools` unconditionally queries both tools regardless of `route_decision`, making the preceding `route_query` LLM call a redundant, cost-incurring dead node.
- **Suggested Fix:** Either enforce `route_decision` during tool execution or remove `route_query` to save latency and token costs.

### [H2-P2] Absence of OpenTelemetry Instrumentation in Python Service
- **File:Line:** [Prism.PythonService/api.py](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py) & [Prism.PythonService/main.py](file:///H:/Work%20projects/Prism/Prism.PythonService/main.py)
- **Current State:** Zero OpenTelemetry SDK setup or instrumentation middleware in the Python service.
- **Diagnosis:** Python background worker and FastAPI service operate as un-traceable black boxes in Azure Application Insights.
- **Suggested Fix:** Add `opentelemetry-instrumentation-fastapi` and OTLP trace exporters to `api.py` and `main.py`.

### [H3-P2] Missing Distributed Correlation ID Propagation Across RabbitMQ
- **File:Line:** [Prism.PythonService/main.py:L177](file:///H:/Work%20projects/Prism/Prism.PythonService/main.py#L177) & [Prism.ApiService/Services/RabbitMqListenerService.cs:L47](file:///H:/Work%20projects/Prism/Prism.ApiService/Services/RabbitMqListenerService.cs#L47)
- **Current State:** Correlation IDs (`ingest-{file_id}`) are generated for local file logs but never injected into RabbitMQ message headers or SignalR payloads.
- **Diagnosis:** End-to-end requests across C# ApiService, RabbitMQ, Python worker, and SignalR cannot be correlated in production logs.
- **Suggested Fix:** Inject `correlation_id` into RabbitMQ headers and forward it through `RabbitMqListenerService` to SignalR clients.

### [H4-P2] Complete Absence of Unit and Integration Tests for C# and React
- **File:Line:** `Prism.ApiService/` & `Prism.Web/`
- **Current State:** Zero test projects (`.csproj`) or test files (`.test.ts`) exist for C# backend endpoints or React UI components.
- **Diagnosis:** Production deployment lacks automated regression testing for API endpoints, EF Core queries, or UI state rendering.
- **Suggested Fix:** Create an xUnit test project for `Prism.ApiService` and set up Vitest for `Prism.Web`.

### [H5-P2] Unhandled Cancellation Tokens in C# Endpoint Handlers
- **File:Line:** [Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs:L18](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs#L18) & [Features/Chat/ChatEndPoint.cs:L25](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/Chat/ChatEndPoint.cs#L25)
- **Current State:** Handlers accept parameters without receiving or forwarding `CancellationToken`.
- **Diagnosis:** Aborted client HTTP requests continue executing expensive storage uploads, database writes, and outbound HTTP calls to completion.
- **Suggested Fix:** Pass `HttpContext.RequestAborted` as `CancellationToken` into all async storage, database, and HTTP client calls.

### [H6-P2] Non-Standard Plain-Text HTTP Error Formatting
- **File:Line:** [Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs:L22](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs#L22)
- **Current State:**
  ```csharp
  return Results.BadRequest("Request is blank");
  ```
- **Diagnosis:** API returns raw unformatted plain strings for bad requests instead of standardized RFC 7807 `ProblemDetails` JSON objects.
- **Suggested Fix:** Standardize error responses using `TypedResults.Problem(...)` or `ProblemDetails`.

### [H7-P2] Missing Multi-Tenant Database Keys and Vector Search Scoping
- **File:Line:** [Prism.ApiService/Data/Schemas/PaperClaim.cs](file:///H:/Work%20projects/Prism/Prism.ApiService/Data/Schemas/PaperClaim.cs) & [Prism.PythonService/RAGService.py:L78](file:///H:/Work%20projects/Prism/Prism.PythonService/RAGService.py#L78)
- **Current State:** Database extraction tables lack tenant foreign keys, and Qdrant search filters only on `file_id`.
- **Diagnosis:** Multi-tenant deployment cannot enforce data isolation at the database schema or vector search level.
- **Suggested Fix:** Add `tenant_id` columns to extraction schemas and include `tenant_id` in Qdrant vector payload filters.

### [H8-P2] Hard Coupling of Extraction Pipeline to Gemini SDK
- **File:Line:** [Prism.PythonService/extraction/engine.py:L26-L27](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/engine.py#L26-L27)
- **Current State:** `from google import genai` is used directly throughout `_call_gemini` in `engine.py`.
- **Diagnosis:** Bypasses the provider-agnostic LiteLLM abstraction used in `grounding.py`, requiring a full rewrite if switching models to Claude or OpenAI.
- **Suggested Fix:** Refactor `engine.py` to route model calls through LiteLLM (`litellm.acompletion`).

---

## 3. NICE TO HAVE — Post-V1 Cleanup

Minor improvements, developer experience enhancements, and structural polish.

### [N1-P2] Monolithic FastAPI File Lacking APIRouter Modules
- **File:Line:** [Prism.PythonService/api.py:L40-L225](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L40-L225)
- **Diagnosis:** All API endpoints are declared directly on `pythonAPI = FastAPI(...)` without modular `APIRouter` separation.
- **Suggested Fix:** Reorganize endpoints into separate router modules under `routers/` (e.g. `routers/chat.py`, `routers/system.py`).

### [N2-P2] Excessive Prop Drilling in React UI Shell
- **File:Line:** [Prism.Web/src/components/AppShell.tsx:L80-L89](file:///H:/Work%20projects/Prism/Prism.Web/src/components/AppShell.tsx#L80-L89)
- **Diagnosis:** `AppShell` passes 8 individual callback and state props down to `Sidebar`.
- **Suggested Fix:** Introduce a lightweight Zustand store for global active paper, chat, and upload state.

### [N3-P2] Hardcoded Verbose Debug Flag in AppHost Configuration
- **File:Line:** [Prism.AppHost/AppHost.cs:L53](file:///H:/Work%20projects/Prism/Prism.AppHost/AppHost.cs#L53)
- **Diagnosis:** `.WithEnvironment("PRISM_DEBUG", "1")` hardcodes verbose debug mode in local worker runs, spamming Aspire console logs.
- **Suggested Fix:** Read `PRISM_DEBUG` from configuration or default to `0` for normal development runs.

### [N4-P2] Raw Console Output Spam in RabbitMQ Listener
- **File:Line:** [Prism.ApiService/Services/RabbitMqListenerService.cs:L45](file:///H:/Work%20projects/Prism/Prism.ApiService/Services/RabbitMqListenerService.cs#L45)
- **Diagnosis:** `Console.WriteLine` prints full raw JSON message payloads to stdout on every pipeline event.
- **Suggested Fix:** Replace `Console.WriteLine` with `_logger.LogDebug(...)`.

### [N5-P2] Untyped `list[dict]` Annotations in LangGraph Agent State
- **File:Line:** [Prism.PythonService/paper_chat/agent.py:L59-L60](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L59-L60)
- **Diagnosis:** `retrieved_claims: list[dict]` and `retrieved_chunks: list[dict]` lack typed schemas, reducing static analysis precision.
- **Suggested Fix:** Replace `list[dict]` with strongly-typed Pydantic models or `TypedDict` definitions.

### [N6-P2] Missing Standalone CLI Run Documentation in README
- **File:Line:** `README.md` & `setup.ps1`
- **Diagnosis:** Setup documentation relies heavily on Windows `winget` and `dev.ps1`, lacking standalone CLI commands for Linux/macOS devs.
- **Suggested Fix:** Add standalone `uv`, `dotnet`, and `npm` CLI execution commands to `README.md`.

### [N7-P2] Overwriting Upload Timestamp on Summary Update
- **File:Line:** [Prism.ApiService/Services/RabbitMqListenerService.cs:L92](file:///H:/Work%20projects/Prism/Prism.ApiService/Services/RabbitMqListenerService.cs#L92)
- **Diagnosis:** `obj.UploadedAt = DateTime.UtcNow;` overwrites the original file upload timestamp upon extraction completion.
- **Suggested Fix:** Preserve `UploadedAt` and add an `UpdatedAt` or `CompletedAt` timestamp column.

### [N8-P2] Null-Forgiving Operators Bypassing Configuration Warnings
- **File:Line:** [Prism.ApiService/Program.cs:L46](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L46), `L63`, `L73`
- **Diagnosis:** `builder.Configuration.GetConnectionString("storage")!` uses `!` to suppress compiler warnings without runtime validation.
- **Suggested Fix:** Bind configuration to strongly-typed `IOptions<T>` classes with startup validation.

---

## 4. FALSE POSITIVES / DELIBERATE CHOICES

Patterns that appear non-standard at first glance but are deliberate architectural choices or documented transition states. **Do not add these to fix lists.**

### [FP1-P2] Polyglot Database Drivers (`psycopg` v3 vs EF Core Npgsql)
- **Files:** `Prism.PythonService/pyproject.toml` & `Prism.ApiService/Prism.ApiService.csproj`
- **Why It Looks Wrong:** Tech-stack duplication accessing the same database.
- **Why It's Deliberate:** Intentional polyglot design: C# ApiService owns EF Core schema migrations, while Python uses lightweight async `psycopg` v3 pools for high-throughput pipeline writes.

### [FP2-P2] React Context vs External State Store (Zustand/Redux)
- **Files:** `Prism.Web/src/contexts/SelectedClaimContext.tsx`
- **Why It Looks Wrong:** State is managed via React Context and top-level hooks rather than Zustand or Redux.
- **Why It's Deliberate:** React Context is entirely sufficient for V1 single-paper audit workflows; adding Zustand/Redux at this stage would introduce unnecessary boilerplate without structural benefit.

---

## Summary & Action Plan

### 1. Total Findings by Bucket (Second Pass)
| Category | Count |
| :--- | :--- |
| **BLOCKERS** | 3 |
| **HIGH IMPACT** | 8 |
| **NICE TO HAVE** | 8 |
| **FALSE POSITIVES** | 2 |
| **TOTAL NEW FINDINGS** | **21** |

---

### 2. Integration into 3-PR Remediation Plan

The second-pass findings integrate directly into the 3-PR remediation sequence:

#### **PR 1: Cloud & Deployment Readiness (Infra + Security)**
- *From First Pass:* CORS policy, Aspire config keys, health checks, unauthenticated system reset protection, startup migration removal, Dockerfiles.
- *NEW from Second Pass:* **SignalR Redis Backplane / Azure SignalR Service configuration ([B1-P2](file:///H:/Work%20projects/Prism/Prism.ApiService/Program.cs#L56))** & **Pydantic BaseSettings startup validation ([B2-P2](file:///H:/Work%20projects/Prism/Prism.PythonService/memory_db.py#L5-L9))**.

#### **PR 2: Concurrency, Observability & Error Handling**
- *From First Pass:* Sync vector search `asyncio.to_thread`, EF Core async queries, Python structured logging, duplicate connection pools.
- *NEW from Second Pass:* **OpenTelemetry Python instrumentation ([H2-P2](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py))**, **Correlation ID propagation across RabbitMQ ([H3-P2](file:///H:/Work%20projects/Prism/Prism.PythonService/main.py#L177))**, **CancellationToken propagation ([H5-P2](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs#L18))**, and **Sanitized ProblemDetails error formatting ([B3-P2](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/Chat/ChatEndPoint.cs#L40) & [H6-P2](file:///H:/Work%20projects/Prism/Prism.ApiService/Features/PaperSubmission/SubmitPaperEndPoint.cs#L22))**.

#### **PR 3: Code Refactoring, Testing & Polish**
- *From First Pass:* OpenAPI cleanup, React Error Boundary, component size decomposition, dependency cleanup.
- *NEW from Second Pass:* **LangGraph Router dead node fix ([H1-P2](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L135))**, **C# xUnit and React Vitest initial test suites ([H4-P2](file:///H:/Work%20projects/Prism/Prism.ApiService/))**, and **Modular FastAPI APIRouter structure ([N1-P2](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L40))**.

---

### 3. Impact on 3-PR Split & Architecture Roadmap
- **No fundamental rewrite of the 3-PR split is needed.** The original 3-PR sequence remains valid.
- **Key Enhancements to PR 1 & 2:** SignalR multi-replica scaling MUST be included in PR 1 to guarantee real-time UI events in Azure Container Apps. OpenTelemetry and Correlation ID propagation MUST be included in PR 2 to ensure complete end-to-end distributed tracing across all microservices.
