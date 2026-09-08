# PR C2 Task #6 Verification

## 1. Does `query_paper_claims` SELECT label, grounding_status, missing, reason, evidence_spans from paper_claims?

**Promised:** Task #6 required exposing metadata fields (`label`, `grounding_status`, etc.) from the database.
**Shipped:** Yes, these fields are explicitly selected. 
**Gap:** None.
**Citation:** `Prism.PythonService/paper_chat/tools.py`, lines 127-128:
```sql
SELECT id, claim_text_verbatim, claim_summary, label, missing,
       grounding_status, reason, evidence_spans
```

## 2. Are those fields returned to the graph state?

**Promised:** The fields must be passed to the graph state.
**Shipped:** Yes, the tool maps all these fields into its output dictionary for each row.
**Gap:** None.
**Citation:** `Prism.PythonService/paper_chat/tools.py`, lines 145-154.

## 3. Are they included in the LLM's context at response generation?

**Promised:** The fields must be included in the context given to the LLM. (If fetched but not passed to LLM, that's the bug).
**Shipped:** Yes, they are formatted into the context block for any claims returned by the tool, and injected into the system prompt.
**Gap:** None (assuming claims are successfully retrieved by the tool).
**Citation:** `Prism.PythonService/paper_chat/agent.py`, lines 289-296 (`_build_context_block`) and line 336 where `context_block` is injected.

## 4. Does the system prompt mention these fields and instruct the model to use them?

**Promised:** A stronger system prompt telling it to answer honestly from that metadata.
**Shipped:** Yes, the prompt includes detailed instructions on using `label`, `grounding_status`, `missing`, and `reason`, and quoting evidence verbatim without re-deriving judgments.
**Gap:** None.
**Citation:** `Prism.PythonService/paper_chat/agent.py`, lines 325-335.

## 5. Can a user query claims by ID or by "claim N"?

**Promised:** Chat should be able to answer questions about specific claims like "show me claim 11".
**Shipped:** No numeric-ID lookup path exists. The retrieval logic strictly uses full-text search: `to_tsvector('english', claim_summary || ' ' || claim_text_verbatim) @@ websearch_to_tsquery('english', %s)`.
**Gap:** The FTS does not index metadata or IDs. Queries like "claim 11", "supported claims", or "refusals" evaluate purely as text searches against claim summaries and verbatim text. Because scientific claim text rarely contains words like "supported", "refusal", or "11", the search returns zero rows. With zero claims in context, the agent refuses to answer.

## 6. Do claims have stable user-visible IDs? Is `position` returned by `query_paper_claims`?

**Promised:** Users should be able to reference claims by the numbers they see in the UI.
**Shipped:** No. The query only selects the UUID (`id` mapped to `claim_id`). It does not query for a `position` or sequence number.
**Gap:** The integer sequence (0, 1, 2, 3...) shown in the UI is entirely unknown to the chat agent. Even if users explicitly ask about "claim 1", the agent has no way to map the number "1" to the corresponding claim UUID.

## Minimum Fixes Needed

To enable the chat to successfully answer the failing live test queries ("Show me evidence of claim 11", "Which claims are supported? which not?", "Any refusal?"), the following fixes are minimally required:

1. **Include `position` in `query_paper_claims`**: Add the integer `position` field to the SQL SELECT statement and map it to the returned dictionaries. This aligns the agent's knowledge with the UI's numbering.
2. **Expand the Retrieval Strategy**: Update `query_paper_claims` (or add a separate routing tool) to support metadata/ID lookups. Relying strictly on full-text search for meta-questions fails because the metadata itself isn't indexed. The tool needs to be able to fetch claims by `position` (to support "claim 11") and to filter/fetch claims based on metadata such as `label` and `grounding_status` (to support "which are supported" and "any refusal").
