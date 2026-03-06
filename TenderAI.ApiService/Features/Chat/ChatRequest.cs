
namespace TenderAI.ApiService.Features.Chat
{
    public class ChatRequest
    {
        public required string question { get; set; }
        public string thread_id { get; set; } = "default_thread";
    }

    public class ChatResponse
    {
        public string Answer { get; set; } = string.Empty;
    }
}
