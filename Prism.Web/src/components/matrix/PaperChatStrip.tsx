import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ArrowUp, ChevronDown, Copy, MessageCircle, Square, ThumbsUp, ThumbsDown } from "lucide-react";
import { toast } from "sonner";
import { useChatStream } from "@/hooks/useChatStream";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { ChatMarkdown, citeMarker, cursorMarker, type ChatCiteInfo } from "@/components/matrix/chat/ChatMarkdown";
import { ChatBottomSheet, type SheetState } from "@/components/matrix/chat/ChatBottomSheet";
import type { ChatBlock, ChatTurn } from "@/types/chat";
import type { ClaimDto } from "@/types/api";
import { displayLabel } from "@/lib/claim-display";
import { cn } from "@/lib/utils";

interface PaperChatStripProps {
  chatId: string;
  activeFileId: string;
  fileName?: string;
  // Full claim list for the active paper (MatrixView already fetches this
  // for the claims table) - needed here so a citation marker can resolve
  // to a real pill even when it didn't arrive as a live claim_reference
  // block, e.g. a history-restored turn (see claimsById below).
  paperClaims: ClaimDto[];
  // Keyed by chatId, held by MatrixView (which doesn't remount on paper
  // switch) so a chat's scroll position survives this component's own
  // per-chat remount (key={activeChatId} in MatrixView). See MessageList.
  scrollPositions: React.RefObject<Map<string, number>>;
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

// The scrollable message list carries a large bottom padding (`pb-40`,
// see its className below) so the floating "jump to bottom" button and the
// composer never cover the last message - but that padding counts toward
// the container's own `scrollHeight`. Snapping to `scrollHeight` directly
// (as every "scroll to bottom" call here used to) overshoots into that
// padding, landing past the real last message - and sometimes even past
// its own follow-up buttons - into blank space instead of flush with them.
// Anchoring to the sentinel's bottom edge instead (a 1px marker placed
// immediately after the real content, before the padding - see sentinelRef
// below) reaches the same "scrolled to the true bottom" position without
// the overshoot.
function bottomScrollTop(root: HTMLElement, sentinel: HTMLElement): number {
  const rootRect = root.getBoundingClientRect();
  const sentinelRect = sentinel.getBoundingClientRect();
  const sentinelBottom = sentinelRect.bottom - rootRect.top + root.scrollTop;
  return Math.max(0, sentinelBottom - root.clientHeight);
}

type ClaimReferenceBlock = Extract<ChatBlock, { type: "claim_reference" }>;

function turnToPlainText(turn: ChatTurn): string {
  return turn.blocks
    .map((b) => (b.type === "text" ? b.content : b.claim_summary))
    .join(" ")
    .trim();
}

// A live turn's text blocks never contain this literally - the backend
// (Prism.PythonService/paper_chat/agent.py, generate_response) buffers its
// own [claim:<id>] markers out into separate claim_reference blocks before
// ever flushing a "text" block. But a history-restored turn (see
// useChatStream.ts's fetchHistoryMessages comment) IS just the model's raw
// saved content as a single text block, brackets and all - the backend only
// ever persists the flat string, never the block split. Converting any
// leftover raw marker here means both sources render the same way, instead
// of a reload/tab-return silently downgrading a citation to dead bracket
// text with no pill.
const RAW_CITATION_RE = /\[claim:([a-zA-Z0-9-]+)\]/g;

function convertRawCitations(text: string): string {
  return text.replace(RAW_CITATION_RE, (_match, claimId: string) => citeMarker(claimId));
}

// Reassembles the block stream into ONE continuous markdown string (citations
// become inline `![](cite:<id>)` markers, see ChatMarkdown.tsx) instead of
// mounting a separate <ChatMarkdown> per TextBlock — the backend splits text
// at every citation, and parsing each fragment in isolation shatters markdown
// structures (lists, paragraphs) that span across a citation.
function turnToMarkdown(turn: ChatTurn, showCursor: boolean): string {
  const body = turn.blocks
    .map((b) => (b.type === "text" ? convertRawCitations(b.content) : citeMarker(b.claim_id)))
    .join("");
  return showCursor ? body + cursorMarker() : body;
}

// Turn-scoped claim_reference blocks take priority (they carry the
// effective_status the backend actually verified for THIS answer), falling
// back to the full-paper map for a marker with no such block - which is
// every marker in a history-restored turn, per convertRawCitations above.
function claimsById(turn: ChatTurn, paperClaimsById: Record<string, ChatCiteInfo>): Record<string, ChatCiteInfo> {
  const map: Record<string, ChatCiteInfo> = { ...paperClaimsById };
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

export function PaperChatStrip({ chatId, activeFileId, fileName, paperClaims, scrollPositions }: PaperChatStripProps) {
  const { turns, isSending, error, sendMessage, abort } = useChatStream(chatId, activeFileId);
  const { highlightClaim } = useSelectedClaim();
  const isLgUp = useIsLgUp();
  const paperClaimsById = useMemo(() => {
    const map: Record<string, ChatCiteInfo> = {};
    for (const c of paperClaims) {
      map[c.id] = { claim_summary: c.claimSummary, display_label: displayLabel(c) };
    }
    return map;
  }, [paperClaims]);
  const [sheetState, setSheetState] = useState<SheetState>("peek");
  // Persisted per-chat to sessionStorage (same pattern as useActivePaper.ts)
  // so the panel's open/closed state survives a remount of this component -
  // e.g. from a backgrounded-tab reload - instead of resetting to the
  // default every time. Default to false for the new pill layout so it pops
  // up nicely on a chat that's never been opened yet.
  const [isChatOpen, setIsChatOpen] = useState(() => {
    try {
      return sessionStorage.getItem(`prism_chat_open_${chatId}`) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      sessionStorage.setItem(`prism_chat_open_${chatId}`, String(isChatOpen));
    } catch {
      // ignore (private browsing / quota)
    }
  }, [chatId, isChatOpen]);

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
      chatId={chatId}
      scrollPositions={scrollPositions}
      turns={turns}
      paperClaimsById={paperClaimsById}
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
            "overflow-hidden transition-all duration-300 ease-in-out rounded-2xl border border-hairline shadow-card bg-surface-subtle",
            isChatOpen ? "max-h-[80vh] opacity-100 mb-4" : "max-h-0 opacity-0 border-transparent shadow-none"
          )}
        >
          <div style={{ height: isChatOpen ? chatHeight : 0 }} className="w-full flex flex-col relative transition-none">
            <div
              className="w-full h-4 cursor-ns-resize flex items-center justify-center bg-surface-subtle hover:bg-surface-muted border-b border-hairline rounded-t-2xl shrink-0"
              onMouseDown={handleMouseDown}
            >
              <div className="w-10 h-1 bg-border-strong rounded-full" />
            </div>
            <div className="flex shrink-0 items-center justify-between border-b border-hairline px-4 py-3 bg-surface">
              <div className="flex items-center gap-2">
                <MessageCircle className="h-4 w-4 text-ink-tertiary" />
                <span className="font-sans text-sm font-semibold text-ink">
                  {fileName ? `Chat — ${fileName}` : "Chat"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsChatOpen(false)}
                className="flex h-6 w-6 items-center justify-center rounded-full text-ink-tertiary hover:bg-surface-subtle hover:text-ink transition-colors"
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
        
        <p className="mt-1.5 text-center font-sans text-[11px] text-slate-500">
          Get answers, ask for clarification, or explore specific claims from this paper.
        </p>
        <p className="text-center font-sans text-[11px] text-slate-500">
          Answers stay within this paper — no outside sources.
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
              className="rounded-md border border-hairline bg-surface px-3 py-1 font-sans text-xs text-ink-secondary transition-colors hover:border-brand hover:text-brand"
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
  chatId,
  scrollPositions,
  turns,
  paperClaimsById,
  error,
  isSending,
  onClaimClick,
  onCopy,
  onFollowUp,
}: {
  chatId: string;
  scrollPositions: React.RefObject<Map<string, number>>;
  turns: ChatTurn[];
  paperClaimsById: Record<string, ChatCiteInfo>;
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
  // The DOM node of whichever assistant turn is currently last - used as the
  // scroll anchor for a new/streaming response (see effect below) instead of
  // the container's ever-growing scrollHeight.
  const lastAssistantBubbleRef = useRef<HTMLDivElement>(null);
  const prevLastTurnIdRef = useRef<string | null>(null);
  // Guards the mount-time restore below to firing exactly once per mount
  // (this component remounts per chatId via PaperChatStrip's key), the first
  // time the scrollable container actually exists in the DOM - which is only
  // once `turns` goes non-empty (see the conditional render below).
  const hasRestoredRef = useRef(false);
  const hasTurns = turns.length > 0;
  // Mirrors the container's scrollTop on every 'scroll' event (cheap - a ref
  // write, no re-render) so the unmount-save effect below has a value to
  // read. It can't read scrollRef.current directly at that point: React nulls
  // out DOM refs for an unmounting subtree BEFORE running that subtree's own
  // effect cleanups, so scrollRef.current is already null by the time an
  // unmount cleanup runs - this ref is what stands in for it.
  const lastScrollTopRef = useRef(0);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root) return;
    const handleScroll = () => {
      lastScrollTopRef.current = root.scrollTop;
    };
    root.addEventListener("scroll", handleScroll, { passive: true });
    return () => root.removeEventListener("scroll", handleScroll);
  }, [hasTurns]);

  // Runs BEFORE paint so there is no frame at the wrong scroll position: a
  // returning chat snaps straight to its saved scrollTop, a chat with no
  // saved position (never opened/scrolled before) snaps straight to the
  // bottom. Deliberately separate from the streaming/new-turn effect below,
  // which still runs (see isNewTurn there) but is now a no-op for this same
  // transition since isAtBottomRef/anchor logic there only ever *adds*
  // motion on top of whatever this effect already settled on.
  useLayoutEffect(() => {
    if (!hasTurns || hasRestoredRef.current) return;
    hasRestoredRef.current = true;
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel) return;
    const saved = scrollPositions.current.get(chatId);
    root.scrollTop = saved != null ? saved : bottomScrollTop(root, sentinel);
    lastScrollTopRef.current = root.scrollTop;
  }, [hasTurns, chatId, scrollPositions]);

  // Persists this chat's scroll position when the user navigates away (this
  // component unmounts - PaperChatStrip is keyed by chatId, so every paper
  // switch is an unmount of the previously-active chat's strip). The save
  // itself only happens once, at unmount (reading the continuously-updated
  // lastScrollTopRef above, since the DOM ref is unavailable by then - see
  // that ref's own comment) rather than on every scroll tick, which keeps
  // this to a single map write per departure with nothing to throttle. It
  // also naturally solves the "streaming completes while backgrounded" edge
  // case: once unmounted, nothing in this component runs again (the backend
  // keeps generating, but recovery on return goes through useChatStream's
  // history fetch, not this component), so the saved position can only ever
  // reflect the user's own last scroll, never content that arrived after
  // they left.
  //
  // Guarded on hasRestoredRef so a React StrictMode dev-mode double-invoke
  // of this effect - which mounts, cleans up, and remounts a component once,
  // synchronously, before any real content has loaded - can't write a bogus
  // 0 into the map from lastScrollTopRef's untouched initial value. Without
  // this guard that phantom cleanup fires while `turns` is still empty (the
  // mount-restore layout effect above hasn't run yet, so hasRestoredRef is
  // still false), permanently poisoning this chatId's entry before the real
  // restore ever gets a chance to read it.
  useEffect(() => {
    return () => {
      if (!hasRestoredRef.current) return;
      scrollPositions.current.set(chatId, lastScrollTopRef.current);
    };
  }, [chatId, scrollPositions]);

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
    const root = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!root || !sentinel) return;

    if (turns.length === 0) {
      prevLastTurnIdRef.current = null;
      return;
    }

    const lastTurn = turns[turns.length - 1];
    const isNewTurn = lastTurn.id !== prevLastTurnIdRef.current;
    // Captured before being overwritten below: true exactly on the same
    // turns-went-from-empty-to-non-empty transition the mount-restore layout
    // effect above fires on (both key off prevLastTurnIdRef starting null).
    const isInitialPopulation = prevLastTurnIdRef.current === null;
    prevLastTurnIdRef.current = lastTurn.id;
    // Only (re)decide where to scroll when a NEW turn appears, not on every
    // chunk appended to the one already last. A turn's own top edge never
    // moves as its content grows - later turns are only ever appended below
    // it - so re-running this on every SSE chunk would just repeat the same
    // scroll call for no benefit. It was also the actual bug: targeting the
    // container's scrollHeight (which DOES grow every chunk) on every chunk
    // is what dragged the view past the start of any response taller than
    // the viewport.
    if (!isNewTurn) return;

    // While a turn is actively streaming in, anchor to ITS top edge so the
    // start of the response stays visible as it grows, rather than the
    // container's absolute bottom.
    const scrollToAnchor = () => {
      const anchor = lastAssistantBubbleRef.current;
      if (!anchor) return;
      const rootRect = root.getBoundingClientRect();
      const anchorRect = anchor.getBoundingClientRect();
      root.scrollTo({ top: anchorRect.top - rootRect.top + root.scrollTop, behavior: "smooth" });
    };
    const isStreamingTurn = lastTurn.role === "assistant" && lastTurn.isStreaming;

    if (isInitialPopulation) {
      // A history-hydrated turn (not streaming) was already positioned -
      // restored to its saved scrollTop, or defaulted to bottom for a
      // chat with no saved position - by the mount-restore layout effect
      // above, synchronously before paint. Redoing that here as an instant
      // jump-to-bottom would stomp a restored (non-bottom) position. Only
      // a genuinely new send on a chat that had zero prior turns (this
      // population IS the first message, streaming in live) needs this
      // effect to do anything, so the usual top-anchor kicks in immediately
      // instead of waiting one more turn.
      if (isStreamingTurn) scrollToAnchor();
      return;
    }

    if (!isAtBottomRef.current) {
      setShowJumpToBottom(true);
      return;
    }

    if (isStreamingTurn) {
      scrollToAnchor();
    } else {
      // Instant, not smooth: this branch is only reached when the last
      // turn isn't actively streaming (the anchor check above already
      // requires isStreaming for the smooth/top-anchor path), which in
      // practice means a new turn was appended (e.g. a follow-up sent)
      // while the user was already scrolled to the bottom of an existing
      // conversation. Animating that "glide" reads as a full page reload.
      root.scrollTo({ top: bottomScrollTop(root, sentinel), behavior: "auto" });
    }
  }, [turns]);

  const scrollToBottom = () => {
    const el = scrollRef.current;
    const sentinel = sentinelRef.current;
    if (!el || !sentinel) return;
    el.scrollTo({ top: bottomScrollTop(el, sentinel), behavior: "smooth" });
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
              className="rounded-md border border-hairline bg-surface px-4 py-1.5 font-sans text-sm text-ink-secondary transition-colors hover:border-brand hover:text-brand"
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
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto bg-surface-subtle p-6 pb-40">
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <UserTurnBubble key={i} turn={turn} />
          ) : (
            <AssistantTurn
              key={i}
              turn={turn}
              isLast={i === turns.length - 1}
              isSending={isSending}
              bubbleRef={i === turns.length - 1 ? lastAssistantBubbleRef : undefined}
              paperClaimsById={paperClaimsById}
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
        <div className="bg-brand-subtle text-ink rounded-2xl rounded-tr-sm px-5 py-4 text-sm shadow-sm">
          {text}
        </div>
        <div className="text-[10px] text-ink-tertiary mt-1.5 mr-1 font-medium">
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      <div className="bg-ink text-white w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 shadow-sm">
        N
      </div>
    </div>
  );
}

function AssistantTurn({
  turn,
  isLast,
  isSending,
  bubbleRef,
  paperClaimsById,
  onClaimClick,
  onCopy,
  onFollowUp,
}: {
  turn: ChatTurn;
  isLast: boolean;
  isSending: boolean;
  bubbleRef?: React.RefObject<HTMLDivElement | null>;
  paperClaimsById: Record<string, ChatCiteInfo>;
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
      <div ref={bubbleRef} className="flex gap-4">
        <GradientSparkle className="h-6 w-6 shrink-0 mt-1" />
        <div className="flex items-center gap-1.5 pt-1.5 bg-surface border border-hairline shadow-card rounded-2xl rounded-tl-sm px-5 py-4">
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-tertiary" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-tertiary" style={{ animationDelay: "150ms" }} />
          <span className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-tertiary" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  return (
    <div ref={bubbleRef} className="flex flex-col">
      <div className="group flex gap-4">
        <div className="shrink-0 mt-2">
          <GradientSparkle className="h-6 w-6" />
        </div>
        <div className="flex flex-col w-full max-w-[85%]">
          <div className="bg-surface border border-hairline shadow-card rounded-2xl rounded-tl-sm p-5 text-sm text-ink prose prose-sm prose-slate max-w-none prose-headings:font-semibold prose-headings:text-ink prose-p:leading-relaxed prose-a:text-ink prose-a:underline prose-li:marker:text-ink-tertiary [contain:layout]">
            <ChatMarkdown
              content={turnToMarkdown(turn, showCursor)}
              claimsById={claimsById(turn, paperClaimsById)}
              onClaimClick={onClaimClick}
            />
          </div>

          {isDone && (
            <div className="mt-2 flex items-center justify-end gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 px-2">
              <span className="text-[10px] text-ink-tertiary mr-auto ml-1 font-medium">
                {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <button
                type="button"
                onClick={onCopy}
                title="Copy"
                className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink-secondary"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                title="Helpful"
                className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink-secondary"
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                title="Not helpful"
                className="rounded-md p-1.5 text-ink-tertiary transition-colors hover:bg-surface-subtle hover:text-ink-secondary"
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
              className="rounded-md border border-hairline bg-surface px-4 py-1.5 font-sans text-sm text-ink-secondary shadow-card transition-colors hover:border-brand hover:text-brand"
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
            "bg-surface border border-hairline rounded-lg px-3 py-1.5 flex items-center gap-2 w-full transition-colors duration-150 z-50",
            "focus-within:border-border-strong"
          )}
          onClick={() => textareaRef.current?.focus()}
        >
          <GradientSparkle className="h-5 w-5 shrink-0" />

          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={onFocus}
            placeholder={placeholder}
            disabled={isSending}
            rows={1}
            className="flex-1 min-w-0 resize-none overflow-y-auto bg-transparent font-sans text-sm text-ink placeholder:text-ink-tertiary outline-none disabled:opacity-60 max-h-24 py-1.5"
          />

          <button className="text-ink-tertiary hover:text-ink-secondary transition-colors p-1.5 shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          </button>

          {isSending ? (
            <button
              type="button"
              onClick={onStop}
              className="flex shrink-0 items-center justify-center rounded-md bg-charcoal text-white transition-opacity hover:opacity-90 w-8 h-8"
            >
              <Square className="h-3.5 w-3.5" fill="currentColor" />
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
                "flex shrink-0 items-center justify-center rounded-md transition-all duration-150 w-8 h-8",
                message.trim() && !isSending
                  ? "bg-charcoal text-white hover:opacity-90"
                  : "bg-surface-muted text-ink-tertiary cursor-not-allowed"
              )}
              aria-label="Send"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="text-xs text-slate-500 mt-2 text-center px-4">
          Responses are based only on the content of {fileName ?? "this paper"}. Always verify important information.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col border-t border-hairline bg-surface pb-safe pt-2">
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
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-charcoal text-white shadow-sm transition-opacity hover:opacity-90"
          >
            <Square className="h-4 w-4" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!message.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-charcoal text-white shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            <ArrowUp className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  );
}
