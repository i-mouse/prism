# PRISM STATUS — 2026-11-18 (single source for new chats)

## Current state

Prism runs locally only (Aspire). The Azure demo was decommissioned 2026-09-28; cancellation not yet confirmed complete. Main holds PR #122 (dev eval baseline + extraction experiments, merged 2026-10-21, commit 4be1cc4) and the work of `eval/vertex-auditor-option` (which contains `auditor/caching-scope-check` and `docs/auditor-diagnostic-2026-10-22`): caching and scope-check code (flags off, replay only), the Vertex AI eval backend, the auditor model option for evals, golden replay, `--repeat-index`, `score_screen` and `score_full_check`, the structurer JSON control-character fix (`engine.py`, `strict=False`), all test records, the fact sheet, the engineering report and the hero diagram. The steps 1-4 work is on branch `eval/step1-free-checks` and is not merged to main yet.

Product behaviour is unchanged: auditor gemini-3.6-flash, all experiment flags off, flag-off prompt hash `cb3272cce551`.

Not released: the dev refusal rate (8/31, 26%, single run) is well below the release bar, and there is no release with the current auditor (decisions.md 2026-10-29; Ship-honest removed).

Auditor phase: Stage A1 FAILED (2026-10-28); A1 diagnosis found no single clear cause (2026-10-28); auditor no-regression rule set (2026-10-28); Auditor v2 T1 FAILED (2026-10-29); T2-R FAILED (2026-10-31); 10-miss analysis (2026-11-02): 8 auditor targets, P5-R1 and P5-R2 parked, P1-R3 is run-to-run noise; Vertex smoke attempt 1 FAIL on mechanics (2026-11-04), attempt 2 PASS (2026-11-06); gemini-3.8-flash screen VOID (attempt 1 2026-11-06, attempt 2 2026-11-07); full 3-run no-regression check (2026-11-08/09): both 3.8 candidates FAIL, no auditor change. 6-step path (2026-11-11): step 1 free checks completed (noise T = 3, cost estimate INR 196 at 2027 list prices, extractor ceiling 5 of 13); step 2 auditor caught 2 of 7 pass-2-recovered claims, directing auditor change first; step 3 public datasets checked; table-finding check PASS (5 of 5 rows); step 4 table checker FAIL on M2, M3, M5, M7 (2026-11-18). Core auditor work stopped after step 4 (decisions.md 2026-11-18).

Report: `docs/PRISM_REPORT.md` (fact sheet `docs/report/PRISM_FACTS.md`, field comparison `docs/report/PRISM_FIELD_COMPARISON.md`, hero diagram `docs/diagrams/prism_hero.drawio.svg`).

Next items in order (decision gate outcome, 2026-11-18):
1. Core auditor work stops; the engineering report stands as the hiring artifact.
2. Remaining Prism polish (not core): two small chat fixes, then a demo video and a blog post.
3. Separate projects next: the fine-tuning learning project (Warrantum), hands-on MCP practice, and resume and LinkedIn rewrite (all separate from the Prism repo).

## Scoreboard

**Golden (3 papers, 16 refusal rows / 37 total, de-leaked prompts, 2026-10-07):**
Refusal-family 5/16 (31%), gate 0.30 (passes by one row); strict 5/16; wrongly affirmed 4; not extracted 7; positive hits 11/21 (floor 10); false rejection 1/21; coverage 37/37. (decisions.md:1474-1479)

**Held-out (arXiv 2609.20812v3, 2 refusal rows — small sample, used 6 times, near-burnt, 2026-10-07):**
Refusal-family 1/2, positive hits 7/10, false rejection 0/10, coverage 12/12. (decisions.md:1479)

**Dev baseline (119 rows / 12 papers, 31 refusal-family rows, single run, 2026-10-12):**
Refusal 8/31 (26%). Of the 23 misses: 10 audit misses (claim extracted, wrongly judged supported), 13 extraction misses. Auditor-only ceiling 18/31 (below 22/31 floor); extraction-only ceiling 21/31 (68%, also below floor) — neither stage alone reaches the release floor. (decisions.md:1750, 1828, 2115, 2212-2213)
False rejections: 4/88 S rows (the weak P5 match was resolved as not a match, decisions.md 'Corrections - 2026-10-22'; re-derived with the filled match map in 'Stage A1 marks and cap re-confirmed - 2026-10-28': P1-S5 via grounding, P8-S7, P9-S4, P10-S2; 67 matched, 21 NO_MATCH).

**Replay check, not a product score (baseline B in the full no-regression check, 2026-11-09; Vertex, gemini-3.1-flash-lite grounding, 3 runs, 2-of-3 vote):**
Golden refusal-family 6/16, golden positive hits 13/21, dev false rejections 1/88 (P4-S4), dev targets fixed 0/8, dev real hits lost 1/7 (P6-R1).

## Release bar (restated 2026-11-18, unchanged)

Nitin (2026-11-18): the release bar stays dev >= 22/31 with false rejections <= 8/88 (auditor-only ceiling 18/31). Release number: one sealed-set run only, never dev or golden numbers. Cost: the INR 200 per paper gate at 2027 list prices, set for step 4 changes (decisions.md 2026-11-12); revisited before any release. No release with the current auditor (decisions.md 2026-10-29). Core auditor work stopped after step 4 (decisions.md 2026-11-18).

## Flags and their defaults

Flags (all default off/unset, each pinned by a test; flag-off prompt hash confirmed `cb3272cce551`):

| Flag | Default | Source |
|---|---|---|
| `auditor_thinking_level` | `None` | `config.py:82` |
| `extractor_fewshot_fix` | `False` | `config.py:100` |
| `extractor_fewshot_shapes` | `False` | `config.py:112` |
| `extractor_second_pass` | `False` | `config.py:121` |
| `pass2_thinking_level` | `None` | `config.py:130` |
| `extractor_pass2_clean` | `False` | `config.py:152` |
| `table_check` | `False` | `eval/replay_audit.py` (branch `eval/step1-free-checks`) |

Existing flags (pre-date this branch):

| Flag | Default | Note |
|---|---|---|
| `GROUNDING_NORMALIZE` | on | Stage-1 text normalisation, merged 2026-10-05 (docs/FINDINGS.md:72) |
| `AUDIT_MODE` | legacy | The scoped auditor was a separate pilot (Exp 1 scoped-auditor, not decisions.md's "Experiment 1"), archived on tag `archive/exp1-scoped-auditor`, never merged (docs/FINDINGS.md:27) |

Eval-only options (replay and eval tools, never product defaults): `--cache`, `--scope-check`, `--table-check`, `--backend vertex`, `--vertex-project`, `--set golden`, `--repeat-index`, and the auditor model choice used for eval runs.

## Experiments and verdicts

| Experiment | Change | Verdict | Spend |
|---|---|---|---|
| 1 | Auditor `thinking_level=high` | REJECTED — fixed 1/10 rows (needed >=3); auditor noise ~±3 rows run-to-run at default | INR 411.95 (decisions.md:1807-1831) |
| 2 | Extractor few-shot claim-shape repair | REJECTED — all 4 required marks failed; evidence leans toward a task-design problem, not proven | INR 177.93 (decisions.md, "Experiment 2 - Stage A result - 2026-10-14") |
| 3 | Windowed pass-2 re-extraction (`extractor_second_pass`) | REJECTED on cost gate c4: projected INR 237.59/paper (pooled) / 243.75 (mean) vs INR 130 cap. c7, c2 passed. c1/c6/c8 not measured (human labelling deviation) | INR 185.79 (Exp-3-specific, meter) (decisions.md:2600-2606) |
| Clean-extraction attempt | Claim-cleaning filter on top of Exp 3 (`extractor_pass2_clean`) | REJECTED — K1 (recall) FAIL 5-6/13; K4 (cost) FAIL ~INR 230/paper vs 130 cap; K7 (dedup safety) FAIL; K8 FAIL on the filter sub-cap (INR 64.25 / 58.31 vs 40). K2, K5, K6 PASS | INR 311.04 of a separate INR 350 cap (decisions.md:3005-3018, 2621) |
| Stage A0 | Explicit context caching on 18 frozen claims | PASS — audit cost 66% below baseline (INR 1.30 vs 3.79), refusal hits 8/31 kept | INR 36.86 (decisions.md, "Stage A0 results - 2026-10-26") |
| Stage A1 | Scope lister + scope checker (3 repeats, 18 claims) | FAIL — A1-fixed 5/10 counted (3 from the scope check); always-missed 1/6, need 4 | INR 136.16 (decisions.md, "Stage A1 results: FAIL - 2026-10-28") |
| Auditor v2 T1 | Table extraction (pymupdf4llm (inside pymupdf 2.0) and Docling 2.144.0) | FAIL — 5/8 usable tables each; row-group spans lost | INR 0 (decisions.md 2026-10-29) |
| Auditor v2 T2-R | Code checks on LaTeX reference tables | FAIL — 4/10 misses fixed, 2/5 hard (needed 3); 0 S rows lowered by code, 2 of 10 set Needs review | INR 0 (decisions.md 2026-10-31) |
| 3.8 screen (Vertex) | Replay: 3.6 medium vs 3.8 medium vs 3.8 high | VOID — attempt 1: arm 2 structurer JSON crash; attempt 2: fallback-served audits in arm 1 (V3 -> V4) | INR 842.86 billed, both attempts (decisions.md 2026-11-06, 2026-11-07, 2026-11-09) |
| Full no-regression check (Vertex) | 106 claims x 3 runs: B 3.6 medium vs C1 3.8 medium vs C2 3.8 high | FAIL both — C1 false rejections 4/88 vs fresh baseline 1/88; C2 false rejections 7/88, golden positives 10/21, cost INR 194.4/paper > 130 | INR 4,111.48 billed (INR 3,542.75 counted audit calls) (decisions.md 2026-11-09) |
| Step 1 (6-step path) | Free checks on saved data: 1a votes, 1b noise T = 3, 1c miss locations, 1d cost estimate | Completed — T = 3; cost estimate ~INR 102 today, INR 196 at 2027 prices; ceiling 5 of 13 | INR 0 (decisions.md 2026-11-12) |
| Step 2 (6-step path) | 7 pass-2-recovered claims to today's auditor (Vertex, 3 runs) | Auditor change first — caught 2/7 (<= 4/7 split rule); P9-R1, P11-R3 caught | About INR 74 total by tool count (cap 117.6) (decisions.md 2026-11-13) |
| Table-finding check | Plain code table finder on 6 tables, 5 target rows | PASS — 5 of 5 rows ready; 100% reference values in blocks | INR 0 (decisions.md 2026-11-15) |
| Step 4 (6-step path) | Table checker over routed table claims (Vertex, 3 runs) | FAIL (M2, M3, M5, M7) — M1 1/8 PASS (P4-R2); M2 lost P12-R2; M3 8/88 FAIL; M4 5/16, 11/21 PASS; M5 FAIL; M7 INR 214.92 > 200 FAIL; not void | About INR 1,074 (cap counter; grounding excluded); billed figure pending (decisions.md 2026-11-18) |

Exploratory-only note: Experiment 3's c1/c6 recall result (8/13 both runs) was AI-proposed, human-verified — not the pre-registered blind adjudication — so no recall claim is made for Experiment 3 itself. (decisions.md:2607-2616)

The 8 -> 12 of 31 figure from T2-R is a ceiling measured with hand-written forms on LaTeX reference tables, not a pipeline result, and is never quoted as a Prism score.

## Extraction findings (2026-10-20)

- All 8 lost target rows were lost at the pass-2 output stage in both clean runs — zero merge or filter drops (pre-filter = final). The filter did not cause the K1 shortfall.
- Old vs new pass-2 prompt, same fuzzy matching method: old 6/13 and 6/13, new 5/13 and 6/13 — no clear recall loss from the new prompt.
- Pass 2 recovers about 5-6 of the 13 target rows, but those recovered claims were never audited end to end — their value is unmeasured.
- Both clean runs used pass-2 thinking LOW, consistent with Experiment 3.
- The K7 filter fix (drop as "same" only if the candidate adds no new number/content word; never resolve "same" against a dropped neighbour; validate neighbour ids; add an id to each filter answer) is parked, design kept, to revisit with a pass-2 redesign.
- Step 1c (2026-11-12) section analysis of the 13 misses: introduction 2, conclusion 3, body 5, appendix 3. Ceiling for abstract/introduction/conclusion extractor option: 5 of 13.

(decisions.md, "K1 diagnostics and filter status (exploratory) - 2026-10-20", lines 3026-3045; "Step 1 results (INR 0) and cost gate raised to INR 200 - 2026-11-12".)

## Auditor diagnostic (2026-10-22)

- Root cause of A1: the auditor does not test the claim's full scope (quantifiers,
  counts, coverage of models/tasks/settings) against what the paper reports. It
  accepts the first supporting evidence and the paper's own summary framing (e.g.
  bold averages over per-cell losses).
- Not the main cause: PDF reading, retrieval or missing evidence.
- Cannot fix the 6 unanimous misses: higher thinking alone, majority voting,
  sentence selection.
- The 2026-10-19 candidate (numbered sentences + majority vote) is dropped as the
  A1 fix. Voting stays a candidate for stability only.
- A prompt-only checklist already failed (B5.1); the scope check is expected to
  need a structural change.

Evidence: docs/evals/auditor_rd/diagnostic_2026-10-22.md.

## 10-miss analysis (2026-11-02)

- A, table number breaks the claim: P1-R1, P4-R1.
- B, claim wider than the cited table: P4-R2, P11-R2, P3-R2.
- C, claim meaning: P5-R2 (parked, semantic duplicate, moved to the extraction phase), P6-R2.
- D, prose caveat elsewhere in the paper: P7-R1, P8-R2.
- E, figure-only evidence: P5-R1 (parked).
- 8 auditor targets remain. P1-R3 is documented run-to-run noise, reported only and excluded from screen and full-check totals.

## Step 4 design findings (2026-11-18)

- Diagnosis of Step 4 FAIL: fair test, genuine design fail; no code bug found (guard re-run on saved inputs 373 of 373 identical).
- Design error 1 (name check): 269 name-check failures across the 6 runs, 257 on pieces the checker answered backed; scope pieces rarely share words with table labels, causing ~80% of routed claims to fall back to today's auditor.
- Design error 2 (routing): P4-R1 and P11-R2 never mention "Table N" in claim or spans; routing routed claims where cited table was not found (P1 Table 1), lowering P1-S1, P1-S2, P1-S4 via no_row (3 of the 5 checker false rejections).
- Model errors: P2-S3 and P6-S4 lowered by no_row on facts stated in prose; today's auditor noise caused M2 (P12-R2) and M5 (REFLEX-M08, REACT-M14).
- P8-S7: label supported in 3 of 3 D runs; counted as false rejection because grounding returned Fail (missing = true) in all 3.
- Picture trigger: 1 layout misread in 1 run (P1-R1); trigger n.

## Known risks (code-sourced, `docs/archive/premerge_review_2026-10-20.md` section 3)

All three risks below are inside code currently gated off by default (`extractor_pass2_clean` / `extractor_second_pass`), so they carry no live-pipeline risk today — but should be fixed before either flag is turned on for real traffic.

- **"Same"-relation chain-drop** — `pass2_clean.py:269-270`: a candidate drops if *any* relation to a neighbour is `"same"`. The docstring (`pass2_clean.py:14-26`) explicitly acknowledges this is positional/order-dependent and relies on `merge.py` having already deduplicated pass-2 candidates — an accepted assumption, not a bug fix.
- **Unvalidated neighbour ids** — `pass2_clean.py:62-66,199,268-269`: the LLM's returned `neighbour_id` drives the drop decision with no membership check against the ids actually offered in that batch. A hallucinated/mismatched id would silently drive a drop.
- **Positional answer mapping** — `prompt_loader.py:291-296`: the pass2-clean response schema carries no id field of its own, so position is the only correspondence, enacted via plain `zip(batch, results)` at `pass2_clean.py:267`. Length mismatches are guarded (`pass2_clean.py:249-264`, falls back to "keep all"), but a same-length reordered response would not be detected.
- **Thinking level not stored in fixture headers** — confirmed against a real fixture (`docs/evals/fixtures/dev/clean/clean_r1/arxiv-2610.10590v1_clean.json:2-13`): header has no `thinking`/`thinking_level` key, even though `replay_clean.py` threads `thinking_level`/`pass2_thinking_level` through every call. (decisions.md:3037)

## Budget status

- GCP Free Credit (Vertex AI eval runs only; cannot pay AI Studio): INR 23,738.43 on 2026-11-09 at 15:37 IST; expires 2026-11-26. Eval spend on it since 2026-11-02: INR 4,955.45 through the full check (smoke tests INR 1.11, 3.8 screen INR 842.86, full check INR 4,111.48). Subsequent eval runs: Step 2 spent about INR 74 total by tool count; Step 4 spent about INR 1,074 (cap counter; grounding excluded); billed figure pending next GCP credit check.
- Product and dev run on AI Studio: Google Developer Program credit (about INR 955-960 around the 13th of each month; INR 160.94 left on 2026-11-02), then prepay (INR 341.81 on 2026-11-02).
- Spend is counted at list price; each test sets its own cap; paid runs stop at 1.3x the estimate; a capped run is void.
- Gemini Flash prices double on 2027-01-01 (estimated about INR 102 today, INR 196 at 2027 list prices). Cost gate: INR 200 per paper at 2027 list prices, set for step 4 changes (decisions.md 2026-11-12); revisited before any release.
- Sealed reserve: INR 300, untouched throughout.
- Earlier spend: Exp 1 INR 411.95; Exp 2 INR 177.93; Exp 3 INR 185.79; clean-extraction attempt INR 311.04; Stage A0 INR 36.86; Stage A1 INR 136.16. T1, Step P, T2-R, Step 1, and Step 4 table-finding check cost INR 0.

## Open items

- REFLEX-M13: claim/notes mismatch (decisions.md:1561).
- REFLEX-M09: flagged unsure (decisions.md:1561).
- COT-M08: pairing doubtful, automatic carry-over not hand-adjudicated (decisions.md:1607).
- COT-M01: false rejection may already be fixed by Stage-1 normalisation — UNVERIFIED, frozen fixtures predate it (decisions.md:1543).
- PR-1 draft #115 (few-shot loader fix): to be closed with this merge and kept as tag `archive/pr1-fewshot-loader`; its logic already ships behind `extractor_fewshot_fix`, default off.
- Held-out eval files (`heldout_eval.json`, `heldout_match_map.json` and an archive copy) and `exp3_targets.json` are public on main from earlier merges; left as is (decisions.md 2026-11-10).
- Deferred: licence check of committed arXiv PDFs; cleanup of `scratch/` folders.
- Full-pipeline token usage is not logged in production.
- Grounding and eval matcher send temperature=0 (Google advises 1.0 for Gemini 3) - parked.
- dev_eval.json scoring-note wording: P5-R2 row letters, P6-R2 Figure 3 count - labels unchanged.

## Working rules

- Never tune prompts to move the number.
- Held-out text never goes in chat or committed notes; counts only.
- The sealed set is never committed to this repository.
- Never merge past red CI; never lower a threshold to pass.
- CC never runs git; use `uv run python` from `Prism.PythonService`.
- Every experiment needs pre-registered marks and a rupee cap, written before any paid call.
- Never run `git push --tags`; push tags one at a time.

(decisions.md, repeated across entries, e.g. 1636-1665.)

## Engineering state and test counts

- 1,006 tests passed at commit bc2f575.
- 1,200 passed in Step 1 (decisions.md 2026-11-12).
- 1,428 passed at the step 4 build (branch eval/step1-free-checks) (decisions.md 2026-11-17).

## Links

Engineering report: `docs/PRISM_REPORT.md`. Fact sheet: `docs/report/PRISM_FACTS.md`. Field comparison: `docs/report/PRISM_FIELD_COMPARISON.md`. Hero diagram: `docs/diagrams/prism_hero.drawio.svg`. Decisions log: `docs/decisions.md`. Code review: `docs/archive/premerge_review_2026-10-20.md`. Dev adjudication: `docs/evals/dev_adjudication_run1.md`. Clean-extraction scoring: `docs/evals/clean_labels/clean_attempt_score.md`.