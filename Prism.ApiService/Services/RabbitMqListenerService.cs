using Microsoft.AspNetCore.SignalR;
using Microsoft.EntityFrameworkCore.Metadata;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using Prism.ApiService.Hubs;
using  System.Text.Json;
using Prism.ApiService.Data;
using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Services;

public class RabbitMqListenerService : BackgroundService
{
    private readonly IConnectionFactory _connectionFactory;
    private readonly IHubContext<DocumentHub,IDocumentClient> _hubContext;
    private readonly IServiceScopeFactory _serviceScopeFactory;
    private readonly ILogger<RabbitMqListenerService> _logger;

    public RabbitMqListenerService(IConnectionFactory connectionFactory, IHubContext<DocumentHub, IDocumentClient> hubContext , IServiceScopeFactory serviceScopeFactory, ILogger<RabbitMqListenerService> logger)
    {
        _connectionFactory = connectionFactory;
        _hubContext = hubContext;   
        _serviceScopeFactory = serviceScopeFactory;
        _logger = logger;
    }
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
      var connection =  await _connectionFactory.CreateConnectionAsync(stoppingToken);
      var channel =  await connection.CreateChannelAsync(cancellationToken: stoppingToken);
      
      await channel.QueueDeclareAsync(
            queue: "document_processed_queue",
            durable:true,
            exclusive:false,
            autoDelete:false,
            cancellationToken:stoppingToken
       );

    var consumer = new AsyncEventingBasicConsumer(channel);

    consumer.ReceivedAsync += async (model ,ea) =>
    {
        var body = ea.Body.ToArray();
        var message = System.Text.Encoding.UTF8.GetString(body);
        Console.WriteLine($"Listener recieved from python : {message}");

        var dataObject = JsonSerializer.Deserialize<JsonElement>(message);

        _logger.LogInformation("Received message payload keys: {Keys}", string.Join(",", dataObject.EnumerateObject().Select(p => p.Name)));

        if (!dataObject.TryGetProperty("fileId", out var fileIdProp) || 
            !dataObject.TryGetProperty("chatId", out var chatIdProp) ||
            !dataObject.TryGetProperty("summary", out var summaryProp))
        {
            _logger.LogWarning("Missing required properties in payload. Skipping message.");
            await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
            return;
        }

        var fileIdStr = fileIdProp.ToString();
        var chatId = chatIdProp.ToString();
        var summary = summaryProp.ToString();

       using (var scope = _serviceScopeFactory.CreateScope())
       {
        var dbContext = scope.ServiceProvider.GetRequiredService<PrismDBContext>();

        var obj = await dbContext.FileRecords.FindAsync(Guid.Parse(fileIdStr));
        if(obj!=null)
            {
                obj.Summary = summary;
                obj.UploadedAt = DateTime.UtcNow;
                await dbContext.SaveChangesAsync();
            }
       }

        // Broadcast to the ChatId-scoped group rather than a single ConnectionId,
        // so the message still lands even if the client reconnected (new socket ID)
        // since it was uploaded.
        await _hubContext.Clients.Group($"chat-{chatId}").DocumentProcessed(dataObject);

        await channel.BasicAckAsync(ea.DeliveryTag,false,stoppingToken);

    };

    await channel.BasicConsumeAsync(
        queue:"document_processed_queue",
        autoAck:false,
        consumer:consumer,
        cancellationToken:stoppingToken
    );

        // keep the aaplication  running forver and close it  when user stop the appl;ication like stop the debugging
      await Task.Delay(-1,stoppingToken);
    }
}