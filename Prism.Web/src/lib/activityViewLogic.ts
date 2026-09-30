import type { ExtractionStatus } from "@/types/api";

export type RowStatus = "completed" | "current" | "pending" | "failed";

export interface ActivityViewFailureSource {
  paperId: string;
  extractionStatus: ExtractionStatus;
  failureReason?: string | null;
}

export interface ActivityViewFailureProps {
  extractionStatus: ExtractionStatus | "In progress";
  failureReason?: string | null;
}

/**
 * B3.6 fix: only pass a paper's status/failure data through to a
 * freshly-mounted PaperActivityView when paperClaims genuinely belongs to
 * the currently active paper. Without this guard, a re-render where
 * activePaperId has already moved on but paperClaims hasn't caught up yet
 * (usePaperClaims resets to null via an effect, one render behind
 * setActivePaperId) feeds the PREVIOUS paper's Failed status/reason into
 * the new paper's initial props - and a synthesized log line derived from
 * that stale reason gets permanently committed to the new paper's own,
 * otherwise-correctly-scoped state.
 */
export function selectActivityViewFailureProps(
  paperClaims: ActivityViewFailureSource | null | undefined,
  activePaperId: string | null,
  cacheHitPending: boolean
): ActivityViewFailureProps {
  const current = paperClaims && paperClaims.paperId === activePaperId ? paperClaims : null;
  return {
    extractionStatus: (!current || cacheHitPending) ? "In progress" : current.extractionStatus,
    failureReason: current?.failureReason,
  };
}

/**
 * B3.6 fix: idempotency check for the fetched-only-path synthesized log
 * line. `alreadySynthesized` must come from a ref in the caller, not React
 * state - React 18 StrictMode double-invokes an effect on mount against
 * the SAME closure before either invocation's setState is visible to the
 * other, so a check against `logs` state alone can't see its own prior
 * write yet on the second invocation. A ref mutates synchronously between
 * the two invocations and closes that gap.
 */
export function shouldSynthesizeFailureLine(
  alreadySynthesized: boolean,
  hasFailed: boolean,
  logs: { stage: string }[]
): boolean {
  if (!hasFailed) return false;
  if (alreadySynthesized) return false;
  if (logs.some((l) => l.stage === "failed")) return false;
  return true;
}

/**
 * B3.7 fix: failedIndex === -1 means the real failed stage isn't known -
 * the live event carries it, but nothing persists it for the fetched-only
 * path (refresh, missed/reconnect-delayed broadcast). Every row renders
 * "pending" in that case: never guess a specific step as failed, and never
 * mark earlier ones as falsely completed just because a guess wasn't made.
 */
export function stepperRowStatus(
  index: number,
  hasFailed: boolean,
  failedIndex: number,
  currentIndex: number
): RowStatus {
  if (hasFailed) {
    if (failedIndex === -1) return "pending";
    if (index === failedIndex) return "failed";
    return index < failedIndex ? "completed" : "pending";
  }
  if (index < currentIndex) return "completed";
  if (index === currentIndex) return "current";
  return "pending";
}
