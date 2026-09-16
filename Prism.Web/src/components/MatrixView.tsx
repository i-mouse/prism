import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Upload } from "lucide-react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PaperHeader } from "@/components/matrix/PaperHeader";
import { ClaimList } from "@/components/matrix/ClaimList";
import { SummaryStrip } from "@/components/matrix/SummaryStrip";
import { cn } from "@/lib/utils";
import { PaperActivityView } from "@/components/matrix/PaperActivityView";
import { PaperChatStrip } from "@/components/matrix/PaperChatStrip";
import { acquireAccessToken } from "@/lib/auth";
import type { ClaimDto, ClaimLabel, PaperClaimsResponse } from "@/types/api";
import { displayLabel } from "@/lib/claim-display";

interface MatrixViewProps {
  paperClaims: PaperClaimsResponse | null;
  isLoading: boolean;
  activePaperId: string | null;
  activeChatId: string;
  // Set from just after an upload starts until the real fileId comes back —
  // lets the activity log mount and start listening before that HTTP round
  // trip resolves instead of missing the earliest progress messages.
  pendingUpload?: { chatId: string; fileName: string } | null;
  // True while a cache-hit paper's inline Continue/Re-run decision hasn't
  // been resolved yet — keeps the activity view showing even though
  // paperClaims already reports "Completed" for a previously-audited paper.
  cacheHitPending?: boolean;
  onCacheHitResolved?: () => void;
  // Guests see Cancel instead of Re-run on the inline decision — resets
  // the view back to the upload dropzone so a different file can be picked.
  onCacheHitCancel?: () => void;
  onViewEvidence: (claimId: string) => void;
  onUploadClick: () => void;
  // Re-run (Google-authenticated users only, never guests) — isGoogleUser gates
  // the banner in PaperHeader, getConnectionId supplies the SignalR connection
  // the re-triggered pipeline reports progress back to.
  isGoogleUser?: boolean;
  getConnectionId?: () => string | null;
}

type SortMode = "position" | "support";

const labelPriority: Record<ClaimLabel, number> = {
  not_supported: 0,
  partially_supported: 1,
  supported: 2,
};

function sortBySupport(a: ClaimDto, b: ClaimDto) {
  const aP = labelPriority[displayLabel(a)];
  const bP = labelPriority[displayLabel(b)];
  if (aP !== bP) return aP - bP;
  return a.position - b.position;
}

export function MatrixView({
  paperClaims,
  isLoading,
  activePaperId,
  activeChatId,
  pendingUpload = null,
  cacheHitPending = false,
  onCacheHitResolved,
  onCacheHitCancel,
  onViewEvidence,
  onUploadClick,
  isGoogleUser = false,
  getConnectionId,
}: MatrixViewProps) {
  const [sortMode, setSortMode] = useState<SortMode>("position");
  const [activeTab, setActiveTab] = useState<"claims" | "overview">("claims");
  const [isRerunning, setIsRerunning] = useState(false);
  const claims = paperClaims?.claims ?? [];

  // Cleared whenever the claims payload's completedAt changes — that happens
  // both on first load and, meaningfully, once a re-run finishes and produces
  // a fresh extraction run (a new completedAt timestamp).
  useEffect(() => {
    setIsRerunning(false);
  }, [paperClaims?.completedAt]);

  const handleRerun = async () => {
    if (!activePaperId) return;
    const connectionId = getConnectionId?.();
    if (!connectionId) {
      toast.error("Realtime connection not ready. Please wait a moment and try again.");
      return;
    }
    setIsRerunning(true);
    try {
      const headers: HeadersInit = { "Content-Type": "application/json" };
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`/api/papers/${activePaperId}/rerun`, {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify({ chatId: activeChatId, connectionId }),
      });
      if (!res.ok) {
        const message = await res.text().catch(() => "");
        throw new Error(message || `Re-run failed: ${res.statusText}`);
      }
    } catch (err) {
      console.error("Re-run error:", err);
      toast.error("Re-run failed to start. Please try again.");
      setIsRerunning(false);
    }
  };

  // Wraps handleRerun for the inline cache-hit decision block: resolving the
  // decision immediately is safe here because isRerunning flips to true in
  // the same call, so the activity view keeps showing without a flicker.
  const handleCacheHitRerun = async () => {
    onCacheHitResolved?.();
    await handleRerun();
  };

  const sortedClaims = useMemo(() => {
    if (sortMode === "support") {
      return [...claims].sort(sortBySupport);
    }
    return [...claims].sort((a, b) => a.position - b.position);
  }, [claims, sortMode]);

  const derivedSummary = useMemo(() => {
    const labels = claims.map(displayLabel);
    return {
      total: claims.length,
      supported: labels.filter((l) => l === "supported").length,
      partiallySupported: labels.filter((l) => l === "partially_supported").length,
      notSupported: labels.filter((l) => l === "not_supported").length,
    };
  }, [claims]);

  if (!activePaperId && !pendingUpload) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-12 px-4 py-8 md:px-6 lg:py-16">
        <div className="w-full max-w-2xl">
          {/* Zone A — HERO DROP ZONE */}
          <div 
            className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-hairline p-8 md:p-12 transition-all duration-200 hover:border-brand hover:bg-brand-subtle group"
            onClick={onUploadClick}
          >
            <Upload className="h-12 w-12 text-ink-tertiary transition-colors group-hover:text-brand" strokeWidth={1.5} />
            <h1 className="mt-4 font-sans text-2xl font-semibold text-ink">
              Drop a research paper
            </h1>
            <p className="mt-2 font-mono text-xs text-ink-tertiary">
              PDF · up to 50MB · no account needed
            </p>
          </div>

          {/* Zone B — HOW IT WORKS STRIP */}
          <div className="mt-12 hidden md:grid grid-cols-3 gap-4 relative">
            {/* Desktop Connector Line */}
            <div className="absolute top-8 left-1/6 right-1/6 h-px border-t border-dashed border-hairline z-0" />
            
            <div className="relative z-10 flex flex-col items-center rounded-xl border border-hairline bg-surface p-5 text-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand font-mono text-xs text-white">1</div>
              <div className="mt-3 font-sans text-sm font-semibold text-ink">Extractor</div>
              <div className="mt-1 font-sans text-xs text-ink-secondary">Pulls every claim from the paper.</div>
            </div>
            
            <div className="relative z-10 flex flex-col items-center rounded-xl border border-hairline bg-surface p-5 text-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-verdict-supported-icon font-mono text-xs text-white">2</div>
              <div className="mt-3 font-sans text-sm font-semibold text-ink">Auditor</div>
              <div className="mt-1 font-sans text-xs text-ink-secondary">Reasons against the paper's own text.</div>
            </div>

            <div className="relative z-10 flex flex-col items-center rounded-xl border border-hairline bg-surface p-5 text-center">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-verdict-refused-icon font-mono text-xs text-white">3</div>
              <div className="mt-3 font-sans text-sm font-semibold text-ink">Verdict</div>
              <div className="mt-1 font-sans text-xs text-ink-secondary">Refuses to affirm what isn't supported.</div>
            </div>
          </div>

          {/* Mobile How It Works Strip */}
          <div className="mt-8 flex flex-col gap-3 md:hidden">
            <div className="flex items-center gap-4 rounded-xl border border-hairline bg-surface p-4">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand font-mono text-xs text-white">1</div>
              <div>
                <div className="font-sans text-sm font-semibold text-ink">Extractor</div>
                <div className="font-sans text-xs text-ink-secondary">Pulls every claim from the paper.</div>
              </div>
            </div>
            <div className="flex items-center gap-4 rounded-xl border border-hairline bg-surface p-4">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-verdict-supported-icon font-mono text-xs text-white">2</div>
              <div>
                <div className="font-sans text-sm font-semibold text-ink">Auditor</div>
                <div className="font-sans text-xs text-ink-secondary">Reasons against the paper's own text.</div>
              </div>
            </div>
            <div className="flex items-center gap-4 rounded-xl border border-hairline bg-surface p-4">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-verdict-refused-icon font-mono text-xs text-white">3</div>
              <div>
                <div className="font-sans text-sm font-semibold text-ink">Verdict</div>
                <div className="font-sans text-xs text-ink-secondary">Refuses to affirm what isn't supported.</div>
              </div>
            </div>
          </div>

          {/* Zone C — METRIC FOOTER */}
          <div className="mt-12 text-center">
            <p className="font-sans text-sm text-ink-secondary">
              <span className="font-mono gradient-brand font-semibold text-base">10 of 14</span> correct refusals on adversarial test cases
            </p>
            <a 
              href="https://github.com/i-mouse/prism#eval" 
              target="_blank" 
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1 font-sans text-xs text-brand hover:text-brand-hover"
            >
              See the eval →
            </a>
          </div>
        </div>
      </div>
    );
  }

  const isCacheHitLoading = cacheHitPending && !paperClaims;
  const showSkeleton = (!pendingUpload && !paperClaims && !isCacheHitLoading) || (isLoading && !paperClaims && !isCacheHitLoading);
  const showActivityView = pendingUpload || isCacheHitLoading || (paperClaims && (paperClaims.extractionStatus !== "Completed" || isRerunning || cacheHitPending));

  if (showSkeleton) {
    return (
      <div className="h-full overflow-y-auto px-8 py-6">
        <MatrixSkeleton />
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      {showActivityView ? (
        <motion.div
          key="activity"
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.2 }}
          className="h-full overflow-y-auto"
        >
          <PaperActivityView
            key={activeChatId}
            fileId={activePaperId}
            chatId={pendingUpload?.chatId || activeChatId}
            fileName={pendingUpload?.fileName || paperClaims?.fileName || ""}
            extractionStatus={(!paperClaims || isRerunning || cacheHitPending) ? "In progress" : paperClaims.extractionStatus}
            isCacheHitPending={cacheHitPending}
            isGoogleUser={isGoogleUser}
            onCacheHitContinue={onCacheHitResolved}
            onCacheHitRerun={handleCacheHitRerun}
            onCacheHitCancel={onCacheHitCancel}
          />
        </motion.div>
      ) : paperClaims ? (
        <motion.div
          key="matrix"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="flex h-full min-h-0 flex-col"
        >
          <div className="shrink-0 px-3 py-3 md:px-8 md:pt-4 md:pb-0">
            <PaperHeader
              fileName={paperClaims.fileName}
              extractionStatus={paperClaims.extractionStatus}
              completedAt={paperClaims.completedAt}
              showRerun={isGoogleUser && paperClaims.extractionStatus === "Completed" && paperClaims.promptVersion != null}
              isCurrentPromptVersion={paperClaims.isCurrentPromptVersion}
              onRerun={handleRerun}
              rerunning={isRerunning}
            />

            <div className="mt-6 flex items-center gap-6 border-b border-hairline px-1">
              <button 
                onClick={() => setActiveTab("claims")}
                className={cn(
                  "relative flex items-center gap-2 pb-3 font-sans text-sm font-semibold",
                  activeTab === "claims" ? "text-brand" : "text-ink-secondary hover:text-ink"
                )}
              >
                Claims
                <span className={cn(
                  "flex h-5 items-center justify-center rounded-full px-2 font-mono text-xs font-semibold",
                  activeTab === "claims" ? "bg-brand-subtle text-brand" : "bg-surface-subtle text-ink-tertiary"
                )}>
                  {claims.length}
                </span>
                {activeTab === "claims" && <div className="absolute -bottom-px left-0 right-0 h-0.5 bg-brand" />}
              </button>
              <button 
                onClick={() => setActiveTab("overview")}
                className={cn(
                  "relative pb-3 font-sans text-sm font-semibold",
                  activeTab === "overview" ? "text-brand" : "text-ink-secondary hover:text-ink"
                )}
              >
                Overview
                {activeTab === "overview" && <div className="absolute -bottom-px left-0 right-0 h-0.5 bg-brand" />}
              </button>
            </div>

            {activeTab === "claims" && (
              <div className="mb-2 flex items-center justify-end gap-3 py-3 md:mb-3">
                <Select value={sortMode} onValueChange={(v) => setSortMode(v as SortMode)}>
                  <SelectTrigger
                    className="gap-1 rounded-lg border-hairline bg-surface px-2 py-1 font-sans text-xs text-ink hover:border-hairline-strong focus-visible:ring-2 focus-visible:ring-brand-subtle md:px-3 md:py-1.5 md:text-sm lg:!h-8"
                  >
                    <span className="text-ink-tertiary">Sort:</span>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="position" className="focus:bg-surface-subtle focus:text-ink">
                      Position
                    </SelectItem>
                    <SelectItem value="support" className="focus:bg-surface-subtle focus:text-ink">
                      Support
                    </SelectItem>
                    <SelectItem
                      value="section"
                      disabled
                      className="cursor-not-allowed opacity-50 focus:bg-surface-subtle focus:text-ink"
                    >
                      Section
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            
            {activeTab === "overview" && (
              <div className="mb-2 py-3 md:mb-3" />
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-24 pt-2 md:px-8 lg:pb-6">
            {activeTab === "claims" ? (
              <ClaimList claims={sortedClaims} onViewEvidence={onViewEvidence} />
            ) : (
              <SummaryStrip summary={derivedSummary} />
            )}
          </div>

          {activePaperId && <PaperChatStrip key={activeChatId} chatId={activeChatId} activeFileId={activePaperId} />}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}



function MatrixSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-32 w-full rounded-lg" />
      <Skeleton className="h-20 w-full rounded-lg" />
      <div className="space-y-3">
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>
    </div>
  );
}
