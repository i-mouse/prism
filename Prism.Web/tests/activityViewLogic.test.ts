// Run with: npm test (node --test tests/*.test.ts)
// Node 24 runs .ts files with node:test natively - no test framework
// installed for this project, and this doesn't need one: these are pure
// functions extracted specifically so B3.6/B3.7 are testable without
// rendering React or touching the DOM. Lives outside src/ (like
// Prism.PythonService/tests/ sits outside its source tree) so tsc -b's
// app build, which has no Node types in scope, never has to see it.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  selectActivityViewFailureProps,
  shouldSynthesizeFailureLine,
  stepperRowStatus,
} from "../src/lib/activityViewLogic.ts";

// ---------------------------------------------------------------------------
// B3.6a: paperId mismatch must yield no failure data
// ---------------------------------------------------------------------------

test("selectActivityViewFailureProps: mismatched paperId yields no failure data", () => {
  const staleFailedPaper = {
    paperId: "test-pdf-id",
    extractionStatus: "Failed" as const,
    failureReason: "corrupted PDF - cannot extract text",
  };

  // activePaperId has already moved on to a different (or not-yet-known)
  // paper, but paperClaims still holds the PREVIOUS paper's Failed response
  // - exactly the one-render race behind B3.6.
  const result = selectActivityViewFailureProps(staleFailedPaper, "different-paper-id", false);

  assert.equal(result.extractionStatus, "In progress");
  assert.equal(result.failureReason, undefined);
});

test("selectActivityViewFailureProps: null activePaperId (mid-upload) yields no failure data", () => {
  const staleFailedPaper = {
    paperId: "test-pdf-id",
    extractionStatus: "Failed" as const,
    failureReason: "corrupted PDF - cannot extract text",
  };

  const result = selectActivityViewFailureProps(staleFailedPaper, null, false);

  assert.equal(result.extractionStatus, "In progress");
  assert.equal(result.failureReason, undefined);
});

test("selectActivityViewFailureProps: matching paperId passes real status and reason through", () => {
  const currentFailedPaper = {
    paperId: "paper-a",
    extractionStatus: "Failed" as const,
    failureReason: "password-protected PDF - cannot extract text",
  };

  const result = selectActivityViewFailureProps(currentFailedPaper, "paper-a", false);

  assert.equal(result.extractionStatus, "Failed");
  assert.equal(result.failureReason, "password-protected PDF - cannot extract text");
});

test("selectActivityViewFailureProps: cacheHitPending forces In progress even for a matching Completed paper", () => {
  const currentCompletedPaper = {
    paperId: "paper-a",
    extractionStatus: "Completed" as const,
    failureReason: null,
  };

  const result = selectActivityViewFailureProps(currentCompletedPaper, "paper-a", true);

  assert.equal(result.extractionStatus, "In progress");
});

// ---------------------------------------------------------------------------
// B3.6b: synthesis idempotency - firing twice with identical inputs writes
// the line once. Simulates React 18 StrictMode's dev-only double-invoke:
// two calls against the SAME stale `logs` (no state commit visible to
// either), with the ref flipping synchronously between them exactly as the
// real effect does.
// ---------------------------------------------------------------------------

test("shouldSynthesizeFailureLine: second call with ref already set (same stale logs) returns false", () => {
  const staleLogs: { stage: string }[] = []; // neither invocation has seen the first write yet

  const first = shouldSynthesizeFailureLine(false, true, staleLogs);
  assert.equal(first, true, "first invocation should synthesize");

  // The real effect sets the ref synchronously right after this check
  // passes, before either invocation's setState is visible - simulate that.
  const second = shouldSynthesizeFailureLine(true, true, staleLogs);
  assert.equal(second, false, "second invocation (ref already set) must not synthesize again");
});

test("shouldSynthesizeFailureLine: does not fire when not failed", () => {
  assert.equal(shouldSynthesizeFailureLine(false, false, []), false);
});

test("shouldSynthesizeFailureLine: does not fire when a real live event already logged the failure", () => {
  const logs = [{ stage: "failed" }];
  assert.equal(shouldSynthesizeFailureLine(false, true, logs), false);
});

// ---------------------------------------------------------------------------
// B3.7: unknown failed stage (failedIndex === -1) renders every row
// neutral - never a red X pinned to a specific (possibly wrong) step.
// ---------------------------------------------------------------------------

test("stepperRowStatus: failedIndex -1 renders every stepper row as pending, never failed or completed", () => {
  const stageCount = 6; // preparing, extracting, auditing, grounding, finalizing, done
  for (let index = 0; index < stageCount; index++) {
    const status = stepperRowStatus(index, /* hasFailed */ true, /* failedIndex */ -1, /* currentIndex */ 0);
    assert.equal(status, "pending", `index ${index} should be pending, got ${status}`);
  }
});

test("stepperRowStatus: known failedIndex still marks exactly that row failed, earlier ones completed", () => {
  // failedIndex=0 ("preparing") - matches the live-event case from the
  // manual smoke test (corrupt PDF fails during preparing).
  assert.equal(stepperRowStatus(0, true, 0, 0), "failed");
  assert.equal(stepperRowStatus(1, true, 0, 0), "pending");
  assert.equal(stepperRowStatus(2, true, 0, 0), "pending");

  // failedIndex=2 ("auditing") - earlier rows are genuinely completed.
  assert.equal(stepperRowStatus(0, true, 2, 0), "completed");
  assert.equal(stepperRowStatus(1, true, 2, 0), "completed");
  assert.equal(stepperRowStatus(2, true, 2, 0), "failed");
  assert.equal(stepperRowStatus(3, true, 2, 0), "pending");
});

test("stepperRowStatus: not failed uses currentIndex for completed/current/pending", () => {
  assert.equal(stepperRowStatus(0, false, -1, 2), "completed");
  assert.equal(stepperRowStatus(1, false, -1, 2), "completed");
  assert.equal(stepperRowStatus(2, false, -1, 2), "current");
  assert.equal(stepperRowStatus(3, false, -1, 2), "pending");
});
