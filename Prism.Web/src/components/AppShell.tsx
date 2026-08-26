import { useCallback, useEffect, useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { MatrixView } from "@/components/MatrixView";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { useActivePaper } from "@/hooks/useActivePaper";
import { useChats } from "@/hooks/useChats";
import { usePaperClaims } from "@/hooks/usePaperClaims";
import { useSignalR } from "@/hooks/useSignalR";
import { formatFileSize } from "@/lib/format";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { cn } from "@/lib/utils";

const USER_ID = "demo-user-01";

export function AppShell() {
  const { activeChatId, setActiveChatId, activePaperId, setActivePaperId } = useActivePaper();
  const { chats, refetch: refetchChats } = useChats(USER_ID);
  const { data: paperClaims, isLoading, refetch: refetchClaims } = usePaperClaims(activePaperId);
  const { joinChat, on, off, getConnectionId } = useSignalR();
  const { selectedClaimId, setSelectedClaimId } = useSelectedClaim();
  const [fileSizeLabels, setFileSizeLabels] = useState<Record<string, string>>({});
  const drawerOpen = selectedClaimId !== null;

  useEffect(() => {
    joinChat(activeChatId).catch((err) => console.error("Failed to join chat group:", err));
  }, [activeChatId, joinChat]);

  useEffect(() => {
    const handleDocumentProcessed = (data: unknown) => {
      const payload = data as { chatId?: string };
      refetchChats();
      if (payload?.chatId && payload.chatId === activeChatId) {
        refetchClaims();
      }
    };

    on("DocumentProcessed", handleDocumentProcessed);
    return () => off("DocumentProcessed", handleDocumentProcessed);
  }, [on, off, activeChatId, refetchChats, refetchClaims]);

  const handleSelectChat = useCallback(
    async (chatId: string) => {
      setActiveChatId(chatId);
      setSelectedClaimId(null);
      try {
        const res = await fetch(`/api/chats/${chatId}/files`);
        if (!res.ok) throw new Error("Failed to load chat files");
        const files: Array<{ fileId: string }> = await res.json();
        setActivePaperId(files[0]?.fileId ?? null);
      } catch (err) {
        console.error("Failed to resolve paper for chat:", err);
        setActivePaperId(null);
      }
    },
    [setActiveChatId, setActivePaperId, setSelectedClaimId]
  );

  const handleUploaded = useCallback(
    (chatId: string, fileId: string, file: File) => {
      setFileSizeLabels((prev) => ({ ...prev, [chatId]: formatFileSize(file.size) }));
      setActiveChatId(chatId);
      setActivePaperId(fileId);
      setSelectedClaimId(null);
    },
    [setActiveChatId, setActivePaperId, setSelectedClaimId]
  );

  return (
    <div className="flex h-screen flex-col">
      <Toaster />
      <TopBar />
      <div
        className={cn(
          "grid min-h-0 flex-1 grid-cols-1 transition-[grid-template-columns] duration-200 ease-smooth",
          drawerOpen ? "md:grid-cols-[240px_minmax(0,1fr)_400px]" : "md:grid-cols-[240px_minmax(0,1fr)]"
        )}
      >
        <Sidebar
          activeChatId={activeChatId}
          chats={chats}
          refetchChats={refetchChats}
          getConnectionId={getConnectionId}
          joinChat={joinChat}
          fileSizeLabels={fileSizeLabels}
          onUploaded={handleUploaded}
          onSelectChat={handleSelectChat}
        />
        <main className="flex min-h-0 min-w-0 flex-col bg-surface">
          <MatrixView
            paperClaims={paperClaims}
            isLoading={isLoading}
            activePaperId={activePaperId}
            activeChatId={activeChatId}
            onViewEvidence={setSelectedClaimId}
          />
        </main>
        {drawerOpen && <EvidenceDrawer paperClaims={paperClaims} />}
      </div>
    </div>
  );
}
