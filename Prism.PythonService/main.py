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
from memory_db import create_db_connection_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent_service import workflow
from langchain_core.messages import AIMessage
from extraction.engine import extract_metadata, extract_claims
from extraction.grounding import ground_extraction
from extraction.writer import write_extraction_result, RESEARCH_PAPER_DOMAIN_ID
from extraction.schemas import PaperMetadataFinal
from extraction.prompt_version import get_prompt_version

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
        return int(delivery_count) + 1  # 0-indexed → 1-indexed
    # Fallback: our own portable counter
    return int(headers.get("x-attempt", 1))

def parse_aspire_minio(conn_str):
    parts = {k: v for k, v in (item.split('=') for item in conn_str.split(';'))}
    endpoint = parts['Endpoint'].replace("http://", "").replace("https://", "").rstrip('/')
    return endpoint, parts['AccessKey'], parts['SecretKey']

def extract_pdf_text_sync(local_path: str) -> str:
    """Synchronous PDF extraction wrapper so it doesn't block the async loop"""
    final_text = ''
    with fitz.open(local_path) as doc:
        for page in doc:
            final_text += page.get_text()
    return final_text

async def main():
    service = AIService()
    rag_service = RAGService()

    connection_string = os.getenv("ConnectionStrings__messaging")
    connection_string_minio = os.getenv("ConnectionStrings__storage")

    if not connection_string_minio or not connection_string:
        print("Error: Connection strings not found!")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # 🔥 THE ASYNC GRAIL: We create the Pool and Compile the Graph exactly ONCE
    # -------------------------------------------------------------------------
    print("⏳ Initializing Database and AI Agent...", flush=True)
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
    print("✅ Database Pool & Agent Workflow Compiled and Ready!", flush=True)

    # --- MinIO Setup ---
    endpoint, user, password = parse_aspire_minio(connection_string_minio)
    minio_client = Minio(endpoint=endpoint, access_key=user, secret_key=password, secure=False)
    print("✅ Connected to MinIO", flush=True)

    # --- aio-pika RabbitMQ Setup ---
    print("⏳ Connecting to RabbitMQ...", flush=True)
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
                    try:
                        data = json.loads(message.body.decode())
                        actual_message = data['message']

                        file_name    = actual_message['fileName']
                        file_id      = actual_message['fileId']
                        chat_id      = actual_message['chatId']
                        connection_id = actual_message['connectionId']

                        attempt = _get_attempt_count(message)
                        print(f'\n[x] Received {file_name} attempt={attempt}/{MAX_ATTEMPTS}')

                        # 1. Download file asynchronously using threads
                        local_path = os.path.join("downloads", file_name)
                        os.makedirs("downloads", exist_ok=True)
                        await asyncio.to_thread(minio_client.fget_object, 'prism-uploads', file_name, local_path)

                        # 2. Extract text asynchronously
                        _, extension = os.path.splitext(local_path)
                        final_text = ''
                        if extension.lower() == ".pdf":
                            final_text = await asyncio.to_thread(extract_pdf_text_sync, local_path)
                        else:
                            final_text = await service.transcribe_audio(file_path=local_path)

                        # 3. LLM Processing
                        text_summary = await service.analyize_text(text=final_text)

                        # 4. Save to Qdrant (wrap in thread since Qdrant native client is sync)
                        await asyncio.to_thread(rag_service.add_document_to_qdrant, file_name, final_text, file_id)

                        # ============================================
                        # NEW: Extraction pipeline (metadata + claims + grounding + DB write)
                        # ============================================
                        correlation_id = f"ingest-{file_id}"

                        print(f'[extraction] chat_id={chat_id} starting metadata extraction')
                        metadata_response = await extract_metadata(
                            paper_text=final_text,
                            chat_id=chat_id,
                            correlation_id=correlation_id,
                        )

                        metadata_final = PaperMetadataFinal(
                            **metadata_response.metadata.model_dump(),
                            prompt_version=get_prompt_version(),
                            model_used=os.getenv("LLM_EXTRACTION_MODEL", "unknown"),
                            extracted_at=datetime.now(timezone.utc),
                        )

                        print(f'[extraction] chat_id={chat_id} starting claims extraction')
                        extraction = await extract_claims(
                            paper_text=final_text,
                            chat_id=chat_id,
                            correlation_id=correlation_id,
                        )

                        print(f'[extraction] chat_id={chat_id} starting grounding')
                        grounded = await ground_extraction(
                            extraction=extraction,
                            paper_text=final_text,
                            chat_id=chat_id,
                            correlation_id=correlation_id,
                        )

                        print(f'[extraction] chat_id={chat_id} writing to DB')
                        doc_extractor_id = await write_extraction_result(
                            file_id=file_id,
                            metadata=metadata_final,
                            claims=grounded,
                            chat_id=chat_id,
                            correlation_id=correlation_id,
                        )

                        print(f'[extraction] chat_id={chat_id} document_extractor_id={doc_extractor_id} claims={len(grounded)}')

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
                        print(f'[✅] Completed: {file_name}')

                    # ==========================================
                    # 1. TERMINAL ERROR (Corrupted PDF)
                    # ==========================================
                    except fitz.FileDataError as e:
                        print(f'[☠️] Corrupted file detected: {file_name}')
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
                        print(f'[☠️] Message {file_name} sent to Dead Letter Queue.')

                    # ==========================================
                    # 2. TERMINAL ERROR (Postgres FK violation — bad file_id upstream)
                    # ==========================================
                    except psycopg.errors.ForeignKeyViolation as e:
                        print(f'[\u2620\ufe0f] FK violation for {file_name} \u2014 file_id may be invalid: {e}')
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
                        await message.reject(requeue=False)  # → DLQ
                        print(f'[\u2620\ufe0f] Message {file_name} sent to Dead Letter Queue (FK violation).')

                    # ==========================================
                    # 3. TRANSIENT ERROR (LLM Timeout, Network Blip, Extraction JSON)
                    #    Retry up to MAX_ATTEMPTS, then DLQ.
                    # ==========================================
                    except Exception as e:
                        traceback.print_exc()

                        if attempt >= MAX_ATTEMPTS:
                            print(f'[\u2620\ufe0f] {file_name} exceeded {MAX_ATTEMPTS} attempts, sending to DLQ')
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
                            await message.reject(requeue=False)  # → DLQ
                        else:
                            print(f'[\u26a0\ufe0f] {file_name} attempt {attempt} failed, retrying in 5s: {e}')
                            await asyncio.sleep(5)
                            # Republish with incremented x-attempt counter.
                            # message.reject(requeue=True) cannot mutate headers, so we
                            # republish-and-ack — the standard pattern for bounded retries
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