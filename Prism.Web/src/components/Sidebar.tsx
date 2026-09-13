import type { Ref } from "react";
import type { ChatListItem } from "@/types/api";
import { PrismLogo } from "@/components/PrismLogo";
import { UploadZone, type UploadZoneHandle } from "@/components/sidebar/UploadZone";
import { CurrentContextCard } from "@/components/sidebar/CurrentContextCard";
import { PaperListItem } from "@/components/sidebar/PaperListItem";
import { SidebarFooter } from "@/components/sidebar/SidebarFooter";
import { ChevronLeft, ChevronRight, X, FileText } from "lucide-react";

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
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onCloseMobile?: () => void;
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
  collapsed = false,
  onToggleCollapse,
  onCloseMobile,
}: SidebarProps) {
  const activeChat = chats.find((c) => c.chatId === activeChatId) ?? null;

  return (
    <aside className="flex h-full flex-col overflow-y-auto border-r border-hairline bg-surface py-6 px-3 w-full">
      <div className="flex items-center justify-between pb-4">
        <div className="flex items-center gap-2 px-1">
          <PrismLogo className="h-6 w-6 shrink-0" />
          {!collapsed && <span className="font-sans font-semibold text-ink transition-opacity">Prism</span>}
        </div>
        
        {/* Desktop Collapse Toggle */}
        <button 
          onClick={onToggleCollapse} 
          className="hidden lg:flex items-center justify-center h-6 w-6 text-ink-tertiary hover:text-ink transition-colors"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>

        {/* Mobile Close Button */}
        <button 
          onClick={onCloseMobile} 
          className="lg:hidden flex items-center justify-center h-8 w-8 text-ink-secondary hover:text-ink transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="pb-6">
        <UploadZone
          ref={uploadZoneRef}
          getConnectionId={getConnectionId}
          joinChat={joinChat}
          refetchChats={refetchChats}
          onUploaded={onUploaded}
          collapsed={collapsed}
        />
      </div>

      {activeChat && !collapsed && (
        <>
          <div className="pb-2 px-1 font-sans text-[10px] uppercase tracking-wider text-ink-tertiary">
            CURRENT PAPER
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

      {!collapsed && (
        <div className="pb-2 px-1 font-sans text-[10px] uppercase tracking-wider text-ink-tertiary">
          RECENT PAPERS
        </div>
      )}
      
      <div className="flex flex-col gap-1 flex-1">
        {chats.length === 0 ? (
          !collapsed ? (
            <div className="px-1 py-4 flex flex-col items-center justify-center text-center gap-2">
              <FileText className="h-8 w-8 text-ink-tertiary" />
              <div className="font-sans text-sm text-ink-secondary space-y-1">
                <p>No papers yet.</p>
                <p>Upload one to get started.</p>
              </div>
            </div>
          ) : null
        ) : (
          chats.map((chat) => (
            <PaperListItem
              key={chat.chatId}
              chat={chat}
              isActive={chat.chatId === activeChatId}
              onSelect={() => onSelectChat(chat.chatId)}
              collapsed={collapsed}
            />
          ))
        )}
      </div>

      {!collapsed && <SidebarFooter />}
    </aside>
  );
}
