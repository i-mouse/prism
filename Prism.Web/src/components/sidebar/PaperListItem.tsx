import type { ChatListItem } from "@/types/api";
import { extractionStatusMeta, extractionStatusToVerdict } from "@/lib/claimMeta";
import { relativeTime } from "@/lib/format";
import { VerdictPill } from "@/components/VerdictPill";
import { cn } from "@/lib/utils";
import { FileText } from "lucide-react";

interface PaperListItemProps {
  chat: ChatListItem;
  isActive: boolean;
  onSelect: () => void;
  collapsed?: boolean;
}

export function PaperListItem({ chat, isActive, onSelect, collapsed = false }: PaperListItemProps) {
  const status = extractionStatusMeta[chat.extractionStatus];
  const verdict = extractionStatusToVerdict[chat.extractionStatus];

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onSelect}
        title={chat.fileName}
        className={cn(
          "mx-auto flex h-10 w-10 items-center justify-center rounded-lg transition-colors",
          isActive ? "bg-brand-subtle text-brand" : "text-ink-tertiary hover:bg-surface-subtle hover:text-ink-secondary"
        )}
      >
        <FileText className="h-5 w-5" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border-l-2 border-transparent px-3 py-3 text-left transition-colors hover:bg-surface-subtle",
        isActive && "border-brand bg-brand-subtle"
      )}
    >
      <div className="truncate font-sans text-sm font-medium text-ink">{chat.fileName}</div>
      <div className="mt-1 flex items-center gap-2">
        <VerdictPill verdict={verdict} label={status.label} size="sm" />
        <span className="font-mono text-xs tabular-nums text-ink-tertiary">{relativeTime(chat.uploadedAt)}</span>
      </div>
    </button>
  );
}
