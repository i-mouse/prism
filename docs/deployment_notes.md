# Azure Container Apps Deployment Notes

Reference for the actual Azure deployment PR. Captures what this PR (infra +
security foundation) assumes.

## Replica pin

Set `minReplicas=1` and `maxReplicas=1` on all three Container Apps
(apiservice, python-api, python-worker). No SignalR backplane is configured -
in-memory SignalR group routing only works with exactly one apiservice
replica.

## Required env vars

**Prism.ApiService** (`Configuration/PrismSettings.cs`): `PYTHON_API_URL`,
`AllowedOrigins` (comma-separated origin list), `ConnectionStrings__prism-db`,
`ConnectionStrings__messaging`, `ConnectionStrings__storage`. Optional:
`SystemAdminToken` (unset disables `/api/system/reset`, returns 403),
`RUN_MIGRATIONS_ON_STARTUP` (unset/false in prod).

**Prism.PythonService** (`config.py`, both API and worker containers):
`PRISM_DB_HOST/PORT/DATABASENAME/USERNAME/PASSWORD`, `AI_API_KEY`,
`GROQ_API_KEY`, and one `LLM_*` var per pipeline stage
(`docs/audit/model_vars_2026-09-07.md`):
`LLM_EXTRACTION_MODEL` / `LLM_EXTRACTION_FALLBACK_MODEL` (Prompt 1 metadata +
Prompt 2 extractor), `LLM_CLAIM_AUDIT_MODEL` / `LLM_CLAIM_AUDIT_FALLBACK_MODEL`
(Prompt 3 auditor + Prompt 4 structurer), `LLM_GROUNDING_MODEL` /
`LLM_GROUNDING_FALLBACK_MODEL` (span-grounding, Groq primary), `LLM_CHAT_MODEL`,
`LLM_ROUTER_MODEL`, `LLM_SUMMARY_MODEL`. `LLM_AUDIT_MODEL` no longer
exists anywhere - it was dead production config (only `eval/matcher.py` read
it, as the LLM-as-judge; that's now `LLM_EVAL_MATCHER_MODEL` /
`LLM_EVAL_MATCHER_FALLBACK_MODEL`, read directly via `os.environ` in
`eval/matcher.py`, not part of `config.py`/`PrismSettings`, and not injected
into `AppHost.cs` - eval-only, never read in production).
Worker only: `ConnectionStrings__messaging`, `ConnectionStrings__storage`.
Optional: `PORT` (default 8000), `SYSTEM_ADMIN_TOKEN` (unset disables reset,
returns 403). All `LLM_*` vars in `PrismSettings` are required - `config.py`
declares them with no default, so a missing one fails the service at startup
(pydantic `ValidationError`) instead of silently falling back to a stale
model string. Still read as raw env vars (not yet in `config.py`):
`QDRANT_HTTPURI`, `QDRANT_APIKEY` (`RAGService.py`).

`PRISM_DB_PASSWORD` unset (Entra-only Azure Postgres) makes `memory_db.py`
authenticate via `azure_postgresql_auth.psycopg3.AsyncEntraConnection`,
which fetches a fresh Managed Identity token per connection instead of once
at pool creation - see `docs/prism_final_audit_2026-09-07.md` §3.1.

**Prism.Web**: `VITE_API_BASE_URL` (Docker build arg, baked into the static
bundle at build time - not a runtime env var).

## Migration strategy

`RUN_MIGRATIONS_ON_STARTUP` must stay unset/false in Azure - EF Core
migrations run via a separate one-shot `azd` deployment task or init
container instead, so concurrent replica starts never race for the
migration lock.

## CORS

`AllowedOrigins` is a comma-separated list of full origins, e.g.
`https://prism.example.com,https://staging.prism.example.com`.

## SystemAdminToken

Protects the nuclear `/api/system/reset` endpoint on both the C# API and the
Python API via an `X-Admin-Token` header. Leaving it unset disables the
endpoint (403) rather than defaulting it open - set it explicitly (Container
Apps secret) if the endpoint is needed post-deploy.

## Health checks

`/health` on all three services (C# API, Python API, static Web via nginx).
Fast, no dependency pings - liveness probes only. `/readiness` (DB/Qdrant
pings) is post-V1.
