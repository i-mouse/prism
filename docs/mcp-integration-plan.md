# PRISM MCP Integration Plan (September 2026)

This document is a senior-level integration plan for adding Model Context Protocol (MCP) capabilities to PRISM. It defines the "why", "where", and "what" of the implementation before any code is written, aligned to the current ecosystem state as of September 2026.

> **This is design intent, not an approval to build.** The standing decision on whether to build is `docs/audit/mcp_readiness.md`, and its recommendation is unchanged: **do not build MCP now.** The blocker is REST API readiness, not MCP itself — the upload endpoint demands a SignalR connection ID, returns no `file_id` for tracking, and there is no polling endpoint for extraction progress, so an MCP server cannot cleanly wrap the current API. This plan records the scope and tenancy answers so they stop being re-litigated; it does not move the gate. **This document and `docs/audit/mcp_readiness.md` have not been reconciled line by line — reconcile pending.**

## 1. Why MCP, why now (Interview + Product Framing)

MCP adoption is real, not hype: it sees ~500M downloads/month across Tier-1 SDKs, with the TypeScript and Python SDKs each past 1 billion total downloads. Job-posting research (1,600+ real listings, 2026) shows MCP as expected knowledge for AI engineer / LLM developer / agent developer / backend roles. However, it is NOT universally mandatory at every company; it matters most at companies actually building agent/tool platforms. This integration demonstrates that capability.

**Senior-Level Interview Depth:**
*   **Primitives:** Clear control-model framing: tools = model-controlled, resources = application-controlled, prompts = user-controlled.
*   **Transport Story:** Stateless HTTP is current; SSE is legacy.
*   **Security Context:** Awareness of security-incident classes such as RCE via dependency chain, cross-tenant leakage, tool-name shadowing, prompt injection via resource content, and OAuth/PKCE gaps.
*   **Deliberate Omissions:** The 2026-07-28 spec deprecated Roots, Sampling, and Logging for NEW implementations. We skip these not out of ignorance, but because a senior engineer knows they are deprecated and avoids building them just for completeness.

## 2. Current State of the Ecosystem (Verified Sept 2026)

*   **Spec:** 2026-07-28 is the current stable specification (finalized July 28, 2026). The major change is that the protocol core is now stateless — no more initialize handshake / session tracking. It also features Multi Round-Trip Requests, header-based routing, cacheable list results, hardened authorization (issuer validation, issuer-bound client credentials, CIMD preferred over Dynamic Client Registration), and a formal extensions framework.
*   **C# SDK:** v2.2.0 is the current release aligned to the 2026-07-28 spec (stateless-by-default). Do not target the pre-stateless v1.0.0 from Feb 2026. *Note: MCP SDKs move fast; re-verify the version at install time rather than trusting this line.*
*   **Auth:** For a server with known, first-party clients (PRISM's use case), Microsoft's guidance recommends pre-registration — a normal Entra app registration. We will reuse the exact same CIAM config already in place — see the auth section of `Prism.ApiService/appsettings.json` for the tenant and app registration values. The Microsoft Entra team explicitly discourages building a CIMD/DCR proxy in front of Entra. The C# SDK handles this natively alongside standard ASP.NET Core JWT bearer auth (`[Authorize]`, `ClaimsPrincipal` injection) — SDK-native, not custom middleware, and separate from Container Apps' platform-level EasyAuth (which lacks full MCP resource-metadata semantics). Note the two extensions are distinct and easy to confuse: **`AddMcpServer` registers the MCP server itself; `AddMcp` is the authentication extension.** Both are needed, and they are not interchangeable.

## 3. Hosting Decision, with Reasoning

*   **Host:** Azure Container Apps — Microsoft's stated preferred platform for MCP servers in 2026 (not Azure App Service's "built-in MCP" which remains in Preview and offers no benefit here).
*   **Placement:** A new `/mcp` endpoint on the EXISTING `apiservice` Container App.
    *   *Why we chose this over a new Container App:* Reusing `apiservice` (`AppHost.cs` -> `builder.AddProject<...>("apiservice").PublishAsAzureContainerApp(...)`) reuses existing Entra JWT auth wiring, the existing EF Core `PrismDBContext` connection, deployment pipeline, and ingress. Creating a new Container App would mean duplicate infrastructure (requiring new `AppHost` declarations, duplicating Postgres/KeyVault managed identity role assignments) and duplicate auth wiring for zero isolation benefit at this project's scale.
*   **Cost/Scaling:** Hosting is **deferred while the environment is offline** (decommissioned 2026-09-28 — see `docs/decisions.md`). Nothing in this section has been tested against a running deployment, and the placement decision above is therefore unvalidated. Cold-start behaviour for an interactive tool-calling loop, and whether Native AOT or a minimum replica count is the right answer, are questions for whenever hosting is revisited — they cannot be settled on paper. Any hosting decision taken at relaunch must be made alongside the cost prerequisites in [docs/RUNBOOK.md](RUNBOOK.md#decommissioned-state-and-relaunch), not separately from them.

## 4. Final Tool Scope — Locked

Three tools, all read-only:
1.  `get_paper_claims(paper_id)` — Claim list + verdicts only, no evidence text. Deliberately lightweight ("table of contents") so a client isn't forced to pay (in tokens and latency) for evidence it didn't ask for.
2.  `get_claim_evidence(claim_id)` — Evidence spans for one specific claim.
3.  `inspect_audit_result(claim_id)` — Full picture: claim + evidence + reasoning combined, for one claim.

**Explicitly Excluded:**
*   *Extraction / auditor / grounding as individually callable tools:* These are internal pipeline steps. Exposing pipeline internals leaks implementation details. Output is already exposed through the tools above.
*   *A generic/raw DB query tool:* Unrestricted access surface breaks the "thin adapter" principle and introduces real security risk.
*   *Paper submission/upload via MCP:* Out of scope for v1. MCP only reads papers already processed through PRISM's web upload flow.
*   *Paper search/discovery via MCP:* Explicitly not PRISM's job (that's Elicit/Consensus/Scite territory).
*   *Cross-paper comparison:* Tier 2 roadmap item, not started, not in MCP v1 scope.
*   *Any write/mutation tool:* PRISM's value is exposing already-audited, grounded evidence.
*   *Rebuilding PRISM's own existing chat to route through this MCP server:* Redundant extra hop for data the chat already has direct access to.
*   *`audit_claim` (re-audit a claim on demand):* Rejected 2026-09-28. It would expose an unmeasured surface — nothing in the eval harness covers on-demand re-auditing, so there would be no way to say whether its output is trustworthy. Every tool above returns something the eval already measures.
*   *A per-paper confidence field on any tool response:* Rejected 2026-09-28. Eval provenance is a server-level property (the refusal-family rate over the golden set); attaching a number to an individual paper would imply a per-paper measurement that does not exist.

**Deferred, not rejected:**
*   *MCP Resources:* Deferred. If added later, a per-user `cacheScope` is **required** — the default cache scope would leak one user's paper list to another, which is the cross-tenant leakage class named in §1.

## 5. Multi-tenancy / Ownership (Required Pre-requisite Decision)

PRISM's web app enforces per-user paper ownership. If MCP tools do not enforce this, any client could see every paper in the database.

**Required Decision:** MCP tools must enforce the exact same ownership/tenancy rule the web app already has — no new or separate access model invented for MCP.

**Resolution (2026-09-28, design intent only — see `docs/decisions.md`, "MCP v1 scope and tenancy decisions"):**
*   **Delegated Entra user tokens only**, resolved through the `oid` claim. This is the same identity the web app's `ResolveUserId` already uses, so there is exactly one ownership model.
*   **App-only tokens are excluded.** There is no user principal in an app-only token, so there is nothing to scope papers to — it would have to mean "all papers", which is the failure this section exists to prevent.
*   **Guests are excluded.** Guest identity is an HttpOnly session cookie (`GuestAuthEndpoints.CookieName`); it has no meaning to an MCP client and cannot be presented as a bearer token.
*   **Implementation Detail (Verified):** The web app currently checks ownership by joining `PrismDocuments` and `ChatFiles` against the resolved `userId`.
*   **Codebase Correction:** The codebase uses `GuestAuthEndpoints.ResolveUserId(httpContext)` which extracts the `oid` claim (`User.FindFirst("oid")?.Value`) for Google-authenticated users. The MCP tool handlers MUST extract the `oid` claim for authorization checks. *(Note: `Program.cs` contains a stale comment incorrectly stating the ID should be read from the `sub` claim. `GuestAuthEndpoints.cs` correctly overrides this and uses `oid`.)*
*   **Data Access Correction:** There are no abstracted "service methods" (e.g., `IPaperService`) to call for these tools. The data access layer uses Entity Framework Core directly. The tools must query `PrismDBContext.PaperClaims` directly, identical to how `SubmitPaperEndPoint.cs` accesses claim properties and the `EvidenceSpans` JSON-owned collection.

## 6. What this integration is NOT

*   Not a way for third parties to add new papers, search for papers, or run cross-paper analysis.
*   Not self-serve/public in the usual MCP sense — each connecting client must be pre-registered in Entra by the operator (Nitin) first.
*   Not production-grade uptime. There is no hosted environment at all right now — it was decommissioned on 2026-09-28 — so anything built here would run locally until a relaunch.
*   **Good-fit examples:** A citation-checker plugin for a writing tool, a research team's internal chat/Slack bot querying papers the team already uploaded, a "verify before you cite" layer bolted onto a paper-finder tool, or an interview/portfolio demo.
*   **Bad-fit examples:** A public "ask about any paper" chatbot, a paper-discovery tool, or any high-traffic production use.

## 7. Prerequisites — What must happen BEFORE implementation starts

MCP work is explicitly gated behind "core works locally" per PRISM's own project rules. Building MCP now is a deliberate, acknowledged parallel learning track for interview prep — not a silent reordering of the core roadmap.

Still open ahead of MCP implementation:
*   **REST API readiness:** The blocker named in `docs/audit/mcp_readiness.md` — upload requires a SignalR connection ID, returns no `file_id`, and there is no extraction-progress polling endpoint. Worth doing on its own merits, independently of MCP.
*   **Extractor/auditor iteration:** The `by_omission` gap (6/14 grounding-negative cases refused only because the extractor never surfaced the claim) and 2/14 tier-wrong labels remain the higher-priority items for the actual hiring artifact.
*   **Proof pack:** (README + blog post + screenshots + walkthrough video) Must be confirmed finished.
*   **Hosting:** No environment exists to host against. See §3.

## 8. Best Practices for Implementation

*   **Thin Adapter:** Keep the MCP layer a strictly thin adapter. Do not write new business logic inside an MCP tool handler; if needed, call into the EF Core `PrismDBContext`.
*   **Short Descriptions:** Tool descriptions stay short and precise — they occupy context on every call.
*   **Annotations are Advisory:** Tool annotations (e.g. read-only hints) are advisory only, never a security boundary.
*   **Strict Auth Flow:** Authenticated principal → authorization check (ownership/tenancy via `oid`) → input validation → query `PrismDBContext` → return a scoped result. Never trust the connecting client.
*   **Pin SDK Version:** Because MCP SDKs move fast, pin the exact SDK version used (v2.2.0 at the time of writing — re-verify at install) and note it in the implementation changelog. Do not assume "latest" will stay stable.
