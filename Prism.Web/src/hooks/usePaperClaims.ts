import { useCallback, useEffect, useRef, useState } from "react";
import { acquireAccessToken } from "@/lib/auth";
import type { PaperClaimsResponse } from "@/types/api";

export function usePaperClaims(paperId: string | null) {
  const [data, setData] = useState<PaperClaimsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The paperId this hook should currently be showing data for. Lets a
  // fetch whose paperId has since changed underneath it - rapid A->B->C
  // switching, or a manual refetch() racing a later paperId change -
  // detect it's stale and skip writing, the same guard purpose as
  // useChatStream.ts's `cancelled` flag on its history-hydration effect.
  const latestPaperIdRef = useRef(paperId);

  const fetchClaims = useCallback(async () => {
    const requestedPaperId = paperId;
    if (!requestedPaperId) {
      setData(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const headers: HeadersInit = {};
      const token = await acquireAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`/api/papers/${requestedPaperId}/claims`, { headers, credentials: "include" });
      if (!res.ok) throw new Error(`Failed to load claims: ${res.status}`);
      const json: PaperClaimsResponse = await res.json();
      if (latestPaperIdRef.current !== requestedPaperId) return;
      setData(json);
    } catch (err) {
      if (latestPaperIdRef.current !== requestedPaperId) return;
      console.error("usePaperClaims error:", err);
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      if (latestPaperIdRef.current === requestedPaperId) {
        setIsLoading(false);
      }
    }
  }, [paperId]);

  // Deliberately does NOT null `data` here just because paperId changed:
  // MatrixView's showSkeleton branch treats `!paperClaims` as "nothing to
  // show yet" and swaps the whole matrix view out for a full-page skeleton
  // - nulling data on every switch between two already-loaded papers was
  // tried and re-triggered exactly that, tearing down (and losing scroll/
  // filter state in) everything under it, including ClaimList, on every
  // switch - the same class of disruption this whole fix exists to remove,
  // just via a different path. `data.paperId` (PaperClaimsResponse already
  // carries it) is what lets a consumer detect "this doesn't match the
  // paper I'm currently showing yet" and render accordingly - see
  // MatrixView.tsx's `currentPaperClaims`.
  useEffect(() => {
    latestPaperIdRef.current = paperId;
    fetchClaims();
  }, [fetchClaims]);

  return { data, isLoading, error, refetch: fetchClaims };
}
