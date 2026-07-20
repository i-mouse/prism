using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace Prism.ApiService.Data.Schemas;

public class DocumentExtractor
{
    [Key]
    public string Id { get; set; } = Guid.NewGuid().ToString();

    [Required]
    public string FileId { get; set; } = string.Empty;

    [Required]
    public string DomainId { get; set; } = string.Empty;

    [Required]
    [Column(TypeName = "jsonb")]
    public string Fields { get; set; } = "{}";

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

    // Navigation
    [ForeignKey(nameof(FileId))]
    public FileRecords? FileRecord { get; set; }

    [ForeignKey(nameof(DomainId))]
    public Domain? Domain { get; set; }
}