import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { acquireAccessToken } from "@/lib/auth";

interface MockCleanupButtonProps {
  onSuccess: () => void;
  collapsed?: boolean;
  chats?: any[];
}

export function MockCleanupButton({ onSuccess, collapsed, chats }: MockCleanupButtonProps) {
  const [enabled, setEnabled] = useState(false);
  const [fileCount, setFileCount] = useState(0);
  const [chatFileCount, setChatFileCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);

  const fetchStatus = async () => {
    try {
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const response = await fetch("/api/mock/status", { headers, credentials: "include" });
      if (response.ok) {
        const data = await response.json();
        setEnabled(data.enabled);
        setFileCount(data.mockFileCount);
        setChatFileCount(data.mockChatFileCount || 0);
      }
    } catch (e) {
      console.error("Failed to fetch mock status", e);
    }
  };

  // Fetch on mount, and re-fetch whenever the parent's chat list refreshes
  useEffect(() => {
    fetchStatus();
  }, [chats]);

  if (!enabled) {
    return null;
  }

  const handleCleanup = async () => {
    setIsCleaning(true);
    try {
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const response = await fetch("/api/mock/cleanup", {
        method: "POST",
        headers,
        credentials: "include"
      });
      if (response.ok) {
        const result = await response.json();
        toast.success(`Cleaned up ${result.deletedFiles} paper${result.deletedFiles === 1 ? "" : "s"} and ${result.deletedChats} chat${result.deletedChats === 1 ? "" : "s"} from mock extraction.`);
        await fetchStatus();
        onSuccess();
      } else {
        console.error("Cleanup failed", await response.text());
        toast.error("Cleanup failed");
      }
    } catch (e) {
      console.error("Cleanup request failed", e);
      toast.error("Cleanup request failed");
    } finally {
      setIsCleaning(false);
      setIsOpen(false);
    }
  };

  return (
    <>
      <Button
        variant="ghost"
        size={collapsed ? "icon" : "sm"}
        onClick={() => setIsOpen(true)}
        className="w-full mt-2 justify-start text-red-600 hover:text-red-700 hover:bg-red-50"
      >
        <Trash2 className="h-4 w-4 shrink-0" />
        {!collapsed && <span className="ml-2 truncate">Clean up mock data{fileCount > 0 ? ` (${fileCount})` : ""}</span>}
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clean up mock data?</DialogTitle>
            <DialogDescription>
              This will permanently delete {fileCount} mock-generated paper{fileCount === 1 ? "" : "s"}, removing {chatFileCount} linked upload{chatFileCount === 1 ? "" : "s"} from your sidebar.
              Real papers and Azure Blob Storage will not be affected.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)} disabled={isCleaning}>
              Cancel
            </Button>
            <Button
              onClick={(e: React.MouseEvent) => {
                e.preventDefault();
                handleCleanup();
              }}
              disabled={isCleaning || fileCount === 0}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isCleaning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Delete mock data"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
