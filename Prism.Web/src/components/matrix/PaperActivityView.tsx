import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, XCircle } from "lucide-react";
import { useExtractionProgress } from "@/hooks/useSignalR";
import type { ExtractionStage } from "@/types/api";
import { cn } from "@/lib/utils";

interface PaperActivityViewProps {
  fileId: string;
  fileName: string;
}

const STAGE_ORDER: ExtractionStage[] = ["preparing", "extracting", "grounding", "finalizing", "done"];

const STAGE_LABELS: Record<ExtractionStage, string> = {
  preparing: "Preparing paper",
  extracting: "Extracting claims",
  grounding: "Auditing evidence",
  finalizing: "Finalizing",
  done: "Complete",
  failed: "Failed",
};

type RowStatus = "completed" | "current" | "pending" | "failed";

export function PaperActivityView({ fileId, fileName }: PaperActivityViewProps) {
  const progress = useExtractionProgress(fileId);

  const hasFailed = progress?.latestStage === "failed";
  const currentIndex = progress && !hasFailed ? STAGE_ORDER.indexOf(progress.latestStage) : 0;
  const failedIndex = hasFailed && progress.failedStage ? STAGE_ORDER.indexOf(progress.failedStage) : -1;

  const getStatus = (index: number): RowStatus => {
    if (hasFailed) {
      if (index === failedIndex) return "failed";
      return index < failedIndex || failedIndex === -1 ? "completed" : "pending";
    }
    if (index < currentIndex) return "completed";
    if (index === currentIndex) return "current";
    return "pending";
  };

  const headerDetail =
    progress?.latestStage === "preparing" && progress.latestDetail ? progress.latestDetail : null;

  const failedStageLabel = hasFailed && progress.failedStage ? STAGE_LABELS[progress.failedStage] : null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="relative min-h-full overflow-hidden bg-surface"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,_oklch(0.96_0.03_285)_0%,_transparent_55%)] opacity-40" />

      <div className="relative mx-auto flex max-w-2xl flex-col gap-10 px-8 pb-12 pt-16">
        {/* Zone 1: header */}
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-accent">AUDITING PAPER</p>
          <h1 className="font-display text-3xl font-bold tracking-[-0.02em] text-ink">{fileName}</h1>
          {headerDetail && <p className="mt-1 text-sm text-ink-muted">{headerDetail}</p>}
        </div>

        {/* Zone 2: process card */}
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.3, ease: [0.32, 0.72, 0, 1], delay: 0.1 }}
          className="rounded-xl border border-border bg-surface p-8 shadow-card"
        >
          <ol className="relative flex flex-col gap-6 pl-4">
            {STAGE_ORDER.map((stage, i) => {
              const status = getStatus(i);
              const isCurrent = status === "current";
              return (
                <StageRow
                  key={stage}
                  label={STAGE_LABELS[stage]}
                  status={status}
                  detail={isCurrent && stage !== "preparing" ? progress?.latestDetail : undefined}
                  completed={isCurrent && stage === "grounding" ? progress?.latestCompleted : undefined}
                  total={isCurrent && stage === "grounding" ? progress?.latestTotal : undefined}
                  isLast={i === STAGE_ORDER.length - 1}
                />
              );
            })}
          </ol>
        </motion.div>

        {/* Zone 3: insight footer */}
        {progress?.finalizingSummary ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-center text-sm tabular-nums text-ink-muted"
          >
            {progress.finalizingSummary}
          </motion.div>
        ) : (
          <div className="text-center text-xs text-ink-subtle">
            Prism grounds every claim in the paper's own evidence.
          </div>
        )}

        {hasFailed && (
          <div className="mx-auto max-w-lg rounded-md border border-refused/20 bg-refused-bg p-4 text-sm text-refused">
            <p className="font-medium">
              Extraction failed at the {failedStageLabel ?? "unknown"} stage.
            </p>
            <p className="mt-1 text-ink-muted">
              The paper couldn't be processed. Try uploading again from the sidebar.
            </p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

interface StageRowProps {
  label: string;
  status: RowStatus;
  detail?: string;
  completed?: number;
  total?: number;
  isLast: boolean;
}

function StageRow({ label, status, detail, completed, total, isLast }: StageRowProps) {
  const showCounter = completed !== undefined && total !== undefined;

  return (
    <li className="relative flex items-start gap-4">
      {!isLast && (
        <div
          className={cn(
            "absolute bottom-[-24px] left-[15px] top-8 w-px",
            status === "completed" ? "bg-border-strong" : "border-l border-dashed border-border"
          )}
        />
      )}

      <div className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center bg-surface">
        {status === "completed" && (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-supported-bg">
            <CheckCircle2 className="h-5 w-5 text-supported" />
          </div>
        )}
        {status === "current" && (
          <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-accent bg-accent-subtle">
            <div className="h-2 w-2 animate-pulse rounded-full bg-accent" />
          </div>
        )}
        {status === "pending" && <div className="h-6 w-6 rounded-full border border-dashed border-border" />}
        {status === "failed" && (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-refused-bg">
            <XCircle className="h-5 w-5 text-refused" />
          </div>
        )}
      </div>

      <div className="min-w-0 flex-1 pt-1">
        <h3
          className={cn(
            "text-base",
            status === "completed" && "font-medium text-ink",
            status === "current" && "font-semibold text-ink",
            status === "pending" && "font-normal text-ink-muted",
            status === "failed" && "font-semibold text-refused"
          )}
        >
          {label}
        </h3>

        {status === "current" && detail && (
          <AnimatePresence mode="popLayout">
            <motion.p
              key={detail}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
            >
              {detail}
            </motion.p>
          </AnimatePresence>
        )}

        {status === "current" && showCounter && (
          <div className="mt-2 flex items-center gap-3">
            <div className="h-1 w-24 overflow-hidden rounded-full bg-border">
              <div
                className="h-full bg-accent transition-[width] duration-300 ease-out"
                style={{ width: `${(completed! / total!) * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium tabular-nums text-ink-muted">
              {completed} / {total}
            </span>
          </div>
        )}
      </div>
    </li>
  );
}
