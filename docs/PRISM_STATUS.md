# PRISM STATUS - 2026-10-15 (single source for new chats)

## Repo state
- PR-A (de-leak) merged, SHA 5091b60. Prompt hash 0bcf9d44e619 -> cb3272cce551.
- PR-B merged (#113, e0dd56a); docs-sync branch docs/pr-b-results-readme-sync in progress.
  - Contents: dump_fixture fix (orders claims by position, new --extraction-run-id and --match-map options, 2 new tests).
  - New golden and held-out fixtures + maps stamped cb3272cce551.
  - Old fixtures archived in docs/evals/archive/2026-10-07_pre-cb3272cce551/.
  - Gate 0.35 -> 0.30, test_matrix_loader assertion updated.
- B5.1 branch stays reference only, never merged.
- Cleanup pending: README numbers checked 2026-10-15: match current golden and held-out values. 2 old tracked logs (logs/eval/matrix_20260827T100808.json, logs/extraction/20260807T074032319542_smoke-test_manual-run-1.json) to untrack and gitignore; 9 old local branches to delete, keep fix/b5.1-auditor-checklist; (archived audit, see git history) has old RFP naming (legacy cleanup list).
- Azure subscription cancelled 2026-09-28, live URL is down. Demo = recorded walkthrough + README; local Aspire stack, Dev Tunnels later.

## Eval
### Current numbers (frozen official run, prompt hash cb3272cc fixtures)
- Golden refusal is 5/16 (31%, gate 0.30, passes by one row); there is no dev baseline yet. Goal: dev refusal at or above the release floor of 70% (stretch 80%), measured on NEW hand-labelled papers (docs/evals/dev_eval.json), not by reaching 10/16 on the same golden 16 rows (10/16 is 62.5%). False rejections on supported rows: hard cap 10% (mean of 3 runs); aim 0%.
- Release number: the sealed-set result from one final run, reported with refusal-row and supported-row counts. Dev numbers are never quoted as the release number. The sealed set is not re-run or re-labelled after that run.
- Exit rule: hard exit after 8 counted experiments, or when total spend from the decisions.md 2026-10-10 entry reaches the push cap, whichever comes first. The push cap is set after the cost check and logged before experiment 1. At the exit: one sealed final run, then log one of two decisions: keep the floor and stop this version, or set a new floor and release with honest numbers.
- Dev-set size rule: at least 30 independent refusal-family rows (amended from 40 before any Prism output was generated; docs/decisions.md, "Dev set size rule amended - 2026-10-10").
- Ceiling estimates on the golden 16 (not measured): extraction alone about 10/16 (62.5%); realistic with clean fixes about 9/16 (56%). The earlier claim that the auditor is the main lever is withdrawn (see decisions.md).
- Refusal 5/16 (31%), gate 0.30, passes by one row.
- Positives 11/21, floor 10, margin 1; 7 of 11 hits are fragile (REFLEX-M01, REFLEX-M02, REFLEX-M05, COT-M04, COT-M05, REACT-M01, REACT-M10); flipping any 2 breaches the floor. False rejection 1. Coverage 37/37.
- Held-out: refusal 1/2, positive 7/10. Held-out paper used 6 times; only 2 refusal rows.
- STALE or DEAD figures: 6/16 (38%, gate 0.35), 79% and 86%. Do not quote them.

### Dev run 1 status (2026-10-12)
- Dev run 1: refusal 8/31 (26%); 10 audit misses, 13 extraction misses; auditor-only ceiling 18/31 < floor 22/31; false rejections 4/88.
- Exp 1 (auditor thinking=high): Stage A FAIL, rejected.
- Exp 2 (extractor few-shot claim-shape repair): Stage A FAIL on all required marks (A1/A2/A3 FAIL, A4 PASS), rejected; INR 177.93 spent.
- Counted experiments: 2 of 8.
- Finding: the medium auditor is non-deterministic (about +/-3 rows).
- Push extension logged 2026-10-14: exactly one more counted experiment (Experiment 3). Budget: ~INR 560 left (738 - 177.93); sealed reserve INR 300 untouched; sealed set not yet created.
- Exp 3 pre-checks done 2026-10-14 (Checks A-E, see docs/evals/exp3_prechecks/ and docs/decisions.md): decided fixed windows (6000/1500 chars) on today's PyMuPDF text; sentence splitting, GROBID and PyMuPDF4LLM rejected as readers.
- Exp 3 built 2026-10-15 (B1 review, B2, B2-FIX all done; commit 8debe66): pass-2 windowed extraction behind EXTRACTOR_SECOND_PASS, default off. Pre-registered 2026-10-15 (docs/decisions.md, "Experiment 3 pre-registration - 2026-10-15"): marks C1-C8 in docs/evals/exp3_thresholds.json, targets sha256 69c60127cdf1..., pilot cap INR 40, pilot paper arxiv-2610.11135v1.
- Window-count correction: the original --estimate math assumed ~21 windows/paper; the actual longest dev paper (arxiv-2610.11135v1, 152,601 chars) is 34 windows. Phase 4 re-estimates the two treatment runs from real pilot cost, not the original 75.9-136.5 estimate.
- Exp 3 in progress: pilot 1 run 2026-10-15, INR 40.12 spent (arxiv-2610.11135v1, pre-registration marks unaffected, no target rows looked at). Amendment 1 logged (docs/decisions.md, "Experiment 3 amendment 1 - 2026-10-15"): pass2_thinking_level=LOW + frozen pass 1 (--pass1-from-fixture) + crash/NDJSON fixes, planned, not yet implemented. Pilot 2 next, cap INR 30, two pre-registered stop rules (recall >=90/128 sentences, cost <=INR 0.60/window).
- Push budget: ~INR 520 left (560 - 40.12 pilot-1 spend).
- Next: B3 in progress - Phase B code changes (pending Nitin's "go B") -> pilot 2 -> re-estimate -> two treatment runs (Phase 5), then B4 (score, adjudicate, result entry).

### Extractor-only harness (PR-1, 5 runs per arm)
- Golden FULL mean: 20.4 before, 20.6 after PR-1.
- Grounding-negative FULL mean: 9.6 before, 8.8 after.
- Extractor finds about 9 of 16 refusal rows per run; union across 10 runs is 11 of 16.
- Token use (PR-1): 30 extractor calls, 1.27M tokens. The auditor is about 64-75% of pipeline input tokens. Cost is about 1.50 USD for those calls, an estimate based on an unverified third-party price page.

### Run details
- Golden de-leaked runs, all VALID (hash cb3272cce551, 0 fallback calls, 0 SKIPPED, 0 dropped):
  - reflexion 0fd9ead9-ad0c-4370-8192-c1b078602104 (33 claims)
  - react b66b3e0f-60ce-4879-acf3-e20d1c63c42c (33 claims)
  - cot 59bda754-f7e9-4b42-9544-72cc71057878 (24 claims)
- Golden result (fixture, new map): refusal-family 5/16 (0.3125), strict 5/16, wrongly affirmed 4, not extracted 7, positive hits 11/21 (floor 10), false rejection 1/21, coverage 37/37. Gate now 0.30; passes by one row.
- Old baseline (frozen fixtures from runs 929ca23a / 90080172 / edbfc5cf, lost in the 09-18 DB reset): 6/16, strict 4/16, wrongly affirmed 4, not extracted 6, positive hits 12/21, false rejection 0/21, coverage 37/37, gate 0.35.
- The whole refusal drop is one row: COT-M12 went REFUSED -> NOT_EXTRACTED (extraction miss, not a refusal change). Wrongly-affirmed stayed 4 but rows swapped. 15 of the 19 re-adjudicated rows are NOT_EXTRACTED.
- Held-out (arXiv 2609.20812v3), run 4804fc57-7b1b-4642-aa91-f9c274fec15e, VALID, 39 claims (old 30): refusal-family 1/2, positive hits 7/10, false rejection 0/10, coverage 12/12, wrongly affirmed 1, not extracted 0.
- Held-out baseline was 1/2, 8/10, 0/10, 12/12. Only change: HELD-M08 marked NOT_EXTRACTED (paraphrase rule). New held-out map: 9 rows rest on 4 distinct claims.
- Held-out paper has now been used 6 times (PR-B run is the 6th).
- Honest reading: no detectable change from the de-leak; the extractor is the unstable stage. One row decides the gate. Variance not measured.
- Map provenance: CC-suggested, Claude cross-checked, human-adjudicated (19 golden rows by Nitin; HELD-M08 by Nitin).
- Matcher gold pass rate 93.3% was carried over to the new fixture headers, not re-measured (matcher fingerprint unchanged 52401482adf2).
- Variance data points: COT-M08 and REACT-M03 scored differently on identical claim text between runs.

## Findings
- Azurite runs on an anonymous volume: blobs are lost on every Aspire restart. Needs restore before any rerun.
- Blobs are keyed by filename, not hash: two different PDFs with the same name share one blob.
- No UI for rerun. API only: POST /api/papers/{paperId}/rerun needs a signed-in user. We triggered runs by publishing PrismUploaded straight to RabbitMQ (scratch/prb kit, untracked).
- Rerun path has no DB-before-publish bug and never sets InProgress; the completion listener ignores rows already Completed.
- matrix_runner --source db picks the latest run, orders by created_at, and always calls the LLM matcher. Not usable for pinned scoring.
- Aspire picks new host ports each restart; .env PRISM_DB_PORT only affects standalone scripts.
- 2 react.pdf file rows exist (not 4); non-canonical 53e2a6c0 left alone.
- prompt_loader few-shot bug is fixed in PR-1 draft #115 (hash 6bfa9ba9790c). Pre-registered marks M1 and M2 failed, so no coverage gain is claimed. Not merged until Milestone A re-dumps fixtures.
- Known limitation (reflexion stuck-row bug): Uploads got permanently stuck at `file_records.status=InProgress` because `SubmitPaperEndPoint` commits the DB row BEFORE publishing.
- Stage-1 text normalisation merged 2026-10-05 (flag GROUNDING_NORMALIZE, default on).
- Rubric clarified: partially_supported for a wording gap only if it makes the claim STRONGER than the evidence.
- Groq primary auditor fails at 512-token cap (json_validate_failed) + rate limits; fallback carries all audits.

## THE EVAL CHAIN
- Steps 0-3 DONE.
- 5 PR-A DONE, PR-B measurement done, PR-B merged (#113, e0dd56a).
- 4 Ship (README with golden + held-out numbers, walkthrough video, blog post) is BLOCKED by the 70% release floor (decisions.md 2026-10-10).
- Steps 5-8 unchanged, except the reorder in docs/decisions.md ("Plan and stop rule - 2026-10-08", CONFIRMED).
- Step order (earlier version, still on file): (1) docs sync; (2) read-only pipeline audit (AG) listing redundant/duplicated stages, per-stage value and token cost; (3) caps-and-429; (4) variance baseline, 3-5 repeats on main; (5) grow the eval by hand: 2-3 new papers, a fresh sealed held-out paper, more grounding-negative rows; (6) fix one thing at a time (prompt_loader few-shot bug: fixed in draft #115, see In-flight work), harness before/after, keep a change only if the gain is larger than the noise range.

## In-flight work
- PR-1 draft #115 (few-shot loader fix, prompt hash 6bfa9ba9790c). CI fixture-freshness is red on the hash mismatch; expected. Merge only after Milestone A re-dumps the fixtures. Still draft, unmerged as of 2026-10-14 (Exp 2 decision entry).
- PR-2 (section-by-section extraction) is parked. Design and build prompt kept on file.
- Exp 3: built and pre-registered 2026-10-15 (flag default off). See docs/research/fact_inventory_2026-10-14.md, docs/evals/exp3_prechecks/, and docs/decisions.md "Experiment 3 build/pre-registration - 2026-10-15".

## Next actions (in order)
1-4. (Done as of 2026-10-14: dev papers ingested, dev_match_map.json built, baseline run 1, Exp 1 and Exp 2 both run and FAILED.)
5. (Done as of 2026-10-15: Experiment 3 built and pre-registered.)
6. Run Exp 3 estimate (Phase 2, no network calls) -> pilot on arxiv-2610.11135v1 at --max-inr 40 (Phase 3) -> re-estimate and set per-run cap (Phase 4) -> two treatment runs (Phase 5).
7. After Experiment 3: take the exit decision per the 2026-10-10 push-extension/exit rule (docs/decisions.md), whatever the result.

Note: The auditor design review and the extractor design review are done (decisions.md 2026-10-08).

## Evidence locations
Raw evidence: private local folder, not in repo.
Fact inventory (read-only cross-check of this file, decisions.md, README.md, FINDINGS.md): docs/research/fact_inventory_2026-10-14.md.
Experiment 3 pre-checks evidence (Checks A-E): docs/evals/exp3_prechecks/.

## Known open items
- REFLEX-M13 label question (claim/notes mismatch).
- REFLEX-M09 label question (flagged unsure).
- COT-M01 false rejection may already be fixed by Stage-1 normalisation (UNVERIFIED: frozen fixtures predate it; held-out flips do not apply). Do not count it as fixed or as a target until re-measured.
- Stage-2 model route logging was added in PR-1 (draft #115, unmerged); it is not present in the existing golden logs or fixtures.
- COT-M08 pairing is doubtful (automatic carry-over, not hand adjudicated); needs a blind human re-adjudication. If confirmed, wrongly affirmed 4 -> 3 and not extracted 7 -> 8, refusal stays 5/16.
- No rupee cap set for the first paid baseline.

## Rules
- Never tune prompts to move the number. No extractor/auditor changes until the new dev papers are labelled and the unchanged baseline run is done (reorder CONFIRMED in decisions.md 2026-10-08).
- Held-out text never goes in chat or committed notes; counts only.
- PRISM_STATUS.md is tracked in git (since 2026-10-08).
- Never merge past red CI. Never lower a threshold to pass.
- CC never runs git; use `uv run python` from Prism.PythonService.
- AG has made wrong claims (invented a Claude model swap): verify its INFERRED rows. AG audits are read-only; auto-execution off.
- Planning/review in claude.ai; in-repo coding in CC; long reads in AG.
- Casual, easy English, short. No analogies. Simple list style.

## Infra facts
- document_extractors.Fields is jsonb in Postgres but plain string in C#.
- SignalR broadcast is scoped to chat-{chatId} groups; DocumentProcessed event is lost on reconnects; /files endpoint is the fallback.
- LangGraph checkpointer race on startup throws DuplicateObject/UniqueViolation (cosmetic).
- Domain seeded via EF Core HasData with fixed Guid 11111111-1111-1111-1111-111111111111.
