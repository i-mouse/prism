# MCP Readiness Audit

## Executive summary
* **Readiness:** The current REST API requires a 3-5 day refactor before an MCP server can cleanly wrap it, largely due to websocket coupling.
* **Top 3 gaps:** The upload endpoint demands a SignalR connection ID, it fails to return a `file_id` for tracking, and there is no polling endpoint to check extraction progress.
* **Recommendation:** Do not build MCP now. Defer until the REST API hygiene issues are resolved and there is a clear user demand.
* **Trigger event:** We will build an MCP server only when a partner integration is scoped or a real user explicitly asks to script PRISM against their local agent workflow.
* **Interview value:** Demonstrates our restraint in adopting new standards: we prioritize fundamental API usability over premature protocol wrappers.

## What MCP is
The Model Context Protocol (MCP) is an open standard designed by Anthropic and donated to the Linux Foundation. It defines a standardized way for AI clients (like Claude Desktop or Cursor) to interact with external tools and resources, functioning similarly to LSP (Language Server Protocol) but for context provision. 

As of September 12, 2026, the currently-active spec revision is [2026-07-28](https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro). It standardizes tool execution, resource reading, and prompt templates, making it easier for local or remote AI agents to discover and invoke server capabilities without bespoke integration code.

## Local stdio vs remote HTTP
MCP supports two transports: local stdio (running as a local subprocess) and Streamable HTTP (remote via SSE with OAuth 2.1). For PRISM's near-term, local stdio is the only viable option. Building remote HTTP would require significant investment in an OAuth 2.1 authorization server and identity infrastructure, which is completely out of scope for our current architecture. 

## Current REST API readiness — per capability

| Capability | Current Endpoint | MCP-wrappable today? | Blocker if N |
|---|---|---|---|
| `audit_paper` | `POST /api/papers` | N | Requires SignalR session; returns no `file_id` |
| `get_claim_matrix` | `GET /api/papers/{paperId}/claims` | Y | None (if `paperId` is known) |
| `get_paper_verdict` | `GET /api/papers/{paperId}/claims` | Y | None (if `paperId` is known) |
| `list_papers` | `GET /api/chats/{userId}` | N | Scoped strictly to chat sessions, not global |
| `get_claim_by_id` | None | N | Endpoint does not exist |

## Gaps and the fix for each

**Missing synchronous identifiers on upload**
Currently, `POST /api/papers` returns a static success message without the generated `file_id`. An MCP tool must return identifiers so subsequent tools can operate on them. The fix is a small update to return the `file_id` in the HTTP 200 response (Independent-of-MCP).

**Forced SignalR coupling**
The upload endpoint explicitly fails if a SignalR `ConnectionId` is not provided. MCP tools operate over request/response and cannot participate in WebSocket sessions. The fix requires removing this validation and treating real-time updates as an optional progressive enhancement (Independent-of-MCP).

**Lack of status polling**
Because extraction takes minutes, MCP needs to poll for completion. There is currently no `GET /api/papers/{paperId}/status` endpoint. The fix involves creating a new endpoint that queries the database for extraction status (Independent-of-MCP).

**Unbounded string metadata fields**
The `PaperMetadataFinal` DTO represents fields like `ablation_studies` as unbounded strings (e.g., "None reported"). An MCP schema would strongly benefit from these being structured as booleans or Enums to prevent hallucination. The fix requires modifying the LLM extraction prompt and Pydantic schemas (MCP-specific).

## Recommended follow-up PRs (independent-of-MCP)

**PR: Decouple document upload from SignalR session state**
* **Files affected:** `SubmitPaperEndPoint.cs`
* **Size:** Small
* **Justification:** We want this even if MCP never exists because uploads should succeed based purely on payload validity. It enables integration testing and programmatic usage (like `curl`) without requiring a WebSocket client.

**PR: Return file identifier synchronously on upload**
* **Files affected:** `SubmitPaperEndPoint.cs`, `SubmitPaperRequest.cs`
* **Size:** Small
* **Justification:** We want this even if MCP never exists because it allows clients to track their uploaded documents deterministically, rather than relying entirely on asynchronous event matching.

**PR: Add document extraction status polling endpoint**
* **Files affected:** `SubmitPaperEndPoint.cs`
* **Size:** Small
* **Justification:** We want this even if MCP never exists because it allows clients that drop their WebSocket connection to recover state without relying solely on chat backfill endpoints.

## When to actually build MCP
We will defer building an MCP server until there is a concrete trigger event: when a partner integration is actively scoped, or when at least one real user explicitly requests to script PRISM against their local agent workflow. 

## What NOT to do
* **Do not** build remote MCP with Streamable HTTP and OAuth 2.1.
* **Do not** treat an MCP server as a replacement for a well-designed REST API.
* **Do not** duplicate business logic or database access directly in the MCP server; it must remain a thin wrapper around the REST API.
* **Do not** build MCP simply because "it is the future." 

## Interview framing
* Highlighting our decision to audit MCP readiness without immediately building it demonstrates mature engineering restraint and prioritization.
* It shows that we evaluate new standards strictly against our current architecture and user needs, rather than chasing hype.
* Identifying basic API hygiene gaps (like forced websocket coupling) proves we understand that a solid REST foundation is a prerequisite for any agentic wrapper.
