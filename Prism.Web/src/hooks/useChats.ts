import { useCallback, useEffect, useState } from "react";
import type { ChatListItem } from "@/types/api";
import { acquireAccessToken } from "@/lib/auth";

export function useChats() {
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchChats = useCallback(async () => {
    setIsLoading(true);
    try {
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/chats", { headers, credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch chats");
      const data: ChatListItem[] = await res.json();
      setChats(data);
    } catch (err) {
      console.error("useChats error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchChats();
  }, [fetchChats]);

  return { chats, isLoading, refetch: fetchChats };
}
