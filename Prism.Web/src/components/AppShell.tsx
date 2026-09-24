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
import { useAuth } from "@/lib/AuthContext";
import { acquireAccessToken } from "@/lib/auth";
import { GuestBanner } from "@/components/GuestBanner";
import { MockBanner } from "@/components/MockBanner";
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

export function AppShell() {
  const { paperId: routeChatId } = useParams<{ paperId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const routeClaimId = searchParams.get("claim");
  const { user } = useAuth();

  const { activeChatId, setActiveChatId, activePaperId, setActivePaperId } = useActivePaper();
  const { chats, refetch: refetchChats } = useChats();
  const { data: paperClaims, refetch: refetchClaims } = usePaperClaims(activePaperId);
  const { joinChat, on, off, getConnectionId } = useSignalR();
  const { selectedClaimId, setSelectedClaimId } = useSelectedClaim();
  const [fileSizeLabels, setFileSizeLabels] = useState<Record<string, string>>({});

  // Set the moment an upload begins (before the POST resolves) so the log
  // panel can mount immediately instead of waiting on fileId, which the
  // backend only hands back once the request completes. Cleared once the
  // real fileId arrives (or the upload fails).
  const [pendingUpload, setPendingUpload] = useState<{ chatId: string; fileName: string } | null>(null);
  // The paperId of a paper whose most recent upload was a cache hit and
  // whose inline Continue/Re-run decision hasn't been resolved yet. Cleared
  // once the user picks one of those options.
  const [cacheHitPaperId, setCacheHitPaperId] = useState<string | null>(null);

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

  // Once real claims data exists for the active paper, the normal
  // paperClaims-driven rendering in MatrixView takes over — drop the
  // upload-in-flight placeholder so it doesn't linger or fight with it.
  useEffect(() => {
    if (pendingUpload && activePaperId && paperClaims) {
      setPendingUpload(null);
    }
  }, [pendingUpload, activePaperId, paperClaims]);

  useEffect(() => {
    const handleDocumentProcessed = (data: unknown) => {
      const payload = data as { chatId?: string; fileId?: string };
      refetchChats();
      if ((payload?.chatId && payload.chatId === activeChatId) || (payload?.fileId && payload.fileId === activePaperId)) {
        refetchClaims();
      }
    };

    on("DocumentProcessed", handleDocumentProcessed);
    return () => off("DocumentProcessed", handleDocumentProcessed);
  }, [on, off, activeChatId, activePaperId, refetchChats, refetchClaims]);

  const fetchChatFiles = async (chatId: string) => {
    try {
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`/api/chats/${chatId}/files`, { headers, credentials: "include" });
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
      // Navigating to a different chat (e.g. picking another paper from the
      // sidebar) while an unrelated upload is still in flight must not leave
      // that upload's placeholder showing here.
      setPendingUpload((prev) => (prev && prev.chatId !== routeChatId ? null : prev));
    } else if (!routeChatId && activeChatId) {
      // Empty state
      setActiveChatId("");
      setActivePaperId(null);
      setPendingUpload(null);
    }
  }, [routeChatId]);

  const handleSelectChat = useCallback(
    (chatId: string) => {
      setIsMobileSidebarOpen(false);
      navigate(`/paper/${chatId}`);
    },
    [navigate]
  );

  const handleUploadStarted = useCallback(
    (chatId: string, file: File) => {
      setFileSizeLabels((prev) => ({ ...prev, [chatId]: formatFileSize(file.size) }));
      setIsMobileSidebarOpen(false);
      setActiveChatId(chatId);
      setActivePaperId(null);
      setCacheHitPaperId(null);
      setPendingUpload({ chatId, fileName: file.name });
      navigate(`/paper/${chatId}`);
    },
    [navigate, setActiveChatId, setActivePaperId]
  );

  const handleUploaded = useCallback(
    (chatId: string, fileId: string, file: File, isCacheHit: boolean) => {
      setFileSizeLabels((prev) => ({ ...prev, [chatId]: formatFileSize(file.size) }));
      setIsMobileSidebarOpen(false);
      setActiveChatId(chatId);
      setActivePaperId(fileId);
      setCacheHitPaperId(isCacheHit ? fileId : null);
      navigate(`/paper/${chatId}`);
    },
    [navigate, setActiveChatId, setActivePaperId]
  );

  const handleUploadFailed = useCallback(
    (chatId: string) => {
      setPendingUpload((prev) => (prev?.chatId === chatId ? null : prev));
      // Only bail back to the empty state if the user hasn't already
      // navigated elsewhere while the failed upload was in flight.
      if (activeChatId === chatId) {
        setActiveChatId("");
        setActivePaperId(null);
        navigate("/");
      }
    },
    [activeChatId, navigate, setActiveChatId, setActivePaperId]
  );

  const handleCacheHitResolved = useCallback(() => {
    setCacheHitPaperId(null);
  }, []);

  // Guest "Cancel" on the inline decision: the ownership link
  // (PrismDocuments/ChatFiles) that HandleCacheHitAsync already committed is
  // left in place rather than actively unlinked — it's harmless (IDOR checks
  // already gate every read on it, and it's invisible/inert to everyone but
  // this guest) and there's no backend endpoint for undoing it. Just reset
  // to the empty upload state so a different file can be picked immediately.
  const handleCacheHitCancel = useCallback(() => {
    setCacheHitPaperId(null);
    setActiveChatId("");
    setActivePaperId(null);
    navigate("/");
  }, [navigate, setActiveChatId, setActivePaperId]);

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
      className="h-dvh-safe flex flex-col overflow-hidden relative bg-surface-subtle"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Drag-over overlay */}
      {isDraggingOver && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-brand-subtle/80 backdrop-blur pointer-events-none">
          <div className="font-sans text-3xl font-semibold text-brand">Drop to audit</div>
        </div>
      )}

      <Toaster />

      {/* Mobile TopBar — hidden on desktop (sidebar carries the logo there) */}
      <TopBar onMenuClick={() => setIsMobileSidebarOpen(true)} />

      {user?.provider === "guest" && <GuestBanner />}
      <MockBanner />

      {/* ── 3-pane layout ───────────────────────────────────────────────── */}
      <div
        className={cn(
          "flex flex-1 overflow-hidden",
          "lg:grid lg:grid-rows-[minmax(0,1fr)]",
          drawerOpen
            ? desktopCollapsed
              ? "lg:grid-cols-[64px_minmax(0,1fr)_400px]"
              : "lg:grid-cols-[260px_minmax(0,1fr)_400px]"
            : desktopCollapsed
              ? "lg:grid-cols-[64px_minmax(0,1fr)]"
              : "lg:grid-cols-[260px_minmax(0,1fr)]"
        )}
      >
        {/* ── Mobile sidebar overlay backdrop ─────────────────────────── */}
        {isMobileSidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm lg:hidden"
            onClick={() => setIsMobileSidebarOpen(false)}
          />
        )}

        {/* ── Left Sidebar ─────────────────────────────────────────────── */}
        <div
          className={cn(
            "fixed inset-y-0 left-0 z-50 w-72 lg:w-auto transform transition-transform duration-200 ease-smooth lg:static lg:translate-x-0 lg:block",
            isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
          )}
        >
          <Sidebar
            activeChatId={activeChatId}
            chats={chats}
            refetchChats={refetchChats}
            getConnectionId={getConnectionId}
            joinChat={joinChat}
            fileSizeLabels={fileSizeLabels}
            completedAt={paperClaims?.completedAt}
            onUploadStarted={handleUploadStarted}
            onUploaded={handleUploaded}
            onUploadFailed={handleUploadFailed}
            onSelectChat={handleSelectChat}
            uploadZoneRef={uploadZoneRef}
            collapsed={belowLg ? false : desktopCollapsed}
            onToggleCollapse={toggleDesktopCollapsed}
            onCloseMobile={() => setIsMobileSidebarOpen(false)}
          />
        </div>

        {/* ── Main Content ─────────────────────────────────────────────── */}
        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-surface-subtle relative">
          {/* Inner white card container with slight inset */}
          <div className="flex h-full flex-col overflow-hidden lg:m-3 lg:rounded-xl lg:border lg:border-hairline lg:bg-surface lg:shadow-card">
            <MatrixView
              paperClaims={paperClaims}
              activePaperId={activePaperId}
              activeChatId={activeChatId}
              pendingUpload={pendingUpload}
              cacheHitPending={cacheHitPaperId !== null && cacheHitPaperId === activePaperId}
              onCacheHitResolved={handleCacheHitResolved}
              onCacheHitCancel={handleCacheHitCancel}
              onViewEvidence={setSelectedClaimId}
              onUploadClick={() => uploadZoneRef.current?.openFilePicker()}
              isGoogleUser={user?.provider === "google"}
            />
          </div>
        </main>

        {/* ── Evidence Drawer mobile backdrop ──────────────────────────── */}
        {drawerOpen && (
          <div
            className="fixed inset-0 z-[55] bg-ink/40 backdrop-blur-sm lg:hidden"
            onClick={() => setSelectedClaimId(null)}
          />
        )}

        {/* ── Right Evidence Drawer ─────────────────────────────────────── */}
        <div
          className={cn(
            "fixed inset-y-0 right-0 z-[60] w-full md:w-[400px] lg:w-auto transform transition-transform duration-200 ease-smooth lg:static lg:block",
            drawerOpen ? "translate-x-0" : "translate-x-full lg:hidden"
          )}
        >
          {drawerOpen && (
            <EvidenceDrawer
              paperClaims={paperClaims}
              onClose={() => setSelectedClaimId(null)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
