# Chat Claim Count Audit - 2026-09-10

## 1. Root Cause Analysis
The LLM is aggressively defending the incorrect claim count ("25 instead of 28") because it is relying on its own poisoned conversation history, and the current retrieval route provides no ground-truth metadata to correct it.

When the user asks *"when I asked about main claims, why did you only show a few but there are total 28 claims?"*:
1. **Router Behavior**: The router classifies this as a topical follow-up, not a direct request for an overall audit state. It sets `claim_lookup="query"` (FTS mode).
2. **Retrieval Subset**: In `"query"` mode, `execute_tools` hardcodes a `limit=5`. The `query_paper_claims` tool returns a plain `list[dict]` of at most 5 claims.
3. **Missing Metadata**: The tool returns **no total count denominator**. The LLM's `context_block` merely says `"Retrieved claims from this paper:"` followed by the 5 claims.
4. **History Reliance**: Because the LLM cannot see the true total count (28) in its current context, it looks back at the conversation history. In the previous turn (before the PR was deployed), the user explicitly asked `"total claims?"`, which triggered `claim_lookup="all"` and hit the old hardcoded `LIMIT 25`. The LLM confidently answered *"There are 25 claims"*. 
5. **Hallucination**: Faced with the user claiming "28" and its own history claiming "25" (with no current context to break the tie), the LLM trusts its own history and "corrects" the user.

## 2. Bug Classification
This is a **new manifestation of the same architectural gap**. 

The deployed fix successfully increased the `_METADATA_LOOKUP_LIMIT` from 25 to 50 for the `"all"` route. If the user started a *new* chat and asked `"how many total claims?"`, the LLM would correctly hit the `"all"` route, receive all 28 claims, and answer 28. 

However, because the `"query"` route isolates the LLM from global paper metadata (like the true total claim count), the LLM remains fundamentally blind to the paper's scope unless explicitly forced into the `"all"` route. This causes hallucination in follow-up turns.

## 3. Proposed Minimal Fix
The LLM needs global ground-truth metadata available on **every** turn, regardless of which retrieval subset was fetched.

**Option A (Recommended): Add a global metadata header to context**
Modify `execute_tools` in `agent.py` to run a fast, lightweight `COUNT(*)` query alongside the existing `asyncio.gather` tool calls. Pass this integer into the `AgentState` and format it at the top of the `_build_context_block` output:
```text
Paper Metadata:
- Total extracted claims: 28

Retrieved claims from this paper (subset for this query):
- Claim 1...
```
This requires no changes to the `query_paper_claims` tool schema, cleanly decoupling the "total denominator" from the "retrieved subset."

**Option B: Modify tool return schema**
Change `query_paper_claims` to return a dictionary instead of a list:
```python
return {"claims": results, "total_paper_claims": total_count}
```
This requires updating `check_empty` and `_build_context_block` in `agent.py` to unwrap the dictionary, but perfectly encapsulates claim metadata within the claim retrieval tool.
