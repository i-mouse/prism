import { motion } from "framer-motion";
import { Check, XCircle, X, Terminal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useExtractionProgress, useSignalR } from "@/hooks/useSignalR";
import type { ExtractionStage, ExtractionProgressEvent } from "@/types/api";
import { cn } from "@/lib/utils";

interface PaperActivityViewProps {
  fileId: string;
  fileName: string;
  extractionStatus: string;
}

const STAGE_ORDER: ExtractionStage[] = ["preparing", "extracting", "grounding", "finalizing", "done"];

const STAGE_LABELS: Record<ExtractionStage, string> = {
  preparing: "Preparing",
  extracting: "Extracting",
  grounding: "Grounding",
  finalizing: "Finalizing",
  done: "Done",
  failed: "Failed",
};

type RowStatus = "completed" | "current" | "pending" | "failed";

// Single source of truth for the 4-color status system — the stepper dots
// and the log panel's bracketed stage tags both read from these instead of
// each hardcoding their own palette.
const STATUS_TEXT_CLASS: Record<RowStatus, string> = {
  completed: "text-status-complete",
  current: "text-status-active",
  pending: "text-status-pending",
  failed: "text-status-failed",
};

const STATUS_BG_CLASS: Record<RowStatus, string> = {
  completed: "bg-status-complete",
  current: "bg-status-active",
  pending: "bg-status-pending",
  failed: "bg-status-failed",
};

const STATUS_BORDER_CLASS: Record<RowStatus, string> = {
  completed: "border-status-complete",
  current: "border-status-active",
  pending: "border-status-pending",
  failed: "border-status-failed",
};

function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export function PaperActivityView({ fileId, fileName, extractionStatus }: PaperActivityViewProps) {
  const progress = useExtractionProgress(fileId);
  const { on, off } = useSignalR();
  const [logs, setLogs] = useState<{ id: string; time: string; stage: string; message: string; isError?: boolean }[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const hasFailed = progress?.latestStage === "failed" || extractionStatus === "Failed";
  const currentIndex = (progress && !hasFailed) ? STAGE_ORDER.indexOf(progress.latestStage) : 0;
  const failedIndex = hasFailed ? (progress?.failedStage ? STAGE_ORDER.indexOf(progress.failedStage) : 1) : -1;
  const isDone = progress?.latestStage === "done";

  const startTimeRef = useRef<number>(Date.now());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (hasFailed || isDone) return;
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [hasFailed, isDone]);

  useEffect(() => {
    const handler = (payload: unknown) => {
      const ev = payload as ExtractionProgressEvent;
      if (ev.fileId !== fileId) return;

      // Bare stage-transition events carry no detail and fire once per stage -
      // the left-hand checklist already reflects the transition, so skip them
      // here rather than logging a line with no new information. "done" and
      // "failed" are terminal states worth a line even without a detail.
      let msg = ev.detail;
      if (!msg) {
        if (ev.stage === "done") msg = "Processing complete.";
        else if (ev.stage === "failed") msg = `Failed during ${ev.failedStage ?? "processing"}`;
        else return;
      }
      const time = new Date().toLocaleTimeString("en-US", { hour12: false });

      setLogs((prev) => [...prev, {
        id: crypto.randomUUID(),
        time,
        stage: ev.stage,
        message: msg,
        isError: ev.stage === "failed"
      }]);
    };
    on("ExtractionProgress", handler);
    return () => off("ExtractionProgress", handler);
  }, [fileId, on, off]);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20;
    setAutoScroll(isAtBottom);
  };

  const getStatus = (index: number): RowStatus => {
    if (hasFailed) {
      if (index === failedIndex) return "failed";
      return index < failedIndex || failedIndex === -1 ? "completed" : "pending";
    }
    if (index < currentIndex) return "completed";
    if (index === currentIndex) return "current";
    return "pending";
  };

  // Same status computation the stepper uses, keyed by a log line's stage
  // string instead of a STAGE_ORDER index — so a log tag and its matching
  // stepper dot always render the same color for the same underlying state.
  const statusForStage = (stage: string): RowStatus => {
    if (stage === "failed") return "failed";
    const index = STAGE_ORDER.indexOf(stage as ExtractionStage);
    if (index === -1) return "pending";
    return getStatus(index);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="relative flex h-full flex-col bg-surface"
    >
      <div className="flex items-center justify-between border-b border-hairline px-6 py-4 lg:px-8">
        <div>
          <h1 className="font-sans text-xl font-semibold text-ink">{fileName}</h1>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-tertiary">
            {extractionStatus === "Completed"
              ? "Audit Complete"
              : extractionStatus === "Failed"
              ? "Audit Failed"
              : "Auditing Paper"}
          </p>
        </div>
        <button 
          onClick={() => {
            if (confirm("Are you sure you want to cancel the audit?")) {
              fetch(`/api/papers/${fileId}/cancel`, { method: "POST" }).catch(console.error);
            }
          }}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-ink-secondary hover:bg-surface-subtle hover:text-ink transition-colors"
        >
          Cancel
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        {/* LEFT COLUMN — STAGE CHECKLIST */}
        <div className="border-b border-hairline lg:border-b-0 lg:border-r lg:w-[320px] shrink-0 overflow-y-auto px-6 py-8 lg:px-8">
          <ol className="relative flex flex-col gap-6">
            {STAGE_ORDER.map((stage, i) => {
              const status = getStatus(i);
              const isLast = i === STAGE_ORDER.length - 1;
              // The row marked "failed" represents a STAGE_ORDER stage (e.g. "grounding"),
              // but the failure event itself is emitted with stage: "failed" - look there instead.
              const stageLogs = logs.filter(l => l.stage === (status === "failed" ? "failed" : stage));
              const logForStage = stageLogs.at(-1);
              return (
                <li key={stage} className="relative flex items-start gap-4">
                  {!isLast && (
                    <div
                      className={cn(
                        "absolute left-[11px] top-7 bottom-[-16px] border-l-2 border-dashed",
                        status === "completed" ? STATUS_BORDER_CLASS.completed : "border-hairline"
                      )}
                    />
                  )}

                  <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center bg-surface mt-0.5">
                    {status === "completed" && (
                      <div className={cn("flex h-6 w-6 items-center justify-center rounded-full text-white", STATUS_BG_CLASS.completed)}>
                        <Check className="h-4 w-4" strokeWidth={3} />
                      </div>
                    )}
                    {status === "current" && (
                      <div className={cn("flex h-6 w-6 items-center justify-center rounded-full border", STATUS_BORDER_CLASS.current, STATUS_TEXT_CLASS.current)}>
                        <div className={cn("h-2 w-2 rounded-full", STATUS_BG_CLASS.current)} />
                      </div>
                    )}
                    {status === "pending" && <div className={cn("h-5 w-5 rounded-full border", STATUS_BORDER_CLASS.pending)} />}
                    {status === "failed" && (
                      <div className={cn("flex h-6 w-6 items-center justify-center rounded-full text-white", STATUS_BG_CLASS.failed)}>
                        <XCircle className="h-4 w-4" />
                      </div>
                    )}
                  </div>

                  <div className="flex-1 pt-1">
                    <div className="flex items-center justify-between">
                      <div className={cn(
                        "font-sans text-sm font-semibold",
                        status === "completed" && "text-ink",
                        status === "current" && STATUS_TEXT_CLASS.current,
                        status === "pending" && "text-ink-tertiary",
                        status === "failed" && STATUS_TEXT_CLASS.failed
                      )}>
                        {STAGE_LABELS[stage]}
                      </div>
                      <div className="font-mono text-xs text-ink-tertiary">
                        {logForStage?.time || ""}
                      </div>
                    </div>
                    {(status === "completed" || status === "current" || status === "failed") && logForStage && (
                      <div className={cn("font-sans text-xs mt-1", status === "failed" ? STATUS_TEXT_CLASS.failed : "text-ink-secondary")}>
                        {logForStage.message}
                      </div>
                    )}
                    {status === "pending" && stage === "grounding" && (
                      <div className="font-sans text-xs text-ink-tertiary mt-1">Linking claims to evidence</div>
                    )}
                    {status === "pending" && stage === "finalizing" && (
                      <div className="font-sans text-xs text-ink-tertiary mt-1">Generating results</div>
                    )}
                    {status === "pending" && stage === "done" && (
                      <div className="font-sans text-xs text-ink-tertiary mt-1">Audit complete</div>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        {/* RIGHT COLUMN — LIVE LOG STREAM */}
        <div className="flex flex-1 flex-col bg-surface p-4 lg:p-6 min-h-0">
          <div className="flex-1 flex flex-col overflow-hidden rounded-xl bg-[#18181B] shadow-inner w-full max-h-[400px]">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 shrink-0">
              <div className="flex items-center gap-2">
                <div className={cn("h-2 w-2 rounded-full animate-pulse", STATUS_BG_CLASS.current)} />
                <span className="font-sans text-sm text-white/90">Analysis in progress...</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-white/50 tabular-nums">{formatElapsed(elapsedSeconds)}</span>
                <div className={cn("flex items-center gap-1.5 rounded-full border px-2 py-0.5", "border-status-active/30")}>
                  <div className={cn("h-3 w-3 rounded-full border-[1.5px] border-t-transparent animate-spin", STATUS_BORDER_CLASS.current)} />
                  <span className={cn("font-sans text-xs font-medium", STATUS_TEXT_CLASS.current)}>{STAGE_LABELS[progress?.latestStage || "preparing"]}</span>
                </div>
                <button className="rounded-md p-1 text-white/50 hover:bg-white/10 hover:text-white transition-colors">
                  <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
            </div>
            <div 
              ref={scrollRef}
              onScroll={handleScroll}
              className="flex-1 overflow-y-auto p-4 font-mono text-sm relative"
            >
              {logs.length === 0 ? (
                <div className="flex h-full items-center justify-center text-white/30">
                  <Terminal className="h-6 w-6 mr-2 opacity-50" />
                  Waiting for logs...
                </div>
              ) : (
                <div>
                  {logs.map((log, i) => {
                    // Same status the matching stepper dot uses, so a log
                    // line's stage tag always matches its dot's color.
                    const status = statusForStage(log.isError ? "failed" : log.stage);
                    const stageColor = STATUS_TEXT_CLASS[status];
                    const isNewGroup = i > 0 && logs[i - 1].stage !== log.stage;

                    return (
                      <div
                        key={log.id}
                        className={cn("break-words leading-relaxed", i === 0 ? "" : isNewGroup ? "mt-4" : "mt-1")}
                      >
                        <span className="text-white/40 mr-3">[{log.time}]</span>
                        <span className={cn("mr-2 font-semibold", stageColor)}>
                          [{STAGE_LABELS[log.stage as ExtractionStage] || log.stage}]
                        </span>
                        <span className={log.isError ? STATUS_TEXT_CLASS.failed : "text-white/90"}>
                          {log.message}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
              
              {/* Scroll Indicator */}
              {!autoScroll && (
                <div className="sticky bottom-2 left-1/2 -translate-x-1/2 inline-flex">
                  <button 
                    onClick={() => setAutoScroll(true)}
                    className="rounded-full bg-white/10 backdrop-blur px-3 py-1 text-xs text-white hover:bg-white/20"
                  >
                    ↓ Resume Auto-scroll
                  </button>
                </div>
              )}
            </div>
          </div>
          
          {/* BELOW BOTH COLUMNS — COUNTER STRIP */}
          <div className="mt-4 flex flex-col md:flex-row gap-4 pt-2">
            <div className="flex-1 flex items-center gap-4 rounded-xl border border-hairline bg-surface p-4">
              <div className="h-6 w-6 shrink-0 rounded-full border-[2.5px] border-brand border-t-transparent animate-spin" />
              <div>
                <div className="font-sans text-sm font-semibold text-ink">Working on your paper...</div>
                <div className="font-sans text-xs text-ink-secondary mt-0.5">This may take a few minutes. You can safely leave this page.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
