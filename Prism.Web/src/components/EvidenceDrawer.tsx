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
}

export function EvidenceDrawer({ paperClaims }: EvidenceDrawerProps) {
  const { selectedClaimId, setSelectedClaimId } = useSelectedClaim();
  const claim = paperClaims?.claims.find((c) => c.id === selectedClaimId) ?? null;

  const openPaper = (e: React.MouseEvent) => {
    e.preventDefault();
    toast("Opening PDFs is coming soon");
  };

  return (
    <aside className="flex h-full w-[400px] shrink-0 flex-col border-l border-hairline bg-surface p-6 shadow-drawer">
      <div className="flex items-center justify-between border-b border-hairline pb-6">
        <h2 className="font-sans text-lg font-semibold text-ink">Evidence</h2>
        <Button variant="ghost" size="icon-sm" onClick={() => setSelectedClaimId(null)} aria-label="Close">
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

          <div className="mt-6 font-sans text-xs uppercase tracking-wider text-ink-tertiary">Source</div>

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
            <div className="space-y-2 rounded-md border border-hairline bg-surface p-4">
              <p className="font-sans text-xs uppercase tracking-wider text-ink-tertiary">Linked to Claim</p>
              <p className="text-sm text-ink">{claim.claimSummary}</p>
              <VerdictPill verdict={claimLabelToVerdict[displayLabel(claim)]} />
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
