import { CheckCircle2, AlertCircle, XCircle, type LucideIcon } from "lucide-react";
import type { ClaimLabel, ExtractionStatus, GroundingStatus } from "@/types/api";
import type { Verdict } from "@/components/VerdictPill";

export const claimLabelToVerdict: Record<ClaimLabel, Verdict> = {
  supported: "supported",
  partially_supported: "partial",
  not_supported: "refused",
};

interface StatusMeta {
  label: string;
  Icon: LucideIcon;
  textClass: string;
  bgClass: string;
}

export const extractionStatusMeta: Record<ExtractionStatus, StatusMeta> = {
  Completed: { label: "Ready", Icon: CheckCircle2, textClass: "text-supported", bgClass: "bg-supported-bg" },
  "In progress": { label: "Analyzing", Icon: AlertCircle, textClass: "text-partial", bgClass: "bg-partial-bg" },
  Pending: { label: "Analyzing", Icon: AlertCircle, textClass: "text-partial", bgClass: "bg-partial-bg" },
  Failed: { label: "Failed", Icon: XCircle, textClass: "text-refused", bgClass: "bg-refused-bg" },
};

export const extractionStatusToVerdict: Record<ExtractionStatus, Verdict> = {
  Completed: "supported",
  "In progress": "partial",
  Pending: "partial",
  Failed: "refused",
};

export const groundingStatusMeta: Record<GroundingStatus, { label: string }> = {
  Pass: { label: "Pass" },
  Partial: { label: "Partial" },
  Fail: { label: "Fail" },
  Skipped: { label: "Skipped" },
};

export const groundingStatusToVerdict: Record<GroundingStatus, Verdict> = {
  Pass: "supported",
  Partial: "partial",
  Fail: "refused",
  Skipped: "other",
};
