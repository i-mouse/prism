using System.ComponentModel.DataAnnotations;

namespace Prism.ApiService.Data;

public class FileRecord
{

    [Key]
    public Guid FileId { get; set; }
    public string FileName { get; set; } = string.Empty;
    public string? Summary { get; set; } // Nullable, filled in later by Python
    public Prism.ApiService.Data.Schemas.ExtractionStatus Status { get; set; } = Prism.ApiService.Data.Schemas.ExtractionStatus.Pending;
    public DateTime UploadedAt { get; set; }

    // SHA-256 hex digest (64 chars) of the uploaded file's bytes, computed
    // before the blob upload. Used to dedupe identical papers across every
    // user/session - see ChatFile for how a chat is linked to a (possibly
    // shared) file now that a file no longer belongs to exactly one chat.
    [MaxLength(64)]
    public string? ContentHash { get; set; }
}