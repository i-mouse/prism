import { useCallback, useEffect, useState } from "react";
import type { ChatListItem } from "@/types/api";

export function useChats(userId: string) {
  const [chats, setChats] = useState<ChatListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchChats = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/chats/${userId}`);
      if (!res.ok) throw new Error("Failed to fetch chats");
      const data: ChatListItem[] = await res.json();
      setChats(data);
    } catch (err) {
      console.error("useChats error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchChats();
  }, [fetchChats]);

  return { chats, isLoading, refetch: fetchChats };
}
