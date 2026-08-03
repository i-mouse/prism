using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace Prism.ApiService.Data.Schemas;

public class DocumentExtractor
{
    [Key]
    public Guid Id { get; set; }

    [Required]
    public Guid FileId { get; set; }

    [Required]
    public Guid DomainId { get; set; }

    [Required]
    [Column(TypeName = "jsonb")]
    public string Fields { get; set; } = "{}";

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

    // Navigation
    [ForeignKey(nameof(FileId))]
    public FileRecord? FileRecord { get; set; }

    [ForeignKey(nameof(DomainId))]
    public Domain? Domain { get; set; }

    public Guid? LatestRunId { get; set; }
    
    public ICollection<PaperClaim> PaperClaims { get; set; } = new List<PaperClaim>();
}