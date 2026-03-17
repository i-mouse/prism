import sys
import asyncio
# --- BUG 1 FIX: Tell Windows to use the correct Async Event Loop for Psycopg ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# -----------------------------------------------------------------------------

import os,pika,json,sys,fitz
from minio import Minio
from ai_service import AIService
from RAGService import RAGService
import traceback # Add this import
import time      # Add this import
from memory_db import create_db_connection_pool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent_service import workflow
from langchain_core.messages import AIMessage




def parse_aspire_minio(conn_str):
    parts = {k: v for k, v in (item.split('=') for item in conn_str.split(';'))}
    endpoint = parts['Endpoint'].replace("http://", "").replace("https://", "").rstrip('/')
    return endpoint, parts['AccessKey'], parts['SecretKey']

async def save_summary_memory(chatId: str, summary_text: str):
    """Explicitly saving summary as memory in postgres"""
    try:
        import psycopg
        conninfo = (
            f"host={os.environ['TENDER_DB_HOST']} "
            f"port={os.environ.get('TENDER_DB_PORT', '5432')} "
            f"dbname={os.environ['TENDER_DB_DATABASENAME']} "
            f"user={os.environ['TENDER_DB_USERNAME']} "
            f"password={os.environ['TENDER_DB_PASSWORD']}"
        )

        # Setup with autocommit connection (required for CREATE INDEX CONCURRENTLY)
        async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as setup_conn:
            checkpointer = AsyncPostgresSaver(setup_conn)
            await checkpointer.setup()

        # Now use pool for actual state update
        pool = create_db_connection_pool()
        await pool.open()

        try:
            checkpointer = AsyncPostgresSaver(pool)
            agent_app = workflow.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": chatId}}  # ← lowercase "configurable"!

            msg = AIMessage(
                content=f"**Processing completed** \n\n **Summary:** \n\n{summary_text} \n\n You can now ask questions about this document."
            )
            await agent_app.aupdate_state(config=config, values={"messages": [msg]})
        finally:
            await pool.close()

    except Exception as e:
        print(f"Failed to save memory: {e}")

async def save_summary_memory2(chatId : str ,summary_text :str):

    "Explicitly saving summary as memopry in postgeg"
    try:
        pool = create_db_connection_pool()

        await pool.open()

        async with AsyncPostgresSaver(pool) as checkpointer:
            agent_app = workflow.compile(checkpointer= checkpointer)
            config = {"Configurable" : {"thread_id" : chatId}}

            msg =  AIMessage( content=f"**Processing completed** \n\n **Summary:** \n\n{summary_text} \n\n You can now ask question about this document.")

            await agent_app.update_state({"messages" : [msg]},config=config)

    except Exception as e:
        print(f"Failed to save memory: {e}")
    finally:
        await pool.close()



def main():

    service = AIService()
    rag_service = RAGService()

    connection_string = os.getenv("ConnectionStrings__messaging")
    connection_string_miniio = os.getenv("ConnectionStrings__storage")

    if not connection_string_miniio:
        print("Error: MinIO connection string not found!")
        sys.exit(1) # This will show as a failure in Aspire

    if not connection_string:
        print("Error: RabbitMQ connection string not found!")
        sys.exit(1) # This will show as a failure in Aspire

    params = pika.URLParameters(connection_string)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    endpoint, user, password = parse_aspire_minio(connection_string_miniio)
        
    minio_client = Minio(
            endpoint=endpoint, # e.g., "localhost:9000"
            access_key=user,
            secret_key=password,
            secure=False
        )
    print("Connected to MinIO with custom credentials!")


    #Setting up exchnage
    exchange_name = 'TenderAI.ApiService.Contracts:TenderUploaded'
    channel.exchange_declare(exchange=exchange_name,exchange_type='fanout', durable=True)    

    # setting up queue
    queue = channel.queue_declare(queue='',exclusive=True)
    queue_name=queue.method.queue

    #Exchange and queue binding
    channel.queue_bind(queue=queue_name,exchange=exchange_name)
    print(f" [*] Waiting for messages in {queue_name}. To exit press CTRL+C")

    #Callback method to receive messages continously
    def callback(ch,method,properties,body):
        try:
            json_string = body.decode()
            data = json.loads(json_string)
            actual_message = data['message']

            file_name = actual_message['fileName']
            file_id = actual_message['fileId']
            chat_id = actual_message['chatId']
            connectionId = actual_message['connectionId']
            print(f'[x] File Name : {file_name} \n[x] File Id : {file_id}')

            download_folder ="downloads"
            os.makedirs(download_folder,exist_ok=True)
            local_path = os.path.join(download_folder,file_name)

            minio_client.fget_object(bucket_name='tender-uploads',object_name=file_name,file_path=local_path)
            print(f'\nFile downloaded successfully {file_name}')

            base_name,extension = os.path.splitext(local_path)
            final_text = ''
            if extension.lower() == ".pdf":            
                with fitz.open(local_path) as doc:
                    for page in doc:
                        first_page = page
                        text =first_page.get_text()
                        final_text += text

            else:
                final_text = asyncio.run( service.transcribe_audio(file_path=local_path))

            text_summary = asyncio.run(service.analyize_text(text=final_text))
            rag_service.add_document_to_qdrant(filename=file_name,doctext=final_text)      
            print(final_text) 
            asyncio.run(save_summary_memory(chat_id, text_summary))
            completion_message  = {
                "fileId" : file_id,
                "fileName" : file_name,
                "connectionId" : connectionId,
                "status" : "Completed",
                "summary" : text_summary
                }    

            # Publish it back to RabbitMQ on a NEW queue
            channel.basic_publish(exchange='',routing_key='document_processed_queue',body=json.dumps(completion_message))      
            ch.basic_ack(delivery_tag=method.delivery_tag)    

            

        except Exception as e:
            print(f'Error: {e}')
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
 

    channel.basic_consume(queue=queue_name,on_message_callback=callback)
    channel.start_consuming()

if __name__== '__main__':
    try:
        main()
    except Exception :
        error_msg = traceback.format_exc()
        print(error_msg)
        time.sleep(60) # Keep container alive so you can see the file
    except KeyboardInterrupt :
        try:
            print(f'\nKeyboard Intereption')
            sys.exit(0) # 0 means exit gracefully, 1 means exit with error | start shutdown and run cleanup like final block and close

        except SystemExit :
            print(f'\nSystem Exit')
            os._exit(1) # sometimes on multithread environment sys.exit(0) is not enough,os._exit(1) shutdown immediately, do not save or clean up




