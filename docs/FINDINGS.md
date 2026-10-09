# Findings

## 1. Headline numbers
- Official refusal rate: 5/16 (frozen run hash `cb3272cce551`).
- 95% range: ~14-56%.
- Expected refusal ≈ 5.8/16 (est); frozen 5/16 was a slightly unlucky draw.
- Positives: 11/21, floor 10.
- Gate threshold: 0.30 (passes by one row).
- Dead figures: 6/16, gate 0.35, 79%, 86%.

## 2. Eval design and limits
- Extractor-only harness (15 runs): most refusal rows found 4-5/5 times. Never found: REFLEX-M11, COT-M07, COT-M11, REACT-M12.
- Extractor finds about 9 of 16 refusal rows per run; union across 10 runs is 11 of 16.
- The 6/16 vs 5/16 gap between two frozen runs came from extraction swaps: COT-M09, M10, M12 dropped out; REFLEX-M09, REACT-M14 came in. Net change was one row.
- COT-M08 is a pairing problem, not an auditor miss.
- Labels re-checked by hand (not blind); all 6 unchanged.

## 3. What worked
- Few-shot loader bug fixed (model had seen only 1 of 15 example claims) — PR-1 draft #115.
- Extractor-only harness and per-call token logging (PR-1).
- De-leak of prompts + CI prompt-leak check (PR-A); PR-B measurement merged.
- Stage-1 text normalisation before fuzzy matching, on by default.

## 4. What failed
- **PR-1 (extractor fix):** real bug fixed, but measured gain was negative: golden FULL mean 20.4 → 20.6, grounding-negative FULL 9.6 → 8.8; predicted 38-44% refusal was wrong. Kept as a bug fix, merge pending.
- **Sample-and-union (2 extractor calls):** estimated ~+0.2; dropped before building.
- **Scoped auditor pilot (Exp 1):** 1 run, 44 claims, ~Rs 204. P1 passed (2/6 targets), P2 passed (positives held 6/6), P4 passed (0 errors). Failed P3: 4 of 11 baseline refusals flipped to supported. Code lowered once, wrongly (a positive). Negative result; AUDIT_MODE stays legacy. Code archived on tag `archive/exp1-scoped-auditor`.
- **B5.1 checklist:** Archived, never merged. Refusals + positives shifted (6+12 -> 9+9 and 7+11) but net was unchanged (18). Same code gave different verdicts across runs.

## 5. Root finding
- The auditor gets the full paper (no retrieval at audit stage). In 5 of 6 wrongly affirmed rows it verified a narrowed version of the claim.
- It refuses correctly when the breaking dimension is named in the claim ("all three tasks"); it affirms when the dimension is only implied (which models, baselines, tasks).
- Retrieval is not the cause; neither prompt checklists (B5.1) nor scope-first design (Exp 1) fixed it.

## 6. Cost
- ~Rs 500 on 7 Oct live runs.
- ~Rs 204 on Exp 1 pilot.
- All audits are free.

## 7. Ops summary
- **Observability:** 7 telemetry and logging gaps found (e.g., silent claim drops, missing token logs). Plan recorded in `docs/observability-and-cost-plan.md`.
- **Deployment:** Live environment decommissioned 2026-09-28. Demos use a recorded walkthrough or local Aspire stack with Dev Tunnels. See `docs/decisions.md` and `docs/PRISM_STATUS.md`.

## 8. Lessons
- **Missing-abstraction bug pattern:** when the same class of bug (e.g. "forgot to attach auth header") shows up in more than one independent call site, the fix is a shared abstraction (apiClient.ts), not patching each site — patching sites individually guarantees a future site will drift the same way.
- **Verify before acting:** AG2.0 audit findings should be verified against real evidence (an actual decoded token, an actual log line) before being acted on — this session had two audit claims that were plausible but unverified, and both turned out to need correction once checked against real data.
- **Restart != Restart:** A restart doesn't always mean a restart: config changes to appsettings.json (or similar startup-read config) require a full process kill, not just a re-run, if a debugger or lingering process still holds the old binary.
- **Check dependencies before removal:** Before removing a UI element, confirm what ELSE currently depends on it (props, gating logic, other call paths) — this session found duplicate Re-run buttons genuinely called the same backend path, but only after checking, not assuming.
- **Agent commit discipline:** An agent committing directly to main instead of a feature branch is a real failure mode, not hypothetical — happened this session, caught only because the commit was unpushed; always check `git log` / `git branch` after any agent session claims to be "done," not just after it claims to have committed.
- **Migration review rigor:** A migration backfill script needs the same evidence-based review as application code — a plausible-sounding `CASE WHEN` can still encode the exact bug it's meant to fix.

## 9. What's next
- **Stop rule:** Decision 9 Oct: stop core changes; clean up; ship with honest numbers.
- **New papers:** Label 2-3 new dev papers and 1 new sealed held-out (single-sentence rows, blind, before any run).
- **Optional model test:** Run the same legacy auditor on a newer Flash model, once, against a fresh baseline, with marks written first.
