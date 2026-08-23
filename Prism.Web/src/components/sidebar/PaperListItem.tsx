import type { ChatListItem } from "@/types/api";
import { extractionStatusMeta } from "@/lib/claimMeta";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PaperListItemProps {
  chat: ChatListItem;
  isActive: boolean;
  onSelect: () => void;
}

export function PaperListItem({ chat, isActive, onSelect }: PaperListItemProps) {
  const status = extractionStatusMeta[chat.extractionStatus];

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border-l-4 border-transparent px-4 py-3 text-left transition-[background-color,box-shadow] duration-quick ease-smooth hover:bg-surface hover:shadow-card",
        isActive && "border-l-accent bg-surface shadow-card"
      )}
    >
      <div className="truncate text-sm font-medium text-ink">{chat.fileName}</div>
      <div className="mt-1 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex h-5 items-center rounded-full px-2 text-xs",
            status.textClass,
            status.bgClass
          )}
        >
          {status.label}
        </span>
        <span className="text-xs tabular-nums text-ink-muted">{relativeTime(chat.uploadedAt)}</span>
      </div>
    </button>
  );
}
