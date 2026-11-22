# Evaluation Artifacts and Sets

This document indexes all top-level folders and JSON files in `docs/evals/`, describing their purpose and tracing each to its corresponding decisions log entry.

| Folder or File | What it is | decisions.md heading (date) |
|---|---|---|
| `fixtures/` | Frozen fixture evaluation runs for golden and held-out papers (`reflexion.json`, `cot.json`, `react.json`, `heldout.json`) | Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map (2026-09-30) |
| `fixtures/dev/` | Frozen fixture dumps of dev-set paper extraction and replay runs | Dev run 1 - fixture dump and pre-registered adjudication rules (2026-10-12) |
| `auditor_rd/` | Auditor research, diagnostics, caching benchmarks, and scope check exploration | Auditor phase diagnostic (INR 0) (2026-10-22) |
| `golden_replay/` | Golden set replay runs and frozen input text caches for no-regression checks | not found |
| `exp3_b4/` | Experiment 3 Phase B4 evaluation pack, scoring scripts, and analysis for windowed pass-2 re-extraction | Experiment 3 B4 result (2026-10-16) |
| `clean_k1/` | Data and diagnostic artifacts for K1 recall recovery attempt under clean-extraction filter | not found |
| `clean_labels/` | Hand-labelled sample sets and adjudication files (K6 claim/non-claim and K7 duplicate checks) for clean-extraction attempt | Clean-extraction attempt result: FAIL, pass 2 stays off (2026-10-20) |
| `exp3_prechecks/` | Local pre-checks (Checks A–E) evaluating text splitters, sentence counts, union recall, and PDF readers | Experiment 3 pre-checks result (2026-10-14) |
| `claim_inventory/` | Extracted claim inventory data across papers | not found |
| `step1_2026-11-11/` | Output data and analysis scripts for Step 1 of the 6-step path (1a audit counts, 1b noise T=3, 1c miss locations, 1d cost model) | Step 1 results (INR 0) and cost gate raised to INR 200 (2026-11-12) |
| `step4_tablefind_2026-11-14/` | Benchmark data, test tables, and code artifacts for Step 4 table finder validation | Table-finding check result: PASS (5 of 5 rows) (2026-11-15) |
| `testb_2026-11-19/` | Manifest, results, and scoring summaries for Test B (single whole-paper call with gemini-4-carbon across 12 dev papers) | Test B result: PRISM BETTER (one Carbon call: 9/31 caught, 17/88 false rejections); Prism core closes (2026-11-20) |
| `archive/` | Archived eval materials, superseded rubrics, early baseline fixtures, and old test artifacts | not found |
| `dev_adjudication_run1.md` | Human adjudication notes for Dev Run 1's match map | Backfill: records missing from this log (2026-10-15) |
| `dev_eval.json` | Development benchmark evaluation set of 119 hand-labeled claims across 12 papers (31 refusal-family, 88 supported) | Dev set frozen (2026-10-11) |
| `dev_match_map.json` | Human-adjudicated mapping pairings between dev benchmark golden rows and claims extracted in Dev Run 1 | Experiment 1 pre-registration (auditor thinking_level=high) (2026-10-12) |
| `exp1_full_check_claims.json` | Frozen set of 84 dev-set claims used in the full 3-run no-regression check and Test A replay | Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex (2026-11-08) |
| `exp1_golden_claims.json` | Frozen set of 22 golden-paper claims used in the full 3-run no-regression check and Test A replay | Pre-registration: full 3-run no-regression check, gemini-3.8-flash medium and high vs gemini-3.6-flash, Vertex (2026-11-08) |
| `exp1_stage_a_claims.json` | Frozen claims used for Stage A0/A1 screening of the scoped auditor and context caching | Experiment 1 pre-registration (auditor thinking_level=high) (2026-10-12) |
| `exp3_pass2_7_claims.json` | Seven pass-2 recovered refusal claims evaluated in Step 2 of the 6-step path | Pre-registration: step 2 - today's auditor on the 7 pass-2-recovered claims, Vertex, 3 runs (2026-11-12) |
| `exp3_targets.json` | Frozen 13 target extraction-miss rows for Experiment 3 | Experiment 3 pre-registration (2026-10-15) |
| `exp3_thresholds.json` | Pre-registered threshold definitions and gates (c1-c8) for Experiment 3 | Experiment 3 pre-registration (2026-10-15) |
| `golden_eval.json` | 21 end-to-end chat evaluation questions | 2026-10-03 - Eval chain step 0: matrix_eval positive rows re-checked (2026-10-03) |
| `heldout_eval.json` | Eval set for the held-out paper arXiv 2609.20812v3 (12 rows); public on main since earlier merges (decisions.md 2026-11-10); not the sealed set, which is never committed | Held-out eval paper sealed (eval chain step 1) (2026-10-03) |
| `heldout_match_map.json` | Adjudicated match map for the held-out paper benchmark rows | Report, hero diagram, docs refresh and merge to main (2026-11-10) |
| `match_map.json` | Human-adjudicated mapping pairings between the 37 golden rows in matrix_eval.json and extracted claims from the 3 golden papers | De-leak: eval-paper text and answer-key wording removed from prompts (2026-10-05) |
| `matcher_gold.json` | 15-pair hand-labeled golden calibration set used to verify eval matcher accuracy offline | Auditor model swap + eval matcher calibration (2026-09-04) |
| `matrix_eval.json` | The 37 golden benchmark rows across 3 papers (Reflexion, CoT, ReAct) defining the golden refusal and positive test set | Eval scorer: removed omission-credit bug, added four-bucket scoring and a human-adjudicated match map (2026-09-30) |
