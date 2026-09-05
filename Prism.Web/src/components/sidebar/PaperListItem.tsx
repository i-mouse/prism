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
        "group flex w-full items-start gap-3 rounded-lg border-l-2 border-transparent px-3 py-2.5 text-left transition-colors hover:bg-surface-subtle",
        isActive && "border-brand bg-brand-subtle hover:bg-brand-subtle"
      )}
    >
      <div className={cn(
        "mt-0.5 shrink-0 rounded-md border border-hairline bg-surface p-1.5",
        isActive ? "text-brand border-brand/20" : "text-ink-tertiary"
      )}>
        <FileText className="h-4 w-4" strokeWidth={1.5} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="truncate font-sans text-sm font-semibold text-ink">{chat.fileName}</div>
        <div className="mt-1 flex items-center gap-1.5 font-sans text-[11px] font-medium">
           {chat.extractionStatus === "Completed" ? (
              <>
                 <div className="flex h-3 w-3 items-center justify-center rounded-full bg-verdict-supported-icon text-white">
                   <svg className="h-2 w-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                 </div>
                 <span className="text-ink-secondary">Ready · {relativeTime(chat.uploadedAt)}</span>
              </>
           ) : chat.extractionStatus === "Failed" ? (
              <>
                 <div className="flex h-3 w-3 items-center justify-center rounded-full bg-verdict-refused-icon text-white">
                    <svg className="h-2 w-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                 </div>
                 <span className="text-ink-secondary">Failed · {relativeTime(chat.uploadedAt)}</span>
              </>
           ) : (
              <>
                 <div className="h-3.5 w-3.5 rounded-full border-[1.5px] border-brand border-t-transparent animate-spin" />
                 <span className="text-brand">Analyzing...</span>
              </>
           )}
        </div>
      </div>
    </button>
  );
}
