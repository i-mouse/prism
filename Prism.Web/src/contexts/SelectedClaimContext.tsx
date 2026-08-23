import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface SelectedClaimContextValue {
  selectedClaimId: string | null;
  setSelectedClaimId: (claimId: string | null) => void;
}

const SelectedClaimContext = createContext<SelectedClaimContextValue | null>(null);

export function SelectedClaimProvider({ children }: { children: ReactNode }) {
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);

  const value = useMemo(() => ({ selectedClaimId, setSelectedClaimId }), [selectedClaimId]);

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
