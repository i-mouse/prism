import { X, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { EvidenceCard } from "@/components/drawer/EvidenceCard";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import { displayLabel } from "@/lib/claim-display";
import { VerdictPill } from "@/components/VerdictPill";
import type { PaperClaimsResponse } from "@/types/api";

interface EvidenceDrawerProps {
  paperClaims: PaperClaimsResponse | null;
  onClose?: () => void;
}

export function EvidenceDrawer({ paperClaims, onClose }: EvidenceDrawerProps) {
  const { selectedClaimId, setSelectedClaimId } = useSelectedClaim();
  const allClaims = paperClaims?.claims ?? [];
  const claimIndex = allClaims.findIndex((c) => c.id === selectedClaimId);
  const claim = claimIndex >= 0 ? allClaims[claimIndex] : null;

  const openPaper = (e: React.MouseEvent) => {
    e.preventDefault();
    toast("Opening PDFs is coming soon");
  };

  const handleClose = () => {
    if (onClose) onClose();
    else setSelectedClaimId(null);
  };

  return (
    <aside className="flex h-full w-full lg:w-[400px] shrink-0 flex-col lg:border-l border-hairline bg-surface p-4 md:p-6 shadow-drawer">
      <div className="flex items-center justify-between border-b border-hairline pb-4 md:pb-6">
        <h2 className="font-sans text-lg font-semibold text-ink">Evidence</h2>
        <Button variant="ghost" size="icon-sm" onClick={handleClose} aria-label="Close">
          <X className="h-4 w-4 text-ink-tertiary hover:text-ink" />
        </Button>
      </div>

      {claim && (
        <div key={claim.id} className="animate-prism-fade-in flex flex-1 flex-col overflow-y-auto">
          <div className="mt-6 flex items-center justify-between gap-3">
            <span className="truncate font-sans text-sm text-ink">{paperClaims?.fileName}</span>
            <button
              type="button"
              onClick={openPaper}
              className="group inline-flex shrink-0 items-center gap-1 font-sans text-sm text-brand hover:text-brand-hover"
            >
              Open Paper
              <ExternalLink className="h-3 w-3" />
            </button>
          </div>
          
          <p className="mt-8 text-base text-ink font-medium leading-snug">{claim.claimSummary}</p>
          
          <div className="mt-3 flex justify-end">
            <VerdictPill verdict={claimLabelToVerdict[displayLabel(claim)]} />
          </div>

          <div className="mt-8 font-sans text-xs uppercase tracking-wider text-ink-tertiary">SOURCES FROM PAPER</div>

          {claim.missing && (
            <div className="mt-3 rounded-md bg-refused-bg p-3 text-sm text-refused">
              The auditor considered these passages but rejected them as sufficient support.
            </div>
          )}

          <div className="mt-1 space-y-3">
            {claim.evidenceSpans.map((span, idx) => (
              <EvidenceCard key={idx} span={span} />
            ))}
          </div>

          <div className="mt-auto pt-6">
            <div className="rounded-md border border-hairline bg-surface p-4">
              <p className="mb-2 font-sans text-xs uppercase tracking-wider text-ink-tertiary">Linked to Claim</p>
              <div className="flex items-start gap-3">
                <p className="flex-1 min-w-0 text-sm text-ink">{claim.claimSummary}</p>
                <div className="flex shrink-0 items-start">
                  <VerdictPill verdict={claimLabelToVerdict[displayLabel(claim)]} className="md:hidden" size="sm" />
                  <VerdictPill verdict={claimLabelToVerdict[displayLabel(claim)]} className="hidden md:inline-flex" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
