using Microsoft.AspNetCore.SignalR;

namespace Prism.ApiService.Hubs;

public interface IDocumentClient
{
    Task DocumentProcessed(object data);
    Task ExtractionProgress(object data);
}
public class DocumentHub: Hub<IDocumentClient>
{
    private readonly ILogger<DocumentHub> _logger;

    public DocumentHub(ILogger<DocumentHub> logger)
    {
        _logger = logger;
    }

    // Called by the client after connect/reconnect so broadcasts can target
    // a ChatId-scoped group instead of a single (potentially stale) ConnectionId.
    public async Task JoinChat(string chatId)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, $"chat-{chatId}");
        _logger.LogInformation("Connection {ConnectionId} joined group chat-{ChatId}", Context.ConnectionId, chatId);
    }

    // Called by the client when it switches to a different chat, so group
    // membership doesn't grow unbounded for the life of the connection —
    // without this, a connection that visits N chats stays subscribed to
    // all N groups forever (or until disconnect), receiving broadcasts for
    // chats it's no longer viewing.
    public async Task LeaveChat(string chatId)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"chat-{chatId}");
        _logger.LogInformation("Connection {ConnectionId} left group chat-{ChatId}", Context.ConnectionId, chatId);
    }

    public override Task OnConnectedAsync()
    {
        _logger.LogInformation("SignalR connection established: {ConnectionId}", Context.ConnectionId);
        return base.OnConnectedAsync();
    }

    public override Task OnDisconnectedAsync(Exception? exception)
    {
        _logger.LogInformation(exception, "SignalR connection closed: {ConnectionId}", Context.ConnectionId);
        return base.OnDisconnectedAsync(exception);
    }
}