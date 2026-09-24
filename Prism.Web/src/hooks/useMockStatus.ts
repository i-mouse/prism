import { useState, useEffect } from "react";
import { acquireAccessToken } from "@/lib/auth";

type MockStatus = {
  enabled: boolean;
  mockFileCount: number;
  mockChatFileCount: number;
};

let cachedStatus: MockStatus = { enabled: false, mockFileCount: 0, mockChatFileCount: 0 };
let fetchPromise: Promise<MockStatus | void> | null = null;
const listeners = new Set<(status: MockStatus) => void>();

const fetchStatusRequest = async (force: boolean = false) => {
  if (fetchPromise && !force) {
    return fetchPromise;
  }

  fetchPromise = (async () => {
    try {
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const response = await fetch("/api/mock/status", { headers, credentials: "include" });
      if (response.ok) {
        const data = await response.json();
        cachedStatus = {
          enabled: data.enabled,
          mockFileCount: data.mockFileCount || 0,
          mockChatFileCount: data.mockChatFileCount || 0
        };
        listeners.forEach(l => l(cachedStatus));
        return cachedStatus;
      }
    } catch (e) {
      console.error("Failed to fetch mock status", e);
    }
  })();

  return fetchPromise;
};

export function useMockStatus(chats?: unknown[]) {
  const [status, setStatus] = useState<MockStatus>(cachedStatus);

  useEffect(() => {
    const listener = (newStatus: MockStatus) => {
      setStatus(newStatus);
    };
    listeners.add(listener);
    
    // Initial fetch if not done yet
    if (!fetchPromise) {
      fetchStatusRequest();
    }

    return () => {
      listeners.delete(listener);
    };
  }, []);

  // Re-fetch when chats change, if provided
  useEffect(() => {
    if (chats) {
      fetchStatusRequest(true);
    }
  }, [chats]);

  // Tab title update
  useEffect(() => {
    if (status.enabled) {
      if (!document.title.startsWith("[MOCK]")) {
        document.title = "[MOCK] " + document.title;
      }
    } else {
      document.title = document.title.replace(/^\[MOCK\]\s*/, "");
    }
    
    // Cleanup is not strictly necessary but good practice, though we want it persistent 
    // unless unmounted and false. But since we use a shared state, if all unmount, we 
    // leave the title as is? Actually, we want to leave the title if it's enabled.
  }, [status.enabled]);

  return { ...status, fetchStatus: () => fetchStatusRequest(true) };
}
