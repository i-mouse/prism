import { ArrowRight } from "lucide-react";
import type { ClaimDto } from "@/types/api";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import { claimEvidenceNote, displayLabel } from "@/lib/claim-display";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { VerdictPill } from "@/components/VerdictPill";
import { cn } from "@/lib/utils";

interface AbsenceRowProps {
  claim: ClaimDto;
  onViewEvidence: () => void;
}

export function AbsenceRow({ claim, onViewEvidence }: AbsenceRowProps) {
  const verdict = claimLabelToVerdict[displayLabel(claim)];
  const { selectedClaimId } = useSelectedClaim();
  const isSelected = selectedClaimId === claim.id;
  const note = claimEvidenceNote(claim);
  const noteIsRefusal = note.state !== "invalid" && note.state !== "check_incomplete";

  return (
    <div
      data-claim-id={claim.id}
      onClick={onViewEvidence}
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_190px_140px] gap-6 items-center px-4 py-5 border-b border-gray-200 cursor-pointer transition-colors duration-100 group",
        isSelected ? "bg-surface-subtle" : "hover:bg-surface-subtle"
      )}
    >
      <div className="min-w-0 pr-4 text-ink text-[15px] flex items-start gap-3">
        <span className="text-ink-tertiary font-mono text-xs mt-[4px] shrink-0 w-5 text-right select-none">{claim.position}.</span>
        <div className="flex-1 min-w-0">
          <p className={cn("line-clamp-2 leading-relaxed", isSelected && "font-medium")}>
            {claim.claimSummary}
          </p>
          {note.listText && (
            <p className={cn("mt-1 text-[11px]", noteIsRefusal ? "text-verdict-refused-text" : "text-ink-tertiary")}>
              {note.listText}
            </p>
          )}
        </div>
      </div>
      <div className="flex justify-start">
        <VerdictPill verdict={verdict} size="sm" />
      </div>
      <div>
        <span className={cn("text-ink-tertiary hover:text-ink font-medium text-sm no-underline flex items-center justify-end gap-1", isSelected && "text-ink")}>
          View evidence <ArrowRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </div>
  );
}
