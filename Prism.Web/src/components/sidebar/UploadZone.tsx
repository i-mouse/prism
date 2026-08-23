import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";

interface UploadZoneProps {
  getConnectionId: () => string | null;
  joinChat: (chatId: string) => Promise<void>;
  onUploaded: (chatId: string, fileId: string, file: File) => void;
  refetchChats: () => void;
}

export function UploadZone({ getConnectionId, joinChat, onUploaded, refetchChats }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    // input.files is a live FileList tied to the element, so it must be
    // copied out before clearing e.target.value below (which also clears it).
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;

    if (files.length > 1) {
      toast.error("Prism audits one paper at a time. Upload a single PDF.");
      return;
    }

    const connectionId = getConnectionId();
    if (!connectionId) {
      toast.error("Realtime connection not ready. Please wait a moment and try again.");
      return;
    }

    const chatId = crypto.randomUUID();
    const file = files[0];

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
        className="h-11 w-full gap-2 bg-accent font-medium text-accent-fg shadow-card hover:bg-accent-hover"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
      >
        <Upload className="h-4 w-4" />
        {uploading ? "Uploading..." : "Upload & Analyze"}
      </Button>
    </div>
  );
}
