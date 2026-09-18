import { ArrowRight } from "lucide-react";
import type { ClaimDto } from "@/types/api";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import { displayLabel } from "@/lib/claim-display";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { VerdictPill } from "@/components/VerdictPill";
import { cn } from "@/lib/utils";

interface ClaimTableRowProps {
  claim: ClaimDto;
  onViewEvidence: () => void;
}

export function ClaimTableRow({ claim, onViewEvidence }: ClaimTableRowProps) {
  const verdict = claimLabelToVerdict[displayLabel(claim)];
  const { selectedClaimId } = useSelectedClaim();
  const isSelected = selectedClaimId === claim.id;

  return (
    <div
      onClick={onViewEvidence}
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_160px_140px] gap-6 items-center p-4 border-b border-slate-100 cursor-pointer transition-colors duration-100 group",
        isSelected ? "bg-slate-50" : "hover:bg-slate-50"
      )}
    >
      <div className="min-w-0 pr-4 text-slate-800 text-sm">
        <p className={cn("line-clamp-2 leading-snug", isSelected && "font-medium")}>
          {claim.claimSummary}
        </p>
        {claim.missing && (
          <p className="mt-0.5 text-[11px] text-red-600">
            No supporting evidence found
          </p>
        )}
      </div>
      <div className="flex justify-start">
        <VerdictPill verdict={verdict} size="sm" />
      </div>
      <div>
        <span className={cn("text-slate-500 hover:text-slate-800 font-medium text-sm no-underline flex items-center justify-end gap-1", isSelected && "text-slate-800")}>
          View evidence <ArrowRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </div>
  );
}
