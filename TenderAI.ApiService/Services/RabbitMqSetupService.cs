//using Microsoft.EntityFrameworkCore.Metadata;
using RabbitMQ.Client;
using System.Collections.Generic;
namespace TenderAI.ApiService.Services;

public class RabbitMqSetupService
{
    public async Task SetupQueuesAsync( IChannel channel)
    {
        string dlxName = "dlx_tender_exchange";
        string dlqName = "dlq_tender_queue";
        var dlqRoutingKey =  "tender_failed";

        string massTransitExchange = "TenderAI.ApiService.Contracts:TenderUploaded";
        string mainQueueName = "main_tender_queue";

        await channel.ExchangeDeclareAsync(exchange : dlxName , type : ExchangeType.Direct, durable : true);

        // The TTL goes HERE, on the graveyard queue!
        var dlqArgs = new Dictionary<string, object>
        {
            { "x-message-ttl", 60000 } 
        };

        await channel.QueueDeclareAsync(queue : dlqName, durable : true , exclusive : false , autoDelete : false, arguments : dlqArgs!);
        await channel.QueueBindAsync(queue : dlqName, exchange : dlxName, routingKey : dlqRoutingKey);

        await channel.ExchangeDeclareAsync(exchange: massTransitExchange, type: ExchangeType.Fanout, durable: true);

         var mainQueueArgs = new Dictionary<string,object>
        {
          {"x-dead-letter-exchange", dlxName},
          {"x-dead-letter-routing-key" ,  dlqRoutingKey}
        };

        await channel.QueueDeclareAsync(queue : mainQueueName,durable : true ,exclusive : false, autoDelete : false,arguments : mainQueueArgs!);

        await channel.QueueBindAsync(queue: mainQueueName, exchange: massTransitExchange, routingKey: "");

      
    }
}