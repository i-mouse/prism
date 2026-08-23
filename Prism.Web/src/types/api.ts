export type ClaimLabel = "supported" | "partially_supported" | "not_supported";

export type GroundingStatus = "Pass" | "Fail" | "Skipped";

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
