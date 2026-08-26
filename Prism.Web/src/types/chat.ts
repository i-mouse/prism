export type ChatBlock =
  | { type: "text"; content: string }
  | {
      type: "claim_reference";
      claim_id: string;
      claim_summary: string;
      display_label: "supported" | "partially_supported" | "not_supported";
    };

export interface ChatTurn {
  role: "user" | "assistant";
  blocks: ChatBlock[];
  timestamp: number;
  isStreaming?: boolean;
}

export interface ChatStripState {
  turns: ChatTurn[];
  isSending: boolean;
  error: string | null;
}
