import { useRef, useState, type KeyboardEvent } from "react";
import { Sparkles, Paperclip, ArrowUp, X, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

interface FloatingChatInputProps {
  fileName?: string;
  onSend: (message: string) => void;
  isSending?: boolean;
}

export function FloatingChatInput({ fileName, onSend, isSending = false }: FloatingChatInputProps) {
  // Local UI state: controls the expanded chat panel above the pill
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const placeholder = fileName
    ? `Ask about this paper (${fileName})...`
    : "Ask about this paper...";

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isSending) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="px-3 pb-4 pt-2 md:px-6 md:pb-5">
      {/* ── Expanded chat panel (slides up from pill when isChatOpen) ── */}
      <div
        className={cn(
          "overflow-hidden transition-all duration-300 ease-in-out",
          isChatOpen ? "max-h-[400px] mb-3 opacity-100" : "max-h-0 opacity-0"
        )}
      >
        <div className="bg-white shadow-xl border border-slate-200 rounded-t-2xl h-[400px] w-full flex flex-col overflow-hidden">
          {/* Chat panel header */}
          <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-slate-500" />
              <span className="font-sans text-sm font-semibold text-slate-800">
                {fileName ? `Chat — ${fileName}` : "Chat"}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsChatOpen(false)}
              className="flex h-6 w-6 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              aria-label="Close chat"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Chat messages area (placeholder — stream renders inside PaperChatStrip) */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <Sparkles className="h-6 w-6 text-slate-300" strokeWidth={1.5} />
              <p className="font-sans text-sm text-slate-400">
                Ask a question about this paper to get started.
              </p>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {["What are the main claims?", "Show me the strongest refusals"].map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => onSend(prompt)}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-sans text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-100"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Pill input bar ── */}
      <div
        className={cn(
          "flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 shadow-sm transition-shadow duration-150",
          "focus-within:border-slate-300 focus-within:shadow-md"
        )}
        onClick={() => inputRef.current?.focus()}
      >
        {/* Sparkle icon — toggles chat open */}
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
          <Sparkles
            className={cn("h-4 w-4 transition-colors", isChatOpen ? "text-slate-800" : "text-slate-400")}
            strokeWidth={1.5}
          />
        </button>

        {/* Text input */}
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsChatOpen(true)}
          placeholder={placeholder}
          disabled={isSending}
          className="flex-1 min-w-0 bg-transparent font-sans text-sm text-slate-800 placeholder:text-slate-400 outline-none disabled:opacity-60"
        />

        {/* Paperclip icon */}
        <button
          type="button"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          title="Attach file (coming soon)"
          onClick={(e) => e.stopPropagation()}
        >
          <Paperclip className="h-3.5 w-3.5" />
        </button>

        {/* Send button */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleSend();
          }}
          disabled={!value.trim() || isSending}
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-all duration-150",
            value.trim() && !isSending
              ? "bg-slate-800 text-white hover:bg-slate-900 shadow-sm"
              : "bg-slate-100 text-slate-400 cursor-not-allowed"
          )}
          aria-label="Send"
        >
          <ArrowUp className="h-3.5 w-3.5" strokeWidth={2.5} />
        </button>
      </div>

      {/* Hint text */}
      <p className="mt-1.5 text-center font-sans text-[11px] text-slate-400">
        Get answers, ask for clarification, or explore specific claims from this paper.
      </p>
    </div>
  );
}
