import type { ChatListItem } from "@/types/api";
import { UploadZone } from "@/components/sidebar/UploadZone";
import { CurrentContextCard } from "@/components/sidebar/CurrentContextCard";
import { PaperListItem } from "@/components/sidebar/PaperListItem";
import { SidebarFooter } from "@/components/sidebar/SidebarFooter";

interface SidebarProps {
  activeChatId: string;
  chats: ChatListItem[];
  refetchChats: () => void;
  getConnectionId: () => string | null;
  joinChat: (chatId: string) => Promise<void>;
  fileSizeLabels: Record<string, string>;
  onUploaded: (chatId: string, fileId: string, file: File) => void;
  onSelectChat: (chatId: string) => void;
}

export function Sidebar({
  activeChatId,
  chats,
  refetchChats,
  getConnectionId,
  joinChat,
  fileSizeLabels,
  onUploaded,
  onSelectChat,
}: SidebarProps) {
  const activeChat = chats.find((c) => c.chatId === activeChatId) ?? null;

  return (
    <aside className="flex h-full flex-col overflow-y-auto border-r border-border bg-surface-alt px-3 py-4">
      <div className="flex items-center gap-2 pb-4">
        <svg viewBox="0 0 24 24" className="h-8 w-8 text-ink" fill="currentColor">
          <path d="M12 1L23 12L12 23L1 12L12 1Z" />
        </svg>
        <span className="font-display text-lg font-bold text-ink">Prism</span>
      </div>

      <div className="pb-6">
        <UploadZone
          getConnectionId={getConnectionId}
          joinChat={joinChat}
          refetchChats={refetchChats}
          onUploaded={onUploaded}
        />
      </div>

      {activeChat && (
        <>
          <div className="pb-2 text-xs font-semibold uppercase tracking-[0.05em] text-ink-subtle">
            Current Context
          </div>
          <div className="pb-6">
            <CurrentContextCard
              fileName={activeChat.fileName}
              fileSizeLabel={fileSizeLabels[activeChatId]}
              extractionStatus={activeChat.extractionStatus}
            />
          </div>
        </>
      )}

      <div className="pb-2 text-xs font-semibold uppercase tracking-[0.05em] text-ink-subtle">
        Papers
      </div>
      <div className="flex flex-col gap-1">
        {chats.length === 0 ? (
          <div className="px-4 py-3 text-sm text-ink-muted">No papers uploaded yet.</div>
        ) : (
          chats.map((chat) => (
            <PaperListItem
              key={chat.chatId}
              chat={chat}
              isActive={chat.chatId === activeChatId}
              onSelect={() => onSelectChat(chat.chatId)}
            />
          ))
        )}
      </div>

      <SidebarFooter />
    </aside>
  );
}
