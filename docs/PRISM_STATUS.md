# PRISM STATUS - 2026-10-08 (single source for new chats)

## Repo state
- PR-A (de-leak) merged, SHA 5091b60. Prompt hash 0bcf9d44e619 -> cb3272cce551.
- PR-B merged (#113, e0dd56a); docs-sync branch docs/pr-b-results-readme-sync in progress.
  - Contents: dump_fixture fix (orders claims by position, new --extraction-run-id and --match-map options, 2 new tests).
  - New golden and held-out fixtures + maps stamped cb3272cce551.
  - Old fixtures archived in docs/evals/archive/2026-10-07_pre-cb3272cce551/.
  - Gate 0.35 -> 0.30, test_matrix_loader assertion updated.
- B5.1 branch stays reference only, never merged.
- Cleanup pending: README numbers stale (fixed in docs-sync branch); 2 old tracked logs (logs/eval/matrix_20260827T100808.json, logs/extraction/20260807T074032319542_smoke-test_manual-run-1.json) to untrack and gitignore; 9 old local branches to delete, keep fix/b5.1-auditor-checklist; docs/prism_final_audit_2026-09-07.md has old RFP naming (legacy cleanup list).
- Azure subscription cancelled 2026-09-28, live URL is down. Demo = recorded walkthrough + README; local Aspire stack, Dev Tunnels later.

## Eval
### Current numbers (frozen official run, prompt hash cb3272cc fixtures)
- Goal: raise refusal from 5/16 (31%, gate 0.30, passes by one row) toward 60% as the stretch goal, measured on NEW hand-labelled papers, not by reaching 10/16 on the same golden 16 rows (10/16 is 62.5%). Nothing ships before that unless the stop rule fires; then ship with honest numbers.
- Stop rule: dev refusal under 45% after 4 experiments means ship with honest numbers.
- Ceiling estimates on the golden 16 (not measured): extraction alone about 10/16 (62.5%); realistic with clean fixes about 9/16 (56%). The earlier claim that the auditor is the main lever is withdrawn (see decisions.md).
- Refusal 5/16 (31%), gate 0.30, passes by one row.
- Positives 11/21, floor 10, margin 1; 7 of 11 hits are fragile (REFLEX-M01, REFLEX-M02, REFLEX-M05, COT-M04, COT-M05, REACT-M01, REACT-M10); flipping any 2 breaches the floor. False rejection 1. Coverage 37/37.
- Held-out: refusal 1/2, positive 7/10. Held-out paper used 6 times; only 2 refusal rows.
- STALE or DEAD figures: 6/16 (38%, gate 0.35), 79% and 86%. Do not quote them.

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
- 4 Ship (README with golden + held-out numbers, walkthrough video, blog post) is BLOCKED by the 60% decision.
- Steps 5-8 unchanged, except the reorder in docs/decisions.md ("Plan and stop rule - 2026-10-08", CONFIRMED).
- Step order (earlier version, still on file): (1) docs sync; (2) read-only pipeline audit (AG) listing redundant/duplicated stages, per-stage value and token cost; (3) caps-and-429; (4) variance baseline, 3-5 repeats on main; (5) grow the eval by hand: 2-3 new papers, a fresh sealed held-out paper, more grounding-negative rows; (6) fix one thing at a time (prompt_loader few-shot bug: fixed in draft #115, see In-flight work), harness before/after, keep a change only if the gain is larger than the noise range.

## In-flight work
- PR-1 draft #115 (few-shot loader fix, prompt hash 6bfa9ba9790c). CI fixture-freshness is red on the hash mismatch; expected. Merge only after Milestone A re-dumps the fixtures.
- PR-2 (section-by-section extraction) is parked. Design and build prompt kept on file.

## Next actions (in order)
1. Label 2-3 new dev papers and 1 new sealed held-out (single-sentence rows, blind, before any run).
2. Write marks and a rupee cap.
3. Run the unchanged pipeline once on the new papers to see which stage fails more.
4. Fix that stage (extractor first if forced), one change batch = one experiment.
5. Milestone A, once.

Note: The auditor design review and the extractor design review are done (decisions.md 2026-10-08).

## Evidence locations
- Prism.PythonService/scratch/audits/
- Prism.PythonService/scratch/pipeline_audit/
- Prism.PythonService/scratch/pr1_evidence/
- H:\Work projects\prism-evidence\

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
