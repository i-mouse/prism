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

/**
 * Rewrites the grounder's log-line reason string into a readable
 * sentence for display. Falls back to the raw string when the
 * expected "N spans failed RapidFuzz... M spans failed LLM audit"
 * shape isn't found, since the reason format isn't a strict contract.
 */
export function humanizeReason(raw: string | null | undefined): string | null {
  if (!raw) return null;
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
