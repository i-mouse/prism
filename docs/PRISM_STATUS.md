# PRISM STATUS — 2026-10-22 (single source for new chats)

## Current state

Prism runs locally only (Aspire). The Azure demo was decommissioned 2026-09-28; cancellation not yet confirmed complete (decisions.md:38-42). PR #122 (dev eval baseline + extraction experiments, all flags off, + eval tooling) merged to main 2026-10-21 (git log, commit 4be1cc4). All new flags default off; the shipping extraction path is pass 1 only. Not released: the dev refusal rate (26%, single run) is well below the 70% release floor. Four experiments aimed at closing the gap have been tried and rejected. Auditor phase: diagnosis done 2026-10-22 (INR 0) - root cause is a missing full-scope check, not PDF reading; design not started (decisions.md, 'Auditor phase diagnostic (INR 0) - 2026-10-22').

## Scoreboard

**Golden (3 papers, 16 refusal rows / 37 total, de-leaked prompts, 2026-10-07):**
Refusal-family 5/16 (31%), gate 0.30 (passes by one row); strict 5/16; wrongly affirmed 4; not extracted 7; positive hits 11/21 (floor 10); false rejection 1/21; coverage 37/37. (decisions.md:1474-1479)

**Held-out (arXiv 2609.20812v3, 2 refusal rows — small sample, used 6 times, near-burnt, 2026-10-07):**
Refusal-family 1/2, positive hits 7/10, false rejection 0/10, coverage 12/12. (decisions.md:1479)

**Dev baseline (119 rows / 12 papers, 31 refusal-family rows, single run, 2026-10-12):**
Refusal 8/31 (26%). Of the 23 misses: 10 audit misses (claim extracted, wrongly judged supported), 13 extraction misses. Auditor-only ceiling 18/31 (below 22/31 floor); extraction-only ceiling 21/31 (68%, also below floor) — neither stage alone reaches the 70% release floor. (decisions.md:1750, 1828, 2115, 2212-2213)
Draft false-rejection count: 4-5/88 S rows (4.5-5.7%), one caused by grounding — still marked "draft," not a final adjudicated number. (docs/evals/dev_adjudication_run1.md:125, 135)

**Release bar:** dev refusal >= 70% (mean of 3 runs), stretch 80%, false-rejection hard cap 10% (aim 0%). Release number comes from one sealed-set run only; dev/golden numbers are never quoted as the release number. (decisions.md:1636-1640)

## Flags and their defaults

New flags from the eval-baseline branch (all default off/unset, each pinned by a test; flag-off prompt hash confirmed `cb3272cce551`):

| Flag | Default | Source |
|---|---|---|
| `auditor_thinking_level` | `None` | `config.py:82` |
| `extractor_fewshot_fix` | `False` | `config.py:100` |
| `extractor_fewshot_shapes` | `False` | `config.py:112` |
| `extractor_second_pass` | `False` | `config.py:121` |
| `pass2_thinking_level` | `None` | `config.py:130` |
| `extractor_pass2_clean` | `False` | `config.py:152` |

(`docs/premerge_review_2026-10-20.md` section 1, lines 9-18.)

Existing flags (pre-date this branch):

| Flag | Default | Note |
|---|---|---|
| `GROUNDING_NORMALIZE` | on | Stage-1 text normalisation, merged 2026-10-05 (docs/FINDINGS.md:72) |
| `AUDIT_MODE` | legacy | The scoped auditor was a separate pilot (Exp 1 scoped-auditor, not decisions.md's "Experiment 1"), archived on tag `archive/exp1-scoped-auditor`, never merged (docs/FINDINGS.md:27) |

## Experiments and verdicts

| Experiment | Change | Verdict | Spend |
|---|---|---|---|
| 1 | Auditor `thinking_level=high` | REJECTED — fixed 1/10 rows (needed >=3); auditor noise ~±3 rows run-to-run at default | INR 411.95 (decisions.md:1807-1831) |
| 2 | Extractor few-shot claim-shape repair | REJECTED — all 4 required marks failed; evidence leans toward a task-design problem, not proven | INR 177.93 (decisions.md, "Experiment 2 - Stage A result - 2026-10-14") |
| 3 | Windowed pass-2 re-extraction (`extractor_second_pass`) | REJECTED on cost gate c4: projected INR 237.59/paper (pooled) / 243.75 (mean) vs INR 130 cap. c7, c2 passed. c1/c6/c8 not measured (human labelling deviation) | INR 185.79 (Exp-3-specific, meter) (decisions.md:2600-2606) |
| Clean-extraction attempt | Claim-cleaning filter on top of Exp 3 (`extractor_pass2_clean`) | REJECTED — K1 (recall) FAIL 5-6/13; K4 (cost) FAIL ~INR 230/paper vs 130 cap; K7 (dedup safety) FAIL; K8 FAIL on the filter sub-cap (INR 64.25 / 58.31 vs 40). K2, K5, K6 PASS | INR 311.04 of a separate INR 350 cap (decisions.md:3005-3018, 2621) |

Exploratory-only note: Experiment 3's c1/c6 recall result (8/13 both runs) was AI-proposed, human-verified — not the pre-registered blind adjudication — so no recall claim is made for Experiment 3 itself. (decisions.md:2607-2616)

## Extraction findings (2026-10-20)

- All 8 lost target rows were lost at the pass-2 output stage in both clean runs — zero merge or filter drops (pre-filter = final). The filter did not cause the K1 shortfall.
- Old vs new pass-2 prompt, same fuzzy matching method: old 6/13 and 6/13, new 5/13 and 6/13 — no clear recall loss from the new prompt.
- Pass 2 recovers about 5-6 of the 13 target rows, but those recovered claims were never audited end to end — their value is unmeasured.
- Both clean runs used pass-2 thinking LOW, consistent with Experiment 3.
- The K7 filter fix (drop as "same" only if the candidate adds no new number/content word; never resolve "same" against a dropped neighbour; validate neighbour ids; add an id to each filter answer) is parked, design kept, to revisit with a pass-2 redesign.

(decisions.md, "K1 diagnostics and filter status (exploratory) - 2026-10-20", lines 3026-3045.)

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

## Known risks (code-sourced, `docs/premerge_review_2026-10-20.md` section 3)

All three risks below are inside code currently gated off by default (`extractor_pass2_clean` / `extractor_second_pass`), so they carry no live-pipeline risk today — but should be fixed before either flag is turned on for real traffic.

- **"Same"-relation chain-drop** — `pass2_clean.py:269-270`: a candidate drops if *any* relation to a neighbour is `"same"`. The docstring (`pass2_clean.py:14-26`) explicitly acknowledges this is positional/order-dependent and relies on `merge.py` having already deduplicated pass-2 candidates — an accepted assumption, not a bug fix.
- **Unvalidated neighbour ids** — `pass2_clean.py:62-66,199,268-269`: the LLM's returned `neighbour_id` drives the drop decision with no membership check against the ids actually offered in that batch. A hallucinated/mismatched id would silently drive a drop.
- **Positional answer mapping** — `prompt_loader.py:291-296`: the pass2-clean response schema carries no id field of its own, so position is the only correspondence, enacted via plain `zip(batch, results)` at `pass2_clean.py:267`. Length mismatches are guarded (`pass2_clean.py:249-264`, falls back to "keep all"), but a same-length reordered response would not be detected.
- **Thinking level not stored in fixture headers** — confirmed against a real fixture (`docs/evals/fixtures/dev/clean/clean_r1/arxiv-2610.10590v1_clean.json:2-13`): header has no `thinking`/`thinking_level` key, even though `replay_clean.py` threads `thinking_level`/`pass2_thinking_level` through every call. (decisions.md:3037)

## Budget status

- Push cap for Experiments 1-3: INR 1,150, set 2026-10-12 (decisions.md:1753).
- Spent: Exp 1 INR 411.95; Exp 2 INR 177.93; Exp 3 INR 185.79 (decisions.md:1807-1831, "Experiment 2 - Stage A result", 2529-2605).
- Clean-extraction attempt: separate cap INR 350, spent INR 311.04 (decisions.md:2621, 3017).
- Sealed reserve: INR 300, untouched throughout (decisions.md:1825).
- The 2026-10-10 hard-exit rule (8 counted experiments or push cap, then one sealed run) was superseded 2026-10-16: Nitin chose to keep improving the core product (extractor, then auditor) before taking the exit decision (decisions.md:2618-2619).
- Gemini project monthly cap: INR 3,232 of 3,600 used as of 2026-10-21 (AI Studio dashboard, per Nitin); resets 1 Nov (PST). Paid runs wait for the reset or a logged cap change.

## Open items

- REFLEX-M13: claim/notes mismatch (decisions.md:1561).
- REFLEX-M09: flagged unsure (decisions.md:1561).
- COT-M08: pairing doubtful, automatic carry-over not hand-adjudicated (decisions.md:1607).
- COT-M01: false rejection may already be fixed by Stage-1 normalisation — UNVERIFIED, frozen fixtures predate it (decisions.md:1543).
- PR-1 draft #115 (few-shot loader fix): still unmerged as of its last logged status (decisions.md:2065); duplicates logic now shipped behind `extractor_fewshot_fix`, default off.
- Restate the release bar ('mean of 3 runs' is stale)
- Full-pipeline token usage is not logged in production
- Grounding and eval matcher send temperature=0 (Google advises 1.0 for Gemini 3) - parked
- dev_eval.json scoring-note wording: P5-R2 row letters, P6-R2 Figure 3 count - labels unchanged

## Working rules

- Never tune prompts to move the number.
- Held-out text never goes in chat or committed notes; counts only.
- Never merge past red CI; never lower a threshold to pass.
- CC never runs git; use `uv run python` from `Prism.PythonService`.
- Every experiment needs pre-registered marks and a rupee cap, written before any paid call.

(decisions.md, repeated across entries, e.g. 1636-1665.)

## Links

Decisions log: `docs/decisions.md`. Code review: `docs/premerge_review_2026-10-20.md`. Dev adjudication: `docs/evals/dev_adjudication_run1.md`. Clean-extraction scoring: `docs/evals/clean_labels/clean_attempt_score.md`.
