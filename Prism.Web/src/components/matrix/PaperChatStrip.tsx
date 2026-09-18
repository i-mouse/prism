import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ArrowUp, ChevronDown, Copy, MessageCircle, Square, ThumbsUp, ThumbsDown } from "lucide-react";
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
  onFollowUp,
}: {
  turns: ChatTurn[];
  error: string | null;
  isSending: boolean;
  onClaimClick: (claimId: string) => void;
  onCopy: (turn: ChatTurn) => void;
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
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto bg-slate-50 p-6 pb-40">
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
    <div className="flex justify-end gap-3 items-start">
      <div className="flex flex-col items-end max-w-[80%]">
        <div className="bg-[#fdf2ece6] text-slate-900 rounded-2xl rounded-tr-sm px-5 py-4 text-sm shadow-sm">
          {text}
        </div>
        <div className="text-[10px] text-slate-400 mt-1.5 mr-1 font-medium">
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      <div className="bg-slate-800 text-white w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 shadow-sm">
        N
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
  onFollowUp,
}: {
  turn: ChatTurn;
  isLast: boolean;
  isSending: boolean;
  onClaimClick: (claimId: string) => void;
  onCopy: () => void;
  onFollowUp: (prompt: string) => void;
}) {
  const isThinking = isSending && turn.isStreaming && turn.blocks.length === 0;
  const isDone = !turn.isStreaming && turn.blocks.length > 0;
  const showFollowUps = isLast && isDone;
  const showCursor = !!turn.isStreaming && isLast;

  if (isThinking) {
    return (
      <div className="flex gap-4">
        <GradientSparkle className="h-6 w-6 shrink-0 mt-1" />
        <div className="flex items-center gap-1.5 pt-1.5 bg-white border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm px-5 py-4">
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-slate-400" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-slate-400" style={{ animationDelay: "150ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-slate-400" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <div className="group flex gap-4">
        <div className="shrink-0 mt-2">
          <GradientSparkle className="h-6 w-6" />
        </div>
        <div className="flex flex-col w-full max-w-[85%]">
          <div className="bg-white border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm p-5 text-sm text-slate-800 prose prose-sm prose-slate max-w-none prose-headings:font-semibold prose-headings:text-slate-900 prose-p:leading-relaxed prose-a:text-blue-600 prose-li:marker:text-slate-400 [contain:layout_paint]">
            <ChatMarkdown
              content={turnToMarkdown(turn, showCursor)}
              claimsById={claimsById(turn)}
              onClaimClick={onClaimClick}
            />
          </div>

          {isDone && (
            <div className="mt-2 flex items-center justify-end gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 px-2">
              <span className="text-[10px] text-slate-400 mr-auto ml-1 font-medium">
                {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
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
                title="Helpful"
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                title="Not helpful"
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {showFollowUps && (
        <div className="ml-10 mt-3 flex flex-wrap gap-2">
          {followUpsFor(turn).map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onFollowUp(prompt)}
              className="rounded-full border border-slate-200 bg-white px-4 py-1.5 font-sans text-sm text-slate-600 shadow-sm transition-colors hover:border-slate-300 hover:text-slate-900"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const GradientSparkle = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="url(#sparkle-grad)" className={className}>
    <defs>
      <linearGradient id="sparkle-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop stopColor="#f97316" offset="0%" />
        <stop stopColor="#ec4899" offset="100%" />
      </linearGradient>
    </defs>
    <path d="M12 0C12 6.627 6.627 12 0 12C6.627 12 12 17.373 12 24C12 17.373 17.373 12 24 12C17.373 12 12 6.627 12 0Z" />
  </svg>
);

function ChatInput({
  onSend,
  onStop,
  isSending,
  placeholder,
  onFocus,
  isChatOpen,
  setIsChatOpen,
  isLgUp,
  fileName,
}: {
  onSend: (msg: string) => void;
  onStop: () => void;
  isSending: boolean;
  placeholder?: string;
  onFocus?: () => void;
  isChatOpen?: boolean;
  setIsChatOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  isLgUp?: boolean;
  fileName?: string;
}) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 96)}px`; // max-h-24
  };

  useEffect(() => {
    adjustHeight();
  }, [message]);

  const handleSubmit = () => {
    if (!message.trim() || isSending) return;
    onSend(message);
    setMessage("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (isLgUp && setIsChatOpen !== undefined && isChatOpen !== undefined) {
    return (
      <div className="flex flex-col items-center w-full">
        <div
          className={cn(
            "bg-white border border-slate-200 shadow-lg rounded-full px-4 py-2 flex items-center gap-3 w-full transition-shadow duration-150 z-50",
            "focus-within:border-slate-300 focus-within:shadow-xl"
          )}
          onClick={() => textareaRef.current?.focus()}
        >
          <GradientSparkle className="h-6 w-6 shrink-0" />

          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={onFocus}
            placeholder={placeholder}
            disabled={isSending}
            rows={1}
            className="flex-1 min-w-0 resize-none overflow-y-auto bg-transparent font-sans text-sm text-slate-900 placeholder:text-slate-400 outline-none disabled:opacity-60 max-h-24 pt-2.5"
          />

          <button className="text-slate-400 hover:text-slate-600 transition-colors p-2 shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          </button>

          {isSending ? (
            <button
              type="button"
              onClick={onStop}
              className="flex shrink-0 items-center justify-center rounded-full bg-slate-800 text-white shadow-md transition-all hover:bg-slate-900 w-10 h-10"
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
                "flex shrink-0 items-center justify-center rounded-full transition-all duration-150 w-10 h-10",
                message.trim() && !isSending
                  ? "bg-gradient-to-r from-orange-400 to-pink-500 text-white shadow-md hover:scale-105"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
              )}
              aria-label="Send"
            >
              <ArrowUp className="h-5 w-5" />
            </button>
          )}
        </div>
        <div className="text-xs text-slate-400 mt-3 text-center px-4">
          Responses are based only on the content of {fileName ?? "this paper"}. Always verify important information.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col border-t border-hairline bg-white pb-safe pt-2">
      <div className="flex items-end gap-2 px-3 pb-3">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={onFocus}
          placeholder={placeholder}
          disabled={isSending}
          rows={1}
          className="max-h-32 min-h-[40px] flex-1 resize-none overflow-y-auto rounded-2xl border border-hairline bg-surface-subtle px-4 py-2.5 font-sans text-sm text-ink placeholder:text-ink-tertiary focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand disabled:opacity-60"
        />
        {isSending ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ink text-white shadow-sm transition-opacity hover:opacity-90"
          >
            <Square className="h-4 w-4" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!message.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-800 text-white shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            <ArrowUp className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
