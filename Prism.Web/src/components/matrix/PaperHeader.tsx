import { Share2, Download, MoreHorizontal, FileText, HardDrive, Calendar, File } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ExtractionStatus } from "@/types/api";
import { extractionStatusMeta, extractionStatusToVerdict } from "@/lib/claimMeta";
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

const secondaryButtonClass =
  "gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-1.5 font-sans text-sm text-ink hover:border-hairline-strong hover:bg-surface";

const verdictDotClass = {
  supported: "bg-verdict-supported-icon",
  partial: "bg-verdict-partial-icon",
  refused: "bg-verdict-refused-icon",
  other: "bg-verdict-other-icon",
} as const;

export function PaperHeader({ 
  fileName, 
  extractionStatus, 
  completedAt,
  fileSize,
  pageCount,
  uploadedAt,
  onCancel
}: PaperHeaderProps) {
  const status = extractionStatusMeta[extractionStatus];
  const verdict = extractionStatusToVerdict[extractionStatus];
  const comingSoon = () => toast("Coming soon");

  return (
    <div className="flex items-start md:items-center justify-between gap-4">
      <div className="flex items-center gap-3 md:gap-4 min-w-0">
        <div className="hidden md:flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#EEF2FF] border border-[#E0E7FF]">
          <FileText className="h-6 w-6 text-[#6366F1]" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className="truncate font-sans text-lg md:text-2xl font-semibold text-ink leading-tight">{fileName}</div>
            <span className="rounded-full bg-surface-subtle border border-hairline px-2 py-0.5 font-sans text-[10px] font-medium text-ink-secondary uppercase tracking-wider">PDF</span>
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            {extractionStatus === "Completed" ? (
              <>
                <span className={cn("h-1.5 w-1.5 rounded-full", verdictDotClass[verdict])} />
                <span className="font-sans text-xs md:text-sm text-ink-secondary truncate">
                  {completedAt ? `Completed ${relativeTime(completedAt)}` : status.label}
                </span>
              </>
            ) : (
              <span className="font-sans text-xs md:text-sm text-ink-secondary truncate">
                Auditing paper
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="hidden lg:flex items-center gap-8 mr-auto ml-12">
        {fileSize && (
          <div className="flex items-center gap-3">
            <HardDrive className="h-4 w-4 text-ink-tertiary" />
            <div className="flex flex-col">
              <span className="font-sans text-xs font-semibold text-ink">{fileSize}</span>
              <span className="font-sans text-[10px] text-ink-secondary">File size</span>
            </div>
          </div>
        )}
        {pageCount !== undefined && (
          <div className="flex items-center gap-3">
            <File className="h-4 w-4 text-ink-tertiary" />
            <div className="flex flex-col">
              <span className="font-sans text-xs font-semibold text-ink">{pageCount} pages</span>
              <span className="font-sans text-[10px] text-ink-secondary">Document</span>
            </div>
          </div>
        )}
        {uploadedAt && (
          <div className="flex items-center gap-3">
            <Calendar className="h-4 w-4 text-ink-tertiary" />
            <div className="flex flex-col">
              <span className="font-sans text-xs font-semibold text-ink">{uploadedAt}</span>
              <span className="font-sans text-[10px] text-ink-secondary">Uploaded</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {extractionStatus !== "Completed" && onCancel ? (
          <Button variant="outline" size="sm" onClick={onCancel} className={cn(secondaryButtonClass, "hidden md:flex")}>
            <Share2 className="h-4 w-4 hidden" />
            Cancel
          </Button>
        ) : (
          <>
            <Button variant="outline" size="sm" onClick={comingSoon} className={cn(secondaryButtonClass, "hidden md:flex")}>
              <Share2 className="h-4 w-4" />
              Share
            </Button>
            <Button variant="outline" size="sm" onClick={comingSoon} className={cn(secondaryButtonClass, "hidden md:flex")}>
              <Download className="h-4 w-4" />
              Export
            </Button>
            <Button variant="outline" size="sm" onClick={comingSoon} className={cn(secondaryButtonClass, "hidden md:flex px-3")}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </>
        )}

        {/* Mobile: Share/Export/More collapse into one overflow menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className={cn(secondaryButtonClass, "flex md:hidden px-2")}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {extractionStatus !== "Completed" && onCancel ? (
              <DropdownMenuItem onSelect={onCancel}>
                Cancel
              </DropdownMenuItem>
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
                <DropdownMenuItem onSelect={comingSoon}>
                  <MoreHorizontal className="mr-2 h-4 w-4" />
                  More
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
