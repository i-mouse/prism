import { CheckCircle2, AlertCircle, XCircle, type LucideIcon } from "lucide-react";
import type { ClaimLabel, ExtractionStatus, GroundingStatus } from "@/types/api";

interface ClaimLabelMeta {
  text: string;
  Icon: LucideIcon;
  textClass: string;
  bgClass: string;
  borderClass: string;
  cardBgClass: string;
}

export const claimLabelMeta: Record<ClaimLabel, ClaimLabelMeta> = {
  supported: {
    text: "SUPPORTED",
    Icon: CheckCircle2,
    textClass: "text-supported",
    bgClass: "bg-supported-bg",
    borderClass: "border-l-supported",
    cardBgClass: "bg-surface",
  },
  partially_supported: {
    text: "PARTIAL",
    Icon: AlertCircle,
    textClass: "text-partial",
    bgClass: "bg-partial-bg",
    borderClass: "border-l-partial",
    cardBgClass: "bg-partial-bg/40",
  },
  not_supported: {
    text: "NOT SUPPORTED",
    Icon: XCircle,
    textClass: "text-refused",
    bgClass: "bg-refused-bg",
    borderClass: "border-l-refused",
    cardBgClass: "bg-refused-bg",
  },
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

export const groundingStatusMeta: Record<GroundingStatus, { label: string; textClass: string; bgClass: string }> = {
  Pass: { label: "Pass", textClass: "text-supported", bgClass: "bg-supported-bg" },
  Fail: { label: "Fail", textClass: "text-refused", bgClass: "bg-refused-bg" },
  Skipped: { label: "Skipped", textClass: "text-ink-muted", bgClass: "bg-surface-sunken" },
};
