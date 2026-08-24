import { useEffect, useState } from "react";
import { signalRService } from "@/services/signalRService";
import type { ExtractionProgressEvent, ExtractionStage } from "@/types/api";

export function useSignalR() {
  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL;
    signalRService.start(baseUrl).catch(() => {
      // Errors are already logged inside signalRService; nothing further to do here.
    });
  }, []);

  return {
    joinChat: (chatId: string) => signalRService.joinChat(chatId),
    on: (event: string, callback: (...args: unknown[]) => void) =>
      signalRService.on(event, callback),
    off: (event: string, callback?: (...args: unknown[]) => void) =>
      signalRService.off(event, callback),
    getConnectionId: () => signalRService.connectionId,
  };
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
export function useExtractionProgress(fileId: string | null) {
  const [state, setState] = useState<ExtractionProgressState | null>(null);

  useEffect(() => {
    setState(null);
    if (!fileId) return;

    const handler = (payload: unknown) => {
      const event = payload as ExtractionProgressEvent;
      if (event?.fileId !== fileId) return;

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
  }, [fileId]);6

  return state;
}
