import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os, json, fitz, traceback, time
import aio_pika
from minio import Minio
from ai_service import AIService
from RAGService import RAGService
from memory_db import create_db_connection_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent_service import workflow
from langchain_core.messages import AIMessage

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
        name="TenderAI Agent"
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
            'TenderAI.ApiService.Contracts:TenderUploaded', 
            aio_pika.ExchangeType.FANOUT, 
            durable=True
        )
        queue = await channel.declare_queue('main_tender_queue', durable=True,arguments={
                "x-dead-letter-exchange": "dlx_tender_exchange",
                "x-dead-letter-routing-key": "tender_failed"
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
                        print(f'\n[x] Received: {file_name}')

                        # 1. Download file asynchronously using threads
                        local_path = os.path.join("downloads", file_name)
                        os.makedirs("downloads", exist_ok=True)
                        await asyncio.to_thread(minio_client.fget_object, 'tender-uploads', file_name, local_path)

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
                        await asyncio.to_thread(rag_service.add_document_to_qdrant, file_name, final_text)

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
                    # 2. TRANSIENT ERROR (LLM Timeout, Network Blip)
                    # ==========================================
                    except Exception as e:
                        print(f'[⚠️] Network/AI issue for {file_name}. Retrying in 5 seconds... Error: {e}')
                        traceback.print_exc()
                        
                        await asyncio.sleep(5)
                        
                        # Put it BACK in the main queue! 
                        # Do NOT send an error to the UI. Let it keep spinning.
                        await message.reject(requeue=True)

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