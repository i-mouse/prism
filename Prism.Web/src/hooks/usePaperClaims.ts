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
  // Completed papers only. Completed is terminal for every flow the UI can
  // reach: claims are read from the newest DocumentExtractor row, and the
  // only thing that ever adds another one is POST /api/papers/{id}/rerun,
  // which nothing in the app calls. A Pending/In progress/Failed paper is
  // deliberately never stored, so a paper still being audited always
  // re-fetches and a DocumentProcessed event can never be hidden behind a
  // stale entry.
  const completedClaimsCacheRef = useRef<Map<string, PaperClaimsResponse>>(new Map());

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
      // Cached under the paper it was fetched FOR, so it stays useful even
      // when the active paper has moved on since. Written on every
      // successful response - set when Completed, deleted otherwise - so
      // refetch() can always overwrite what's cached, including dropping a
      // Completed entry whose paper is no longer Completed.
      if (json.extractionStatus === "Completed") {
        completedClaimsCacheRef.current.set(requestedPaperId, json);
      } else {
        completedClaimsCacheRef.current.delete(requestedPaperId);
      }
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

  const clearCache = useCallback(() => {
    completedClaimsCacheRef.current.clear();
  }, []);

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
    // A cached paper is served straight from the render below - there is
    // nothing to fetch, and no loading state to enter.
    if (paperId && completedClaimsCacheRef.current.has(paperId)) return;
    fetchClaims();
  }, [fetchClaims]);

  // Read during render rather than copied into state: switching back to an
  // already-completed paper must produce its claims on the SAME render that
  // changed paperId. Routing it through setData would render once with the
  // previous paper's response still in place - MatrixView's brief, honest
  // "0 claims" state - before correcting itself, reintroducing exactly the
  // flicker this cache exists to remove. Falling back to `data` on a miss
  // preserves the no-null behaviour described above unchanged.
  //
  // react-hooks/refs forbids reading a ref during render because the value
  // can change between render and commit, leaving the committed output
  // stale. It converges here: the only writer is the fetch continuation
  // above, and every write that concerns the CURRENTLY rendered paper is
  // paired with the setData(json) on the next line, which schedules the
  // re-render that picks the entry up. A write for any OTHER paper cannot
  // affect this render's output, since it is keyed by a paperId this render
  // does not read. React Compiler is not enabled in this project, so no
  // memoization can skip that re-render either.
  // eslint-disable-next-line react-hooks/refs
  const cachedClaims = paperId ? completedClaimsCacheRef.current.get(paperId) : undefined;

  // isLoading/error are derived here too rather than written by the effect
  // above: a cache hit must report "not loading, no error" on the very
  // first render of the switch, instead of leaving the previous paper's
  // values standing for a frame while an effect catches up. Nothing
  // consumes either today (AppShell destructures only data + refetch), so
  // this costs nothing now and keeps the hook honest for whatever does.
  return {
    data: cachedClaims ?? data,
    isLoading: cachedClaims ? false : isLoading,
    error: cachedClaims ? null : error,
    refetch: fetchClaims,
    clearCache,
  };
}
