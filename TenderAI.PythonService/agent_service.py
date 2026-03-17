import os
from typing import TypedDict,Annotated
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph,END
from langchain_core.tools import tool
from langgraph.prebuilt import tools_condition,ToolNode
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from RAGService import RAGService
import time

memory = MemorySaver()

class AgentState(TypedDict):
    messages : Annotated[list,add_messages]

llm = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    api_key=os.getenv("AI_API_KEY")
)

ragservice = RAGService()

@tool
def search_tender_doc(query : str) ->str:
    """use this tool to search qdrant database for tender  docs, calulations, meeting notes,budgets"""

    print(f' [🔍] Agent searching database for: "{query}"')

    results = ragservice.search_db(user_query=query,limit=7)

    final_result = ""
    if not results:
        return "No relevant information is found in the tender documents"
    
    else:
        for hit in results:
            score = hit.score
            fileName = hit.payload.get("filename","unKnown")
            content = hit.payload.get("text","")
            final_result +=  f"Source : {fileName}\nScore : {score}\nContent : {content}"

    return final_result    
   
tools = [search_tender_doc]
tool_nodes = ToolNode(tools= tools)
llm_with_tools = llm.bind_tools(tools)



def agent_node(state:AgentState)->str:
    time.sleep(10)
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)

    return {"messages" : [response]}

def decide_next_step(state:AgentState) -> str:
    last_msg = state["messages"][-1]

    if 'Error' in last_msg.content:
        return "Search_Again_Node"
    
    else:
        return "End_Node"
    
workflow = StateGraph(AgentState)

workflow.add_node("agent",agent_node)
workflow.add_node("tools",tool_nodes)
workflow.set_entry_point("agent")

workflow.add_conditional_edges("agent",tools_condition)
workflow.add_edge("tools","agent")

agent_app = workflow.compile(checkpointer=memory)

print(" [✅] Agent Workflow Compiled!")
