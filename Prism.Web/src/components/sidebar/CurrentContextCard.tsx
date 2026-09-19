import { FileText } from "lucide-react";
import type { ExtractionStatus } from "@/types/api";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface CurrentContextCardProps {
  fileName: string;
  fileSizeLabel?: string | null;
  extractionStatus: ExtractionStatus;
  completedAt?: string | null;
}

export function CurrentContextCard({
  fileName,
  extractionStatus,
  completedAt,
}: CurrentContextCardProps) {
  const isCompleted = extractionStatus === "Completed";
  const isFailed = extractionStatus === "Failed";
  const isInProgress = !isCompleted && !isFailed;

  const statusText = isCompleted
    ? completedAt
      ? `Completed ${relativeTime(completedAt)}`
      : "Completed"
    : isFailed
      ? "Failed"
      : "Analyzing…";

  return (
    <div className="flex items-center gap-3 rounded-lg border border-hairline bg-surface-subtle px-3 py-2.5">
      {/* PDF badge — ink-black, not verdict-red: this marks the active
          paper (a selection/status indicator), not a claim verdict. */}
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-ink text-white">
        <FileText className="h-4 w-4" strokeWidth={1.5} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate font-sans text-sm font-semibold text-ink">{fileName}</div>
        <div className="mt-0.5 flex items-center gap-1.5">
          {/* Status dot — reuses the audit-progress status tokens, not
              verdict colors, since this reflects extraction status rather
              than a claim verdict. */}
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 rounded-full shrink-0",
              isCompleted
                ? "bg-status-complete"
                : isFailed
                  ? "bg-status-failed"
                  : "bg-status-active animate-pulse"
            )}
          />
          {/* Status text */}
          {isInProgress ? (
            <span className="font-sans text-[11px] text-status-active">{statusText}</span>
          ) : (
            <span className="font-sans text-[11px] text-ink-secondary">{statusText}</span>
          )}
        </div>
      </div>
    </div>
  );
}
