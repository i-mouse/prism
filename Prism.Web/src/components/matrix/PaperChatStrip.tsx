import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ArrowUp, ChevronDown, ChevronUp, Copy, MessageCircle, RotateCw, Square } from "lucide-react";
import { toast } from "sonner";
import { useChatStream } from "@/hooks/useChatStream";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { ChatMarkdown, citeMarker, cursorMarker, type ChatCiteInfo } from "@/components/matrix/chat/ChatMarkdown";
import { ChatResizeHandle } from "@/components/matrix/chat/ChatResizeHandle";
import { DEFAULT_CHAT_HEIGHT, clampChatHeight } from "@/components/matrix/chat/chatHeight";
import { ChatBottomSheet, type SheetState } from "@/components/matrix/chat/ChatBottomSheet";
import type { ChatBlock, ChatTurn } from "@/types/chat";
import { cn } from "@/lib/utils";

interface PaperChatStripProps {
  chatId: string;
  activeFileId: string;
}

const SUGGESTED_PROMPTS = ["What are the main claims?", "Show me the strongest refusals"];
const CHAT_HEIGHT_STORAGE_KEY = "prism.chatHeight";

// Approximates "the agent declined to answer" from block shape alone —
// there's no explicit refusal flag on the wire, so this is a best-effort
// heuristic pending a real signal from the backend (post-V1).
const REFUSAL_PATTERN =
  /\b(can'?t|cannot|unable to|does(?:n't| not) (?:address|cover|mention|discuss)|outside (?:the )?scope|no (?:relevant )?(?:information|evidence))\b/i;

function useIsLgUp() {
  const [isLgUp, setIsLgUp] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches
  );

  useEffect(() => {
    const mql = window.matchMedia("(min-width: 1024px)");
    const handler = () => setIsLgUp(mql.matches);
    handler();
    mql.addEventListener("change", handler);
    // Some embedded/emulated viewports resize without firing the
    // MediaQueryList change event — window "resize" is a redundant but
    // harmless fallback that keeps the breakpoint switch reliable there.
    window.addEventListener("resize", handler);
    return () => {
      mql.removeEventListener("change", handler);
      window.removeEventListener("resize", handler);
    };
  }, []);

  return isLgUp;
}

function readStoredHeight(): number {
  if (typeof window === "undefined") return DEFAULT_CHAT_HEIGHT;
  const raw = window.localStorage.getItem(CHAT_HEIGHT_STORAGE_KEY);
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) ? clampChatHeight(parsed) : DEFAULT_CHAT_HEIGHT;
}

type ClaimReferenceBlock = Extract<ChatBlock, { type: "claim_reference" }>;

function turnToPlainText(turn: ChatTurn): string {
  return turn.blocks
    .map((b) => (b.type === "text" ? b.content : b.claim_summary))
    .join(" ")
    .trim();
}

// Reassembles the block stream into ONE continuous markdown string (citations
// become inline `![](cite:<id>)` markers, see ChatMarkdown.tsx) instead of
// mounting a separate <ChatMarkdown> per TextBlock — the backend splits text
// at every citation, and parsing each fragment in isolation shatters markdown
// structures (lists, paragraphs) that span across a citation.
function turnToMarkdown(turn: ChatTurn, showCursor: boolean): string {
  const body = turn.blocks.map((b) => (b.type === "text" ? b.content : citeMarker(b.claim_id))).join("");
  return showCursor ? body + cursorMarker() : body;
}

function claimsById(turn: ChatTurn): Record<string, ChatCiteInfo> {
  const map: Record<string, ChatCiteInfo> = {};
  for (const b of turn.blocks) {
    if (b.type === "claim_reference") {
      map[b.claim_id] = { claim_summary: b.claim_summary, display_label: b.display_label };
    }
  }
  return map;
}

function followUpsFor(turn: ChatTurn): string[] {
  const claimRefs = turn.blocks.filter((b): b is ClaimReferenceBlock => b.type === "claim_reference");
  if (claimRefs.length > 0) {
    return ["Explain further", "Why were those claims refused?"];
  }
  const text = turn.blocks
    .filter((b): b is Extract<ChatBlock, { type: "text" }> => b.type === "text")
    .map((b) => b.content)
    .join(" ");
  if (REFUSAL_PATTERN.test(text)) {
    return ["What CAN this paper answer?", "Show me the main claims"];
  }
  return ["Which claims support this?", "Show me the evidence"];
}

function PrismAvatar() {
  return (
    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border border-brand/20 bg-brand-subtle">
      <div className="h-2 w-2 rotate-45 rounded-sm bg-brand" />
    </div>
  );
}

export function PaperChatStrip({ chatId, activeFileId }: PaperChatStripProps) {
  const { turns, isSending, error, sendMessage, abort } = useChatStream(chatId, activeFileId);
  const { highlightClaim } = useSelectedClaim();
  const isLgUp = useIsLgUp();

  const [chatHeight, setChatHeight] = useState(readStoredHeight);
  const panelRef = useRef<HTMLDivElement>(null);
  const [sheetState, setSheetState] = useState<SheetState>("peek");
  // Collapsing never unmounts this component (or the useChatStream hook
  // above), so turns/scroll state survives a collapse/reopen cycle — see
  // the "chat collapse" task. Default true: additive, no behavior change
  // for users who never touch the toggle.
  const [isChatOpen, setIsChatOpen] = useState(true);

  const handleHeightChange = (h: number) => {
    setChatHeight(h);
    window.localStorage.setItem(CHAT_HEIGHT_STORAGE_KEY, String(h));
  };

  const handleClaimClick = (claimId: string) => {
    highlightClaim(claimId);
    const rowEl = document.querySelector(`[data-claim-id="${claimId}"]`);
    if (rowEl) rowEl.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const handleCopy = async (turn: ChatTurn) => {
    try {
      await navigator.clipboard.writeText(turnToPlainText(turn));
      toast("Copied");
    } catch {
      toast("Could not copy");
    }
  };

  const handleRegenerate = () => toast("Regenerate coming soon");

  const handleInputFocus = () => {
    if (sheetState === "peek") setSheetState("half");
  };

  const inputRow = (
    <ChatInput
      onSend={sendMessage}
      onStop={abort}
      isSending={isSending}
      placeholder="Ask about this paper..."
      onFocus={!isLgUp ? handleInputFocus : undefined}
    />
  );

  const messages = (
    <MessageList
      turns={turns}
      error={error}
      isSending={isSending}
      onClaimClick={handleClaimClick}
      onCopy={handleCopy}
      onRegenerate={handleRegenerate}
      onFollowUp={sendMessage}
    />
  );

  if (isLgUp) {
    return (
      <div
        ref={panelRef}
        style={isChatOpen ? { height: chatHeight } : undefined}
        className="flex shrink-0 flex-col border-t border-hairline bg-surface"
      >
        {isChatOpen && <ChatResizeHandle panelRef={panelRef} height={chatHeight} onHeightChange={handleHeightChange} />}
        <div className="flex shrink-0 items-center justify-between px-4 py-2">
          <span className="font-sans text-sm font-semibold text-ink">Chat</span>
          <button
            type="button"
            onClick={() => setIsChatOpen((v) => !v)}
            aria-label={isChatOpen ? "Collapse chat" : "Expand chat"}
            title={isChatOpen ? "Collapse chat" : "Expand chat"}
            className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink"
          >
            {isChatOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        </div>
        {/* Hidden rather than unmounted so scroll position and any unsent
            draft in ChatInput survive a collapse/reopen cycle. */}
        <div className={cn("flex min-h-0 flex-1 flex-col", !isChatOpen && "hidden")}>
          {messages}
          {inputRow}
        </div>
      </div>
    );
  }

  const bottomContent = (
    <div className="border-t border-hairline pt-1">
      {turns.length === 0 && (
        <div className="flex flex-wrap justify-center gap-2 px-4 pb-1 pt-1">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => sendMessage(prompt)}
              className="rounded-full border border-hairline bg-surface px-3 py-1 font-sans text-xs text-ink-secondary transition-colors hover:border-brand hover:text-brand"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
      {inputRow}
    </div>
  );

  if (!isChatOpen) {
    return createPortal(
      <button
        type="button"
        onClick={() => setIsChatOpen(true)}
        aria-label="Open chat"
        title="Open chat"
        className="fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-brand text-white shadow-drawer transition-transform hover:scale-105 lg:hidden"
      >
        <MessageCircle className="h-5 w-5" />
      </button>,
      document.body
    );
  }

  return (
    <ChatBottomSheet
      state={sheetState}
      onStateChange={setSheetState}
      bottomContent={bottomContent}
      onRequestClose={() => setIsChatOpen(false)}
    >
      {messages}
    </ChatBottomSheet>
  );
}

function MessageList({
  turns,
  error,
  isSending,
  onClaimClick,
  onCopy,
  onRegenerate,
  onFollowUp,
}: {
  turns: ChatTurn[];
  error: string | null;
  isSending: boolean;
  onClaimClick: (claimId: string) => void;
  onCopy: (turn: ChatTurn) => void;
  onRegenerate: () => void;
  onFollowUp: (prompt: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef(true);
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);
  const prevTurnCountRef = useRef(turns.length);

  useEffect(() => {
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        isAtBottomRef.current = entry.isIntersecting;
        if (entry.isIntersecting) setShowJumpToBottom(false);
      },
      { root, rootMargin: "0px 0px 100px 0px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const grew = turns.length !== prevTurnCountRef.current;
    prevTurnCountRef.current = turns.length;
    if (!grew && turns.length === 0) return;

    if (isAtBottomRef.current) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    } else if (turns.length > 0) {
      setShowJumpToBottom(true);
    }
  }, [turns]);

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setShowJumpToBottom(false);
  };

  if (turns.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-4 py-8">
        <div className="flex max-w-lg flex-wrap justify-center gap-2">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onFollowUp(prompt)}
              className="rounded-full border border-hairline bg-surface px-4 py-1.5 font-sans text-sm text-ink-secondary transition-colors hover:border-brand hover:text-brand"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-3">
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <UserTurnBubble key={i} turn={turn} />
          ) : (
            <AssistantTurn
              key={i}
              turn={turn}
              isLast={i === turns.length - 1}
              isSending={isSending}
              onClaimClick={onClaimClick}
              onCopy={() => onCopy(turn)}
              onRegenerate={onRegenerate}
              onFollowUp={onFollowUp}
            />
          )
        )}
        {error && <div className="px-1 text-sm text-refused">{error}</div>}
        <div ref={sentinelRef} className="h-px w-full" />
      </div>

      {showJumpToBottom && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="absolute bottom-3 right-4 rounded-full bg-brand px-3 py-1.5 font-sans text-xs text-white shadow-sm transition-opacity hover:opacity-90"
        >
          ↓ New message
        </button>
      )}
    </div>
  );
}

function UserTurnBubble({ turn }: { turn: ChatTurn }) {
  const text = turn.blocks.map((b) => (b.type === "text" ? b.content : "")).join("");
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-brand-subtle px-4 py-2.5 font-sans text-sm text-ink leading-relaxed">{text}</div>
    </div>
  );
}

function AssistantTurn({
  turn,
  isLast,
  isSending,
  onClaimClick,
  onCopy,
  onRegenerate,
  onFollowUp,
}: {
  turn: ChatTurn;
  isLast: boolean;
  isSending: boolean;
  onClaimClick: (claimId: string) => void;
  onCopy: () => void;
  onRegenerate: () => void;
  onFollowUp: (prompt: string) => void;
}) {
  const isThinking = isSending && turn.isStreaming && turn.blocks.length === 0;
  const isDone = !turn.isStreaming && turn.blocks.length > 0;
  const isStreamingWithContent = turn.isStreaming && turn.blocks.length > 0;
  const showFollowUps = isLast && isDone;
  const showCursor = !!turn.isStreaming && isLast;

  if (isThinking) {
    return (
      <div className="flex gap-3">
        <PrismAvatar />
        <div className="flex items-center gap-1.5 pt-1.5">
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-tertiary" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-tertiary" style={{ animationDelay: "150ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-tertiary" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="group flex gap-3">
        <PrismAvatar />
        <div
          className="min-w-0 flex-1 [contain:layout_paint]"
          style={isStreamingWithContent ? { minHeight: "1.5em" } : undefined}
        >
          <div className="font-sans text-sm text-ink">
            <ChatMarkdown
              content={turnToMarkdown(turn, showCursor)}
              claimsById={claimsById(turn)}
              onClaimClick={onClaimClick}
            />
          </div>

          {isDone && (
            <div className="mt-2 flex items-center gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
              <button
                type="button"
                onClick={onCopy}
                title="Copy"
                className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={onRegenerate}
                title="Regenerate"
                className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink"
              >
                <RotateCw className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {showFollowUps && (
        <div className="ml-9 mt-3 flex flex-wrap gap-2">
          {followUpsFor(turn).map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onFollowUp(prompt)}
              className="rounded-full border border-hairline bg-surface px-4 py-1.5 font-sans text-sm text-ink-secondary transition-colors hover:border-brand hover:text-brand"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ChatInput({
  onSend,
  onStop,
  isSending,
  placeholder,
  onFocus,
}: {
  onSend: (message: string) => void;
  onStop: () => void;
  isSending: boolean;
  placeholder: string;
  onFocus?: () => void;
}) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    }
  };

  const handleSubmit = () => {
    const trimmed = message.trim();
    if (!trimmed || isSending) return;
    onSend(trimmed);
    setMessage("");
    const el = textareaRef.current;
    if (el) el.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends (Ctrl/Cmd+Enter still does too, for existing muscle
    // memory); Shift+Enter inserts a newline instead. isComposing guards
    // IME input (e.g. Japanese) where Enter confirms a candidate rather
    // than submitting the message.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="shrink-0 px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] lg:px-6 lg:pb-4 lg:pt-3">
      <div
        className={cn(
          "flex w-full items-end gap-2 rounded-full border border-hairline bg-surface px-5 py-3",
          "transition-all duration-150",
          "focus-within:border-brand focus-within:ring-2 focus-within:ring-brand-subtle"
        )}
      >
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={onFocus}
          placeholder={placeholder}
          disabled={isSending}
          rows={1}
          className={cn(
            "max-h-24 flex-1 resize-none overflow-y-auto bg-transparent",
            "font-sans text-sm text-ink placeholder:text-ink-tertiary",
            "focus:outline-none"
          )}
        />
        {isSending ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-surface transition-all hover:bg-ink-secondary"
          >
            <Square className="h-3 w-3" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!message.trim()}
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-100",
              "bg-brand text-white hover:bg-brand-hover active:scale-95",
              "disabled:cursor-not-allowed disabled:bg-hairline disabled:text-ink-tertiary disabled:hover:bg-hairline"
            )}
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
