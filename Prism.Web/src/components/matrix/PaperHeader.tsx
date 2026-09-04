import { Share2, Download, MoreHorizontal, FileText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-accent-subtle/60">
          <FileText className="h-5 w-5 text-ink-tertiary" />
        </div>
        <div>
          <div className="font-sans text-2xl font-semibold text-ink">{fileName}</div>
          <div className="flex items-center gap-1.5">
            <span className={cn("h-1.5 w-1.5 rounded-full", verdictDotClass[verdict])} />
            <span className="font-sans text-sm text-ink-secondary">
              {extractionStatus === "Completed" && completedAt
                ? `Completed ${relativeTime(completedAt)}`
                : status.label}
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={comingSoon} className={secondaryButtonClass}>
          <Share2 className="h-4 w-4" />
          Share
        </Button>
        <Button variant="outline" size="sm" onClick={comingSoon} className={secondaryButtonClass}>
          <Download className="h-4 w-4" />
          Export
        </Button>
        <Button variant="outline" size="sm" onClick={comingSoon} className={secondaryButtonClass}>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
