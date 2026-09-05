import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, Upload } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PaperHeader } from "@/components/matrix/PaperHeader";
import { SummaryStrip } from "@/components/matrix/SummaryStrip";
import { ClaimList } from "@/components/matrix/ClaimList";
import { PaperActivityView } from "@/components/matrix/PaperActivityView";
import { PaperChatStrip } from "@/components/matrix/PaperChatStrip";
import { useOverviewCollapsed } from "@/hooks/useOverviewCollapsed";
import type { ClaimDto, ClaimLabel, PaperClaimsResponse } from "@/types/api";
import { displayLabel } from "@/lib/claim-display";

interface MatrixViewProps {
  paperClaims: PaperClaimsResponse | null;
  isLoading: boolean;
  activePaperId: string | null;
  activeChatId: string;
  onViewEvidence: (claimId: string) => void;
  onUploadClick: () => void;
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
  onViewEvidence,
  onUploadClick,
}: MatrixViewProps) {
  const [sortMode, setSortMode] = useState<SortMode>("position");
  const [overviewCollapsed, setOverviewCollapsed] = useOverviewCollapsed();

  const claims = paperClaims?.claims ?? [];

  const derivedSummary = useMemo(() => {
    const labels = claims.map(displayLabel);
    return {
      total: claims.length,
      supported: labels.filter((l) => l === "supported").length,
      partiallySupported: labels.filter((l) => l === "partially_supported").length,
      notSupported: labels.filter((l) => l === "not_supported").length,
    };
  }, [claims]);

  const sortedClaims = useMemo(() => {
    if (sortMode === "support") {
      return [...claims].sort(sortBySupport);
    }
    return [...claims].sort((a, b) => a.position - b.position);
  }, [claims, sortMode]);

  if (!activePaperId) {
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

  if (isLoading && !paperClaims) {
    return (
      <div className="h-full overflow-y-auto px-8 py-6">
        <MatrixSkeleton />
      </div>
    );
  }

  if (!paperClaims) {
    return (
      <div className="h-full overflow-y-auto px-8 py-6">
        <MatrixSkeleton />
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      {paperClaims.extractionStatus !== "Completed" ? (
        <motion.div
          key="activity"
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.2 }}
          className="h-full overflow-y-auto"
        >
          <PaperActivityView fileId={activePaperId} fileName={paperClaims.fileName} />
        </motion.div>
      ) : (
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
            />

            <div className="mt-3 flex items-center justify-between md:mt-4">
              <span className="font-sans text-xs uppercase tracking-wider text-ink-tertiary">
                Audit overview
              </span>
              <button
                type="button"
                onClick={() => setOverviewCollapsed(!overviewCollapsed)}
                aria-expanded={!overviewCollapsed}
                aria-controls="audit-overview-region"
                aria-label="Toggle audit overview"
                className="rounded-md bg-transparent p-1 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                {overviewCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
              </button>
            </div>

            <CollapsibleRegion id="audit-overview-region" collapsed={overviewCollapsed}>
              <div className="mt-2 md:mt-3">
                <SummaryStrip summary={derivedSummary} />
              </div>
            </CollapsibleRegion>

            <div className="mb-2 flex items-center justify-between border-b border-hairline py-2 md:mb-3 md:py-3">
              <span className="hidden font-sans text-xs text-ink-secondary sm:inline md:text-sm">
                {claims.length} {claims.length === 1 ? "claim" : "claims"}
              </span>
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
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-24 pt-2 md:px-8 lg:pb-6">
            <ClaimList claims={sortedClaims} onViewEvidence={onViewEvidence} />
          </div>

          <PaperChatStrip key={activeChatId} chatId={activeChatId} activeFileId={activePaperId} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Drives the collapse/expand height manually via rAF instead of a CSS
// `transition: max-height` — the latter reliably got stuck mid-transition
// (computed height pinned at 0) on this element in testing, so height is
// interpolated by hand every frame instead of trusting the CSS engine.
function CollapsibleRegion({ id, collapsed, children }: { id: string; collapsed: boolean; children: ReactNode }) {
  const outerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const isFirstRender = useRef(true);

  useEffect(() => {
    const outer = outerRef.current;
    const content = contentRef.current;
    if (!outer || !content) return;

    if (isFirstRender.current) {
      isFirstRender.current = false;
      outer.style.height = collapsed ? "0px" : "auto";
      return;
    }

    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);

    if (prefersReducedMotion()) {
      outer.style.height = collapsed ? "0px" : "auto";
      return;
    }

    const startHeight = outer.getBoundingClientRect().height;
    const targetHeight = collapsed ? 0 : content.getBoundingClientRect().height;
    const duration = 200;
    const start = performance.now();
    const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const h = startHeight + (targetHeight - startHeight) * easeOut(t);
      outer.style.height = `${h}px`;
      if (t < 1) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        outer.style.height = collapsed ? "0px" : "auto";
        rafRef.current = null;
      }
    };
    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [collapsed]);

  return (
    <div id={id} ref={outerRef} className="overflow-hidden" style={{ height: collapsed ? 0 : undefined }}>
      <div ref={contentRef}>{children}</div>
    </div>
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
