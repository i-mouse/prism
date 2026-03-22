# import sys
# import asyncio
# # --- BUG 1 FIX: Tell Windows to use the correct Async Event Loop for Psycopg ---
# if sys.platform == "win32":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# # -----------------------------------------------------------------------------

# import os,pika,json,sys,fitz
# from minio import Minio
# from ai_service import AIService
# from RAGService import RAGService
# import traceback # Add this import
# import time      # Add this import
# from memory_db import create_db_connection_pool
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# from agent_service import workflow
# from langchain_core.messages import AIMessage




# def parse_aspire_minio(conn_str):
#     parts = {k: v for k, v in (item.split('=') for item in conn_str.split(';'))}
#     endpoint = parts['Endpoint'].replace("http://", "").replace("https://", "").rstrip('/')
#     return endpoint, parts['AccessKey'], parts['SecretKey']

# async def save_summary_memory(chatid: str, summary_text: str):
#     """Explicitly saving summary as memory in postgres"""
#     try:
#         import psycopg
#         conninfo = (
#             f"host={os.environ['TENDER_DB_HOST']} "
#             f"port={os.environ.get('TENDER_DB_PORT', '5432')} "
#             f"dbname={os.environ['TENDER_DB_DATABASENAME']} "
#             f"user={os.environ['TENDER_DB_USERNAME']} "
#             f"password={os.environ['TENDER_DB_PASSWORD']}"
#         )

#         # Setup with autocommit connection (required for CREATE INDEX CONCURRENTLY)
#         async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as setup_conn:
#             checkpointer = AsyncPostgresSaver(setup_conn)
#             await checkpointer.setup()

#         # Now use pool for actual state update
#         pool = create_db_connection_pool()
#         await pool.open()

#         try:
#             checkpointer = AsyncPostgresSaver(pool)
#             agent_app = workflow.compile(checkpointer=checkpointer)
#             config = {"configurable": {"thread_id": chatid}}  # ← lowercase "configurable"!

#             msg = AIMessage(
#                 content=f"**Processing completed** \n\n **Summary:** \n\n{summary_text} \n\n You can now ask questions about this document."
#             )

#             await agent_app.aupdate_state(
#                 config=config, 
#                 values={"messages": [msg]}, 
#                 as_node="agent"  # <--- THE FIX: Tell LangGraph who is updating the state
#             )
#         finally:
#             await pool.close()

#     except Exception as e:
#         print(f"Failed to save memory: {e}")
#         raise

# def main():

#     service = AIService()
#     rag_service = RAGService()

#     connection_string = os.getenv("ConnectionStrings__messaging")
#     connection_string_miniio = os.getenv("ConnectionStrings__storage")

#     if not connection_string_miniio:
#         print("Error: MinIO connection string not found!")
#         sys.exit(1) # This will show as a failure in Aspire

#     if not connection_string:
#         print("Error: RabbitMQ connection string not found!")
#         sys.exit(1) # This will show as a failure in Aspire

#     params = pika.URLParameters(connection_string)
#     connection = pika.BlockingConnection(params)
#     channel = connection.channel()

#     endpoint, user, password = parse_aspire_minio(connection_string_miniio)
        
#     minio_client = Minio(
#             endpoint=endpoint, # e.g., "localhost:9000"
#             access_key=user,
#             secret_key=password,
#             secure=False
#         )
#     print("Connected to MinIO with custom credentials!")


#     #Setting up exchnage
#     exchange_name = 'TenderAI.ApiService.Contracts:TenderUploaded'
#     channel.exchange_declare(exchange=exchange_name,exchange_type='fanout', durable=True)    

#     # setting up queue
#     queue = channel.queue_declare(queue='',exclusive=True)
#     queue_name=queue.method.queue

#     #Exchange and queue binding
#     channel.queue_bind(queue=queue_name,exchange=exchange_name)
#     print(f" [*] Waiting for messages in {queue_name}. To exit press CTRL+C")

#     #Callback method to receive messages continously
#     def callback(ch,method,properties,body):
#         try:
#             json_string = body.decode()
#             data = json.loads(json_string)
#             actual_message = data['message']

#             file_name = actual_message['fileName']
#             file_id = actual_message['fileId']
#             chat_id = actual_message['chatId']
#             connection_id = actual_message['connectionId']
#             print(f'[x] File Name : {file_name} \n[x] File Id : {file_id}')

#             download_folder ="downloads"
#             os.makedirs(download_folder,exist_ok=True)
#             local_path = os.path.join(download_folder,file_name)

#             minio_client.fget_object(bucket_name='tender-uploads',object_name=file_name,file_path=local_path)
#             print(f'\nFile downloaded successfully {file_name}')

#             base_name,extension = os.path.splitext(local_path)
#             final_text = ''
#             if extension.lower() == ".pdf":            
#                 with fitz.open(local_path) as doc:
#                     for page in doc:
#                         first_page = page
#                         text =first_page.get_text()
#                         final_text += text

#             else:
#                 final_text = asyncio.run( service.transcribe_audio(file_path=local_path))

#             text_summary = asyncio.run(service.analyize_text(text=final_text))
#             rag_service.add_document_to_qdrant(filename=file_name,doctext=final_text)      
#             print(final_text) 
#             asyncio.run(save_summary_memory(chat_id, text_summary))
#             completion_message  = {
#                 "fileId" : file_id,
#                 "fileName" : file_name,
#                 "connectionId" : connection_id,
#                 "status" : "Completed",
#                 "summary" : text_summary
#                 }    

#             # Publish it back to RabbitMQ on a NEW queue
#             channel.basic_publish(exchange='',routing_key='document_processed_queue',body=json.dumps(completion_message))      
#             ch.basic_ack(delivery_tag=method.delivery_tag)    

            

#         except Exception as e:
#             print(f'Error: {e}')
#             ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
 

#     channel.basic_consume(queue=queue_name,on_message_callback=callback)
#     channel.start_consuming()

# if __name__== '__main__':
#     try:
#         main()
#     except Exception :
#         error_msg = traceback.format_exc()
#         print(error_msg)
#         time.sleep(60) # Keep container alive so you can see the file
#         raise
#     except KeyboardInterrupt :
#         try:
#             print(f'\nKeyboard Intereption')
#             sys.exit(0) # 0 means exit gracefully, 1 means exit with error | start shutdown and run cleanup like final block and close
#             raise

#         except SystemExit :
#             print(f'\nSystem Exit')
#             os._exit(1) # sometimes on multithread environment sys.exit(0) is not enough,os._exit(1) shutdown immediately, do not save or clean up
#             raise

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# import sys
# import asyncio

# if sys.platform == "win32":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# import os, pika, json, fitz
# from minio import Minio
# from ai_service import AIService
# from RAGService import RAGService
# import traceback
# import time
# import psycopg
# from memory_db import create_db_connection_pool
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# from agent_service import workflow
# from langchain_core.messages import AIMessage

# def parse_aspire_minio(conn_str):
#     parts = {k: v for k, v in (item.split('=') for item in conn_str.split(';'))}
#     endpoint = parts['Endpoint'].replace("http://", "").replace("https://", "").rstrip('/')
#     return endpoint, parts['AccessKey'], parts['SecretKey']

# async def run_setup_once(conninfo: str):
#     """Run checkpointer table setup exactly once at startup."""
#     async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as conn:
#         checkpointer = AsyncPostgresSaver(conn)
#         await checkpointer.setup()
#     print("✅ Checkpointer tables ready", flush=True)

# # -------------------------------------------------------------------------
# # THE FIX: Bring pool creation and compilation INSIDE the async universe
# # -------------------------------------------------------------------------
# async def process_message(service: AIService, rag_service: RAGService,
#                            file_name: str, final_text: str, chat_id: str) -> str:
    
#     # Step 1 — summarise the document
#     text_summary = await service.analyize_text(text=final_text)

#     # Step 2 — store vectors
#     rag_service.add_document_to_qdrant(filename=file_name, doctext=final_text)

#     # Step 3 — The Async Universe
#     # We MUST open the pool here so it belongs to THIS event loop
#     pool = create_db_connection_pool()
#     await pool.open()

#     try:
#         # Compile the agent using the fresh, safe pool
#         agent_app = workflow.compile(
#             checkpointer=AsyncPostgresSaver(pool),
#             name="TenderAI Agent"
#         )

#         config = {"configurable": {"thread_id": chat_id}}
#         msg = AIMessage(
#             content=(
#                 f"**Processing completed**\n\n"
#                 f"**Summary:**\n\n{text_summary}\n\n"
#                 f"You can now ask questions about this document."
#             )
#         )
        
#         await agent_app.aupdate_state(
#             config=config,
#             values={"messages": [msg]},
#             as_node="agent"
#         )
#     finally:
#         # ALWAYS close the pool before the universe dies
#         await pool.close()

#     return text_summary

# def main():
#     service = AIService()
#     rag_service = RAGService()

#     connection_string = os.getenv("ConnectionStrings__messaging")
#     connection_string_minio = os.getenv("ConnectionStrings__storage")

#     if not connection_string_minio or not connection_string:
#         print("Error: Connection strings not found!")
#         sys.exit(1)

#     # --- ONE-TIME SETUP: checkpointer tables ---
#     conninfo = (
#         f"host={os.environ['TENDER_DB_HOST']} "
#         f"port={os.environ.get('TENDER_DB_PORT', '5432')} "
#         f"dbname={os.environ['TENDER_DB_DATABASENAME']} "
#         f"user={os.environ['TENDER_DB_USERNAME']} "
#         f"password={os.environ['TENDER_DB_PASSWORD']}"
#     )
#     asyncio.run(run_setup_once(conninfo))

#     # --- RabbitMQ setup ---
#     params = pika.URLParameters(connection_string)
#     connection = pika.BlockingConnection(params)
#     channel = connection.channel()

#     endpoint, user, password = parse_aspire_minio(connection_string_minio)
#     minio_client = Minio(
#         endpoint=endpoint,
#         access_key=user,
#         secret_key=password,
#         secure=False
#     )
#     print("✅ Connected to MinIO", flush=True)

#     exchange_name = 'TenderAI.ApiService.Contracts:TenderUploaded'
#     channel.exchange_declare(exchange=exchange_name, exchange_type='fanout', durable=True)

#     queue = channel.queue_declare(queue='', exclusive=True)
#     queue_name = queue.method.queue
#     channel.queue_bind(queue=queue_name, exchange=exchange_name)
#     print(f" [*] Waiting for messages in {queue_name}. To exit press CTRL+C")

#     def callback(ch, method, properties, body):
#         try:
#             data = json.loads(body.decode())
#             actual_message = data['message']

#             file_name    = actual_message['fileName']
#             file_id      = actual_message['fileId']
#             chat_id      = actual_message['chatId']
#             connection_id = actual_message['connectionId']
#             print(f'\n[x] Received: {file_name}')

#             # Download file from MinIO
#             local_path = os.path.join("downloads", file_name)
#             os.makedirs("downloads", exist_ok=True)
#             minio_client.fget_object('tender-uploads', file_name, local_path)

#             # Extract text
#             _, extension = os.path.splitext(local_path)
#             final_text = ''
#             if extension.lower() == ".pdf":
#                 with fitz.open(local_path) as doc:
#                     for page in doc:
#                         final_text += page.get_text()
#             else:
#                 final_text = asyncio.run(service.transcribe_audio(file_path=local_path))

#             # --- ALL ASYNC WORK HAPPENS IN THIS SINGLE CALL ---
#             text_summary = asyncio.run(
#                 process_message(service, rag_service, file_name, final_text, chat_id)
#             )

#             # Publish completion back to C#
#             completion_message = {
#                 "fileId": file_id,
#                 "fileName": file_name,
#                 "connectionId": connection_id,
#                 "status": "Completed",
#                 "summary": text_summary
#             }
#             channel.basic_publish(exchange='', routing_key='document_processed_queue', body=json.dumps(completion_message))
#             ch.basic_ack(delivery_tag=method.delivery_tag)
#             print(f'[✅] Completed: {file_name}')

#         except Exception as e:
#             print(f'[❌] Error: {e}')
#             traceback.print_exc()
#             ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

#     channel.basic_consume(queue=queue_name, on_message_callback=callback)
#     channel.start_consuming()

# if __name__ == '__main__':
#     try:
#         main()
#     except KeyboardInterrupt:
#         print('\n[*] Shutting down gracefully')
#         sys.exit(0)
#     except Exception:
#         print(traceback.format_exc())
#         time.sleep(60) 
#         raise

    # ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

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

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup() # Run table creation safely once
    
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
        
        # Setup Exchange & Queue
        exchange = await channel.declare_exchange(
            'TenderAI.ApiService.Contracts:TenderUploaded', 
            aio_pika.ExchangeType.FANOUT, 
            durable=True
        )
        queue = await channel.declare_queue('', exclusive=True)
        await queue.bind(exchange)
        
        print(f" [*] Waiting for messages in {queue.name}. To exit press CTRL+C")

        # The Async Iterator (Listens for messages continuously)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                # message.process() automatically ACKs if the block succeeds, and NACKs if it crashes!
                async with message.process():
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
                        print(f'[✅] Completed: {file_name}')

                    except Exception as e:
                        print(f'[❌] Error: {e}')
                        traceback.print_exc()
                        # Because of `async with message.process()`, it automatically NACKs here.

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