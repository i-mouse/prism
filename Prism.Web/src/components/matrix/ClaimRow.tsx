import { ArrowRight } from "lucide-react";
import type { ClaimDto } from "@/types/api";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import { displayLabel, humanizeReason } from "@/lib/claim-display";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { VerdictPill, verdictBorderClass } from "@/components/VerdictPill";
import { cn } from "@/lib/utils";

interface ClaimRowProps {
  claim: ClaimDto;
  onViewEvidence: () => void;
}

export function ClaimRow({ claim, onViewEvidence }: ClaimRowProps) {
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
      <div className={cn("absolute top-0 left-0 h-full w-1", verdictBorderClass[verdict])} />

      <div className="flex items-start gap-4">
        <div className="pt-0.5 font-sans text-base font-semibold text-ink w-6 shrink-0 text-center pl-1.5">{claim.position}</div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4">
            <VerdictPill verdict={verdict} className="hidden md:inline-flex" />
            <VerdictPill verdict={verdict} size="sm" className="md:hidden" />
            
            <button
              type="button"
              onClick={onViewEvidence}
              className={cn(
                "group hidden md:inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 bg-surface border border-hairline font-sans text-sm text-brand hover:border-brand-subtle transition-colors hover:text-brand-hover",
                isSelected && "border-brand-subtle bg-brand-subtle text-brand"
              )}
            >
              View Evidence
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </button>
          </div>

          <div className="mt-3 line-clamp-2 font-sans text-sm md:text-base font-medium leading-snug text-ink md:line-clamp-none md:leading-normal">{claim.claimSummary}</div>

          {firstSpan && (
            <blockquote className="mt-2 line-clamp-1 border-l-[2px] border-hairline pl-3 font-sans text-xs md:mt-3 md:line-clamp-none md:text-sm text-ink-secondary italic">
              &ldquo;{firstSpan.sourceText}&rdquo;
            </blockquote>
          )}

          <div className="mt-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-tertiary md:mt-3 md:text-xs">
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            {firstSpan?.sourceSection}
            {firstSpan?.pageNumber != null ? ` · Page ${firstSpan.pageNumber}` : ""}
          </div>

          {claim.groundingStatus === "Partial" && claim.reason && (
            <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-verdict-partial-text md:line-clamp-none">{humanizeReason(claim.reason)}</p>
          )}

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
      </div>
    </div>
  );
}
