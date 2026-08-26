import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileText } from "lucide-react";
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
import type { ClaimDto, ClaimLabel, PaperClaimsResponse } from "@/types/api";
import { displayLabel } from "@/lib/claim-display";

interface MatrixViewProps {
  paperClaims: PaperClaimsResponse | null;
  isLoading: boolean;
  activePaperId: string | null;
  activeChatId: string;
  onViewEvidence: (claimId: string) => void;
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
}: MatrixViewProps) {
  const [sortMode, setSortMode] = useState<SortMode>("position");

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
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <FileText className="h-12 w-12 text-ink-subtle" />
        <p className="text-sm text-ink-muted">
          Select a paper from the sidebar, or upload a paper to get started.
        </p>
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
          <div className="shrink-0 px-8 pt-6">
            <PaperHeader
              fileName={paperClaims.fileName}
              extractionStatus={paperClaims.extractionStatus}
              completedAt={paperClaims.completedAt}
            />

            <div className="mt-6">
              <SummaryStrip summary={derivedSummary} />
            </div>

            <div className="mt-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="font-display text-lg font-semibold text-ink">Claims</h2>
                <span className="inline-flex h-6 items-center rounded-full bg-surface-sunken px-2 text-xs font-medium tabular-nums text-ink-muted">
                  {derivedSummary.total} claims
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-ink-muted">Sort by:</span>
                <Select value={sortMode} onValueChange={(v) => setSortMode(v as SortMode)}>
                  <SelectTrigger size="sm" className="border-border text-sm text-ink hover:border-border-strong">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="position" className="focus:bg-surface-sunken focus:text-ink">
                      Position
                    </SelectItem>
                    <SelectItem value="support" className="focus:bg-surface-sunken focus:text-ink">
                      Support
                    </SelectItem>
                    <SelectItem
                      value="section"
                      disabled
                      className="cursor-not-allowed opacity-50 focus:bg-surface-sunken focus:text-ink"
                    >
                      Section
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-8 pb-6 pt-2">
            <ClaimList claims={sortedClaims} onViewEvidence={onViewEvidence} />
          </div>

          <PaperChatStrip key={activeChatId} chatId={activeChatId} activeFileId={activePaperId} />
        </motion.div>
      )}
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
