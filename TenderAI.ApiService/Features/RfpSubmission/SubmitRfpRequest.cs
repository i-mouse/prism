
namespace TenderAI.ApiService.Features.RfpSubmission
{
    public class SubmitRfpRequest
    {
        public required IFormFile File { get; set; }
        public required string UserId { get; set; }
        public required string ConnectionId { get; set; }
        public  string? FileId { get; set; }
        public string ChatId {get;set;}= string.Empty;

    }
}
