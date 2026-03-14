using Microsoft.AspNetCore.SignalR;

namespace TenderAI.ApiService.Hubs;

public interface IDocumentClient
{
    Task DocumentProcessed(object data);
}
public class DocumentHub: Hub<IDocumentClient> 
{
    // This is the empty WebSocket server that React will connect to later
}