using System;
using System.Collections.Generic;

namespace Prism.ApiService.Data.Schemas;

public class PaperClaim
{
    public Guid Id { get; set; }
    public Guid DocumentExtractorId { get; set; }
    public DocumentExtractor DocumentExtractor { get; set; } = null!;
    public Guid ExtractionRunId { get; set; }
    public string ClaimTextVerbatim { get; set; } = "";
    public string ClaimSummary { get; set; } = "";
    public ClaimLabel Label { get; set; }
    public List<EvidenceSpan> EvidenceSpans { get; set; } = new();
    public GroundingStatus GroundingStatus { get; set; }
    public bool Missing { get; set; }
    public string? Reason { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}
