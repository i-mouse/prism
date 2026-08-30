import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os, json, fitz, traceback, time
import aio_pika
import psycopg
from datetime import datetime, timezone
from minio import Minio
from ai_service import AIService
from RAGService import RAGService
from config import settings
from memory_db import create_db_connection_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent_service import workflow
from langchain_core.messages import AIMessage
from extraction.engine import extract_metadata, extract_claims
from extraction.grounding import ground_extraction
from extraction.writer import write_extraction_result, RESEARCH_PAPER_DOMAIN_ID
from extraction.schemas import PaperMetadataFinal
from extraction.prompt_version import get_prompt_version
from extraction.pipeline_events import ProgressEmitter, Stage
from correlation import set_correlation_id
from telemetry import init_telemetry
from opentelemetry import context as otel_context, propagate, trace
from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

tracer = init_telemetry("prism-python-worker")
PsycopgInstrumentor().instrument()

MAX_ATTEMPTS = 3

def _get_attempt_count(message) -> int:
    """Returns attempt count from message headers, defaulting to 1.

    RabbitMQ 3.10+ auto-populates x-delivery-count (0-indexed) on requeues
    of quorum/classic queues. Falls back to our own x-attempt header which
    we set explicitly when republishing so the counter is portable across
    RabbitMQ versions and queue types.
    """
    headers = message.headers or {}
    # RabbitMQ 3.10+ auto-populates x-delivery-count on requeues (0-indexed)
    delivery_count = headers.get("x-delivery-count")
    if delivery_count is not None:
        return int(delivery_count) + 1  # 0-indexed -> 1-indexed
    # Fallback: our own portable counter
    return int(headers.get("x-attempt", 1))

def parse_aspire_minio(conn_str):
    parts = {k: v for k, v in (item.split('=') for item in conn_str.split(';'))}
    endpoint = parts['Endpoint'].replace("http://", "").replace("https://", "").rstrip('/')
    return endpoint, parts['AccessKey'], parts['SecretKey']

def extract_pdf_text_sync(local_path: str) -> tuple[str, int]:
    """Synchronous PDF extraction wrapper so it doesn't block the async loop.

    Returns (text, page_count) - the page count feeds the "preparing" stage
    detail message shown in the activity view.
    """
    final_text = ''
    with fitz.open(local_path) as doc:
        page_count = doc.page_count
        for page in doc:
            final_text += page.get_text()
    return final_text, page_count

async def main():
    service = AIService()
    rag_service = await RAGService.create()

    connection_string = settings.messaging_connection_string
    connection_string_minio = settings.storage_connection_string

    # -------------------------------------------------------------------------
    # THE ASYNC GRAIL: We create the Pool and Compile the Graph exactly ONCE
    # -------------------------------------------------------------------------
    print("[...] Initializing Database and AI Agent...", flush=True)
    pool = create_db_connection_pool()
    await pool.open()

    async with await pool.getconn() as conn:
        await conn.set_autocommit(True) # This prevents the transaction block error!
        setup_checkpointer = AsyncPostgresSaver(conn)
        await setup_checkpointer.setup()

    checkpointer = AsyncPostgresSaver(pool)
    
    agent_app = workflow.compile(
        checkpointer=checkpointer,
        name="Prism Agent"
    )
    print("[OK] Database Pool & Agent Workflow Compiled and Ready!", flush=True)

    # --- MinIO Setup ---
    endpoint, user, password = parse_aspire_minio(connection_string_minio)
    minio_client = Minio(endpoint=endpoint, access_key=user, secret_key=password, secure=False)
    print("[OK] Connected to MinIO", flush=True)

    # --- aio-pika RabbitMQ Setup ---
    AioPikaInstrumentor().instrument()
    print("[...] Connecting to RabbitMQ...", flush=True)
    connection = await aio_pika.connect_robust(connection_string)
    
    async with connection:
        channel = await connection.channel()

        await channel.set_qos(prefetch_count=1)
        
        # Setup Exchange & Queue
        exchange = await channel.declare_exchange(
            'Prism.ApiService.Contracts:PrismUploaded', 
            aio_pika.ExchangeType.FANOUT, 
            durable=True
        )
        queue = await channel.declare_queue('main_prism_queue', durable=True,arguments={
                "x-dead-letter-exchange": "dlx_prism_exchange",
                "x-dead-letter-routing-key": "prism_failed"
            })
        await queue.bind(exchange)
        
        print(f" [*] Waiting for messages in {queue.name}. To exit press CTRL+C")

        # The Async Iterator (Listens for messages continuously)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                # message.process() automatically ACKs if the block succeeds, and NACKs if it crashes!
                async with message.process(ignore_processed=True): # We set ignore_processed=True so we can manually ACK or REJECT
                    emitter: ProgressEmitter | None = None
                    current_stage: Stage = "preparing"

                    # Continue the distributed trace started by MassTransit's publish (C# side
                    # writes standard W3C traceparent/tracestate into the AMQP headers when its
                    # own "MassTransit" ActivitySource is registered - see Prism.ServiceDefaults).
                    incoming_headers = message.headers or {}
                    trace_carrier = {
                        key: (value.decode() if isinstance(value, bytes) else value)
                        for key, value in incoming_headers.items()
                        if key in ("traceparent", "tracestate")
                    }
                    parent_otel_context = propagate.extract(trace_carrier)
                    otel_context_token = otel_context.attach(parent_otel_context)

                    header_correlation_id = incoming_headers.get("x-correlation-id")
                    if isinstance(header_correlation_id, bytes):
                        header_correlation_id = header_correlation_id.decode()

                    try:
                        with tracer.start_as_current_span("process_document") as process_span:
                            try:
                                data = json.loads(message.body.decode())
                                actual_message = data['message']

                                file_name    = actual_message['fileName']
                                file_id      = actual_message['fileId']
                                chat_id      = actual_message['chatId']
                                connection_id = actual_message['connectionId']

                                # Preserve the header-provided correlation ID when C# sent one;
                                # otherwise fall back to the existing derived value.
                                correlation_id = header_correlation_id or f"ingest-{file_id}"
                                set_correlation_id(correlation_id)
                                process_span.set_attribute("correlation_id", correlation_id)
                                process_span.set_attribute("paper_id", file_id)
                                process_span.set_attribute("chat_id", chat_id)

                                attempt = _get_attempt_count(message)
                                print(f'\n[x] Received {file_name} attempt={attempt}/{MAX_ATTEMPTS} correlation_id={correlation_id}')

                                emitter = ProgressEmitter(channel, file_id=file_id, chat_id=chat_id)
                                await emitter.emit_stage("preparing")

                                # 1. Download file asynchronously using threads
                                local_path = os.path.join("downloads", file_name)
                                os.makedirs("downloads", exist_ok=True)
                                await asyncio.to_thread(minio_client.fget_object, 'prism-uploads', file_name, local_path)

                                # 2. Extract text asynchronously
                                _, extension = os.path.splitext(local_path)
                                final_text = ''
                                page_count: int | None = None
                                is_pdf = extension.lower() == ".pdf"
                                if is_pdf:
                                    final_text, page_count = await asyncio.to_thread(extract_pdf_text_sync, local_path)
                                else:
                                    final_text = await service.transcribe_audio(file_path=local_path)

                                # 3. LLM Processing
                                text_summary = await service.analyize_text(text=final_text)

                                # 4. Save to Qdrant (natively async - AsyncQdrantClient, no thread needed)
                                chunk_count = await rag_service.add_document_to_qdrant(file_name, final_text, file_id)

                                if is_pdf:
                                    await emitter.emit_stage_detail(
                                        "preparing", f"Parsed {page_count} pages, {chunk_count} chunks"
                                    )
                                else:
                                    await emitter.emit_stage_detail(
                                        "preparing", f"Transcribed audio, {chunk_count} chunks"
                                    )

                                # ============================================
                                # NEW: Extraction pipeline (metadata + claims + grounding + DB write)
                                # ============================================
                                print(f'[extraction] chat_id={chat_id} correlation_id={correlation_id} starting metadata extraction')
                                with tracer.start_as_current_span("extract_metadata") as span:
                                    span.set_attribute("correlation_id", correlation_id)
                                    span.set_attribute("paper_id", file_id)
                                    metadata_response = await extract_metadata(
                                        paper_text=final_text,
                                        chat_id=chat_id,
                                        correlation_id=correlation_id,
                                    )

                                metadata_final = PaperMetadataFinal(
                                    **metadata_response.metadata.model_dump(),
                                    prompt_version=get_prompt_version(),
                                    model_used=settings.llm_extraction_model,
                                    extracted_at=datetime.now(timezone.utc),
                                )

                                await emitter.emit_stage_detail("preparing", "Extracted paper metadata")

                                current_stage = "extracting"
                                await emitter.emit_stage("extracting")
                                print(f'[extraction] chat_id={chat_id} correlation_id={correlation_id} starting claims extraction')
                                with tracer.start_as_current_span("extract_claims") as span:
                                    span.set_attribute("correlation_id", correlation_id)
                                    span.set_attribute("paper_id", file_id)
                                    extraction = await extract_claims(
                                        paper_text=final_text,
                                        chat_id=chat_id,
                                        correlation_id=correlation_id,
                                        on_detail=lambda d: emitter.emit_stage_detail("extracting", d),
                                    )

                                current_stage = "grounding"
                                await emitter.emit_stage("grounding")
                                await emitter.emit_stage_detail(
                                    "grounding", f"Verifying evidence spans for {len(extraction.claims)} claims"
                                )
                                print(f'[extraction] chat_id={chat_id} correlation_id={correlation_id} starting grounding')
                                with tracer.start_as_current_span("ground_extraction") as span:
                                    span.set_attribute("correlation_id", correlation_id)
                                    span.set_attribute("paper_id", file_id)
                                    grounded = await ground_extraction(
                                        extraction=extraction,
                                        paper_text=final_text,
                                        chat_id=chat_id,
                                        correlation_id=correlation_id,
                                        on_progress=emitter.emit_grounding_progress,
                                    )

                                current_stage = "finalizing"
                                await emitter.emit_stage("finalizing")
                                await emitter.emit_stage_detail("finalizing", "Writing results")
                                print(f'[extraction] chat_id={chat_id} correlation_id={correlation_id} writing to DB')
                                with tracer.start_as_current_span("writer.write") as span:
                                    span.set_attribute("correlation_id", correlation_id)
                                    span.set_attribute("paper_id", file_id)
                                    doc_extractor_id = await write_extraction_result(
                                        file_id=file_id,
                                        metadata=metadata_final,
                                        claims=grounded,
                                        chat_id=chat_id,
                                        correlation_id=correlation_id,
                                    )

                                print(f'[extraction] chat_id={chat_id} correlation_id={correlation_id} document_extractor_id={doc_extractor_id} claims={len(grounded)}')

                                supported = sum(1 for c in grounded if c.label.value == "supported" and not c.missing)
                                partial = sum(1 for c in grounded if c.label.value == "partially_supported" and not c.missing)
                                refused = sum(1 for c in grounded if c.missing)
                                await emitter.emit_stage_detail(
                                    "finalizing",
                                    f"{len(grounded)} audited · {supported} supported · "
                                    f"{refused} refused · {partial} partial",
                                )

                                await emitter.emit_stage("done")

                                # 5. Inject memory using our globally compiled agent!
                                config = {"configurable": {"thread_id": chat_id}}
                                msg = AIMessage(
                                    content=f"**Processing completed**\n\n**Summary:**\n\n{text_summary}\n\nYou can now ask questions about this document."
                                )

                                await agent_app.aupdate_state(
                                    config=config,
                                    values={"messages": [msg]},
                                    as_node="agent"
                                )

                                # 6. Publish completion message
                                completion_message = {
                                    "fileId": file_id,
                                    "fileName": file_name,
                                    "connectionId": connection_id,
                                    "chatId": chat_id,
                                    "status": "Completed",
                                    "summary": text_summary
                                }

                                await channel.default_exchange.publish(
                                    aio_pika.Message(body=json.dumps(completion_message).encode()),
                                    routing_key='document_processed_queue',
                                )
                                await message.ack()
                                print(f'[OK] Completed: {file_name} correlation_id={correlation_id}')

                            # ==========================================
                            # 1. TERMINAL ERROR (Corrupted PDF)
                            # ==========================================
                            except fitz.FileDataError as e:
                                process_span.record_exception(e)
                                process_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                                print(f'[CORRUPT] Corrupted file detected: {file_name}')
                                traceback.print_exc()

                                error_message = {
                                    "fileId": file_id,
                                    "fileName": file_name,
                                    "connectionId": connection_id,
                                    "chatId": chat_id,
                                    "status": "Error", # Matches your React UI exactly
                                    "summary": f"Could not process document. The file may be corrupted. Error: {str(e)}"
                                }

                                await channel.default_exchange.publish(
                                    aio_pika.Message(body=json.dumps(error_message).encode()),
                                    routing_key='document_processed_queue',
                                )
                                await message.reject(requeue=False)
                                print(f'[DEAD] Message {file_name} sent to Dead Letter Queue.')

                            # ==========================================
                            # 2. TERMINAL ERROR (Postgres FK violation - bad file_id upstream)
                            # ==========================================
                            except psycopg.errors.ForeignKeyViolation as e:
                                process_span.record_exception(e)
                                process_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                                print(f'[DEAD] FK violation for {file_name} - file_id may be invalid: {e}')
                                traceback.print_exc()

                                error_message = {
                                    "fileId": file_id,
                                    "fileName": file_name,
                                    "connectionId": connection_id,
                                    "chatId": chat_id,
                                    "status": "Error",
                                    "summary": f"Database FK violation. Extraction cannot proceed: {str(e)}"
                                }

                                await channel.default_exchange.publish(
                                    aio_pika.Message(body=json.dumps(error_message).encode()),
                                    routing_key='document_processed_queue',
                                )
                                await message.reject(requeue=False)  # -> DLQ
                                print(f'[DEAD] Message {file_name} sent to Dead Letter Queue (FK violation).')

                            # ==========================================
                            # 3. TRANSIENT ERROR (LLM Timeout, Network Blip, Extraction JSON)
                            #    Retry up to MAX_ATTEMPTS, then DLQ.
                            # ==========================================
                            except Exception as e:
                                process_span.record_exception(e)
                                process_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                                traceback.print_exc()

                                if emitter is not None:
                                    try:
                                        await emitter.emit_failed(current_stage)
                                    except Exception:
                                        pass  # don't let failure emission mask the original error

                                if attempt >= MAX_ATTEMPTS:
                                    print(f'[DEAD] {file_name} exceeded {MAX_ATTEMPTS} attempts, sending to DLQ')
                                    error_message = {
                                        "fileId": file_id,
                                        "fileName": file_name,
                                        "connectionId": connection_id,
                                        "chatId": chat_id,
                                        "status": "Error",
                                        "summary": f"Processing failed after {MAX_ATTEMPTS} attempts: {str(e)}"
                                    }
                                    await channel.default_exchange.publish(
                                        aio_pika.Message(body=json.dumps(error_message).encode()),
                                        routing_key='document_processed_queue',
                                    )
                                    await message.reject(requeue=False)  # -> DLQ
                                else:
                                    print(f'[WARN] {file_name} attempt {attempt} failed, retrying in 5s: {e}')
                                    await asyncio.sleep(5)
                                    # Republish with incremented x-attempt counter.
                                    # message.reject(requeue=True) cannot mutate headers, so we
                                    # republish-and-ack - the standard pattern for bounded retries
                                    # in aio-pika / RabbitMQ.
                                    new_headers = dict(message.headers or {})
                                    new_headers["x-attempt"] = attempt + 1
                                    await channel.default_exchange.publish(
                                        aio_pika.Message(
                                            body=message.body,
                                            headers=new_headers,
                                            content_type=message.content_type,
                                        ),
                                        routing_key='main_prism_queue',
                                    )
                                    await message.ack()  # ack current delivery; new message is already queued
                    finally:
                        otel_context.detach(otel_context_token)

if __name__ == '__main__':
    try:
        # We start the ONE master universe right here.
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n[*] Shutting down gracefully')
        sys.exit(0)
    except Exception:
        print(traceback.format_exc())
        time.sleep(60) 
        raise