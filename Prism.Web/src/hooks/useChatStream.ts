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

function appendTextToLastTurn(turns: ChatTurn[], content: string): ChatTurn[] {
  const last = turns[turns.length - 1];
  const lastBlock = last.blocks[last.blocks.length - 1];
  const blocks: ChatBlock[] =
    lastBlock && lastBlock.type === "text"
      ? [...last.blocks.slice(0, -1), { type: "text", content: lastBlock.content + content }]
      : [...last.blocks, { type: "text", content }];
  return [...turns.slice(0, -1), { ...last, blocks }];
}

function appendBlockToLastTurn(turns: ChatTurn[], block: ChatBlock): ChatTurn[] {
  const last = turns[turns.length - 1];
  return [...turns.slice(0, -1), { ...last, blocks: [...last.blocks, block] }];
}

function markLastTurnDone(turns: ChatTurn[]): ChatTurn[] {
  const last = turns[turns.length - 1];
  return [...turns.slice(0, -1), { ...last, isStreaming: false }];
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

export function useChatStream(chatId: string | null, activeFileId: string | null) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  // Restores prior conversation on mount (the parent remounts this hook via
  // `key={activeChatId}` on paper switch — see PaperChatStrip) instead of
  // always starting from an empty transcript. Failures fall back to an empty
  // transcript rather than blocking a fresh conversation.
  useEffect(() => {
    if (!chatId) return;
    let cancelled = false;

    (async () => {
      try {
        const headers: HeadersInit = {};
        const token = await acquireAccessToken();
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(`/api/chat/${chatId}/history`, { headers, credentials: "include" });
        if (!res.ok || cancelled) return;

        const data: { messages: HistoryMessage[] } = await res.json();
        if (cancelled || !data.messages?.length) return;

        setTurns(
          data.messages.map((m) => ({
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

      setError(null);
      setTurns((prev) => [
        ...prev,
        { role: "user", blocks: [{ type: "text", content: message }], timestamp: Date.now() },
        { role: "assistant", blocks: [], timestamp: Date.now(), isStreaming: true },
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
              setTurns((prev) => appendTextToLastTurn(prev, frame.content));
            } else if (frame.type === "claim_reference") {
              setTurns((prev) =>
                appendBlockToLastTurn(prev, {
                  type: "claim_reference",
                  claim_id: frame.claim_id,
                  claim_summary: frame.claim_summary,
                  display_label: frame.display_label,
                })
              );
            } else if (frame.type === "error") {
              setError(frame.message);
              setTurns((prev) => markLastTurnDone(prev));
            } else if (frame.type === "done") {
              setTurns((prev) => markLastTurnDone(prev));
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Chat request failed");
        setTurns((prev) => markLastTurnDone(prev));
      } finally {
        if (controllerRef.current === controller) {
          setIsSending(false);
        }
      }
    },
    [chatId, activeFileId]
  );

  const abort = useCallback(() => {
    controllerRef.current?.abort();
    // Without this, the aborted turn's isStreaming flag never flips: the
    // fetch's own AbortError branch intentionally no-ops (see catch below)
    // so unmount-triggered aborts don't touch state, but a user-triggered
    // stop needs the cursor/thinking-dots to actually stop.
    setTurns((prev) => (prev.length ? markLastTurnDone(prev) : prev));
  }, []);

  return { turns, isSending, error, sendMessage, clear, abort };
}
