from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import HumanMessage
from agent_service import  workflow,ragservice
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from memory_db import create_db_connection_pool
import os
from contextlib import asynccontextmanager
import json
import psycopg

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting FastAPI server", flush=True)

    app.state.pool = create_db_connection_pool()
    await app.state.pool.open()

    # Use a raw connection with autocommit=True for setup (avoids transaction block error)
    async with await app.state.pool.getconn() as conn:
        await conn.set_autocommit(True)
        checkpointer = AsyncPostgresSaver(conn)
        await checkpointer.setup()

    # Now create the real checkpointer using the pool for all requests
    app.state.checkpointer = AsyncPostgresSaver(app.state.pool)
    app.state.compiled_agent = workflow.compile(checkpointer=app.state.checkpointer)

    print("✅ Checkpointer and Agent ready", flush=True)

    yield

    await app.state.pool.close()


pythonAPI = FastAPI(title="TenderAI python agent", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str
    chatId: str = "default_thread"

@pythonAPI.post("/api/chat/ask")
async def ask_agent_with_memory(request: QueryRequest, contextrequest: Request):
    """API endpoint to ask agent questions with postgres memory"""
    try:
        input_config = {"configurable": {"thread_id": request.chatId}}
        input_message = {"messages": [HumanMessage(content=request.question)]}

        # 1. Run the Graph
        result = await contextrequest.app.state.compiled_agent.ainvoke(input=input_message, config=input_config)
        
        # 2. Extract Text
        final_raw_answer = result["messages"][-1].content
        if isinstance(final_raw_answer, list):
            final_answer = final_raw_answer[0].get("text", str(final_raw_answer))
        else:
            final_answer = str(final_raw_answer)

        # 3. Extract Metadata
        caveat = result.get("caveat")
        is_trusted = result.get("grounding_passed", True)
        intent = result.get("intent", "casual_chat")

        # 4. Extract Sources (from the tool message)
        sources = []
        if intent == "tender_search":
            # Read messages in reverse to find the most recent tool call
            for msg in reversed(result["messages"]):
                if msg.type == "tool":
                    if msg.content not in ["NO_RESULTS_FOUND", "DATABASE_ERROR"]:
                        try:
                            sources = json.loads(msg.content)
                        except json.JSONDecodeError:
                            pass
                    break # Stop looking after we find the latest tool response

        # 5. Send it all back
        return {
            "answer": final_answer,
            "caveat": caveat,
            "isTrusted": is_trusted,
            "intent": intent,
            "sources": sources
        }

    except Exception as e:
        print(f"Error while processing ask agent API: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@pythonAPI.get("/api/chat/{chatid}/history")
async def get_chat_history(chatid: str, http_request: Request):
    """API endpoint to get chat history from postgres memory"""
    try:
        input_config = {"configurable": {"thread_id": chatid}}
        state = await http_request.app.state.compiled_agent.aget_state(config=input_config)

        if not state or not hasattr(state, "values") or "messages" not in state.values:
            return {"messages": []}

        formatted_messages = []
        for msg in state.values["messages"]:
            if msg.type in ["human", "ai"]:
                
                # --- 🛡️ THE FIX: Safely extract the string from the history object ---
                raw_content = msg.content
                if len(raw_content) > 0:
                    if isinstance(raw_content, list):
                        safe_content = raw_content[0].get("text", str(raw_content))
                    elif isinstance(raw_content, dict):
                        safe_content = raw_content.get("text", str(raw_content))
                    else:
                        safe_content = str(raw_content)
                    # ---------------------------------------------------------------------

                formatted_messages.append({
                    "id": os.urandom(4).hex(),
                    "role": "user" if msg.type == "human" else "ai",
                    "content": safe_content,
                    "timestamp": "loaded-from-db"
                })

        return {"messages": formatted_messages}

    except Exception as e:
        print(f"Error while processing get chat history: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- SYSTEM RESET (NUCLEAR OPTION) ---
@pythonAPI.delete("/api/system/reset")
async def wipe_ai_system(http_request: Request): # 🛡️ ADD Request parameter
    try:
        # 1. WIPE QDRANT (Vector Database)
        try:
            ragservice.client.delete_collection(collection_name="tender_collection")
        except Exception as e:
            print(f" [⚠️] Qdrant wipe warning: {e}")

        # 2. WIPE LANGGRAPH MEMORY (Using existing connection pool)
        # 🛡️ This guarantees it works with Aspire's injected database
        async with await http_request.app.state.pool.getconn() as conn:
            await conn.execute("TRUNCATE TABLE checkpoints, checkpoint_blobs, checkpoint_writes CASCADE;")
            await conn.commit() # Don't forget to commit the wipe!
                
        print(" [🧨] NUCLEAR WIPE COMPLETE: Vectors and Memory erased.")
        return {"status": "success", "message": "AI Brain wiped."}
        
    except Exception as e:
        print(f" [❌] Nuclear Wipe Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))     
if __name__ == "__main__":
    import uvicorn
    porta = int(os.environ.get("PORT", 8000))
    uvicorn.run(pythonAPI, host="0.0.0.0", port=porta)