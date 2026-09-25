import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { createChatStreamStore, type ChatStreamStore } from "@/lib/chat-stream-store";

// ── Owner hook: called by MatrixView ─────────────────────────────────────────
// MatrixView is the one component in this tree that survives both a paper
// switch and the skeleton/activity branch (all its hooks run before its
// `!activePaperId` early return, and /paper/:paperId is a single Route so
// React Router reconciles rather than remounts AppShell). A stream owned here
// therefore outlives the chat strip that started it - which is the whole fix:
// PaperChatStrip is keyed by activeChatId, so switching papers used to unmount
// it, abort the fetch mid-stream, and cache the half-written turn as if it
// were settled.
export function useChatStreamStore(): ChatStreamStore {
  // useState's lazy initializer rather than a ref: one store per mounted
  // MatrixView, created once and never replaced (so this never re-renders),
  // without reading a ref during render - which react-hooks/refs rejects.
  const [store] = useState(createChatStreamStore);

  // The ONLY abort-everything path: this component tree unmounting - a route
  // change off /paper/:paperId, which is also what sign-out's navigate("/login")
  // produces. A paper switch never reaches here. activate() on mount pairs
  // with dispose() so StrictMode's phantom mount/cleanup/remount is harmless.
  useEffect(() => {
    store.activate();
    return () => {
      store.dispose();
    };
  }, [store]);

  // Relocated from the old in-hook visibilitychange effect, same purpose: a
  // stream whose connection the browser killed while the tab was frozen ends
  // with no closing frame, and the backend has persisted the real answer
  // regardless (Prism.PythonService/api.py, _run_paper_chat_graph), so
  // returning to the tab is the cue to go fetch it. Event-driven only - no
  // timer, no polling. Now covers every chat in the store rather than the one
  // chat a single hook instance happened to be mounted for.
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      store.retryPendingRecovery();
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [store]);

  return store;
}

// ── View hook: called by PaperChatStrip ──────────────────────────────────────
// Owns no fetch and no AbortController any more. It selects the active chat's
// slice out of the parent's store and forwards user intent back into it, so
// its unmount - which happens on every paper switch, via key={activeChatId} in
// MatrixView - is entirely inert.
export function useChatStream(
  chatId: string | null,
  activeFileId: string | null,
  store: ChatStreamStore
) {
  const entry = useSyncExternalStore(
    store.subscribe,
    useCallback(() => store.getEntry(chatId), [store, chatId])
  );

  // Mount-time reconciliation for the chat now on screen.
  //
  // "empty": nothing local to preserve, so loadHistory alone - it is
  // authoritative and clears pendingRecovery itself.
  //
  // "ready": the stored turns are the truth, so only the specific turn whose
  // stream ended abnormally needs the surgical re-fetch. loadHistory still
  // runs behind it as condition (b)'s safety net - needsHistory() makes it a
  // no-op unless an assistant turn is left marked isStreaming with no live
  // stream and no queued recovery, the one shape that must never be allowed
  // to sit here as a permanent cache hit. Ordering matters: retryRecovery
  // claims the chat in historyFetches synchronously, so the two can never
  // fire overlapping /history requests.
  useEffect(() => {
    if (!chatId) return;
    if (store.getHistoryStatus(chatId) === "empty") {
      void store.loadHistory(chatId);
      return;
    }
    store.retryRecovery(chatId);
    void store.loadHistory(chatId);
  }, [chatId, store]);

  const sendMessage = useCallback(
    (message: string) => {
      if (!chatId || !activeFileId) return;
      void store.sendMessage(chatId, activeFileId, message);
    },
    [store, chatId, activeFileId]
  );

  const abort = useCallback(() => {
    if (chatId) store.abort(chatId, "user");
  }, [store, chatId]);

  // No call site anywhere in the app - preserved only so this hook's return
  // shape is unchanged. Dead code; see the handover note.
  const clear = useCallback(() => {
    if (chatId) store.clear(chatId);
  }, [store, chatId]);

  return {
    turns: entry.turns,
    isSending: entry.isSending,
    error: entry.error,
    sendMessage,
    clear,
    abort,
  };
}
