# Read-only auditor-redesign diagnostic — verification report

No files changed, no commands beyond read-only Read/Grep/Glob/Bash/Write-plan-file-only. No LLM/API calls, no git commands, no servers started. This file mirrors the chat report below (the user's task asked for chat output; this file exists only because plan mode requires a plan file).

Tags: VERIFIED (file:line) / NOT FOUND (paths searched) / UNSURE (why).

---

## CHECK A — Pass 2 and filter on main

**A.1 — config.py defaults**
| Flag | Default | Location |
|---|---|---|
| `auditor_thinking_level` | `None` | VERIFIED `Prism.PythonService/config.py:82` |
| `extractor_second_pass` | `False` | VERIFIED `Prism.PythonService/config.py:121` |
| `pass2_thinking_level` | `None` | VERIFIED `Prism.PythonService/config.py:130` |
| `extractor_pass2_clean` | `False` | VERIFIED `Prism.PythonService/config.py:152` |

**A.2 — files exist; code path with both flags off**
- `extraction/pass2.py` and `extraction/pass2_clean.py` exist on this branch. VERIFIED (Glob).
- With `extractor_second_pass=False`, `extract_claims` (`extraction/engine.py:489-516`) runs only the pass-1 extractor call (`engine.py:505-516`) and skips the entire pass-2/pass-2-clean block, which is gated by `if settings.extractor_second_pass:` at `engine.py:518` (pass-2-clean itself additionally gated at `engine.py:539`). VERIFIED `extraction/engine.py:489-556`.

**A.3 — prompt-hash pinning**
- `cb3272cce551` (flag-off hash) IS pinned in a test: `Prism.PythonService/tests/test_extractor_second_pass.py:33-34,44` (`get_prompt_version(extractor_second_pass=False) == "cb3272cce551"`), and also referenced as the preflight-required hash in `eval/replay_audit.py:19,51` and `eval/replay_exp3.py:199`. VERIFIED.
- `7b3e37e260b9` (clean-attempt pass-2 prompt hash) is pinned in `docs/decisions.md:2915,2931,2954` and in fixture headers (e.g. `docs/evals/fixtures/dev/clean/clean_r2/arxiv-2610.10590v1_buckets.json:6`), but **NOT FOUND in any test** (searched `Prism.PythonService/tests/`, zero matches). VERIFIED (pinned in decisions/fixtures) + NOT FOUND (no test pin).

---

## CHECK B — Clean-attempt results (pass 2 + filter)

**B.1 — K1–K8 table** (source: `docs/evals/clean_labels/clean_attempt_score.md`)

| Mark | Bar | r1 (clean_r1) | r2 (clean_r2) | Verdict | Source line |
|---|---|---|---|---|---|
| K1 | — (13 target, 7 stable, no key) | found 5/13 | found 6/13 | FAIL | score.md:3-7 |
| K2 | retain 18/18 | 18/18 pass | 18/18 pass | PASS | score.md:9-12 |
| K3 | r <= 1.4 (report only) | mean r=2.5037 | pooled r=2.4696 | no verdict | score.md:14-17 |
| K4 | <= INR 130/paper | mean proj. 230.52 | pooled proj. 227.55 | FAIL | score.md:19-22 |
| K5 | >= 0.95 grounding | 0.9907 | 0.9905 | PASS | score.md:24-27 |
| K6 | precision >= 0.70 | low 0.8136 (n=59) | high 0.9492 (n=59) | PASS | score.md:29-32 |
| K7 | not_same <= 1 | low 43 (n=60) | high 18 (n=60) | FAIL | score.md:34-37 |
| K8 | filter <= INR 40/run; attempt <= 350 | filter 64.25 | filter 58.31 | FAIL (attempt total 311.04 itself <=350) | score.md:39-43 |

Overall: FAIL (score.md:45).

**B.2 — the 13 extraction-miss rows, found in r1/r2** (source: `docs/evals/clean_labels/k1_stage_diagnostic.md:9-21,31-43`)

| row_id | clean_r1 (S2/S3) | clean_r2 (S2/S3) |
|---|---|---|
| P1-R2 | not found | not found |
| P2-R1 | not found | not found |
| P2-R3 | found | found |
| P2-R4 | found | found |
| P3-R1 | found | found |
| P4-R3 | found | found |
| P5-R3 | not found | not found |
| P7-R2 | not found | not found |
| P8-R3 | found | found |
| P9-R1 | found | found |
| P11-R1 | not found | not found |
| P11-R3 | not found | not found |
| P12-R1 | not found | not found |

VERIFIED, `docs/evals/clean_labels/k1_stage_diagnostic.md`.

**B.3 — reconciling K1 (0 drop) vs K7 (18-43 drop) — different sets, both true**
- K1 diagnostic (`k1_stage_diagnostic.md:23-25,45-47`): "S2 (pre-filter) found" == "S3 (final) found" in BOTH runs (clean_r1: 5/13 both stages; clean_r2: 6/13 both stages) — **delta = 0**. This measures only the 13 known target rows: the filter removes none of them.
- K7 (`clean_attempt_score.md:34-37`): measures a **separate 60-claim sample** of pass-2 output across all 12 papers (not restricted to the 13 target rows), scored against a hand-labelled key for "is this candidate the same claim as a neighbour." `not_same` = 43 of 60 (low bound) / 18 of 60 (high bound) candidates that a human labeller judged genuinely distinct got the filter's "same" (duplicate) tag anyway.
- Both numbers are VERIFIED and both true: they are disjoint samples (13 specific target rows vs. a 60-claim general-population sample) measuring different things (recall on known misses vs. over-aggressive dedup on a broad sample).

**B.4 — were pass-2-recovered claims ever sent to the auditor?**
- VERIFIED NO. `docs/decisions.md:3045-3046`: "Pass-2-recovered claims (about 5-6 of 13) were never audited: their end-to-end value is unmeasured." Consistent with Check A.2: `EXTRACTOR_PASS2_CLEAN`/`EXTRACTOR_SECOND_PASS` are off by default and the clean-attempt runs that produced pass-2 claims were extraction-only replays (`eval/replay_clean.py`), never piped into `_audit_and_structure_claim`.

---

## CHECK C — Auditor misses: missed evidence, or seen and excused?

**C.1 — how were NEVER/EXCUSED/CAUGHT decided?**
VERIFIED: from structured fields only (the claim's `label`/VERDICT and `evidence_spans[].grounding_status`), **not** from the auditor's free-text reasoning.
- The six samples Table 6 of `docs/evals/auditor_rd/diagnostic_2026-10-22.md` draws from (`run1` + `exp1_medium_1/2` + `exp1_high_1/2/3`) are the fixture files under `docs/evals/fixtures/dev/{run1,exp1_medium_1,exp1_medium_2,exp1_high_1,exp1_high_2,exp1_high_3}/*.json`.
- VERIFIED by direct inspection (`docs/evals/fixtures/dev/exp1_high_1/arxiv-2610.10871v1.json:25,28,34,41,44,50,56`): these files contain only `label` and `grounding_status` fields — **no free-text field exists in them at all**. So any tagging done from these files is necessarily structured-field-only.
- Corroborating detail in the diagnostic itself: P7-R1 is tagged EXCUSED "via a 'Fail'-tagged span" (a `grounding_status` value) and P5-R1 is downgraded to INDETERMINATE because its `evidence_spans` were "byte-identical" to a NEVER sample — both are comparisons of structured fields, not quotes from free text.
- The diagnostic file itself never quotes or references `response_raw` content for any of the 10 miss rows' Table 6 classification (it explicitly says raw-request text, not raw-response text, "is never persisted" — a different claim).

**C.2 — where is the auditor's full free-text output saved, and how reliable is the (row, sample) mapping?**
- VERIFIED: saved in `Prism.PythonService/logs/audit/{timestamp}_{chat_id}_{correlation_id}.json`, field `response_raw` (`extraction/engine.py:136-161`, `_call_gemini_freetext` docstring at `engine.py:389-400`: "reasoning happens in prose first").
- For the 5 `exp1_*` replay arms, `eval/replay_audit.py` calls the auditor with `chat_id=f"replay-{paper_id}"`, `correlation_id=None` (`replay_audit.py:276-277`), giving filenames like `..._replay-arxiv-2610.10871v1_none.json`. VERIFIED — 96 such files exist on disk, dated 2026-10-12.
- **Row mapping is reliable by content, not by filename/position.** The filename only identifies the paper, not the claim index or arm. `_run_once` (`replay_audit.py:301-328`) processes papers and claims in a fixed, deterministic sorted order with `asyncio.Semaphore(1)` (fully sequential, no concurrency), so position-within-a-run is theoretically deterministic — but run boundaries are not marked in the logs (no `level`/`repeat_index`/`claim_index` field is written, `engine.py:152-162`), and raw timestamp gaps in the 96 files do not cleanly segment into 5 even blocks. The reliable method actually used here was **content matching**: each `response_raw` restates the specific claim being audited, which uniquely identifies the row even without knowing the arm.
- **Arm identity (medium_1 vs. medium_2 vs. high_1/2/3) is NOT reliably recoverable** from the logs: no field records thinking_level, repeat index, or arm name, and `usage` (which could have fingerprinted an arm via thought-token counts) is absent from these log entries (confirmed empty in every file read). This matches Check D.5's finding. Per the task's own instruction, I did not force an arm label onto any single file; findings below are reported as "at least one of the 5 replay samples for this row," not attributed to a specific arm.
- **`run1`'s own free text is NOT FOUND.** `docs/evals/fixtures/dev/run1/arxiv-2610.10871v1.json:10` stores `extraction_run_id` (a Postgres row id), which does not appear in any `logs/audit/*.json` filename (searched, 0 matches) — and that id is a DB primary key looked up via `eval/replay_audit.py:196` (`_RUN_SQL`), not a chat_id/correlation_id ever used for a log filename. Resolving it would require querying Postgres, which the hard rules forbid. **Stopping this part of the check for `run1`, per the task's own instruction.**

**C.3 — breaking-value search in available free text** (6 always-missed rows, each confirmed by at least 1 of the ~5-6 replay instances for that row; exact quotes below)

| Row | Tag | Evidence |
|---|---|---|
| P4-R1 | **MENTIONED-NOT-USED** | `logs/audit/20261012T153352041982_replay-arxiv-2610.10871v1_none.json`: quotes "Across the four RULER configurations at 32K, 64K, and 128K, MASA improves **11 of 12** matched length-level scores" as supporting evidence for VERDICT: supported, never noting "11 of 12" contradicts the claim's "consistent gains." |
| P4-R2 | **NOT MENTIONED** | `logs/audit/20261012T161612972579_replay-arxiv-2610.10871v1_none.json`: cites only the favorable cells (87.88→88.09 at clip p=90); never mentions clip p=85 (87.76, below raw) or that FlexPrefill-Llama has no raw/"-" row at all. VERDICT: supported. |
| P3-R2 | **NOT MENTIONED** | `logs/audit/20261012T153508087978_replay-arxiv-2610.11135v1_none.json`: claims JevKT is "above the best deep KT model **at every position**," then cites only "the second to fifth interactions" — silently skipping position 1, the one cell (.709 vs .749) where JevKT loses. Word "noisy" never appears. VERDICT: supported. |
| P5-R2 | **NOT MENTIONED** | `logs/audit/20261012T153553721716_replay-arxiv-2610.11291v1_none.json`: takes the paper's "17 teacher-student pairs" at face value ("Table 3 explicitly lists all 17... tested"); never mentions "SFT" or "warm-start" or that 2 of the 17 are same-teacher duplicates. VERDICT: supported. |
| P6-R2 | **NOT MENTIONED** | `logs/audit/20261012T154933429552_replay-arxiv-2610.11312v1_none.json`: takes the paper's "twelve VLMs" self-description at face value, quoting Section 5.1/Table 3; never cross-checks Table 10's actual count (11) or BreastGPT-8B's absence. VERDICT: supported. |
| P11-R2 | **MENTIONED-NOT-USED** | `logs/audit/20261012T154323987217_replay-arxiv-2610.12114v1_none.json`: explicitly quotes "under the Pro->Qwen setting" from Table 3's own caption, then still concludes the claim's "across the evaluated settings" is VERDICT: supported. |

Summary for the 6 always-missed rows: **4 NOT MENTIONED, 2 MENTIONED-NOT-USED, 0 MENTIONED-AND-ARGUED-AWAY, 0 NO FREE TEXT.** (Sample size caveat: 1 replay instance read per row, not all 5 arms — see C.2 on why arm identity can't be assigned; a second instance of P4-R1, P4-R2, P5-R2 and others was skimmed and showed the same pattern but is not separately quoted here.)

Two additional rows checked beyond the always-missed set, both showing genuine within-row variance (supporting decisions.md's own "+/-3 rows of noise" finding, and *contradicting* the "causal link unconfirmed" framing for P5-R1 — see note):
- **P1-R1**: `...T161955500345_replay-arxiv-2610.11519v1_none.json` — MENTIONED-AND-USED: explicitly cites "Table 4... slightly *improves* performance... sampled OPD (+0.30)" and downgrades VERDICT to partially_supported ("does not lower performance universally"). This is a CAUGHT-arm instance.
- **P5-R1**: two instances read, `...153533262234` (VERDICT: supported, no scope caveat) vs. `...154820734542`/`...154047056309` (VERDICT: partially_supported, explicitly reasoning "extrapolating from a single non-math domain on one model pair... uses broader language than the experimental scope justifies"). **Note:** the original diagnostic (`diagnostic_2026-10-22.md:173`) called this row's PS verdicts "causal link to breaking evidence unconfirmed" because the *structured* `evidence_spans` were byte-identical to a NEVER sample — but the *free text* in the PS instances explicitly articulates and uses the single-pair/coding-only scope limitation. This is a direct illustration of C.1's finding: structured-field-only tagging can disagree with what the free text actually reasoned.
- **P7-R1**: checked one instance (`...153330562344_replay-arxiv-2610.10590v1_none.json`, VERDICT: supported) — no mention of "Section 7," "trajectories," or the single-pair/confound caveat; the free text only cites the favorable OpenTelemetry/Planroom comparison. Consistent with Table 6's EXCUSED framing, though I could not locate the word "trajectories" itself in this instance to confirm it's the identical claim wording quoted in the diagnostic's locator table — **UNSURE** whether this is the exact same claim variant referenced there (same paper, same section evidence, but the claim's own restated wording differs slightly in emphasis).
- **P8-R2**: multiple instances mention "95.8" and use it to downgrade VERDICT to partially_supported — but paper P8 has two claims (R1-hit and R2-miss) that are nearly identically worded ("unused experience... recedes... without importance scores/decay rules"), and I could not reliably tell the two apart by content alone. **UNSURE / mapping not reliable — stopping this part of the check for P8-R2 specifically**, per the task's own instruction.

---

## CHECK D — Cost

**D.1 — source of the per-paper cost figures**
- INR ~101/paper: MEASURED, mid-run extrapolation from 4 of 12 papers' real AI Studio spend. VERIFIED `docs/decisions.md:1707` (2026-10-11): "AI Studio spend INR 1,250.00 -> 1,655.55 for 4 papers = about INR 101 per paper."
- INR ~87/paper: MEASURED, the actual completed 12-paper run. VERIFIED `docs/evals/dev_adjudication_run1.md:17`: "run 1 ingestion INR 1,250.00 -> 2,298.40 (INR 1,048.40 for 12 papers, about INR 87/paper)." Cross-referenced in `docs/research/fact_inventory_2026-10-14.md:64`.
- Both are measured real spend, not modeled estimates; "87-101" spans the mid-run extrapolation and the real final number from the same run.

**D.2 — per-paper pass2_cost_inr / filter_cost_inr, both full clean runs**
VERIFIED, run-level totals ÷ 12 papers (`docs/evals/fixtures/dev/clean/clean_r1/_summary.json:7-8`, `clean_r2/_summary.json:7-8`; paper count confirmed as 12 via `docs/decisions.md:2954` "12/12 papers"):

| Run | pass2_cost_inr (total → per-paper) | filter_cost_inr (total → per-paper) |
|---|---|---|
| clean_r1 | 91.00 → 7.58 | 64.25 → 5.35 |
| clean_r2 | 91.08 → 7.59 | 58.31 → 4.86 |
| mean | 7.59 | 5.11 |
| range | 7.58-7.59 | 4.86-5.35 |

Note: no per-call `cost_inr` field exists in the fixture `records` arrays (only token counts) — true paper-by-paper variance (vs. this run-total average) is **NOT FOUND**; only the run-level mean is stored.

**D.3 — is 87 hard-coded in the K4 scorer?**
VERIFIED YES: `Prism.PythonService/eval/score_clean.py:50`: `C4_COST_PER_PAPER_FACTOR = 87`.

**D.4 — price table**
VERIFIED `Prism.PythonService/eval/pricing.py:8-10`: model gemini-3.6-flash; `USD_PER_1M_INPUT = 0.75`, `USD_PER_1M_OUTPUT = 3.75` (thinking tokens billed as output per the module docstring, sourced to `docs/decisions.md:1676`), `INR_PER_USD = 100`. No separate cached-token rate exists in this formula.

**D.5 — cached_tokens logging; usage-null in live logs**
- VERIFIED NOT FOUND in the current pipeline/replay schema: `cached_tokens` exists only in `scratch/b51_replay/out/*/usage.json` (an unrelated B5.1-checklist replay), per `docs/evals/auditor_rd/diagnostic_2026-10-22.md` Table 5. It is absent from `logs/audit/*.json`'s schema (`extraction/engine.py:152-161` — no such key written) and from the `exp1/exp2/exp3/clean` fixture summaries.
- VERIFIED directly: a genuine production log (`Prism.PythonService/logs/audit/20260820T110037220756_..._ingest-....json`) has no `usage` key at all (not null — absent entirely). Same confirmed for the `exp1_*`/`replay-` logs read in Check C (e.g. `...153352041982...`) — none carry a `usage` field, consistent with `_write_structured_log` not being passed `usage` from `_call_gemini_freetext` (`engine.py:421-428`, no `usage=` kwarg passed, unlike the structured-call variants at `engine.py:282-291,305-314`).

---

## CHECK E — Readiness for a paid auditor replay (nothing executed)

**E.1 — what eval/replay_audit.py needs**
- Env vars (names only, no values read): `prism_db_host`, `prism_db_databasename`, `prism_db_username`, `prism_db_password` (Postgres); `ConnectionStrings__messaging`, `ConnectionStrings__blobs` (RabbitMQ/Blob — required with no default); `ai_api_key` (Gemini); `groq_api_key`; plus several `llm_*_model` name vars. All VERIFIED required (no default) at `Prism.PythonService/config.py:39-41,52-53,56,63` — pydantic-settings fails fast at import if any is missing (`config.py:3-7`).
- DB: **required for a real run** (not `--estimate`/`--dry-run`). `_hash_check_and_load_text` (`replay_audit.py:188-218`) opens a live Postgres pool (`memory_db.create_db_connection_pool`) to verify each paper's `extraction_run_id` against `file_records.content_hash` before loading its PDF text; called once per paper in `_run_once` (`replay_audit.py:320`) unless `--dry-run` (which `continue`s before reaching it, `replay_audit.py:315-318`).
- RabbitMQ/Qdrant/Aspire: **not used by the replay logic itself** — but importing the script pulls in `extraction.engine` → `config.py`, whose `PrismSettings` requires the RabbitMQ/Blob connection-string vars to be *present* (any string value) just to construct successfully, even though replay_audit.py never calls them. Qdrant is NOT FOUND anywhere in `replay_audit.py` (grep, 0 matches) — not a dependency of this script at all.
- Input files: `docs/research_papers/*.pdf` (12 dev papers), `docs/evals/fixtures/dev/run1/*.json` (claim text + headers), optionally a `--claims` JSON file.
- **Can it run with only a Gemini key? NO.** VERIFIED: `--estimate`/`--dry-run` need no live services but still need all the above env vars present as strings (import-time validation) plus Groq's var; a real paid run additionally needs a live, reachable Postgres instance with the matching `file_records`/`document_extractors` rows.

**E.2 — flag support**
| Flag | Supported? | file:line |
|---|---|---|
| `--estimate` | YES | `replay_audit.py:426`, short-circuits before any DB/LLM call (`:409-411`) |
| `--max-inr` | **NOT FOUND** in this file (searched `replay_audit.py` argparse block, `:420-430`; such a flag exists in a different script, `replay_clean.py`, not here) | — |
| inline claims | **NOT FOUND** — `--claims` (`:423`) takes a JSON **file path** only, no inline/string option | — |
| grounding cost logging | **NOT supported, explicitly excluded**: the cost summary print says "(grounding calls not included - approximate..." | `replay_audit.py:362` |
| thinking-level flag | YES, `--level` (required, `low`/`medium`/`high`) | `replay_audit.py:422` |

**E.3 — installed google-genai SDK**
- Version: `1.64.0`. VERIFIED `Prism.PythonService/.venv/Lib/site-packages/google/genai/version.py:16`.
- `service_tier`: **NOT FOUND** anywhere in `types.py` (0 matches) — confirms `docs/decisions.md`'s "no service_tier" claim.
- Explicit caching: **YES, present**. `CachedContent`/`CachedContentDict` classes at `types.py:12603,12634`; `client.caches` property on both sync and async clients, `Prism.PythonService/.venv/Lib/site-packages/google/genai/client.py:572` (sync) and `:216` (async).
- Batch API: **YES, present**. `BatchJob`/`BatchJobSource` classes at `types.py:14222-14280+`; `client.batches` property at `client.py:580` (sync) and `:224` (async).
- This is a finding worth flagging: nothing in the diagnostic or decisions.md discusses caching/batch availability even though both exist in the installed SDK — only Flex/`service_tier` was checked and ruled out.

---

## CHECK F — False-rejection baseline

**F.1 — does an S-row match map for the 88 dev S rows exist?**
- VERIFIED, path `docs/evals/dev_match_map.json`. It contains exactly 88 `"P#-S#"` row keys (grep count = 88) alongside the 31 refusal-family rows. **But all 88 S-row entries have `"decided_by": null"` (grep count = 88 of 88)** — none are adjudicated. The 31 entries with `"decided_by": "Nitin..."` are all non-S (refusal-family) rows.
- So: the match map's *schema/placeholder* exists, but it has **zero completed S-row adjudications**. This matches `docs/decisions.md:3113-3115`, which lists "S-row match map" under "free checks" still to be done, not something already done.

**F.2 — source of the draft false-rejection count (4-5/88)**
- VERIFIED `docs/evals/dev_adjudication_run1.md:119-125,135`. Under heading "False-rejection check (Part B, draft)" (`:119`): 37 Prism PS/NS claims across 12 papers were text-matched (not via the dev_match_map.json adjudication) against the 88 dev S rows; one match (P5 #9 to P5-S3) was flagged weak ("tsr 64.5... still to confirm," `:124`) giving a range of 4-5/88 (4.5-5.7%) pending that confirmation. Later in the same file (`:135`), that weak match is resolved as "confirmed not a match," settling the number at 4/88 (4.5%) — but the heading itself is still literally labelled "draft," and `:133` lists an open ticket ("persist thinking setting, grounding model used, per-call cost; fix --dry-run") implying this pass wasn't treated as final/instrumented work. `docs/PRISM_STATUS.md:17` still quotes the "4-5/88... still marked 'draft'" range rather than the resolved 4/88, i.e. the status doc hasn't been updated to reflect the `:135` resolution.

---

## Contradictions (vs. decisions.md / PRISM_STATUS.md / the 2026-10-22 diagnostic)

1. **PRISM_STATUS.md:17 is stale relative to its own cited source.** It quotes "Draft false-rejection count: 4-5/88 S rows... still marked 'draft'," but `dev_adjudication_run1.md:135` (same file PRISM_STATUS cites) already resolved the ambiguous match and landed on 4/88 — the status doc did not pick up that resolution.
2. **The diagnostic's NEVER/EXCUSED/CAUGHT tags (Table 6) imply free-text analysis but are actually structured-field-only** (Check C.1) — not a contradiction of a stated claim, but worth flagging because the diagnostic's own prose ("evidence present every time via a 'Fail'-tagged span, consistently discounted") could be read as describing the auditor's reasoning narrative, when it is describing the structured `evidence_spans` grounding tag instead.
3. **P5-R1's "causal link... unconfirmed" framing (diagnostic:173) is contradicted by the free text itself** (Check C.3): the PS-labelled replay instances explicitly articulate the single-pair/coding-only scope limitation in prose, even though their structured `evidence_spans` happened to be byte-identical to a NEVER sample. The structured-only comparison that produced "unconfirmed" misses what the model actually reasoned.
4. **Caching/Batch API availability is undocumented.** Neither `decisions.md` nor the 2026-10-22 diagnostic mentions that the installed google-genai SDK (1.64.0) already exposes `client.caches`/`CachedContent` and `client.batches` — only the absence of `service_tier` (Flex) was checked and recorded. Not a contradiction of a false statement, but a gap: cost-reduction options were ruled out (Flex) without checking two others that exist in the same SDK version.

## Open questions (could not settle from static inspection)

- Which specific `exp1_{level}_{repeat}` arm each `logs/audit/replay-*.json` file belongs to — no field in the log schema or filename records thinking_level/repeat_index, and timestamp-block boundaries don't cleanly divide into 5 even groups of 18 (Check C.2).
- Whether `run1`'s own auditor free text is recoverable at all — its `extraction_run_id` is a DB row id with no corresponding entry among any `logs/audit/*.json` filename, and resolving it would require a live Postgres query (forbidden under this task's hard rules).
- Whether the P8-R1 vs. P8-R2 replay instances for paper arxiv-2610.12124v1 can be told apart by anything other than exact byte-for-byte claim-text comparison (both claims are near-identically worded and both cite Appendix A.6/95.8%) — stopped per the task's own instruction rather than guess.
- Whether the P7-R1 instance read is the exact same claim-wording variant the diagnostic's locator table describes (same section/evidence, but I could not confirm the word "trajectories" appears in that specific claim's own text).
