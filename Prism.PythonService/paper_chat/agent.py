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
from paper_chat.tools import query_paper_chunks, query_paper_claims

REFUSAL_MESSAGE = (
    "The paper doesn't discuss this. I can only answer questions grounded "
    "in the uploaded paper."
)

CITATION_MARKER_RE = re.compile(r"\[claim:([a-zA-Z0-9-]+)\]")


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    active_file_id: str
    retrieved_claims: list[dict]
    retrieved_chunks: list[dict]
    route_decision: str


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


llm = ChatGoogleGenerativeAI(
    model=settings.llm_agent_model,
    api_key=settings.ai_api_key,
    temperature=0.2,
)

fast_llm = ChatGoogleGenerativeAI(
    model=settings.llm_fast_model,
    api_key=settings.ai_api_key,
    temperature=0.0,
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

async def route_query(state: AgentState):
    print(" [ROUTE] Node: route_query executing...")
    last_message = get_safe_text(state["messages"][-1].content)

    structured_llm = fast_llm.with_structured_output(RetrievalRoute)
    result = await structured_llm.ainvoke(
        "Always call at least one retrieval tool for any user question about the "
        "paper. Prefer query_paper_chunks for open-ended or general questions "
        "(main contribution, summary, methodology). Prefer query_paper_claims for "
        "questions about specific verdicts, audit results, or claim-level content. "
        "Call both when the question spans both (e.g. 'why was claim X refused'). "
        "Never respond without retrieving. If in doubt, call query_paper_chunks.\n\n"
        "Decide what to retrieve from the active paper to answer this question.\n"
        f"Question: {last_message}"
    )
    print(f" [ROUTE] route_decision={result.route}")
    return {"route_decision": result.route}


async def execute_tools(state: AgentState):
    print(" [TOOLS] Node: execute_tools executing...")
    query = get_safe_text(state["messages"][-1].content)
    active_file_id = state["active_file_id"]
    route = state.get("route_decision", "both")

    # The router's route_decision is retained for observability only. Tool
    # execution always calls both retrieval tools: a route of "claims" whose
    # single tool call comes up empty must not silently skip chunks (or vice
    # versa) and fall through to a false refusal - see
    # docs/slice3a_diagnosis_2026_08_25.md Root Cause #2.
    if route != "both":
        print(f" [TOOLS] route_decision={route!r} restricted a tool; calling both anyway")

    tool_input = {"active_file_id": active_file_id, "query": query, "limit": 5}
    claims, chunks = await asyncio.gather(
        query_paper_claims.ainvoke(tool_input),
        query_paper_chunks.ainvoke(tool_input),
    )

    print(f" [TOOLS] retrieved_claims={len(claims)} retrieved_chunks={len(chunks)}")
    return {"retrieved_claims": claims, "retrieved_chunks": chunks}


def check_empty(state: AgentState) -> str:
    claims = state.get("retrieved_claims") or []
    chunks = state.get("retrieved_chunks") or []
    if not claims and not chunks:
        print(" [CHECK_EMPTY] both tools returned empty, refusing")
        return "refuse"
    print(f" [CHECK_EMPTY] claims={len(claims)} chunks={len(chunks)}, proceeding to generate")
    return "respond"


async def refusal_node(state: AgentState):
    print(" [REFUSE] Node: refusal_node executing (empty retrieval)")
    writer = get_stream_writer()
    writer({"type": "text", "content": REFUSAL_MESSAGE})
    return {"messages": [AIMessage(content=REFUSAL_MESSAGE)]}


def _build_context_block(retrieved_claims: list[dict], retrieved_chunks: list[dict]) -> str:
    parts = []

    if retrieved_claims:
        claims_text = "\n".join(
            f"- claim_id={c['claim_id']} label={c['label']}: {c['claim_summary']}"
            f" (verbatim: \"{c['claim_text_verbatim']}\")"
            for c in retrieved_claims
        )
        parts.append(f"Retrieved claims from this paper:\n{claims_text}")

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
    workflow.add_node("route_query", route_query)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("refusal_node", refusal_node)
    workflow.add_node("generate_response", generate_response)

    workflow.add_edge(START, "route_query")
    workflow.add_edge("route_query", "execute_tools")
    workflow.add_conditional_edges("execute_tools", check_empty, {
        "refuse": "refusal_node",
        "respond": "generate_response",
    })
    workflow.add_edge("refusal_node", END)
    workflow.add_edge("generate_response", END)

    return workflow.compile(checkpointer=checkpointer)
