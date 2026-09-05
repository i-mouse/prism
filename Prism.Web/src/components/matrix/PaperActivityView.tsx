import { motion } from "framer-motion";
import { Check, XCircle, X, Terminal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useExtractionProgress, useSignalR } from "@/hooks/useSignalR";
import type { ExtractionStage, ExtractionProgressEvent } from "@/types/api";
import { cn } from "@/lib/utils";

interface PaperActivityViewProps {
  fileId: string;
  fileName: string;
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

export function PaperActivityView({ fileId, fileName }: PaperActivityViewProps) {
  const progress = useExtractionProgress(fileId);
  const { on, off } = useSignalR();
  const [logs, setLogs] = useState<{ id: number; time: string; stage: string; message: string; isError?: boolean }[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const hasFailed = progress?.latestStage === "failed";
  const currentIndex = progress && !hasFailed ? STAGE_ORDER.indexOf(progress.latestStage) : 0;
  const failedIndex = hasFailed && progress.failedStage ? STAGE_ORDER.indexOf(progress.failedStage) : -1;

  useEffect(() => {
    let logId = 0;
    const handler = (payload: unknown) => {
      const ev = payload as ExtractionProgressEvent;
      if (ev.fileId !== fileId) return;
      
      const msg = ev.detail || (ev.stage === "done" ? "Processing complete." : `Started ${ev.stage}`);
      const time = new Date().toLocaleTimeString("en-US", { hour12: false });
      
      setLogs((prev) => [...prev, {
        id: ++logId,
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
          <p className="font-mono text-xs uppercase tracking-wider text-ink-tertiary">Auditing Paper</p>
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
              return (
                <li key={stage} className="relative flex items-center gap-4">
                  {!isLast && (
                    <div
                      className={cn(
                        "absolute left-[11px] top-7 bottom-[-16px] w-[2px]",
                        status === "completed" ? "bg-emerald-500" : "bg-hairline"
                      )}
                    />
                  )}
                  
                  <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center bg-surface">
                    {status === "completed" && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
                        <Check className="h-4 w-4" strokeWidth={3} />
                      </div>
                    )}
                    {status === "current" && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full border border-brand text-brand">
                        <div className="h-2 w-2 animate-pulse rounded-full bg-brand" />
                      </div>
                    )}
                    {status === "pending" && <div className="h-5 w-5 rounded-full border border-hairline" />}
                    {status === "failed" && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500 text-white">
                        <XCircle className="h-4 w-4" />
                      </div>
                    )}
                  </div>
                  
                  <div className={cn(
                    "font-mono text-sm uppercase tracking-wider",
                    status === "completed" && "text-ink",
                    status === "current" && "text-brand",
                    status === "pending" && "text-ink-tertiary",
                    status === "failed" && "text-red-500"
                  )}>
                    {STAGE_LABELS[stage]}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>

        {/* RIGHT COLUMN — LIVE LOG STREAM */}
        <div className="flex flex-1 flex-col bg-surface p-4 lg:p-6 min-h-0">
          <div 
            ref={scrollRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto rounded-xl bg-ink p-4 font-mono text-sm shadow-inner relative max-h-64 lg:max-h-96 w-full"
          >
            {logs.length === 0 ? (
              <div className="flex h-full items-center justify-center text-white/30">
                <Terminal className="h-6 w-6 mr-2 opacity-50" />
                Waiting for logs...
              </div>
            ) : (
              <div className="space-y-1">
                {logs.map((log) => {
                  let stageColor = "text-white/70";
                  if (log.stage === "extracting" || log.stage === "grounding") stageColor = "text-brand";
                  if (log.stage === "done") stageColor = "text-emerald-400";
                  if (log.isError) stageColor = "text-red-400";
                  
                  return (
                    <div key={log.id} className="break-words">
                      <span className="text-white/50 mr-3">[{log.time}]</span>
                      <span className={cn("mr-2 font-semibold", stageColor)}>
                        [{STAGE_LABELS[log.stage as ExtractionStage] || log.stage}]
                      </span>
                      <span className={log.isError ? "text-red-300" : "text-white/90"}>
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
                  className="rounded-full bg-surface-subtle/20 backdrop-blur px-3 py-1 text-xs text-white hover:bg-surface-subtle/40"
                >
                  ↓ Resume Auto-scroll
                </button>
              </div>
            )}
          </div>
          
          {/* BELOW BOTH COLUMNS — COUNTER STRIP */}
          <div className="mt-4 flex flex-wrap gap-6 border-t border-hairline pt-4">
            {progress?.latestCompleted !== undefined && progress?.latestTotal !== undefined && (
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xl gradient-brand font-bold">
                  {progress.latestCompleted} of {progress.latestTotal}
                </span>
                <span className="font-sans text-sm text-ink-secondary">
                  {progress.latestStage === "extracting" ? "claims extracted" : "claims verified"}
                </span>
              </div>
            )}
            {progress?.finalizingSummary && (
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xl text-ink font-bold">
                  Done
                </span>
                <span className="font-sans text-sm text-ink-secondary">
                  {progress.finalizingSummary}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
