import { useCallback, useEffect, useState } from "react";
import type { PaperClaimsResponse } from "@/types/api";

export function usePaperClaims(paperId: string | null) {
  const [data, setData] = useState<PaperClaimsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchClaims = useCallback(async () => {
    if (!paperId) {
      setData(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/papers/${paperId}/claims`);
      if (!res.ok) throw new Error(`Failed to load claims: ${res.status}`);
      const json: PaperClaimsResponse = await res.json();
      setData(json);
    } catch (err) {
      console.error("usePaperClaims error:", err);
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setIsLoading(false);
    }
  }, [paperId]);

  useEffect(() => {
    fetchClaims();
  }, [fetchClaims]);

  return { data, isLoading, error, refetch: fetchClaims };
}
