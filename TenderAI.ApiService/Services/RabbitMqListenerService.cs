using Microsoft.AspNetCore.SignalR;
using Microsoft.EntityFrameworkCore.Metadata;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using TenderAI.ApiService.Hubs;
using  System.Text.Json;
using TenderAI.ApiService.Data;
using Microsoft.EntityFrameworkCore;

namespace TenderAI.ApiService.Services;

public class RabbitMqListenerService : BackgroundService
{
    private readonly IConnectionFactory _connectionFactory;
    private readonly IHubContext<DocumentHub,IDocumentClient> _hubContext;
      private readonly IServiceScopeFactory _serviceScopeFactory;
    public RabbitMqListenerService(IConnectionFactory connectionFactory, IHubContext<DocumentHub, IDocumentClient> hubContext , IServiceScopeFactory serviceScopeFactory)
    {
        _connectionFactory = connectionFactory;
        _hubContext = hubContext;   
        _serviceScopeFactory = serviceScopeFactory;
    }
    protected override async Task ExecuteAsync(CancellationToken _stoppingToken)
    {
      var connection =  await _connectionFactory.CreateConnectionAsync(_stoppingToken);
      var channel =  await connection.CreateChannelAsync(cancellationToken: _stoppingToken);
      
      await channel.QueueDeclareAsync(
            queue: "document_processed_queue",
            durable:true,
            exclusive:false,
            autoDelete:false,
            cancellationToken:_stoppingToken
       );

    var consumer = new AsyncEventingBasicConsumer(channel);

    consumer.ReceivedAsync += async (model ,ea) =>
    {
        var body = ea.Body.ToArray();
        var message = System.Text.Encoding.UTF8.GetString(body);
        Console.WriteLine($"Listener recieved from python : {message}");

        var dataObject = JsonSerializer.Deserialize<JsonElement>(message);
        var fileId = dataObject.GetProperty("fileId").ToString();
        var status = dataObject.GetProperty("status").ToString();
        var connectionId = dataObject.GetProperty("connectionId").ToString();
        var summary = dataObject.GetProperty("summary").ToString();
      
       using (var scope = _serviceScopeFactory.CreateScope())
       {
        var dbContext = scope.ServiceProvider.GetRequiredService<TenderDBContext>();

        var obj = await dbContext.fileRecords.FindAsync(fileId);
        if(obj!=null)
            {
                obj.Summary = summary;
                obj.UploadedAt = DateTime.UtcNow;
                await dbContext.SaveChangesAsync();
            }
       }
      
        await _hubContext.Clients.Client(connectionId).DocumentProcessed(dataObject);

        await channel.BasicAckAsync(ea.DeliveryTag,false,_stoppingToken);

    };

    await channel.BasicConsumeAsync(
        queue:"document_processed_queue",
        autoAck:false,
        consumer:consumer,
        cancellationToken:_stoppingToken
    );

        // keep the aaplication  running forver and close it  when user stop the appl;ication like stop the debugging
      await Task.Delay(-1,_stoppingToken);
    }
}