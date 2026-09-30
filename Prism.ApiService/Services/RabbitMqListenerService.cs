using Microsoft.AspNetCore.SignalR;
using Microsoft.EntityFrameworkCore.Metadata;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;
using Prism.ApiService.Hubs;
using  System.Text.Json;
using Prism.ApiService.Data;
using Prism.ApiService.Telemetry;
using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Services;

public class RabbitMqListenerService : BackgroundService
{
    private readonly IConnectionFactory _connectionFactory;
    private readonly IHubContext<DocumentHub,IDocumentClient> _hubContext;
    private readonly IServiceScopeFactory _serviceScopeFactory;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<RabbitMqListenerService> _logger;

    public RabbitMqListenerService(IConnectionFactory connectionFactory, IHubContext<DocumentHub, IDocumentClient> hubContext , IServiceScopeFactory serviceScopeFactory, IHttpClientFactory httpClientFactory, ILogger<RabbitMqListenerService> logger)
    {
        _connectionFactory = connectionFactory;
        _hubContext = hubContext;
        _serviceScopeFactory = serviceScopeFactory;
        _httpClientFactory = httpClientFactory;
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

        // ExtractionProgress events (stage events + grounding counter from the Python
        // pipeline) share this queue with the DocumentProcessed completion message.
        // They carry a "stage" field the completion message never has, so branch on
        // that rather than adding a second queue/consumer.
        if (dataObject.TryGetProperty("stage", out _))
        {
            if (!dataObject.TryGetProperty("fileId", out _) ||
                !dataObject.TryGetProperty("chatId", out var progressChatIdProp))
            {
                _logger.LogWarning("Missing required properties in progress payload. Skipping message.");
                await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
                return;
            }

            var progressChatId = progressChatIdProp.ToString();
            using (var activity = PrismTelemetry.ActivitySource.StartActivity("signalr.broadcast"))
            {
                activity?.SetTag("chat.id", progressChatId);
                activity?.SetTag("signalr.method", "ExtractionProgress");
                await _hubContext.Clients.Group($"chat-{progressChatId}").ExtractionProgress(dataObject);
            }
            await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
            return;
        }

        if (!dataObject.TryGetProperty("fileId", out var fileIdProp) ||
            !dataObject.TryGetProperty("chatId", out var chatIdProp) ||
            !dataObject.TryGetProperty("summary", out var summaryProp))
        {
            // Shape only (property names), never content - see log hygiene (§3 D).
            var payloadShape = string.Join(",", dataObject.EnumerateObject().Select(p => p.Name));
            _logger.LogWarning("Malformed completion message, shape: {Shape}. Missing required property.", payloadShape);

            // Without fileId there is no row to mark Failed - log and drop is
            // all that's possible. With fileId, the paper would otherwise be
            // stuck InProgress forever (B1.12) - mark it Failed instead.
            // Guarded the same way as the normal completion branch below: a
            // duplicate/late malformed message for an already-terminal file
            // must never flip a Completed paper to Failed and destroy its
            // real Summary (regression found and closed within this PR).
            if (fileIdProp.ValueKind != JsonValueKind.Undefined && Guid.TryParse(fileIdProp.ToString(), out var malformedFileGuid))
            {
                using var malformedScope = _serviceScopeFactory.CreateScope();
                var malformedDbContext = malformedScope.ServiceProvider.GetRequiredService<PrismDBContext>();
                var malformedRecord = await malformedDbContext.FileRecords.FindAsync(new object?[] { malformedFileGuid }, stoppingToken);
                if (malformedRecord != null)
                {
                    if (ShouldApplyStatusTransition(malformedRecord.Status))
                    {
                        malformedRecord.Status = Prism.ApiService.Data.Schemas.ExtractionStatus.Failed;
                        malformedRecord.Summary = "Processing failed: malformed completion message from the extraction worker.";
                        malformedRecord.UploadedAt = DateTime.UtcNow;
                        await malformedDbContext.SaveChangesAsync(stoppingToken);
                    }
                    else
                    {
                        _logger.LogWarning(
                            "Malformed completion message for fileId={FileId} arrived after it already reached a terminal state ({Status}) - ignoring, not overwriting.",
                            malformedFileGuid, malformedRecord.Status);
                    }
                }
            }

            await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
            return;
        }

        var fileIdStr = fileIdProp.ToString();
        var chatId = chatIdProp.ToString();
        var summary = summaryProp.ToString();
        
        var statusString = dataObject.TryGetProperty("status", out var statusProp) ? statusProp.ToString() : null;
        var finalStatus = MapCompletionStatus(statusString);
        if (finalStatus == Prism.ApiService.Data.Schemas.ExtractionStatus.Failed && statusString != "Error")
        {
            _logger.LogWarning("Completion message for fileId={FileId} had missing/unrecognized status {Status} - marking Failed", fileIdStr, statusString ?? "(missing)");
        }

       using (var scope = _serviceScopeFactory.CreateScope())
       {
        var dbContext = scope.ServiceProvider.GetRequiredService<PrismDBContext>();
        var fileGuid = Guid.Parse(fileIdStr);

        var obj = await dbContext.FileRecords.FindAsync(new object?[] { fileGuid }, stoppingToken);
        if (obj != null && !ShouldApplyStatusTransition(obj.Status))
        {
            // A duplicate or late completion message for a paper that already
            // reached a terminal state (Completed or Failed) - RabbitMQ has no
            // persistent volume in production and the retry path is
            // republish-and-ack, so duplicates are plausible. Applying this
            // would silently flip a Completed paper to Failed and destroy its
            // real Summary - worse than the bug it would "fix". Log and ignore
            // the whole message, including the broadcast below: the paper's
            // true state hasn't changed, so there is nothing honest to tell
            // connected clients that a refetch of the unchanged record
            // wouldn't already show them.
            _logger.LogWarning(
                "Completion message for fileId={FileId} arrived after it already reached a terminal state ({Status}) - ignoring, not overwriting.",
                fileIdStr, obj.Status);
            await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
            return;
        }
        if(obj!=null)
            {
                obj.Summary = summary;
                obj.Status = finalStatus;
                obj.UploadedAt = DateTime.UtcNow;
                await dbContext.SaveChangesAsync(stoppingToken);

                // main.py injects the summary directly into the chat_id that
                // actually ran this pipeline (the chat in this message's own
                // "chatId" field). Any OTHER chat already linked to this file —
                // one that joined via the Pending/InProgress path while this
                // run was still in flight — never gets that injection, so it
                // never gets a summary turn at all unless we do it here. Every
                // chat that ends up owning a Completed file should get exactly
                // one summary turn; see ChatSummaryInjector / SubmitPaperEndPoint's
                // HandleCacheHitAsync for the equivalent cache-hit case.
                if (finalStatus == Prism.ApiService.Data.Schemas.ExtractionStatus.Completed && Guid.TryParse(chatId, out var chatGuid))
                {
                    var otherChatIds = await dbContext.ChatFiles
                        .Where(cf => cf.FileId == fileGuid && cf.ChatId != chatGuid)
                        .Select(cf => cf.ChatId)
                        .ToListAsync(stoppingToken);

                    // Fire-and-forget, deliberately not awaited: a file can be
                    // linked to many chats (61, for one paper, in tonight's
                    // testing alone), and awaiting each injection here would
                    // block this consumer - a single-threaded receive loop -
                    // from picking up the next queued message for as long as
                    // the whole fan-out takes. ChatSummaryInjector already
                    // treats a failed injection as best-effort (it swallows
                    // its own exceptions), so not awaiting it here changes
                    // nothing about failure handling - only how soon the
                    // consumer is free to process the next message.
                    foreach (var otherChatId in otherChatIds)
                    {
                        _ = ChatSummaryInjector.InjectAsync(_httpClientFactory, otherChatId.ToString(), summary, stoppingToken);
                    }
                }
            }
       }

        // Broadcast to the ChatId-scoped group rather than a single ConnectionId,
        // so the message still lands even if the client reconnected (new socket ID)
        // since it was uploaded.
        using (var activity = PrismTelemetry.ActivitySource.StartActivity("signalr.broadcast"))
        {
            activity?.SetTag("chat.id", chatId);
            activity?.SetTag("signalr.method", "DocumentProcessed");
            await _hubContext.Clients.Group($"chat-{chatId}").DocumentProcessed(dataObject);
        }

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

    // Pure and static so it's testable without a broker. "Completed" maps to
    // Completed; everything else - "Error", missing, empty, or any other
    // value - maps to Failed. Callers decide separately whether an
    // unrecognized (non-"Error") value is worth a warning log.
    public static Prism.ApiService.Data.Schemas.ExtractionStatus MapCompletionStatus(string? statusString) =>
        statusString switch
        {
            "Completed" => Prism.ApiService.Data.Schemas.ExtractionStatus.Completed,
            _ => Prism.ApiService.Data.Schemas.ExtractionStatus.Failed,
        };

    // Pure and static so it's testable without a broker or a DbContext. A
    // completion message (normal or malformed) is only ever allowed to move
    // a paper OUT of Pending/InProgress. Once a paper is Completed or Failed,
    // every later message for that fileId - a duplicate, a late retry replay,
    // a malformed one - is logged and ignored rather than applied. RabbitMQ
    // has no persistent volume in production and the retry path is
    // republish-and-ack, so a duplicate delivery is plausible, not
    // theoretical. Regression found and closed within this PR: a prior
    // version of this guard did not exist, so a duplicate/malformed message
    // for an already-Completed file could silently flip it to Failed and
    // overwrite its real Summary.
    public static bool ShouldApplyStatusTransition(Prism.ApiService.Data.Schemas.ExtractionStatus currentStatus) =>
        currentStatus == Prism.ApiService.Data.Schemas.ExtractionStatus.Pending ||
        currentStatus == Prism.ApiService.Data.Schemas.ExtractionStatus.InProgress;
}