import { Share2, Download, MoreHorizontal, FileText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { ExtractionStatus } from "@/types/api";
import { extractionStatusMeta } from "@/lib/claimMeta";
import { relativeTime } from "@/lib/format";

interface PaperHeaderProps {
  fileName: string;
  extractionStatus: ExtractionStatus;
  completedAt: string | null;
}

const secondaryButtonClass =
  "gap-1.5 border-border bg-surface text-ink hover:border-border-strong hover:bg-surface-sunken";

export function PaperHeader({ fileName, extractionStatus, completedAt }: PaperHeaderProps) {
  const status = extractionStatusMeta[extractionStatus];
  const StatusIcon = status.Icon;
  const comingSoon = () => toast("Coming soon");

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-accent-subtle/60">
          <FileText className="h-5 w-5 text-accent" />
        </div>
        <div>
          <div className="font-display text-2xl font-bold tracking-[-0.02em] text-ink">{fileName}</div>
          <div className="flex items-center gap-1.5">
            <StatusIcon className={`h-4 w-4 ${status.textClass}`} />
            <span className="text-sm tabular-nums text-ink-muted">
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
