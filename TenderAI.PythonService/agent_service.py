import os
import json
from typing import TypedDict, Annotated, Optional, Literal
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from RAGService import RAGService

# --- Pydantic Models ---
class RouteIntent(BaseModel):
    intent: Literal["casual_chat", "tender_search", "memory_query"] = Field(
        description=(
            "Categorize the user's input. "
            "1. 'casual_chat': Greetings and pleasantries. "
            "2. 'tender_search': Asking for specific clauses, rules, or deep facts found INSIDE the uploaded documents. "
            "3. 'memory_query': Asking about the system, chat history, or metadata (e.g., 'how many files are there?', 'what did I just say?')."
        )
    )

class RetrievedChunk(TypedDict):
    filename: str
    content: str
    score: float

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    original_query: str
    rewritten_query: str
    intent: str 
    retrieved_chunks: list[RetrievedChunk]
    grounding_passed: bool
    confidence_score: float
    final_answer: Optional[str]
    caveat: Optional[str]

# --- LLM Initialization ---
llm = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    api_key=os.getenv("AI_API_KEY"),
    temperature=0.2 
)

fast_llm = ChatGoogleGenerativeAI(
    # model="gemini-flash-latest",
    model="gemini-3.1-flash-lite-preview" ,
    api_key=os.getenv("AI_API_KEY"),
    temperature=0.0
)

ragservice = RAGService()

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
    return str(content)

# --- Nodes ---

async def intent_decision_node(state: AgentState):
    """The Bouncer: Analyzes the question and decides which graph path to take.""" 
    print(" [🚦] Node: Intent Router executing...")
    last_message = state["messages"][-1].content

    structured_llm = fast_llm.with_structured_output(RouteIntent)
    response = await structured_llm.ainvoke(last_message)
    
    print(f" [🛣️] Routing to: {response.intent}")
    return {"intent": response.intent, "original_query": last_message}

async def casual_chat_node(state: AgentState):
    print(" [👋] Node: Casual Chat executing...")
    system_prompt = SystemMessage(content=(
        "You are a strict, professional Tender AI assistant. "
        "The user is making casual conversation. "
        "Respond in ONE OR TWO sentences maximum. Be polite, but immediately guide them back to asking about their tender documents."
    ))
    
    # Only passing last 3 messages to save tokens/money
    recent_history = state["messages"][-3:]
    
    messages_for_llm = [system_prompt] + recent_history
    response = await fast_llm.ainvoke(messages_for_llm)
    
    return {"messages": [response]}

async def query_rewriter_node(state: AgentState):
    print(" [⚙️] Node: Query Rewriter executing...")
    original_query = state["messages"][-1].content
    
    rewrite_prompt = f"""You are an expert search query optimizer for legal and tender documents.
    Convert the following user question into a dense string of keywords optimized for a vector database search.
    Do not answer the question. Just output the keywords.
    
    User Question: {original_query}
    Optimized Keywords:"""
    
    response = await fast_llm.ainvoke(rewrite_prompt)
    optimized_query = get_safe_text(response.content).strip()
    print(f" [🔄] Rewrote: '{original_query}' -> '{optimized_query}'")
    
    return {
        "original_query": original_query,
        "rewritten_query": optimized_query
    }

@tool
def search_tender_doc(query: str) -> str:
    """Search the tender document database for relevant information.
    Use specific keywords from the question."""
    print(f' [🔍] Agent searching database for: "{query}"')
    
    # FIX: Enterprise Fault Tolerance via Try/Except
    try:
        results = ragservice.search_db(user_query=query, limit=7)
        if not results:
            return "NO_RESULTS_FOUND"
        
        structured_results = [{"filename": hit.payload.get("filename", "Unknown"), "score": hit.score, "content": hit.payload.get("text", "")} for hit in results]
        return json.dumps(structured_results)
    except Exception as e:
        print(f" [⚠️] Database Error: {e}")
        return "DATABASE_ERROR: Could not retrieve documents at this time."


async def agent_node(state: AgentState):
    """The core reasoning engine."""
    print(" [🧠] Node: Agent thinking...")
    messages = state["messages"]
    rewritten_query = state.get("rewritten_query", "")

    if rewritten_query:
        system_instruction = f"""You are a strict, helpful legal and tender assistant.
        CRITICAL RULE: Even if you see a summary of the document in your chat history, you MUST use the `search_tender_doc` tool to fetch the exact source chunks before answering. Do not answer from memory alone.
        
        You MUST use the following optimized keywords in your search tool:
        "{rewritten_query}"
        """
        messages_for_llm = [SystemMessage(content=system_instruction)] + messages
    else:
        # It's a memory query, just let the agent look at the history normally
        messages_for_llm = messages

    response = await llm_with_tools.ainvoke(messages_for_llm)
    return {"messages": [response]}

async def grounding_checker_node(state: AgentState):
    print(" [🛡️] Node: Grounding Checker executing...")
    
    proposed_answer = get_safe_text(state["messages"][-1].content)
    
    tool_messages = [m.content for m in state["messages"] if m.type == "tool"]
    
    if not tool_messages or "NO_RESULTS_FOUND" in tool_messages or "DATABASE_ERROR" in str(tool_messages):
        print(" [🛡️] No context used. Bypassing grounding check.")
        return {"grounding_passed": True, "caveat": "No documents found to support or deny this."}

    context = "\n---\n".join(tool_messages)
    grading_prompt = f"""You are a strict legal auditor. 
    Look at the Proposed Answer, and check if it is completely supported by the Source Documents.
    If the Proposed Answer contains facts, numbers, or claims NOT found in the Source Documents, you must fail it.
    
    Source Documents:
    {context[:4000]}
    
    Proposed Answer:
    {proposed_answer}
    
    Reply ONLY with the word "PASS" if the answer is completely supported, or "FAIL" if it contains ungrounded claims/hallucinations."""

    response = await fast_llm.ainvoke(grading_prompt)
    
    grade = get_safe_text(response.content).strip().upper()

    if "PASS" in grade:
        print(" [✅] Grounding Check: PASSED")
        return {"grounding_passed": True, "caveat": None}
    else:
        print(" [❌] Grounding Check: FAILED (Hallucination Detected!)")
        return {"grounding_passed": False, "caveat": "⚠️ Warning: Parts of this answer could not be verified in the uploaded documents."}
    

# --- Edges and Routing ---
tools = [search_tender_doc]
tool_nodes = ToolNode(tools=tools)
llm_with_tools = llm.bind_tools(tools)

def route_by_intent(state: AgentState):
    """The physical switch for the graph edge."""
    intent = state.get("intent")
    
    if intent == "casual_chat":
        return "casualchat"
    elif intent == "memory_query":
        return "agent" # Skip the rewriter! Go straight to the brain.
    else:
        return "query_rewriter" # Only do heavy vector searches for 'tender_search'
    
def route_after_agent(state: AgentState):
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "grounding_checker"

# --- Compilation ---
workflow = StateGraph(AgentState)
workflow.add_node("casualchat", casual_chat_node)
workflow.add_node("intent", intent_decision_node)
workflow.add_node("query_rewriter", query_rewriter_node)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_nodes)
workflow.add_node("grounding_checker", grounding_checker_node)

workflow.set_entry_point("intent")
workflow.add_conditional_edges("intent", route_by_intent, {
    "casualchat": "casualchat",
    "agent": "agent",                 # <--- The new bypass lane
    "query_rewriter": "query_rewriter"
})
workflow.add_edge("casualchat", END)
workflow.add_edge("query_rewriter", "agent")
workflow.add_conditional_edges("agent", route_after_agent)
workflow.add_edge("tools", "agent")
workflow.add_edge("grounding_checker", END)

app = workflow.compile()
print(" [✅] Enterprise CRAG Workflow Compiled!")