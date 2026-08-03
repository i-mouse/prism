using System.ComponentModel.DataAnnotations;

namespace Prism.ApiService.Data;

public class FileRecord
{
    
    [Key]
    public Guid FileId { get; set; }
    public string FileName { get; set; } = string.Empty;
    public string? Summary { get; set; } // Nullable, filled in later by Python
    public DateTime UploadedAt { get; set; }

    // Foreign Key linking back to the Chat
    public Guid ChatId { get; set; }
}