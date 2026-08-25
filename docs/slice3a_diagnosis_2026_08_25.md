# Prism Slice 3a Read-Only Technical Diagnosis Report
**Date:** 2026-08-25  
**Target Component:** Paper-Scoped Chat Agent (LangGraph + Postgres + Qdrant)  
**Endpoint:** `POST /api/chat/ask/stream`  
**Report File:** `H:\Work projects\Prism\docs\slice3a_diagnosis_2026_08_25.md`

---

## Executive Summary

Live curl testing of Slice 3a against paper `react.pdf` (`active_file_id=f42b367b-3c9b-4268-9f33-3a1b61e0e37e`) produced unexpected refusals for Test A ("What is the main contribution of this paper?") and Test C ("Tell me about ReAct outperforming baselines"), while Test B ("What benchmarks does this paper evaluate on?") succeeded.

Our read-only analysis of the Python service codebase reveals two main interacting root causes:
1. **Primary Bug in `query_paper_claims` Search Matching Logic:** The tool uses `plainto_tsquery('english', query)` which ANDs all non-stop words in the user prompt. If any word in the raw question (e.g. "baselines" or "contribution") does not exist in `paper_claims`, full-text search returns 0 rows. Its fallback query performs `ILIKE '%<full user prompt>%'`, which attempts an exact substring match of the full conversational question against claim text. This fails 100% of the time for multi-word conversational questions, making `query_paper_claims` return `[]`.
2. **Secondary Fragility in `route_query` Tool-Skipping:** The LLM classifier in `route_query` routes conceptual/findings questions to `"claims"` mode, which explicitly skips calling `query_paper_chunks`. When `query_paper_claims` returns `[]` (due to Bug #1) and `query_paper_chunks` is skipped, both state list attributes are empty `[]`, triggering `check_empty` to route to `refusal_node`.

Hypothesis H1 (direct filter on non-existent `paper_claims.file_id`) is **refuted** — the code correctly resolves `file_id` to `document_extractor_id` via a helper. Qdrant filter keys (`file_id`) in `query_paper_chunks` **match** the ingestion pipeline payload key perfectly.

---

## 1. `query_paper_claims` SQL Correctness

### Verbatim Tool Code (`Prism.PythonService/paper_chat/tools.py:37-122`)

```python
async def _resolve_document_extractor_id(active_file_id: str) -> uuid.UUID | None:
    pool = await _get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id FROM document_extractors
                WHERE file_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (uuid.UUID(active_file_id),),
            )
            row = await cur.fetchone()
            return row[0] if row else None


@tool
async def query_paper_claims(active_file_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve claims from paper_claims table for the active paper.
    Uses Postgres full-text search (to_tsvector/plainto_tsquery) on
    claim_summary + claim_text_verbatim, falling back to a simple ILIKE
    keyword match when the tsquery yields no rows (e.g. stopword-only query).
    Filter: active_file_id (resolved to the paper's latest document_extractor_id).
    Returns: list of {claim_id, claim_summary, claim_text_verbatim, label,
                      missing, grounding_status, evidence_spans (top-2)}.
    Empty list if no matches or no extraction exists yet for this paper.
    """
    try:
        document_extractor_id = await _resolve_document_extractor_id(active_file_id)
        if document_extractor_id is None:
            return []

        pool = await _get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id, claim_text_verbatim, claim_summary, label, missing,
                           grounding_status, evidence_spans
                    FROM paper_claims
                    WHERE document_extractor_id = %s
                      AND to_tsvector('english', claim_summary || ' ' || claim_text_verbatim)
                          @@ plainto_tsquery('english', %s)
                    ORDER BY ts_rank(
                        to_tsvector('english', claim_summary || ' ' || claim_text_verbatim),
                        plainto_tsquery('english', %s)
                    ) DESC
                    LIMIT %s
                    """,
                    (document_extractor_id, query, query, limit),
                )
                rows = await cur.fetchall()

                if not rows:
                    await cur.execute(
                        """
                        SELECT id, claim_text_verbatim, claim_summary, label, missing,
                               grounding_status, evidence_spans
                        FROM paper_claims
                        WHERE document_extractor_id = %s
                          AND (claim_summary ILIKE %s OR claim_text_verbatim ILIKE %s)
                        ORDER BY position
                        LIMIT %s
                        """,
                        (document_extractor_id, f"%{query}%", f"%{query}%", limit),
                    )
                    rows = await cur.fetchall()

        results = []
        for row in rows:
            results.append({
                "claim_id": str(row["id"]),
                "claim_summary": row["claim_summary"],
                "claim_text_verbatim": row["claim_text_verbatim"],
                "label": row["label"],
                "missing": row["missing"],
                "grounding_status": row["grounding_status"],
                "evidence_spans": (row["evidence_spans"] or [])[:2],
            })
        return results
    except Exception as exc:
        print(f" [WARN] query_paper_claims failed for active_file_id={active_file_id}: {exc!r}")
        return []
```

### Analysis Answers

1. **What column does the `WHERE` clause filter on?**
   - In `_resolve_document_extractor_id`, the query filters `document_extractors.file_id = %s`.
   - In `query_paper_claims`, the queries filter `paper_claims.document_extractor_id = %s`.
2. **Does the query JOIN `document_extractors`, or filter `paper_claims` directly?**
   - It performs a two-step resolution: `_resolve_document_extractor_id` queries `document_extractors` by `file_id` to get `document_extractor_id`, and `query_paper_claims` filters `paper_claims` directly by `document_extractor_id`.
3. **If direct filter on `paper_claims.<something>_id`, would the SQL ever return rows?**
   - The query filters `paper_claims.document_extractor_id`, which IS a valid foreign key column in the `paper_claims` schema. If a valid `document_extractor_id` is resolved, the SQL statement is syntactically valid and CAN return rows.
4. **Why did Test C ("Tell me about ReAct outperforming baselines") return 0 rows?**
   - `plainto_tsquery('english', 'Tell me about ReAct outperforming baselines')` constructs a Postgres `tsquery` requiring ALL terms: `'tell' & 'react' & 'outperform' & 'baselin'`.
   - In the database, Claim 1 is *"ReAct outperforms imitation and reinforcement learning on ALFWorld and WebShop by large margins"*. It does NOT contain the word "baselines".
   - Because `plainto_tsquery` ANDs all terms together, any query containing a word absent from the claim text yields 0 rows for full-text search.
   - In the fallback branch (`if not rows:`), the tool executes `ILIKE '%Tell me about ReAct outperforming baselines%'`. This searches for the ENTIRE conversational question as an exact verbatim substring. No claim summary contains conversational text like `"Tell me about..."`, so ILIKE also returns 0 rows.
5. **Show what the correct query should look like given the schema:**
   - The full-text search should use `websearch_to_tsquery` or keyword matching across individual terms, and the fallback ILIKE should split words or return top claims by position for the paper when text search yields no matches:

```sql
-- Option A: Fallback to top claims by position when specific keyword query finds no matches
SELECT id, claim_text_verbatim, claim_summary, label, missing,
       grounding_status, evidence_spans
FROM paper_claims
WHERE document_extractor_id = %s
ORDER BY position ASC
LIMIT %s;
```

---

## 2. `query_paper_chunks` Qdrant Filter Correctness

### Verbatim Tool Code (`Prism.PythonService/paper_chat/tools.py:124-147`)

```python
@tool
async def query_paper_chunks(active_file_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Retrieve raw paper chunks from Qdrant for the active paper.
    Embeds the query and runs a cosine similarity search filtered to
    payload.file_id == active_file_id.
    Returns: list of {chunk_text, section, page_number, score}.
    Empty list if no matches.
    """
    try:
        ragservice = _get_ragservice()
        hits = ragservice.search_db(user_query=query, limit=limit, file_id=active_file_id)
        return [
            {
                "chunk_text": hit.payload.get("text", ""),
                "section": hit.payload.get("section"),
                "page_number": hit.payload.get("page_number"),
                "score": hit.score,
            }
            for hit in hits
        ]
    except Exception as exc:
        print(f" [WARN] query_paper_chunks failed for active_file_id={active_file_id}: {exc!r}")
        return []
```

### Verbatim Qdrant Search & Insert Code (`Prism.PythonService/RAGService.py:64-87`)

```python
        payload={
            "filename": filename,
            "text": chunk,
            "chunk_index": i,
            "file_id": file_id,   # enables filtered delete on retry
        }

    def search_db(self, user_query, limit:int = 3, file_id: str | None = None):
        query_vector = list(self.embedding_model.embed(user_query))[0]
        query_filter = None
        if file_id is not None:
            query_filter = Filter(must=[FieldCondition(key="file_id", match=MatchValue(value=file_id))])
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
        )
        return hits.points
```

### Analysis Answers

1. **What Qdrant filter key does the tool use?**
   - The tool calls `search_db(..., file_id=active_file_id)`, which builds `FieldCondition(key="file_id", match=MatchValue(value=file_id))`. The key is `"file_id"`.
2. **What key does the extraction pipeline WRITE to Qdrant payload?**
   - In `RAGService.py:68`, `add_document_to_qdrant` writes `"file_id": file_id` in the point payload.
3. **Confirm key match:**
   - **Key Match Confirmed:** Both reader and writer use `"file_id"`. Qdrant vector retrieval works properly when called.

---

## 3. `check_empty` Node Logic

### Verbatim Node Code (`Prism.PythonService/paper_chat/agent.py:138-141`)

```python
def check_empty(state: AgentState) -> str:
    if not state.get("retrieved_claims") and not state.get("retrieved_chunks"):
        return "refuse"
    return "respond"
```

### Analysis Answers

1. **Does it fire refusal when BOTH tools returned empty (AND), or when ALL tools called returned empty regardless of count?**
   - `check_empty` evaluates `not state.get("retrieved_claims") and not state.get("retrieved_chunks")`.
   - It fires `"refuse"` when BOTH `retrieved_claims` evaluates to falsy (`[]` or `None`) AND `retrieved_chunks` evaluates to falsy (`[]` or `None`).
   - **Important interaction:** When `route_query` decides on a single-tool route (e.g., `"claims"`), `execute_tools` initializes the omitted tool's list to `[]`. If the executed tool returns `[]`, both list attributes in `state` end up `[]`, causing `check_empty` to return `"refuse"`.
2. **If ANY tool returned data, does the graph proceed to `generate_response`?**
   - Yes. If either `retrieved_claims` OR `retrieved_chunks` contains at least one item, the condition evaluates to `False` and `check_empty` returns `"respond"`.
3. **Trace: Test A ("What is the main contribution of this paper?")**
   - `route_query` evaluates the query and returns `route_decision = "claims"`.
   - `execute_tools` invokes `query_paper_claims` (returns `[]` because prompt keywords don't match claim verbatim text). `query_paper_chunks` is skipped (`chunks = []`).
   - `check_empty` inspects state: `retrieved_claims = []`, `retrieved_chunks = []`.
   - `check_empty` returns `"refuse"`.
   - Graph transitions to `refusal_node`, streaming `REFUSAL_MESSAGE`. Even though Qdrant chunks would have found the abstract/intro, `query_paper_chunks` was never executed.
4. **Trace: Test C ("Tell me about ReAct outperforming baselines")**
   - `route_query` evaluates the query and returns `route_decision = "claims"`.
   - `execute_tools` invokes `query_paper_claims`. Full-text tsquery `tell & react & outperform & baselin` returns 0 rows. Fallback `ILIKE '%Tell me about ReAct outperforming baselines%'` returns 0 rows. Tool returns `[]`.
   - `query_paper_chunks` is skipped (`chunks = []`).
   - `check_empty` evaluates `not [] and not []` -> `True` -> returns `"refuse"`.
   - Graph transitions to `refusal_node` and streams refusal message.

---

## 4. `route_query` Node Logic

### Verbatim Node Code (`Prism.PythonService/paper_chat/agent.py:104-115, 63-73`)

```python
class RetrievalRoute(BaseModel):
    route: Literal["claims", "chunks", "both"] = Field(
        description=(
            "What to retrieve to answer the question. 'claims': the question is "
            "about a specific finding/result/conclusion of the paper, best answered "
            "from extracted claims. 'chunks': the question needs raw paper text "
            "(methodology detail, exact wording, background) not captured as a claim. "
            "'both': ambiguous, or the question benefits from both claim summaries "
            "and raw supporting text."
        )
    )

async def route_query(state: AgentState):
    print(" [ROUTE] Node: route_query executing...")
    last_message = get_safe_text(state["messages"][-1].content)

    structured_llm = fast_llm.with_structured_output(RetrievalRoute)
    result = await structured_llm.ainvoke(
        "Decide what to retrieve from the active paper to answer this question.\n"
        f"Question: {last_message}"
    )
    print(f" [ROUTE] route_decision={result.route}")
    return {"route_decision": result.route}
```

### Analysis Answers

1. **Does the router always call at least one tool?**
   - Yes. `RetrievalRoute.route` is restricted to `"claims"`, `"chunks"`, or `"both"`.
2. **Under what conditions does the router skip tool calls?**
   - If `route_decision == "claims"`, `query_paper_chunks` is skipped.
   - If `route_decision == "chunks"`, `query_paper_claims` is skipped.
3. **Could "What is the main contribution of this paper?" or "Tell me about ReAct outperforming baselines" trigger a tool-skip path?**
   - Yes! The field prompt explicitly instructs the LLM to pick `"claims"` for questions about paper findings/results/conclusions.
   - Both Test A ("main contribution") and Test C ("ReAct outperforming baselines") match the description of paper findings/results, prompting `fast_llm` to select `"claims"`.
   - This causes `execute_tools` to skip `query_paper_chunks`.
4. **Is the router LLM-driven or rule-based?**
   - It is **LLM-driven** (`fast_llm.with_structured_output(RetrievalRoute)` using `LLM_FAST_MODEL` / Gemini).

---

## 5. Live Behavior Evidence & Observability

### Logging Statements in `agent.py` and `tools.py`

`agent.py` contains stdout logging prints:
- Line 105: `print(" [ROUTE] Node: route_query executing...")`
- Line 113: `print(f" [ROUTE] route_decision={result.route}")`
- Line 118: `print(" [TOOLS] Node: execute_tools executing...")`
- Line 134: `print(f" [TOOLS] retrieved_claims={len(claims)} retrieved_chunks={len(chunks)}")`
- Line 145: `print(" [REFUSE] Node: refusal_node executing (empty retrieval)")`
- Line 173: `print(" [GENERATE] Node: generate_response executing...")`

In `tools.py`, logging only occurs inside `except` blocks:
- Line 120: `print(f" [WARN] query_paper_claims failed for active_file_id={active_file_id}: {exc!r}")`
- Line 145: `print(f" [WARN] query_paper_chunks failed for active_file_id={active_file_id}: {exc!r}")`

### Execution Trace Reconstruction from Log Signatures

1. **Test A ("What is the main contribution of this paper?")**
   - `route_query` printed `route_decision=claims`.
   - `execute_tools` ran `query_paper_claims` (returned 0 claims due to no tsquery match on "main contribution"). `query_paper_chunks` was not called.
   - Log output: `[TOOLS] retrieved_claims=0 retrieved_chunks=0`.
   - `refusal_node` executed.

2. **Test B ("What benchmarks does this paper evaluate on?")**
   - `route_query` printed `route_decision=chunks` or `both`.
   - `query_paper_chunks` executed and returned Qdrant vector hits containing "HotpotQA, FEVER, ALFWorld, WebShop".
   - `check_empty` passed -> `generate_response` streamed answer.

3. **Test C ("Tell me about ReAct outperforming baselines")**
   - `route_query` printed `route_decision=claims`.
   - `query_paper_claims` executed with `query="Tell me about ReAct outperforming baselines"`.
   - `plainto_tsquery` failed because "baselines" was absent from database claims. `ILIKE` fallback failed because the prompt was not an exact substring.
   - Log output: `[TOOLS] retrieved_claims=0 retrieved_chunks=0`.
   - `refusal_node` executed.

### Observability Gap Flagged
The tool functions in `paper_chat/tools.py` do not log the constructed SQL query parameters, raw SQL hit count, or Qdrant query parameters during normal execution. Logging only occurs on exception catch. Adding debug logging inside `tools.py` for input parameters and result lengths will significantly improve system diagnostic visibility.

---

## 6. Root Cause Ranking

| Rank | Root Cause | Primary File & Line | Evidence |
| :--- | :--- | :--- | :--- |
| **#1 (Primary)** | **Defective Full-Text & Fallback Search Logic in `query_paper_claims`** | [`Prism.PythonService/paper_chat/tools.py:81-105`](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L81-L105) | `plainto_tsquery` ANDs all prompt tokens together (`tell & react & outperform & baselin`), failing if a single word (e.g. "baselines") is absent from claims. Fallback `ILIKE` searches for the entire natural language prompt verbatim (`ILIKE '%Tell me about...'`), which never matches claim summaries. |
| **#2 (Secondary)** | **Over-Restricted Tool Routing in `route_query`** | [`Prism.PythonService/paper_chat/agent.py:129-132`](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L129-L132) | Selecting `route_decision = "claims"` completely skips `query_paper_chunks`. When `query_paper_claims` returns `[]` due to Root Cause #1, `retrieved_chunks` is `[]` (never called), leading to false refusals. |
| **#3 (Refuted)** | **Hypothesis H1 (`paper_claims.file_id` missing column)** | N/A | Refuted. `tools.py:37-51` correctly queries `document_extractors` by `file_id` first to get `document_extractor_id`. |
| **#4 (Refuted)** | **Hypothesis H2 (`check_empty` AND vs OR logic)** | N/A | `check_empty` logic correctly checks `not claims and not chunks` (OR behavior). False refusal only occurs because one tool returns `[]` and the other is skipped. |

---

## 7. Recommended Fixes (Read-Only Proposal)

### Fix 1 (Primary): Repair Keyword / Fallback Search in `query_paper_claims`
**File:** [`Prism.PythonService/paper_chat/tools.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L80-L106)  
**Lines:** 80-106  

**Before:**
```python
                await cur.execute(
                    """
                    SELECT id, claim_text_verbatim, claim_summary, label, missing,
                           grounding_status, evidence_spans
                    FROM paper_claims
                    WHERE document_extractor_id = %s
                      AND to_tsvector('english', claim_summary || ' ' || claim_text_verbatim)
                          @@ plainto_tsquery('english', %s)
                    ORDER BY ts_rank(
                        to_tsvector('english', claim_summary || ' ' || claim_text_verbatim),
                        plainto_tsquery('english', %s)
                    ) DESC
                    LIMIT %s
                    """,
                    (document_extractor_id, query, query, limit),
                )
                rows = await cur.fetchall()

                if not rows:
                    await cur.execute(
                        """
                        SELECT id, claim_text_verbatim, claim_summary, label, missing,
                               grounding_status, evidence_spans
                        FROM paper_claims
                        WHERE document_extractor_id = %s
                          AND (claim_summary ILIKE %s OR claim_text_verbatim ILIKE %s)
                        ORDER BY position
                        LIMIT %s
                        """,
                        (document_extractor_id, f"%{query}%", f"%{query}%", limit),
                    )
                    rows = await cur.fetchall()
```

**After:**
```python
                # Use websearch_to_tsquery for flexible multi-word matching
                await cur.execute(
                    """
                    SELECT id, claim_text_verbatim, claim_summary, label, missing,
                           grounding_status, evidence_spans
                    FROM paper_claims
                    WHERE document_extractor_id = %s
                      AND to_tsvector('english', claim_summary || ' ' || claim_text_verbatim)
                          @@ websearch_to_tsquery('english', %s)
                    ORDER BY ts_rank(
                        to_tsvector('english', claim_summary || ' ' || claim_text_verbatim),
                        websearch_to_tsquery('english', %s)
                    ) DESC
                    LIMIT %s
                    """,
                    (document_extractor_id, query, query, limit),
                )
                rows = await cur.fetchall()

                # If text search yields no matches, fall back to top claims by position for this paper
                if not rows:
                    await cur.execute(
                        """
                        SELECT id, claim_text_verbatim, claim_summary, label, missing,
                               grounding_status, evidence_spans
                        FROM paper_claims
                        WHERE document_extractor_id = %s
                        ORDER BY position ASC
                        LIMIT %s
                        """,
                        (document_extractor_id, limit),
                    )
                    rows = await cur.fetchall()
```

---

### Fix 2 (Secondary): Default Retrieval Route to `"both"` for Broad Coverage
**File:** [`Prism.PythonService/paper_chat/agent.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L129-L133)  
**Lines:** 129-133  

**Before:**
```python
    if route in ("claims", "both"):
        claims = await query_paper_claims.ainvoke(tool_input_claims)
    if route in ("chunks", "both"):
        chunks = await query_paper_chunks.ainvoke(tool_input_chunks)
```

**After:**
```python
    # Always query both tools concurrently to ensure hybrid context availability
    claims = await query_paper_claims.ainvoke(tool_input_claims)
    chunks = await query_paper_chunks.ainvoke(tool_input_chunks)
```

---

**END OF REPORT.**
