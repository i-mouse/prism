import { Share2, Download, MoreHorizontal, FileText } from "lucide-react";
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
}

const secondaryButtonClass =
  "gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-1.5 font-sans text-sm text-ink hover:border-hairline-strong hover:bg-surface";

const verdictDotClass = {
  supported: "bg-verdict-supported-icon",
  partial: "bg-verdict-partial-icon",
  refused: "bg-verdict-refused-icon",
  other: "bg-verdict-other-icon",
} as const;

export function PaperHeader({ fileName, extractionStatus, completedAt }: PaperHeaderProps) {
  const status = extractionStatusMeta[extractionStatus];
  const verdict = extractionStatusToVerdict[extractionStatus];
  const comingSoon = () => toast("Coming soon");

  return (
    <div className="flex items-start md:items-center justify-between gap-4">
      <div className="flex items-center gap-3 md:gap-4 min-w-0">
        <div className="hidden md:flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-surface-subtle border border-hairline">
          <FileText className="h-5 w-5 text-ink-tertiary" />
        </div>
        <div className="min-w-0">
          <div className="truncate font-sans text-lg md:text-2xl font-semibold text-ink leading-tight">{fileName}</div>
          <div className="flex items-center gap-1.5 mt-1">
            <span className={cn("h-1.5 w-1.5 rounded-full", verdictDotClass[verdict])} />
            <span className="font-sans text-xs md:text-sm text-ink-secondary truncate">
              {extractionStatus === "Completed" && completedAt
                ? `Completed ${relativeTime(completedAt)}`
                : status.label}
            </span>
          </div>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
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

        {/* Mobile: Share/Export/More collapse into one overflow menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className={cn(secondaryButtonClass, "flex md:hidden px-2")}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onSelect={comingSoon}>
              <Share2 />
              Share
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={comingSoon}>
              <Download />
              Export
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={comingSoon}>
              <MoreHorizontal />
              More
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
