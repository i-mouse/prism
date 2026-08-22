namespace Prism.ApiService.Features.PaperSubmission;

public record PaperClaimsResponse(
    Guid PaperId,
    string FileName,
    string ExtractionStatus,
    DateTime? CompletedAt,
    ClaimsSummary Summary,
    IReadOnlyList<ClaimDto> Claims);

public record ClaimsSummary(
    int Total,
    int Supported,
    int PartiallySupported,
    int NotSupported);

public record ClaimDto(
    Guid Id,
    string ClaimTextVerbatim,
    string ClaimSummary,
    string Label,
    bool Missing,
    string? Reason,
    string GroundingStatus,
    int Position,
    IReadOnlyList<EvidenceSpanDto> EvidenceSpans);

public record EvidenceSpanDto(
    string SourceText,
    string SourceSection,
    string? SectionHeader,
    int? PageNumber,
    string GroundingStatus);
