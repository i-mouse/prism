import type { ClaimDto, ClaimLabel } from "@/types/api";

/**
 * Which label the UI should display for a claim.
 * When the grounder vetoes evidence (missing=true), the pill
 * shows NOT SUPPORTED regardless of the extractor's optimistic
 * label. This honors the correct-refusal thesis: the grounder
 * is the final verdict on display, not the extractor.
 * The raw claim.label remains available for diagnostic purposes.
 */
export function displayLabel(claim: ClaimDto): ClaimLabel {
  return claim.missing ? "not_supported" : claim.label;
}

export type ClaimEvidenceState =
  | "no_evidence"             // missing + Fail, zero spans
  | "evidence_insufficient"   // missing + Fail, spans present
  | "check_incomplete"        // Skipped
  | "evidence_contradicts"    // not_supported, Pass/Partial
  | "ok"                      // supported / partially_supported, Pass/Partial
  | "invalid";                // violates the grounder's invariants

export interface ClaimEvidenceNote {
  state: ClaimEvidenceState;
  /** Subtitle under the claim in the matrix list; null = none. */
  listText: string | null;
  /** Note box in the evidence drawer; null = none. */
  drawerText: string | null;
}

const warnedInvalidClaimIds = new Set<string>();

/**
 * Single source of truth for the evidence note shown in both the
 * matrix list row and the evidence drawer, so the two always agree.
 * Mirrors the grounder's rollup (grounding.py): missing=true iff
 * groundingStatus=Fail, and a claim with zero spans is always Fail.
 * Anything outside that is an invariant violation and gets a neutral
 * fallback plus a console.warn (once per claim).
 */
export function claimEvidenceNote(claim: ClaimDto): ClaimEvidenceNote {
  const spanCount = claim.evidenceSpans.length;
  const status = claim.groundingStatus;

  const violation =
    (claim.missing && status !== "Fail") ||
    (!claim.missing && status === "Fail") ||
    (!claim.missing && spanCount === 0);

  if (violation) {
    if (!warnedInvalidClaimIds.has(claim.id)) {
      warnedInvalidClaimIds.add(claim.id);
      console.warn("[claim-state] invariant violation", {
        claimId: claim.id,
        missing: claim.missing,
        groundingStatus: status,
        label: claim.label,
        evidenceSpanCount: spanCount,
      });
    }
    return {
      state: "invalid",
      listText: "Unable to render claim state",
      drawerText: "Unable to render claim state",
    };
  }

  if (claim.missing) {
    return spanCount === 0
      ? {
          state: "no_evidence",
          listText: "No supporting evidence found",
          drawerText: "No evidence was cited for this claim.",
        }
      : {
          state: "evidence_insufficient",
          listText: "Cited evidence considered — none sufficient",
          drawerText: "The auditor considered the cited evidence but found none sufficient to support this claim.",
        };
  }

  if (status === "Skipped") {
    return {
      state: "check_incomplete",
      listText: "Evidence check incomplete",
      drawerText: "Evidence check incomplete — grounding verification unavailable for this claim.",
    };
  }

  if (claim.label === "not_supported") {
    return {
      state: "evidence_contradicts",
      listText: "Cited evidence doesn't support this claim",
      drawerText: null,
    };
  }

  return { state: "ok", listText: null, drawerText: null };
}

/**
 * Rewrites the grounder's log-line reason string into a readable
 * sentence for display. Falls back to the raw string when neither
 * the Fail shape ("N spans failed RapidFuzz... M spans failed LLM
 * audit") nor the Partial shape ("accepted... as partial support")
 * is found, since the reason format isn't a strict contract.
 */
export function humanizeReason(raw: string | null | undefined): string | null {
  if (!raw) return null;

  const partialMatch = raw.match(/accepted the cited evidence as partial support:\s*(\d+)\s+passages?/i);
  if (partialMatch) {
    const count = parseInt(partialMatch[1], 10);
    return `The auditor found partial support: ${count} passage${count === 1 ? "" : "s"} touched on the claim but did not fully confirm it.`;
  }

  const match = raw.match(
    /(\d+)\s+spans?\s+failed\s+RapidFuzz.*?(\d+)\s+spans?\s+failed\s+LLM\s+audit/i
  );
  if (!match) return raw;
  const rapid = parseInt(match[1], 10);
  const llm = parseInt(match[2], 10);
  const total = rapid + llm;
  if (total === 0) return "The auditor rejected the cited evidence.";
  const parts: string[] = [];
  if (rapid > 0) {
    parts.push(`${rapid} passage${rapid === 1 ? "" : "s"} could not be located in the paper`);
  }
  if (llm > 0) {
    parts.push(`${llm} passage${llm === 1 ? "" : "s"} did not semantically support the claim`);
  }
  return `The auditor rejected the cited evidence: ${parts.join("; ")}.`;
}
