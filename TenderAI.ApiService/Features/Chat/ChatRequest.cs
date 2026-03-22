
namespace TenderAI.ApiService.Features.Chat
{
    public class ChatRequest
    {
        public required string question { get; set; }
        
        public required string userId { get; set; }
        public string chatId { get; set; } = "default_thread";
    }

    // Update your models
public class ChatResponse
{
    public string Answer { get; set; } = string.Empty;
    public string? Caveat { get; set; }
    public bool IsTrusted { get; set; }
    public string? Intent { get; set; }
    public List<TenderSource>? Sources { get; set; }
}

public class TenderSource
{
    public string Filename { get; set; } = string.Empty;
    public float Score { get; set; }
    public string Content { get; set; } = string.Empty;
}
}
