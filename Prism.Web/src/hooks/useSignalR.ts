import { useCallback, useEffect, useState } from "react";
import { signalRService } from "@/services/signalRService";
import type { ExtractionProgressEvent, ExtractionStage } from "@/types/api";

export function useSignalR() {
  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL;
    if (!baseUrl) {
      console.error("VITE_API_BASE_URL is not set; skipping SignalR connection.");
      return;
    }
    signalRService.start(baseUrl).catch(() => {
      // Errors are already logged inside signalRService; nothing further to do here.
    });
  }, []);

  // Stable identities (empty deps) are load-bearing, not just tidiness:
  // these are consumed as useEffect dependencies elsewhere (e.g.
  // PaperActivityView's SignalR message listener, AppShell's join/
  // DocumentProcessed effects) — a fresh function reference every render
  // was tearing those effects down and rebuilding them on every render
  // instead of only when the thing they actually depend on (chatId)
  // changed. They only ever delegate to the signalRService singleton, so
  // memoizing them is safe.
  const joinChat = useCallback((chatId: string) => signalRService.joinChat(chatId), []);
  const on = useCallback(
    (event: string, callback: (...args: unknown[]) => void) => signalRService.on(event, callback),
    []
  );
  const off = useCallback(
    (event: string, callback?: (...args: unknown[]) => void) => signalRService.off(event, callback),
    []
  );
  const getConnectionId = useCallback(() => signalRService.connectionId, []);

  return { joinChat, on, off, getConnectionId };
}

export interface ExtractionProgressState {
  latestStage: ExtractionStage;
  latestCompleted?: number;
  latestTotal?: number;
  latestDetail?: string;
  finalizingSummary?: string;
  failedStage?: ExtractionStage;
}

// Tracks extraction progress for one paper as cumulative state rather than
// a single latest event, so a detail-only or counter-only event doesn't
// blow away the other. Assumes a SignalR connection is already being
// started elsewhere (AppShell calls useSignalR()); this hook only
// subscribes/unsubscribes to the event.
//
// Filters by chatId rather than fileId: chatId is generated client-side and
// known before the upload's POST request is even sent, while fileId only
// comes back once that request resolves — filtering on fileId would silently
// drop every progress event emitted before then.
export function useExtractionProgress(chatId: string | null, fileId: string | null) {
  const [state, setState] = useState<ExtractionProgressState | null>(null);

  useEffect(() => {
    setState(null);
    if (!chatId) return;

    const handler = (payload: unknown) => {
      const event = payload as ExtractionProgressEvent;
      // Accept events targeting this chat, OR events for this file (from an original joined chat)
      if (event?.chatId !== chatId && (!fileId || event?.fileId !== fileId)) return;

      setState((prev) => {
        if (event.stage === "failed") {
          return {
            latestStage: "failed",
            failedStage: event.failedStage,
            finalizingSummary: prev?.finalizingSummary,
          };
        }

        // A fresh stage resets detail/counter rather than inheriting the
        // previous stage's leftovers; within the same stage, a
        // detail-only or counter-only event merges onto what's there.
        const isNewStage = !prev || prev.latestStage !== event.stage;

        const next: ExtractionProgressState = {
          latestStage: event.stage,
          latestCompleted: isNewStage ? event.completed : (event.completed ?? prev?.latestCompleted),
          latestTotal: isNewStage ? event.total : (event.total ?? prev?.latestTotal),
          latestDetail: isNewStage ? event.detail : (event.detail ?? prev?.latestDetail),
          finalizingSummary: prev?.finalizingSummary,
        };

        if (event.stage === "finalizing" && event.detail?.includes("audited")) {
          next.finalizingSummary = event.detail;
        }

        return next;
      });
    };

    signalRService.on("ExtractionProgress", handler);
    return () => signalRService.off("ExtractionProgress", handler);
  }, [chatId, fileId]);

  return state;
}
