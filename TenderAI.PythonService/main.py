import os,pika,json,sys,fitz
from minio import Minio
from ai_service import AIService
from RAGService import RAGService
import asyncio

def main():

    service = AIService()
    rag_service = RAGService()
    # Establising the connection and channel
    credential = pika.PlainCredentials(username='guest',password='1AVWTEyHt77pH7dBsj140P')
    connection_parameters = pika.ConnectionParameters(host='localhost',port=59040,credentials=credential)
    connection = pika.BlockingConnection(parameters=connection_parameters)
    channel = connection.channel()

    minio_client = Minio(
        endpoint= "localhost:59038",
        access_key= "minioadmin",
        secret_key="F7gmz*p~v)5uEN{Kc~7UqP",
        secure=False
    )


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
            print(f'[x] File Name : {file_name} \n[x] File Id : {file_id}')

            download_folder ="downloads"
            os.makedirs(download_folder,exist_ok=True)
            local_path = os.path.join(download_folder,file_name)

            minio_client.fget_object(bucket_name='tender-uploads',object_name=file_name,file_path=local_path)
            print(f'\nFile downloaded successfully {file_name}')

            base_name,extension = os.path.splitext(local_path)
            
            if extension.lower() == ".pdf":           
                final_text = ''
                with fitz.open(local_path) as doc:
                    first_page = doc[0]
                    text =first_page.get_text()
                    final_text += text

                summary = asyncio.run(service.analyize_text(text=final_text))
                rag_service.add_document_to_qdrant(filename=file_name,doctext=summary)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            else:
                audio_text = asyncio.run( service.transcribe_audio(file_path=local_path))
                print(audio_text)   

            
            text_file_path = f"{base_name}_summary.txt"
            
            with open(text_file_path,mode="w",encoding="utf-8") as f:
                f.write(summary)

            

        except Exception as e:
            print(f'Error: {e}')
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
 

    channel.basic_consume(queue=queue_name,on_message_callback=callback)
    channel.start_consuming()

if __name__== '__main__':
    try:
        main()
    except KeyboardInterrupt :
        try:
            print(f'\nKeyboard Intereption')
            sys.exit(0) # 0 means exit gracefully, 1 means exit with error | start shutdown and run cleanup like final block and close

        except SystemExit :
            print(f'\nSystem Exit')
            os._exit(1) # sometimes on multithread environment sys.exit(0) is not enough,os._exit(1) shutdown immediately, do not save or clean up




