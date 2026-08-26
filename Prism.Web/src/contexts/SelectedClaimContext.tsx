import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

interface SelectedClaimContextValue {
  selectedClaimId: string | null;
  setSelectedClaimId: (claimId: string | null) => void;
  highlightedClaimId: string | null;
  highlightClaim: (claimId: string) => void;
}

const SelectedClaimContext = createContext<SelectedClaimContextValue | null>(null);

const HIGHLIGHT_DURATION_MS = 2000;

export function SelectedClaimProvider({ children }: { children: ReactNode }) {
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [highlightedClaimId, setHighlightedClaimId] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const highlightClaim = useCallback((claimId: string) => {
    if (highlightTimeoutRef.current) {
      clearTimeout(highlightTimeoutRef.current);
    }
    setHighlightedClaimId(claimId);
    highlightTimeoutRef.current = setTimeout(() => {
      setHighlightedClaimId(null);
      highlightTimeoutRef.current = null;
    }, HIGHLIGHT_DURATION_MS);
  }, []);

  const value = useMemo(
    () => ({ selectedClaimId, setSelectedClaimId, highlightedClaimId, highlightClaim }),
    [selectedClaimId, highlightedClaimId, highlightClaim]
  );

  return (
    <SelectedClaimContext.Provider value={value}>{children}</SelectedClaimContext.Provider>
  );
}

export function useSelectedClaim() {
  const ctx = useContext(SelectedClaimContext);
  if (!ctx) {
    throw new Error("useSelectedClaim must be used within a SelectedClaimProvider");
  }
  return ctx;
}
