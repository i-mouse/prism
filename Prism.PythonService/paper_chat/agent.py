"""LangGraph agent for paper-scoped chat (Slice 3a).

API surfaces confirmed via web search before writing this module (this repo
pins langgraph==1.0.9, langchain-google-genai==4.2.1, fastapi==0.135.1):
  - get_stream_writer (langgraph.config): call it inside an async node to
    emit arbitrary JSON-able payloads on stream_mode="custom". Works
    without an explicit `writer` node parameter on Python >=3.11 (this repo
    requires >=3.13, so the plain get_stream_writer() call is safe).
  - graph.astream(..., stream_mode=["custom", "messages"]) yields
    (mode, chunk) tuples when stream_mode is a list. "messages" chunks are
    (message_chunk, metadata) tuples carrying token deltas + the node name
    that produced them; "custom" chunks are exactly what was passed to
    get_stream_writer().
  - langchain_google_genai.ChatGoogleGenerativeAI.bind_tools /
    with_structured_output are unchanged from the pattern already used in
    agent_service.py.

Citation design (Task 6, option (a) chosen): generate_response prompts
Gemini to mark citations inline as `[claim:<claim_id>]`. Rather than
forwarding raw token deltas (which would leak literal `[claim:...]` text
to the client), the node consumes the model's astream() itself, buffers
tokens, and emits fully-formed blocks via get_stream_writer() on
stream_mode="custom" only: prose before a marker as TextBlock, the marker
itself resolved against retrieved_claims as ClaimReferenceBlock. A trailing
"[" with no closing "]" yet is held back across chunks so a marker can
never be split into visible garbage. stream_mode="messages" is requested
by the FastAPI endpoint (matches the task template) but its frames are not
forwarded to the client - "custom" is the only channel that reaches SSE.
Option (b) (a model-invoked cite_claim tool) was rejected for this slice:
Gemini interleaving text streaming with a parallel tool call mid-turn is
not guaranteed to preserve citation position relative to the prose, and
option (a) needs no extra graph nodes.
"""
import asyncio
import re
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from config import settings
from paper_chat.tools import (
    CHUNK_SIMILARITY_THRESHOLD,
    query_paper_chunks_scored,
    query_paper_claims,
)

REFUSAL_OUT_OF_SCOPE_MESSAGE = (
    "I can only answer questions about the claims, evidence, or refusals in "
    "this paper. For an overall summary, see the Overview tab."
)

# Below this raw cosine score (well under CHUNK_SIMILARITY_THRESHOLD from
# paper_chat/tools.py), a chunk carries no meaningful topical signal at all.
# Used only in check_empty to tell a genuinely out-of-scope question (e.g.
# "who won the World Cup") apart from one that's in-scope but unsupported
# (e.g. "does ReAct work on physical robots" - related to the paper's
# domain, just not demonstrated by it). Same caveat as
# CHUNK_SIMILARITY_THRESHOLD: a starting point picked in PR C2
# (fix/chat-retrieval-refusal) before real query data existed, not a
# claim of correctness - retune from logs/chat/ alongside it.
OUT_OF_SCOPE_SCORE_FLOOR = 0.15

CITATION_MARKER_RE = re.compile(r"\[claim:([a-zA-Z0-9-]+)\]")

QUERY_REWRITE_INSTRUCTIONS = (
    "Rewrite the user's latest message as a single standalone search query, "
    "resolving pronouns and implicit references using the conversation "
    "history below. Output ONLY the rewritten query as plain text - no "
    "quotes, no explanation, no prefix.\n\n"
    "Example:\n"
    "History:\n"
    "user: What is ReAct?\n"
    "assistant: ReAct is a paradigm combining reasoning and acting in LLMs.\n"
    "Latest message: How was it evaluated?\n"
    "Standalone query: How was ReAct evaluated?"
)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    active_file_id: str
    standalone_query: str
    retrieved_claims: list[dict]
    retrieved_chunks: list[dict]
    chunk_scores: list[float]
    route_decision: str
    claim_lookup: str
    claim_position: int | None
    claim_label_filter: str | None


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
    claim_lookup: Literal["position", "label_filter", "query", "all"] = Field(
        default="query",
        description=(
            "How query_paper_claims should look up claims. 'position': the user "
            "named a specific claim number, e.g. 'claim 11', 'show me claim 3', "
            "'what does claim 5 say' - set claim_position to that number. "
            "'label_filter': the user asked for claims sharing one audit label, "
            "e.g. 'which claims are refused?', 'show partial claims', 'are there "
            "any supported claims?' - set claim_label_filter to 'supported', "
            "'partially_supported', or 'not_supported' to match. 'all': the user "
            "asked about the paper's OVERALL audit state rather than one label or "
            "claim, e.g. 'any refusal?', 'how many claims in total', 'how many "
            "are supported vs refused' - fetches every claim so it can be counted "
            "exactly. 'query': anything else - a topical question best answered "
            "by full-text search over claim content, e.g. 'claims about "
            "hallucination'. Precedence when a question could fit more than one: "
            "position > label_filter > query > all."
        ),
    )
    claim_position: int | None = Field(
        default=None,
        description="The claim number the user asked about. Only set when claim_lookup='position'.",
    )
    claim_label_filter: Literal["supported", "partially_supported", "not_supported"] | None = Field(
        default=None,
        description="The audit label the user asked about. Only set when claim_lookup='label_filter'.",
    )


llm = ChatGoogleGenerativeAI(
    model=settings.llm_chat_model,
    api_key=settings.ai_api_key,
)

fast_llm = ChatGoogleGenerativeAI(
    model=settings.llm_router_model,
    api_key=settings.ai_api_key,
)


def get_safe_text(content) -> str:
    if isinstance(content, list):
        if len(content) > 0:
            first_item = content[0]
            if isinstance(first_item, dict):
                return first_item.get("text", str(content))
            return str(first_item)
        return ""
    elif isinstance(content, dict):
        return content.get("text", str(content))
    return str(content) if content else ""


# --- Nodes ---

async def rewrite_query(state: AgentState):
    """Turns the latest message into a standalone search query using up to
    the last 3 messages of conversation history, so pronouns like "it" in a
    follow-up ("How was it evaluated?") resolve before hitting retrieval.
    First turn (no history yet) skips the LLM call entirely."""
    print(" [REWRITE] Node: rewrite_query executing...")
    messages = state["messages"]
    latest = get_safe_text(messages[-1].content)

    if len(messages) <= 1:
        print(" [REWRITE] first turn, skipping rewrite")
        return {"standalone_query": latest}

    history_lines = [
        f"{'user' if m.type == 'human' else 'assistant'}: {get_safe_text(m.content)}"
        for m in messages[-3:-1]
    ]
    prompt = (
        f"{QUERY_REWRITE_INSTRUCTIONS}\n\n"
        f"History:\n{chr(10).join(history_lines)}\n"
        f"Latest message: {latest}\n"
        "Standalone query:"
    )
    result = await fast_llm.ainvoke(prompt)
    standalone = get_safe_text(result.content).strip() or latest
    print(f" [REWRITE] standalone_query={standalone!r}")
    return {"standalone_query": standalone}


async def route_query(state: AgentState):
    print(" [ROUTE] Node: route_query executing...")
    query = state["standalone_query"]

    structured_llm = fast_llm.with_structured_output(RetrievalRoute)
    result = await structured_llm.ainvoke(
        "Always call at least one retrieval tool for any user question about the "
        "paper. Prefer query_paper_chunks for open-ended or general questions "
        "(main contribution, summary, methodology). Prefer query_paper_claims for "
        "questions about specific verdicts, audit results, or claim-level content. "
        "Call both when the question spans both (e.g. 'why was claim X refused'). "
        "Never respond without retrieving. If in doubt, call query_paper_chunks.\n\n"
        "Decide what to retrieve from the active paper to answer this question.\n"
        f"Question: {query}"
    )
    print(
        f" [ROUTE] route_decision={result.route} claim_lookup={result.claim_lookup} "
        f"claim_position={result.claim_position} claim_label_filter={result.claim_label_filter}"
    )
    return {
        "route_decision": result.route,
        "claim_lookup": result.claim_lookup,
        "claim_position": result.claim_position,
        "claim_label_filter": result.claim_label_filter,
    }


async def execute_tools(state: AgentState):
    print(" [TOOLS] Node: execute_tools executing...")
    query = state["standalone_query"]
    active_file_id = state["active_file_id"]
    route = state.get("route_decision", "both")
    claim_lookup = state.get("claim_lookup", "query")
    claim_position = state.get("claim_position")
    claim_label_filter = state.get("claim_label_filter")

    # The router's route_decision is retained for observability only. Tool
    # execution always calls both retrieval tools: a route of "claims" whose
    # single tool call comes up empty must not silently skip chunks (or vice
    # versa) and fall through to a false refusal - see
    # docs/slice3a_diagnosis_2026_08_25.md Root Cause #2. Deliberate, do not
    # remove (see PR C2 description).
    if route != "both":
        print(f" [TOOLS] route_decision={route!r} restricted a tool; calling both anyway")

    # query_paper_claims itself also enforces this precedence (position >
    # label_filter > query > all) - built explicitly here too so each call
    # only carries the one argument that's actually relevant to claim_lookup.
    if claim_lookup == "position":
        claims_tool_input = {"active_file_id": active_file_id, "position": claim_position}
    elif claim_lookup == "label_filter":
        claims_tool_input = {"active_file_id": active_file_id, "label_filter": claim_label_filter}
    elif claim_lookup == "all":
        claims_tool_input = {"active_file_id": active_file_id}
    else:
        claims_tool_input = {"active_file_id": active_file_id, "query": query, "limit": 5}

    claims, (chunks, chunk_scores) = await asyncio.gather(
        query_paper_claims.ainvoke(claims_tool_input),
        query_paper_chunks_scored(active_file_id=active_file_id, query=query, limit=5),
    )

    print(f" [TOOLS] retrieved_claims={len(claims)} retrieved_chunks={len(chunks)} chunk_scores={chunk_scores}")
    return {"retrieved_claims": claims, "retrieved_chunks": chunks, "chunk_scores": chunk_scores}


def check_empty(state: AgentState) -> str:
    """Routes to generate_response only when something confidently supports
    an answer. What "confident" means depends on claim_lookup:
      - position/label_filter/all are explicit metadata/identity lookups,
        not fuzzy topical matches - any non-empty result IS the answer,
        whatever label those claims happen to carry (e.g. a label_filter of
        "not_supported" returning 3 claims is a complete, correct answer to
        "which claims are refused?", not a low-confidence one). label_filter
        and all also treat a genuinely empty result as answerable ("zero
        claims with that label" is itself the correct answer) rather than a
        refusal. A position miss is the one case that IS a refusal: the
        user named a specific claim number that doesn't exist.
      - query (the default topical FTS mode) keeps the original confidence
        cascade: a claim the grounding pipeline itself labeled "supported",
        or a chunk above CHUNK_SIMILARITY_THRESHOLD, proceeds to generate.
        Otherwise it picks between two refusals using whatever weaker
        signal exists - a claim matched by FTS but not labeled "supported",
        or a chunk that scored above OUT_OF_SCOPE_SCORE_FLOOR but below
        CHUNK_SIMILARITY_THRESHOLD - as in-scope-but-unsupported. Neither
        signal at all means the question doesn't relate to this paper.
    """
    claims = state.get("retrieved_claims") or []
    chunks = state.get("retrieved_chunks") or []
    chunk_scores = state.get("chunk_scores") or []
    claim_lookup = state.get("claim_lookup", "query")

    if claim_lookup == "position":
        if claims:
            print(" [CHECK_EMPTY] position lookup found the claim, proceeding to generate")
            return "respond"
        print(" [CHECK_EMPTY] position lookup found no such claim - refusing")
        return "refuse_unsupported"

    if claim_lookup in ("label_filter", "all"):
        print(f" [CHECK_EMPTY] {claim_lookup} lookup returned {len(claims)} claims, proceeding to generate")
        return "respond"

    supported_claims = [c for c in claims if c.get("label") == "supported"]
    if supported_claims or chunks:
        print(f" [CHECK_EMPTY] supported_claims={len(supported_claims)} chunks={len(chunks)}, proceeding to generate")
        return "respond"

    has_related_claim = bool(claims)
    top_chunk_score = max(chunk_scores, default=0.0)
    has_related_chunk = top_chunk_score >= OUT_OF_SCOPE_SCORE_FLOOR
    if has_related_claim or has_related_chunk:
        print(f" [CHECK_EMPTY] no confident match, but related signal found (claims={len(claims)}, top_chunk_score={top_chunk_score}) - in-scope-unsupported")
        return "refuse_unsupported"

    print(f" [CHECK_EMPTY] no signal at all (claims=0, top_chunk_score={top_chunk_score}) - out-of-scope")
    return "refuse_out_of_scope"


async def refusal_out_of_scope_node(state: AgentState):
    print(" [REFUSE] Node: refusal_out_of_scope_node executing")
    writer = get_stream_writer()
    writer({"type": "text", "content": REFUSAL_OUT_OF_SCOPE_MESSAGE})
    return {"messages": [AIMessage(content=REFUSAL_OUT_OF_SCOPE_MESSAGE)]}


def _build_unsupported_message(retrieved_claims: list[dict], retrieved_chunks: list[dict]) -> str:
    topics: list[str] = []
    for c in retrieved_claims:
        summary = c.get("claim_summary")
        if summary and summary not in topics:
            topics.append(summary)
        if len(topics) == 2:
            break
    if len(topics) < 2:
        for ch in retrieved_chunks:
            section = ch.get("section")
            if section and section not in topics:
                topics.append(section)
            if len(topics) == 2:
                break

    if not topics:
        return "The paper doesn't demonstrate this."
    if len(topics) == 1:
        return f"The paper doesn't demonstrate this. It covers {topics[0]} but not this."
    return f"The paper doesn't demonstrate this. It covers {topics[0]} and {topics[1]} but not this."


async def refusal_unsupported_node(state: AgentState):
    print(" [REFUSE] Node: refusal_unsupported_node executing")
    if state.get("claim_lookup") == "position":
        position = state.get("claim_position")
        message = f"I couldn't find claim {position} in this paper."
    else:
        message = _build_unsupported_message(
            state.get("retrieved_claims") or [], state.get("retrieved_chunks") or []
        )
    writer = get_stream_writer()
    writer({"type": "text", "content": message})
    return {"messages": [AIMessage(content=message)]}


def _build_context_block(retrieved_claims: list[dict], retrieved_chunks: list[dict]) -> str:
    parts = []

    if retrieved_claims:
        claim_blocks = []
        for c in retrieved_claims:
            evidence_text = "; ".join(
                f'"{e.get("source_text", "")}" ({e.get("source_section") or "unknown section"})'
                for e in (c.get("evidence_spans") or [])[:2]
            ) or "none"
            claim_blocks.append(
                f"- Claim {c['position']} (claim_id={c['claim_id']}) label={c['label']} "
                f"grounding_status={c['grounding_status']} missing={c['missing']} "
                f"reason={c.get('reason') or 'n/a'}\n"
                f"  summary: {c['claim_summary']}\n"
                f"  verbatim: \"{c['claim_text_verbatim']}\"\n"
                f"  evidence: {evidence_text}"
            )
        parts.append(f"Retrieved claims from this paper:\n" + "\n".join(claim_blocks))

    if retrieved_chunks:
        chunks_text = "\n---\n".join(
            f"[{c.get('section') or 'unknown section'}] {c['chunk_text']}"
            for c in retrieved_chunks
        )
        parts.append(f"Retrieved raw paper text:\n{chunks_text}")

    return "\n\n".join(parts)


async def generate_response(state: AgentState):
    print(" [GENERATE] Node: generate_response executing...")
    writer = get_stream_writer()
    retrieved_claims = state.get("retrieved_claims") or []
    retrieved_chunks = state.get("retrieved_chunks") or []
    claims_by_id = {c["claim_id"]: c for c in retrieved_claims}

    context_block = _build_context_block(retrieved_claims, retrieved_chunks)
    system_instruction = SystemMessage(content=(
        "You are a strict, paper-scoped research assistant. Answer ONLY using the "
        "context below, drawn from the single active paper. Do not use outside "
        "knowledge. When a sentence relies on a specific retrieved claim, immediately "
        "append a citation marker in the exact form [claim:<claim_id>] using one of "
        "the claim_id values listed below - never invent a claim_id, never cite a "
        "claim_id not present below. If the context does not support an answer, say "
        "so plainly instead of guessing.\n\n"
        "Each claim below carries internal audit metadata set by Prism's own "
        "grounding pipeline, not by you - answer from it honestly rather than "
        "re-deriving your own verdict, but never expose it as data. Concretely: "
        "never write the field names themselves (label, reason, grounding_status, "
        "missing, evidence_spans) and never format anything as \"field: value\". "
        "Translate a claim's label into plain language instead of naming it - "
        "supported means the paper's evidence confirms it, partially_supported "
        "means the evidence is relevant but doesn't fully back it, not_supported "
        "means the evidence doesn't back it. Paraphrase the internal reason in one "
        "plain sentence instead of quoting it - write something like \"Claim 3 is "
        "partial: the paper cites one relevant passage but doesn't fully back the "
        "assertion,\" never \"reason: cited evidence supports the claim across 1 "
        "passage.\" The one exception is evidence text itself: when the user asks "
        "for evidence, quote the listed evidence spans verbatim, since that's the "
        "paper's own words, not internal metadata. If the retrieved claims and "
        "text are topically related but do not clearly support the specific "
        "comparison or conclusion being asked, say plainly \"The paper doesn't "
        "demonstrate this\" instead of stretching a partial or unsupported claim "
        "into a confident answer.\n\n"
        "Formatting rules, no exceptions: speak like a research assistant "
        "answering a colleague, not a database printout. Keep answers under "
        "about 150 words unless the user explicitly asks for a full breakdown. "
        "Write plain conversational prose - never spec-sheet key-value pairs. "
        "A short bullet list is fine for enumerating several items, but never "
        "nest bullets more than one level deep. Never add section headers (e.g. "
        "\"Performance on X:\", \"Combining Y:\") unless the user explicitly asked "
        "for a structured breakdown.\n\n"
        "The [claim:<claim_id>] marker renders as a small pill showing ONLY that "
        "claim's label (Supported / Partial / Not Supported) - it does NOT show "
        "the claim's summary or any other content. That means a claim is only "
        "meaningful to the reader if YOU state what it says; the marker alone "
        "conveys nothing about the claim's content. Never render a claim as just "
        "its number and citation with no summary - that's useless to the reader. "
        "When citing a single claim inline, paraphrase what it says in your own "
        "sentence and put the marker at the end of that sentence. When listing "
        "multiple claims, give one line per claim in the form \"Claim N - "
        "<summary in 15 words or fewer>. [claim:<claim_id>]\" - for example "
        "\"Claim 0 - ReAct outperforms SOTA baselines on diverse tasks with "
        "better interpretability. [claim:abc123]\". You may still skip repeating "
        "the claim's label as a word (\"supported\", \"refused\", \"partial\") "
        "right next to the citation, since the pill already shows that part - "
        "but the summary text itself must always be there.\n\n"
        "For a question about the paper's overall audit state (e.g. \"any "
        "refusal?\", \"how many supported?\", \"how many claims in total\"), the "
        "claims listed below already include every claim for this paper - give "
        "the exact count in one sentence (including zero if nothing matches), "
        "then list them one per line in the \"Claim N - summary. [claim:ID]\" "
        "form above if it adds value. For a question about one specific label "
        "(e.g. \"which claims are refused?\", \"show partial claims\"), say how "
        "many there are in one sentence, then list every one of them in that "
        "same form - if none were retrieved, say plainly that none exist rather "
        "than guessing.\n\n"
        f"{context_block}"
    ))

    messages_for_llm = [system_instruction] + state["messages"]

    buffer = ""
    full_text = ""
    async for chunk in llm.astream(messages_for_llm):
        delta = get_safe_text(chunk.content)
        if not delta:
            continue
        buffer += delta
        full_text += delta

        while True:
            match = CITATION_MARKER_RE.search(buffer)
            if not match:
                break
            pre = buffer[:match.start()]
            if pre:
                writer({"type": "text", "content": pre})
            claim_id = match.group(1)
            claim = claims_by_id.get(claim_id)
            if claim is not None:
                writer({
                    "type": "claim_reference",
                    "claim_id": claim_id,
                    "claim_summary": claim["claim_summary"],
                    "display_label": claim["label"],
                })
            buffer = buffer[match.end():]

        last_bracket = buffer.rfind("[")
        if last_bracket != -1 and "]" not in buffer[last_bracket:]:
            safe_len = last_bracket
        else:
            safe_len = len(buffer)
        if safe_len > 0:
            writer({"type": "text", "content": buffer[:safe_len]})
            buffer = buffer[safe_len:]

    if buffer:
        writer({"type": "text", "content": buffer})

    return {"messages": [AIMessage(content=full_text)]}


# --- Compilation ---

def build_paper_chat_graph(checkpointer):
    workflow = StateGraph(AgentState)
    workflow.add_node("rewrite_query", rewrite_query)
    workflow.add_node("route_query", route_query)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("refusal_out_of_scope_node", refusal_out_of_scope_node)
    workflow.add_node("refusal_unsupported_node", refusal_unsupported_node)
    workflow.add_node("generate_response", generate_response)

    workflow.add_edge(START, "rewrite_query")
    workflow.add_edge("rewrite_query", "route_query")
    workflow.add_edge("route_query", "execute_tools")
    workflow.add_conditional_edges("execute_tools", check_empty, {
        "refuse_out_of_scope": "refusal_out_of_scope_node",
        "refuse_unsupported": "refusal_unsupported_node",
        "respond": "generate_response",
    })
    workflow.add_edge("refusal_out_of_scope_node", END)
    workflow.add_edge("refusal_unsupported_node", END)
    workflow.add_edge("generate_response", END)

    return workflow.compile(checkpointer=checkpointer)
