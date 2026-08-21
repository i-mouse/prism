
namespace Prism.ApiService.Features.PaperSubmission
{
    public class SubmitPaperRequest
    {
        public IFormFileCollection? Files { get; set; }
        public required string UserId { get; set; }
        public required string ConnectionId { get; set; }
        public string ChatId {get;set;}= string.Empty;

    }
}
