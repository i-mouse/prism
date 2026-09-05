import { useCallback, useEffect, useRef, useState } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TopBar } from "@/components/TopBar";
import { Sidebar } from "@/components/Sidebar";
import { MatrixView } from "@/components/MatrixView";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import type { UploadZoneHandle } from "@/components/sidebar/UploadZone";
import { useActivePaper } from "@/hooks/useActivePaper";
import { useChats } from "@/hooks/useChats";
import { usePaperClaims } from "@/hooks/usePaperClaims";
import { useSignalR } from "@/hooks/useSignalR";
import { useBodyScrollLock } from "@/hooks/useBodyScrollLock";
import { formatFileSize } from "@/lib/format";
import { useSelectedClaim } from "@/contexts/SelectedClaimContext";
import { cn } from "@/lib/utils";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";

// Below Tailwind's `lg` breakpoint (1024px), the sidebar and evidence drawer
// render as overlays and must lock body scroll; at `lg`+ they're static
// grid columns and shouldn't touch it.
function useBelowLg() {
  const [belowLg, setBelowLg] = useState(
    () => typeof window !== "undefined" && !window.matchMedia("(min-width: 1024px)").matches
  );

  useEffect(() => {
    const mql = window.matchMedia("(min-width: 1024px)");
    const handler = () => setBelowLg(!mql.matches);
    handler();
    mql.addEventListener("change", handler);
    // Some embedded/emulated viewports resize without firing the
    // MediaQueryList change event — window "resize" is a redundant but
    // harmless fallback that keeps the breakpoint switch reliable there.
    window.addEventListener("resize", handler);
    return () => {
      mql.removeEventListener("change", handler);
      window.removeEventListener("resize", handler);
    };
  }, []);

  return belowLg;
}

const USER_ID = "demo-user-01";

export function AppShell() {
  const { paperId: routeChatId } = useParams<{ paperId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const routeClaimId = searchParams.get("claim");

  const { activeChatId, setActiveChatId, activePaperId, setActivePaperId } = useActivePaper();
  const { chats, refetch: refetchChats } = useChats(USER_ID);
  const { data: paperClaims, isLoading, refetch: refetchClaims } = usePaperClaims(activePaperId);
  const { joinChat, on, off, getConnectionId } = useSignalR();
  const { selectedClaimId, setSelectedClaimId } = useSelectedClaim();
  const [fileSizeLabels, setFileSizeLabels] = useState<Record<string, string>>({});
  
  const drawerOpen = selectedClaimId !== null;
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const uploadZoneRef = useRef<UploadZoneHandle>(null);

  const belowLg = useBelowLg();
  useBodyScrollLock(isMobileSidebarOpen);
  useBodyScrollLock(drawerOpen && belowLg);

  // Sync selected claim -> URL
  useEffect(() => {
    if (selectedClaimId && selectedClaimId !== routeClaimId) {
      setSearchParams({ claim: selectedClaimId }, { replace: true });
    } else if (!selectedClaimId && routeClaimId) {
      setSearchParams({}, { replace: true });
    }
  }, [selectedClaimId]);

  // Sync URL -> selected claim
  useEffect(() => {
    if (routeClaimId !== selectedClaimId) {
      setSelectedClaimId(routeClaimId);
    }
  }, [routeClaimId]);

  useEffect(() => {
    if (activeChatId) {
      joinChat(activeChatId).catch((err) => console.error("Failed to join chat group:", err));
    }
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

  const fetchChatFiles = async (chatId: string) => {
    try {
      const res = await fetch(`/api/chats/${chatId}/files`);
      if (!res.ok) throw new Error("Failed to load chat files");
      const files: Array<{ fileId: string }> = await res.json();
      setActivePaperId(files[0]?.fileId ?? null);
    } catch (err) {
      console.error("Failed to resolve paper for chat:", err);
      setActivePaperId(null);
    }
  };

  // Sync route param -> active paper
  useEffect(() => {
    if (routeChatId && routeChatId !== activeChatId) {
      setActiveChatId(routeChatId);
      fetchChatFiles(routeChatId);
    } else if (!routeChatId && activeChatId) {
      // Empty state
      setActiveChatId("");
      setActivePaperId(null);
    }
  }, [routeChatId]);

  const handleSelectChat = useCallback(
    (chatId: string) => {
      setIsMobileSidebarOpen(false);
      navigate(`/paper/${chatId}`);
    },
    [navigate]
  );

  const handleUploaded = useCallback(
    (chatId: string, _fileId: string, file: File) => {
      setFileSizeLabels((prev) => ({ ...prev, [chatId]: formatFileSize(file.size) }));
      setIsMobileSidebarOpen(false);
      navigate(`/paper/${chatId}`);
    },
    [navigate]
  );

  const isDesktopCollapsed = localStorage.getItem("prism_sidebar_collapsed") === "true";
  const [desktopCollapsed, setDesktopCollapsed] = useState(isDesktopCollapsed);

  const toggleDesktopCollapsed = () => {
    const next = !desktopCollapsed;
    setDesktopCollapsed(next);
    localStorage.setItem("prism_sidebar_collapsed", next.toString());
  };

  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const dragCounter = useRef(0);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current += 1;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDraggingOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) {
      setIsDraggingOver(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDraggingOver(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadZoneRef.current?.handleFiles(e.dataTransfer.files);
    }
  };

  return (
    <div 
      className="h-dvh-safe flex flex-col overflow-hidden relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {isDraggingOver && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-brand-subtle/80 backdrop-blur pointer-events-none">
          <div className="font-sans text-3xl font-semibold text-brand">Drop to audit</div>
        </div>
      )}
      <Toaster />
      <TopBar onMenuClick={() => setIsMobileSidebarOpen(true)} />
      <div
        className={cn(
          "flex flex-1 overflow-hidden transition-[grid-template-columns] duration-200 ease-smooth",
          "lg:grid",
          drawerOpen ? (desktopCollapsed ? "lg:grid-cols-[64px_minmax(0,1fr)_400px]" : "lg:grid-cols-[240px_minmax(0,1fr)_400px]") : (desktopCollapsed ? "lg:grid-cols-[64px_minmax(0,1fr)]" : "lg:grid-cols-[240px_minmax(0,1fr)]")
        )}
      >
        {/* Mobile Sidebar Overlay */}
        {isMobileSidebarOpen && (
          <div 
            className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm lg:hidden"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
        )}
        
        {/* Sidebar */}
        <div className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 lg:w-auto transform transition-transform duration-200 ease-smooth lg:static lg:translate-x-0 lg:block",
          isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          <Sidebar
            activeChatId={activeChatId}
            chats={chats}
            refetchChats={refetchChats}
            getConnectionId={getConnectionId}
            joinChat={joinChat}
            fileSizeLabels={fileSizeLabels}
            onUploaded={handleUploaded}
            onSelectChat={handleSelectChat}
            uploadZoneRef={uploadZoneRef}
            collapsed={desktopCollapsed}
            onToggleCollapse={toggleDesktopCollapsed}
            onCloseMobile={() => setIsMobileSidebarOpen(false)}
          />
        </div>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-surface relative">
          <MatrixView
            paperClaims={paperClaims}
            isLoading={isLoading}
            activePaperId={activePaperId}
            activeChatId={activeChatId}
            onViewEvidence={setSelectedClaimId}
            onUploadClick={() => uploadZoneRef.current?.openFilePicker()}
          />
        </main>
        
        {/* Evidence Drawer Mobile Overlay */}
        {drawerOpen && (
          <div 
            className="fixed inset-0 z-[55] bg-ink/40 backdrop-blur-sm lg:hidden"
            onClick={() => setSelectedClaimId(null)}
          />
        )}

        <div className={cn(
          "fixed inset-y-0 right-0 z-[60] w-full md:w-[400px] lg:w-auto transform transition-transform duration-200 ease-smooth lg:static lg:block shadow-drawer",
          drawerOpen ? "translate-x-0" : "translate-x-full lg:hidden"
        )}>
          {drawerOpen && (
            <EvidenceDrawer paperClaims={paperClaims} onClose={() => setSelectedClaimId(null)} />
          )}
        </div>
      </div>
    </div>
  );
}
