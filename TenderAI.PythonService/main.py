import os,pika,json,sys

def main():

    # Establising the connection and channel
    credential = pika.PlainCredentials(username='guest',password='1AVWTEyHt77pH7dBsj140P')
    connection_parameters = pika.ConnectionParameters(host='localhost',port=58943,credentials=credential)
    connection = pika.BlockingConnection(parameters=connection_parameters)
    channel = connection.channel()

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
        print(f'[x] Received : {body}')

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




