import { FileText } from "lucide-react";
import type { ExtractionStatus } from "@/types/api";
import { extractionStatusMeta } from "@/lib/claimMeta";

interface CurrentContextCardProps {
  fileName: string;
  fileSizeLabel?: string | null;
  extractionStatus: ExtractionStatus;
}

export function CurrentContextCard({ fileName, fileSizeLabel, extractionStatus }: CurrentContextCardProps) {
  const status = extractionStatusMeta[extractionStatus];
  const StatusIcon = status.Icon;
  const statusText =
    extractionStatus === "Completed"
      ? "Ready to analyze"
      : extractionStatus === "Failed"
        ? "Failed"
        : "Analyzing…";

  return (
    <div className="space-y-3 rounded-md border border-border bg-surface p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent-subtle/60">
          <FileText className="h-4 w-4 text-accent" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-ink">{fileName}</div>
          <div className="text-xs text-ink-muted">PDF{fileSizeLabel ? ` · ${fileSizeLabel}` : ""}</div>
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <StatusIcon className={`h-4 w-4 ${status.textClass}`} />
        <span className="text-xs text-ink-muted">{statusText}</span>
      </div>
    </div>
  );
}
