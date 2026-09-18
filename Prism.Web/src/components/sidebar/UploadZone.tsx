import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { acquireAccessToken } from "@/lib/auth";
import type { SubmitPaperResponse } from "@/types/api";

interface UploadZoneProps {
  getConnectionId: () => string | null;
  joinChat: (chatId: string) => Promise<void>;
  // Fires as soon as chatId is generated and the SignalR group joined —
  // before the POST is sent — so the log panel can mount and start
  // listening early instead of missing the earliest progress messages.
  onUploadStarted: (chatId: string, file: File) => void;
  onUploaded: (chatId: string, fileId: string, file: File, isCacheHit: boolean) => void;
  onUploadFailed: (chatId: string) => void;
  refetchChats: () => void;
  collapsed?: boolean;
}

export interface UploadZoneHandle {
  openFilePicker: () => void;
  handleFiles: (files: FileList | File[]) => void;
}

export const UploadZone = forwardRef<UploadZoneHandle, UploadZoneProps>(function UploadZone(
  { getConnectionId, joinChat, onUploadStarted, onUploaded, onUploadFailed, refetchChats, collapsed = false },
  ref
) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const processFiles = async (filesArray: File[]) => {
    if (filesArray.length === 0) return;

    if (filesArray.length > 1) {
      toast.error("Prism audits one paper at a time. Upload a single PDF.");
      return;
    }

    const connectionId = getConnectionId();
    if (!connectionId) {
      toast.error("Realtime connection not ready. Please wait a moment and try again.");
      return;
    }

    const chatId = crypto.randomUUID();
    const file = filesArray[0];

    setUploading(true);
    try {
      await joinChat(chatId);
      // Mount the log panel now, before the POST is sent — otherwise the
      // earliest progress messages (which the backend can emit synchronously
      // during the request) fire while nothing is listening yet.
      onUploadStarted(chatId, file);

      const formData = new FormData();
      // UserId intentionally omitted — backend resolves identity from JWT or
      // the prism-guest-session HttpOnly cookie. Never trust client-supplied IDs.
      formData.append("ConnectionId", connectionId);
      formData.append("ChatId", chatId);
      formData.append("Files", file);

      // Acquire a Bearer token for Google-authenticated users. Guest users have
      // no token; the guest-session cookie is sent automatically by the browser.
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/papers", { method: "POST", body: formData, headers, credentials: "include" });
      if (!res.ok) {
        // The backend returns a ProblemDetails body (e.g. the guest 2-paper
        // limit) — surface its "detail" text instead of a generic message.
        const body = await res.text().catch(() => "");
        let detail: string | undefined;
        try {
          detail = JSON.parse(body)?.detail;
        } catch {
          // not JSON — fall through to the generic message below
        }
        throw new Error(detail || body || `Upload failed: ${res.statusText}`);
      }

      const submitResponse: SubmitPaperResponse = await res.json();

      refetchChats();

      const filesHeaders: HeadersInit = {};
      const filesToken = await acquireAccessToken();
      if (filesToken) {
        filesHeaders["Authorization"] = `Bearer ${filesToken}`;
      }

      const filesRes = await fetch(`/api/chats/${chatId}/files`, { headers: filesHeaders, credentials: "include" });
      if (filesRes.ok) {
        const chatFiles: Array<{ fileId: string }> = await filesRes.json();
        const fileId = chatFiles[0]?.fileId;
        if (fileId) {
          onUploaded(chatId, fileId, file, submitResponse.isCacheHit === true);
        }
      }
    } catch (err) {
      console.error("Upload error:", err);
      const message = err instanceof Error && err.message ? err.message : "Upload failed. Please check if the backend is running.";
      toast.error(message);
      onUploadFailed(chatId);
    } finally {
      setUploading(false);
    }
  };

  useImperativeHandle(ref, () => ({
    openFilePicker: () => inputRef.current?.click(),
    handleFiles: (files) => processFiles(Array.from(files)),
  }));

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    processFiles(files);
  };

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        hidden
        multiple
        accept=".pdf"
        onChange={handleChange}
      />
      <Button
        className={cn(
          "h-auto w-full gap-2 rounded-lg bg-slate-800 px-4 py-2.5 font-sans text-sm font-medium text-white hover:bg-slate-900 focus-visible:ring-2 focus-visible:ring-slate-400 transition-all duration-150 ease-smooth",
          collapsed ? "px-0 justify-center min-w-[2.75rem]" : ""
        )}
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        title={collapsed ? "Upload & Analyze" : undefined}
      >
        <Upload className={cn("h-4 w-4", collapsed && "mx-auto")} />
        {!collapsed && (uploading ? "Uploading..." : "Upload & Analyze")}
      </Button>
    </div>
  );
});
