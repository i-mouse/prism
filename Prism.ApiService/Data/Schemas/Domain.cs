using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace Prism.ApiService.Data.Schemas;

public class Domain
{
    [Key]
    public string Id { get; set; } = Guid.NewGuid().ToString();

    [Required]
    public string Name { get; set; } = string.Empty;

    [Required]
    [Column(TypeName = "jsonb")]
    public string PromptSchema { get; set; } = "{}";

    public bool IsActive { get; set; } = true;

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

    // Navigation
   public ICollection<DocumentExtractor> DocumentExtractors { get; set; } = new List<DocumentExtractor>();
}