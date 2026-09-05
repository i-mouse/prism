import type { EvidenceSpanDto } from "@/types/api";
import { groundingStatusToVerdict } from "@/lib/claimMeta";
import { VerdictPill } from "@/components/VerdictPill";

interface EvidenceCardProps {
  span: EvidenceSpanDto;
}

export function EvidenceCard({ span }: EvidenceCardProps) {
  const verdict = groundingStatusToVerdict[span.groundingStatus];

  return (
    <div className="space-y-2 mt-4">
      <div className="flex items-center justify-between">
        <div className="font-sans text-xs md:text-sm font-semibold text-ink">
          {span.sourceSection}
        </div>
        <div className="flex items-center gap-4">
          <VerdictPill verdict={verdict} label={verdict === "supported" ? "PASS" : "FAIL"} size="sm" />
          {span.pageNumber != null && (
            <span className="font-sans text-[10px] md:text-xs text-ink-tertiary">Page {span.pageNumber}</span>
          )}
        </div>
      </div>
      <p className="rounded-lg border border-hairline bg-surface-subtle p-3 md:p-4 font-mono text-xs md:text-sm text-ink leading-relaxed">
        {span.sourceText}
      </p>
    </div>
  );
}
