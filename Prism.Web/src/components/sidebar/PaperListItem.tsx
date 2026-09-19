import type { ChatListItem } from "@/types/api";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FileText } from "lucide-react";

interface PaperListItemProps {
  chat: ChatListItem;
  isActive: boolean;
  onSelect: () => void;
  collapsed?: boolean;
}

export function PaperListItem({ chat, isActive, onSelect, collapsed = false }: PaperListItemProps) {
  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onSelect}
        title={chat.fileName}
        className={cn(
          "mx-auto flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
          isActive
            ? "bg-surface-muted text-ink"
            : "text-ink-tertiary hover:bg-surface-subtle hover:text-ink-secondary"
        )}
      >
        <FileText className="h-4 w-4" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
        isActive ? "bg-surface-subtle" : "hover:bg-surface-subtle"
      )}
    >
      {/* Document icon */}
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
          isActive ? "text-ink" : "text-ink-tertiary"
        )}
      >
        <FileText className="h-4 w-4" strokeWidth={1.5} />
      </div>

      {/* Text */}
      <div className="min-w-0 flex-1">
        <div
          className={cn(
            "truncate font-sans text-sm",
            isActive ? "font-semibold text-ink" : "font-medium text-ink-secondary"
          )}
        >
          {chat.fileName}
        </div>
        <div className="font-sans text-[11px] text-ink-tertiary">
          {relativeTime(chat.uploadedAt)}
        </div>
      </div>

      {/* Status dot — extraction status, not a claim verdict, so this uses
          the status token family rather than verdict colors. */}
      {chat.extractionStatus === "Completed" ? (
        <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-status-complete" />
      ) : chat.extractionStatus === "Failed" ? (
        <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-status-failed" />
      ) : (
        <span className="shrink-0 h-2.5 w-2.5 rounded-full border-[1.5px] border-ink-tertiary border-t-transparent animate-spin" />
      )}
    </button>
  );
}
