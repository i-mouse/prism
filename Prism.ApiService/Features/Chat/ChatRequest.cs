
namespace Prism.ApiService.Features.Chat
{
    public class PaperChatAskRequest
{
    public required string chat_id { get; set; }
    public required string active_file_id { get; set; }
    public required string message { get; set; }
}
}
