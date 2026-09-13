
namespace Prism.ApiService.Features.PaperSubmission
{
    public class SubmitPaperRequest
    {
        public IFormFileCollection? Files { get; set; }
        // UserId intentionally removed — resolved server-side from JWT or guest-session cookie.
        public required string ConnectionId { get; set; }
        public string ChatId {get;set;}= string.Empty;

    }
}
