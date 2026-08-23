import { useEffect, useState } from "react";

const CHAT_ID_KEY = "prism_active_chat";
const PAPER_ID_KEY = "prism_active_paper";

export function useActivePaper() {
  const [activeChatId, setActiveChatIdState] = useState<string>(() => {
    return sessionStorage.getItem(CHAT_ID_KEY) || crypto.randomUUID();
  });
  const [activePaperId, setActivePaperIdState] = useState<string | null>(() => {
    return sessionStorage.getItem(PAPER_ID_KEY);
  });

  useEffect(() => {
    sessionStorage.setItem(CHAT_ID_KEY, activeChatId);
  }, [activeChatId]);

  useEffect(() => {
    if (activePaperId) {
      sessionStorage.setItem(PAPER_ID_KEY, activePaperId);
    } else {
      sessionStorage.removeItem(PAPER_ID_KEY);
    }
  }, [activePaperId]);

  const setActiveChatId = (chatId: string) => {
    setActiveChatIdState(chatId);
  };

  const setActivePaperId = (paperId: string | null) => {
    setActivePaperIdState(paperId);
  };

  return { activeChatId, setActiveChatId, activePaperId, setActivePaperId };
}
