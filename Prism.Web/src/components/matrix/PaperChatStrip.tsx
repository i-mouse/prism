import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ArrowUp, ChevronDown, Copy, MessageCircle, RotateCw, Square, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useChatStream } from "@/hooks/useChatStream";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { ChatMarkdown, citeMarker, cursorMarker, type ChatCiteInfo } from "@/components/matrix/chat/ChatMarkdown";
import { ChatBottomSheet, type SheetState } from "@/components/matrix/chat/ChatBottomSheet";
import type { ChatBlock, ChatTurn } from "@/types/chat";
import { cn } from "@/lib/utils";

interface PaperChatStripProps {
  chatId: string;
  activeFileId: string;
  fileName?: string;
}

const SUGGESTED_PROMPTS = ["What are the main claims?", "Show me the strongest refusals"];

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

export function PaperChatStrip({ chatId, activeFileId, fileName }: PaperChatStripProps) {
  const { turns, isSending, error, sendMessage, abort } = useChatStream(chatId, activeFileId);
  const { highlightClaim } = useSelectedClaim();
  const isLgUp = useIsLgUp();
  const [sheetState, setSheetState] = useState<SheetState>("peek");
  // Default to false for the new pill layout so it pops up nicely
  const [isChatOpen, setIsChatOpen] = useState(false);

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
    if (!isLgUp && sheetState === "peek") setSheetState("half");
    if (isLgUp) setIsChatOpen(true);
  };

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

  const [chatHeight, setChatHeight] = useState(400);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = chatHeight;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      // Invert delta because dragging UP increases height
      const deltaY = startY - moveEvent.clientY;
      const newHeight = Math.max(200, Math.min(startHeight + deltaY, window.innerHeight * 0.8));
      setChatHeight(newHeight);
    };

    const handleMouseUp = () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  if (isLgUp) {
    return (
      <div className="px-3 pb-4 pt-2 md:px-6 md:pb-5 relative">
        <div
          className={cn(
            "overflow-hidden transition-all duration-300 ease-in-out rounded-2xl border border-slate-200 shadow-sm bg-slate-50",
            isChatOpen ? "max-h-[80vh] opacity-100 mb-4" : "max-h-0 opacity-0 border-transparent shadow-none"
          )}
        >
          <div style={{ height: isChatOpen ? chatHeight : 0 }} className="w-full flex flex-col relative transition-none">
            <div 
              className="w-full h-4 cursor-ns-resize flex items-center justify-center bg-slate-50 hover:bg-slate-100 border-b border-slate-200 rounded-t-2xl shrink-0" 
              onMouseDown={handleMouseDown}
            >
              <div className="w-10 h-1 bg-slate-300 rounded-full" />
            </div>
            <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-4 py-3 bg-white">
              <div className="flex items-center gap-2">
                <MessageCircle className="h-4 w-4 text-slate-500" />
                <span className="font-sans text-sm font-semibold text-slate-800">
                  {fileName ? `Chat — ${fileName}` : "Chat"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsChatOpen(false)}
                className="flex h-6 w-6 items-center justify-center rounded-full text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
                aria-label="Close chat"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0 pb-20">
              {messages}
            </div>
          </div>
        </div>

        <div className={cn("relative z-50 transition-all duration-300", isChatOpen ? "absolute bottom-8 left-10 right-10" : "")}>
          <ChatInput
            onSend={sendMessage}
            onStop={abort}
            isSending={isSending}
            placeholder={fileName ? `Ask about this paper (${fileName})...` : "Ask about this paper..."}
            onFocus={handleInputFocus}
            isChatOpen={isChatOpen}
            setIsChatOpen={setIsChatOpen}
            isLgUp={isLgUp}
          />
        </div>
        
        <p className="mt-1.5 text-center font-sans text-[11px] text-slate-400">
          Get answers, ask for clarification, or explore specific claims from this paper.
        </p>
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
      <ChatInput
        onSend={sendMessage}
        onStop={abort}
        isSending={isSending}
        placeholder="Ask about this paper..."
        onFocus={!isLgUp ? handleInputFocus : undefined}
      />
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
      <div className="bg-slate-800 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-[80%] text-sm">
        {text}
      </div>
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
  const showFollowUps = isLast && isDone;
  const showCursor = !!turn.isStreaming && isLast;

  if (isThinking) {
    return (
      <div className="flex gap-3">
        <Sparkles className="h-6 w-6 text-red-500 mt-1 shrink-0" />
        <div className="flex items-center gap-1.5 pt-1.5">
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-slate-400" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-slate-400" style={{ animationDelay: "150ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-slate-400" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="group flex gap-3">
        <Sparkles className="h-6 w-6 text-red-500 mt-1 shrink-0" />
        <div className="bg-white border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3 max-w-[85%] text-sm text-slate-800 prose prose-sm prose-slate space-y-3 whitespace-pre-wrap max-w-none [contain:layout_paint]">
          <ChatMarkdown
            content={turnToMarkdown(turn, showCursor)}
            claimsById={claimsById(turn)}
            onClaimClick={onClaimClick}
          />

          {isDone && (
            <div className="mt-2 flex items-center gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
              <button
                type="button"
                onClick={onCopy}
                title="Copy"
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={onRegenerate}
                title="Regenerate"
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
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
  isChatOpen,
  setIsChatOpen,
  isLgUp,
}: {
  onSend: (message: string) => void;
  onStop: () => void;
  isSending: boolean;
  placeholder: string;
  onFocus?: () => void;
  isChatOpen?: boolean;
  setIsChatOpen?: (open: boolean | ((prev: boolean) => boolean)) => void;
  isLgUp?: boolean;
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
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (isLgUp && setIsChatOpen !== undefined && isChatOpen !== undefined) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 shadow-lg transition-shadow duration-150 z-50",
          "focus-within:border-slate-300 focus-within:shadow-xl"
        )}
        onClick={() => textareaRef.current?.focus()}
      >
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsChatOpen((v) => !v);
          }}
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-slate-100"
          aria-label={isChatOpen ? "Close chat" : "Open chat"}
          title={isChatOpen ? "Close chat" : "Open chat"}
        >
          <Sparkles className="h-4 w-4 text-red-500" strokeWidth={1.5} />
        </button>

        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={onFocus}
          placeholder={placeholder}
          disabled={isSending}
          rows={1}
          className="flex-1 min-w-0 resize-none overflow-y-auto bg-transparent font-sans text-sm text-slate-800 placeholder:text-slate-400 outline-none disabled:opacity-60 max-h-24 pt-0.5"
        />

        {isSending ? (
          <button
            type="button"
            onClick={onStop}
            className="flex shrink-0 items-center justify-center rounded-xl bg-slate-800 text-white shadow-sm transition-all hover:bg-slate-900 p-2"
          >
            <Square className="h-4 w-4" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleSubmit();
            }}
            disabled={!message.trim()}
            className={cn(
              "flex shrink-0 items-center justify-center rounded-xl transition-all duration-150 p-2",
              message.trim() && !isSending
                ? "bg-slate-800 text-white hover:bg-slate-900 shadow-sm"
                : "bg-slate-100 text-slate-400 cursor-not-allowed"
            )}
            aria-label="Send"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="shrink-0 px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] lg:px-6 lg:pb-4 lg:pt-3">
      <div
        className={cn(
          "flex w-full items-end gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 shadow-sm",
          "transition-all duration-150",
          "focus-within:border-slate-300 focus-within:shadow-md"
        )}
      >
        <div className="flex h-6 w-6 shrink-0 items-center justify-center mb-1">
          <Sparkles className="h-4 w-4 text-red-500" strokeWidth={1.5} />
        </div>
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
            "max-h-24 flex-1 resize-none overflow-y-auto bg-transparent mb-1",
            "font-sans text-sm text-slate-800 placeholder:text-slate-400 outline-none"
          )}
        />
        {isSending ? (
          <button
            type="button"
            onClick={onStop}
            className="flex shrink-0 items-center justify-center rounded-xl bg-slate-800 text-white shadow-sm transition-all hover:bg-slate-900 p-2"
          >
            <Square className="h-4 w-4" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!message.trim()}
            className={cn(
              "flex shrink-0 items-center justify-center rounded-xl transition-all duration-150 p-2",
              message.trim() && !isSending
                ? "bg-slate-800 text-white hover:bg-slate-900 shadow-sm"
                : "bg-slate-100 text-slate-400 cursor-not-allowed"
            )}
            aria-label="Send"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
