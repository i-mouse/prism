import { useCallback, useEffect, useRef, useState } from "react";
import { acquireAccessToken } from "@/lib/auth";
import type { ChatBlock, ChatTurn } from "@/types/chat";

type SseFrame =
  | { type: "text"; content: string }
  | {
      type: "claim_reference";
      claim_id: string;
      claim_summary: string;
      display_label: "supported" | "partially_supported" | "not_supported";
    }
  | { type: "error"; message: string }
  | { type: "done" };

// All three below target a turn by `id` rather than by array position. A
// send's SSE handlers, its abnormal-end fallback, and the tab-visibility
// recovery check are all async and can resolve well after a newer send has
// pushed its own turns onto the array - matching positionally on "last turn"
// would silently corrupt whichever turn happens to be last by the time the
// callback fires instead of the turn that callback actually belongs to.
function appendTextToTurn(turns: ChatTurn[], id: string, content: string): ChatTurn[] {
  const idx = turns.findIndex((t) => t.id === id);
  if (idx === -1) return turns;
  const target = turns[idx];
  const lastBlock = target.blocks[target.blocks.length - 1];
  const blocks: ChatBlock[] =
    lastBlock && lastBlock.type === "text"
      ? [...target.blocks.slice(0, -1), { type: "text", content: lastBlock.content + content }]
      : [...target.blocks, { type: "text", content }];
  return [...turns.slice(0, idx), { ...target, blocks }, ...turns.slice(idx + 1)];
}

function appendBlockToTurn(turns: ChatTurn[], id: string, block: ChatBlock): ChatTurn[] {
  const idx = turns.findIndex((t) => t.id === id);
  if (idx === -1) return turns;
  const target = turns[idx];
  return [...turns.slice(0, idx), { ...target, blocks: [...target.blocks, block] }, ...turns.slice(idx + 1)];
}

function markTurnDone(turns: ChatTurn[], id: string): ChatTurn[] {
  const idx = turns.findIndex((t) => t.id === id);
  if (idx === -1) return turns;
  const target = turns[idx];
  if (!target.isStreaming) return turns;
  return [...turns.slice(0, idx), { ...target, isStreaming: false }, ...turns.slice(idx + 1)];
}

// Shape returned by GET /api/chat/{chatId}/history (Prism.PythonService/api.py,
// get_chat_history) — flattened plain-text messages from the LangGraph
// checkpoint, role "ai"/"user" rather than the frontend's "assistant"/"user".
// Historical messages carry no claim_reference block structure (the history
// endpoint only ever serializes plain content), so they're restored as
// plain-text blocks — only messages from the live SSE stream in the current
// session get interactive citation pills. Fixing that would mean persisting
// block structure server-side, out of scope here.
interface HistoryMessage {
  role: "user" | "ai";
  content: string;
}

async function fetchHistoryMessages(chatId: string): Promise<HistoryMessage[] | null> {
  const headers: HeadersInit = {};
  const token = await acquireAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`/api/chat/${chatId}/history`, { headers, credentials: "include" });
  if (!res.ok) return null;

  const data: { messages: HistoryMessage[] } = await res.json();
  return data.messages ?? null;
}

export function useChatStream(chatId: string | null, activeFileId: string | null) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  // Mirrors `turns` for synchronous reads from the visibilitychange handler
  // below, which needs to check isStreaming without triggering a re-render
  // or routing a side effect (the history fetch) through a setState updater.
  const turnsRef = useRef<ChatTurn[]>(turns);
  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);
  // Tracks the assistant turn currently in flight from sendMessage, so the
  // visibilitychange recovery check below can look it up by id when the tab
  // regains focus. Cleared as soon as that turn resolves (sendMessage's
  // `finally` block) - its presence here is exactly "this turn is still
  // streaming", which the recovery check relies on to skip entirely once a
  // turn is already done.
  const activeAssistantTurnRef = useRef<{ id: string; chatId: string } | null>(null);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  // Recovers a turn whose live SSE stream may have ended abnormally (tab
  // backgrounded/frozen mid-stream, connection dropped with no closing
  // "done" frame - see useChatStream's sendMessage `finally` block and
  // docs/decisions.md "Known gap: Bug 4"). The backend keeps running the
  // chat graph and persists the answer regardless of the SSE connection's
  // fate (Prism.PythonService/api.py, _run_paper_chat_graph), so on return
  // to the tab we can always recover the true answer from chat history -
  // matched to the specific tracked turn `id`, never positionally on
  // "last turn", so a chat switch (which fully remounts this hook via
  // `key={activeChatId}` in MatrixView) or a newer send can't cause this to
  // clobber the wrong turn.
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      const tracked = activeAssistantTurnRef.current;
      if (!tracked || tracked.chatId !== chatId) return;

      const idx = turnsRef.current.findIndex((t) => t.id === tracked.id);
      // Gated on isStreaming, read synchronously off turnsRef rather than
      // via a setTurns updater - this must decide whether to fetch at all
      // BEFORE doing anything async, so a long-finished turn (the common
      // case on most tab switches, since the ref only clears once
      // sendMessage's finally runs) costs nothing, not even a network call.
      if (idx === -1 || !turnsRef.current[idx].isStreaming) return;
      // This turn's ordinal among assistant turns up to itself - used to
      // pick the matching message out of history's flat list below, since
      // history has no turn ids of its own to match on directly.
      const assistantOrdinal = turnsRef.current.slice(0, idx + 1).filter((t) => t.role === "assistant").length - 1;

      (async () => {
        const messages = await fetchHistoryMessages(tracked.chatId).catch(() => null);
        if (!messages?.length) return;
        // Still guarding on chatId here (not just at the top of the
        // handler) since this resolves after an await - the ref, and the
        // chat this closure was registered for, could have moved on by now.
        if (activeAssistantTurnRef.current?.chatId !== tracked.chatId) return;

        const assistantMessages = messages.filter((m) => m.role === "ai");
        // Backend only ever writes a chat message once generation is fully
        // complete (Prism.PythonService/api.py, _run_paper_chat_graph) - so
        // its presence at this ordinal is itself the "done" signal. No
        // length/content comparison against the live render needed (and
        // none would be reliable: the persisted text carries raw
        // "[claim:ID]" tokens where the live render has full claim_summary
        // text, so the two are never directly comparable).
        if (assistantMessages.length <= assistantOrdinal) return;
        const persistedText = assistantMessages[assistantOrdinal].content;

        activeAssistantTurnRef.current = null;
        setTurns((prev) => {
          const i = prev.findIndex((t) => t.id === tracked.id);
          if (i === -1) return prev;
          const recovered: ChatTurn = {
            ...prev[i],
            blocks: [{ type: "text", content: persistedText }],
            isStreaming: false,
          };
          return [...prev.slice(0, i), recovered, ...prev.slice(i + 1)];
        });
      })();
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [chatId]);

  // Restores prior conversation on mount (the parent remounts this hook via
  // `key={activeChatId}` on paper switch — see PaperChatStrip) instead of
  // always starting from an empty transcript. Failures fall back to an empty
  // transcript rather than blocking a fresh conversation.
  useEffect(() => {
    if (!chatId) return;
    let cancelled = false;

    (async () => {
      try {
        const messages = await fetchHistoryMessages(chatId);
        if (cancelled || !messages?.length) return;

        setTurns(
          messages.map((m) => ({
            id: crypto.randomUUID(),
            role: m.role === "ai" ? "assistant" : "user",
            blocks: [{ type: "text", content: m.content }],
            timestamp: Date.now(),
          }))
        );
      } catch {
        // Leave turns empty — a history-fetch failure shouldn't block chat.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chatId]);

  const clear = useCallback(() => {
    controllerRef.current?.abort();
    setTurns([]);
    setIsSending(false);
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!chatId || !activeFileId || !message.trim()) return;

      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      const assistantTurnId = crypto.randomUUID();
      activeAssistantTurnRef.current = { id: assistantTurnId, chatId };

      setError(null);
      setTurns((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", blocks: [{ type: "text", content: message }], timestamp: Date.now() },
        { id: assistantTurnId, role: "assistant", blocks: [], timestamp: Date.now(), isStreaming: true },
      ]);
      setIsSending(true);

      try {
        const headers: HeadersInit = { "Content-Type": "application/json" };
        const token = await acquireAccessToken();
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch("/api/chat/ask/stream", {
          method: "POST",
          headers,
          body: JSON.stringify({ chat_id: chatId, active_file_id: activeFileId, message }),
          credentials: "include",
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Chat request failed: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const rawFrame of frames) {
            const line = rawFrame.trim();
            if (!line.startsWith("data: ")) continue;

            let frame: SseFrame;
            try {
              frame = JSON.parse(line.slice("data: ".length));
            } catch {
              continue;
            }

            if (frame.type === "text") {
              setTurns((prev) => appendTextToTurn(prev, assistantTurnId, frame.content));
            } else if (frame.type === "claim_reference") {
              setTurns((prev) =>
                appendBlockToTurn(prev, assistantTurnId, {
                  type: "claim_reference",
                  claim_id: frame.claim_id,
                  claim_summary: frame.claim_summary,
                  display_label: frame.display_label,
                })
              );
            } else if (frame.type === "error") {
              setError(frame.message);
              setTurns((prev) => markTurnDone(prev, assistantTurnId));
            } else if (frame.type === "done") {
              setTurns((prev) => markTurnDone(prev, assistantTurnId));
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          // Fall through to `finally` — a non-user-initiated abort (browser
          // killing a frozen/discarded background tab's fetch) still needs
          // isStreaming resolved, same as any other abnormal end.
        } else {
          setError(err instanceof Error ? err.message : "Chat request failed");
        }
      } finally {
        if (controllerRef.current === controller) {
          setIsSending(false);
        }
        // Unconditional safety net so isStreaming always resolves the first
        // time this code runs, regardless of how the stream ended: a clean
        // "done"/"error" frame (already handled above, this is then a
        // no-op), a thrown error, an abort, or - the gap this closes - the
        // response body simply ending with no closing frame at all (e.g.
        // the backend's is_disconnected() check skipping the final "done"
        // frame, Prism.PythonService/api.py paper_chat_ask). Matched by
        // this send's own assistantTurnId, not "last turn", so it can't
        // clobber a newer turn if another send started before this one's
        // stream actually finished unwinding.
        setTurns((prev) => markTurnDone(prev, assistantTurnId));
        // Only clear if it still points at this send's own turn - a newer
        // send may already have overwritten it, and clearing here would
        // wrongly un-track that newer, still-in-flight turn.
        if (activeAssistantTurnRef.current?.id === assistantTurnId) {
          activeAssistantTurnRef.current = null;
        }
      }
    },
    [chatId, activeFileId]
  );

  const abort = useCallback(() => {
    controllerRef.current?.abort();
    // sendMessage's `finally` block resolves isStreaming unconditionally,
    // but only after its catch/finally chain unwinds asynchronously - this
    // marks it done immediately so the cursor/thinking-dots stop the instant
    // the user clicks Stop, matched by id via the same tracked-turn ref the
    // visibility recovery check uses, not positionally on "last turn".
    const activeId = activeAssistantTurnRef.current?.id;
    if (activeId) {
      setTurns((prev) => markTurnDone(prev, activeId));
    }
  }, []);

  return { turns, isSending, error, sendMessage, clear, abort };
}
