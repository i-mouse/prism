import { X, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { EvidenceCard } from "@/components/drawer/EvidenceCard";
import { claimLabelMeta } from "@/lib/claimMeta";
import { displayLabel } from "@/lib/claim-display";
import { cn } from "@/lib/utils";
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

  const linkedMeta = claim ? claimLabelMeta[displayLabel(claim)] : null;

  return (
    <aside className="flex h-full w-[400px] shrink-0 flex-col border-l border-border bg-surface p-6 shadow-drawer">
      <div className="flex items-center justify-between border-b border-border pb-6">
        <h2 className="font-display text-base font-semibold text-ink">Evidence</h2>
        <Button variant="ghost" size="icon-sm" onClick={() => setSelectedClaimId(null)} aria-label="Close">
          <X className="h-4 w-4 text-ink-muted" />
        </Button>
      </div>

      {claim && (
        <div key={claim.id} className="animate-prism-fade-in flex flex-1 flex-col overflow-y-auto">
          <div className="mt-6 flex items-center justify-between gap-3">
            <span className="truncate text-sm text-ink">{paperClaims?.fileName}</span>
            <button
              type="button"
              onClick={openPaper}
              className="group inline-flex shrink-0 items-center gap-1 text-sm font-medium text-ink-muted underline-offset-4 transition-colors duration-quick ease-smooth hover:text-ink hover:underline"
            >
              Open Paper
              <ExternalLink className="h-4 w-4 opacity-0 transition-opacity duration-quick ease-smooth group-hover:opacity-100" />
            </button>
          </div>

          <div className="mt-6 text-xs font-semibold uppercase tracking-[0.05em] text-ink-subtle">
            Source
          </div>

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
            <div className="space-y-3 rounded-md border border-border bg-surface p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.05em] text-ink-subtle">
                Linked to Claim
              </p>
              <p className="text-sm text-ink">{claim.claimSummary}</p>
              {linkedMeta && (
                <span
                  className={cn(
                    "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-semibold uppercase tracking-wider",
                    linkedMeta.bgClass,
                    linkedMeta.textClass
                  )}
                >
                  <linkedMeta.Icon className="h-3.5 w-3.5" />
                  {linkedMeta.text}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
