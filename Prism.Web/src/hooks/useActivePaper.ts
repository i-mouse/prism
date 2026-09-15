import { useEffect, useState } from "react";

const CHAT_ID_KEY = "prism_active_chat";
const PAPER_ID_KEY = "prism_active_paper";

export function useActivePaper() {
  // No random-UUID fallback here: a phantom chatId with nothing behind it
  // would get joined via SignalR by AppShell's "keep active chat joined"
  // effect before the route-sync effect below ever corrects it — producing
  // a real, pointless group join unrelated to any actual chat. "" is a
  // clean "no chat yet" sentinel; the upload flow and the route-sync effect
  // are the only things that should ever introduce a real chatId.
  const [activeChatId, setActiveChatIdState] = useState<string>(() => {
    return sessionStorage.getItem(CHAT_ID_KEY) || "";
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
