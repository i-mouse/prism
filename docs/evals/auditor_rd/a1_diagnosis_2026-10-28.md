# A1 diagnosis (read-only, INR 0) - 2026-10-28
Source: Claude Code, plan mode, no LLM calls. Text recovered from the Claude Code session log by Antigravity (not pasted by hand); key figures checked against decisions.md.
Reading rule: decisions.md "A1 diagnosis plan and reading rule - 2026-10-28"
(tag before-A1-diagnosis).
Decision: Ship-honest (decisions.md option B).
Note: the report below is as recovered from the log. Where it says "option B", read
"Ship-honest (decisions.md option B)".

---

**A1 diagnosis (read-only): 30 cells coded, Phase 1 reproduced exactly**

I stayed in plan mode and wrote no plan file and called no ExitPlanMode, as you instructed. The diagnosis is in this reply only.

- **Stray file:** a mistyped command of mine created an empty file at `/tmp/_x`, outside the repo. I left it there. It's the only file this task touched.
- **Handoff file missing:** `claude/handoff_2026-10-28.md` was not found anywhere under `H:\Work projects`, so I worked from `decisions.md` and the 10-22 docs only.
- **Not applied:** no verdict, no reading rule, no fixes.

## Phase 1: mapping and reconciliation (passed)

- **Mapping:** I mapped all 54 `logs/scope_list` and 44 `logs/scope_check` files by order within each paper plus exact item-text equality with the trace. Repeats were 18 lister logs each, windows 08:38–08:48, 08:49–08:59 and 09:00–09:10.
  - There are no probe logs in these folders; every file is dated 2026-10-28.
  - Nothing needed guessing. The checker echoes `[kind]` and `N.` prefixes on item text; I stripped these and every item text matched.
  - Statuses in the traces equal statuses in the logs for all 44 checker calls.
- **Counts:** I recomputed every count from the traces.

| Repeat | claims_with_items | contradicted | guard_failed | lowered |
|---|---|---|---|---|
| r1 | 14 | 9 | 0 | 6 |
| r2 | 15 | 5 | 0 | 3 |
| r3 | 15 | 4 | 2 | 2 |

- **Per-row scope results:** P4-R1 3/3, P7-R1 3/3, P1-R1 2/3, P3-R2 1/3, P5-R2 1/3 and P4-R2, P6-R2, P11-R2 0/3. These match what you gave me, and `score_a1` printed the same marks.
- **One claim, two rows:** claim `11291#1` is matched to both P5-R2 and S-row P5-S1.

## Table A: 30 cells

- **Item hit** is Y when a lister item covers the pinned breaking element. **Reported** is Y when `reported[]` contains the breaking value.
- **OK†** means the claim was lowered, but on evidence other than the pinned breaking evidence.
- **R(sum)** means `reported[]` held only prose or caption sentences, and none of the breaking table row.
- **Evidence path:** `S<n>` is `scratch/a1_output_2026-10-28/exp1_medium_scope_<n>/<paper>.json`, then `claims[index=…].scope_items[k]`. `chk` is the `logs/scope_check/20261028T<id>_replay-<paper>_none.json` timestamp.

| Row | Rep | Auditor | Final | Item hit | Reported | Status | Guard | Code | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| P3-R2 | r1 | S | PS | N | N | contradicted (item1) | T, 194 chars | OK† | S1 11135#3 item1; chk 084053187251 |
| P3-R2 | r2 | S | S | N | N | matches (item3) | – | L1 | S2 11135#3; no "first interactions" item; chk 085144902746 |
| P3-R2 | r3 | S | S | Y | Y | contradicted (item2) | **F**, 52 chars | G | S3 11135#3 item2; chk 090315263674 |
| P5-R2 | r1 | S | PS | Y | N | contradicted (item1) | T, 162 chars | OK† | S1 11291#1 item1; chk 084200895912 |
| P5-R2 | r2 | S | S | Y | N | matches (item2) | – | R(sum) | S2 11291#1; chk 085251725152 |
| P5-R2 | r3 | S | S | Y | N | matches (item2) | – | R(sum) | S3 11291#1; chk 090424473341 |
| P4-R2 | r1 | S | S | Y | N | matches (item1, item2) | – | R(sum) | S1 10871#30; chk 083930243415 |
| P4-R2 | r2 | S | S | Y | N | matches | – | R(sum) | chk 085019975772 |
| P4-R2 | r3 | S | S | Y | N | matches | – | R(sum) | chk 090143934378 |
| P6-R2 | r1 | S | S | Y | N | matches (item1) | – | R(sum) | S1 11312#3; chk 084307043132 |
| P6-R2 | r2 | S | S | Y | N | matches | – | R(sum) | chk 085404836341 |
| P6-R2 | r3 | S | S | Y | N | matches | – | R(sum) | chk 090538168455 |
| P11-R2 | r1 | S | S | Y | **Y** | matches (item1, item4) | – | S1 | S1 12114#7; chk 084505497315 |
| P11-R2 | r2 | S | S | Y | **Y** | matches (item1) | – | S1 | chk 085606642981 |
| P11-R2 | r3 | S | S | Y | N | matches (items 1, 2) | – | R | caption appears only under item3 (pair); chk 090745668041 |
| P4-R1 | r1 | S | PS | Y | Y | contradicted (item4) | T, 111 chars | OK | S1 10871#2; chk 083906263072 |
| P4-R1 | r2 | S | PS | Y | Y | contradicted (item4) | T, 70 chars | OK | chk 084949396794 |
| P4-R1 | r3 | S | PS | Y | N (captions only) | contradicted (item4) | T, 703 chars | OK† | chk 090108574751 |
| P1-R1 | r1 | S | PS | Y | Y | contradicted (item1) | T, 106 chars | OK | S1 11519#32; chk 084354961107 |
| P1-R1 | r2 | S | PS | Y | Y | contradicted (item2) | T, 106 chars | OK | chk 085451297491 |
| P1-R1 | r3 | S | S | Y | N | matches (items 1, 2) | – | R | chk 090629488714 |
| P5-R1 | r1 | PS | PS | Y | Y | contradicted (item2) | T, 120 chars | A | S1 11291#33; chk 084129092664 |
| P5-R1 | r2 | S | S | Y (tasks) | N | matches | – | R | chk 085217661144 |
| P5-R1 | r3 | PS | PS | Y | N | matches | – | A | chk 090350832165 |
| P7-R1 | r1 | S | PS | Y | Y | contradicted | T, 182 chars | OK | S1 10590#5; chk 083830663677 |
| P7-R1 | r2 | S | PS | Y | Y | contradicted | T, 182 chars | OK | chk 084911172233 |
| P7-R1 | r3 | S | PS | Y | Y | contradicted | T, 182 chars | OK | chk 090027346695 |
| P8-R2 | r1 | S | S | N | N | matches (item1, wrong element) | – | L1 | S1 12124#7; chk 084606777024 |
| P8-R2 | r2 | PS | PS | N | – | matches | – | A | chk 085708562548 |
| P8-R2 | r3 | PS | PS | N | – | none (lister returned 0 items) | – | A | lister 090845215409 |

The OK† cells are:
- **P3-R2 r1:** the quote is the ".713 … best deep KT … ahead (.729; JevKT is better on 1/7 datasets; Table 10)" sentence. The lister item misread the claim, which says deep KT *remains ahead* on unseen items. It is not the Table 9 position-1 cell.
- **P5-R2 r1:** the quote is the paper's own "Across 17 … in 14 cases" sentence. It is read as "14 of 17, not all", not the SFT double count.
- **P4-R1 r3:** the quote is the Table 2 caption (703 chars). `reported[]` held only the Table 1 and Table 2 captions.

## Table B: codes per row

| Row | r1 / r2 / r3 | Dominant | Stable across repeats |
|---|---|---|---|
| P3-R2 | OK† / L1 / G | none | N |
| P5-R2 | OK† / R / R | R | N |
| P4-R2 | R / R / R | R | Y |
| P6-R2 | R / R / R | R | Y |
| P11-R2 | S1 / S1 / R | S1 | N |
| P4-R1 | OK / OK / OK† | OK | Y |
| P7-R1 | OK / OK / OK | OK | Y |
| P1-R1 | OK / OK / R | OK | N |
| P5-R1 | A / R / A | A | N |
| P8-R2 | L1 / A / A | A | N |

## Table C: code counts

Cell counts first, then the number of rows having that code in at least 2 of 3 repeats.

| Code | (i) 5 unfixed: cells | rows ≥2/3 | (ii) all 10: cells | rows ≥2/3 |
|---|---|---|---|---|
| OK | 2 | 0 | 10 | 3 (P4-R1, P7-R1, P1-R1) |
| A | 0 | 0 | 4 | 2 (P5-R1, P8-R2) |
| L1 | 1 | 0 | 2 | 0 |
| L2 | 0 | 0 | 0 | 0 |
| R | 9 | 3 (P5-R2, P4-R2, P6-R2) | 11 | 3 (same three) |
| S1 | 2 | 1 (P11-R2) | 2 | 1 |
| S2, S3, X | 0 | 0 | 0 | 0 |
| G | 1 | 0 | 1 | 0 |
| Total | 15 | | 30 | |

S3 never appears as a code. By the first-break rule that behaviour lands in R, because `reported[]` never reached the table rows.

## Table D: lister then vs now

| Row | 10-22 item | A1 r1 | A1 r2 | A1 r3 |
|---|---|---|---|---|
| P1-R1 | Y | Y (one merged item) | Y | Y |
| P3-R2 | Y | N | N | Y |
| P4-R1 | Y | Y | Y | Y |
| P4-R2 | Y | Y (names the models) | Y | Y |
| P5-R1 | Partly | Y (tasks, not pairs) | Y | Y |
| P5-R2 | Y | Y | Y | Y |
| P6-R2 | Y | Y | Y | Y |
| P7-R1 | N | Y ("trajectories") | Y | Y |
| P8-R2 | N | N | N | N (no items) |
| P11-R2 | Y | Y | Y | Y |

## Table E: instability buckets

**Contradicted items reconcile to lowered claims**

| Repeat | Contradicted = | Lowered | Auditor already PS | Guard-failed on an S claim |
|---|---|---|---|---|
| r1 | 9 | 6 | 3 (P2-R5, P5-R1, P10-R2) | 0 |
| r2 | 5 | 3 | 2 (P2-R5, P10-R3) | 0 |
| r3 | 4 | 2 | 1 (P2-R5, which also failed its guard) | 1 (P3-R2) |

**Why lowered went 6 → 3 → 2**

| Bucket | Claims | Change |
|---|---|---|
| Checker status flip on an equivalent item | P3-R2 (r1→r2): same reported sentences, status changed. P5-R2 (r1→r2): lister wording drifted, status changed. P1-R1 (r2→r3): `reported[]` lost the Table 4 sentence. | −3 |
| Auditor label variance | P10-R3: auditor S in r1, PS in r2 and r3, so r1's lowering vanished | −1 |
| Guard | P3-R2 r3: contradicted but guard failed. Both guard failures in r3 are P2-R5 and P3-R2. | blocks 1 |
| Lister variance as primary cause | none (item counts for one claim still vary, for example P4-R1 5/9/8) | 0 |
| Several contradicted items on one claim | none | 0 |

The three flips are not all equal: P3-R2 is a pure checker flip, P5-R2 had lister wording drift on an equivalent item, and P1-R1 changed `reported[]` content.

## Table F: lowered claims

| Repeat | Claim | Eval row | Type |
|---|---|---|---|
| r1 | 10590#5 | P7-R1 | refusal |
| r1 | 10871#2 | P4-R1 | refusal |
| r1 | 11135#3 | P3-R2 | refusal |
| r1 | 11291#1 | P5-R2 and P5-S1 | refusal and S |
| r1 | 11519#32 | P1-R1 | refusal |
| r1 | 12176#16 | P10-R3 | refusal (real-hit row) |
| r2 | 10590#5, 10871#2, 11519#32 | P7-R1, P4-R1, P1-R1 | refusal |
| r3 | 10590#5, 10871#2 | P7-R1, P4-R1 | refusal |

No lowered claim is unmatched. The only S-row touch is P5-S1, in r1, on the claim shared with P5-R2.

## Not determinable

- **P3-R2 r3 guard failure:** the cause is inferred. The quote is 52 characters, so it's long enough, which leaves a fuzzy-match failure. It is a reformatted row joined with " | ". Confirming it needs the raw paper text, which is off-limits.
- **P3-R2 r1 and P5-R2 r1 (OK†):** whether their off-target evidence is a legitimate contradiction of the claim needs a paper read.
- **P4-R1 r3 (OK†):** `reported[]` holds captions only, so I can't tell from the logs what the checker looked at when it contradicted.
- **P11-R2 r1 and r2:** the checker's reasoning for "matches" is not logged. The logs hold only the `reported[]` and status fields.
- **No cell was coded X.**

## Findings

1. **Unfixed rows, mostly a reading failure.** Of the 15 cells for the five unfixed rows, the lister had an item naming the breaking element in 13. The break came later: 9 are R (reading), 2 are S1, 1 is L1, 1 is G. The 2 OK cells were lowered on different evidence than the pinned breaking evidence.
2. **R cells quote summaries, not table rows.** In all 9 unfixed-row R cells, plus the 2 other R cells where the value was missing, `reported[]` held prose or caption sentences. In P4-R2 r1 item 2 it held rows from a different table. In P4-R1 r2 the checker did quote full table rows, so quoting rows is possible.
3. **S1 is one row.** P11-R2 r1 and r2 quoted the "under the Pro→Qwen setting" caption and still returned matches. In r3 the caption surfaced only under the pair item, not the "evaluated settings" item.
4. **Instability is mainly the checker.** The lowered drop comes from three checker flips, one auditor label change and one guard block. The lister never failed.
5. **Three of the ten OK cells lowered on weak evidence.** P3-R2 r1, P5-R2 r1 and P4-R1 r3 are OK† (off-target quote, or caption-only quote). P4-R1, P7-R1 and P1-R1 are otherwise lowered on targeted evidence. P6-R1, which the scorer lists as "lost", had zero scope items and auditor S in all three repeats.
