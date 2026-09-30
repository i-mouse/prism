export type ClaimLabel = "supported" | "partially_supported" | "not_supported";

export type GroundingStatus = "Pass" | "Partial" | "Fail" | "Skipped";

export type ExtractionStatus = "Pending" | "In progress" | "Completed" | "Failed";

export interface EvidenceSpanDto {
  sourceText: string;
  sourceSection: string;
  sectionHeader?: string | null;
  pageNumber?: number | null;
  groundingStatus: GroundingStatus;
}

export interface ClaimDto {
  id: string;
  claimTextVerbatim: string;
  claimSummary: string;
  label: ClaimLabel;
  missing: boolean;
  reason?: string | null;
  groundingStatus: GroundingStatus;
  position: number;
  evidenceSpans: EvidenceSpanDto[];
}

export interface ClaimsSummary {
  total: number;
  supported: number;
  partiallySupported: number;
  notSupported: number;
}

export interface PaperClaimsResponse {
  paperId: string;
  fileName: string;
  extractionStatus: ExtractionStatus;
  completedAt: string | null;
  summary: ClaimsSummary;
  claims: ClaimDto[];
  promptVersion?: string | null;
  isCurrentPromptVersion?: boolean | null;
  // Only set when extractionStatus is "Failed" - the authoritative, fetched
  // cause of the failure. See ExtractionProgressEvent.reason for the live
  // (fast-path) equivalent; the two are written from the same source string
  // on the backend and must never disagree.
  failureReason?: string | null;
}

export interface ChatListItem {
  chatId: string;
  fileName: string;
  extractionStatus: ExtractionStatus;
  uploadedAt: string;
}

export interface FileListItem {
  fileId: string;
  fileName: string;
  summary: string | null;
  uploadedAt: string;
  status: string;
}

export type ExtractionStage =
  | "preparing"
  | "extracting"
  | "auditing"
  | "grounding"
  | "finalizing"
  | "done"
  | "failed";

export interface ExtractionProgressEvent {
  fileId: string;
  chatId: string;
  stage: ExtractionStage;
  completed?: number;
  total?: number;
  failedStage?: ExtractionStage;
  detail?: string;
  // Only present on a stage:"failed" event - the live (fast-path) cause of
  // the failure. See PaperClaimsResponse.failureReason for the fetched,
  // authoritative equivalent.
  reason?: string;
}

export interface SubmitPaperResponse {
  message: string;
  userId: string;
  isCacheHit: boolean;
}
