import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { ArrowUp, Copy, RotateCw, Square } from "lucide-react";
import { toast } from "sonner";
import { useChatStream } from "@/hooks/useChatStream";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import type { ChatBlock, ChatTurn } from "@/types/chat";
import { cn } from "@/lib/utils";

interface PaperChatStripProps {
  chatId: string;
  activeFileId: string;
}

const SUGGESTED_PROMPTS = [
  "What are the main claims of this paper?",
  "Show me the strongest refusals",
  "Explain the grounding methodology",
  "Which claims are only partially supported?",
];

// Approximates "the agent declined to answer" from block shape alone —
// there's no explicit refusal flag on the wire, so this is a best-effort
// heuristic pending a real signal from the backend (post-V1).
const REFUSAL_PATTERN =
  /\b(can'?t|cannot|unable to|does(?:n't| not) (?:address|cover|mention|discuss)|outside (?:the )?scope|no (?:relevant )?(?:information|evidence))\b/i;

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

type ClaimReferenceBlock = Extract<ChatBlock, { type: "claim_reference" }>;

const claimPillClasses: Record<ClaimReferenceBlock["display_label"], string> = {
  supported: "bg-supported-bg text-supported border-supported/30",
  partially_supported: "bg-partial-bg text-partial border-partial/30",
  not_supported: "bg-refused-bg text-refused border-refused/30",
};

function turnToPlainText(turn: ChatTurn): string {
  return turn.blocks
    .map((b) => (b.type === "text" ? b.content : b.claim_summary))
    .join(" ")
    .trim();
}

function followUpsFor(turn: ChatTurn): string[] {
  const claimRefs = turn.blocks.filter((b): b is ClaimReferenceBlock => b.type === "claim_reference");
  if (claimRefs.length > 0) {
    return ["Explain that further", "Why were those claims refused?", "Show me stronger evidence"];
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
    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border border-accent/20 bg-accent-subtle">
      <div className="h-2 w-2 rotate-45 rounded-sm bg-accent" />
    </div>
  );
}

export function PaperChatStrip({ chatId, activeFileId }: PaperChatStripProps) {
  const { turns, isSending, error, sendMessage, abort } = useChatStream(chatId, activeFileId);
  const { highlightClaim } = useSelectedClaim();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);

  const isNearBottom = () => {
    const el = scrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 100;
  };

  useEffect(() => {
    if (isNearBottom()) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
      setShowJumpToBottom(false);
    } else if (turns.length > 0) {
      setShowJumpToBottom(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turns]);

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setShowJumpToBottom(false);
  };

  const handleScroll = () => {
    if (isNearBottom()) setShowJumpToBottom(false);
  };

  const handleClaimClick = (claimId: string) => {
    highlightClaim(claimId);
    const rowEl = document.querySelector(`[data-claim-id="${claimId}"]`);
    if (rowEl) {
      rowEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const handleCopy = async (turn: ChatTurn) => {
    try {
      await navigator.clipboard.writeText(turnToPlainText(turn));
      toast("Copied");
    } catch {
      toast("Could not copy");
    }
  };

  const handleRegenerate = () => {
    toast("Regenerate coming soon");
  };

  return (
    <motion.div
      layout
      className="flex shrink-0 flex-col border-t border-border bg-gradient-to-b from-surface-alt/60 to-surface-alt/90 backdrop-blur-sm"
    >
      {turns.length === 0 ? (
        <div className="flex flex-col items-center gap-3 px-6 py-6">
          <p className="text-center text-sm text-ink-muted">
            Ask Prism about this paper&rsquo;s claims, evidence, or audit.
          </p>
          <div className="flex max-w-lg flex-wrap justify-center gap-2">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => sendMessage(prompt)}
                className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-ink-muted transition-all hover:border-border-strong hover:bg-surface-sunken"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="relative">
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="max-h-96 overflow-y-auto px-6 py-6"
          >
            {turns.map((turn, i) =>
              turn.role === "user" ? (
                <UserTurnBubble key={i} turn={turn} />
              ) : (
                <AssistantTurn
                  key={i}
                  turn={turn}
                  isLast={i === turns.length - 1}
                  isSending={isSending}
                  onClaimClick={handleClaimClick}
                  onCopy={() => handleCopy(turn)}
                  onRegenerate={handleRegenerate}
                  onFollowUp={sendMessage}
                />
              )
            )}
            {error && <div className="px-1 text-sm text-refused">{error}</div>}
          </div>

          {showJumpToBottom && (
            <button
              type="button"
              onClick={scrollToBottom}
              className="absolute bottom-3 right-6 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-ink-muted shadow-sm transition-all hover:border-border-strong hover:bg-surface-sunken"
            >
              New messages ↓
            </button>
          )}
        </div>
      )}

      <ChatInput
        onSend={sendMessage}
        onStop={abort}
        isSending={isSending}
        placeholder="Ask about this paper..."
      />
    </motion.div>
  );
}

function UserTurnBubble({ turn }: { turn: ChatTurn }) {
  const text = turn.blocks.map((b) => (b.type === "text" ? b.content : "")).join("");
  return (
    <div className="mb-4 flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-br-md bg-accent-subtle px-4 py-2.5 text-sm leading-relaxed text-ink">
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

  if (isThinking) {
    return (
      <div className="mb-6 flex gap-3">
        <PrismAvatar />
        <div className="flex items-center gap-1.5 pt-1.5">
          <span
            className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-muted"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-muted"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="h-1.5 w-1.5 animate-thinking-dot rounded-full bg-ink-muted"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6">
      <div className="group flex gap-3">
        <PrismAvatar />
        <div className="min-w-0 flex-1">
          <div className="text-sm leading-relaxed text-ink">
            {turn.blocks.map((block, i) => {
              const isLastBlock = i === turn.blocks.length - 1;
              if (block.type === "text") {
                return (
                  <span key={i} className={cn(turn.isStreaming && isLastBlock && "streaming-cursor")}>
                    {block.content}
                  </span>
                );
              }
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => onClaimClick(block.claim_id)}
                  className={cn(
                    "mx-0.5 inline-flex h-6 items-center gap-1 rounded-full border px-2 text-xs font-medium transition-colors",
                    claimPillClasses[block.display_label],
                    "hover:brightness-95"
                  )}
                >
                  {truncate(block.claim_summary, 50)}
                </button>
              );
            })}
          </div>

          {isDone && (
            <div className="mt-2 flex items-center gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
              <button
                type="button"
                onClick={onCopy}
                title="Copy"
                className="rounded-md p-1.5 text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={onRegenerate}
                title="Regenerate"
                className="rounded-md p-1.5 text-ink-muted transition-colors hover:bg-surface-sunken hover:text-ink"
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
              className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-ink-muted transition-all hover:border-border-strong hover:bg-surface-sunken"
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
}: {
  onSend: (message: string) => void;
  onStop: () => void;
  isSending: boolean;
  placeholder: string;
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
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="px-6 pb-6">
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border border-border bg-surface p-2",
          "transition-all duration-150",
          "focus-within:border-accent/50 focus-within:ring-4 focus-within:ring-accent/10"
        )}
      >
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isSending}
          rows={1}
          className={cn(
            "max-h-24 flex-1 resize-none overflow-y-auto bg-transparent px-3 py-1.5",
            "text-sm text-ink placeholder:text-ink-subtle",
            "focus:outline-none"
          )}
        />
        {isSending ? (
          <button
            type="button"
            onClick={onStop}
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
              "bg-ink text-surface transition-all hover:bg-ink-muted"
            )}
          >
            <Square className="h-3 w-3" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!message.trim()}
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
              "bg-accent text-accent-fg transition-all duration-100",
              "hover:bg-accent-hover active:scale-95",
              "disabled:cursor-not-allowed disabled:opacity-30"
            )}
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
