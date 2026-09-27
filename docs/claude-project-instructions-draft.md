# Prism Project Instructions

## Product Summary
Prism is an autonomous empirical claim-auditing engine for research papers. It extracts empirical claims from uploaded PDFs and rigorously audits whether each claim is supported by evidence within the same paper. It produces a claim-support matrix with exact citation spans and a paper-scoped chat for interactive questioning. The core value proposition is correct refusal: the engine must confidently reject claims lacking explicit textual support in the paper, rather than fabricating support.

## Architecture (Locked-in Stack)
* **Orchestration:** .NET Aspire 13.4
* **API Gateway:** ASP.NET Core (.NET 10), EF Core 10
* **Worker & Agent:** Python 3.13 (`uv`), FastAPI, LangGraph
* **LLMs:** Gemini 3.6 Flash (Extraction & Audit), Groq/LiteLLM gpt-oss-20b/Gemini 3.5 Flash Lite (Grounding, Router, Summary)
* **Vector & Search:** Qdrant 1.18
* **Data & Messaging:** PostgreSQL 18, RabbitMQ 4.3, Azure Blob Storage (MinIO locally)
* **Frontend:** React 19, TypeScript, Vite, Tailwind CSS

## Current Build State (Shipped vs Not)
### Shipped / Merged to Main
* Azure Container Apps deployment setup (`prism-env`), Managed Identity, Key Vault.
* `fix/entra-idx10511-and-deploy-hardening` and `fix/entra-api-token-audience-scope` (merged as commits `2d0a437` and `925408d`: Entra CIAM authority mismatch, MSAL hardening, .default scope API token acquisition).
* Mid-stream chat tab-switch persistence (`useChatStream.ts` / `MatrixView.tsx` stream store relocation).
* Session-level caching for claims avoiding re-fetch flicker and stale-response races (`usePaperClaims.ts`).
* Google IdP name/email claims mapped correctly from Entra External ID for all new sign-ups and re-registrations.
* Python worker OOM resource limits (4.0 CPU / 8Gi Memory) codified into AppHost.cs.

### Priority Order / Not Yet Shipped
1. Fix extraction auto-retry failure state (currently 3-retry exhaustion reports as "Completed" with 0 claims rather than "Failed").
2. Implement `readiness` probes for DB and Qdrant (post-V1).
3. SignalR Redis backplane for horizontal scaling (currently pinned to 1 replica).

## Constraints
* **Deployment Divergence:** Backend uses `aspire deploy`, but React frontend requires the `Prism.Web/deploy.ps1` manual script due to an upstream Aspire `WithBuildArg` publish bug.
* **Schema boundaries:** LLM-layer models use default Pydantic, while Final-layer models writing to DB must use `ConfigDict(extra="forbid")` for strict validation.
* **Database migrations:** Must NOT run on Container App startup (`RUN_MIGRATIONS_ON_STARTUP=false` in prod) to prevent locking races. Run manually after DB resets via `az containerapp update` toggle.
* **Mock Extraction Mode:** Enabled manually via `Prism.AppHost/AppHost.cs` (`mockExtraction = "false"` by default).

## Known Sharp Edges
* **Legacy Google Accounts:** Existing Google accounts created before the Entra CIAM mapping fix will still see empty name/email claims ("Google User") until they re-register.
* **Postgres password drift:** Aspire auto-generated DB passwords in user secrets can drift from local Docker volumes. Fix is `docker volume rm` on the DB.
* **Visual Studio Debugger Lock:** Detach debugger explicitly, otherwise `dotnet run` fails to update the binary.
* **Aspire Restart Crashes:** Manually running `docker restart` on Aspire containers crashes the DCP orchestrator. Use Aspire's dashboard instead.
* **Blob Storage Collision:** Azure Blob Storage uploads use the raw filename, risking collisions across sessions.

## NOT VERIFIED Details
The following production aspects could not be verified statically during audit:
* reactUI replica count / CPU / memory in prod
* Whether the live container image matches the current `main` HEAD
* Current live value of `RUN_MIGRATIONS_ON_STARTUP`
* Aspire dashboard accessibility in prod
* `CORS_ALLOWED_ORIGINS` env var set on live apiservice
