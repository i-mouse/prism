import { Share2, Download, ChevronDown, FileText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ExtractionStatus } from "@/types/api";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PaperHeaderProps {
  fileName: string;
  extractionStatus: ExtractionStatus;
  completedAt: string | null;
  fileSize?: string;
  pageCount?: number;
  uploadedAt?: string;
  onCancel?: () => void;
}

const actionButtonClass =
  "h-9 flex items-center justify-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 font-sans text-sm text-ink-secondary hover:border-hairline-strong hover:bg-surface-subtle";

export function PaperHeader({
  fileName,
  extractionStatus,
  completedAt,
  onCancel,
}: PaperHeaderProps) {
  const isCompleted = extractionStatus === "Completed";
  const isFailed = extractionStatus === "Failed";
  const comingSoon = () => toast("Coming soon");

  const statusText = isCompleted
    ? completedAt
      ? `Completed ${relativeTime(completedAt)}`
      : "Completed"
    : isFailed
      ? "Audit failed"
      : "Auditing paper…";

  return (
    <div className="flex items-center justify-between gap-4">
      {/* Left: PDF badge + filename + status */}
      <div className="flex items-center gap-3 md:gap-4 min-w-0">
        {/* PDF icon badge — ink-black; red is reserved for claim verdicts */}
        <div className="hidden md:flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-ink text-white">
          <FileText className="h-6 w-6" strokeWidth={1.5} />
        </div>

        <div className="min-w-0">
          {/* Filename + PDF pill */}
          <div className="flex items-center gap-2">
            <h1 className="truncate font-sans text-lg md:text-2xl font-bold text-ink leading-tight">
              {fileName}
            </h1>
            <span className="shrink-0 rounded-md bg-surface-subtle px-1.5 py-0.5 font-sans text-[10px] font-bold text-ink-tertiary uppercase tracking-wider">
              PDF
            </span>
          </div>

          {/* Status row */}
          <div className="mt-0.5 flex items-center gap-1.5">
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
            <span
              className={cn(
                "font-sans text-xs md:text-sm",
                isFailed ? "text-status-failed" : "text-ink-secondary"
              )}
            >
              {statusText}
            </span>
          </div>
        </div>
      </div>

      {/* Right: action buttons */}
      <div className="flex shrink-0 items-center gap-2">
        {extractionStatus !== "Completed" && onCancel ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onCancel}
            className={cn(actionButtonClass, "hidden md:flex")}
          >
            Cancel
          </Button>
        ) : (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={comingSoon}
              className={cn(actionButtonClass, "hidden md:flex")}
            >
              <Share2 className="h-4 w-4" />
              Share
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={comingSoon}
              className={cn(actionButtonClass, "hidden md:flex")}
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
          </>
        )}

        {/* Mobile overflow menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className={cn(actionButtonClass, "flex md:hidden px-2")}
            >
              <ChevronDown className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {extractionStatus !== "Completed" && onCancel ? (
              <DropdownMenuItem onSelect={onCancel}>Cancel</DropdownMenuItem>
            ) : (
              <>
                <DropdownMenuItem onSelect={comingSoon}>
                  <Share2 className="mr-2 h-4 w-4" />
                  Share
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={comingSoon}>
                  <Download className="mr-2 h-4 w-4" />
                  Export
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
