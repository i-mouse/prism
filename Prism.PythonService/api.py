from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage
import agent_service
from agent_service import workflow
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from config import settings
from memory_db import create_db_connection_pool
from paper_chat.agent import build_paper_chat_graph
from paper_chat.blocks import ClaimReferenceBlock, TextBlock, block_to_sse
from correlation import correlation_id_var, get_correlation_id
from telemetry import init_telemetry
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
import asyncio
import os
import uuid
from contextlib import asynccontextmanager
import json
import psycopg

CORRELATION_ID_HEADER = "X-Correlation-Id"

tracer = init_telemetry("prism-python-api")
HTTPXClientInstrumentor().instrument()
PsycopgInstrumentor().instrument()


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
    app.state.paper_chat_graph = build_paper_chat_graph(app.state.checkpointer)

    print("[OK] Checkpointer and Agent ready", flush=True)

    yield

    await app.state.pool.close()


pythonAPI = FastAPI(title="Prism python agent", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(pythonAPI)


@pythonAPI.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
    correlation_id_var.set(correlation_id)

    span = trace.get_current_span()
    span.set_attribute("correlation_id", correlation_id)

    response = await call_next(request)
    response.headers[CORRELATION_ID_HEADER] = correlation_id
    return response


def _trace_id_hex() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")


def _problem_response(status_code: int, title: str, detail: str, type_: str = "about:blank") -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": type_,
            "title": title,
            "status": status_code,
            "detail": detail,
            "traceId": _trace_id_hex(),
            "correlationId": get_correlation_id(),
        },
        media_type="application/problem+json",
    )


@pythonAPI.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _problem_response(status_code=exc.status_code, title=exc.detail, detail=exc.detail)


@pythonAPI.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    print(f"Unhandled exception: {exc!r}", flush=True)
    trace.get_current_span().set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
    # No confirmed dev/prod environment flag exists in config.py (verified: no such
    # field there, and AppHost.cs never sets ASPNETCORE_ENVIRONMENT/ENVIRONMENT for
    # either Python resource) - defaults to always hiding exception details. Flagged
    # in the PR description for a follow-up decision on adding one.
    return _problem_response(
        status_code=500,
        title="An unexpected error occurred",
        detail="An internal error occurred",
    )


@pythonAPI.get("/health", include_in_schema=False)
async def health():
    return {"status": "healthy"}


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
        if intent == "prism_search":
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


class ChatAskRequest(BaseModel):
    chat_id: str
    active_file_id: str
    message: str


def serialize_event_to_sse(event) -> str | None:
    """Turns one (mode, data) tuple from graph.astream(stream_mode=[...]) into
    an SSE frame. Only "custom" events (get_stream_writer emissions from the
    agent's nodes) reach the client - see paper_chat/agent.py module docstring
    for why raw "messages" token deltas are not forwarded."""
    mode, data = event
    if mode != "custom":
        return None
    try:
        block_type = data.get("type")
        if block_type == "text":
            block = TextBlock(content=data["content"])
        elif block_type == "claim_reference":
            block = ClaimReferenceBlock(
                claim_id=data["claim_id"],
                claim_summary=data["claim_summary"],
                display_label=data["display_label"],
            )
        else:
            return None
        return block_to_sse(block)
    except Exception as exc:
        print(f" [WARN] Failed to serialize custom stream event {data!r}: {exc!r}", flush=True)
        return None


@pythonAPI.post("/api/chat/ask/stream")
async def paper_chat_ask(request: ChatAskRequest, contextrequest: Request):
    """Paper-scoped chat: streams typed blocks (text / claim_reference) over SSE.

    Named /api/chat/ask/stream rather than /api/chat/ask (the legacy path) so
    it can coexist with the legacy general-chat endpoint above - legacy
    deletion is Slice 3c, out of scope here.
    """
    async def event_stream():
        try:
            graph = contextrequest.app.state.paper_chat_graph
            config = {"configurable": {"thread_id": request.chat_id}}
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "active_file_id": request.active_file_id,
            }
            async for event in graph.astream(
                initial_state, config, stream_mode=["custom", "messages"]
            ):
                if await contextrequest.is_disconnected():
                    print(f" [CANCEL] paper chat stream: client disconnected, chat_id={request.chat_id}", flush=True)
                    return
                frame = serialize_event_to_sse(event)
                if frame:
                    yield frame
            yield 'data: {"type": "done"}\n\n'
        except asyncio.CancelledError:
            print(f" [CANCEL] paper chat stream cancelled, chat_id={request.chat_id}", flush=True)
            raise
        except Exception as exc:
            print(f" [FAIL] paper chat stream error: {exc!r}", flush=True)
            yield f'data: {{"type": "error", "message": {json.dumps(str(exc))}}}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
                
                # --- [FIX] Safely extract the string from the history object ---
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
async def wipe_ai_system(http_request: Request, x_admin_token: str | None = Header(default=None)):
    if not settings.system_admin_token:
        raise HTTPException(status_code=403, detail="System reset disabled: no admin token configured")
    if x_admin_token != settings.system_admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # 1. WIPE QDRANT (Vector Database)
        try:
            ragservice = await agent_service._get_ragservice()
            await ragservice.client.delete_collection(collection_name="prism_collection")
        except Exception as e:
            print(f" [WARN] Qdrant wipe warning: {e}")

        # 2. WIPE LANGGRAPH MEMORY (Using existing connection pool)
        # This guarantees it works with Aspire's injected database
        async with await http_request.app.state.pool.getconn() as conn:
            await conn.execute("TRUNCATE TABLE checkpoints, checkpoint_blobs, checkpoint_writes CASCADE;")
            await conn.commit() # Don't forget to commit the wipe!
                
        print(" [WIPE] NUCLEAR WIPE COMPLETE: Vectors and Memory erased.")
        return {"status": "success", "message": "AI Brain wiped."}
        
    except Exception as e:
        print(f" [FAIL] Nuclear Wipe Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))     
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(pythonAPI, host="0.0.0.0", port=settings.port)