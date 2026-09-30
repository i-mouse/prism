namespace Prism.ApiService.Features.PaperSubmission;

public record PaperClaimsResponse(
    Guid PaperId,
    string FileName,
    string ExtractionStatus,
    DateTime? CompletedAt,
    ClaimsSummary Summary,
    IReadOnlyList<ClaimDto> Claims,
    string? PromptVersion = null,
    bool? IsCurrentPromptVersion = null,
    // Only set when ExtractionStatus is "Failed" - the same FileRecord.Summary
    // column also carries the AI-generated paper summary for a Completed
    // paper, so this is named for what it means here, not for the column it
    // reads from. Null for every other status.
    string? FailureReason = null);

public record RerunPaperRequest(string ChatId, string ConnectionId);

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
