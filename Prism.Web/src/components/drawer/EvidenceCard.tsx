import type { EvidenceSpanDto } from "@/types/api";
import { groundingStatusMeta, groundingStatusToVerdict } from "@/lib/claimMeta";
import { VerdictPill } from "@/components/VerdictPill";

interface EvidenceCardProps {
  span: EvidenceSpanDto;
}

export function EvidenceCard({ span }: EvidenceCardProps) {
  const status = groundingStatusMeta[span.groundingStatus];
  const verdict = groundingStatusToVerdict[span.groundingStatus];

  return (
    <div className="space-y-2">
      <p className="rounded-lg border border-hairline bg-surface-subtle p-3 font-mono text-sm text-ink">
        {span.sourceText}
      </p>
      <div className="flex items-center justify-between">
        <p className="font-mono text-xs uppercase tracking-wider text-ink-tertiary">
          {span.sourceSection}
          {span.pageNumber != null ? ` · p. ${span.pageNumber}` : ""}
        </p>
        <VerdictPill verdict={verdict} label={status.label} size="sm" />
      </div>
    </div>
  );
}
