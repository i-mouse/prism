import type { ChatListItem } from "@/types/api";
import { extractionStatusMeta, extractionStatusToVerdict } from "@/lib/claimMeta";
import { relativeTime } from "@/lib/format";
import { VerdictPill } from "@/components/VerdictPill";
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
        "w-full rounded-lg border-l-4 border-transparent px-3 py-2 text-left transition-colors hover:bg-surface-subtle",
        isActive && "border-l-accent bg-surface shadow-card"
      )}
    >
      <div className="truncate font-sans text-sm text-ink">{chat.fileName}</div>
      <div className="mt-1 flex items-center gap-2">
        <VerdictPill verdict={extractionStatusToVerdict[chat.extractionStatus]} label={status.label} size="sm" />
        <span className="font-mono text-xs tabular-nums text-ink-tertiary">{relativeTime(chat.uploadedAt)}</span>
      </div>
    </button>
  );
}
