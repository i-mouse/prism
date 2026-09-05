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

export function PaperActivityView({ fileId, fileName, extractionStatus }: PaperActivityViewProps) {
  const progress = useExtractionProgress(fileId);
  const { on, off } = useSignalR();
  const [logs, setLogs] = useState<{ id: string; time: string; stage: string; message: string; isError?: boolean }[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const hasFailed = progress?.latestStage === "failed" || extractionStatus === "Failed";
  const currentIndex = (progress && !hasFailed) ? STAGE_ORDER.indexOf(progress.latestStage) : 0;
  const failedIndex = hasFailed ? (progress?.failedStage ? STAGE_ORDER.indexOf(progress.failedStage) : 1) : -1;

  useEffect(() => {
    const handler = (payload: unknown) => {
      const ev = payload as ExtractionProgressEvent;
      if (ev.fileId !== fileId) return;
      
      const msg = ev.detail || (ev.stage === "done" ? "Processing complete." : `Started ${ev.stage}`);
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
              const logForStage = logs.find(l => l.stage === stage);
              return (
                <li key={stage} className="relative flex items-start gap-4">
                  {!isLast && (
                    <div
                      className={cn(
                        "absolute left-[11px] top-7 bottom-[-16px] border-l-2 border-dashed",
                        status === "completed" ? "border-emerald-500" : "border-hairline"
                      )}
                    />
                  )}
                  
                  <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center bg-surface mt-0.5">
                    {status === "completed" && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
                        <Check className="h-4 w-4" strokeWidth={3} />
                      </div>
                    )}
                    {status === "current" && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full border border-brand text-brand">
                        <div className="h-2 w-2 rounded-full bg-brand" />
                      </div>
                    )}
                    {status === "pending" && <div className="h-5 w-5 rounded-full border border-hairline" />}
                    {status === "failed" && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500 text-white">
                        <XCircle className="h-4 w-4" />
                      </div>
                    )}
                  </div>
                  
                  <div className="flex-1 pt-1">
                    <div className="flex items-center justify-between">
                      <div className={cn(
                        "font-sans text-sm font-semibold",
                        status === "completed" && "text-ink",
                        status === "current" && "text-brand",
                        status === "pending" && "text-ink-tertiary",
                        status === "failed" && "text-red-500"
                      )}>
                        {STAGE_LABELS[stage]}
                      </div>
                      <div className="font-mono text-xs text-ink-tertiary">
                        {logForStage?.time || ""}
                      </div>
                    </div>
                    {status === "completed" && stage === "preparing" && (
                      <div className="font-sans text-xs text-ink-secondary mt-1">Parsed 33 pages, 111 chunks</div>
                    )}
                    {status === "completed" && stage === "extracting" && (
                      <div className="font-sans text-xs text-ink-secondary mt-1">Extracted paper metadata</div>
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
                <div className="h-2 w-2 rounded-full bg-brand animate-pulse" />
                <span className="font-sans text-sm text-white/90">Analysis in progress...</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 rounded-full border border-brand/30 px-2 py-0.5">
                  <div className="h-3 w-3 rounded-full border-[1.5px] border-brand border-t-transparent animate-spin" />
                  <span className="font-sans text-xs font-medium text-brand">{STAGE_LABELS[progress?.latestStage || "preparing"]}</span>
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
                <div className="space-y-1">
                  {logs.map((log) => {
                    let stageColor = "text-white/70";
                    if (log.stage === "extracting" || log.stage === "grounding") stageColor = "text-brand";
                    if (log.stage === "done") stageColor = "text-emerald-400";
                    if (log.isError) stageColor = "text-red-400";
                    
                    return (
                      <div key={log.id} className="break-words leading-relaxed">
                        <span className="text-white/40 mr-3">[{log.time}]</span>
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
            
            <div className="flex-1 flex items-start gap-4 rounded-xl border border-hairline bg-surface p-4">
              <div className="flex shrink-0 items-center justify-center">
                <svg className="h-5 w-5 text-brand" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div>
                <div className="font-sans text-sm font-semibold text-ink">Tip</div>
                <div className="font-sans text-xs text-ink-secondary mt-0.5">Prism analyzes each claim and grounds it in the paper's own evidence.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
