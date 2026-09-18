import type { Ref } from "react";
import type { ChatListItem } from "@/types/api";
import { PrismLogo } from "@/components/PrismLogo";
import { UploadZone, type UploadZoneHandle } from "@/components/sidebar/UploadZone";
import { CurrentContextCard } from "@/components/sidebar/CurrentContextCard";
import { PaperListItem } from "@/components/sidebar/PaperListItem";
import { SidebarFooter } from "@/components/sidebar/SidebarFooter";
import {
  ChevronLeft,
  ChevronRight,
  X,
  FileText,
  Home,
  BookOpen,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  activeChatId: string;
  chats: ChatListItem[];
  refetchChats: () => void;
  getConnectionId: () => string | null;
  joinChat: (chatId: string) => Promise<void>;
  fileSizeLabels: Record<string, string>;
  /** completedAt from PaperClaimsResponse — used for "Completed X ago" in CurrentContextCard */
  completedAt?: string | null;
  onUploadStarted: (chatId: string, file: File) => void;
  onUploaded: (chatId: string, fileId: string, file: File, isCacheHit: boolean) => void;
  onUploadFailed: (chatId: string) => void;
  onSelectChat: (chatId: string) => void;
  uploadZoneRef?: Ref<UploadZoneHandle>;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onCloseMobile?: () => void;
}

const navItems = [
  { label: "Home", Icon: Home },
  { label: "Recent Papers", Icon: BookOpen },
  { label: "Settings", Icon: Settings },
];

export function Sidebar({
  activeChatId,
  chats,
  refetchChats,
  getConnectionId,
  joinChat,
  fileSizeLabels,
  completedAt,
  onUploadStarted,
  onUploaded,
  onUploadFailed,
  onSelectChat,
  uploadZoneRef,
  collapsed = false,
  onToggleCollapse,
  onCloseMobile,
}: SidebarProps) {
  const activeChat = chats.find((c) => c.chatId === activeChatId) ?? null;

  return (
    <aside className="flex h-full flex-col border-r border-hairline bg-surface overflow-y-auto w-full">
      {/* ── Logo area ─────────────────────────────── */}
      <div className="flex items-center justify-between px-4 pt-5 pb-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <PrismLogo className={cn("shrink-0", collapsed ? "h-7 w-7" : "h-7 w-7")} />
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-sans font-black text-2xl text-slate-900 leading-tight tracking-tight">
                PRISM
              </div>
              <div className="font-sans text-xs text-slate-500 leading-tight">
                Audit the claims. Verify the evidence.
              </div>
            </div>
          )}
        </div>

        {/* Desktop collapse toggle */}
        <button
          onClick={onToggleCollapse}
          className="hidden lg:flex items-center justify-center h-6 w-6 text-ink-tertiary hover:text-ink transition-colors shrink-0"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>

        {/* Mobile close button */}
        <button
          onClick={onCloseMobile}
          className="lg:hidden flex items-center justify-center h-8 w-8 text-ink-secondary hover:text-ink transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* ── Upload & Analyze ─────────────────────── */}
      <div className={cn("px-3 pb-4", collapsed && "px-2")}>
        <UploadZone
          ref={uploadZoneRef}
          getConnectionId={getConnectionId}
          joinChat={joinChat}
          refetchChats={refetchChats}
          onUploadStarted={onUploadStarted}
          onUploaded={onUploaded}
          onUploadFailed={onUploadFailed}
          collapsed={collapsed}
        />
      </div>

      {/* ── Nav links ────────────────────────────── */}
      {!collapsed && (
        <nav className="px-3 pb-4">
          {navItems.map(({ label, Icon }) => (
            <button
              key={label}
              type="button"
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2 font-sans text-sm text-ink-secondary transition-colors hover:bg-surface-subtle hover:text-ink"
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          ))}
        </nav>
      )}

      {/* ── Current paper ─────────────────────────── */}
      {activeChat && !collapsed && (
        <div className="px-3 pb-4">
          <div className="mb-2 px-1 font-sans text-[10px] uppercase tracking-wider text-ink-tertiary">
            Current Paper
          </div>
          <CurrentContextCard
            fileName={activeChat.fileName}
            fileSizeLabel={fileSizeLabels[activeChatId]}
            extractionStatus={activeChat.extractionStatus}
            completedAt={completedAt}
          />
        </div>
      )}

      {/* ── Recent papers ─────────────────────────── */}
      {!collapsed && (
        <div className="mb-2 px-4 font-sans text-[10px] uppercase tracking-wider text-ink-tertiary">
          Recent Papers
        </div>
      )}

      <div className={cn("flex flex-col gap-0.5 flex-1 pb-3", collapsed ? "px-2" : "px-3")}>
        {chats.length === 0 ? (
          !collapsed ? (
            <div className="px-1 py-6 flex flex-col items-center justify-center text-center gap-2">
              <FileText className="h-7 w-7 text-ink-tertiary" />
              <div className="font-sans text-xs text-ink-secondary space-y-0.5">
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

      {/* ── Footer ───────────────────────────────── */}
      {!collapsed && <SidebarFooter />}
    </aside>
  );
}
