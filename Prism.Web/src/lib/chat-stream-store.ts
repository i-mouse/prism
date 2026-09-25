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
// (Unchanged from useChatStream.ts, only relocated here.)
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

// Flattens a turn back to the plain string the backend would have persisted
// for it. Only meaningful for USER turns here (a single text block, either
// typed by the user or restored from history), which is all the recovery
// anchor below needs - an assistant turn's blocks are not comparable to
// persisted text, see recoverTurn.
function turnPlainText(turn: ChatTurn): string {
  return turn.blocks.map((b) => (b.type === "text" ? b.content : "")).join("");
}

// Shape returned by GET /api/chat/{chatId}/history (Prism.PythonService/api.py,
// get_chat_history) - flattened plain-text messages from the LangGraph
// checkpoint, role "ai"/"user" rather than the frontend's "assistant"/"user".
// Historical messages carry no claim_reference block structure (the history
// endpoint only ever serializes plain content), so they're restored as
// plain-text blocks - only messages from the live SSE stream in the current
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

function historyToTurns(messages: HistoryMessage[]): ChatTurn[] {
  return messages.map((m): ChatTurn => ({
    id: crypto.randomUUID(),
    role: m.role === "ai" ? "assistant" : "user",
    blocks: [{ type: "text", content: m.content }],
    timestamp: Date.now(),
  }));
}

// "empty" - no /history load has succeeded for this chat yet. Also the state
//           a FAILED load falls back to, so a transient failure retries on
//           the next visit instead of caching the chat as loaded.
// "ready" - history loaded (a legitimately empty chat included).
export type HistoryStatus = "empty" | "ready";

export interface ChatStreamEntry {
  turns: ChatTurn[];
  isSending: boolean;
  error: string | null;
  historyStatus: HistoryStatus;
}

// Why a user-initiated stop is distinguished from every other way a stream
// can end: it is the one ending where the user asked for the partial answer
// to stand, so it must NOT trigger the recovery re-fetch that would quietly
// complete the answer they just stopped.
type AbortReason = "user" | "superseded" | "recovered";

const NO_TURNS: ChatTurn[] = [];
const EMPTY_ENTRY: ChatStreamEntry = {
  turns: NO_TURNS,
  isSending: false,
  error: null,
  historyStatus: "empty",
};

export type ChatStreamStore = ReturnType<typeof createChatStreamStore>;

// One store per mounted MatrixView, owning every paper-scoped chat stream in
// that view. Deliberately NOT React state: MatrixView re-renders on every
// claims/paper change and PaperChatStrip remounts on every chat switch, and
// neither event may disturb a stream in flight. Subscribers read it through
// useSyncExternalStore (see useChatStream.ts), which also keeps token-rate
// re-renders scoped to the chat strip instead of re-rendering MatrixView's
// whole claims table on every SSE frame.
export function createChatStreamStore() {
  const entries = new Map<string, ChatStreamEntry>();
  // One AbortController per chatId, never more. Deleted the moment its
  // stream ends by any route - done frame, error frame, thrown error, or
  // abort - so the map never accumulates dead controllers.
  const controllers = new Map<string, AbortController>();
  // The assistant turn currently being streamed for a chat, so an abort or a
  // tab-return recovery can find it by id rather than positionally.
  const inFlight = new Map<string, { turnId: string; stoppedByUser: boolean }>();
  // Turns whose stream ended abnormally and whose real answer must still be
  // pulled from /history. Retried on chat mount and on tab return - both
  // events, never a timer, so this introduces no polling.
  const pendingRecovery = new Map<string, string>();
  // Synchronous guard shared by both /history entry points (initial load and
  // recovery) so they can never fire two overlapping fetches for one chat.
  // A plain Set rather than an entry field: it must be settable without
  // emitting, since both callers run inside an effect body.
  const historyFetches = new Set<string>();
  const listeners = new Set<() => void>();
  let disposed = false;

  function emit() {
    for (const listener of listeners) listener();
  }

  function getEntry(chatId: string | null): ChatStreamEntry {
    if (!chatId) return EMPTY_ENTRY;
    return entries.get(chatId) ?? EMPTY_ENTRY;
  }

  function getHistoryStatus(chatId: string | null): HistoryStatus {
    return getEntry(chatId).historyStatus;
  }

  // Referential stability matters here: useSyncExternalStore re-renders
  // whenever getSnapshot returns a new object, so an entry is only replaced
  // when a field actually changed.
  function patch(chatId: string, next: Partial<ChatStreamEntry>) {
    const prev = getEntry(chatId);
    const merged: ChatStreamEntry = { ...prev, ...next };
    if (
      merged.turns === prev.turns &&
      merged.isSending === prev.isSending &&
      merged.error === prev.error &&
      merged.historyStatus === prev.historyStatus
    ) {
      return;
    }
    entries.set(chatId, merged);
    emit();
  }

  // Every stream mutation routes through here, addressed by chatId. Combined
  // with the by-id turn helpers above, a frame can only ever land on the turn
  // of the chat it belongs to - no cross-chat bleed even while two chats
  // stream at once.
  function updateTurns(chatId: string, fn: (turns: ChatTurn[]) => ChatTurn[]) {
    patch(chatId, { turns: fn(getEntry(chatId).turns) });
  }

  function subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }

  // Condition (b) of the fix: an assistant turn still marked isStreaming is
  // NOT settled state, so it can never count as a cache hit that suppresses
  // /history. A turn streaming because a stream is genuinely live is excluded
  // - re-fetching there would clobber the tokens still arriving.
  function needsHistory(chatId: string): boolean {
    if (historyFetches.has(chatId)) return false;
    const entry = getEntry(chatId);
    if (entry.historyStatus === "empty") return true;
    if (controllers.has(chatId)) return false;
    return entry.turns.some((t) => t.role === "assistant" && t.isStreaming);
  }

  async function loadHistory(chatId: string): Promise<void> {
    if (disposed || !needsHistory(chatId)) return;

    // Anything already on screen when the fetch starts. Turns appended while
    // it is in flight (a send fired before history landed) are re-appended
    // after the restored history below rather than overwritten by it - the
    // previous implementation dropped them.
    const baseline = getEntry(chatId).turns;
    historyFetches.add(chatId);

    let messages: HistoryMessage[] | null = null;
    try {
      messages = await fetchHistoryMessages(chatId);
    } catch {
      messages = null;
    } finally {
      historyFetches.delete(chatId);
    }
    if (disposed) return;

    // null = fetch failed (see fetchHistoryMessages) - deliberately leaves
    // historyStatus at "empty", so a transient failure retries on the next
    // visit instead of permanently caching this chat as loaded.
    if (messages === null) return;

    const current = getEntry(chatId).turns;
    const appended = current.slice(baseline.length);
    patch(chatId, { turns: [...historyToTurns(messages), ...appended], historyStatus: "ready" });
    // History is authoritative, so nothing is left to recover for this chat.
    pendingRecovery.delete(chatId);
  }

  // Surgical counterpart to loadHistory for a turn whose stream ended
  // abnormally: replaces only the broken turn's blocks with the persisted
  // answer, leaving every healthy turn's live block structure (and therefore
  // its citation pills) intact, which a wholesale history reload flattens.
  //
  // The persisted answer is located by ANCHORING ON THE PROMPT, not by
  // counting assistant turns. An ordinal is unsound in two real cases: a send
  // that happened before /history loaded leaves the client holding fewer
  // turns than the server (so ordinal 0 would resolve to the chat's oldest
  // answer), and a client-side assistant turn the server never persisted (a
  // failed request, an error frame) shifts every later ordinal by one and can
  // paint one answer into a different question's turn. The prompt text is the
  // only thing both sides agree on verbatim.
  async function recoverTurn(chatId: string): Promise<void> {
    const turnId = pendingRecovery.get(chatId);
    if (disposed || !turnId || historyFetches.has(chatId)) return;

    const turns = getEntry(chatId).turns;
    const idx = turns.findIndex((t) => t.id === turnId);
    if (idx === -1) {
      pendingRecovery.delete(chatId);
      return;
    }

    // The question this broken answer belongs to. Scanning back rather than
    // assuming idx-1 so an interleaved turn can't break the anchor.
    let promptText: string | null = null;
    for (let i = idx - 1; i >= 0; i--) {
      if (turns[i].role === "user") {
        promptText = turnPlainText(turns[i]);
        break;
      }
    }
    // No prompt to anchor on at all - structurally unrecoverable, so drop it
    // rather than leave it queued to retry forever on every mount. The turn
    // itself is already marked done by sendMessage's `finally`, so this
    // leaves no caret behind.
    if (promptText === null) {
      pendingRecovery.delete(chatId);
      return;
    }

    historyFetches.add(chatId);
    let messages: HistoryMessage[] | null = null;
    try {
      messages = await fetchHistoryMessages(chatId);
    } catch {
      messages = null;
    } finally {
      historyFetches.delete(chatId);
    }
    if (disposed || !messages) return;

    // Searched from the END: the same question may have been asked more than
    // once in a chat, and the one being recovered is always the most recent.
    let anchor = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user" && messages[i].content === promptText) {
        anchor = i;
        break;
      }
    }
    // Backend only ever writes a chat message once generation is fully
    // complete (Prism.PythonService/api.py, _run_paper_chat_graph), so a
    // missing question - or a question with no answer after it yet - simply
    // means the run hasn't finished. Stay in pendingRecovery and get retried
    // on the next chat mount or tab return.
    if (anchor === -1) return;
    const answer = messages.slice(anchor + 1).find((m) => m.role === "ai");
    if (!answer) return;

    pendingRecovery.delete(chatId);
    updateTurns(chatId, (current) => {
      const i = current.findIndex((t) => t.id === turnId);
      if (i === -1) return current;
      const recovered: ChatTurn = {
        ...current[i],
        blocks: [{ type: "text", content: answer.content }],
        isStreaming: false,
      };
      return [...current.slice(0, i), recovered, ...current.slice(i + 1)];
    });

    // Recovered a turn whose stream is still nominally open (the frozen-tab
    // case below): its connection is dead as far as this client is concerned,
    // so close it out rather than leaving a controller hanging in the map.
    if (inFlight.get(chatId)?.turnId === turnId) {
      abort(chatId, "recovered");
    }
  }

  function retryRecovery(chatId: string): void {
    void recoverTurn(chatId);
  }

  // Tab-return recovery, relocated from useChatStream.ts's visibilitychange
  // effect. Covers both a stream that already ended abnormally while hidden
  // and one still nominally in flight whose connection the browser killed
  // when it froze the background tab (the original case): the backend keeps
  // running the chat graph and persists the answer regardless of the SSE
  // connection's fate, so the true answer is always recoverable from history.
  function retryPendingRecovery(): void {
    for (const [chatId, tracked] of inFlight) {
      const turn = getEntry(chatId).turns.find((t) => t.id === tracked.turnId);
      if (turn?.isStreaming) pendingRecovery.set(chatId, tracked.turnId);
    }
    for (const chatId of [...pendingRecovery.keys()]) void recoverTurn(chatId);
  }

  function abort(chatId: string, reason: AbortReason = "user"): void {
    const tracked = inFlight.get(chatId);
    if (tracked && (reason === "user" || reason === "recovered")) {
      // Suppresses the abnormal-end recovery re-fetch in sendMessage's
      // `finally`: a user stop means the partial answer stands, and a
      // recovered turn already holds the persisted one.
      tracked.stoppedByUser = true;
      // Stops the caret the instant the user clicks Stop rather than waiting
      // for the catch/finally chain below to unwind asynchronously.
      updateTurns(chatId, (turns) => markTurnDone(turns, tracked.turnId));
    }
    controllers.get(chatId)?.abort();
  }

  async function sendMessage(chatId: string, activeFileId: string, message: string): Promise<void> {
    if (disposed || !chatId || !activeFileId || !message.trim()) return;

    // Supersedes an earlier send on THIS chat only. Streams on every other
    // chat are untouched - that separation is the whole point of keying
    // controllers by chatId.
    abort(chatId, "superseded");

    const controller = new AbortController();
    controllers.set(chatId, controller);
    const assistantTurnId = crypto.randomUUID();
    inFlight.set(chatId, { turnId: assistantTurnId, stoppedByUser: false });

    const prev = getEntry(chatId);
    patch(chatId, {
      error: null,
      isSending: true,
      turns: [
        ...prev.turns,
        { id: crypto.randomUUID(), role: "user", blocks: [{ type: "text", content: message }], timestamp: Date.now() },
        { id: assistantTurnId, role: "assistant", blocks: [], timestamp: Date.now(), isStreaming: true },
      ],
    });

    // Whether a closing "done"/"error" frame was actually seen. Its absence
    // is what distinguishes an abnormal end (needing recovery) from a clean
    // one, and it cannot be inferred from the turn state alone.
    let sawTerminalFrame = false;

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
            updateTurns(chatId, (turns) => appendTextToTurn(turns, assistantTurnId, frame.content));
          } else if (frame.type === "claim_reference") {
            updateTurns(chatId, (turns) =>
              appendBlockToTurn(turns, assistantTurnId, {
                type: "claim_reference",
                claim_id: frame.claim_id,
                claim_summary: frame.claim_summary,
                display_label: frame.display_label,
              })
            );
          } else if (frame.type === "error") {
            sawTerminalFrame = true;
            patch(chatId, { error: frame.message });
            updateTurns(chatId, (turns) => markTurnDone(turns, assistantTurnId));
          } else if (frame.type === "done") {
            sawTerminalFrame = true;
            updateTurns(chatId, (turns) => markTurnDone(turns, assistantTurnId));
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        patch(chatId, { error: err instanceof Error ? err.message : "Chat request failed" });
      }
      // An AbortError falls through to `finally` - a non-user-initiated abort
      // (the browser killing a frozen background tab's fetch) still needs
      // isStreaming resolved, same as any other abnormal end.
    } finally {
      // Controller removed the instant this stream ends, however it ended.
      // Guarded on identity so a newer send that already replaced it keeps
      // its own controller (and its own isSending).
      if (controllers.get(chatId) === controller) {
        controllers.delete(chatId);
        patch(chatId, { isSending: false });
      }
      // Condition (a) of the fix: a turn is never left marked isStreaming
      // once its stream is over. This runs in the store, which outlives the
      // chat strip's remount, so unlike the old in-hook version it can no
      // longer be dropped as a setState on an unmounted component.
      updateTurns(chatId, (turns) => markTurnDone(turns, assistantTurnId));

      const tracked = inFlight.get(chatId);
      // Only act on the tracking slot if it still points at THIS send's turn
      // - a newer send may already have taken it over.
      if (tracked && tracked.turnId === assistantTurnId) {
        inFlight.delete(chatId);
        if (sawTerminalFrame) {
          pendingRecovery.delete(chatId);
        } else if (!tracked.stoppedByUser && !disposed) {
          // Ended with no closing frame (thrown error, dropped connection, or
          // the body simply ending - e.g. the backend's is_disconnected()
          // check skipping the final "done" frame). The answer is still being
          // persisted server-side, so pull it from /history once.
          pendingRecovery.set(chatId, assistantTurnId);
          void recoverTurn(chatId);
        }
      }
    }
  }

  // Resets a chat's entry entirely. No call site today - kept only at parity
  // with the hook's previous `clear` (see useChatStream.ts).
  function clear(chatId: string): void {
    abort(chatId, "user");
    pendingRecovery.delete(chatId);
    patch(chatId, { turns: NO_TURNS, isSending: false, error: null, historyStatus: "empty" });
  }

  // Called only when the owning component tree unmounts. Reversible via
  // activate() so React StrictMode's dev-mode mount/cleanup/remount cycle
  // cannot leave a permanently dead store behind.
  function dispose(): void {
    disposed = true;
    for (const controller of controllers.values()) controller.abort();
  }

  function activate(): void {
    disposed = false;
  }

  return {
    subscribe,
    getEntry,
    getHistoryStatus,
    sendMessage,
    abort,
    clear,
    loadHistory,
    retryRecovery,
    retryPendingRecovery,
    dispose,
    activate,
  };
}
