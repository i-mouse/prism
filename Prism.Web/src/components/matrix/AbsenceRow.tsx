import { ArrowRight } from "lucide-react";
import type { ClaimDto } from "@/types/api";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import { displayLabel, humanizeReason } from "@/lib/claim-display";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { VerdictPill, verdictBorderClass } from "@/components/VerdictPill";
import { cn } from "@/lib/utils";

interface AbsenceRowProps {
  claim: ClaimDto;
  onViewEvidence: () => void;
}

export function AbsenceRow({ claim, onViewEvidence }: AbsenceRowProps) {
  const verdict = claimLabelToVerdict[displayLabel(claim)];
  const firstSpan = claim.evidenceSpans[0];
  const { selectedClaimId, highlightedClaimId } = useSelectedClaim();
  const isSelected = selectedClaimId === claim.id;
  const isHighlighted = highlightedClaimId === claim.id;

  return (
    <div
      data-claim-id={claim.id}
      className={cn(
        "relative overflow-hidden rounded-xl border border-hairline bg-surface p-3 md:p-5 transition-all duration-150 ease-out hover:border-zinc-400 hover:bg-surface-subtle",
        isHighlighted && "ring-2 ring-brand-subtle ring-offset-2 ring-offset-surface transition-all duration-300"
      )}
    >
      <div className={cn("absolute top-0 left-0 h-full w-1.5", verdictBorderClass[verdict])} />

      <div className="flex items-start justify-between gap-4">
        <VerdictPill verdict={verdict} className="hidden md:inline-flex" />
        <VerdictPill verdict={verdict} size="sm" className="md:hidden" />
        
        <button
          type="button"
          onClick={onViewEvidence}
          className={cn(
            "group hidden md:inline-flex shrink-0 items-center gap-1 font-sans text-sm text-brand hover:text-brand-hover",
            isSelected && "underline"
          )}
        >
          View Evidence
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>

      <div className="mt-2 line-clamp-2 font-sans text-sm md:text-base font-medium leading-snug text-ink md:line-clamp-none md:leading-normal">{claim.claimSummary}</div>

      <div className="mt-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-verdict-refused-text md:mt-3">
        (No Evidence)
      </div>
      <p className="line-clamp-1 text-sm font-normal text-verdict-refused-text md:line-clamp-none">No supporting evidence in this paper.</p>
      {claim.reason && <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-ink md:line-clamp-none">{humanizeReason(claim.reason)}</p>}

      <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-ink-tertiary md:mt-2 md:text-xs">
        {firstSpan?.sourceSection}
        {firstSpan?.pageNumber != null ? ` · p. ${firstSpan.pageNumber}` : ""}
      </div>

      <button
        type="button"
        onClick={onViewEvidence}
        className={cn(
          "group mt-1.5 inline-flex md:hidden shrink-0 items-center gap-1 font-sans text-xs text-brand hover:text-brand-hover",
          isSelected && "underline"
        )}
      >
        View Evidence
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </button>
    </div>
  );
}
