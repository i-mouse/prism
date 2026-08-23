import type { EvidenceSpanDto } from "@/types/api";
import { groundingStatusMeta } from "@/lib/claimMeta";

interface EvidenceCardProps {
  span: EvidenceSpanDto;
}

export function EvidenceCard({ span }: EvidenceCardProps) {
  const status = groundingStatusMeta[span.groundingStatus];

  return (
    <div className="space-y-3 rounded-md border border-border bg-surface p-4">
      <p className="font-mono text-[13px] leading-relaxed text-ink">{span.sourceText}</p>
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.05em] text-ink-subtle">
          {span.sourceSection}
          {span.pageNumber != null ? ` · p. ${span.pageNumber}` : ""}
        </p>
        <span className={`h-5 text-xs font-semibold uppercase tracking-[0.05em] ${status.textClass}`}>
          {status.label}
        </span>
      </div>
    </div>
  );
}
