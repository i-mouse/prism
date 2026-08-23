import { useEffect } from "react";
import { signalRService } from "@/services/signalRService";

export function useSignalR() {
  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL;
    signalRService.start(baseUrl).catch(() => {
      // Errors are already logged inside signalRService; nothing further to do here.
    });
  }, []);

  return {
    joinChat: (chatId: string) => signalRService.joinChat(chatId),
    on: (event: string, callback: (...args: unknown[]) => void) =>
      signalRService.on(event, callback),
    off: (event: string, callback?: (...args: unknown[]) => void) =>
      signalRService.off(event, callback),
    getConnectionId: () => signalRService.connectionId,
  };
}
