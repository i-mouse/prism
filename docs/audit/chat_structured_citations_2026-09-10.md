# Chat Structured Citations Audit - 2026-09-10

## 1. Current Actual Data Shape
The backend **already** sends cleanly separated, typed blocks over SSE. It does not send raw markdown with embedded `[claim:ID]` markers to the frontend. The `generate_response` node in `agent.py` buffers the LLM's text stream, intercepts `[claim:ID]` markers, and splits the stream on the fly. 

**Example SSE Wire Format:**
```json
data: {"type": "text", "content": "ReAct outperforms state-of-the-art baselines on diverse tasks. "}

data: {"type": "claim_reference", "claim_id": "uuid-1234", "claim_summary": "ReAct outperforms SOTA...", "display_label": "supported"}

data: {"type": "text", "content": "\nIt also improves interpretability. "}
```

## 2. Root Cause of Formatting Bugs
The root cause is an **implementation drift in the frontend renderer**, not the backend block design. 

Because the backend splits the markdown text at every citation, the frontend (`PaperChatStrip.tsx`) loops over the `ChatBlock` array and mounts a separate `<ChatMarkdown>` instance for each individual `TextBlock`. 
- Markdown structures (like lists, tables, or paragraphs) that span across a citation are shattered into independent parser instances and fail to render.
- To prevent pills from breaking lines, `ChatMarkdown.tsx` overrides the paragraph tag (`p: ({ children }) => <Fragment>{children}</Fragment>`). This forcefully collapses the entire shattered response into a single, unreadable inline paragraph.
- Because the frontend expects the LLM to probabilistically generate the claim summary in the prose preceding the pill, any deviation by the LLM results in orphaned or doubled pills.

## 3. Proposed Backend Schema & Streaming Impact
**Streaming UX Constraint:**
Migrating to a true structured output schema (e.g., Gemini's `response_schema` via LangChain's `with_structured_output`) **requires buffering the full response**. LangChain waits for the JSON to be fully generated and validated before yielding the parsed Pydantic object, completely breaking the token-by-token typing UX. 

**Proposed Schema:**
Since the backend already emits typed blocks (`TextBlock` and `ClaimReferenceBlock`), no schema change is necessary on the backend to achieve structural separation. The current alternating block stream successfully preserves token-by-token streaming for text while isolating citation data structurally.

However, the LLM prompt in `agent.py` should be simplified. Remove the probabilistic formatting instructions (e.g., "give one line per claim in the form 'Claim N - summary'"). Instruct the LLM to simply cite naturally using `[claim:ID]`, relying on the frontend to render the structural `ClaimReferenceBlock` data.

## 4. Proposed Frontend Renderer Change
The frontend must stop feeding shattered text fragments into separate `<ChatMarkdown>` instances.

1. **Reconstruct a continuous markdown string:** In `useChatStream.ts` or `PaperChatStrip.tsx`, concatenate the incoming blocks into a single string. Replace `ClaimReferenceBlock` objects with a custom markdown-friendly tag, e.g., `<cite id="uuid" />`.
2. **Single parser pass:** Feed this unified string into a single `<ChatMarkdown>` component.
3. **Custom component mapping:** Update `ChatMarkdown.tsx`'s components dictionary to map the `<cite>` tag to the `<VerdictPill>` component, looking up the `claim_summary` and `display_label` from the block array via the ID.

This allows ReactMarkdown to correctly parse full block structures (lists, newlines, paragraphs) while securely embedding the pill component inline.

## 5. Scope & Compatibility
**What does NOT need to change:**
- `query_paper_claims`, `query_paper_chunks`, and the entire retrieval logic.
- Grounding status, thresholds, and extraction schemas.
- The `api.py` SSE endpoint logic.

**Estimated Scope:**
- `Prism.Web/src/components/matrix/PaperChatStrip.tsx`: ~30-50 lines (concatenate blocks for rendering, remove `AssistantBlocks` map loop).
- `Prism.Web/src/components/matrix/chat/ChatMarkdown.tsx`: ~10-20 lines (remove `<p>` override, add `<cite>` custom component).
- `Prism.PythonService/paper_chat/agent.py`: ~10 lines (remove strict text formatting rules from the system prompt).

## 6. Multi-turn and Streaming UX
By retaining the backend's current on-the-fly stream interception (rather than full JSON structured output), the token-by-token streaming UX remains completely intact. Prose text streams live to the user, and citations pop in as discrete structural events interspersed seamlessly into the live markdown.
