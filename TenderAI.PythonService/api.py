from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import HumanMessage
from agent_service import agent_app, workflow
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from memory_db import create_db_connection_pool
import os
from contextlib import asynccontextmanager


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

    print("✅ Checkpointer ready", flush=True)

    yield

    await app.state.pool.close()


pythonAPI = FastAPI(title="TenderAI python agent", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str
    chatId: str = "default_thread"


@pythonAPI.post("/api/chat/ask")
async def ask_agent_with_memory(request: QueryRequest, contextRequest: Request):
    """API endpoint to ask agent questions with postgres memory"""
    try:
        checkpointer = contextRequest.app.state.checkpointer
        compiled_app = workflow.compile(checkpointer=checkpointer)

        input_config = {"configurable": {"thread_id": request.chatId}}
        input_message = {"messages": [HumanMessage(content=request.question)]}

        result = await compiled_app.ainvoke(input=input_message, config=input_config)
        final_raw_answer = result["messages"][-1].content

        if isinstance(final_raw_answer, list):
            final_answer = final_raw_answer[0].get("text", str(final_raw_answer))
        else:
            final_answer = final_raw_answer

        return {"answer": final_answer}

    except Exception as e:
        print(f"Error while processing ask agent API: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


@pythonAPI.get("/api/chat/{chatId}/history")
async def get_chat_history(chatId: str, http_request: Request):
    """API endpoint to get chat history from postgres memory"""
    try:
        checkpointer = http_request.app.state.checkpointer
        compiled_app = workflow.compile(checkpointer=checkpointer)

        input_config = {"configurable": {"thread_id": chatId}}
        state = await compiled_app.aget_state(config=input_config)

        if not state or not hasattr(state, "values") or "messages" not in state.values:
            return {"messages": []}

        formatted_messages = []
        for msg in state.values["messages"]:
            if msg.type in ["human", "ai"]:
                
                # --- 🛡️ THE FIX: Safely extract the string from the history object ---
                raw_content = msg.content
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


if __name__ == "__main__":
    import uvicorn
    porta = int(os.environ.get("PORT", 8000))
    uvicorn.run(pythonAPI, host="0.0.0.0", port=porta)