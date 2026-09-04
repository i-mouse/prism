import type { Ref } from "react";
import type { ChatListItem } from "@/types/api";
import { PrismLogo } from "@/components/PrismLogo";
import { UploadZone, type UploadZoneHandle } from "@/components/sidebar/UploadZone";
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
  uploadZoneRef?: Ref<UploadZoneHandle>;
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
  uploadZoneRef,
}: SidebarProps) {
  const activeChat = chats.find((c) => c.chatId === activeChatId) ?? null;

  return (
    <aside className="flex h-full flex-col overflow-y-auto border-r border-hairline bg-surface px-4 py-6">
      <div className="flex items-center gap-2 pb-4">
        <PrismLogo className="h-6 w-6" />
        <span className="font-sans font-semibold text-ink">Prism</span>
      </div>

      <div className="pb-6">
        <UploadZone
          ref={uploadZoneRef}
          getConnectionId={getConnectionId}
          joinChat={joinChat}
          refetchChats={refetchChats}
          onUploaded={onUploaded}
        />
      </div>

      {activeChat && (
        <>
          <div className="pb-2 font-sans text-xs uppercase tracking-wider text-ink-tertiary">
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

      <div className="pb-2 font-sans text-xs uppercase tracking-wider text-ink-tertiary">
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
