import { ChevronRight } from "lucide-react";
import type { ClaimDto } from "@/types/api";
import { claimLabelMeta } from "@/lib/claimMeta";
import { displayLabel, humanizeReason } from "@/lib/claim-display";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { cn } from "@/lib/utils";

interface AbsenceRowProps {
  claim: ClaimDto;
  onViewEvidence: () => void;
}

export function AbsenceRow({ claim, onViewEvidence }: AbsenceRowProps) {
  const meta = claimLabelMeta[displayLabel(claim)];
  const Icon = meta.Icon;
  const firstSpan = claim.evidenceSpans[0];
  const { selectedClaimId, highlightedClaimId } = useSelectedClaim();
  const isSelected = selectedClaimId === claim.id;
  const isHighlighted = highlightedClaimId === claim.id;

  return (
    <div
      data-claim-id={claim.id}
      className={cn(
        "flex items-start gap-4 rounded-r-md rounded-l-none border border-border border-l-4 px-6 py-4",
        meta.borderClass,
        meta.cardBgClass,
        isHighlighted && "ring-2 ring-accent ring-offset-2 ring-offset-surface transition-all duration-300"
      )}
    >
      <div className="flex w-40 shrink-0 flex-col items-start">
        <span
          className={cn(
            "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-semibold uppercase tracking-wider",
            meta.bgClass,
            meta.textClass
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {meta.text}
        </span>
      </div>

      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="text-[15px] font-semibold leading-snug text-ink">{claim.claimSummary}</div>
        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-refused">(No Evidence)</div>
        <p className="text-sm font-normal text-refused">No supporting evidence in this paper.</p>
        {claim.reason && (
          <p className="text-sm leading-relaxed text-ink">{humanizeReason(claim.reason)}</p>
        )}
        <div className="text-xs text-ink-subtle uppercase tracking-[0.05em]">
          {firstSpan?.sourceSection}
          {firstSpan?.pageNumber != null ? ` · p. ${firstSpan.pageNumber}` : ""}
        </div>
      </div>

      <button
        type="button"
        onClick={onViewEvidence}
        className={cn(
          "group inline-flex shrink-0 items-center gap-1 text-sm font-medium text-ink-muted underline-offset-4 transition-colors duration-quick ease-smooth hover:text-ink hover:underline",
          isSelected && "text-accent underline hover:text-accent"
        )}
      >
        View Evidence
        <ChevronRight className="h-4 w-4 opacity-0 transition-opacity duration-quick ease-smooth group-hover:opacity-100" />
      </button>
    </div>
  );
}
