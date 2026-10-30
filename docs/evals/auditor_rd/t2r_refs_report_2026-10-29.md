# T2-R reference tables - build report (2026-10-29)

INR 0. No LLM, no network. Run state: **OK**


## Tables

| paper | table | identified | PDF caption start (<=80) | rows x cols | header rows | multirow/multicolumn | unknown macros | flags | parse problems | pins cell x/y (certain) | structural x/y | uncertain x/y | relaxed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2610.10590v1 | 1 | n (latex-none) | OpenTelemetry, both phases unless specified. Metric | - | - | - | - | - | - | - | - | - | - |
| 2610.10871v1 | 1 | y | RULER (Hsieh et al., 2024) results under matched sparse-attention settings. With | 13x11 | 1 | 5/0 | - | - | - | 7/7 | 0/0 | 8/8 | 1 |
| 2610.10871v1 | 2 | y | InfiniteBench (Zhang et al., 2024) results under matched sparse-attention settin | 10x15 | 1 | 4/0 | - | - | - | 2/2 | 0/0 | 1/1 | 0 |
| 2610.10871v1 | 3 | y | LongBench (Bai et al., 2024b) results under matched sparse-attention settings. | 4x6 | 1 | 0/0 | - | - | - | - | - | - | - |
| 2610.10871v1 | 9 | y | Full RULER probe ablation. Clip p denotes norm clipping at percentile p, and Nor | 13x10 | 1 | 0/0 | - | - | - | 11/11 | 2/2 | 0/0 | 13 |
| 2610.11132v1 | 1 | y | SFT-as-context successfully mitigates the forgetting of general capabilities and | 27x6 | 1 | 0/9 | - | - | - | - | - | - | - |
| 2610.11135v1 | 1 | y | Cold-start AUC (P1) of Jev against the best deep KT and the best LLM-based KT ba | 26x11 | 1 | 8/0 | - | - | - | - | - | - | - |
| 2610.11135v1 | 9 | y | P2 (new learners), every cell. AUC by the position of the target in a new learne | 25x9 | 1 | 0/6 | - | - | - | 3/3 | 0/0 | 10/10 | 0 |
| 2610.11291v1 | 3 | y | All 17 teacher–student pairs, sorted by AUC gain of Semi-OPD over OPD. Model nam | 19x8 | 2 | 0/1 | - | - | - | 0/0 | 6/6 | 0/0 | 0 |
| 2610.11312v1 | 1a | y | Task-space construction and evidence-mapping results. Task-Space Precision (P),  | 7x8 | 2 | 1/2 | - | - | - | - | - | - | - |
| 2610.11312v1 | 1b | y | Task-space construction and evidence-mapping results. Task-Space Precision (P),  | 6x4 | 1 | 0/0 | - | - | - | - | - | - | - |
| 2610.11312v1 | 10 | y | Evaluation performance on ISIC 2018. Choice tasks report Accuracy / Macro-F1 (%) | 15x8 | 2 | 3/3 | - | - | - | 1/1 | 4/4 | 0/0 | 0 |
| 2610.11519v1 | 1 | n (pdf-ambiguous) | Residual guidance improves both RLVR estimators on every benchmark and metric, | - | - | - | - | - | - | - | - | - | - |
| 2610.11519v1 | 2 | y | Every residual variant improves on verifier-only training at every tested weight | 8x7 | 2 | 1/4 | - | - | - | - | - | - | - |
| 2610.11519v1 | 4 | y | The same teacher-peak branch slightly helps sampled OPD but lowers both students | 5x8 | 3 | 0/9 | - | - | - | 1/1 | 0/0 | 2/2 | 3 |
| 2610.11519v1 | 10 | y | Macro differences among runs. Differences of three-seed macro means from Tables  | 18x4 | 1 | 0/0 | - | - | - | - | - | - | - |
| 2610.12114v1 | 3 | y | Comparison with KD methods under the Pro→Qwen setting. | 8x4 | 2 | 1/1 | - | - | - | 6/6 | 2/2 | 0/0 | 1 |
| 2610.12114v1 | 5 | n (latex-ambiguous) | Primer effectiveness and cross-model transferability on Vision Dominant plane ge | - | - | - | - | - | - | - | - | - | - |
| 2610.12124v1 | 2 | y | Cross-domain knowledge generalization and integration. ScienceWorld mean progres | 10x7 | 2 | 0/3 | - | drawing removed | - | - | - | - | - |
| 2610.12375v1 | 6 | y | Abort threshold sweep on severe flag density (n=150 per class, balanced). Precis | 5x5 | 1 | 0/0 | - | - | - | - | - | - | - |

## Pin check (gate tables)

### 2610.11519v1 Table 4

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P1-T4-01 | cell | breaking | relaxed | +0.30 | - |
| P1-T4-02 | cell | uncertain | relaxed | -0.38 | - |
| P1-T4-03 | cell | uncertain | relaxed | +0.64 | - |

Pins that needed the relaxed label compare:

- P1-T4-01: labels ['∆macro Avg@8', 'Sampled OPD', 'no weight']; strict: row key path not found or ambiguous
- P1-T4-02: labels ['∆macro Avg@8', 'REINFORCE++', 'λ=5']; strict: row key path not found or ambiguous
- P1-T4-03: labels ['∆macro Pass@8', 'Sampled OPD', 'no weight']; strict: row key path not found or ambiguous

### 2610.11135v1 Table 9

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P3-T9-01 | cell | breaking | strict | .709±.059 | - |
| P3-T9-02 | cell | breaking | strict | .749±.049 | - |
| P3-T9-03 | cell | - | strict | .689±.103 | - |
| P3-T9-04 | cell | uncertain | strict | .644±.047 | - |
| P3-T9-05 | cell | uncertain | strict | .512±.057 | - |
| P3-T9-06 | cell | uncertain | strict | – | - |
| P3-T9-07 | cell | uncertain | strict | .799±.022 | - |
| P3-T9-08 | cell | uncertain | strict | .517±.024 | - |
| P3-T9-09 | cell | uncertain | strict | .660±.066 | - |
| P3-T9-10 | cell | uncertain | strict | .640 | - |
| P3-T9-11 | cell | uncertain | strict | .558±.056 | - |
| P3-T9-12 | cell | uncertain | strict | .542±.049 | - |
| P3-T9-13 | cell | uncertain | resolved | .605 | - |

Pins resolved from the PDF page (pins file unchanged):

- P3-T9-13: pinned .607, page .605 -> got .605; diagnostic column attributed by position (key_uncertain); Nitin, direct PDF page read, 2026-10-30

### 2610.10871v1 Table 1

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P4-T1-01 | cell | breaking | strict | 81.57 | - |
| P4-T1-02 | cell | - | strict | 97.93 | - |
| P4-T1-03 | cell | - | strict | 91.29 | - |
| P4-T1-04 | cell | - | strict | 88.50 | - |
| P4-T1-05 | cell | - | strict | 85.45 | - |
| P4-T1-06 | cell | - | strict | 78.88 | - |
| P4-T1-07 | cell | - | strict | 87.27 | - |
| P4-T1-08 | cell | uncertain | relaxed | +2.87 | - |
| P4-T1-09 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,3) | - |
| P4-T1-10 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,4) | - |
| P4-T1-11 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,5) | - |
| P4-T1-12 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,6) | - |
| P4-T1-13 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,7) | - |
| P4-T1-14 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,8) | - |
| P4-T1-15 | cell | uncertain | ambiguous-consistent | 4 rows x 1 cols candidate; value present in (2,9) | - |

Pins that needed the relaxed label compare:

- P4-T1-08: labels ['MInfer', 'MASA', '∆Full']; strict: column key path not found or ambiguous

### 2610.10871v1 Table 2

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P4-T2-01 | cell | breaking | strict | 19.73 | - |
| P4-T2-02 | cell | breaking | strict | 12.15 | - |
| P4-T2-03 | cell | uncertain | strict | 66.81 | - |

### 2610.10871v1 Table 9

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P4-T9-01 | cell | - | relaxed | 87.13 | - |
| P4-T9-02 | cell | - | relaxed | 87.27 | - |
| P4-T9-03 | cell | breaking | relaxed | 87.88 | - |
| P4-T9-04 | cell | breaking | relaxed | 87.76 | - |
| P4-T9-05 | cell | breaking | relaxed | 88.09 | - |
| P4-T9-06 | cell | breaking | relaxed | 87.79 | - |
| P4-T9-07 | cell | - | relaxed | 89.26 | - |
| P4-T9-08 | cell | - | relaxed | 89.22 | - |
| P4-T9-09 | cell | - | relaxed | 89.94 | - |
| P4-T9-10 | cell | - | relaxed | 72.16 | - |
| P4-T9-11 | cell | - | relaxed | 97.66 | - |
| P4-T9-S1 | row_absent | breaking | relaxed | 0 matching rows | - |
| P4-T9-S2 | row_exists | - | relaxed | 1 matching rows | - |

Pins that needed the relaxed label compare:

- P4-T9-01: labels ['MInference', '-', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-02: labels ['MInference', '90', '0.6', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-03: labels ['SeerAttention', '-', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-04: labels ['SeerAttention', '85', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-05: labels ['SeerAttention', '90', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-06: labels ['SeerAttention', '95', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-07: labels ['FlexPrefill-Llama', '90', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-08: labels ['FlexPrefill-Llama', '95', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-09: labels ['FlexPrefill-Llama', '97.5', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-10: labels ['FlexPrefill-Qwen', '-', '-', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-11: labels ['MInference', '-', '-', '4K', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-S1: labels []; strict: named column not found or ambiguous
- P4-T9-S2: labels []; strict: named column not found or ambiguous

### 2610.11291v1 Table 3

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P5-T3-S1 | row_count | breaking | strict | 17 | - |
| P5-T3-S2 | col_contains_count | breaking | strict | 2 | - |
| P5-T3-S3 | row_exists | breaking | strict | 1 matching rows | - |
| P5-T3-S4 | row_exists | breaking | strict | 1 matching rows | - |
| P5-T3-S5 | row_exists | breaking | strict | 1 matching rows | - |
| P5-T3-S6 | row_exists | breaking | strict | 1 matching rows | - |

### 2610.11312v1 Table 10

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P6-T10-01 | cell | - | strict | 44.5 / 53.3 | - |
| P6-T10-S1 | row_count | breaking | strict | 11 | - |
| P6-T10-S2 | name_set | breaking | strict | all present once | - |
| P6-T10-S3 | label_absent | breaking | strict | absent | - |
| P6-T10-S4 | group_counts | - | strict | {"General-purpose VLMs": 6, "Medical VLMs": 5} | - |

### 2610.12114v1 Table 3

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P11-T3-01 | cell | - | strict | 34.3 | - |
| P11-T3-02 | cell | - | strict | 9.2 | - |
| P11-T3-03 | cell | - | strict | 12 | - |
| P11-T3-04 | cell | - | strict | 62.4 | - |
| P11-T3-05 | cell | - | strict | 50.0 | - |
| P11-T3-06 | cell | - | strict | 32 | - |
| P11-T3-S1 | caption | breaking | strict | all fragments found | - |
| P11-T3-S2 | row_exists | - | relaxed | 1 matching rows | - |

Pins that needed the relaxed label compare:

- P11-T3-S2: labels ['SeqKD (Kim & Rush, 2016)']; strict: 0 matching rows

## S rows (resolution)

selected_final: ['P1-S2', 'P2-S2', 'P3-S1', 'P4-S1', 'P5-S4', 'P6-S1', 'P1-S3', 'P8-S6', 'P9-S4', 'P1-S6']

| old | new | reason |
|---|---|---|
| P1-S1 | P1-S2 | P1 T1: pdf-ambiguous |
| P7-S2 | P1-S3 | P7 T1: latex-none |
| P11-S8 | P1-S6 | P11 T5: latex-ambiguous |

Skipped replacement candidates:

- P1-S4: P1 T1: pdf-ambiguous

P7-S2: P7 Table 1 not identified (latex-none); replaced by P1-S3 per entry rule

## Parser fixes after run 1

1. `\href{url}{text}` now yields `text` (P5 T3 cells).
3. A table environment with more than one tabular is parsed as sub-tables T<n>a, T<n>b, ... in source order; each is its own ref file. A pin on such a table takes the first sub-table where it passes.
4. `\makebox`, `\framebox`, `\raisebox` keep their content; `\put(x,y){c}` keeps c; picture environments are dropped and flagged "drawing removed".

## Rule amendments after run 1 (approved by Nitin)

2. Relaxed label compare also treats `-`, en dash, em dash and minus sign as one character (decisions.md 2026-10-29: glyph differences in labels do not count). LaTeX `--` is still rendered as an en dash in cell text. Lone-dash cells (missing values) are relaxed too.
5. Citation-blind matching for caption identification and for the relaxed label compare, on both sides: parenthetical groups that contain a year 1900-2099 (optional letter), e.g. `(Hsieh et al., 2024)`, and numeric brackets such as `[12]` or `[3,4]` are removed (LaTeX `\cite*` was already dropped). Uniqueness is still required.

