# Pre-merge review: eval/dev-baseline-run1 vs main

Context: file inventory already done (0 junk, 0 secrets, no large files). This covers the remaining 7 checks. Read-only; no git/code/LLM calls were run — findings come from parallel read-only explorations of the branch's current files, prepared git-data files in `scratch/`, and saved fixtures/diagnostics.

## 1. Product safety — flag-off parity

Changed files under the live pipeline: `Prism.PythonService/config.py`, `extraction/engine.py`, `extraction/prompt_loader.py`, `extraction/prompt_version.py`, plus new `extraction/merge.py`, `pass2.py`, `pass2_clean.py`, `windowing.py`, and new prompt files. **`main.py`/`api.py` do not appear in `scratch/branch_files.txt` — unchanged.**

Flags added, all default **off/unset**, each pinned by a test:

| Flag | Default | Location | Pinning test |
|---|---|---|---|
| `auditor_thinking_level` | `None` | `config.py:82` | `test_auditor_thinking_config.py:21-22,49-66` |
| `extractor_fewshot_fix` | `False` | `config.py:100` | implicit via hash test below |
| `extractor_fewshot_shapes` | `False` | `config.py:112` | `test_extractor_fewshot_shapes.py:48-50` |
| `extractor_second_pass` | `False` | `config.py:121` | `test_extractor_second_pass.py:32-34` (asserts hash `cb3272cce551`) |
| `pass2_thinking_level` | `None` | `config.py:130` | `test_extractor_second_pass.py:37-44` |
| `extractor_pass2_clean` | `False` | `config.py:152` | `test_extractor_pass2_clean.py:25-26,39-41` |

**Flag-off prompt hash confirmed: `cb3272cce551`** — asserted in `test_extractor_second_pass.py:33-34` and `test_extractor_pass2_clean.py:40-41`; `extraction/prompt_version.py:68-158` shows no flag-marker bytes are hashed when all flags are default.

Pass-2/clean code paths are properly gated behind `if settings.extractor_second_pass` / `extractor_pass2_clean` in `engine.py:518,539`.

**Flag-off visible changes found (none affect pipeline output, but are new unconditional surface):**
- `engine.py:106-132,273,345` — new `_extract_usage_and_finish_reason` helper runs on **every** LLM call regardless of flags, and `_write_structured_log` (`:135-164`) now always writes `usage`/`finish_reason` keys into per-call JSON log files. Return values are unaffected (confirmed by dedicated test `test_usage_capture.py:44-94`), but log file shape changes unconditionally — flag this for the record, not a blocker.
- `engine.py:212-271,380-430` — new `thinking_config` plumbing, tested byte-identical to prior behavior when unset (the default).

Could not fully rule out other unconditional edits in `prompt_loader.py`/`prompt_version.py` without main's copy to diff (stat shows +131/+113 lines, consistent with additive-only).

## 2. Tests and CI

- **Confirmed**: `.github/workflows/eval.yml:59` runs only `pytest eval/tests/`. No other workflow exists. `Prism.PythonService/tests/` (22 files, 18 added/changed on this branch) is never referenced in CI.
- **Smallest CI fix** (now applied, see repo diff): add one step after line 59 reusing the same job/env block:
  ```yaml
  - name: Run service unit tests
    run: uv run pytest tests/ -v
  ```
  No new job or matrix needed — same `uv sync --frozen` and dummy env vars (job-level `env:` and `defaults.run.working-directory`) already satisfy `config.py`'s required settings.
- **Env/network needs**: 12 of 18 new test files transitively import `config.settings` (via `extraction.engine`/`pass2`/`pass2_clean`) and need the dummy env vars already set in CI. 4 files need neither (`test_exp3_b4.py`, `test_pass2_merge.py`, `test_score_exp3.py`, `test_score_replay.py`), plus `test_windowing.py`. **None make real network calls**; `test_replay_clean_estimate.py` explicitly asserts no client is constructed under `--estimate`.

## 3. Known risks left in (not fixed, listed only)

- **pass2_clean "same" chain-drop** — `pass2_clean.py:269-270`: a candidate drops if *any* relation to a neighbour is `"same"`. Docstring (`:14-26`) explicitly acknowledges this is positional/order-dependent and relies on `merge.py` having already deduplicated pass-2 candidates — an accepted assumption, not a bug fix.
- **Unvalidated neighbour ids** — `pass2_clean.py:62-66,199,268-269`: the LLM's returned `neighbour_id` is used to drive the drop decision with no membership check against the ids actually offered in that batch. A hallucinated/mismatched id would silently drive a drop.
- **Positional answer mapping** — `prompt_loader.py:291-296` docstring states outright: the pass2-clean response schema "carries no id field of its own, so position is the only correspondence." Enacted via plain `zip(batch, results)` at `pass2_clean.py:267`. Length mismatches are guarded (`:249-264`, falls back to "keep all"), but a same-length reordered response would not be detected.
- **Thinking level not stored in fixture headers** — confirmed against a real fixture (`docs/evals/fixtures/dev/clean/clean_r1/arxiv-2610.10590v1_clean.json:2-13`): header has no `thinking`/`thinking_level` key, even though `replay_clean.py` threads `thinking_level`/`pass2_thinking_level` through every call.
- Other accepted-tradeoff comments found: `prompt_version.py:114` ("second-pass-only hash is intentionally unreachable"); `pass2_clean.py:33-37` (failed/mismatched batch keeps all items rather than dropping, paper marked incomplete); `pass2_clean.py:108-120` (`locate_context` returning `None` must never cause a drop). No bare TODO/FIXME/HACK found in `extraction/`/`eval/` on this branch, though the ~190K-line diff (mostly JSON fixtures/docs under `docs/evals/`) was not exhaustively scanned for prose caveats.

## 4. Decisions consistency

All four items have a dated pre-registration followed by a dated result — none missing either half:
- **Exp 1** (auditor thinking_level=high): pre-reg `decisions.md:1742-1776`, result `:1807-1828` — "**Verdict: FAIL. Experiment 1 rejected.**" (`:1810-1811`)
- **Exp 2** (few-shot claim-shape repair): pre-reg `:1833-1839`, result `:2000-2012` — "**Verdict: FAIL. Experiment 2 (redesigned) rejected.**" (`:2011-2012`)
- **Exp 3** (pass-2 windowed extraction): pre-reg `:2236-2323`, result `:2600-2605` — "**Verdict: REJECTED on c4**" (`:2603`)
- **Clean-extraction attempt**: pre-reg (final methodology) `:2976-3003`, result `:3005-3020` — "Decision: EXTRACTOR_PASS2_CLEAN stays off." (`:3018`)

**Contradiction check**: README.md and PRISM_STATUS.md numeric claims (golden/held-out, Exp1/Exp2 numbers) match decisions.md exactly — no direct numeric contradiction.

**Staleness flag (not a direct contradiction, but material)**: `PRISM_STATUS.md` is dated 2026-10-15 and describes Experiment 3 as still "in progress" (lines 33-38, 90-92), with no mention at all of Exp 3's actual rejection (2026-10-16) or the entire clean-extraction attempt (2026-10-16 to 2026-10-20, FAIL). Since PRISM_STATUS.md bills itself as "single source for new chats," this is stale and should be updated soon.

## 5. Scoreboard (quoted from decisions.md)

- Dev baseline 31 refusal rows: 8 caught, 10 auditor misses, 13 extraction misses. Not stated together in one decisions.md line — assembled from `:1750` ("reproduces run 1 at 8/31"), `:1762-1763` ("10 run-1 audit misses + 8 run-1 hits"), `:1828` ("13 extraction misses"). Stated together only in `PRISM_STATUS.md:27`. 8+10+13 = 31, consistent.
- Golden (last logged, `:1474-1476`, 2026-10-07): "refusal-family 5/16 (0.3125), strict 5/16, wrongly affirmed 4, not extracted 7, positive hits 11/21 (floor 10), false rejection 1/21, coverage 37/37."
- Held-out (last logged, `:1479`): "1/2, 7/10, 0/10, 12/12; baseline 1/2, 8/10, 0/10, 12/12... Held-out used 6 times."
- Exp 1 verdict (`:1810-1811`): "FAIL. Experiment 1 rejected. AUDITOR_THINKING_LEVEL stays unset."
- Exp 2 verdict (`:2011-2012`): "FAIL. Experiment 2 (redesigned) rejected."
- Exp 3 verdict (`:2603`): "REJECTED on c4... EXTRACTOR_SECOND_PASS stays default off."
- Clean attempt verdict (`:3018`): "EXTRACTOR_PASS2_CLEAN stays off. Code kept behind the flag."

## 6. Per-row table — 31 dev refusal-family rows

Built entirely from saved files (`dev_eval.json`, `dev_match_map.json`, dev run-1 fixtures, `score_replay.resolve_adjudicated_rows` logic read but not executed, `diag_k1_stages.run_diagnostic` logic read but not executed, plus saved reports `docs/evals/clean_labels/k1_stage_diagnostic.md` and `k1_prompt_comparison.md`). Totals matched 8/10/13 exactly with no forcing.

| row id | paper | shape | dev label | pass‑1 found | auditor | pass‑2 OLD r1/r2 | pass‑2 NEW r1/r2 | auditor on pass‑2 |
|---|---|---|---|---|---|---|---|---|
| P1-R1 | RA | - | PS | Yes | missed | - | - | not run |
| P1-R2 | RA | E1 | PS | No | - | not found/not found | not found/not found | not run |
| P1-R3 | RA | - | PS | Yes | caught | - | - | not run |
| P2-R1 | SFT-as-Context | E1 | NS | No | - | not found/found | not found/not found | not run |
| P2-R3 | SFT-as-Context | E2 | PS | No | - | not found/not found | not found/found | not run |
| P2-R4 | SFT-as-Context | E2 | PS | No | - | found/found | found/found | not run |
| P2-R5 | SFT-as-Context | - | PS | Yes | caught | - | - | not run |
| P3-R1 | JevKT | E3 | PS | No | - | found/found | found/found | not run |
| P3-R2 | JevKT | - | PS | Yes | missed | - | - | not run |
| P4-R1 | MASA | - | PS | Yes | missed | - | - | not run |
| P4-R2 | MASA | - | PS | Yes | missed | - | - | not run |
| P4-R3 | MASA | E3 | PS | No | - | not found/not found | found/found | not run |
| P5-R1 | Semi-OPD | - | PS | Yes | missed | - | - | not run |
| P5-R2 | Semi-OPD | - | PS | Yes | missed | - | - | not run |
| P5-R3 | Semi-OPD | E3 | PS | No | - | not found/not found | not found/not found | not run |
| P6-R1 | MedBenchAgent | - | PS | Yes | caught | - | - | not run |
| P6-R2 | MedBenchAgent | - | PS | Yes | missed | - | - | not run |
| P7-R1 | Agent-Controlled Forgetting | - | PS | Yes | missed | - | - | not run |
| P7-R2 | Agent-Controlled Forgetting | E1 | PS | No | - | found/not found | not found/not found | not run |
| P8-R1 | Hippocam | - | PS | Yes | caught | - | - | not run |
| P8-R2 | Hippocam | - | PS | Yes | missed | - | - | not run |
| P8-R3 | Hippocam | E3 | PS | No | - | found/found | found/found | not run |
| P9-R1 | OnTrack | E2 | PS | No | - | found/found | found/found | not run |
| P10-R1 | MASS | - | PS | Yes | caught | - | - | not run |
| P10-R2 | MASS | - | PS | Yes | caught | - | - | not run |
| P10-R3 | MASS | - | PS | Yes | caught | - | - | not run |
| P11-R1 | UTT | E4 | PS | No | - | not found/not found | not found/not found | not run |
| P11-R2 | UTT | - | PS | Yes | missed | - | - | not run |
| P11-R3 | UTT | E5 | NS | No | - | found/found | not found/not found | not run |
| P12-R1 | Hindsight Hierarchies | E1 | NS | No | - | not found/not found | not found/not found | not run |
| P12-R2 | Hindsight Hierarchies | - | NS | Yes | caught | - | - | not run |

Totals: 13 extraction misses, 8 caught, 10 missed (8+10+13=31) — matches target exactly.

## 7. Merge verdict

**MERGE AS IS.**

Reasons:
- All new behavior-changing flags default off and are each pinned by a dedicated test against the known flag-off prompt hash `cb3272cce551`; `main.py`/`api.py` are untouched; the only flag-off-visible change is additive logging fields (usage/finish_reason) with no effect on return values — acceptable.
- Every experiment this branch represents (Exp1, Exp2, Exp3, clean-extraction attempt) followed proper pre-registration → result discipline and all were correctly rejected, with their code kept behind off-by-default flags rather than ripped out — exactly the intended "fail safely, keep the artifact" pattern.
- Scoreboard and per-row table reconcile exactly to the stated 8/10/13 split with no forcing.
- No numeric contradictions between decisions.md and README/PRISM_STATUS.

Non-blocking fixes to do soon after merge (do not block this merge):
1. Update `docs/PRISM_STATUS.md` — it is stale since 2026-10-15 and omits the Exp 3 rejection and the entire clean-extraction attempt; misleading as a "single source for new chats."
2. `Prism.PythonService/tests/` wired into CI (done as part of this review — see `.github/workflows/eval.yml` diff below).
3. Consider recording `thinking_level`/`pass2_thinking_level` in clean/pass-2 fixture headers for future reproducibility, since these flags measurably affect output.
4. The three known risks in section 3 (same-chain drop, unvalidated neighbour ids, positional answer mapping) are all inside code gated off by default (`extractor_pass2_clean`/`extractor_second_pass`), so they carry no live-pipeline risk today — but should be fixed before either flag is ever turned on for real traffic.
