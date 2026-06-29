using System.ComponentModel.DataAnnotations;

namespace Prism.ApiService.Data;

public class FileRecords
{
    
    [Key]
    public string FileId { get; set; } = string.Empty;
    public string FileName { get; set; } = string.Empty;
    public string? Summary { get; set; } // Nullable, filled in later by Python
    public DateTime UploadedAt { get; set; }

    // Foreign Key linking back to the Chat
    public string ChatId { get; set; } = string.Empty;
    public PrismDocument? Chat { get; set; }

}