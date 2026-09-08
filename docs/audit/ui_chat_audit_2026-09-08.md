# Prism UI & Chat Audit — 2026-09-08

## UI/UX findings

### Issue: "Started grounding" spam
- Reproduction: Upload a paper and monitor the live log stream on the right during the grounding stage. The log appends a new line saying "Started grounding" ~19 times in a row.
- Root cause: Python side `Prism.PythonService/extraction/pipeline_events.py` `emit_grounding_progress` sends progress events `{"stage": "grounding", "completed": X, "total": Y}` without a `detail` string. `PaperActivityView.tsx:43` falls back to `ev.detail || Started ${ev.stage}` and appends it to the log array on every single progress event.
- Fix category: event emission (Python) / render logic (React)
- Effort: XS (< 15 min)

### Issue: Silent gap during "Preparing"
- Reproduction: Upload a paper and observe the left-side stage checklist. "Parsed 33 pages, 111 chunks" appears immediately after `preparing` completes, then there is an 8-minute gap before `extracting` completes and "Extracted paper metadata" appears.
- Root cause: `PaperActivityView.tsx` hardcodes incorrect subtitles for the stages in the left checklist (lines 160 & 163). It assigns "Parsed 33 pages..." to the completion of `preparing`, and "Extracted paper metadata" to the completion of `extracting`. The 8-minute void is actually the `extract_claims` pipeline running during the `extracting` stage.
- Fix category: render logic / copy change
- Effort: XS (< 15 min)

### Issue: Stale copy on completed papers
- Reproduction: Wait for a paper's extraction to complete and view the activity page header. The pill correctly states "Completed Xm ago" but the subtitle still reads "AUDITING PAPER".
- Root cause: `PaperActivityView.tsx:91` hardcodes `<p>Auditing Paper</p>` regardless of the `extractionStatus`.
- Fix category: render logic / copy change
- Effort: XS (< 15 min)

### Issue: "Tip" card generic copy
- Reproduction: Look at the Tip card at the bottom right of the extraction page.
- Root cause: `PaperActivityView.tsx:266` hardcodes the generic marketing copy "Prism analyzes each claim and grounds it in the paper's own evidence."
- Fix category: copy change
- Effort: XS (< 15 min)

## Chat findings

### Test case: "What's the main contribution of this paper?"
- Actual: The key contributions of this paper are:
1. **Introducing ReAct:** The paper introduces ReAct, a prompt-based paradigm that synergizes reasoning and acting in language models for general task-solving [claim:fab607fd-1aa4-46b0-906c-1adfd83e4718].
(Output continues with correctly cited lists from the retrieved context).
- Expected: Correctly answers the question using both tools.
- Failure stage: router (bypassed)
- Root cause: The router's logic is explicitly bypassed in `execute_tools` (`if route != "both": print(...)`), so both tools are forcefully called. This masks any potential router failures.

### Test case: "What benchmarks was ReAct evaluated on?"
- Actual: Based on the paper, ReAct was evaluated on four main benchmarks:
1. **HotpotQA:** A question answering benchmark [claim:85215850-feb4-42e1-bf19-7446d5d4a595][claim:97cd38da-3738-4283-a59a-01f2ba3912ee].
2. **Fever:** A fact verification benchmark [claim:85215850-feb4-42e1-bf19-7446d5d4a595][claim:97cd38da-3738-4283-a59a-01f2ba3912ee].
3. **ALFWorld:** A synthetic text-based interactive decision-making benchmark [claim:4790fb22-d199-425a-b4c8-883792142dc4].
4. **WebShop:** An interactive web navigation and shopping decision-making benchmark [claim:4790fb22-d199-425a-b4c8-883792142dc4].
- Expected: Correctly outputs the benchmarks with citations.
- Failure stage: none (successful despite router bypass)
- Root cause: N/A

### Test case: "How does ReAct compare to Chain-of-Thought on HotPotQA?"
- Actual: On HotpotQA, ReAct compares to Chain-of-Thought (CoT) in the following ways... By interacting with a Wikipedia API, ReAct is competitive with CoT reasoning [claim:97cd38da-3738-4283-a59a-01f2ba3912ee]...
- Expected: Correctly answers with citations.
- Failure stage: none
- Root cause: N/A

### Test case: "Does ReAct work on physical robots?"
- Actual: Based on the provided text, the paper does not test or demonstrate ReAct on physical robots. Its experiments are limited to interactive text-based and web environments, specifically Wikipedia API interactions, synthetic text games (ALFWorld), and web navigation simulations (WebShop).
- Expected: The chat should output the strict refusal message: "The paper doesn't discuss this. I can only answer questions grounded in the uploaded paper."
- Failure stage: retrieval / check_empty
- Root cause: `check_empty` expects empty retrieval results to trigger `refusal_node`, but `query_paper_claims` falls back to the top N claims by position when the query fails to match, and `query_paper_chunks` always returns results via un-thresholded cosine similarity. The context is never empty, bypassing the refusal node and forcing the LLM to synthesize a soft refusal.

### Test case: "How does ReAct compare to fine-tuned baselines?"
- Actual: Based on the provided paper text, when models are fine-tuned (tested using PaLM-8B and PaLM-62B on HotpotQA with 3,000 examples):
* **Superiority over Fine-Tuned Baselines:** Fine-tuning ReAct or Act yields significantly better performance than fine-tuning Standard or CoT baselines.
- Expected: The chat should refuse ("the paper doesn't demonstrate this").
- Failure stage: retrieval / synthesis
- Root cause: The retrieval tools return related context regardless of the strict matching intent. The LLM then answers the question using the retrieved context because the context isn't empty, bypassing the strict refusal mechanism.

### Test case: "Is ReAct better than traditional RL?"
- Actual: Yes. On interactive decision-making benchmarks, few-shot ReAct outperforms reinforcement learning (RL) methods [claim:4790fb22-d199-425a-b4c8-883792142dc4]...
- Expected: The chat should refuse ("the paper doesn't demonstrate this").
- Failure stage: retrieval / synthesis
- Root cause: Same as above. `query_paper_claims` and `query_paper_chunks` return context that contains IL/RL references, causing the LLM to answer the question instead of hitting the hard refusal block.

### Test case: "Who won the World Cup?"
- Actual: Based on the provided context, the paper does not contain information about who won the World Cup.
- Expected: The chat should output the loud refusal message via `refusal_node`.
- Failure stage: retrieval / check_empty
- Root cause: Out-of-scope questions still return the paper's top N claims and chunks, so `check_empty` evaluates to false. The LLM wastes tokens synthesizing a generic context-based refusal instead of the system catching it at the router/retrieval layer.

### Test case: "Summarize the follow-up paper"
- Actual: Based on the provided context, there is no information about a follow-up paper.
- Expected: The chat should output the loud refusal message via `refusal_node`.
- Failure stage: retrieval / check_empty
- Root cause: Same as above.

### Test case: "What is ReAct?" -> "How was it evaluated?"
- Actual: 
"What is ReAct?": **ReAct** is a general paradigm that combines verbal reasoning traces and task-specific actions...
"How was it evaluated?": ReAct was evaluated across a diverse set of language and decision-making tasks in a few-shot setup...
- Expected: The chat should gracefully answer using the conversational context.
- Failure stage: retrieval
- Root cause: In `agent.py`, `route_query` and `execute_tools` extract only the last message for the query (`query = get_safe_text(state["messages"][-1].content)`). The conversation history is ignored during retrieval, meaning pronouns like "it" in "How was it evaluated?" are completely unresolvable by the vector database and full-text search. The retrieval only succeeds through broad fallback matches.

## Recommended fix order
1. Fix `query_paper_claims` and `query_paper_chunks` to allow returning empty results (e.g., threshold cosine similarity, remove fallback) so `check_empty` and `refusal_node` work properly (Addresses all Refusal & Out-of-scope test cases).
2. Fix the hardcoded stage subtitles in `PaperActivityView.tsx` to align with the actual pipeline stages (Addresses "Silent gap during Preparing").
3. Update `route_query` and `execute_tools` in `agent.py` to synthesize a standalone search query using the full conversation history, resolving pronouns (Addresses Multi-turn failures).
4. Remove the `route != "both"` hack in `execute_tools` and fix the router prompt/logic so it accurately delegates tasks (Addresses Router bypass).
5. Add a `detail` string to `emit_grounding_progress` in Python and update the React logs fallback to avoid duplicate spam (Addresses "Started grounding" spam).
6. Update `PaperActivityView.tsx` header to dynamically reflect `extractionStatus` (Addresses "Stale copy").
7. Update `PaperActivityView.tsx` Tip card to be context-aware or remove it (Addresses generic copy).

## Open questions
- Should the `refusal_node` message be customized based on whether the query was completely out of scope vs. just unsupported by the paper's findings?
- What is the appropriate cosine similarity threshold for `query_paper_chunks` to confidently trigger an empty result?
- Should `route_query` be merged into the query-synthesis step for multi-turn conversations, or remain a separate LLM call?
