import os,pika,json,sys,fitz
from minio import Minio


def main():

    # Establising the connection and channel
    credential = pika.PlainCredentials(username='guest',password='1AVWTEyHt77pH7dBsj140P')
    connection_parameters = pika.ConnectionParameters(host='localhost',port=50343,credentials=credential)
    connection = pika.BlockingConnection(parameters=connection_parameters)
    channel = connection.channel()

    minio_client = Minio(
        endpoint= "localhost:50336",
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

        with fitz.open(local_path) as doc:
            first_page = doc[0]
            text =first_page.get_text()
            print(f"\n Text : {text}")

    channel.basic_consume(queue=queue_name,on_message_callback=callback,auto_ack=True)
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




