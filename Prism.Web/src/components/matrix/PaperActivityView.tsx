import { motion } from "framer-motion";
import { Check, XCircle, Terminal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useExtractionProgress, useSignalR } from "@/hooks/useSignalR";
import type { ExtractionStage, ExtractionProgressEvent } from "@/types/api";
import { cn } from "@/lib/utils";
import { shouldSynthesizeFailureLine, stepperRowStatus, type RowStatus } from "@/lib/activityViewLogic";

interface PaperActivityViewProps {
  // null until the upload's POST response resolves — chatId is what the
  // component actually listens on, since it's known up front.
  fileId: string | null;
  chatId: string;
  fileName: string;
  extractionStatus: string;
  // Authoritative failure cause once extractionStatus is "Failed" - fetched
  // from PaperClaimsResponse.failureReason. Preferred over the live event's
  // reason (below) once it lands; see ExtractionProgressState.failedReason.
  failureReason?: string | null;
  // Cache-hit inline decision (Continue / Re-run). Undefined/false outside
  // of a cache-hit upload flow.
  isCacheHitPending?: boolean;
  isGoogleUser?: boolean;
  onCacheHitContinue?: () => void;
  onCacheHitCancel?: () => void;
  // Returns the user to upload from the failed state. Deliberately not a
  // retry/re-run: terminal content failures (corrupt/password/scanned) are
  // deterministic on the same file, and re-run bypasses dedupe with no
  // quota or cooldown today (A2.7, deferred to PR 3) - a retry button here
  // would be an uncapped spend path.
  onChooseDifferentFile?: () => void;
}

const STAGE_ORDER: ExtractionStage[] = ["preparing", "extracting", "auditing", "grounding", "finalizing", "done"];

const STAGE_LABELS: Record<ExtractionStage, string> = {
  preparing: "Preparing",
  extracting: "Extracting",
  auditing: "Auditing",
  grounding: "Grounding",
  finalizing: "Finalizing",
  done: "Done",
  failed: "Failed",
};

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

// Mirrors AUDIT_STRUCTURE_CONCURRENCY in Prism.PythonService/extraction/engine.py.
// There's no per-claim completion event on the wire, only per-claim "started"
// messages, so completion is inferred from the concurrency ceiling: once more
// than this many claims have started, each additional start implies an


// Cache-hit messages arrive back-to-back with no natural spacing (the server
// emits them synchronously, one after another, with no processing delay in
// between) — this is how long each one stays visible before the next is
// revealed. Only messages in the cache-hit flow are paced; the fresh-pipeline
// sequence already arrives naturally spaced by real processing time.
const CACHE_HIT_LOG_PACE_MS = 250;

interface LogEntry {
  id: string;
  time: string;
  stage: string;
  message: string;
  isError?: boolean;
  isBurstStatus?: boolean;
  // True only for the fetched-only-path fallback line (no live
  // ExtractionProgress "failed" event ever arrived this mount) - the worker
  // never said this, so it must render visibly differently from a real
  // pipeline event line, not just carry the same reason text.
  synthesized?: boolean;
}

function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function nowTime(): string {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

function capitalize(s: string): string {
  return s.length ? s[0].toUpperCase() + s.slice(1) : s;
}

export function PaperActivityView({
  fileId,
  chatId,
  fileName,
  extractionStatus,
  failureReason,
  isCacheHitPending = false,
  isGoogleUser = false,
  onCacheHitContinue,
  onCacheHitCancel,
  onChooseDifferentFile,
}: PaperActivityViewProps) {
  const progress = useExtractionProgress(chatId, fileId);
  const { on, off } = useSignalR();
  const [logState, setLogState] = useState({ visible: [] as LogEntry[], pending: [] as LogEntry[] });
  const logs = logState.visible;
  const pendingLogs = logState.pending;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [cacheHitDecisionMade, setCacheHitDecisionMade] = useState(false);

  const cacheHitFlowRef = useRef(false);
  const cacheHitContinuePendingRef = useRef(false);
  // Idempotency guard for the synthesized-failure-line effect below,
  // independent of where hasFailed's value comes from. A ref (not the
  // `logs` state the effect also checks) because React 18 StrictMode
  // double-invokes an effect on mount against the SAME closure before
  // either invocation's setState is visible to the other - a state-only
  // check can't see its own prior write yet, but a ref mutates
  // synchronously and is shared across both invocations.
  const hasSynthesizedFailureLineRef = useRef(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setLogState((prev) => {
        if (prev.pending.length === 0) return prev;
        const [next, ...rest] = prev.pending;
        return {
          visible: [...prev.visible, next],
          pending: rest,
        };
      });
    }, CACHE_HIT_LOG_PACE_MS);
    return () => {
      clearInterval(interval);
    };
  }, []);

  // Cache-hit tail state (Continue -> "Loading your results..." -> "Audit
  // complete — ready for chat") is driven entirely by frontend-synthesized
  // log lines, not real ExtractionProgress events, so the left-hand stepper
  // is advanced from those lines directly rather than from `progress`.
  const cacheHitTailStage: ExtractionStage | null = logs.some((l) => l.message === "Audit complete — ready for chat")
    ? "done"
    : logs.some((l) => l.message === "Loading your results...")
    ? "finalizing"
    : null;
  const effectiveStage = cacheHitTailStage ?? progress?.latestStage;

  const hasFailed = effectiveStage === "failed" || extractionStatus === "Failed";
  const currentIndex = (effectiveStage && !hasFailed) ? STAGE_ORDER.indexOf(effectiveStage) : 0;
  // -1 (not a hardcoded stage guess) when the real failedStage is unknown -
  // the live event carries it, but nothing persists it for the fetched-only
  // path (refresh, missed broadcast). Guessing a specific step here would
  // show a wrong one as failed; -1 makes getStatus render every row neutral
  // instead (known limitation - see B3.7 in docs/observability-and-cost-plan.md).
  const failedIndex = hasFailed ? (progress?.failedStage ? STAGE_ORDER.indexOf(progress.failedStage) : -1) : -1;
  const isDone = effectiveStage === "done";

  // Fetched (authoritative) reason wins once it lands; the live event's
  // reason is the fast path shown before that fetch resolves; a page
  // refresh after the run already ended has only the fetched one. Generic
  // fallback covers the small window where hasFailed is true from
  // extractionStatus alone but neither reason has arrived yet.
  const effectiveFailureReason = failureReason ?? progress?.failedReason ?? "we couldn't process this file";

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
      if (ev.chatId !== chatId && (!fileId || ev.fileId !== fileId)) return;

      // Bare stage-transition events carry no detail and fire once per stage -
      // the left-hand checklist already reflects the transition, so skip them
      // here rather than logging a line with no new information. "done" and
      // "failed" are terminal states worth a line even without a detail.
      let msg = ev.detail;
      if (!msg) {
        if (ev.stage === "done") msg = "Processing complete.";
        else if (ev.stage === "failed") msg = ev.reason ?? `Failed during ${ev.failedStage ?? "processing"}`;
        else return;
      }
      const time = nowTime();

      const entry: LogEntry = {
        id: crypto.randomUUID(),
        time,
        stage: ev.stage,
        message: msg,
        isError: ev.stage === "failed",
      };

      if (ev.stage === "preparing" && msg.startsWith("Found it")) {
        cacheHitFlowRef.current = true;
      }

      setLogState((prev) => {
        if (cacheHitFlowRef.current) {
          return { ...prev, pending: [...prev.pending, entry] };
        } else {
          return { ...prev, visible: [...prev.visible, entry] };
        }
      });
    };
    on("ExtractionProgress", handler);

    return () => {
      off("ExtractionProgress", handler);
    };
  }, [chatId, fileId, on, off]);

  // Covers the case no live "failed" ExtractionProgress event ever arrives
  // for this mount - a page refresh after the run already ended, or a
  // missed/reconnect-delayed broadcast. The live handler above already logs
  // a line when the event does arrive; this only fills the gap when it
  // didn't, so the log strip's last line is always the failure reason
  // before the stepper switches to the failed state (never silent).
  //
  // Idempotent regardless of how many times this fires with the same
  // inputs (e.g. React 18 StrictMode's dev-only double-invoke-on-mount):
  // hasSynthesizedFailureLineRef flips synchronously on the first run, so a
  // second invocation against the same stale `logs` closure is a no-op.
  useEffect(() => {
    if (!shouldSynthesizeFailureLine(hasSynthesizedFailureLineRef.current, hasFailed, logs)) return;
    hasSynthesizedFailureLineRef.current = true;
    setLogState((prev) => ({
      ...prev,
      visible: [
        ...prev.visible,
        {
          id: crypto.randomUUID(),
          time: nowTime(),
          stage: "failed",
          message: effectiveFailureReason,
          isError: true,
          synthesized: true,
        },
      ],
    }));
  }, [hasFailed, logs, effectiveFailureReason]);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Once the paced Continue tail has fully drained into view, the decision
  // is truly resolved — hand control back so the parent can swap in results.
  useEffect(() => {
    if (!cacheHitContinuePendingRef.current) return;
    if (pendingLogs.length > 0) return;
    if (!logs.some((l) => l.message === "Audit complete — ready for chat")) return;
    cacheHitContinuePendingRef.current = false;
    onCacheHitContinue?.();
  }, [pendingLogs, logs, onCacheHitContinue]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20;
    setAutoScroll(isAtBottom);
  };

  const handleCacheHitContinueClick = () => {
    setCacheHitDecisionMade(true);
    cacheHitContinuePendingRef.current = true;
    const time = nowTime();
    setLogState((prev) => ({
      ...prev,
      pending: [
        ...prev.pending,
        { id: crypto.randomUUID(), time, stage: "finalizing", message: "Loading your results..." },
        { id: crypto.randomUUID(), time, stage: "done", message: "Audit complete — ready for chat" },
      ]
    }));
  };



  const showCacheHitDecision =
    isCacheHitPending &&
    !cacheHitDecisionMade &&
    pendingLogs.length === 0 &&
    logs.some((l) => l.message.startsWith("Found it — already audited"));

  const getStatus = (index: number): RowStatus =>
    stepperRowStatus(index, hasFailed, failedIndex, currentIndex);

  // Same status computation the stepper uses, keyed by a log line's stage
  // string instead of a STAGE_ORDER index — so a log tag and its matching
  // stepper dot always render the same color for the same underlying state.
  const statusForStage = (stage: string): RowStatus => {
    if (stage === "failed") return hasFailed ? "failed" : "pending";
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
                <div className={cn("h-2 w-2 rounded-full", hasFailed ? STATUS_BG_CLASS.failed : cn(STATUS_BG_CLASS.current, "animate-pulse"))} />
                <span className="font-sans text-sm text-white/90">{hasFailed ? "Processing failed" : "Analysis in progress..."}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-white/50 tabular-nums">{formatElapsed(elapsedSeconds)}</span>
                <div className={cn("flex items-center gap-1.5 rounded-full border px-2 py-0.5", hasFailed ? "border-status-failed/30" : "border-status-active/30")}>
                  {hasFailed ? (
                    <XCircle className={cn("h-3 w-3", STATUS_TEXT_CLASS.failed)} />
                  ) : (
                    <div className={cn("h-3 w-3 rounded-full border-[1.5px] border-t-transparent animate-spin", STATUS_BORDER_CLASS.current)} />
                  )}
                  <span className={cn("font-sans text-xs font-medium", hasFailed ? STATUS_TEXT_CLASS.failed : STATUS_TEXT_CLASS.current)}>{hasFailed ? "Failed" : STAGE_LABELS[effectiveStage || "preparing"]}</span>
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

                    // A synthesized line is never something the worker sent -
                    // it must not read like a real pipeline event. Muted color,
                    // "[Status]" instead of "[Failed]", and an explicit note
                    // that it's a saved status rather than a live report.
                    const tagLabel = log.synthesized ? "Status" : (STAGE_LABELS[log.stage as ExtractionStage] || log.stage);
                    const tagColor = log.synthesized ? "text-white/50" : stageColor;
                    const messageColor = log.synthesized ? "text-white/60 italic" : status === "failed" ? STATUS_TEXT_CLASS.failed : "text-white/90";

                    return (
                      <div
                        key={log.id}
                        className={cn("break-words leading-relaxed", i === 0 ? "" : isNewGroup ? "mt-4" : "mt-1")}
                      >
                        <span className="text-white/40 mr-3">[{log.time}]</span>
                        <span className={cn("mr-2 font-semibold", tagColor)}>
                          [{tagLabel}]
                        </span>
                        <span className={messageColor}>
                          {log.message}
                          {log.synthesized && " (saved status - not a live report)"}
                        </span>
                      </div>
                    );
                  })}

                  {showCacheHitDecision && (
                    <div className="mt-4 rounded-lg border border-white/10 bg-white/5 p-4">
                      <div className="font-sans text-sm text-white/90">This paper is already in our system.</div>
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={handleCacheHitContinueClick}
                          className="rounded-md bg-charcoal px-3 py-1.5 font-sans text-xs font-medium text-white hover:opacity-90 transition-colors"
                        >
                          Continue
                        </button>
                        {!isGoogleUser && (
                          <button
                            onClick={() => onCacheHitCancel?.()}
                            className="rounded-md border border-white/20 px-3 py-1.5 font-sans text-xs font-medium text-white/80 hover:bg-white/10 transition-colors"
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </div>
                  )}
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
            {hasFailed ? (
              <div className={cn("flex-1 flex items-center gap-4 rounded-xl border bg-surface p-4", STATUS_BORDER_CLASS.failed)}>
                <div className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white", STATUS_BG_CLASS.failed)}>
                  <XCircle className="h-4 w-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-sans text-sm font-semibold text-ink">Couldn&apos;t process this file</div>
                  <div className={cn("font-sans text-xs mt-0.5", STATUS_TEXT_CLASS.failed)}>{capitalize(effectiveFailureReason)}.</div>
                </div>
                {onChooseDifferentFile && (
                  <button
                    onClick={onChooseDifferentFile}
                    className="shrink-0 rounded-md bg-charcoal px-3 py-1.5 font-sans text-xs font-medium text-white hover:opacity-90 transition-colors"
                  >
                    Choose a different file
                  </button>
                )}
              </div>
            ) : (
              <div className="flex-1 flex items-center gap-4 rounded-xl border border-hairline bg-surface p-4">
                <div className="h-6 w-6 shrink-0 rounded-full border-[2.5px] border-brand border-t-transparent animate-spin" />
                <div>
                  <div className="font-sans text-sm font-semibold text-ink">Working on your paper...</div>
                  <div className="font-sans text-xs text-ink-secondary mt-0.5">This may take a few minutes. You can safely leave this page.</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
