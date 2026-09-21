import { useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Upload, ChevronDown } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PaperHeader } from "@/components/matrix/PaperHeader";
import { ClaimList } from "@/components/matrix/ClaimList";
import { AuditSummaryCard } from "@/components/matrix/AuditSummaryCard";
import { PaperActivityView } from "@/components/matrix/PaperActivityView";
import { PaperChatStrip } from "@/components/matrix/PaperChatStrip";
import { useAuth } from "@/lib/AuthContext";
import { useNavigate } from "react-router-dom";
import type { ClaimDto, ClaimLabel, PaperClaimsResponse } from "@/types/api";
import { displayLabel } from "@/lib/claim-display";

interface MatrixViewProps {
  paperClaims: PaperClaimsResponse | null;
  isLoading: boolean;
  activePaperId: string | null;
  activeChatId: string;
  pendingUpload?: { chatId: string; fileName: string } | null;
  cacheHitPending?: boolean;
  onCacheHitResolved?: () => void;
  onCacheHitCancel?: () => void;
  onViewEvidence: (claimId: string) => void;
  onUploadClick: () => void;
  isGoogleUser?: boolean;
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

// ── User profile pill rendered in the top-right corner of the main content ──
function UserProfileButton() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const isGuest = user?.provider === "guest";
  const displayName = isGuest ? "Guest" : (user?.name ?? "User");
  const initial = displayName[0]?.toUpperCase() ?? "?";

  const handleSignOut = async () => {
    await signOut();
    navigate("/login");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex h-9 items-center gap-2 rounded-lg border border-hairline bg-surface px-2.5 shadow-sm transition-colors hover:bg-surface-subtle outline-none">
          {/* Avatar circle */}
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink font-sans text-xs font-semibold text-white">
            {initial}
          </div>
          <span className="hidden font-sans text-sm font-medium text-ink-secondary md:block">
            {displayName}
          </span>
          <ChevronDown className="h-3.5 w-3.5 text-ink-tertiary" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {isGuest && (
          <DropdownMenuItem onSelect={() => navigate("/login")}>
            Sign in
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onSelect={handleSignOut}>Sign out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
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
}: MatrixViewProps) {
  const [sortMode, setSortMode] = useState<SortMode>("position");
  // Survives PaperChatStrip's per-chat remount (key={activeChatId}) because
  // MatrixView itself never remounts on paper switch (no key at its own call
  // site in AppShell.tsx) - a ref here, not state, so a scroll event doesn't
  // trigger a re-render of this whole view.
  const chatScrollPositionsRef = useRef<Map<string, number>>(new Map());
  // usePaperClaims doesn't null its data just because activePaperId changed
  // (that re-triggers the full-page skeleton below - see usePaperClaims.ts)
  // so `paperClaims` can briefly still be the PREVIOUS paper's response
  // after a switch. Every display value below is derived from this
  // paper-matched view instead of raw `paperClaims`, so a switch renders an
  // honest brief "0 claims" rather than the previous paper's claims under
  // the new paper's identity. `showSkeleton`/`showActivityView` further
  // below intentionally keep reading raw `paperClaims` - its mere presence,
  // not which paper it's for, is what should decide whether to show the
  // skeleton, or that regresses right back to a full remount every switch.
  const currentPaperClaims = paperClaims?.paperId === activePaperId ? paperClaims : null;
  const claims = currentPaperClaims?.claims ?? [];

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

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!activePaperId && !pendingUpload) {
    return (
      <div className="flex h-full flex-col">
        {/* Top-right user profile — visible even on empty state */}
        <div className="flex shrink-0 items-center justify-end px-4 py-3 md:px-6">
          <UserProfileButton />
        </div>

        <div className="flex flex-1 flex-col items-center justify-center gap-12 px-4 pb-8 md:px-6">
          <div className="w-full max-w-2xl">
            {/* Drop zone */}
            <div
              className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 p-8 md:p-12 transition-all duration-200 hover:border-slate-400 hover:bg-slate-50 group"
              onClick={onUploadClick}
            >
              <Upload className="h-12 w-12 text-slate-300 transition-colors group-hover:text-slate-500" strokeWidth={1.5} />
              <h1 className="mt-4 font-sans text-2xl font-semibold text-ink">
                Drop a research paper
              </h1>
              <p className="mt-2 font-mono text-xs text-ink-tertiary">
                PDF · up to 50MB · no account needed
              </p>
            </div>

            {/* How it works — desktop */}
            <div className="mt-12 hidden md:grid grid-cols-3 gap-4 relative">
              <div className="absolute top-8 left-1/6 right-1/6 h-px border-t border-dashed border-hairline z-0" />
              {[
                { n: 1, label: "Extractor", sub: "Pulls every claim from the paper.", color: "bg-slate-700" },
                { n: 2, label: "Auditor", sub: "Reasons against the paper's own text.", color: "bg-verdict-supported-icon" },
                { n: 3, label: "Verdict", sub: "Refuses to affirm what isn't supported.", color: "bg-verdict-refused-icon" },
              ].map(({ n, label, sub, color }) => (
                <div key={n} className="relative z-10 flex flex-col items-center rounded-xl border border-hairline bg-surface p-5 text-center">
                  <div className={`flex h-6 w-6 items-center justify-center rounded-full ${color} font-mono text-xs text-white`}>{n}</div>
                  <div className="mt-3 font-sans text-sm font-semibold text-ink">{label}</div>
                  <div className="mt-1 font-sans text-xs text-ink-secondary">{sub}</div>
                </div>
              ))}
            </div>

            {/* How it works — mobile */}
            <div className="mt-8 flex flex-col gap-3 md:hidden">
              {[
                { n: 1, label: "Extractor", sub: "Pulls every claim from the paper.", color: "bg-slate-700" },
                { n: 2, label: "Auditor", sub: "Reasons against the paper's own text.", color: "bg-verdict-supported-icon" },
                { n: 3, label: "Verdict", sub: "Refuses to affirm what isn't supported.", color: "bg-verdict-refused-icon" },
              ].map(({ n, label, sub, color }) => (
                <div key={n} className="flex items-center gap-4 rounded-xl border border-hairline bg-surface p-4">
                  <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${color} font-mono text-xs text-white`}>{n}</div>
                  <div>
                    <div className="font-sans text-sm font-semibold text-ink">{label}</div>
                    <div className="font-sans text-xs text-ink-secondary">{sub}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Metric footer */}
            <div className="mt-12 text-center">
              <p className="font-sans text-sm text-ink-secondary">
                <span className="font-mono font-semibold text-base text-slate-800">10 of 14</span>{" "}
                correct refusals on adversarial test cases
              </p>
              <a
                href="https://github.com/i-mouse/prism#eval"
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 font-sans text-xs text-slate-500 hover:text-slate-700"
              >
                See the eval →
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const isCacheHitLoading = cacheHitPending && !paperClaims;
  const showSkeleton =
    (!pendingUpload && !paperClaims && !isCacheHitLoading) ||
    (isLoading && !paperClaims && !isCacheHitLoading);
  const showActivityView =
    pendingUpload ||
    isCacheHitLoading ||
    (paperClaims && (paperClaims.extractionStatus !== "Completed" || cacheHitPending));

  if (showSkeleton) {
    return (
      <div className="h-full overflow-y-auto px-4 py-6 md:px-8">
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
            extractionStatus={(!paperClaims || cacheHitPending) ? "In progress" : paperClaims.extractionStatus}
            isCacheHitPending={cacheHitPending}
            isGoogleUser={isGoogleUser}
            onCacheHitContinue={onCacheHitResolved}
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
          {/* ── Top bar: paper header + user profile ── */}
          <div className="shrink-0 px-4 pt-4 pb-3 md:px-6 md:pt-5">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                <PaperHeader
                  fileName={currentPaperClaims?.fileName ?? "Loading paper…"}
                  extractionStatus={currentPaperClaims?.extractionStatus ?? "In progress"}
                  completedAt={currentPaperClaims?.completedAt ?? null}
                />
              </div>
              {/* User profile — top right of main content area */}
              <div className="shrink-0 hidden md:flex items-center">
                <UserProfileButton />
              </div>
            </div>
          </div>

          {/* ── Scrollable content region ── */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {/* Audit Summary Card — elevated card on the paper canvas */}
            <div className="px-4 pb-4 md:px-6">
              <AuditSummaryCard summary={derivedSummary} />
            </div>

            {/* Claims table — wrapped in a card for elevation */}
            <div className="px-4 pb-6 md:px-6">
              <div className="rounded-xl border border-hairline bg-surface shadow-card overflow-hidden">
                <ClaimList
                  paperId={activePaperId}
                  claims={sortedClaims}
                  onViewEvidence={onViewEvidence}
                  sortControl={
                    <Select value={sortMode} onValueChange={(v) => setSortMode(v as SortMode)}>
                      <SelectTrigger className="gap-1 rounded-lg border-hairline bg-surface px-2 py-1 font-sans text-xs text-ink-secondary hover:border-hairline-strong focus-visible:ring-2 focus-visible:ring-ink/20 md:px-3 md:py-1.5 md:text-sm lg:!h-8">
                        <span className="text-ink-tertiary">Sort by:</span>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="position" className="focus:bg-surface-subtle focus:text-ink">
                          Claim number (asc)
                        </SelectItem>
                        <SelectItem value="support" className="focus:bg-surface-subtle focus:text-ink">
                          Support level
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  }
                />
              </div>
            </div>
          </div>

          {/* ── Floating chat input — pinned to bottom ── */}
          {activePaperId && (
            <>
              <div className="shrink-0 border-t border-slate-100 bg-slate-50">
                <PaperChatStrip
                  key={activeChatId}
                  chatId={activeChatId}
                  activeFileId={activePaperId}
                  fileName={currentPaperClaims?.fileName}
                  paperClaims={claims}
                  scrollPositions={chatScrollPositionsRef}
                />
              </div>
            </>
          )}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function MatrixSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-24 w-full rounded-xl" />
      <Skeleton className="h-28 w-full rounded-xl" />
      <div className="space-y-2">
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-12 w-full rounded-lg" />
      </div>
    </div>
  );
}
