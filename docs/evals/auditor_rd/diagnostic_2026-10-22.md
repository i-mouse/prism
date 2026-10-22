> **Status note (2026-10-22, added after review):** Phase 1 tables below are the
> read-only diagnostic. The "Phase 2, revision 2" script in this file was NOT run;
> it was superseded by a direct read of scratch/auditor_rd/raw_text_cache/*.txt
> plus a human spot-check (P6-R2, P4-R1). Corrections: (1) "P1-R3 is a genuine
> regression" is wrong - same code, so it is run-to-run noise; (2) CC's READABLE
> ratings mean "evidence present, numbers correct, rows clear; columns only by
> counting positions". Conclusions are in docs/decisions.md, "Auditor phase
> diagnostic (INR 0) - 2026-10-22".

# Auditor R&D — Phase 1 diagnostic audit (read-only)

## Context

Prism's dev baseline shows 31 refusal rows, 8 caught by the auditor and 10 missed
(pattern A1: a claim's "every/consistent/across" generalization is broken by a table
cell, table scope note, caveat, or appendix line that the auditor never weighs). Three
problems are under investigation: (1) auditor cost, (2) the auditor's failure to find
counter-evidence, (3) verdict flips of roughly ±3 rows between nominally identical
re-runs. This plan captures the Phase 1 read-only findings (SDK settings, cost/caching,
and per-row evidence for all 18 dev rows) and lays out the Phase 2 script, gated on
Nitin's approval. `docs/decisions.md` is authoritative on any conflict with this plan.

All of Phase 1 was done with Read/Grep/Glob/Bash(read-only) only — no file writes, no
LLM/API calls, no code/prompt/label/config/fixture changes. `docs/LABEL_RUBRIC.md`,
`.env`, and any `_key/` or held-out path were not opened.

## Table 1 — Thinking settings per call (file:line), vs SDK-allowed values

**google-genai 1.64.0** (`Prism.PythonService/.venv/Lib/site-packages/google/genai/version.py:16`).
**`ThinkingLevel` enum** (`google/genai/types.py:308-320`): `THINKING_LEVEL_UNSPECIFIED, LOW, MEDIUM, HIGH, MINIMAL`.
**`ThinkingConfig`** fields (`types.py:4665-4681`): `include_thoughts: bool|None`, `thinking_budget: int|None` (0=disabled, -1=automatic), `thinking_level: ThinkingLevel|None`.

| Stage | Call site | Thinking sent at default | Flag that changes it | Flag's allowed values |
|---|---|---|---|---|
| Metadata extraction | `extraction/engine.py:619-627` → `_call_gemini_structured` | Not sent (`thinking_config=None`, `engine.py:220`, `245-249`) | none | — |
| Extractor (pass 1) | `extraction/engine.py:508-515` → `_call_gemini_json` | Not sent — function has **no** `thinking_level` param (`engine.py:319-339`) | none | — |
| Pass 2 | `extraction/pass2.py:51-60` → `engine._call_gemini_structured` | Not sent by default; `pass2_thinking_level` defaults `None` (`config.py:130`) | `pass2_thinking_level` field (`config.py:130`), CLI `--pass2-thinking-level` (`eval/replay_exp3.py:414-416`, `eval/replay_clean.py:643-645`) | `{minimal, low, medium, high}` (`config.py:24`, validator `:132-139`) |
| Pass-2 clean filter | `extraction/pass2_clean.py:166-175` → `engine._call_gemini_structured` | Not sent by default; reuses `pass2_thinking_level` (`engine.py:546`) | same field as Pass 2 | same set |
| Auditor | `extraction/engine.py:462-470` (`_audit_and_structure_claim`) → `_call_gemini_freetext` | Not sent by default; `auditor_thinking_level` defaults `None` (`config.py:82`) | `auditor_thinking_level` (`config.py:82`, validator `:84-91`), CLI `--level` (`eval/replay_audit.py:422`) | `{low, medium, high}` (`config.py:17`) — **no MINIMAL** |
| Structurer | `extraction/engine.py:476-484` (same function) → `_call_gemini_structured` | **Never sent, unconditionally** — no `thinking_level` kwarg passed at all; docstring confirms thinking "reaches only the audit call ... never the structure call" (`engine.py:451-452`) | **none exists** — architecturally excluded | — |
| Span/claim grounding | `extraction/grounding.py:165-172` → `litellm.acompletion` (Groq primary / Gemini Flash Lite fallback) | N/A — non-Gemini-native call, no thinking param | model name only (`config.py:64-65`) | — |
| Eval matcher | `eval/matcher.py:114`/`:177` → `generate_content` | Not sent (`matcher.py:155-160` has no `thinking_config`) | model via env `LLM_EVAL_MATCHER_MODEL` | — |

## Table 2 — Thought tokens per auditor call, unset("medium") vs explicit high

**Correction to the task's premise:** `Prism.PythonService/scratch/b51_replay/` is **not** the
Exp 1 thinking-level experiment — it replays an unrelated "B5.1 checklist" change, on
different papers (Reflexion/CoT/ReAct, not the dev set), with the thinking setting held
constant throughout (grep for "thinking" in `replay.py`/`replay_v3.py`: zero matches).
The genuine Exp 1 unset-vs-high data is `docs/evals/fixtures/dev/exp1_medium_{1,2}` vs
`exp1_high_{1,2,3}` (`_summary.json`, confirmed `"thinking_level"` field at e.g.
`exp1_high_1/_summary.json:13`). Each run = 18 claims × 2 calls (audit + structurer),
exactly the 10 miss + 8 hit rows below. The structurer is bundled under the same
`"stage":"audit"` label (`eval/replay_audit.py:270-274`) but is distinguishable by
prompt size (audit ≈37K tokens vs structurer ≈1.2-1.6K tokens) — and per Table 1, the
structurer never receives a thinking_level regardless of arm, so its token counts here
reflect only API noise, not the "unset vs high" variable.

| Arm | avg audit prompt_tokens | avg audit output_tokens | **avg audit thought_tokens** | avg structurer thought_tokens | file total_thought_tokens | cost_inr |
|---|---|---|---|---|---|---|
| exp1_medium_1 | 37,389 | 346 | **2,263** | 953 | 57,874 | 78.19 |
| exp1_medium_2 | 37,389 | 344 | **2,295** | 751 | 54,832 | 76.92 |
| exp1_high_1 | 37,389 | 337 | **3,333** | 731 | 73,142 | 83.86 |
| exp1_high_2 | 37,389 | 355 | **3,568** | 874 | 79,954 | 86.63 |
| exp1_high_3 | 37,389 | 345 | **3,543** | 881 | 79,629 | 86.35 |

Mean medium ≈2,279 thought-tokens/audit-call (matches `docs/decisions.md:1787`'s own
"real 2,279"); mean high ≈3,481 (+53%), cost +~10%. Per `docs/decisions.md:1807-1811`
this experiment already ran and was **rejected**: "fixed rows 1 of 10 (P1-R1); lost
hits 0 of 8 ... AUDITOR_THINKING_LEVEL stays unset."

For context on run-to-run noise at a *constant* thinking setting (not a thinking-level
comparison, but directly relevant to problem 3 — verdict flips between runs), the 5
`b51_replay` re-runs of the identical 23 claims at the same unset setting show thought
tokens/call swinging 2,696–3,155 (run2 2,848; run_a 2,896; run_b 2,696; v3_a 3,155; v3_b
3,106 — `b51_replay/out/*/usage.json`), and `cached_tokens` swinging 0%–57% of audit
input tokens between nominally identical re-runs.

## Table 3 — Other generation settings

| Call | temperature | top_p | top_k | seed | max_output_tokens |
|---|---|---|---|---|---|
| Auditor (`engine.py:406-413`) | not set | not set | not set | not set | not set |
| Structurer (`engine.py:241-250`) | not set | not set | not set | not set | not set |
| Grounding (`grounding.py:168-169`), for context | **0 (explicit)** | — | — | — | 512 (`AUDIT_MAX_OUTPUT_TOKENS`, `grounding.py:39`) |
| Eval matcher (`matcher.py:157`), for context | **0 (explicit)** | — | — | — | — |

Neither the auditor nor the structurer sets temperature below 1.0 — in fact neither
sets it at all. The two calls with `temperature=0` (Google advises keeping 1.0 for
Gemini 3 models) are grounding and the eval matcher, both outside the auditor/structurer
path this task asked about.

## Table 4 — Auditor request order & cache-eligibility

Builder: `build_gemini_messages_for_audit` (`extraction/prompt_loader.py:153-173`),
called from `_audit_and_structure_claim` (`extraction/engine.py:433-486`, call at
`:463`).

```python
user_content = (
    f"PAPER TEXT:\n{paper_text}\n\n"
    "CLAIM TO AUDIT:\n"
    f"CLAIM_TEXT_VERBATIM: {claim_text_verbatim}\n"
    f"CLAIM_SUMMARY: {claim_summary}"
)
```

- Parts, in order: (1) system prompt = static file `prompts/audit_claim_system.md`,
  re-read fresh every call (`prompt_loader.py:145-150`) but byte-identical content; (2)
  one user message: `PAPER TEXT` block, then `CLAIM TO AUDIT` / `CLAIM_TEXT_VERBATIM` /
  `CLAIM_SUMMARY`.
- **Paper text is before the claim text**: yes.
- **Byte-identical prefix across claims of the same paper**: yes, through the literal
  `"CLAIM TO AUDIT:\nCLAIM_TEXT_VERBATIM: "` — no claim index, no list of prior claims,
  no dynamic instructions are injected earlier. `claim_number`/`total_claims` are passed
  into `_audit_and_structure_claim` but used only for tracer spans/progress callbacks,
  never passed into the builder (confirmed from the full function body). So the stable,
  cache-eligible prefix is: system prompt + `"PAPER TEXT:\n{paper_text}\n\nCLAIM TO
  AUDIT:\nCLAIM_TEXT_VERBATIM: "` for every claim of one paper.

## Table 5 — Measured token split by stage, cached %, auditor share

**No single run on disk has extractor + auditor + structurer + grounding usage
together.** What exists, by source:

- `scratch/b51_replay/out/{run2,run_a,run_b,v3_a,v3_b}/usage.json` — **auditor +
  grounding only** (extraction was replayed from a frozen fixture; `structurer_calls`
  is `[]` in all 5 runs — the "if VERDICT unreadable" fallback never fired across 185
  replayed claims):

  | run | auditor input tokens | grounding input tokens | auditor % of (auditor+grounding) | cached tokens (count/22 calls, % of audit input) |
  |---|---|---|---|---|
  | run2 | 692,415 | 65,604 | 91.3% | 97,460 / 3 calls (14.1%) |
  | run_a | 809,608 | 83,697 | 90.6% | 134,390 / 4 calls (16.6%) |
  | run_b | 809,608 | 85,157 | 90.5% | 458,732 / 13 calls (56.7%) |
  | v3_a | 805,205 | 77,403 | 91.2% | 0 / 0 calls (0.0%) |
  | v3_b | 805,205 | 74,853 | 91.5% | 380,335 / 13 calls (47.2%) |

- `docs/evals/fixtures/dev/exp1_{medium,high}_*/_summary.json` — **auditor + structurer
  only** (no grounding tokens captured here). Auditor share of (auditor+structurer)
  input ≈ 96.4% in all 5 runs (673,003 / (673,003 + ~24,900)).
- `docs/evals/fixtures/dev/exp2/*`, `exp3/*`, `clean/*` — **extractor pass-1/pass-2/
  filter only**, no auditor or grounding at all.
- Top-level `Prism.PythonService/logs/*/*.json` (production/dev-ingest logs): the
  `usage` key exists in the schema (`engine.py:106-164`) but is non-null **only** in
  1,151 files explicitly tagged as eval-replay runs (1,113 `logs/pass2` replay-exp3,
  37 `logs/pass2_clean` replay-clean-filter, 1 `logs/extraction` replay-exp3-pass1).
  **Every genuine production/live ingest log (audit, grounding, structure, matcher,
  metadata, writer, extractor_eval) has `usage` null or absent — NOT FOUND for any real
  cost measurement.**
- `cached_tokens` as a field exists **only** in `b51_replay/out/*/usage.json`; it is
  absent from the production log schema and from the exp1/exp2/exp3/clean schemas.

**Bottom line:** `docs/decisions.md`'s "~75%" auditor cost-share figure is an ESTIMATE
with no measured full-pipeline denominator anywhere on disk. The closest MEASURED
partial shares are ≈90–91% of (auditor+grounding) tokens, and ≈96% of
(auditor+structurer) tokens — never all four stages in one run.

## Table 6 — The 10 auditor misses

6-sample set per row where available: run1 + exp1_medium_1 + exp1_medium_2 +
exp1_high_1 + exp1_high_2 + exp1_high_3. "Raw text" and "position %" are NOT FOUND for
every row (see below) — no file on disk stores the raw text actually sent to the
auditor; `logs/audit/*.json` stores only `response_raw` (the model's output) and call
metadata, never the request body.

| Row | Breaking evidence | Location | NEVER / EXCUSED / CAUGHT / LABEL-ONLY | Scope words dropped? | Raw text | Position % |
|---|---|---|---|---|---|---|
| P1-R1 | Table 4: sampled-OPD cell *rises* under the ablation the claim says "lowers performance" | Table 4 / §4.4 | NEVER×3 (run1, medium_1, medium_2); CAUGHT×3 (high_1,2,3) | **YES** ("every" dropped) | NOT FOUND | NOT FOUND |
| P4-R1 | Table 1/2 per-cell regressions (MInference@64K, FlexPrefill@8K/En.Sum/En.QA/En.MC) contradict "consistent gains" | Abstract/Intro/Concl vs Tables 1-2 | NEVER×7/7 (run1×2 retries + medium_1,2 + high_1,2,3) — unanimous | NO (selective aggregation) | NOT FOUND | NOT FOUND |
| P4-R2 | FlexPrefill-Llama has no raw baseline in Tables 9/10; SeerAttention clip-85/95 below raw, only clip-90 helps | §4.4 | NEVER×6/6 — unanimous | N/A (no quantifier to drop) | NOT FOUND | NOT FOUND |
| P3-R2 | Table 9 position 1: JevKT loses to best deep KT on A09/XES3G5M, below mean; paper calls position 1 "noisy" | §4.2/Table 9 | NEVER×6/6 — unanimous | **YES** ("even at ... first interactions" dropped) | NOT FOUND | NOT FOUND |
| P5-R1 | Fig. 11: only ONE teacher-student pair tested on coding; every other pair is math-only | §5/Fig. 11 | NEVER×2 (run1, medium_1); 4 samples (medium_2, high_1,2,3) carry the adjudicated PS label but with evidence_spans byte-identical to the NEVER sample — **causal link to breaking evidence unconfirmed**, reported INDETERMINATE not CAUGHT | not cleanly assessable | NOT FOUND | NOT FOUND |
| P5-R2 | Table 3 rows g/h are SFT-variants of rows a/f — 15 distinct pairs, not 17; single (math) domain; no survey support for "most commonly used" | §2.1/§6/Table 3 | NEVER×6/6 — unanimous | NO (count "17" preserved; numeric double-count miss) | NOT FOUND | NOT FOUND |
| P6-R2 | Table 10 (dermoscopy) lists 11 VLMs, not 12 — BreastGPT-8B absent; Fig. 3 shows only 8 | Table 3/10, Fig. 3 | NEVER×6/6 — unanimous | NO (precise count, not a generalization word) | NOT FOUND | NOT FOUND |
| P7-R1 | Plural "trajectories" rests on ONE OpenTelemetry pair; paper's own §7 calls it a "development-informed case study not confirmatory"; retained arm had 275 image occurrences vs 0 for method arm (confound) | Abstract/§4.1/§7 | run1 NOT FOUND (no reliable log match); EXCUSED×5/5 (medium_1,2 + high_1,2,3) — evidence present every time via a "Fail"-tagged span, consistently discounted, verdict stays supported | **YES** ("trajectories"→"tasks" in restatement) | NOT FOUND | NOT FOUND |
| P8-R2 | "Use" half is backed; "disuse" half is unsupported per Appendix A.6 (same concession as P8-R1); use proxy is only API-linked | §1/§6/App. A.6/Table 10 | NEVER×2 (run1 tentative match, medium_2); CAUGHT×4 (medium_1 + high_1,2,3 — high thinking unanimous 3/3) | NO | NOT FOUND | NOT FOUND |
| P11-R2 | Table 2 (prompt-eng) vs Table 3 (KD, explicitly "under Pro→Qwen setting" only) — KD baselines never run for Flash target / Opus teacher | §1/Table 2/Table 3/App. A.4 | NEVER×6/6 — unanimous | NO, **notably inverted**: "across the evaluated settings" is preserved verbatim in every paraphrase but never checked against the table's actual coverage | NOT FOUND | NOT FOUND |

6 of 10 rows are NEVER-caught in every available sample regardless of thinking level
(P4-R1, P4-R2, P3-R2, P5-R2, P6-R2, P11-R2).

## Table 7 — The 8 hits

| Row | Evidence used | Caught x/n |
|---|---|---|
| P2-R5 | Table 8 caption itself names the exception: OlympicCoder-7B loses (−1.9), Bespoke-Stratos-7B ties | run1 1/3 self-consistency samples; replay 4/5 |
| P1-R3 | Appendix A.6: the bound doesn't establish how guidance actually evolves during training | run1 1/1; **replay 0/5 — regression**, every replay arm (medium and high alike) lost a hit the original run caught |
| P6-R1 | §6 Limitations: "limited human involvement remains at planning checkpoints," no scalability/cost measurement given | run1 1/1; replay 4/5 (medium_2 misses) |
| P8-R1 | Appendix A.6: 95.8% of unused items unchanged, undercuts the "fading" claim | run1 inconclusive (tentative match only); replay 4/5 (medium_2 misses) |
| P10-R1 | Appendix J: "empirical loop, no formal guarantee" + Table 7 declining scores across cycles | run1 1/1; replay 4/5 confirmed + 1 indeterminate (high_2) |
| P10-R2 | Appendix D.1: M+ is not a matched-data control (different sampler/broader coverage) | run1 adjudicated PS, not independently re-verified; replay 5/5 unanimous |
| P10-R3 | Appendix F.3: estimates are descriptive text stats, not a causal measurement; 1 of 4 estimator configs rises instead of falls | run1 adjudicated PS, not independently re-verified; replay 5/5 unanimous |
| P12-R2 | §6: paper runs zero experiments ("empirical evaluation remains future work") | run1 1/1; replay 4/5 (medium_1 misses this blatant evidence) |

## Key findings (bullets)

1. **The task's premise about `b51_replay` is wrong.** It is not the Exp 1
   thinking-level comparison — it's an unrelated "B5.1 checklist" replay on different
   papers, with thinking held constant throughout. The real medium-vs-high data lives
   in `docs/evals/fixtures/dev/exp1_{medium,high}_*`, and per `docs/decisions.md` that
   experiment already ran and was **rejected** (fixed 1/10 misses, lost 0/8 hits, +10%
   cost) — raising thinking level is a closed question, not an open one.
2. **No measured full-pipeline token split exists anywhere on disk.** The "~75%
   auditor share" figure in `docs/decisions.md` is an estimate; measured partial shares
   are ≈90-91% of (auditor+grounding) and ≈96% of (auditor+structurer) — never all four
   stages together, and no real production ingest has non-null usage data at all.
3. **6 of 10 miss rows are never caught at any thinking level, in any sample found**
   (P4-R1, P4-R2, P3-R2, P5-R2, P6-R2, P11-R2) — thinking level is not the lever for
   most of pattern A1; one row (P7-R1) is a clean EXCUSED case where the evidence is
   always found and always discounted, not missed.
4. **P1-R3 is a genuine regression, independent of thinking level**: the original run's
   auditor caught this hit, but all 5 replay samples (medium and high alike) lost it —
   direct evidence that re-running the identical pipeline can make the auditor strictly
   worse on a row it previously got right, separate from the thinking-level question.
5. **The raw text actually sent to the auditor is never persisted anywhere on disk**
   (production logs store only `response_raw` and call metadata, never the request
   body) — so Table 6's readability/position-% columns are NOT FOUND for all 18 rows.
   This is exactly the gap Phase 2 is meant to close.

## Phase 2 plan (gated — only after "go phase 2")

One local Python script, no network/LLM calls, writing only to
`Prism.PythonService/scratch/auditor_rd/`:

1. Re-create raw paper text for the 12 dev PDFs (`docs/research_papers/`) using the
   pipeline's own extraction path: `extract_pdf_text_sync` (`Prism.PythonService/main.py:102`).
2. For each of the 10 miss rows, locate the breaking evidence in that raw text using the
   pipeline's own normalization: `normalize_for_match` (`extraction/grounding.py:269`)
   plus fuzzy matching (same approach as `docs/evals/exp3_prechecks/check_e_*.py`, which
   already does token-normalized + fuzzy matching against raw PDF text — reuse that
   pattern rather than inventing a new one).
3. Report, per row: found/not found, readable/garbled (row/column labels intact vs.
   split by extraction artifacts), position as % of paper length, and paper length in
   both chars and tokens (chars/4, tagged ESTIMATED).
4. Output: `scratch/auditor_rd/report.md`, then fill the Table 6 gaps in chat.
5. Show the script and exact command before running; Nitin approves each command with
   "Allow once" — do not rely on the existing broad `Bash(uv run *)` allow rule in
   `.claude/settings.local.json`.

No git commands will be run by Claude Code at any point; all changes are left as
uncommitted working-tree changes for Nitin to commit himself.

## Phase 2, revision 2 — after the script stopped at the (invalid) token sanity check

The first Phase 2 script gated on "chars/4 estimate vs measured `prompt_tokens`,"
which Nitin correctly flagged as an invalid test (token usage includes the system
prompt + claim text, and number-heavy text tokenizes denser than chars/4 assumes).
This revision replaces that gate with the checks below. Not yet run — Nitin runs it.

### 1A. Code trace: extracted text -> paper_text in the audit prompt

Nothing is added, removed, truncated, or normalized between PDF extraction and the
auditor's prompt. Full hop-by-hop trace, both for the live pipeline and for the
`eval/replay_audit.py` script that produced the exp1 fixtures:

**Live pipeline:**
1. `main.py:249` - `final_text, page_count = await asyncio.to_thread(extract_pdf_text_sync, local_path)`
2. `main.py:333-334` - `extraction = await extract_claims(paper_text=final_text, ...)` - same `final_text`, unmodified.
3. Inside `extract_claims` (`extraction/engine.py:489-593`), the identical `paper_text` parameter (never reassigned, never sliced) is passed to:
   - the extractor: `extraction/engine.py:508-509` `build_gemini_messages_for_extractor(paper_text)`
   - pass 2: `extraction/engine.py:525-526` `run_pass2(paper_text, ...)`
   - pass-2 clean filter: `extraction/engine.py:545-546` `filter_merged_claims(claims, paper_text, ...)`
   - the audit fan-out: `extraction/engine.py:589-593` `_audit_wrapper(semaphore, paper_text, claim, ...)` - per claim, same `paper_text`.
4. `_audit_and_structure_claim` (`extraction/engine.py:433-470`) receives `paper_text` as a parameter and passes it straight to `build_gemini_messages_for_audit(paper_text, claim_text_verbatim, claim_summary)` at `engine.py:463`.
5. `build_gemini_messages_for_audit` (`extraction/prompt_loader.py:153-173`) embeds it verbatim: `f"PAPER TEXT:\n{paper_text}\n\n..."` - no slicing, no normalization call anywhere in this function.

**`eval/replay_audit.py` (produced the exp1 fixtures used for Table 2):**
1. `eval/replay_audit.py:215-218` - `from main import extract_pdf_text_sync; text, _ = extract_pdf_text_sync(str(pdf_path))`, returned unmodified.
2. `eval/replay_audit.py:265-278` (`_replay_claim`) - `engine._audit_and_structure_claim(semaphore=semaphore, paper_text=paper_text, claim=claim_dict, ...)` - same `text` passed straight through as `paper_text`, zero transformation.

**Answer: NO** - nothing is added, removed, truncated, or normalized on the way, in either path.

### 1B. Saved-text check

**NOT FOUND.** Searched:
- `docs/evals/exp3_prechecks/` - grepped every script for file-write calls (`.write_text`, `open(..., "w")`, `json.dump`, `pickle.dump`, `.txt"`); the only write found is `check_d_grobid_v2.py:139` (`tei_path.write_text(resp.text, ...)`), which saves **GROBID's** TEI-XML output, a different extraction method entirely, not the pipeline's own PyMuPDF/fitz text. `exp3_prechecks/lib.py:61-66` has its own `fitz.open()` extraction function matching `main.py`'s logic, but it recomputes transiently - it is never written to disk.
- `Prism.PythonService/scratch/exp3/` (named in `exp3_prechecks/report.md` as where "raw output" lives) - directory does not exist (glob returned nothing); presumably cleaned up after that experiment.
- No other location in the repo was found holding a persisted PyMuPDF/fitz extraction of any dev paper (consistent with the Phase 1 finding that the request body sent to the LLM is never logged anywhere).

So there is nothing to byte-compare against - the revised script's step 1B will perform this same search at run time and write NOT FOUND (with the paths it checked) into `report.md`, rather than hard-coding today's answer, in case something changes.

### Locator list for the 10 misses + 3 controls (built from `docs/evals/dev_eval.json` scoring_notes, never from the claim's own sentence)

| Row | Window kind | Anchor(s) | Locator string(s) - literal breaking evidence | Notes |
|---|---|---|---|---|
| P1-R1 | table (caption -> +2000) | "Table 4" | "24.80 to 25.10"; "slightly helps sampled OPD" | Cell values/phrase for the one ablation variant that *rises* under the branch. |
| P3-R2 | table | "Table 9" | "0.709"; "0.749"; "noisy" | 0.709/0.749 = A09 position-1 cell (JevKT vs best deep KT); "noisy" = the paper's own characterization of position 1. |
| P4-R1 | table (two anchors) | "Table 1" (locators "81.57", "88.94"); "Table 2" (locators "19.73", "12.15", "66.81") | see anchors | Also check prose locator "11 of 12" (the paper's own hedge phrase) near Abstract/Conclusion. |
| P4-R2 | table | "Table 4"; "Table 9" | "87.76"; "87.79"; "88.09"; "87.88" | SeerAttention/RULER clip percentile cells; 87.88 = raw baseline, 88.09 = the one clip (p=90) that helps. |
| P5-R1 | table (figure caption) | "Figure 11" | "Qwen3-4B-Instruct-2507"; "HumanEval" | The single teacher-student pair name + the coding-only benchmark it's tested on. |
| P5-R2 | table | "Table 3" | "warm-start"; "SFT" | Breaking evidence is structural (rows g/h are SFT-warm-started variants of a/f), not a single prose sentence - see note below. |
| P6-R2 | table | "Table 10" | "ISIC 2018" (must be found in-window); "BreastGPT" (must be ABSENT from the Table-10 window - this is the breaking evidence) | Absence check, not a found-quote check, for the second locator. |
| P7-R1 | prose (+/-600) | "Section 7" / "§7" | "do not estimate the variance of the policy's effect"; "development-informed case study" | Literal caveat phrasing, not the claim's own wording. |
| P8-R2 | prose | "Appendix A.6" | "95.8%" | Exact percentage already confirmed present in Phase 1's agent findings. |
| P11-R2 | table | "Table 3" | "Pro→Qwen" / "Pro->Qwen"; "under the Pro" | Table 3's own caption restricts it to the Pro->Qwen setting. |
| P10-R2 (control) | table | "Table 8" | "broader training-task coverage"; "different sampler" | Scoring_notes says this is **in Table 8's own caption**, so table-window rule applies. |
| P10-R3 (control) | prose | "Appendix F.3" | "permutation-adjusted MPNet"; "does not hold for every proposed iterate" | |
| P12-R2 (control) | prose | "Section 6" / "§6" | "does not by itself establish that the retained idea helped"; "Future work should experimentally evaluate" | |

**P5-R2 note:** this row's own claim sentence is one of the 7 rows Exp 3 pre-check E found "not whole in raw text" (fuzzy score 99.5, cause tagged "other / missing_or_extra_space" in `docs/evals/exp3_prechecks/check_e_raw_output.txt`). That finding is about the **claim's** sentence, not about these table-row locators - per the new rule we never use the claim sentence as a locator anyway, so this shouldn't block finding "warm-start"/"SFT" near Table 3. Flagging it so the result isn't misread if those locators come back NOT FOUND for an unrelated reason.

### pymupdf4llm check

**NOT INSTALLED** - `Prism.PythonService/.venv/Lib/site-packages/` contains `pymupdf` (fitz) only, no `pymupdf4llm`. Per the hard rule, it will not be installed; the script's step 3 prints `NOT INSTALLED` and skips the side-by-side markdown comparison.

### Revised script

The full revised script is below (not yet written to `phase2_locate_evidence.py` - plan mode restricts me to editing only this plan file; Nitin applies it or tells me to write it).

What changed vs. the first version:
- Removed: the chars/4-vs-prompt_tokens gate (Step 1 of v1).
- Added: Step 1B (saved-text search, NOT FOUND reproducible check), Step 1C (evidence-span quote check against `run1` + all 5 `exp1_*` fixtures, grounding_status Pass/Partial, `normalize_for_match` + `fuzz.partial_ratio >= 88`, 95%-per-paper gate, STOP on failure), Step 1D (chars, measured audit prompt_tokens, chars/token, digit-share - info only, explains density outliers like P3).
- Replaced: the old single best-match `locate_quote` with anchor-aware disambiguation - finds every occurrence of each row's anchor string, checks which occurrence's window actually contains the locator string(s), and reports all positions plus which one was picked and why (never silently takes the first match).
- Replaced: fixed +/-600-char window for every row with a window-kind-aware window (table: caption -> +2000 chars; prose: +/-600 chars), and adds a body/table/caption/appendix tag per row.
- Added: pymupdf4llm side-by-side (info only, skipped - not installed).
- Unchanged: control rows (P10-R2, P10-R3, P12-R2), position % computation, `report.md` as the only write target, no network/LLM/DB calls, dev PDFs only via the explicit 12-name list.

**DROPPED** - Nitin decided not to run a script at all for this step. Instead,
since `scratch/auditor_rd/raw_text_cache/*.txt` (written by the first script
before it stopped) are confirmed-trustworthy copies of the exact PyMuPDF text
the auditor received (per the 1A trace: nothing transforms it), the rest of
Phase 2 was done by Read/Grep directly on those 12 cached `.txt` files -
no script, no further writes. Results are in "Phase 2.5" below. The script
text that follows is kept only as a record of what was drafted and NOT run.

```python
"""Phase 2, revision 2 - auditor R&D: reconstruct raw paper text via the
pipeline's own extraction path, validate that reconstruction against saved
evidence-span quotes (not a chars/4 token estimate), then locate the
breaking evidence for the 10 auditor-miss rows (plus 3 stable-hit controls)
in that raw text.

Hard rules this script honors:
- No network calls, no DB calls, no LLM/API calls, no package installs.
- Reads only: docs/research_papers/*.pdf (the explicit 12 dev papers below),
  docs/evals/fixtures/dev/{run1,exp1_medium_1,exp1_medium_2,exp1_high_1,
  exp1_high_2,exp1_high_3}/*.json, docs/evals/exp3_prechecks/ (searched for
  saved raw text only).
- Writes only under Prism.PythonService/scratch/auditor_rd/.
- Does not import main.py or extraction.grounding (import-time side effects
  - aio_pika, psycopg, Azure credentials, OTEL telemetry init, litellm,
  config.settings). extract_pdf_text_sync and normalize_for_match /
  normalize_with_map are copied verbatim below, sources cited.

Sources copied verbatim:
- extract_pdf_text_sync: Prism.PythonService/main.py:102-115
- normalize_for_match, normalize_with_map, _HYPHEN_LINEBREAK_RE,
  _QUOTE_DASH_TABLE, _join_hyphen_linebreak: extraction/grounding.py:253-333
"""
import json
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF - same library main.py uses
from rapidfuzz import fuzz

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../Prism.PythonService
PROJECT_ROOT = REPO_ROOT.parent  # .../Prism
PAPERS_DIR = PROJECT_ROOT / "docs" / "research_papers"
FIXTURES_DIR = PROJECT_ROOT / "docs" / "evals" / "fixtures" / "dev"
PRECHECKS_DIR = PROJECT_ROOT / "docs" / "evals" / "exp3_prechecks"
OUT_DIR = Path(__file__).resolve().parent  # scratch/auditor_rd/
CACHE_DIR = OUT_DIR / "raw_text_cache"
REPORT_PATH = OUT_DIR / "report.md"

CHARS_PER_TOKEN_ESTIMATE = 4  # chars/4, tagged ESTIMATED - info only, not a gate
QUOTE_FUZZ_THRESHOLD = 88
QUOTE_PASS_FRACTION = 0.95

# ---------------------------------------------------------------------------
# Inlined, verbatim pipeline logic. Do not "improve" - fidelity to the real
# code is the point.
# ---------------------------------------------------------------------------


class PdfPasswordProtectedError(Exception):
    pass


def extract_pdf_text_sync(local_path: str) -> tuple[str, int]:
    """Verbatim copy of Prism.PythonService/main.py:102-115."""
    final_text = ""
    with fitz.open(local_path) as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise PdfPasswordProtectedError("password-protected PDF")
        page_count = doc.page_count
        for page in doc:
            final_text += page.get_text()
    return final_text, page_count


_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")
_QUOTE_DASH_TABLE = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"', "‟": '"',
        "–": "-", "—": "-",
    }
)


def _join_hyphen_linebreak(m: "re.Match") -> str:
    if m.group(2).islower():
        return m.group(1) + m.group(2)
    return m.group(0)


def normalize_for_match(text: str) -> str:
    """Verbatim copy of extraction/grounding.py:269-282."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")
    text = _HYPHEN_LINEBREAK_RE.sub(_join_hyphen_linebreak, text)
    text = text.translate(_QUOTE_DASH_TABLE)
    return " ".join(text.split())


def normalize_with_map(text: str) -> tuple[str, tuple]:
    """Verbatim copy of extraction/grounding.py:286-333 (lru_cache dropped;
    this script calls it once per paper)."""
    chars: list[str] = []
    idx: list[int] = []
    i, n = 0, len(text)
    while i < n:
        j = i + 1
        while j < n and unicodedata.combining(text[j]):
            j += 1
        for ch in unicodedata.normalize("NFKC", text[i:j]):
            if ch != "­":
                chars.append(ch)
                idx.append(i)
        i = j

    drop: set[int] = set()
    for m in _HYPHEN_LINEBREAK_RE.finditer("".join(chars)):
        if m.group(2).islower():
            drop.update(range(m.start() + 1, m.end() - 1))

    norm_chars: list[str] = []
    norm_idx: list[int] = []
    pending_space: int | None = None
    for k, (ch, raw_i) in enumerate(zip(chars, idx)):
        if k in drop:
            continue
        if ch.isspace():
            if pending_space is None and norm_chars:
                pending_space = raw_i
            continue
        if pending_space is not None:
            norm_chars.append(" ")
            norm_idx.append(pending_space)
            pending_space = None
        norm_chars.append(ch.translate(_QUOTE_DASH_TABLE))
        norm_idx.append(raw_i)
    return "".join(norm_chars), tuple(norm_idx)


# ---------------------------------------------------------------------------
# Dev paper manifest (docs/evals/dev_adjudication_run1.md:26-39) - explicit
# 12-name list, dev papers only.
# ---------------------------------------------------------------------------

DEV_PAPERS = {
    "P1": "2610.11519v1", "P2": "2610.11132v1", "P3": "2610.11135v1",
    "P4": "2610.10871v1", "P5": "2610.11291v1", "P6": "2610.11312v1",
    "P7": "2610.10590v1", "P8": "2610.12124v1", "P9": "2610.12375v1",
    "P10": "2610.12176v1", "P11": "2610.12114v1", "P12": "2610.12168v1",
}

EXP1_ARMS = ["exp1_medium_1", "exp1_medium_2", "exp1_high_1", "exp1_high_2", "exp1_high_3"]
FIXTURE_SOURCES_FOR_QUOTE_CHECK = ["run1"] + EXP1_ARMS

# The 10 miss rows + 3 stable-hit controls. anchors/locators are literal
# breaking-evidence strings from docs/evals/dev_eval.json scoring_notes -
# never the claim's own sentence. window_kind: "table" -> caption to
# +2000 chars; "prose" -> +/-600 chars.
ROWS = {
    "P1-R1": {
        "paper": "P1", "claim_index": 32, "window_kind": "table",
        "anchors": ["Table 4"],
        "locators": ["24.80 to 25.10", "slightly helps sampled OPD"],
        "section_hint": "Table 4 / §4.4",
    },
    "P3-R2": {
        "paper": "P3", "claim_index": 3, "window_kind": "table",
        "anchors": ["Table 9"],
        "locators": ["0.709", "0.749", "noisy"],
        "section_hint": "Table 9 / §4.2",
    },
    "P4-R1": {
        "paper": "P4", "claim_index": 2, "window_kind": "table",
        "anchor_groups": [
            {"anchors": ["Table 1"], "locators": ["81.57", "88.94"]},
            {"anchors": ["Table 2"], "locators": ["19.73", "12.15", "66.81"]},
        ],
        "locators": ["11 of 12"],  # prose hedge, checked near Abstract/Conclusion
        "section_hint": "Tables 1-2 / Abstract/Intro/Concl",
    },
    "P4-R2": {
        "paper": "P4", "claim_index": 30, "window_kind": "table",
        "anchors": ["Table 4", "Table 9"],
        "locators": ["87.76", "87.79", "88.09", "87.88"],
        "section_hint": "§4.4 (RULER clip ablation)",
    },
    "P5-R1": {
        "paper": "P5", "claim_index": 33, "window_kind": "table",
        "anchors": ["Figure 11"],
        "locators": ["Qwen3-4B-Instruct-2507", "HumanEval"],
        "section_hint": "Figure 11 / §5",
    },
    "P5-R2": {
        "paper": "P5", "claim_index": 1, "window_kind": "table",
        "anchors": ["Table 3"],
        "locators": ["warm-start", "SFT"],
        "section_hint": "Table 3 / §2.1 / §6",
        "note": "claim sentence is one of Exp3 pre-check E's 7 'not whole in raw text' rows; locators here are table-structural, not the claim sentence.",
    },
    "P6-R2": {
        "paper": "P6", "claim_index": 3, "window_kind": "table",
        "anchors": ["Table 10"],
        "locators": ["ISIC 2018"],
        "absence_locators": ["BreastGPT"],  # breaking evidence = this NOT being in-window
        "section_hint": "Table 10 / Table 3 / Figure 3",
    },
    "P7-R1": {
        "paper": "P7", "claim_index": 5, "window_kind": "prose",
        "anchors": ["Section 7", "§7"],
        "locators": ["do not estimate the variance of the policy's effect", "development-informed case study"],
        "section_hint": "§4.1 / §7",
    },
    "P8-R2": {
        "paper": "P8", "claim_index": 7, "window_kind": "prose",
        "anchors": ["Appendix A.6", "A.6"],
        "locators": ["95.8%"],
        "section_hint": "Appendix A.6",
    },
    "P11-R2": {
        "paper": "P11", "claim_index": 7, "window_kind": "table",
        "anchors": ["Table 3"],
        "locators": ["Pro→Qwen", "Pro->Qwen", "under the Pro"],
        "section_hint": "Table 2 / Table 3 / Appendix A.4",
    },
    # Controls (3 stable hits)
    "P10-R2": {
        "paper": "P10", "claim_index": 4, "window_kind": "table",
        "anchors": ["Table 8"],
        "locators": ["broader training-task coverage", "different sampler"],
        "section_hint": "Table 8 caption / Appendix D.1",
    },
    "P10-R3": {
        "paper": "P10", "claim_index": 16, "window_kind": "prose",
        "anchors": ["Appendix F.3", "F.3"],
        "locators": ["permutation-adjusted MPNet", "does not hold for every proposed iterate"],
        "section_hint": "Appendix F.3",
    },
    "P12-R2": {
        "paper": "P12", "claim_index": 0, "window_kind": "prose",
        "anchors": ["Section 6", "§6"],
        "locators": ["does not by itself establish that the retained idea helped", "Future work should experimentally evaluate"],
        "section_hint": "§6",
    },
}


def load_measured_audit_prompt_tokens():
    """paper_id -> claim_index -> {arm: prompt_tokens}, audit-stage call only
    (filtered from the structurer call sharing the same 'stage':'audit'
    label, by taking the larger prompt_tokens of the two records per
    paper+claim)."""
    out: dict = {}
    for arm in EXP1_ARMS:
        path = FIXTURES_DIR / arm / "_summary.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        by_paper_claim: dict = {}
        for rec in data.get("records", []):
            key = (rec["paper_id"], rec["claim_index"])
            by_paper_claim.setdefault(key, []).append(rec["prompt_tokens"])
        for (paper_id, claim_index), tokens_list in by_paper_claim.items():
            audit_tokens = max(tokens_list)
            out.setdefault(paper_id, {}).setdefault(claim_index, {})[arm] = audit_tokens
    return out


def search_for_saved_raw_text(arxiv_id: str):
    """Step 1B: look for a persisted PyMuPDF/fitz extraction of this paper
    anywhere under docs/evals/exp3_prechecks/. Returns (found, searched_paths,
    content_or_None)."""
    searched = []
    candidates = [
        PRECHECKS_DIR / f"{arxiv_id}.txt",
        PRECHECKS_DIR / f"{arxiv_id}_raw.txt",
        PRECHECKS_DIR / "raw" / f"{arxiv_id}.txt",
    ]
    for c in candidates:
        searched.append(str(c))
        if c.exists():
            return True, searched, c.read_text(encoding="utf-8")
    return False, searched, None


def load_evidence_span_quotes(paper_id: str):
    """Gather every evidence_spans[].source_text with grounding_status in
    {Pass, Partial} for this paper, from run1 + all 5 exp1_* fixtures."""
    quotes: set[str] = set()
    for source in FIXTURE_SOURCES_FOR_QUOTE_CHECK:
        path = FIXTURES_DIR / source / f"{paper_id}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for claim in data.get("claims", []):
            for span in claim.get("evidence_spans", []):
                if span.get("grounding_status") in ("Pass", "Partial"):
                    text = span.get("source_text", "").strip()
                    if text:
                        quotes.add(text)
    return quotes


def quote_check(paper_id: str, normalized_text: str) -> tuple[int, int, list]:
    """Step 1C. Returns (found_count, total_count, misses) where misses is
    a list of quotes that did not reach QUOTE_FUZZ_THRESHOLD."""
    quotes = load_evidence_span_quotes(paper_id)
    if not quotes:
        return 0, 0, []
    found = 0
    misses = []
    for q in quotes:
        nq = normalize_for_match(q)
        if not nq:
            continue
        if nq in normalized_text:
            found += 1
            continue
        alignment = fuzz.partial_ratio_alignment(nq, normalized_text)
        score = alignment.score if alignment else 0.0
        if score >= QUOTE_FUZZ_THRESHOLD:
            found += 1
        else:
            misses.append((q, score))
    return found, len(quotes), misses


def find_all_occurrences(normalized_text: str, needle: str) -> list:
    """All normalized-text start positions of needle (case-sensitive, exact
    substring on normalized text - anchors are literal strings like 'Table 4'
    and should match normalized text directly)."""
    positions = []
    start = 0
    while True:
        pos = normalized_text.find(needle, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    return positions


def window_for(normalized_text: str, idx_map: tuple, n_pos: int, window_kind: str, needle_len: int):
    """Raw-text window for a given normalized-position anchor occurrence."""
    if window_kind == "table":
        n_start = n_pos
        n_end = min(n_pos + 2000, len(normalized_text))
    else:  # prose
        n_start = max(0, n_pos - 600)
        n_end = min(n_pos + needle_len + 600, len(normalized_text))
    raw_start = idx_map[min(n_start, len(idx_map) - 1)]
    raw_end = idx_map[min(max(n_end, 1), len(idx_map)) - 1] + 1
    return raw_start, raw_end


def tag_for(anchor: str) -> str:
    if anchor.lower().startswith("table"):
        return "table"
    if anchor.lower().startswith("figure"):
        return "figure caption"
    if "appendix" in anchor.lower():
        return "appendix"
    return "body"


def locate_row(row_id: str, meta: dict, text: str, normalized_text: str, idx_map: tuple):
    """Anchor-aware disambiguation: find every occurrence of every anchor,
    check which occurrence's window actually contains the row's locator
    string(s), and report all positions - never silently take the first
    match. Returns a dict describing what was found, for report.md."""
    groups = meta.get("anchor_groups") or [{"anchors": meta["anchors"], "locators": meta["locators"]}]
    window_kind = meta["window_kind"]
    result_groups = []

    for group in groups:
        group_result = {"anchors": group["anchors"], "locators": group["locators"], "candidates": [], "picked": None}
        for anchor in group["anchors"]:
            n_anchor = normalize_for_match(anchor)
            occ_positions = find_all_occurrences(normalized_text, n_anchor)
            for occ_pos in occ_positions:
                raw_start, raw_end = window_for(normalized_text, idx_map, occ_pos, window_kind, len(n_anchor))
                window_text = text[raw_start:raw_end]
                norm_window = normalize_for_match(window_text)
                locator_hits = {}
                for loc in group["locators"]:
                    n_loc = normalize_for_match(loc)
                    exact = n_loc in norm_window
                    score = 100.0 if exact else (fuzz.partial_ratio_alignment(n_loc, norm_window).score if norm_window else 0.0)
                    locator_hits[loc] = {"found": exact or score >= QUOTE_FUZZ_THRESHOLD, "score": score}
                group_result["candidates"].append(
                    {
                        "anchor": anchor, "norm_pos": occ_pos, "raw_start": raw_start, "raw_end": raw_end,
                        "locator_hits": locator_hits,
                        "hit_count": sum(1 for h in locator_hits.values() if h["found"]),
                    }
                )
        # absence_locators (e.g. P6-R2's "BreastGPT" must NOT appear) are
        # checked against the picked candidate's window after picking.
        if group_result["candidates"]:
            group_result["candidates"].sort(key=lambda c: -c["hit_count"])
            group_result["picked"] = group_result["candidates"][0]
        result_groups.append(group_result)

    absence_results = {}
    for loc in meta.get("absence_locators", []):
        n_loc = normalize_for_match(loc)
        picked = result_groups[0]["picked"] if result_groups else None
        if picked is None:
            absence_results[loc] = "NO WINDOW TO CHECK"
            continue
        window_text = text[picked["raw_start"]:picked["raw_end"]]
        norm_window = normalize_for_match(window_text)
        absence_results[loc] = "ABSENT (as expected)" if n_loc not in norm_window else "PRESENT (unexpected - check manually)"

    return {"groups": result_groups, "absence_results": absence_results}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    measured_tokens = load_measured_audit_prompt_tokens()
    report = []
    report.append("# Phase 2, revision 2 - auditor evidence location (read-only reconstruction)\n")
    report.append("No network/LLM/DB/package-install calls were made. Dev PDFs only, via the explicit 12-name list. All output confined to this directory.\n")

    extracted = {}

    # --- Step 1A note (computed in chat, not here) ---
    report.append("## Step 1A - code trace\nSee chat / plan file: confirmed no transformation between extract_pdf_text_sync and build_gemini_messages_for_audit.\n")

    # --- Step 1B: saved-text search ---
    report.append("## Step 1B - saved raw text search\n")
    report.append("| Paper | Found on disk? | Searched paths |")
    report.append("|---|---|---|")
    saved_text_found = {}
    for p_label, arxiv_id in DEV_PAPERS.items():
        found, searched, content = search_for_saved_raw_text(arxiv_id)
        saved_text_found[p_label] = (found, content)
        report.append(f"| {p_label} | {'FOUND' if found else 'NOT FOUND'} | {', '.join(searched)} |")

    # --- Extract all 12 papers ---
    for p_label, arxiv_id in DEV_PAPERS.items():
        pdf_path = PAPERS_DIR / f"{arxiv_id}.pdf"
        if not pdf_path.exists():
            continue
        text, page_count = extract_pdf_text_sync(str(pdf_path))
        extracted[p_label] = {"text": text, "arxiv_id": arxiv_id, "page_count": page_count}
        (CACHE_DIR / f"{arxiv_id}.txt").write_text(text, encoding="utf-8")

    # byte-for-byte compare if any saved text was found
    report.append("\n### Byte-for-byte comparison (only for papers where saved text was FOUND)\n")
    any_saved = False
    for p_label, (found, content) in saved_text_found.items():
        if not found:
            continue
        any_saved = True
        recreated = extracted.get(p_label, {}).get("text", "")
        if recreated == content:
            report.append(f"- {p_label}: IDENTICAL")
        else:
            first_diff = next((i for i, (a, b) in enumerate(zip(recreated, content)) if a != b), min(len(recreated), len(content)))
            report.append(f"- {p_label}: DIFFERENT - first differing offset {first_diff}")
    if not any_saved:
        report.append("N/A - no saved raw text was found for any paper (see Step 1B table above).")

    # --- Step 1C: quote check (the real validity gate) ---
    report.append("\n## Step 1C - evidence-span quote check (replaces the chars/4 token gate)\n")
    report.append(f"PASS threshold: >= {QUOTE_PASS_FRACTION:.0%} of saved Pass/Partial evidence-span quotes (run1 + all 5 exp1_* arms) found in the recreated text via normalize_for_match + fuzz.partial_ratio >= {QUOTE_FUZZ_THRESHOLD}.\n")
    report.append("| Paper | Found | Total | % | Result |")
    report.append("|---|---|---|---|---|")
    quote_failures = []
    for p_label, arxiv_id in DEV_PAPERS.items():
        if p_label not in extracted:
            report.append(f"| {p_label} | - | - | - | NOT FOUND (PDF missing) |")
            continue
        normalized, _ = normalize_with_map(extracted[p_label]["text"])
        paper_id = f"arxiv-{arxiv_id}"
        found, total, misses = quote_check(paper_id, normalized)
        if total == 0:
            report.append(f"| {p_label} | - | 0 | - | NO SAVED QUOTES (not in run1/exp1 fixtures) |")
            continue
        pct = found / total
        result = "PASS" if pct >= QUOTE_PASS_FRACTION else "**FAIL**"
        report.append(f"| {p_label} | {found} | {total} | {pct:.1%} | {result} |")
        if pct < QUOTE_PASS_FRACTION:
            quote_failures.append((p_label, pct, misses))

    if quote_failures:
        report.append("\n**STOPPED: quote check failed for:** " + ", ".join(f"{p} ({pct:.1%})" for p, pct, _ in quote_failures))
        for p_label, pct, misses in quote_failures:
            report.append(f"\n### {p_label} misses")
            for q, score in misses[:10]:
                report.append(f"- score {score:.1f}: `{q[:150]}`")
        REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
        print(f"STOPPED after quote check - see {REPORT_PATH}")
        return

    report.append("\nQuote check passed for all papers with saved quotes.\n")

    # --- Step 1D: info-only stats ---
    report.append("## Step 1D - info only: chars, measured tokens, chars/token, digit share\n")
    report.append("| Paper | chars | est. tokens (chars/4, ESTIMATED) | measured audit prompt_tokens (claim: arm=value) | chars/measured-token | digit share |")
    report.append("|---|---|---|---|---|---|")
    for p_label, arxiv_id in DEV_PAPERS.items():
        if p_label not in extracted:
            continue
        text = extracted[p_label]["text"]
        chars = len(text)
        est_tokens = chars / CHARS_PER_TOKEN_ESTIMATE
        digit_share = sum(ch.isdigit() for ch in text) / chars if chars else 0
        paper_id = f"arxiv-{arxiv_id}"
        claims_tokens = measured_tokens.get(paper_id, {})
        if not claims_tokens:
            report.append(f"| {p_label} | {chars} | {est_tokens:.0f} | NOT FOUND (not in exp1 replay set) | N/A | {digit_share:.1%} |")
            continue
        claim_index = sorted(claims_tokens.keys())[0]
        arm_tokens = claims_tokens[claim_index]
        token_strs = ", ".join(f"{arm}={v}" for arm, v in sorted(arm_tokens.items()))
        measured_val = max(arm_tokens.values())
        chars_per_token = chars / measured_val if measured_val else None
        report.append(
            f"| {p_label} | {chars} | {est_tokens:.0f} | claim {claim_index}: {token_strs} | "
            f"{chars_per_token:.2f} | {digit_share:.1%} |"
        )

    report.append(
        "\nchars/measured-token well below ~4 indicates denser-than-average tokenization "
        "(e.g. number-heavy tables - digits tokenize less efficiently per character than "
        "prose); check the digit-share column for an explanation of any such outlier.\n"
    )

    # --- Steps 2-4: evidence location ---
    report.append("## Steps 2-4 - evidence window, occurrence disambiguation, position, tag\n")
    report.append(
        "READABLE/PARTLY/GARBLED ratings, the ROW/COLUMN sub-answers, and the P5-R2/P6-R2 "
        "count-recovery answers are added by hand after reading this report - not computed here.\n"
    )

    summary_rows = []
    for row_id, meta in ROWS.items():
        p_label = meta["paper"]
        if p_label not in extracted:
            report.append(f"### {row_id}\nNOT FOUND (paper text not extracted)\n")
            continue
        text = extracted[p_label]["text"]
        normalized, idx_map = normalize_with_map(text)
        located = locate_row(row_id, meta, text, normalized, idx_map)

        report.append(f"### {row_id} ({meta['section_hint']})")
        if meta.get("note"):
            report.append(f"- note: {meta['note']}")

        best_overall = None
        for group in located["groups"]:
            report.append(f"- anchors tried: {group['anchors']}; locators: {group['locators']}")
            report.append(f"  - occurrences found: {len(group['candidates'])}")
            for i, cand in enumerate(group["candidates"]):
                hits = ", ".join(f"{loc}={'HIT' if h['found'] else 'miss'}({h['score']:.0f})" for loc, h in cand["locator_hits"].items())
                marker = " <-- PICKED" if group["picked"] is cand else ""
                report.append(f"    - occurrence {i} at norm_pos {cand['norm_pos']} ({cand['anchor']}): {hits}{marker}")
            if group["picked"] and group["picked"]["hit_count"] > 0:
                if best_overall is None or group["picked"]["hit_count"] > best_overall["hit_count"]:
                    best_overall = group["picked"]
            if group["picked"]:
                tag = tag_for(group["picked"]["anchor"])
                report.append(f"  - picked occurrence reason: highest locator-hit count ({group['picked']['hit_count']}/{len(group['locators'])}); tag={tag}")

        for loc, result in located["absence_results"].items():
            report.append(f"- absence check for `{loc}`: {result}")

        if best_overall is None:
            report.append("- NOT FOUND - no anchor occurrence contained any locator.\n")
            summary_rows.append((row_id, "NOT FOUND", "NOT FOUND", "NOT FOUND"))
            continue

        raw_start, raw_end = best_overall["raw_start"], best_overall["raw_end"]
        window = text[raw_start:raw_end]
        position_pct = (raw_start / len(text)) * 100 if len(text) else 0
        tag = tag_for(best_overall["anchor"])

        report.append(f"- raw char offset: {raw_start}-{raw_end} of {len(text)} ({position_pct:.1f}% through the paper, tag={tag})")
        report.append("- raw text window (exact extraction, no cleanup):")
        report.append("```")
        report.append(window)
        report.append("```\n")
        summary_rows.append((row_id, f"{position_pct:.1f}%", tag, None))

    # --- Step 3: pymupdf4llm side-by-side (info only) ---
    report.append("## Step 3 - pymupdf4llm side-by-side (info only)\n")
    try:
        import pymupdf4llm  # noqa: F401
        has_pymupdf4llm = True
    except ImportError:
        has_pymupdf4llm = False
    if not has_pymupdf4llm:
        report.append("NOT INSTALLED - skipped. Per the hard rule, this script does not install it.\n")
    else:
        report.append("pymupdf4llm is installed; markdown-table regions would be added here (not reached - not installed in this venv as of writing).\n")

    # --- Step 5: summary ---
    report.append("## Step 5 - summary (misses vs hit controls)")
    report.append("| Row | Position % | Tag | Note |")
    report.append("|---|---|---|---|")
    for row_id, pos, tag, note in summary_rows:
        kind = "CONTROL (hit)" if row_id in ("P10-R2", "P10-R3", "P12-R2") else "MISS"
        report.append(f"| {row_id} ({kind}) | {pos} | {tag} | {note or ''} |")

    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
```

## Phase 2.5 - read-only Grep/Read on the cached raw text (no script)

Source: `Prism.PythonService/scratch/auditor_rd/raw_text_cache/*.txt`, one file
per dev paper, written by the first script before it stopped. Line counts:
P1=4166, P2=2947, P3=10131, P4=2217, P5=3153, P6=3005, P7=699, P8=2567,
P9=1941, P10=3149, P11=1793, P12=1273.

### P1-R1 (`2610.11519v1.txt`)
Grep "Table 4": 2 body hits (line 833 caption, line 866 prose) + an incidental
duplicate of the same cell values inside a later appendix table (Table 27,
line ~3902-3928) describing the same ablation at a different seed count -
not the named occurrence. Picked line 833 (the actual Table 4 caption+grid),
because it has the caption, column headers and all 7 cells, unlike the
appendix echo.

Pasted (lines 833-871, caption to +38 lines - the whole table plus the
confirming prose that follows it):
```
833:Table 4: The same teacher-peak branch slightly helps sampled OPD but lowers both students
834:trained with the verifier. Change in three-seed macro score when the branch is added, Qwen3-1.7B-
835:Base, in points. The weight lambda multiplies the branch's teacher part and, with RA, also the sampled
836:guidance. Absolute, benchmark, and per-seed scores are in Appendix D.3.
837:Effect of the teacher-peak branch
838:Sampled OPD
839:REINFORCE++
840:RA+REINFORCE++
841:no weight
842:lambda=5
843:lambda=10
844:lambda=20
845:lambda=5
846:lambda=10
847:lambda=20
848:deltamacro Avg@8
849:+0.30
850:-0.38
...
856:deltamacro Pass@8
857:+0.64
...
864:8
865:Preprint
866:Under sampled OPD (Table 4) the branch raises macro Avg@8 from 24.80 to 25.10 and the Avg@8
867:of every seed. Under REINFORCE++, where lambda scales only the branch, it lowers macro Avg@8 by
868:0.38-1.76 points and Pass@8 by 3.41-3.91 points, a loss that grows with the branch weight. Added
869:to RA, it lowers macro Avg@8 by 2.05-2.16 points and Pass@8 by 3.41-3.91 points...
```
ROW: YES - "deltamacro Avg@8"(848) sits directly above its 7 values.
COLUMN: YES - the value "+0.30" is the 1st of 7 (matches "Sampled OPD, no
weight", the 1st of the 7 header fields 838-847) AND line 866 restates the
exact same fact in plain prose ("the branch raises macro Avg@8 from 24.80 to
25.10"), removing any need to count columns at all.
**READABLE.** Reason: the breaking cell is stated twice - once in the
flattened table (countable), once in unambiguous prose immediately after.
Position: line 833/4166 = 20.0%. Tag: table (+ immediate prose restatement).

### P3-R2 (`2610.11135v1.txt`)
Grep "0.709"/"0.749" (with leading zero): 0 hits - the paper prints decimals
without a leading zero (".709"). Re-grepped "noisy": 2 hits (line 2125,
the Table 9 footnote; line 2307, an unrelated appendix mention). Table 9
caption itself: 1 hit (line 2123, preceded by an early citation at line 697
that is just a reference, not the table). Picked line 2123 as the named
occurrence (has the caption, headers and data; line 697 has none of that).

Pasted (lines 2123-2163, caption to +40 lines - the Position-1 block the
scoring_notes cites):
```
2123:Table 9: P2 (new learners), every cell. AUC by the position of the target in a new learner's sequence with N=8
2124:training learners (Jev0-shot uses none), mean+-SD over 5 seeds...
2125:predictions as P1. Position 1 has only 41-50 targets per dataset, so its AUC is noisy; - = one class only. +Best of 28
2126:pyKT models, chosen on the whole (N, dataset) cell. Best in bold, second best underlined.
2127:Method
2128:A09
2129:NIPS34
2130:XES3G5M
2131:DBE
2132:Alg05
2133:Junyi
2134:A17
2135:Mean
2136:Position 1
2137:JevKT
2138:.709+-.059
2139:.644+-.047
2140:.512+-.057
2141:-
2142:.799+-.022
2143:.517+-.024
2144:.660+-.066
2145:.640
2146:Jev0-shot (N=0)
2147:.689+-.103
...
2155:Best deep KT+
2156:.749+-.049
2157:.558+-.056
2158:.542+-.049
...
2163:.607
```
ROW: YES - "Position 1"(2136) + method name (2137/2146/2155) sit directly
above each 8-value block.
COLUMN: PARTLY - the 8 headers (A09...Mean, lines 2128-2135) appear ONCE at
the very top of the whole table and are never repeated near the "Position
1"/"Positions 2-5"/"Positions 6-10"... blocks that follow every ~27 lines, so
tying ".512" to "XES3G5M" (3rd of 8) means counting 3 positions into an
unlabeled run of 8 numbers with no local anchor, 7 row-groups deep into the
table. The *first* column (A09, used for the primary .709-vs-.749 citation)
is easier (it's simply the first number after the method name), but later
columns genuinely require counting.
**PARTLY.** Reason: row labels are clear and local; column attribution is
correct-by-position but has no local header to check against.
Position: line 2123/10131 = 21.0%. Tag: table.
Note: this is also the paper (P3) whose chars/token ran ~2x the chars/4
estimate in the original sanity check - Table 9 alone (and its many sibling
tables) is dense with these one-decimal-per-line values (".709", ".644",
etc.), which tokenize far less efficiently per character than prose; the
10,131-line file is unusually long relative to its page count for exactly
this reason.

### P4-R1 (`2610.10871v1.txt`) - Table 1, Table 2, and the "11 of 12" sentence
Grep "Table 1"/"Table 2"/cell values: Table 1 caption 1 hit (line 487); cell
values 81.57/88.94 each appear 3x (main Table 1 body + two appendix repeats of
the same ablation, e.g. lines 1470/1555/1575/1985/2044/2062) - picked the
first (lines 487-548), the main-body occurrence, over the appendix repeats.
Same for Table 2 (caption line 550; cell values 19.73/12.15/66.81 repeat at
596-598, 1683-1685, 2133-2135 - picked 596-598, inside the named Table 2).//
"11 of 12" appears once (line 763).

Pasted, Table 1 (lines 487-521, caption to +34 lines):
```
487:Table 1: RULER (Hsieh et al., 2024) results under matched sparse-attention settings. Within each
488:framework, Original and MASA use the same sparse implementation and differ only in the ranking
489:rule; Full Attention is the reference. deltaFull is the signed Avg. difference from Full Attention. Higher
490:is better. Bold marks the better Avg. between Original and MASA.
491:Variant
492:4K
493:8K
494:16K
495:32K
496:64K
497:128K
498:Avg.
499:deltaFull
500:MInfer
...
510:Original
511:97.7 91.2 88.5 85.0 82.3 77.6 87.0
...
519:MASA
520:97.93 91.29 88.50 85.45 81.57 78.88 87.27
521:+2.87
```
ROW: YES - "MInfer"(500)/"MASA"(519) labels directly precede the value line.
COLUMN: YES - all 7 values are on ONE line (520), in the same order as the
7 headers listed just above (492-498); counting to the 5th (64K=81.57) is
trivial on a single line.
**READABLE.**

Pasted, Table 2 (lines 550-607, caption to +57 lines):
```
550:Table 2: InfiniteBench (Zhang et al., 2024) results under matched sparse-attention settings...
...
554:Variant
555:En.Sum En.QA En.MC En.Dia Zh.QA
556:Code
557:Debug
558:Math
559:Find
...
568:MInfer
...
595:MASA
596:19.73
597:12.15
598:66.81
...
607:+1.00
```
ROW: YES - "MInfer"(568)/"MASA"(595) precede the block.
COLUMN: YES *for the cited cells specifically* - "En.Sum En.QA En.MC En.Dia
Zh.QA" are all on ONE line (555) in order, so the first two per-line values
(19.73, 12.15) map unambiguously to En.Sum/En.QA. Later headers ("Code
Debug", "Math Find", "Retr. PassKey/Number/KV") are each split across two
lines with no visual grid, which would be harder to parse - but that's not
what this row's locators need.
**READABLE** (for the specific cells cited; flagging the later headers as a
structural wrinkle that doesn't affect this row).

Pasted, "11 of 12" (lines 760-768, caveat +/-3... extended to show the full
sentence since it runs long):
```
760:The benefits are particularly evident at longer con-
761:text lengths, the main target of sparse attention
762:acceleration. Across the four RULER configurations
763:at 32K, 64K, and 128K, MASA improves 11 of 12
764:matched length-level scores. For every configuration,
765:the mean gain over these longer contexts at 32K-128K
766:exceeds that at 4K-16K.
```
ROW/COLUMN: N/A (prose). **READABLE** - plain sentence, no structure to
parse. Note: the unqualified headline ("MASA improves all eight matched
average scores... consistent accuracy gains") sits only ~45 lines earlier
(line 717-718) in the same subsection (4.2 Main Results) as this "11 of 12"
caveat - they are not far apart.
Position: Table 1 line 487/2217 = 22.0%; Table 2 line 550/2217 = 24.8%;
"11 of 12" line 763/2217 = 34.4%. Tag: table / table / body.

### P4-R2 (`2610.10871v1.txt`) - Table 9 (RULER probe ablation)
Grep "87.76"/"87.79"/"87.88"/"88.09": the smaller Table 4 (line 993,
"Ablation of MASA probe choices") has 87.88/87.79/88.09 but NOT 87.76; Table
9 (line 1955, "Full RULER probe ablation") has all four. Picked Table 9
because it's the only one containing all the cited values.

Pasted (lines 1955-2067, caption to +112 lines - long because each row
explicitly repeats its own "Setting"+"Clip p"+"Norm alpha" fields rather
than relying on a one-time header):
```
1955:Table 9: Full RULER probe ablation. Clip p denotes norm clipping at percentile p, and Norm alpha
1956:denotes soft norm balancing. The case p = - and alpha = - is raw MASA without norm control. Bold
1957:Avg. marks the best MASA variant within each setting.
1958:Setting
1959:Clip p
1960:Norm alpha
1961:4K
1962:8K
1963:16K
1964:32K
1965:64K
1966:128K
1967:Avg.
1968:MInference
1969:-
1970:-
1971:97.66
...
1977:87.13
1978:MInference
1979:90
1980:0.6
...
1987:87.27
1988:SeerAttention
1989:-
1990:-
...
1997:87.88
1998:SeerAttention
1999:85
2000:-
...
2007:87.76
2008:SeerAttention
2009:90
2010:-
...
2017:88.09
2018:SeerAttention
2019:95
2020:-
...
2027:87.79
2028:FlexPrefill-Llama
2029:90
2030:-
...
2037:89.26
2038:FlexPrefill-Llama
2039:95
2040:-
...
2047:89.22
2048:FlexPrefill-Llama
2049:97.5
2050:-
...
2057:89.94
2058:FlexPrefill-Qwen
2059:-
2060:-
...
2067:72.16
```
ROW: YES, unusually strong - every row restates its own "SeerAttention" +
clip-percentile ("85"/"90"/"95"/"-") as literal row-identifying fields
immediately before its 7 values, so there is no counting at all, unlike
P3-R2's table.
COLUMN: YES - 7 values per row in the same fixed order as the 7 headers
above; "Avg." is always the 7th/last number before the next row's labels
restart.
**READABLE.** Also directly confirms, by literal absence, that
FlexPrefill-Llama has no "-"/"-" (raw) row in this table (its rows start at
clip p=90) while FlexPrefill-Qwen does (line 2058-2060) - the "FlexPrefill-
Llama has no raw MASA result" claim is verifiable just by scanning for the
missing row.
Position: line 1955/2217 = 88.2%. Tag: table.

### P5-R1 (`2610.11291v1.txt`) - Figure 11
Grep "Figure 11": 1 hit (line 1339, the caption). Grep "Qwen3-4B-Instruct-
2507": 7 hits across the paper (main text, Table 2 hyperparameters, Table 3
rows, Figure 13-17 panel labels) - the Figure 11 caption occurrence (line
1339-1341) is the one that names the pair for the coding-transfer claim.

Pasted (lines 1274-1341, the body sentence through the figure's caption and
axis/legend text - no numeric curve values are present as text, only axis
ticks and legend labels):
```
1274:The gains transfer beyond the training domain.
1275:As shown in Fig. 11, models distilled only on math-
1276:heavy datasets [26] also improve on HumanEval and
1277:HumanEval+, with Semi-OPD remaining ahead of
1278:OPD. This suggests that the gains are not limited to
1279:fitting the math training distribution but transfer to
1280:broader reasoning tasks.
...
1310:0
1311:50
1312:100
1313:Distillation step
1314:60.0
...
1320:untrained
1321:HumanEval
1322:OPD
1323:Semi-OPD
...
1337:Math-only OPD 
1338: coding task transfer
1339:Figure 11 | Transfer to coding. Code performance
1340:of models distilled on math only (Qwen3-1.7B <-
1341:Qwen3-4B-Instruct-2507).
```
ROW/COLUMN: N/A (figure, not a table). The SCOPE fact (only one pair, only
coding) is plain text in the caption (1339-1341) and matches the body
prose's own wording "models" (plural) despite only one pair being shown.
The plotted curve VALUES themselves are **FIGURE-DATA-NOT-IN-TEXT** - only
axis ticks (0/50/100, 60.0/62.5/.../70.0) and legend labels (untrained/
HumanEval/OPD/Semi-OPD) are extractable as text; the actual line/point data
is vector graphics, not text.
**READABLE** for the scope-limitation evidence this row needs (caption
states the single pair and single benchmark family in plain English);
**FIGURE-DATA-NOT-IN-TEXT** for the underlying curve values, which aren't
needed here but are flagged per the task's rule.
Position: line 1339/3153 = 42.5%. Tag: figure caption.

### P5-R2 (`2610.11291v1.txt`) - Table 3 (17 pairs)
Grep "Table 3": 1 caption hit (line 1725) plus later cross-references (1682,
2879) that are just pointers, not the table itself. Grep "warm-start"/"SFT":
"Pairs (g) and (h) start from an SFT checkpoint of the student..." at line
1666, inside the "A. Training and Evaluation Setup / Models" intro that
directly precedes Table 3's own caption (1725) - picked this as the primary
occurrence (it's prose, directly adjacent to the table, not a stray mention).

Pasted (lines 1659-1732, intro section through the table's own caption/
footnote - table body continues below, reconstructed separately):
```
1659:When Do We Need On-Policy Distillation? Distilling on Offline Student Rollouts Is Often Better
1660:A. Training and Evaluation Setup
1661:Models.
1662:Tab. 3 lists all 17 teacher-student pairs used in our experiments. They cover three groups:
...
1666:expert pair. Pairs (g) and (h) start from an SFT checkpoint of the student, after doing 1 epoch of SFT on
1667:the teacher generated rollouts. Reasoning mode (thinking T / non-thinking NT) is fixed and matched per
1668:pair...
...
1725:Table 3 | All 17 teacher-student pairs, sorted by AUC gain of Semi-OPD over OPD. Model names link to the
...
1730:Train Len
...
1731:SFT on teacher rollouts. +Evaluated with a 40,960-token response limit; all other pairs use 32,768.
```
Table body reconstruction (letter printed AFTER each row's 7 values, not
before - confirmed by cross-checking against the caption's own AUC-sorted
order): of the 17 rows, exactly two have "(SFT)" literally in the Student
field - letter **h** (Student "Qwen3-1.7B (SFT)", Teacher "Qwen3-4B-
Instruct-2507") and letter **d** (Student "Qwen3-4B (SFT)", Teacher
"Qwen3-30B-A3B-Instruct-2507"). Cross-matching teachers: row **h**'s teacher
matches row **p**'s (Student "Qwen3-1.7B", same teacher, non-SFT); row
**d**'s teacher matches row **c**'s (Student "Qwen3-4B", same teacher,
non-SFT). So the two SFT-tagged rows are each a same-teacher duplicate of a
*different*, non-adjacent-lettered row than the scoring_notes' "(g) and (h)
are variants of a and f" states.
ROW: YES. COLUMN: YES, unusually clean - no header-counting needed at all
for "is this row SFT or not," because it's printed directly in the Student
field itself.
**READABLE**, with one flagged discrepancy: the raw text supports "YES, 2 of
17 rows are SFT-warm-started duplicates of other already-tested pairs" (so
15 distinct pairs) via both the line-1666 prose and the literal "(SFT)"
Student-field tags - but the *specific letters* the raw text ties to the SFT
rows (h and d, matching p and c's teachers) don't match the letters the
scoring_notes cites (g and f) or (g and h). This may be a labeling slip in
either dev_eval.json's scoring_notes or in how this table's "#" column was
captured by the extractor (the column is printed once per row at a fixed
offset, so a page-layout quirk could shift which value lands next to which
letter) - worth a second look before relying on exact letters, though the
core double-count fact itself is solid.
Position: line 1725/3153 = 54.7%. Tag: table (caption + intro prose).

### P6-R2 (`2610.11312v1.txt`) - Table 10 (11 VLMs, no BreastGPT-8B)
Grep "Table 10": 1 caption hit (line 2366) plus 2 prose references just
before it (2353, 2357) discussing it - picked 2366 (the actual grid).
Grep "BreastGPT": 11 hits total; checked each against the Table 10 window
(2366-2466) - **zero** fall inside it; all 11 are either in Table 3 (771),
its surrounding prose (648, 868, 950, 2495, 2580, 2626, 2725, 2790, 2850,
2943) or the Table-3-vs-Table-10 comparison discussion after Table 10
(2958, 2960, 2999) - none inside Table 10's own grid.

Pasted (lines 2366-2466, caption to +100 lines - the full table):
```
2366:Table 10: Evaluation performance on ISIC 2018. Choice tasks report Accuracy / Macro-F1 (%),
2367:while detection reports mIoU / Acc@IoU0.5 (%). Best results for each metric are shown in bold.
2368:Finding Attribute
2369:Model
2370:Diagnosis
2371:Globules
2372:Milia-like
2373:Neg. net.
2374:Pigment net.
2375:Streaks
2376:Detection
2377:General-purpose VLMs
2378:InternVL3-8B
...
2394:Qwen3-VL-8B-I
...
2418:Qwen3-VL-32B
...
2426:Medical VLMs
2427:MedGemma-4B
...
2435:Lingshu-7B
...
2443:Hulu-Med-7B
...
2451:QoQ-Med-7B+
...
2459:Lingshu-32B
...
2466:44.5 / 53.3
```
ROW: YES - each model name directly precedes its own row of 7 value-pairs.
COLUMN: YES - 7 headers (Diagnosis...Detection, 2370-2376) sit directly
above the first data row, ~10 lines away, same order every row.
**READABLE.** The model list is exactly 11 names (6 general-purpose + 5
medical) - counting them directly gives 11, and BreastGPT-8B is confirmably
absent from this specific list (it appears elsewhere in the paper, including
Table 3's 12-model list, just not here).

Also checked Figure 3 (line 1019 caption, legend at lines 979-1018): found
only **4** distinct model names repeated across its 3 sub-panels (Qwen2.5-7B,
Qwen3-32B, MedGemma-4B, Lingshu-32B) - not 8 as the dev_eval.json
scoring_notes states. Flagging this as a second possible imprecision in the
scoring_notes (alongside P5-R2's letter mismatch) rather than asserting a
number the raw text doesn't support; it does not affect the Table 10 finding
above, which is independently solid.
Position: Table 10 line 2366/3005 = 78.7%. Tag: table.

### P7-R1 (`2610.10590v1.txt`)
Two independent pieces of breaking evidence, both very explicit:
- "Section 4.1"/Table 2 (Planroom numbers): Table 2 caption at line 440; the
  "283,105 versus 265,965" restatement is 1 hit, immediately below the table
  (line 462-463) - no ambiguity about which occurrence.
- Section 7 ("Limitations and next experiments", line 583-584): the exact
  caveat sentence at lines 585-586 - 1 hit, no other candidates.

Pasted, Table 2 + prose (lines 439-467, caption to +28 lines):
```
439:Workload contrast and repeated pilot
440:Table 2. Planroom completed pair.
441:Metric
442:Retained
443:Method
444:Supported browser journeys
445:12/12
446:12/12
447:Final and peak prompt tokens
448:265,965
449:283,105
...
462:Planroom yields no context or cost saving: the method ends with 6% more prompt tokens
463:(283,105 versus 265,965) and uses less than 1% more total tokens (68,136,934 versus 67,669,624).
```
ROW: YES ("Final and peak prompt tokens" directly above its 2 values).
COLUMN: YES (only 2 columns, Retained/Method, labeled right above).
**READABLE**, and the prose at 462-463 restates the exact same numbers
immediately below - zero ambiguity either way.

Pasted, Section 7 (caveat sentence +/-3 lines, lines 582-589):
```
582:10
583:7
584:Limitations and next experiments
585:The principal limitation is sampling: one OpenTelemetry pair and one Planroom pair do not
586:estimate the variance of the policy's effect. The Sphinx batch has three sessions per arm but
587:only one authored task and an older configuration.
588:There is no preregistered held-out task
589:distribution, no randomized OpenTelemetry order...
```
**READABLE** - plain prose under an explicit "Limitations" heading.
Position: Table 2 line 440/699 = 63.0%; Section 7 caveat line 585/699 =
83.7%. Tag: table (small) and body (a numbered main-text Limitations
section, not literally an appendix).

### P8-R2 (`2610.12124v1.txt`) - Appendix A.6
Grep "A.6": 1 heading hit (line 1468) plus 1 cross-reference from earlier in
the paper (line 826, "(SS A.6)") pointing to it. Grep "95.8%": 1 hit (line
1493, inside Table 10) plus its own prose restatement at line 1518 - picked
line 1468 onward as the named occurrence (it's the actual appendix section).

Pasted (lines 1468-1519, heading to +51 lines, table included):
```
1468:A.6
1469:KNOWLEDGE CHANGES ACROSS CONSECUTIVE CONSOLIDATIONS
...
1488:Table 10: Knowledge-item transitions in ToolBench grouped by API-linked use between consecutive
1489:consolidations. Outcome columns report percentages within each group.
1490:Intervening use
1491:Unchanged Supplemented Updated Rewritten Dropped
1492:No detected use
1493:95.8
1494:0.9
1495:0.1
1496:3.1
1497:0.1
...
1517:detected (0.1%). These associations connect subsequent knowledge changes to intervening work and
1518:feedback, without establishing that use alone causes the changes. Most items without detected use
1519:remain unchanged (95.8%), so these adjacent-consolidation statistics do not establish general fading
```
ROW: YES ("No detected use" directly above its 5 values).
COLUMN: YES - all 5 headers on ONE line (1491) immediately above the first
data row; "95.8" is the 1st value under "Unchanged", the 1st header.
**READABLE**, doubly confirmed by the prose restatement at 1517-1519
immediately below the table.
Position: line 1468/2567 = 57.2%. Tag: appendix.

### P11-R2 (`2610.12114v1.txt`) - Table 3
Grep "Table 3": 1 hit (line 713, the caption, which names the scope
restriction directly: "Comparison with KD methods under the Pro->Qwen
setting"). Grep "under the Pro": same single hit. No other candidates - this
is the only Table 3 in the paper.

Pasted (lines 706-752, 7 lines before through the confirming prose after):
```
706:UTT (Ours)
707:51.7
...
713:Table 3: Comparison with KD methods under the Pro->Qwen setting.
714:Method
715:Omni-MATH-2
716:KernelBench
717:Acc.
718:Acc.
719:Fast1
720:Student
721:34.3
722:9.2
723:12
724:SeqKD (Kim & Rush, 2016)
...
740:UTT (Ours)
741:62.4
742:50.0
743:32
744:tasks and target models...
...
749:Comparison with KD methods. Table 3 compares UTT with parameter-updating KD methods.
750:With Student parameters fixed, UTT exceeds the strongest baseline by 7.2, 8.2, and 4 percentage
751:points on Omni-MATH-2 accuracy, KernelBench accuracy, and Fast1, respectively.
```
ROW: YES. COLUMN: YES (3 values per row, 3 headers immediately above).
**READABLE** - and the scope restriction itself is stated in the table's own
title, as plainly as possible; the "7.2, 8.2, 4" margins are also restated
in prose right after the table.
Position: line 713/1793 = 39.8%. Tag: table (caption states scope).

### P10-R2 (`2610.12176v1.txt`) - Table 8 caption / Appendix D.1
Grep "Table 8": the controls are defined earlier (line 1612, a pointer) and
the actual table is at line 1847 - picked 1847 (the table itself). Grep the
caveat phrase: 1 hit, inside the caption (1849-1850).

Pasted (lines 1840-1859, the last data row through the Appendix D.1
restatement):
```
1840:M +
1841:119
1842:17.22
1843:28.82
1844:68.3
1845:73.3
1846:48.3
1847:Table 8: Teacher-composition controls on five shared evaluation tasks. Shared train denotes tasks
1848:51, 53, 56, and 307. Dashes mark quantities not reported here. X has 49 evaluated rollout pairs; the
1849:other S, M, S+, M + comparisons have 50. M + has broader training-task coverage and a different
1850:sampler, so it is not a matched-data control.
...
1858:These differences in sampling, data, and checkpoint selection limit what can be attributed to teacher
1859:composition alone.
```
**READABLE** - the limitation is stated by name ("M +") directly in the
table's own caption, and restated independently in Appendix D.1 nine lines
later.
Position: line 1847/3149 = 58.7%. Tag: table caption.

### P10-R3 (`2610.12176v1.txt`) - Appendix F.3
Grep "permutation-adjusted MPNet": 3 hits (line 656, main text; line 2169,
Appendix F.3 itself; line 2334, Appendix G/behavioral audit, a different
context). Picked line 2169 - inside the section the scoring_notes names.

Pasted (lines 2164-2177, heading to +13 lines):
```
2164:F.3
2165:VALUES AND INTERPRETATION
2166:Tables 12 and 13 give the absolute estimates underlying the changes plotted in the main text. From
2167:iteration 3 to 11, roles and instructions lose task information, while contracts and hops gain it.
2168:Unconditional total correlation falls in all four encoder/estimator combinations. The task-centered
2169:estimate falls in three; permutation-adjusted MPNet is the exception. Intermediate values need not
2170:be monotone.
...
2173:redundancy concerns the retained path and does not hold for every proposed iterate. These estimates
```
**READABLE** - plain prose under an explicit "F.3 Values and Interpretation"
heading.
Position: line 2164/3149 = 68.7%. Tag: appendix.

### P12-R2 (`2610.12168v1.txt`)
Grep "Section 6": only an early roadmap sentence (line 86, "Appendix A.
Section 6 discusses limitations...") - the actual body heading is just
"Discussion" (line 762), not literally printed as "Section 6" anywhere near
the content. Grep the two breaking quotes: 1 hit each (lines 781, 787), both
inside "Discussion" / "From hindsight to foresight" and "Future empirical
validation".

Pasted (lines 762-796, the section header through the single bluntest
sentence in the paper):
```
762:Discussion
763:From hindsight to foresight.
...
780:(provided a certain threshold is met), while the other ideas are discarded...
781:in the spirit of expert iteration. However, a high score does not by itself establish that the retained idea helped the model
782:solve the problem. For example, when not orchestrating the training loop carefully, the model might learn to ignore the
...
786:Future empirical validation.
787:Future work should experimentally evaluate the proposed method. The evaluation
...
795:AI assistance was also used for implementation and testing in the associated software project. This version of the
796:manuscript reports no empirical evaluation.
```
**READABLE** - about as explicit as a caveat can get; the paper states
outright, twice, that it ran no experiments. Note: dev_eval.json's "Section
6" is a referent label the scoring_notes author used, not the paper's own
literal heading text ("Discussion") - a minor naming mismatch, not a
readability problem.
Position: line 781/1273 = 61.4% (or line 762/1273 = 59.9% at the section
header). Tag: body.

## Summary table

| Row | Rating | Position | Tag |
|---|---|---|---|
| P1-R1 | READABLE | 20.0% | table (+ prose restatement) |
| P3-R2 | PARTLY | 21.0% | table |
| P4-R1 (Table 1) | READABLE | 22.0% | table |
| P4-R1 (Table 2) | READABLE | 24.8% | table |
| P4-R1 ("11 of 12") | READABLE | 34.4% | body |
| P4-R2 | READABLE | 88.2% | table |
| P5-R1 | READABLE (scope evidence); FIGURE-DATA-NOT-IN-TEXT (curve values) | 42.5% | figure caption |
| P5-R2 | READABLE (letter-label discrepancy flagged) | 54.7% | table + body |
| P6-R2 | READABLE | 78.7% | table |
| P7-R1 (Table 2) | READABLE | 63.0% | table |
| P7-R1 (§7) | READABLE | 83.7% | body |
| P8-R2 | READABLE | 57.2% | appendix |
| P11-R2 | READABLE | 39.8% | table |
| P10-R2 (control) | READABLE | 58.7% | table caption |
| P10-R3 (control) | READABLE | 68.7% | appendix |
| P12-R2 (control) | READABLE | 61.4% | body |

**Headline finding: 15 of 16 located regions are READABLE; only P3-R2 is
PARTLY (column attribution, not row attribution, is the weak point - and
only for its later columns, not the specific one the breaking evidence
needs). Every one of the 10 miss rows' breaking evidence is sitting in
plainly readable text - most restated in plain prose immediately next to
the table they discuss. This rules out "the auditor couldn't find/parse the
evidence" as the explanation for 9 of the 10 misses; the failure is in what
the auditor does with evidence it can read, not in extraction quality.**
