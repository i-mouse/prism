# Chat Subsystem Architecture Review — 2026-09-20
**Phase 0: Discovery & Diagnosis. No code changes in this pass.**
**Author**: AGY (Antigravity) — commissioned by Nitin for pre-Phase-1 review.

---

## Top-Level Summary Table

| Component | Rating | Severity | Patch vs. Architectural | Caught by Automation? |
|:---|:---|:---|:---|:---|
| **`rewrite_query` node** | **fragile** | Medium | Architectural design, but first-turn shortcut is a correctness gap | No |
| **`route_query` node / `RetrievalRoute`** | **fragile** | High | Label-filter examples are patches reacting to observed misroutes | No |
| **`execute_tools` — both-always bypass** | **correct (defended patch)** | Low | Principled patch promoted to permanent policy | No |
| **`check_empty` gate** | **correct** | Low | Principled; two-threshold logic is documented | No |
| **`generate_response` — system prompt** | **fragile** | High | Accumulated patch stack; no versioning, no regression gate | No |
| **`generate_response` — citation buffer** | **correct** | Low | Principled streaming design | No |
| **`query_paper_claims`** | **correct** | Low | Correct after METADATA_LOOKUP_LIMIT fix | Partial (matrix_runner, extraction only) |
| **`query_paper_chunks_scored` / threshold** | **fragile** | Medium | Threshold is a tuning constant with no re-tune mechanism | No |
| **`get_total_claim_count`** | **correct** | Low | Principled fix after hallucination discovery | No |
| **`api.py` — ChatEndpoint** | **correct** | Low | Principled async task decoupling | No |
| **`api.py` — `/history` endpoint** | **fragile** | Medium | Block structure stripped; history restores as plain text | No |
| **LangGraph / Postgres checkpointer** | **correct** | Low | Standard LangGraph pattern | No |
| **`useChatStream.ts`** | **correct** | Low | Principled SSE consumer | No |
| **`PaperChatStrip.tsx` — markdown assembly** | **correct** | Low | Fixed block-concatenation approach (supersedes earlier audit) | No |
| **`PaperChatStrip.tsx` — `REFUSAL_PATTERN`** | **fragile** | Medium | Regex on rendered text; no wire-level refusal flag | No |
| **`MatrixView.tsx` — AnimatePresence / key remount** | **correct** | Low | `key={activeChatId}` on `PaperChatStrip` is correct | No |
| **`signalRService.ts`** | **correct** | Low | Reconnect/group-leave ordering is principled | No |
| **`ChatMarkdown.tsx`** | **correct** | Low | Image-node sentinel design avoids rehype-raw XSS vector | No |
| **`prompts/` — chat prompt versioning** | **missing** | High | No content-hash, no storage, no change gate | No |
| **`docs/evals/golden_eval.json`** | **wrong** | Critical | Hand-authored file; no runner; not wired to CI | No (not wired at all) |

**Severity tiers**: Critical > High > Medium > Low.

---

## Section 1 — `paper_chat/agent.py`: `rewrite_query`

**Code path**: [`agent.py` L182–208](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L182-L208)

### 1. Principled design or patch?
Mostly principled. The decision to resolve pronouns before retrieval is a documented architectural choice (PR C2 era). The first-turn shortcut (`if len(messages) <= 1: return {standalone_query: latest}`) is clean.

### 2. LLM judgment calls / determinism
**LLM_CALL #1** (router model, `fast_llm`): Free-form text rewrite. No schema, no validation of the output. If the model returns an explanation prefix ("The standalone query is: ...") instead of a bare query, `standalone = result.content.strip() or latest` keeps the polluted string and sends it to retrieval. There is no deterministic fallback that would sanitize this.

The first-turn shortcut (single message, skip rewrite) is deterministic and correct. The multi-turn path is fully model-dependent.

**Specific variance risk**: A restated-claim question like "When you said it outperforms SOTA, what exactly did you mean?" will be rewritten by the fast router model. Whether it is rewritten to a clean embedding query or to something partial depends on the model's interpretation of the conversation window (`messages[-3:-1]`, i.e., up to two prior exchanges). No test covers this.

### 3. Automated failure detection
None. There is no test that feeds a multi-turn conversation through `rewrite_query` and checks whether the output is a valid, pronoun-free query string.

### 4. Rating
**Fragile.** The core idea is sound but the LLM output is consumed without any validation. A garbage rewrite silently poisons the retrieval step downstream and causes either a false refusal or an off-topic answer; neither is distinguishable from a retrieval-quality issue.

### 5. State flow
Reads: `state["messages"][-3:]` (LangGraph message list, persisted in Postgres checkpoint).
Writes: `state["standalone_query"]` (transient per-turn state, not persisted across turns).
Source of truth: **One** — the LangGraph checkpoint for `messages`; `standalone_query` is local to the turn.

---

## Section 2 — `route_query` / `RetrievalRoute`

**Code path**: [`agent.py` L211–235](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L211-L235), [`agent.py` L106–153](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L106-L153)

### 1. Principled design or patch?
**This is the single most patch-heavy component in the chat pipeline.**

The `RetrievalRoute` schema was originally a two-field struct. The `claim_lookup` field with its five-way enum (`position`, `label_filter`, `no_evidence`, `query`, `all`) grew through successive discovered bugs:
- `label_filter` was added when the router kept sending metadata-style questions to FTS (bug found: "Show me the strongest refusals" returned `claims=[]`). See [`chat_refusal_bug_2026-09-10.md`](file:///H:/Work%20projects/Prism/docs/audit/chat_refusal_bug_2026-09-10.md).
- The disambiguation between `label_filter` and `no_evidence` was added when "claims with no evidence" was incorrectly handled by `label_filter=not_supported` (which would include claims that *do* have refuting evidence).
- The `all` mode was added when "how many claims in total" triggered `query` mode with `limit=5`, producing a truncated count.

The `RetrievalRoute` description field is now 300 words of examples and explicit "do not use X for Y" disambiguators. This is a strong indicator of an enum whose boundaries were discovered symptom-by-symptom rather than designed from a taxonomy.

### 2. LLM judgment calls / determinism
**LLM_CALL #2** (router model, `fast_llm.with_structured_output(RetrievalRoute)`): This is the most non-deterministic decision in the entire pipeline.

The router must choose between five `claim_lookup` values and three `route` values given a free-form natural-language query. There is **no deterministic backstop**. The schema prompt gives examples, but:
- Phrasing variants not listed in examples can land on the wrong enum value. The original `chat_refusal_bug_2026-09-10.md` shows "strongest refusals" misrouting to `query` because the description examples used "which claims are refused?" — a different phrasing.
- The precedence rule "position > label_filter > no_evidence > query > all" is duplicated in both the `claim_lookup` schema description and in `execute_tools`. The LLM sees the description; `execute_tools` enforces it in code. But if the LLM *also* sets the wrong `claim_lookup` despite the description, `execute_tools` cannot fix it — it trusts whatever `claim_lookup` the router returned.
- The `RetrievalRoute` description now contains the text "strongest refusals" and "show me refusals" as explicit examples for `label_filter`. This is a patch: the examples were updated to cover the observed misroute. **Any phrasing not in the examples is unguarded.**

**Specific question for Phase 1**: A restated-claim question such as "You said Claim 5 wasn't supported — can you explain the evidence for it?" contains both a position reference (Claim 5) and a label reference (not_supported) and a content question (explain the evidence). The router must choose `position` (per the precedence rule). Whether it reliably does so across model runs is unknown.

### 3. Automated failure detection
None. The `execute_tools` bypass comment on L253 ("router's route_decision is retained for observability only") actually *masks* router failures: even if the router misclassifies `label_filter` as `query`, the agent still produces an answer (from both tools being called). The wrong answer is indistinguishable from a correct answer without knowing what `route_decision` was logged.

### 4. Rating
**Fragile.** The core design of structured-output routing is defensible (much better than string matching), but the schema is patch-accumulated. The lack of any deterministic backstop on the classification means any novel phrasing variant is a latent bug. Critically: the test surface that would catch a new misroute does not exist.

### 5. State flow
Reads: `state["standalone_query"]` (produced by `rewrite_query`).
Writes: `state["route_decision"]`, `state["claim_lookup"]`, `state["claim_position"]`, `state["claim_label_filter"]`.
Source of truth: **One** — these fields only exist in the transient turn state.

---

## Section 3 — `execute_tools` / `tools.py`

**Code path**: [`agent.py` L238–287](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L238-L287), [`tools.py` L107–278](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L107-L278)

### 1. Principled design or patch?

**The both-always bypass** ([`agent.py` L253–254](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L253-L254)) is a **patch promoted to permanent policy**. The comment cites `docs/slice3a_diagnosis_2026_08_25.md Root Cause #2` explicitly. It was the correct response to a failure mode (a route of "claims" with an empty FTS result causing a false refusal because chunks were never checked), but it means the `route` field of `RetrievalRoute` is permanently non-actionable. Every question pays the cost of both a Qdrant search and a Postgres query. The `route` field is logged for observability only.

**`_METADATA_LOOKUP_LIMIT = 50`** ([`tools.py` L118](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L118)): Was 25 when the claim-count truncation bug occurred (react.pdf has 28 claims, so the "all" route returned 25 and the LLM reported 25). Raised to 50 in a subsequent PR. 50 is a better starting point, but it is still an arbitrary ceiling with no principled basis: a paper with 60 claims will silently truncate again. The fix is a patch on a patch; the underlying issue (passing all claims into LLM context as a list) has no ceiling-independent solution.

**`CHUNK_SIMILARITY_THRESHOLD = 0.35`** ([`tools.py` L35](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L35)): Documented as a starting point picked before any real query/score distribution existed. The log infrastructure to retune it exists (`_log_chat_retrieval`), but the retuning has not happened. The comment on L35 says "retune from logs/chat/ alongside it" — this is unresolved debt.

**`OUT_OF_SCOPE_SCORE_FLOOR = 0.15`** ([`agent.py` L74](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L74)): Same situation — picked at PR time, no real data.

**`get_total_claim_count`** ([`tools.py` L281–303](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/tools.py#L281-L303)): Principled. The parallel COUNT(*) call in `asyncio.gather` decouples the true paper total from the subset retrieved by any route.

### 2. LLM judgment calls / determinism
No LLM judgment in this node. Fully deterministic once the router's inputs are fixed.

### 3. Automated failure detection
Partial. The matrix_runner harness covers the extraction/audit pipeline. It does not call the chat pipeline at all. Retrieval failures are caught only if they produce a wrong chat output that a human notices.

### 4. Rating
- `_METADATA_LOOKUP_LIMIT` path: **Fragile** — the 50-claim ceiling will silently truncate for larger papers.
- Both-always bypass: **Correct** (defended patch; it prevents a class of false refusals at the cost of the `route` field being ornamental).
- Threshold constants: **Fragile** — `0.35` and `0.15` are unjustified by data and untested.
- `get_total_claim_count`: **Correct**.

### 5. State flow
Reads: `state["standalone_query"]`, `state["active_file_id"]`, `state["claim_lookup"]`, `state["claim_position"]`, `state["claim_label_filter"]`.
Writes: `state["retrieved_claims"]`, `state["retrieved_chunks"]`, `state["chunk_scores"]`, `state["total_claim_count"]`.
Source of truth: **One** per field; all values are fetched from Postgres/Qdrant fresh each turn.

---

## Section 4 — `check_empty` gate

**Code path**: [`agent.py` L290–341](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L290-L341)

### 1. Principled design or patch?
Principled. The two-level refusal distinction (out-of-scope vs. in-scope-but-unsupported), the explicit handling of non-topical lookup modes (`position`, `label_filter`, `all`, `no_evidence`) as unconditional-proceed, and the score-floor backstop (`OUT_OF_SCOPE_SCORE_FLOOR`) are all documented decisions.

The only exception: `label_filter`, `all`, and `no_evidence` always return `"respond"` even when `claims=[]`. This is correct for `label_filter` ("zero claims with label X is itself a valid answer") but creates a path where `generate_response` is called with zero context for any of these modes if the DB returns nothing (e.g., no extraction yet for this paper). In that case, the LLM will produce a hallucinated or hedging answer rather than a hard refusal. This is a minor gap.

### 2. LLM judgment calls / determinism
Fully deterministic — pure Python conditionals on list lengths and float comparisons.

### 3. Automated failure detection
None for this node specifically.

### 4. Rating
**Correct.** Logic is clean and well-commented. One minor edge case (zero-context respond path for bulk modes) is worth noting but not urgent.

### 5. State flow
Read-only (conditional edge function — returns a string key, writes nothing to state).

---

## Section 5 — `generate_response` node

**Code path**: [`agent.py` L430–611](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L430-L611)

### 1. Principled design or patch?
**The system prompt is a patch stack.** The current system prompt in `generate_response` is ~115 lines of inline Python string. Its history, reconstructed from the audit documents:

1. **Original**: basic "answer only from the paper" instruction.
2. **Claim-count patch**: "The 'Total extracted claims' number in Paper Metadata above is the exact, authoritative count — state that number, do not re-derive a count" — added after the hallucinated-25-count bug.
3. **Formatting patch**: "Write plain conversational prose — never spec-sheet key-value pairs" — added after the dense-paragraph rendering bug.
4. **Categorization patch**: "When a question asks you to categorize...follow this exact structure every time, no variation: three sections in fixed order..." — added after unstructured claim-listing responses.
5. **Citation format patch**: "NEVER combine multiple claims into one bracket like [claim:ID1, claim:ID2]" — added after the citation rendering breakage.
6. **Status override patch**: "if status=not_supported, present the claim as not supported... EVEN IF the claim's own wording or a quoted passage sounds convincing" — added after the context-ignoring hallucination (see [chat_contradicts_label_2026-09-10.md](file:///H:/Work%20projects/Prism/docs/audit/chat_contradicts_label_2026-09-10.md)).
7. **Evidence status patch**: "Evidence spans with Status: Fail could not be verified as real quotes from the paper — never present a Fail'd span as confirmed evidence" — added in the same PR to surface span-level `grounding_status` (previously stripped).

Each patch was correct at the time. But there is no version tracking of the system prompt. It is an inline string in Python source — not a file in `prompts/`, not content-hashed, not listed in `PROMPT_FILENAMES` in `extraction/prompt_version.py`. The prompt has changed multiple times and those changes have zero traceability beyond git blame.

### 2. LLM judgment calls / determinism
**LLM_CALL #3** (main `llm`, `gemini-3.6-flash`): The generation call is the largest source of non-determinism in the entire pipeline. Every behavioral instruction in the system prompt is a free-form natural language directive the LLM may comply with imperfectly. The most critical ones with known failure histories:

- **"Do not re-derive the status"**: Confirmed to fail when evidence spans contain plausible-looking text. The prompt now adds "Status: Fail" to the evidence format (see `_build_context_block` L401–405), but whether this is sufficient depends on the model's attention to the evidence line vs. the prose quote. This has not been tested against adversarial inputs.
- **"State the Total extracted claims number exactly"**: Relies on the LLM reading and quoting a single number from the context block rather than counting items. Complied with correctly in normal operation, but the instruction is still free-form.
- **"150 words unless the user explicitly asks for a full breakdown"**: Model-dependent length compliance.

### 3. Automated failure detection
None. The system prompt has no regression gate. A change to a single line of the system prompt (e.g., softening the "never combine multiple claims" instruction) can reintroduce the citation rendering breakage with zero automated signal.

### 4. Rating
**Fragile.** The node's streaming architecture (citation-marker buffer, `get_stream_writer`, token delta assembly) is correct and principled. The system prompt it feeds into is accumulated patches with no versioning, no testing, and no automated regression protection. It is the single most fragile artifact in the chat path.

### 5. State flow
Reads: `state["messages"]` (full conversation history), `state["retrieved_claims"]`, `state["retrieved_chunks"]`, `state["total_claim_count"]`.
Writes: `state["messages"]` (appends one `AIMessage`).
The system prompt is constructed inline from state — it is not a separable artifact.

---

## Section 6 — `api.py`: ChatEndpoint and Checkpointer

**Code path**: [`api.py` L209–273](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L209-L273), [`api.py` L33–65](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L33-L65)

### 1. Principled design or patch?
**The `_run_paper_chat_graph` / task-decoupling pattern** is principled and well-documented. The comment on L184–198 correctly explains why `graph.astream()` must run in an independent `asyncio.Task` rather than be awaited inline: a client disconnect would tear down LangGraph's checkpoint commit bookkeeping mid-turn. The solution — drain the stream into a queue, let the event-stream generator drain the queue, and run `_run_paper_chat_graph` as a background task held in `app.state.background_chat_tasks` — correctly decouples the two lifecycles.

**The `inject-summary` endpoint** ([`api.py` L319–334](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L319-L334)) writes a synthetic AI message into a LangGraph checkpoint for chats that receive a cache-hit rather than running extraction themselves. This is a pragmatic patch for a coordination gap (not every chat can run `aupdate_state` directly); the mechanism is correct but the semantics are implicit: `inject_summary` injects into `compiled_agent` (the legacy general-chat graph), not `paper_chat_graph`. This is intentional (the "processing completed" summary is a pre-chat bootstrap message, not a paper-chat turn), but the shared checkpointer means a thread_id's history is mixed across two graphs. The `get_chat_history` endpoint ([`api.py` L276–312](file:///H:/Work%20projects/Prism/Prism.PythonService/api.py#L276-L312)) reads from `compiled_agent`, not `paper_chat_graph`. Whether history is being read from the correct graph for any given `chat_id` depends on which graph last wrote to that `thread_id`. This is an implicit coupling.

**The `/history` endpoint** has two issues:
1. It reads from `compiled_agent` not `paper_chat_graph` — if paper-chat turns are stored under a different checkpoint key format, they may not appear.
2. `safe_content` has a scoping bug at L292: `len(raw_content) > 0` is checked but `safe_content` is only assigned inside the `if` block and then used unconditionally at L301. If `raw_content` is empty (e.g., a message with content `[]`), `safe_content` will be the value from the *previous iteration* due to Python's scoping rules. This is a latent bug. It is not caught by any test.

### 2. LLM judgment calls / determinism
None in this layer.

### 3. Automated failure detection
None for chat-specific paths. The checkpointer setup is tested only implicitly by any successful round-trip; no unit test exercises disconnect/reconnect behavior.

### 4. Rating
- Task decoupling: **Correct**.
- Checkpointer setup: **Correct** (standard LangGraph pattern).
- `/history` endpoint: **Fragile** — `safe_content` scoping bug + graph-identity ambiguity.
- `inject-summary` graph mixing: **Fragile** — implicit coupling between two graphs sharing a checkpointer with no documented invariant.

### 5. State flow
The **shared checkpointer** (`AsyncPostgresSaver(app.state.pool)`) is used by both `compiled_agent` and `paper_chat_graph`. This means both graphs write to the same `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` tables, keyed by `thread_id`. State for a given `chat_id` can contain turns from either graph. There is no separation or namespacing. This is the one place where state is genuinely ambiguous at the storage layer.

---

## Section 7 — `prompts/` Directory: Versioning Asymmetry

**Code path**: [`extraction/prompt_version.py`](file:///H:/Work%20projects/Prism/Prism.PythonService/extraction/prompt_version.py), [`prompts/`](file:///H:/Work%20projects/Prism/Prism.PythonService/prompts/)

### 1. Principled design or patch?
The extraction pipeline has a principled prompt-versioning mechanism:
- All extraction/audit/grounding prompts live in `prompts/` as named files.
- `extraction/prompt_version.py` content-hashes them at startup.
- The hash is stored per extraction run in `document_extractors.fields["prompt_version"]`.
- `GET /api/system/prompt-version` exposes the current hash so the API service can detect stale cached results.

**Chat has none of this.** The chat system prompt is an inline Python string inside `generate_response` in `agent.py`. It is not a file in `prompts/`. It is not listed in `PROMPT_FILENAMES`. Its version is not stored anywhere. A change to the chat prompt:
- Is not detectable by the API service's prompt-version check.
- Is not covered by any hash comparison.
- Has no associated cache-invalidation mechanism.
- Has no regression gate.

The asymmetry is complete: extraction prompts are versioned, change-gated, and content-addressable; the chat prompt is an anonymous inline blob.

### 2. LLM judgment calls / determinism
N/A (configuration artifact, not executable code).

### 3. Automated failure detection
None for chat prompts. The extraction prompt version is CI-checked implicitly through matrix_runner using frozen fixtures. Chat is not.

### 4. Rating
**Missing.** A versioning mechanism exists and works for extraction. The equivalent mechanism is entirely absent for chat.

### 5. State flow
The chat system prompt is rebuilt from a Python string template on every call to `generate_response`. It has no persistent identity.

---

## Section 8 — Frontend: `useChatStream.ts`

**Code path**: [`useChatStream.ts` L1–208](file:///H:/Work%20projects/Prism/Prism.Web/src/hooks/useChatStream.ts#L1-L208)

### 1. Principled design or patch?
Principled. The hook manages:
- SSE frame parsing (correct `\n\n`-split framing).
- Append-to-last-turn for `text` frames (coalescing adjacent text deltas into the last TextBlock).
- Structured insertion for `claim_reference` frames.
- `AbortController` lifecycle (unmount cleanup, new-message pre-abort, user-stop).
- History restore on `chatId` change (with `cancelled` flag guard against race).

The comment at L39–43 is honest about what history restore *cannot* do: prior `claim_reference` blocks are not restored because the history endpoint serializes plain text only. This is a documented limitation, not a hidden gap.

### 2. LLM judgment calls / determinism
None. Pure client-side event processing.

### 3. Automated failure detection
None. There are no React testing library tests for this hook.

### 4. Rating
**Correct.** The design is clean. The one open issue — citation pills don't survive history restore — is documented and out of scope here.

### 5. State flow
Owns: `turns` (`ChatTurn[]`), `isSending` (`boolean`), `error` (`string | null`).
Source of truth: **React state** (`useState`). Chat turns are **not** written to `sessionStorage` or any browser-side persistence. On a hard refresh, turns are re-fetched from the Postgres history endpoint (as plain text). There is no drift between sessionStorage and React state (sessionStorage is not used at all for chat). The **only** potential drift is between the Postgres-restored `turns` (plain text) and a live-session `turns` (with citation blocks) — this is expected and documented.

---

## Section 9 — Frontend: `PaperChatStrip.tsx`

**Code path**: [`PaperChatStrip.tsx` L1–660](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L1-L660)

### 1. Principled design or patch?
**Block concatenation (`turnToMarkdown`)** ([`PaperChatStrip.tsx` L63–66](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L63-L66)): Principled. The current implementation reassembles the block stream into a single markdown string (`citeMarker(b.claim_id)` for citation blocks) and feeds it into a single `<ChatMarkdown>` instance. This is the correct fix documented in `chat_structured_citations_2026-09-10.md` §4. The previous approach (separate `<ChatMarkdown>` per TextBlock) shattered markdown structures at citation boundaries and was the root cause of the dense-paragraph rendering bug.

**`REFUSAL_PATTERN`** ([`PaperChatStrip.tsx` L23–24](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L23-L24)):
```typescript
/\b(can'?t|cannot|unable to|does(?:n't| not) (?:address|cover|mention|discuss)|outside (?:the )?scope|no (?:relevant )?(?:information|evidence))\\b/i
```
This is a **pattern-match heuristic on rendered text**. It is used to select follow-up prompt suggestions: if a refusal is detected, suggestions change to "What CAN this paper answer?" / "Show me the main claims". This is entirely decorative and has no effect on routing or behavior. However, it means the component is attempting to reverse-engineer the backend's intent from text it already parsed — a direction inversion that will silently break if the backend's refusal phrasing changes.

**Hardcoded avatar** ([`PaperChatStrip.tsx` L389](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L389)): The user avatar renders the hardcoded letter "N". Not a bug, but signals the component was written for a specific user.

### 2. LLM judgment calls / determinism
None.

### 3. Automated failure detection
None.

### 4. Rating
**Correct** for the core message rendering path. **Fragile** for `REFUSAL_PATTERN` (heuristic, no wire signal).

### 5. State flow
Receives all state from `useChatStream` props — no local duplication. `isChatOpen` and `chatHeight` are purely UI state with no backend correlation.

---

## Section 10 — Frontend: `MatrixView.tsx` — AnimatePresence / Remount Behavior

**Code path**: [`MatrixView.tsx` L226–318](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L226-L318), [`MatrixView.tsx` L311](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L311)

### 1. Principled design or patch?
The `PaperChatStrip` is mounted as:
```tsx
<PaperChatStrip key={activeChatId} chatId={activeChatId} activeFileId={activePaperId} ... />
```
`key={activeChatId}` forces React to unmount and remount `PaperChatStrip` (and therefore `useChatStream`) when the active chat changes. This is principled: it resets all local state cleanly and re-triggers the history fetch for the new `chatId`.

**Bug 4 (tab-switch state loss) — status**: Confirmed resolved by `key={activeChatId}` on `PaperChatStrip`. The earlier `AnimatePresence` identity issue was that `isChatOpen` was being reset on every paper switch because the component was remounted. Based on the current code, `isChatOpen` lives in `PaperChatStrip`'s own state, so remounting *does* reset it to `false` — but that is correct behavior (opening chat on paper A, switching to paper B should start with chat closed). There is no remaining AnimatePresence remount bug for this layout. The earlier diagnosis in `ui_chat_audit_2026-09-08.md` predates the current key-based remount design and the block-concatenation renderer fix.

The `AnimatePresence mode="wait"` wraps the `showActivityView` / `paperClaims` branches ([`MatrixView.tsx` L227](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L227)). This governs the fade transition between the activity view and the claims matrix, not chat state. `PaperChatStrip` is inside the `paperClaims` branch only, so the animation does not affect it.

### 2. LLM judgment calls / determinism
None.

### 3. Automated failure detection
None.

### 4. Rating
**Correct.** Bug 4 as originally described (tab-switch UI state loss due to AnimatePresence remount) is resolved by the `key={activeChatId}` design. There is no remaining live instance of this bug in the current code.

### 5. State flow
`activeChatId` and `activePaperId` are props from the parent (app-level state). They are the single source of truth for which chat/paper is active. No duplication in sessionStorage.

---

## Section 11 — Frontend: `signalRService.ts`

**Code path**: [`signalRService.ts` L1–115](file:///H:/Work%20projects/Prism/Prism.Web/src/services/signalRService.ts#L1-L115)

### 1. Principled design or patch?
Principled. The join-then-leave ordering (join new group before leaving old group, L74–85) is correctly designed to prevent a window where the connection is a member of zero groups. The `onreconnected` handler re-joins `currentChatId` after a reconnect, preventing ghost subscriptions.

**Relation to chat stream**: SignalR is used for upload progress and extraction status events (document hub), not for chat SSE. Chat streaming uses a separate direct HTTP SSE connection (`/api/chat/ask/stream`). The two channels are independent. A SignalR reconnect does not affect an in-flight chat SSE stream.

### 2. LLM judgment calls / determinism
None.

### 3. Automated failure detection
None.

### 4. Rating
**Correct.** The SignalR service is not in the hot path for chat responses. It handles extraction progress events correctly.

### 5. State flow
Singleton service. `currentChatId` tracks the currently joined group (in-memory). No duplication.

---

## Section 12 — Frontend: `ChatMarkdown.tsx`

**Code path**: [`ChatMarkdown.tsx` L1–122](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/chat/ChatMarkdown.tsx#L1-L122)

### 1. Principled design or patch?
Principled. The image-node sentinel design (`![](cite:<id>)` / `![](cursor:1)`) avoids the `rehype-raw` plugin, which would allow arbitrary LLM-generated HTML to render as live DOM. The custom `urlTransform` only exempts the two known sentinel schemes, so genuine http/https links from the LLM go through normal sanitization. The orphaned-citation guard (L93–94, `if (!claim) return null`) silently drops pills for claim IDs not in the current turn's retrieved set.

### 2. LLM judgment calls / determinism
None (pure rendering).

### 3. Automated failure detection
None.

### 4. Rating
**Correct.** The XSS defense via image-node sentinels is principled and intentional.

### 5. State flow
Read-only (props only). No external state reads.

---

## Section 13 — Eval: `docs/evals/golden_eval.json`

**Code path**: [`golden_eval.json`](file:///H:/Work%20projects/Prism/docs/evals/golden_eval.json), [`.github/workflows/eval.yml`](file:///H:/Work%20projects/Prism/.github/workflows/eval.yml)

### 1. Principled design or patch?
`golden_eval.json` is a thoughtfully constructed evaluation artifact. Its 21 questions cover factual retrieval, table extraction, reasoning aggregation, and grounding-negative cases across three papers (Reflexion, CoT, ReAct). The `regression_gate` metadata field at the top states:
```json
"run_policy": "Run before and after any model, prompt, or retrieval change. A grounding_negative FAIL blocks the change."
```

This is an aspirational contract, not an enforced one. **`golden_eval.json` is not wired to the CI pipeline at any point.**

Evidence:
- [`eval.yml`](file:///H:/Work%20projects/Prism/.github/workflows/eval.yml) runs three steps: `pytest eval/tests/`, `check_fixture_freshness`, and `matrix_runner --source fixture`.
- `matrix_runner` runs against `docs/evals/matrix_eval.json` (the claims-level matrix), not `golden_eval.json`.
- `golden_eval.json` contains chat-style QA questions that require calling `/api/chat/ask/stream` against a live (or mocked) paper. The eval harness has no infrastructure to do this.
- The `eval/` directory contains no file that reads or references `golden_eval.json` — confirmed by inspection of `matrix_runner.py`, `data_source.py`, `scorer.py`, `matcher.py`.

### 2. LLM judgment calls / determinism
N/A (a data file, not executable code).

### 3. Automated failure detection
**None.** A grounding-negative question added to `golden_eval.json` would never fail CI regardless of what the chat agent does, because nothing in CI ever invokes the chat agent against it.

### 4. Rating
**Wrong.** The file's own `regression_gate` metadata claims it is "the CI gate", but it is not executed by anything. Its `run_policy` is an unmet promise. The file exists as a specification document, not as an enforced contract. The gap between the claim ("CI gate") and the reality (no runner) is the most consequential single finding in this review.

### 5. State flow
Static JSON file. No runtime state.

---

## Resolution of Specific Open Items

### Router Non-Determinism on Restated-Claim Phrasing

**Finding**: The routing mechanism is **LLM-classification-only with no deterministic backstop**.

The exact mechanism is `fast_llm.with_structured_output(RetrievalRoute)` at [`agent.py` L215–225](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L215-L225). The `claim_lookup` enum examples have been updated reactively to include "strongest refusals" and "show me refusals" after the 2026-09-10 bug. The `RetrievalRoute` description now explicitly lists example phrasings for `label_filter`, but these examples are a finite list in a prompt — any unstated variant is unguarded.

A restated-claim question such as "You said Claim 5 wasn't supported — why exactly?" contains both a position signal ("Claim 5") and a content question. The precedence rule "position > label_filter" is written into the schema description but is not enforced by any deterministic code path. If the model routes this to `query` or `label_filter` instead of `position`, the tool call uses FTS rather than a direct `WHERE position = 5` lookup. The FTS may or may not match claim 5's text. There is no observable failure signal.

**Shape of a durable fix**: A deterministic pre-filter (e.g., a regex match on "claim \d+" in the standalone query before the LLM call) would remove this variance entirely for the most common position-reference phrasing. The LLM router would remain for the cases a regex cannot cover.

### Context-Ignoring Hallucination (Chat Contradicts Label)

**Finding**: Root cause traced and partially fixed; residual risk identified.

Per [`chat_contradicts_label_2026-09-10.md`](file:///H:/Work%20projects/Prism/docs/audit/chat_contradicts_label_2026-09-10.md), the confirmed mechanism was:
1. Evidence spans were formatted without their `grounding_status` field. The LLM saw plausible-sounding quote text and interpreted it as real evidence.
2. The system prompt contained "when the user asks for evidence, quote the listed evidence spans verbatim, since that's the paper's own words" — this was an explicit instruction to trust the unverified quotes over the claim's `not_supported` label.

**Current code** ([`agent.py` L401–405](file:///H:/Work%20projects/Prism/Prism.PythonService/paper_chat/agent.py#L401-L405)): The evidence format now includes `Status: {grounding_status}`, and the system prompt includes "Evidence spans with Status: Fail could not be verified as real quotes from the paper — never present a Fail'd span as confirmed evidence."

**Residual risk**: Whether the LLM reliably defers to `Status: Fail` over compelling quote text remains untested. The system prompt instruction is now in direct conflict with the evidential weight of the quote text for claims where the auditor generated highly plausible hallucinations. No adversarial test case exists that verifies this specific instruction is followed consistently.

**Is this session's prompt changes plausibly touching this path?** Yes. The current system prompt (as of this review) includes both the `Status:` field in evidence spans and the "never present a Fail'd span" instruction. Both were added in the same PR that diagnosed the bug. These changes are present in the code now but were not present in the 2026-09-08 audit's version.

### Bug 4 — Tab-Switch UI State Loss

**Finding**: Confirmed resolved, independent of the AnimatePresence remount issue.

The current code mounts `PaperChatStrip` with `key={activeChatId}` ([`MatrixView.tsx` L311](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L311)). This forces a full React unmount/remount on paper switch. Chat UI state (`isChatOpen`, `chatHeight`) resets to defaults on every paper switch — which is the correct behavior. The earlier `ui_chat_audit_2026-09-08.md` diagnosis of "AnimatePresence remount resets isChatOpen" predates the `key=` fix and the current component layout. In the current code, there is no live instance of tab-switch state loss that would persist across a paper switch.

There is a separate, minor issue: switching papers while a chat response is streaming will abort the in-flight SSE fetch (`controllerRef.current?.abort()` in `useChatStream.ts` unmount cleanup), but the backend graph task is already decoupled (in `background_chat_tasks`) and will continue to completion and persist. The partial response appears on the abandoned turn only if the user switches back before the stream ends, but the turn's `isStreaming` flag is never flipped to `false` because `markLastTurnDone` is only called inside the SSE loop. The turn will appear to the user as an infinitely-thinking bubble until they refresh. This is a separate minor UI bug.

### `golden_eval.json` Execution Status

**Finding**: Not executed by anything. The CI gate described in its metadata is a fiction.

The CI pipeline ([`eval.yml`](file:///H:/Work%20projects/Prism/.github/workflows/eval.yml)) runs `matrix_runner --source fixture`, which evaluates the claims-level extraction pipeline using frozen fixtures in `docs/evals/fixtures/`. It does not invoke the chat agent. `golden_eval.json` has no runner, no fixtures, no test infrastructure, and no CI job.

**Smallest viable harness**: The minimum to make chat a regression-gated surface equivalent to claims:
1. A `chat_eval_runner.py` script that, for each question in `golden_eval.json`, calls `/api/chat/ask/stream` with the `chat_id` of a pre-seeded conversation for the relevant paper (requiring a fixture extraction to be loaded into the test DB first).
2. A `chat_scorer.py` that applies a graded rubric: for `grounding_negative` items, any substantive answer is a FAIL; for factual items, an LLM-as-judge call verifies the expected_answer against the actual response.
3. A CI step that runs `chat_eval_runner.py --source fixture` and fails if any `grounding_negative` item produces a non-refusal response.

The blocking dependency is step 1: the fixture-mode runner for extraction already exists, but chat eval requires a live (or stubbed) LLM response, which means the harness either needs real API keys in CI (expensive and non-deterministic) or a pre-recorded golden-response fixture per question (same freeze/re-record discipline as `matcher_gold.json`). The second approach maps cleanly to how the existing harness works.

---

## Stop Point

This report ends here. All findings above are diagnostic. No code change has been made, proposed in detail, or begun. Phase 1 scope, prioritization, and fix strategy are for Nitin to decide based on this report.

**The four highest-severity findings to inform Phase 1 prioritization:**

1. **`golden_eval.json` has no runner (Critical)** — the self-described CI gate for chat is not wired to CI. Chat has no regression protection at all. Every fix made to date has been unverified against a repeatable baseline.
2. **Chat system prompt has no version tracking (High)** — a single-line change can silently reintroduce any of the bugs fixed since 2026-09-08 with no automated detection.
3. **Router is LLM-only with no deterministic backstop (High)** — novel phrasing variants are unguarded. The `claim_lookup` schema is a symptom-driven patch accumulation, not a classification taxonomy.
4. **`_METADATA_LOOKUP_LIMIT = 50` is an arbitrary ceiling (Medium)** — a paper with >50 claims will silently truncate in bulk-retrieval modes, reproducing the exact class of bug that was fixed when it was raised from 25.
