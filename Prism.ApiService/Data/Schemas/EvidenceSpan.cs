namespace Prism.ApiService.Data.Schemas;

public class EvidenceSpan
{
    public string SourceText { get; set; } = "";
    public string SourceSection { get; set; } = "";
    public string? SectionHeader { get; set; }
    public int? PageNumber { get; set; }
    public GroundingStatus GroundingStatus { get; set; }
}
