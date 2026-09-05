import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  getConnectionId: () => string | null;
  joinChat: (chatId: string) => Promise<void>;
  onUploaded: (chatId: string, fileId: string, file: File) => void;
  refetchChats: () => void;
  collapsed?: boolean;
}

export interface UploadZoneHandle {
  openFilePicker: () => void;
  handleFiles: (files: FileList | File[]) => void;
}

export const UploadZone = forwardRef<UploadZoneHandle, UploadZoneProps>(function UploadZone(
  { getConnectionId, joinChat, onUploaded, refetchChats, collapsed = false },
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

      const formData = new FormData();
      formData.append("UserId", "demo-user-01");
      formData.append("ConnectionId", connectionId);
      formData.append("ChatId", chatId);
      formData.append("Files", file);

      const res = await fetch("/api/papers", { method: "POST", body: formData });
      if (!res.ok) {
        const message = await res.text().catch(() => "");
        throw new Error(message || `Upload failed: ${res.statusText}`);
      }

      refetchChats();

      const filesRes = await fetch(`/api/chats/${chatId}/files`);
      if (filesRes.ok) {
        const chatFiles: Array<{ fileId: string }> = await filesRes.json();
        const fileId = chatFiles[0]?.fileId;
        if (fileId) {
          onUploaded(chatId, fileId, file);
        }
      }
    } catch (err) {
      console.error("Upload error:", err);
      toast.error("Upload failed. Please check if the backend is running.");
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
          "h-auto w-full gap-2 rounded-lg bg-brand px-4 py-2.5 font-sans text-sm font-medium text-white hover:bg-brand-hover focus-visible:ring-2 focus-visible:ring-brand-subtle transition-all duration-150 ease-smooth",
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
