import { X, ExternalLink, Quote } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { claimLabelToVerdict } from "@/lib/claimMeta";
import { displayLabel } from "@/lib/claim-display";
import { VerdictPill } from "@/components/VerdictPill";
import type { PaperClaimsResponse } from "@/types/api";
import { cn } from "@/lib/utils";

interface EvidenceDrawerProps {
  paperClaims: PaperClaimsResponse | null;
  onClose?: () => void;
}

export function EvidenceDrawer({ paperClaims, onClose }: EvidenceDrawerProps) {
  const { selectedClaimId, setSelectedClaimId } = useSelectedClaim();
  const allClaims = paperClaims?.claims ?? [];
  const claimIndex = allClaims.findIndex((c) => c.id === selectedClaimId);
  const claim = claimIndex >= 0 ? allClaims[claimIndex] : null;
  const claimPosition = claim ? claim.position : claimIndex + 1;
  const firstSpan = claim?.evidenceSpans[0];

  const openPaper = (e: React.MouseEvent) => {
    e.preventDefault();
    toast("Opening PDFs is coming soon");
  };

  const handleClose = () => {
    if (onClose) onClose();
    else setSelectedClaimId(null);
  };

  return (
    <aside className="flex h-full w-full lg:w-[400px] shrink-0 flex-col bg-surface lg:border-l border-hairline shadow-drawer">
      {/* ── Header ──────────────────────────────────── */}
      <div className="flex shrink-0 items-center justify-between px-5 py-4 border-b border-hairline">
        <span className="font-sans text-sm font-semibold text-ink">
          {claim ? `Claim ${claimPosition}` : "Evidence"}
        </span>
        <Button variant="ghost" size="icon-sm" onClick={handleClose} aria-label="Close">
          <X className="h-4 w-4 text-ink-tertiary" />
        </Button>
      </div>

      {claim ? (
        <div key={claim.id} className="flex flex-1 flex-col overflow-y-auto px-5 pb-6">
          {/* ── Claim text ──────────────────────────── */}
          <h2 className="mt-5 font-sans text-xl font-bold leading-snug text-ink">
            {claim.claimSummary}
          </h2>

          {/* ── Status badge + page ──────────────────── */}
          <div className="mt-3 flex items-center gap-3">
            <VerdictPill verdict={claimLabelToVerdict[displayLabel(claim)]} />
            {firstSpan?.pageNumber != null && (
              <span className="font-sans text-sm text-ink-secondary">
                Page {firstSpan.pageNumber}
              </span>
            )}
          </div>

          {/* ── Claim summary ────────────────────────── */}
          {claim.claimSummary !== claim.claimTextVerbatim && claim.claimTextVerbatim && (
            <section className="mt-6">
              <h3 className="font-sans text-sm font-semibold text-ink">Claim summary</h3>
              <p className="mt-2 font-sans text-sm leading-relaxed text-ink-secondary">
                The paper claims that {claim.claimSummary.charAt(0).toLowerCase() + claim.claimSummary.slice(1)}
              </p>
            </section>
          )}

          {/* ── Evidence from the paper ──────────────── */}
          {firstSpan && (
            <section className="mt-6">
              <h3 className="font-sans text-sm font-semibold text-ink">Evidence from the paper</h3>
              <div className="mt-2 rounded-xl bg-surface-subtle border border-hairline p-4 relative">
                {/* Decorative quote mark */}
                <Quote className="absolute top-3 left-3 h-5 w-5 text-brand opacity-40" strokeWidth={1.5} />
                <p className="pl-6 font-sans text-sm leading-relaxed text-ink-secondary italic">
                  {firstSpan.sourceText}
                </p>
                {firstSpan.pageNumber != null && (
                  <p className="mt-2 pl-6 font-sans text-xs text-ink-tertiary">
                    Page {firstSpan.pageNumber}
                    {firstSpan.sourceSection && ` · ${firstSpan.sourceSection}`}
                  </p>
                )}
              </div>

              {/* Additional spans if present */}
              {claim.evidenceSpans.slice(1).map((span, idx) => (
                <div
                  key={idx}
                  className="mt-2 rounded-xl bg-surface-subtle border border-hairline p-4 relative"
                >
                  <Quote className="absolute top-3 left-3 h-5 w-5 text-brand opacity-40" strokeWidth={1.5} />
                  <p className="pl-6 font-sans text-sm leading-relaxed text-ink-secondary italic">
                    {span.sourceText}
                  </p>
                  {span.pageNumber != null && (
                    <p className="mt-2 pl-6 font-sans text-xs text-ink-tertiary">
                      Page {span.pageNumber}
                      {span.sourceSection && ` · ${span.sourceSection}`}
                    </p>
                  )}
                </div>
              ))}
            </section>
          )}

          {/* ── No evidence note ─────────────────────── */}
          {claim.missing && (
            <div className="mt-4 rounded-lg border border-verdict-refused-border/30 bg-verdict-refused-bg p-3 font-sans text-sm text-verdict-refused-text">
              The auditor considered available passages but found none sufficient to support this claim.
            </div>
          )}

          {/* ── Why this supports the claim ──────────── */}
          {claim.reason && (
            <section className="mt-6">
              <h3 className="font-sans text-sm font-semibold text-ink">
                Why this{" "}
                {displayLabel(claim) === "not_supported"
                  ? "doesn't support"
                  : displayLabel(claim) === "partially_supported"
                    ? "partially supports"
                    : "supports"}{" "}
                the claim
              </h3>
              <p className="mt-2 font-sans text-sm leading-relaxed text-ink-secondary">
                {claim.reason}
              </p>
            </section>
          )}

          {/* ── Footer: View in document ─────────────── */}
          <div className="mt-auto pt-8">
            <Button
              variant="outline"
              onClick={openPaper}
              className={cn(
                "w-full gap-2 rounded-lg border border-hairline bg-surface font-sans text-sm text-ink",
                "hover:border-hairline-strong hover:bg-surface-subtle transition-colors"
              )}
            >
              View in document
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center px-5">
          <p className="font-sans text-sm text-ink-tertiary">
            Select a claim to view its evidence.
          </p>
        </div>
      )}
    </aside>
  );
}
