# Fact Inventory — Prism Core Agent Decisions (2026-10-14)

Internal evidence base for a future reader-facing "Design Decisions" doc and Experiment 3's lessons check. Zero-guessing rule: every fact below cites file + entry title/date or file:line. "NOT RECORDED" rows list exactly which files and terms were checked. Disagreements between sources are listed in §7 (Divergences), unresolved.

**Method:** read-only. No git commands were run (branch/tag/PR facts are cited "per `<doc>`" and marked "not verified (no git)" where the source itself used git). `docs/LABEL_RUBRIC.md` and `docs/research_papers` were never opened/listed. No existing file was edited.

**Sources read in full:** `docs/decisions.md` (2077 lines), `docs/PRISM_STATUS.md`, `README.md`, `docs/discovery/D1_report.md` (188 lines), `scratch/exp3/report.md` (423 lines, git-ignored/untracked), `docs/evals/dev_adjudication_run1.md`, `docs/FINDINGS.md`, `docs/evals/fixtures/dev/exp2/review_pack.md`, `Prism.PythonService/config.py`. Read for cost/token fields only: `docs/evals/fixtures/dev/exp2/{control_r1,treatment_r1,treatment_r2}/_summary.json`. Read via file:line citation (code): `extraction/engine.py`, `extraction/prompt_loader.py`, `extraction/grounding.py`, `extraction/prompt_version.py`. Listed, not read: `Prism.PythonService/prompts/`, `Prism.PythonService/eval/`.

---

## 1. PDF reading / text extraction

### 1a. Used today (code)
Papers are read with PyMuPDF (`fitz`), `page.get_text()` over all pages, no chunking or layout-aware parsing — flattened text, tables lose row/column structure, figures are absent except captions. Source: `docs/discovery/D1_report.md:92` (`[VERIFIED prompt_loader.py:98-118; main.py:108-115]`); corroborated `docs/decisions.md:262` (table text "Supervised SoTAb 67.5 89.5" cited correctly from flattened text, disproving a layout-parser hypothesis).

### 1b. Alternatives tried / piloted / parked / rejected

| What | Date | Result (rows) | Spend INR | Why rejected/parked | Code/flag/tag state | Source |
|---|---|---|---|---|---|---|
| Layout-aware PDF parser (Document Intelligence) swap, considered for grounding | 2026-09-04 | Disproved by citation evidence (auditor correctly read a flattened table) | N/A | Hypothesis ruled out; nothing to fix | Not built | `docs/decisions.md:262,270` |
| PyMuPDF `TEXT_DEHYPHENATE` flag | 2026-10-05 (discussion) | Not measured as a change | N/A | Would re-extract + reindex everything at once; golden showed zero hyphen issues; doesn't fix ligatures/table breaks | Not used | `docs/decisions.md:1335` |
| Sentence-ID citing (split paper into numbered sentences, auditor cites `[S142]`) | 2026-10-05 (discussion) | Not built | N/A | Auditor redesign, re-baselines all numbers; gated by step 8 | Parked, "for discussion" | `docs/decisions.md:1334` |
| **Experiment 3 Check A — sentence-splitter survival** (`pysbd_pdf_clean`, `pysbd_text_noclean`, `regex`) | 2026-10-14 | 119 dev rows: WHOLE% 51.3% / 5.0% / 75.6% vs a pre-set **≥95% WHOLE bar** | N/A (local, no LLM calls) | **All three FAIL the bar** | Evidence in `scratch/exp3/report.md`, **git-ignored** (`.gitignore:61`), not in repo history | `scratch/exp3/report.md:34-51` |
| **Experiment 3 Check D — reader bake-off** (GROBID 0.9.0, PyMuPDF4LLM, fixed 6000/1500-char windows) | 2026-10-14 | 119 rows WHOLE%: GROBID 53.8%, PyMuPDF4LLM+regex 50.4%, PyMuPDF4LLM+pysbd 58.8%, fixed windows 94.1%, vs the same **≥95% bar** | N/A (only network call: local GROBID instance) | **All four FAIL**; fixed windows closest, "FAIL (by 1 row)" | Same git-ignored `scratch/exp3/` evidence | `scratch/exp3/report.md:116-255` |

### 1c. Current scores
No standalone "PDF reading" score is tracked separately from extraction (golden/held-out/dev numbers are reported at the extraction/pipeline level — see §2c). Experiment 3 Check D's bar (≥95% of 119 dev rows findable WHOLE in the reader's output) is the only PDF-reading-specific score, and nothing passes it (see 1b).

### 1d. Cost and tokens
Check A/D used no LLM/API calls (local only; GROBID runs on a local instance). No separate PDF-reading token/cost figure exists — PDF text feeds directly into extraction's token count (§2d). Source: `scratch/exp3/report.md:3` ("Local only. No LLM/API calls").

---

## 2. Extraction (claim extraction)

### 2a. Used today (code)
Call #2 of the pipeline: one extractor call per paper emits all claims (no chunking), using `LLM_EXTRACTION_MODEL` → `settings.llm_extraction_model` (default `gemini-3.6-flash`) with fallback `LLM_EXTRACTION_FALLBACK_MODEL` → `settings.llm_extraction_fallback_model` (default `gemini-3.1-flash-lite`). No `thinking_config` sent (API default, medium on 3.6-flash). JSON mode, no schema. Few-shot examples render from `Prism.PythonService/prompts/extract_claims_fewshot.json` (base 11) via `extraction/prompt_loader.py`; two experimental flags `extractor_fewshot_fix` and `extractor_fewshot_shapes` (both default `False` in `config.py:93,105`) gate a bug fix and 8 additional shape examples respectively. Source: `extraction/engine.py:429-430`; `docs/discovery/D1_report.md:69-70`; `config.py:53,63,93,105`.

### 2b. Alternatives tried / piloted / parked / rejected

| What | Date | Result (rows) | Spend INR | Why rejected/parked | Code/flag/tag state | Source |
|---|---|---|---|---|---|---|
| PR-1 #115: fix few-shot loader "note"-field bug (8 of 9 claim-bearing few-shots were blanked to `{"claims": []}`, only example #1 reached the model intact) | Bug found 2026-10-06; PR-1 result 2026-10-08 | Golden FULL mean 20.4→20.6; grounding-negative FULL mean 9.6→8.8; pre-registered marks M1 FAILED, M2 FAILED, M3-M5 passed, M6 not run | Not separately logged for this PR | **Negative on golden** — no coverage gain claimed; kept only as a correctness fix | Draft PR #115, prompt hash `6bfa9ba9790c`; **unmerged**, "merge only after Milestone A re-dumps the fixtures" | `docs/decisions.md:1498-1502,1517-1525` |
| Section-by-section extraction (PR-2) | Parked 2026-10-08 | Feasibility confirmed, not run live | N/A | Of 4 fully-missed refusal rows, 3 sit in sections the extractor already reads — at most 1 row gain; cost 3.1× extractor input, 48 calls/run at 12k max piece size | **PARKED.** Design/build prompt "kept on file"; cited source `pr2_feasibility_report.md` does **not exist in repo** (Glob `**/pr2_feasibility_report.md` → 0 results) | `docs/decisions.md:1527-1532` |
| Experiment 2 (redesigned): extractor few-shot claim-shape repair (`EXTRACTOR_FEWSHOT_SHAPES`, 8 new E1/E2/E3/E5 examples + prompt addendum) | Pre-registered 2026-10-13; result 2026-10-14 | A1 FAIL (treatment recovered 1/13 both runs, needed ≥5/13); A2 FAIL (1-3=-2, needed ≥3); A3 FAIL (treatment kept 11/13 and 9/13, needed ≥12/13); A4 PASS (treatment claim counts 285/287 ≤ control 309×1.5) | **INR 177.93** (pilot 2.77 + control-batch 56.58 + treatment_r1 59.63 + treatment_r2 58.95), against amended 280 cap | **All 4 marks required together; FAIL.** Diagnosis leans toward a task-design problem (one list-all-claims call), not a teaching problem — treatment saw matching examples and still missed E2 (0/3), E3 (0/4), E5 (0/1) | Both flags (`EXTRACTOR_FEWSHOT_FIX`, `EXTRACTOR_FEWSHOT_SHAPES`) stay **default off**; prompt hashes: control `0e07bb0f2680`, treatment `da3a1ab6b587` | `docs/decisions.md:1833-1979,2000-2069` |
| **Experiment 3 Check C — union of past runs** (recovery of the 13 target extraction-miss rows across run1/control_r1/treatment_r1/treatment_r2 combined) | 2026-10-14 | Target rows found in ANY of the 4 runs: **3/13** (P1-R2, P12-R1, P3-R1); matched rows found in ANY: 13/13 | N/A (re-analysis of existing run data, no new calls) | Measurement only, no pass/fail bar | Evidence in git-ignored `scratch/exp3/report.md:82-112` | `scratch/exp3/report.md:91-92` |
| **Experiment 3 Check B — sentence-count sanity check** | 2026-10-14 | Headline anomaly: `2610.11135v1.pdf` under `pysbd_pdf_clean` reports 9,436 sentences (236 chunks) vs. 586 (regex) and 10,606 (`pysbd_text_noclean`) | N/A | Measurement/diagnostic only, no pass/fail bar | Same git-ignored evidence | `scratch/exp3/report.md:73-75` |
| 2-call extractor (sample-and-union) | Mentioned as estimated, never built | Estimated ~+0.2 rows | N/A | Never run | Not built | `docs/discovery/D1_report.md:120`; `docs/FINDINGS.md:26` |

### 2c. Current scores (row counts, date, dev/golden/held-out)
- **Golden (37 rows, 16 refusal/21 positive), current/post-reset, de-leaked prompt `cb3272cce551`:** refusal-family 5/16 (31%), gate 0.30, passes by one row; strict 5/16; wrongly affirmed 4; not extracted 7; positive hits 11/21 (floor 10); false rejection **1/21**; coverage 37/37. Source: `docs/PRISM_STATUS.md:21,22,44`; `docs/decisions.md:1536,1563`.
- **Golden, old baseline (pre-09-18-DB-reset, frozen fixtures from runs 929ca23a/90080172/edbfc5cf — "STALE or DEAD, do not quote"):** 6/16 (38%, gate 0.35), strict 4/16, wrongly affirmed 4, not extracted 6, positive 12/21, false rejection 0/21, coverage 37/37. Source: `docs/PRISM_STATUS.md:24,45`.
- **Held-out (arXiv 2609.20812v3, 12 rows), current:** refusal-family 1/2, positive hits 7/10, false rejection 0/10, coverage 12/12. Used 6 times total; only 2 refusal rows. Source: `docs/PRISM_STATUS.md:23,47-49`.
- **Dev run 1 (12 papers, 31 refusal-family rows), 2026-10-12:** refusal 8/31 (26%); 10 audit misses, 13 extraction misses, 0 grounding misses; auditor-only ceiling 18/31 < floor 22/31 (70%); false rejections 4/88 (draft). Source: `docs/evals/dev_adjudication_run1.md:98-104`; `docs/PRISM_STATUS.md:27`.
- **Extractor-only harness (PR-1, 5 runs/arm):** Golden FULL mean 20.4 before → 20.6 after. Grounding-negative FULL mean 9.6 before → 8.8 after. Extractor finds ~9/16 refusal rows per run; union across 10 runs is 11/16. Source: `docs/PRISM_STATUS.md:34-37`.

### 2d. Cost and tokens
- **~43 LLM calls per paper per pipeline run (range 33-63).** Source: `docs/decisions.md:1677` (2026-10-11).
- **Token use (PR-1 harness):** 30 extractor calls, 1.27M tokens; auditor is ~64-75% of pipeline input tokens; cost ~1.50 USD for those calls (estimate, based on an "unverified third-party price page"). Source: `docs/PRISM_STATUS.md:37`.
- **Cost per claim audit (estimate, not a logged measurement):** ~₹3.9 at today's default (medium thinking) vs ~₹4.7 at thinking=high. Source: `docs/discovery/D1_report.md:129` (Q6 table, marked HYPOTHESIS-level estimate; no per-call cost logging exists in code — gap recorded `docs/decisions.md:48`).
- **Cost of a full 12-paper run — three different recorded values, unreconciled:**
  - Pre-run estimate: INR 240-550/run. Source: `docs/decisions.md:1679` (2026-10-11, before any dev run).
  - Mid-run extrapolation (from 4 of 12 papers): ~INR 101/paper → ~INR 1,220/run. Source: `docs/decisions.md:1707` (2026-10-11).
  - **Actual full 12-paper run:** INR 1,250.00 → 2,298.40, i.e. INR 1,048.40 for 12 papers (~INR 87/paper). Source: `docs/evals/dev_adjudication_run1.md:17` (2026-10-12).
  - A later reference to "about INR 1,050+" for a hypothetical re-run (`docs/decisions.md:1829`) matches the actual-run figure, not the two earlier estimates. **Not reconciled:** why the 4-paper extrapolation (₹1,220/run) overshot the real 12-paper result (₹1,048.40/run).

---

## 3. Grounding (span audit)

### 3a. Used today (code)
Two-stage span grounding in `extraction/grounding.py`. Stage 1: RapidFuzz fuzzy match (`partial_ratio`, threshold 88, unchanged) between the auditor's quoted span and the paper text; since 2026-10-05, both sides are passed through `normalize_for_match` (NFKC, drop U+00AD, rejoin hyphenated line breaks, curly quotes→straight, en/em dash→`-`, collapse whitespace) only when the raw score is <88 — flag `GROUNDING_NORMALIZE`, default **on** (`config.py:60`). Stage 2: LLM judge call, model `LLM_GROUNDING_MODEL` → `settings.llm_grounding_model` (default `groq/openai/gpt-oss-20b`) with fallback `LLM_GROUNDING_FALLBACK_MODEL` → `settings.llm_grounding_fallback_model` (default `gemini/gemini-3.1-flash-lite`); `temperature=0`, JSON-schema output, **max output 512 tokens** (`AUDIT_MAX_OUTPUT_TOKENS = 512`, `extraction/grounding.py:39`, used at `grounding.py:169`), concurrency `AUDIT_CONCURRENCY = 1` (`grounding.py:44`), retries `AUDIT_MAX_ATTEMPTS = 3` with backoff `(1,2,4)s` (`grounding.py:46-47`). Verdict vocabulary Pass/Partial/Fail, rubric branches on the auditor's claim `label`; a `stance` field (`supports`/`refutes`/`neutral`) was added 2026-09-05, independent of verdict, not yet read by any downstream consumer. Source: `extraction/grounding.py:39-47,558-559`; `docs/decisions.md:1319,208-224,232-247`.

### 3b. Alternatives tried / piloted / parked / rejected

| What | Date | Result | Spend INR | Why rejected/parked | Code/flag state | Source |
|---|---|---|---|---|---|---|
| Groq primary auditor (`gpt-oss-20b`) at the 512-token cap | Ongoing, parked for caps-and-429 work | Failed all 11 calls in one measured batch (7 rate limits, 3 `json_validate_failed` at the cap); fallback answered all. Confirmed **still true in current code** (grounding.py:39,169,171) | N/A | Parked for caps-and-429 work, not yet fixed | Unchanged; `AUDIT_MAX_OUTPUT_TOKENS=512` still in code | `docs/decisions.md:1337`; `docs/PRISM_STATUS.md:67` |
| Stage-1 text normalisation (`GROUNDING_NORMALIZE`) | **Merged 2026-10-05**, default on | 20/185 spans fail→pass, 0 pass→fail; 2 claim-level flips (REACT-M03, REACT-M05), both FAIL→PASS; 0 flips on grounding-negative/not_supported rows | N/A (code-only, measured on post-reset DB runs) | Shipped as a correctness fix | **Merged**, flag default on | `docs/decisions.md:1318-1325` |
| Stage-2 grounding rubric "option B" replay (post-normalisation context re-audit) | Measured 2026-10-05 | 9 outcome-changeable spans: 4 Pass, 5 Partial, 0 Fail; claim-level REACT-M03 Fail→Pass, REACT-M05 Fail→Partial | N/A | Measured as a candidate only | **NOT merged** — measured/tested option only; `docs/PRISM_STATUS.md:95` confirms Stage-2 route logging exists only in unmerged PR-1 draft #115 | `docs/decisions.md:1330,1336` |
| B5.1 auditor checklist (caveat-catching, see §4) — table-row gate port item | Dropped 2026-10-02 entry's "Next, item 3" | Not built | N/A | Fixes one symbol seen on one eval row (INFERRED reason) | Dropped | `docs/decisions.md:1203-1207` |

### 3c. Current scores
Reported jointly with golden/held-out extraction numbers (§2c) via `effective_status` — grounding only demotes a claim's status, never raises it. 7 of 13 "not_supported" rows in Dev run 1 are grounding demotions (raw label supported → effective not_supported); 0 demotions on the first 4 papers of that run. Source: `docs/decisions.md:1728`; `docs/evals/dev_adjudication_run1.md:20-21`.

### 3d. Cost and tokens
No grounding-specific cost figure is logged separately; Groq calls are reported as free/low-cost relative to Gemini but no number is given. `docs/FINDINGS.md:38`: "All audits are free" (ambiguous — likely refers to read-only code audits, not LLM grounding calls; **NOT RECORDED** which).

---

## 4. Auditing (claim-level verdict)

### 4a. Used today (code)
Call #3 of the pipeline: one auditor call per claim, free-text output (`VERDICT: supported|partially_supported|not_supported` + `QUOTE:`/`SECTION:`), model `LLM_CLAIM_AUDIT_MODEL` → `settings.llm_claim_audit_model` (default `gemini-3.6-flash`) with fallback `LLM_CLAIM_AUDIT_FALLBACK_MODEL` → `settings.llm_claim_audit_fallback_model` (default `gemini-3.1-flash-lite`), via `prompts/audit_claim_system.md`. No `thinking_config` sent by default (API default, medium). The auditor sees the system prompt plus the whole paper plus the claim text and summary — no chunking or retrieval. Flag `auditor_thinking_level: str | None = None` (`config.py:75`) can override to `low`/`medium`/`high`, unset today. Source: `extraction/engine.py:383-384`; `docs/discovery/D1_report.md:92`; `config.py:75`.

### 4b. Alternatives tried / piloted / parked / rejected

| What | Date | Result (rows) | Spend INR | Why rejected/parked | Code/flag/tag state | Source |
|---|---|---|---|---|---|---|
| Auditor model swap flash-lite → 3.6-flash | 2026-09-04 | Refusal 9/14 FAIL (flash-lite) → 11/14 PASS (3.6-flash) on identical rows — gate flipped on judge strictness alone | N/A | flash-lite was over-matching/under-refusing; matcher's own `DEFAULT_MODEL` (`gemini-2.5-flash-lite`) was retired by Google | **Shipped** — current default is 3.6-flash | `docs/decisions.md:258-270` |
| Auditor prompt v2 — trap-claim labeling (Pattern A/B few-shots) | 2026-09-03 | Refusal 4/14 (29%, v4.1-extractor-only) → 10/14 (71%) with the auditor fix | N/A | Fixed the v4.1 extractor's induced auditor regression | **Shipped**, prompt hash `055d52687cc8` | `docs/decisions.md:282-298` |
| **B5.1 auditor checklist** (checklist fields + deterministic verdict cap, meant to catch missed caveats) | Measured 2026-10-02 | Net effect neutral (18 vs 18 vs 18 across v3 runs); marks failed in both v3 runs, each on different marks; run-to-run variance on identical code as large as the effect | NOT RECORDED (not logged in the entry) | Marks failed; no net gain; noise as large as effect | **Not merged.** Branch `fix/b5.1-auditor-checklist`, tag `archive/b5.1-checklist-attempt`; "stays reference only" | `docs/decisions.md:1044-1050,1178-1181,1496` |
| **Experiment 1 — `AUDITOR_THINKING_LEVEL=high`** | Pre-registered 2026-10-12; result 2026-10-12 | Fixed rows 1/10 (needed ≥3 to PASS); lost hits 0/8. Medium-arm control itself unstable: 8/7/5 refusal hits across 3 samples (~±3 rows of noise). High was stable across 3 repeats (0 variance) but this is an unregistered observation, not a result | **INR 411.95** total (medium×2 155.11, high×3 256.84); push budget left ~INR 738; sealed reserve INR 300 untouched | **FAIL.** Needed fixed ≥3; got 1 | `AUDITOR_THINKING_LEVEL` stays **unset**; switch/replay tooling stays in code, default off. Counted experiment 1 of 8 | `docs/decisions.md:1742-1831` |
| **Scoped-auditor pilot ("Exp 1" in this doc's own numbering — a separate, earlier episode from the one above)** | 1 run, 2026 (exact date NOT RECORDED in `docs/FINDINGS.md`) | 44 claims. P1 passed (2/6 targets), P2 passed (positives held 6/6), P4 passed (0 errors). **Failed P3**: 4 of 11 baseline refusals flipped to supported; code lowered one verdict wrongly (a positive) | **~₹204** | **Negative result.** AUDIT_MODE retired, no current code reference | Code archived on tag `archive/exp1-scoped-auditor` (no code on main). **This pilot has no entry in `docs/decisions.md` at all** — recorded only in `docs/FINDINGS.md:27`, corroborated by `docs/discovery/D1_report.md:118` | `docs/FINDINGS.md:27`; `docs/discovery/D1_report.md:118` |

### 4c. Current scores
See §2c (golden/held-out/dev numbers are reported jointly across extraction+audit+grounding; no auditor-isolated score is tracked except via the ceiling estimates below).
- **Auditor-only ceiling estimates (not measured, explicitly labeled estimates):** on golden-16, extraction-alone ceiling ~10/16 (62.5%), realistic-with-fixes ~9/16 (56%) — "the auditor is the main lever" claim is **withdrawn**. Source: `docs/PRISM_STATUS.md:20`; `docs/decisions.md:1607`.
- **Dev run 1:** auditor-only ceiling (perfect auditor, today's extractor) 18/31 (58%), below the 22/31 (70%) floor. Source: `docs/evals/dev_adjudication_run1.md:102-104`.

### 4d. Cost and tokens
See §2d (per-claim audit cost estimate ~₹3.9-4.7, unmeasured). Experiment 1's medium-arm actual cost (INR 155.11) exceeded its own pre-registered estimate (INR 86.52) by 1.79×, because the estimate assumed 600 audit "thought" tokens vs. a real 2,279. Source: `docs/decisions.md:1785-1788`.

---

## 5. Structuring / brief

### 5a. Used today (code)
Call #4 of the pipeline: one structurer call per claim, same model pair as the auditor (`settings.llm_claim_audit_model` / fallback), using a Pydantic schema (`ClaimLLM`). Its job is to turn the auditor's free-text verdict into structured fields; the structurer's own label is never independently checked against the auditor's `VERDICT:` line. Source: `extraction/engine.py:398-399`; `docs/discovery/D1_report.md:108` (`[VERIFIED engine.py:375-385]`).

### 5b. Alternatives tried / piloted / parked / rejected
No dedicated structurer-stage experiment was found in any source read. The only structurer-adjacent decision is the 2026-09-05 `stance` field addition (reported under §3, since it is consumed by grounding, not the structurer).

### 5c. Current scores
Not tracked separately; folded into the overall pipeline scores (§2c). One known defect: an audit-or-structure exception **drops the claim entirely**, scored as "not extracted." Historically 15 of 84 complete runs lost claims, 76 claims total, all at one call site; PR-B runs had 0. Source: `docs/decisions.md:48`; `docs/discovery/D1_report.md:107`.

### 5d. Cost and tokens
No structurer-specific cost figure found (folded into the ~43-calls/paper total, §2d).

---

## 6. Claims-checklist results (your 14 items)

**1. "Dev run 1: refusal 8/31; 13 extraction misses (E1-E5); 10 auditor misses, pattern A1."**
VERDICT: **VERIFIED.** `docs/evals/dev_adjudication_run1.md:98-101,106-118` (2026-10-12): "Refusal hits: 8/31 (26%). Audit misses: 10. Extraction misses: 13. Grounding misses: 0." Pattern **A1** defined exactly: "headline 'consistent/every/across settings/count' claim contradicted by a specific table cell, a table's scope, or the paper's own caveat/appendix. The auditor accepts the headline and supporting text and does not search tables or appendices for counter-examples." E1-E5 shapes: E1 hedged/in-principle (4), E2 table-derived quantities (3), E3 overreach-vs-sibling (4), E4 method/setup (1), E5 unreported "we observed" (1) = 13.

**2. "Experiment 1 (auditor thinking_level=high): result, spend, verdict."**
VERDICT: **VERIFIED.** `docs/decisions.md:1807-1831`. Verdict: "FAIL. Experiment 1 rejected. AUDITOR_THINKING_LEVEL stays unset. Stage B not run." Spend: "medium x2 INR 155.11, high x3 INR 256.84, total INR 411.95."

**3. "Scoped-auditor pilot negative, tag archive/exp1-scoped-auditor; AUDIT_MODE legacy."**
VERDICT: **VERIFIED — but recorded only in `docs/FINDINGS.md`, with no entry in `docs/decisions.md` (see §10).** `docs/FINDINGS.md:27`: "1 run, 44 claims, ~Rs 204... Failed P3... Negative result; AUDIT_MODE stays legacy. Code archived on tag `archive/exp1-scoped-auditor`." Whole-repo grep for the literal string `AUDIT_MODE` (not just `config.py`) found zero hits in `Prism.PythonService` — confirms it is retired, with no current code reference.

**4. "'Newer Flash with thinking pinned' experiment: amended/deferred?"**
VERDICT: **VERIFIED — deferred, not dropped.** `docs/decisions.md:1916-1919`: "deferred, not dropped — remains a candidate for a later slot if budget allows." `docs/FINDINGS.md:55` separately lists it as an "Optional model test" for the future.

**5. "Note bug: only 1 of 9 claim-bearing few-shots reaches the model intact; PR-1 #115 fix, hash 6bfa9ba9790c, negative on golden; merge after Milestone A."**
VERDICT: **VERIFIED.** `docs/decisions.md:1498-1502,1517-1525`. "8 of 9 claim-bearing few-shots... have a 'note' field, so only example #1 ever reaches the model intact." PR-1: "M1 FAILED... M2 FAILED... No coverage gain is claimed... Prompt hash `6bfa9ba9790c`... Merge only after Milestone A re-dumps the fixtures." Bug confirmed still present in code: `extraction/prompt_loader.py:58`.

**6. "PR-2 section-by-section: parked 2026-10-08; design file pr2_feasibility_report.md missing from repo."**
VERDICT: **VERIFIED.** `docs/decisions.md:1527-1532`. `Glob **/pr2_feasibility_report.md` → 0 results.

**7. "Stage-1 normalisation merged 2026-10-05 (GROUNDING_NORMALIZE on); Stage-2 status?"**
VERDICT: **VERIFIED for Stage-1; Stage-2 NOT merged (measured option only).** `docs/decisions.md:1318-1319,1330,1336`; `docs/PRISM_STATUS.md:95`.

**8. "Groq primary auditor failing at 512-token cap, fallback carries audits — still true in code?"**
VERDICT: **VERIFIED true in docs and in current code.** `docs/PRISM_STATUS.md:67`; code: `extraction/grounding.py:39,169,171`.

**9. "B5.1 branch — what was it, why reference only?"**
VERDICT: **VERIFIED.** Auditor-checklist experiment to catch missed caveats; net effect neutral (18/18/18), marks failed, run-to-run variance as large as the effect. Never merged, tag `archive/b5.1-checklist-attempt`, "stays reference only." `docs/decisions.md:1044-1050,1178-1181,1496`.

**10. "Experiment 2 Stage A: A1 1/13 & 1/13, A2 -2, A3 11/13 & 9/13, A4 PASS; FAIL; INR 177.93."**
VERDICT: **VERIFIED, exact match on every number.** `docs/decisions.md:2000-2014`.

**11. "Push extension: one more experiment, ~INR 560 left, sealed reserve INR 300."**
VERDICT: **VERIFIED, exact match.** `docs/decisions.md:2071-2076`.

**12. "Prompt hashes cb3272cce551 / 0e07bb0f2680 / 0bcf9d44e619 — which is current production?"**
VERDICT: **cb3272cce551, by inference (not stated verbatim anywhere as "production").** `0bcf9d44e619` = pre-de-leak baseline (superseded). `cb3272cce551` = de-leaked frozen baseline, used in Dev run 1, and the hash both `extractor_fewshot_fix` and `extractor_fewshot_shapes` off produce (`config.py:93,105` both default `False`; `extraction/prompt_version.py:43-89`). `0e07bb0f2680` = Experiment 2's rejected control arm.

**13. "Golden refusal 5/16 (or 6/16?), positives 11/21 (or 12/21?), false rejections — latest recorded values and dates."**
VERDICT: **VERIFIED — both real, 5/16 and 11/21 (false rejection 1/21) are current; 6/16 and 12/21 (false rejection 0/21) are the explicitly superseded pre-reset baseline, marked "STALE or DEAD" by `PRISM_STATUS.md:24`.** See §2c for full citations.

**14. "Checks A-E as in scratch/exp3/report.md."**
VERDICT: **VERIFIED, with an important correction to the premise: only Checks A and D carry a pre-set pass/fail bar (≥95% WHOLE); both FAIL it. Checks B, C and E have no bar — they are measurements/diagnosis, not pass/fail results.**
- Check A (splitter survival): FAIL, all 3 splitters (51.3%/5.0%/75.6% vs 95%). `scratch/exp3/report.md:34-51`.
- Check B (sentence-count sanity check): no bar; flags a 9,436-vs-586-vs-10,606 sentence-count anomaly on one PDF. `scratch/exp3/report.md:69-80`.
- Check C (union of past runs): no bar; 3/13 target rows recovered across all 4 prior runs combined. `scratch/exp3/report.md:82-112`.
- Check D (reader bake-off): FAIL, all 4 candidates (53.8%/50.4%/58.8%/94.1% vs 95%); fixed windows closest, "FAIL (by 1 row)." `scratch/exp3/report.md:116-255`.
- **Check E (failure diagnosis): no bar — read-only root-cause analysis of why A and D missed rows.** Key result: raw-text reader-loss ceiling is 112/119 (refusal-family 30/31); fixed-windows' 7 misses are **exactly** the raw-text reader-loss rows — i.e. windowing adds **zero additional loss** beyond what the raw PDF text itself cannot represent. By contrast PyMuPDF4LLM's ceiling is 77/119 (refusal 27/31) and GROBID's is 81/119 (refusal 24/31) — both lose far more at the reader level than raw text does. `scratch/exp3/report.md:259-423`, esp. the Step 1 ceiling table (`:328-332`) and the refusal-family summary table (`:417-421`).

---

## 7. Divergences (unresolved)

1. **D1_report.md vs PRISM_STATUS.md on false rejections.** D1_report.md's own divergences table (`D1_report.md:13`) flags that its working snapshot said 0/21 while the real recorded value is 1/21 (COT-M01) — matches what this inventory independently found for claim 13, but is worth surfacing since D1_report.md is not an authoritative decisions.md entry.
2. **D1_report.md's boundary notes** (`D1_report.md:1-5`) disclose it ran git commands under an exception its author flagged as conflicting with `PRISM_STATUS.md`'s "CC never runs git" rule, and that it saw sealed file *names* (not contents) via a directory listing. Everything D1_report.md asserts is treated here as "per D1_report.md," not independently re-verified (no git was run for this inventory).
3. **`docs/FINDINGS.md:36-38` ("All audits are free")** is ambiguous as to whether it means LLM grounding/audit calls or read-only code-review audits (AG/CC). Not resolved — see §8.

---

## 8. NOT RECORDED

- **Exact date of the scoped-auditor pilot run.** Checked: `docs/FINDINGS.md` (full read, no date given beyond being part of the "What failed" section near PR-1/B5.1 entries, both October 2026), `docs/discovery/D1_report.md` (full read, no date). Not found.
- **Whether "AUDIT_MODE" was ever a real config field before being retired.** Checked: `Prism.PythonService/config.py` (full read), whole-repo grep for literal `AUDIT_MODE` across `Prism.PythonService`. No current or historical definition found in code; only referenced as a value to "record" in two decisions.md run-procedure entries (`:1690,1913`), never defined.
- **Whether "`docs/FINDINGS.md:36-38`'s 'All audits are free'" means LLM calls or review audits.** Checked: `docs/FINDINGS.md` full text (§6 "Cost" section, 3 lines total). Ambiguous on its face; no cross-reference found elsewhere.
- **Why the 4-paper cost extrapolation (~₹1,220/run) overshot the actual 12-paper result (~₹1,048.40/run).** Checked: `docs/decisions.md:1679,1707,1829`; `docs/evals/dev_adjudication_run1.md:17`. No explanation given in any of these entries.
- **Exact date stamps for the "golden 6/16" vs "golden 5/16" results as standalone dated entries.** Checked: `docs/decisions.md:1340,1438-1439,1476-1477,1536`; `docs/PRISM_STATUS.md:16,21,24,44,45`. Both numbers are well-sourced but neither carries its own explicit "— YYYY-MM-DD" header; dates are inferred from surrounding entries.

---

## 9. Other significant facts found (not on the checklist)

- **Four-bucket scorer** replacing omission-credit PASS/FAIL (`docs/decisions.md:929`, ~2026-09-30): old scorer credited silent omissions as refusals; new scorer has 4 mutually exclusive outcomes (skipped/refused/wrongly_affirmed/not_extracted), gated on `match_map.json` coverage.
- **Auditor model swap, 2026-09-04**: flash-lite → 3.6-flash after discovering `LLM_AUDIT_MODEL` also drove the eval matcher, inflating positive hits; `matcher.py`'s old `DEFAULT_MODEL` (`gemini-2.5-flash-lite`) was retired by Google and would 404.
- **Dev set size rule amended, 2026-10-10**: planning estimate assumed ~40 refusal rows from 12 papers; actual yield ~2.7 rows/paper (32 rows, ~30 independent). Rule lowered 40→30 *before* any Prism output was seen.
- **Release targets (2026-10-10)**: release floor = 70% dev refusal (mean of 3 runs), stretch 80%, false-rejection hard cap 10%. Hard exit after 8 counted experiments or push-cap exhaustion.
- **Known labeling uncertainties on the golden set**: REFLEX-M13 claim/notes mismatch; REFLEX-M09, COT-M04, REACT-M10, REACT-M12 flagged unsure; COT-M08's match-map pairing is doubtful (automatic fingerprint carry-over, not hand-adjudicated) — if corrected, wrongly-affirmed 4→3, not-extracted 7→8, refusal count unchanged at 5/16. Source: `docs/decisions.md:1558-1561,1598-1602,1618-1623`.
- **Exp2 cost/token fields** (exact, from `_summary.json`): control_r1 9 calls / 351,467 prompt tok / 24,403 output tok / 56,181 thought tok / INR 56.58; treatment_r1 10 calls / 376,931 / 24,963 / 58,661 / INR 59.63; treatment_r2 10 calls / 376,931 / 24,337 / 57,474 / INR 58.95. All `model_used: gemini-3.6-flash`.
- **Prompt hash computation**: SHA-256 over 8 `PROMPT_FILENAMES` + `schemas.py`, truncated to 12 hex chars (`extraction/prompt_version.py:43-89`); flag states append literal marker bytes rather than changing which files are hashed.
- **Live inventory**: `Prism.PythonService/prompts/` has 10 files (includes the Experiment 2 shape files, currently unused — both flags default off). `Prism.PythonService/eval/` has ~24 top-level modules plus `tests/` and `leakcheck/` subdirectories.

---

## 10. Documentation gaps to backfill (list only — not fixed here)

(a) The scoped-auditor pilot (claim 3) has **no entry in `docs/decisions.md`** — recorded only in `docs/FINDINGS.md:27`, corroborated by `docs/discovery/D1_report.md:118`.
(b) The 2026-10-09 stop-rule decision quoted at `docs/FINDINGS.md:53` ("stop core changes; ship with honest numbers") has **no corresponding entry in `docs/decisions.md`** — flagged independently by `docs/discovery/D1_report.md:15`.
(c) `pr2_feasibility_report.md` is cited as a source at `docs/decisions.md:1532` but **does not exist in the repo** (confirmed via `Glob **/pr2_feasibility_report.md`, 0 results).
(d) Experiment 3's Checks A-E evidence (the splitter/reader bake-off and failure diagnosis underlying claim 14) **sits only in `scratch/exp3/report.md`, which is git-ignored** (`.gitignore:61: scratch/`) — it is local, untracked, and will not survive a clean checkout.

---

*Note on handoff files searched for this inventory: `claude/handoff_2026-10-12.md` and `claude/handoff_2026-10-13.md` are Claude Project docs, outside this repository by design — not a repo documentation gap.*
