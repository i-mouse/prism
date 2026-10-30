# T2-R reference tables - build report (2026-10-29)

INR 0. No LLM, no network. Run state: **STOPPED**

- STOP: gate table P3-T9: 1 pin(s) not matched: P3-T9-13
- STOP: gate table P4-T1 unidentified (latex-none)
- STOP: gate table P4-T2 unidentified (latex-none)
- STOP: gate table P4-T9: 11 pin(s) not matched: P4-T9-01, P4-T9-03, P4-T9-04, P4-T9-05, P4-T9-06, P4-T9-07, P4-T9-08, P4-T9-09, P4-T9-10, P4-T9-11, P4-T9-S2
- STOP: gate table P5-T3: 4 pin(s) not matched: P5-T3-S3, P5-T3-S4, P5-T3-S5, P5-T3-S6
- STOP: gate table P11-T3: 1 pin(s) not matched: P11-T3-S2
- STOP: parse problems in 2610.11312v1 T1: 2 tabular environments in one table body (first used)

## Tables

| paper | table | identified | PDF caption start (<=80) | rows x cols | header rows | multirow/multicolumn | unknown macros | parse problems | pins cell x/y (certain) | structural x/y | uncertain x/y | relaxed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2610.10590v1 | 1 | n (latex-none) | OpenTelemetry, both phases unless specified. Metric | - | - | - | - | - | - | - | - | - |
| 2610.10871v1 | 1 | n (latex-none) | RULER (Hsieh et al., 2024) results under matched sparse-attention settings. With | - | - | - | - | - | - | - | - | - |
| 2610.10871v1 | 2 | n (latex-none) | InfiniteBench (Zhang et al., 2024) results under matched sparse-attention settin | - | - | - | - | - | - | - | - | - |
| 2610.10871v1 | 3 | n (latex-none) | LongBench (Bai et al., 2024b) results under matched sparse-attention settings. | - | - | - | - | - | - | - | - | - |
| 2610.10871v1 | 9 | y | Full RULER probe ablation. Clip p denotes norm clipping at percentile p, and Nor | 13x10 | 1 | 0/0 | - | - | 1/11 | 1/2 | 0/0 | 2 |
| 2610.11132v1 | 1 | y | SFT-as-context successfully mitigates the forgetting of general capabilities and | 27x6 | 1 | 0/9 | - | - | - | - | - | - |
| 2610.11135v1 | 1 | y | Cold-start AUC (P1) of Jev against the best deep KT and the best LLM-based KT ba | 26x11 | 1 | 8/0 | - | - | - | - | - | - |
| 2610.11135v1 | 9 | y | P2 (new learners), every cell. AUC by the position of the target in a new learne | 25x9 | 1 | 0/6 | - | - | 3/3 | 0/0 | 9/10 | 0 |
| 2610.11291v1 | 3 | y | All 17 teacher–student pairs, sorted by AUC gain of Semi-OPD over OPD. Model nam | 19x8 | 2 | 0/1 | \href | - | 0/0 | 2/6 | 0/0 | 0 |
| 2610.11312v1 | 1 | y | Task-space construction and evidence-mapping results. Task-Space Precision (P),  | 7x8 | 2 | 1/2 | - | 2 tabular environments in one table body (first used) | - | - | - | - |
| 2610.11312v1 | 10 | y | Evaluation performance on ISIC 2018. Choice tasks report Accuracy / Macro-F1 (%) | 15x8 | 2 | 3/3 | - | - | 1/1 | 4/4 | 0/0 | 0 |
| 2610.11519v1 | 1 | n (pdf-ambiguous) | Residual guidance improves both RLVR estimators on every benchmark and metric, | - | - | - | - | - | - | - | - | - |
| 2610.11519v1 | 2 | y | Every residual variant improves on verifier-only training at every tested weight | 8x7 | 2 | 1/4 | - | - | - | - | - | - |
| 2610.11519v1 | 4 | y | The same teacher-peak branch slightly helps sampled OPD but lowers both students | 5x8 | 3 | 0/9 | - | - | 1/1 | 0/0 | 2/2 | 3 |
| 2610.11519v1 | 10 | y | Macro differences among runs. Differences of three-seed macro means from Tables  | 18x4 | 1 | 0/0 | - | - | - | - | - | - |
| 2610.11519v1 | 30 | y | The adapted teacher is a worse solver than the frozen teacher. Qwen3-8B in non- | 7x9 | 2 | 1/4 | - | - | - | - | - | - |
| 2610.12114v1 | 3 | y | Comparison with KD methods under the Pro→Qwen setting. | 8x4 | 2 | 1/1 | - | - | 6/6 | 1/2 | 0/0 | 0 |
| 2610.12114v1 | 5 | n (latex-ambiguous) | Primer effectiveness and cross-model transferability on Vision Dominant plane ge | - | - | - | - | - | - | - | - | - |
| 2610.12124v1 | 2 | y | Cross-domain knowledge generalization and integration. ScienceWorld mean progres | 10x7 | 2 | 0/3 | \makebox, \put | - | - | - | - | - |
| 2610.12375v1 | 6 | y | Abort threshold sweep on severe flag density (n=150 per class, balanced). Precis | 5x5 | 1 | 0/0 | - | - | - | - | - | - |

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
| P3-T9-13 | cell | uncertain | mismatch | .605 | value differs |

### 2610.10871v1 Table 9

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P4-T9-01 | cell | - | mismatch | - | row key path not found or ambiguous |
| P4-T9-02 | cell | - | relaxed | 87.27 | - |
| P4-T9-03 | cell | breaking | mismatch | - | row key path not found or ambiguous |
| P4-T9-04 | cell | breaking | mismatch | - | row key path not found or ambiguous |
| P4-T9-05 | cell | breaking | mismatch | - | row key path not found or ambiguous |
| P4-T9-06 | cell | breaking | mismatch | - | row key path not found or ambiguous |
| P4-T9-07 | cell | - | mismatch | - | row key path not found or ambiguous |
| P4-T9-08 | cell | - | mismatch | - | row key path not found or ambiguous |
| P4-T9-09 | cell | - | mismatch | - | row key path not found or ambiguous |
| P4-T9-10 | cell | - | mismatch | - | row key path not found or ambiguous |
| P4-T9-11 | cell | - | mismatch | - | row key path not found or ambiguous |
| P4-T9-S1 | row_absent | breaking | relaxed | 0 matching rows | - |
| P4-T9-S2 | row_exists | - | mismatch | 0 matching rows | named column not found or ambiguous |

Pins that needed the relaxed label compare:

- P4-T9-02: labels ['MInference', '90', '0.6', 'Avg.', 'Setting', 'Clip p', 'Norm alpha']; strict: row key path not found or ambiguous
- P4-T9-S1: labels []; strict: named column not found or ambiguous

### 2610.11291v1 Table 3

| pin | kind | class | status | got | reason |
|---|---|---|---|---|---|
| P5-T3-S1 | row_count | breaking | strict | 17 | - |
| P5-T3-S2 | col_contains_count | breaking | strict | 2 | - |
| P5-T3-S3 | row_exists | breaking | mismatch | 0 matching rows | - |
| P5-T3-S4 | row_exists | breaking | mismatch | 0 matching rows | - |
| P5-T3-S5 | row_exists | breaking | mismatch | 0 matching rows | - |
| P5-T3-S6 | row_exists | breaking | mismatch | 0 matching rows | - |

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
| P11-T3-S2 | row_exists | - | mismatch | 0 matching rows | - |

## S rows (resolution)

selected_final: ['P1-S2', 'P2-S2', 'P3-S1', 'P1-S3', 'P5-S4', 'P6-S1', 'P1-S6', 'P8-S6', 'P9-S4', 'P1-S8']

| old | new | reason |
|---|---|---|
| P1-S1 | P1-S2 | P1 T1: pdf-ambiguous |
| P4-S1 | P1-S3 | P4 T1: latex-none; P4 T2: latex-none; P4 T3: latex-none |
| P7-S2 | P1-S6 | P7 T1: latex-none |
| P11-S8 | P1-S8 | P11 T5: latex-ambiguous |

Skipped replacement candidates:

- P1-S4: P1 T1: pdf-ambiguous

P7-S2: P7 Table 1 not identified (latex-none); replaced by P1-S6 per entry rule

## Parser fixes after run 1

(none)

## Grids of failing gate tables

### P3-T9 (pins failed)

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H | Method | A09 | NIPS34 | XES3G5M | DBE | Alg05 | Junyi | A17 | Mean |
| 1 | S | Position 1 [cs=9] | < | < | < | < | < | < | < | < |
| 2 | R | JevKT | .709±.059 | .644±.047 | .512±.057 | – | .799±.022 | .517±.024 | .660±.066 | .640 |
| 3 | R | Jev0-shot (N=0) | .689±.103 | .492±.094 | .533±.102 | – | .650±.086 | .466±.119 | .654±.090 | .580 |
| 4 | R | Best deep KT† | .749±.049 | .558±.056 | .542±.049 | – | .663±.016 | .510±.030 | .607±.080 | .605 |
| 5 | S | Positions 2–5 [cs=9] | < | < | < | < | < | < | < | < |
| 6 | R | JevKT | .771±.008 | .729±.041 | .666±.006 | .768±.042 | .714±.013 | .657±.007 | .689±.032 | .714 |
| 7 | R | Jev0-shot (N=0) | .776±.035 | .707±.046 | .644±.048 | .675±.050 | .669±.052 | .649±.045 | .691±.046 | .687 |
| 8 | R | Best deep KT† | .745±.019 | .672±.029 | .659±.010 | .753±.052 | .683±.015 | .642±.009 | .682±.022 | .691 |
| 9 | S | Positions 6–10 [cs=9] | < | < | < | < | < | < | < | < |
| 10 | R | JevKT | .745±.010 | .708±.030 | .657±.027 | .888±.022 | .746±.007 | .690±.012 | .648±.043 | .726 |
| 11 | R | Jev0-shot (N=0) | .758±.034 | .712±.038 | .651±.042 | .811±.056 | .711±.045 | .693±.040 | .649±.037 | .712 |
| 12 | R | Best deep KT† | .705±.015 | .654±.041 | .577±.032 | .908±.016 | .742±.013 | .632±.040 | .647±.021 | .695 |
| 13 | S | Positions 11–15 [cs=9] | < | < | < | < | < | < | < | < |
| 14 | R | JevKT | .719±.009 | .725±.040 | .750±.019 | .773±.017 | .698±.015 | .781±.002 | .614±.028 | .723 |
| 15 | R | Jev0-shot (N=0) | .726±.037 | .698±.037 | .762±.036 | .729±.058 | .661±.052 | .768±.041 | .623±.042 | .710 |
| 16 | R | Best deep KT† | .678±.026 | .693±.019 | .727±.014 | .773±.035 | .714±.013 | .707±.066 | .601±.021 | .699 |
| 17 | S | Positions 16–30 [cs=9] | < | < | < | < | < | < | < | < |
| 18 | R | JevKT | .728±.004 | .719±.015 | .733±.010 | .845±.011 | .729±.007 | .670±.005 | .648±.020 | .725 |
| 19 | R | Jev0-shot (N=0) | .721±.021 | .700±.023 | .729±.023 | .742±.037 | .706±.025 | .669±.028 | .659±.022 | .704 |
| 20 | R | Best deep KT† | .680±.007 | .652±.049 | .693±.062 | .789±.029 | .689±.005 | .625±.039 | .618±.015 | .678 |
| 21 | S | Positions 31–49 [cs=9] | < | < | < | < | < | < | < | < |
| 22 | R | JevKT | .737±.010 | .692±.021 | .749±.011 | .802±.010 | .750±.005 | .734±.007 | .630±.012 | .728 |
| 23 | R | Jev0-shot (N=0) | .745±.025 | .684±.019 | .764±.022 | .734±.023 | .716±.023 | .735±.023 | .641±.020 | .717 |
| 24 | R | Best deep KT† | .710±.021 | .646±.030 | .726±.066 | .782±.012 | .731±.009 | .676±.027 | .621±.008 | .699 |

### P4-T9 (pins failed)

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H | Setting | Clip p | Norm α | 4K | 8K | 16K | 32K | 64K | 128K | Avg. |
| 1 | R | MInference | – | – | 97.66 | 91.46 | 88.57 | 85.21 | 81.76 | 78.11 | 87.13 |
| 2 | R | MInference | 90 | 0.6 | 97.93 | 91.29 | 88.50 | 85.45 | 81.57 | 78.88 | 87.27 |
| 3 | R | SeerAttention | – | – | 95.53 | 92.50 | 92.98 | 89.58 | 84.20 | 72.50 | 87.88 |
| 4 | R | SeerAttention | 85 | – | 95.63 | 92.40 | 91.98 | 89.55 | 83.64 | 73.34 | 87.76 |
| 5 | R | SeerAttention | 90 | – | 95.53 | 92.74 | 92.84 | 89.56 | 84.01 | 73.85 | 88.09 |
| 6 | R | SeerAttention | 95 | – | 95.32 | 92.84 | 92.70 | 89.59 | 83.52 | 72.72 | 87.79 |
| 7 | R | FlexPrefill-Llama | 90 | – | 95.67 | 94.47 | 93.99 | 88.70 | 84.13 | 78.61 | 89.26 |
| 8 | R | FlexPrefill-Llama | 95 | – | 95.67 | 94.23 | 93.99 | 88.94 | 83.89 | 78.61 | 89.22 |
| 9 | R | FlexPrefill-Llama | 97.5 | – | 95.43 | 93.99 | 94.95 | 89.66 | 85.09 | 80.54 | 89.94 |
| 10 | R | FlexPrefill-Qwen | – | – | 90.88 | 88.94 | 84.85 | 82.64 | 62.79 | 22.83 | 72.16 |
| 11 | R | FlexPrefill-Qwen | 95 | – | 90.11 | 89.94 | 83.37 | 82.69 | 58.44 | 21.39 | 70.99 |
| 12 | R | FlexPrefill-Qwen | – | 1.0 | 89.92 | 88.49 | 81.73 | 81.20 | 59.14 | 24.03 | 70.75 |

### P5-T3 (pins failed)

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  |  |  | Train Len | Init. | Gain [cs=2] | < |
| 1 | H | # | Student | Teacher | Mode | Cap | Overlap | Last-step | AUC |
| 2 | R | n | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B | \hrefhttps://huggingface.co/Qwen/Qwen3-30B-A3B-Thinking-2507Qwen3-30B-A3B-Thinking | T | 16K | 58.9 | +9.4 | +7.57 |
| 3 | R | a | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B | \hrefhttps://huggingface.co/Qwen/Qwen3-4B-Instruct-2507Qwen3-4B-Instruct-2507 | NT | 4K | 62.5 | +9.5 | +7.09 |
| 4 | R | p | \hrefhttps://huggingface.co/Qwen/Qwen3-4BQwen3-4B | \hrefhttps://huggingface.co/Qwen/Qwen3-30B-A3B-Thinking-2507Qwen3-30B-A3B-Thinking | T | 16K | 63.8 | +6.2 | +6.22 |
| 5 | R | o | \hrefhttps://huggingface.co/Qwen/Qwen3-14BQwen3-14B | \hrefhttps://huggingface.co/Qwen/Qwen3-235B-A22B-Thinking-2507Qwen3-235B-A22B-Thinking | T | 16K | 63.4 | +13.1 | +5.85 |
| 6 | R | b | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B | \hrefhttps://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 59.8 | +6.8 | +5.18 |
| 7 | R | f | \hrefhttps://huggingface.co/Qwen/Qwen3-4BQwen3-4B | \hrefhttps://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 62.5 | +4.2 | +4.61 |
| 8 | R | c | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B | \hrefhttps://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507Qwen3-235B-A22B-Instruct-2507 | NT | 4K | 56.9 | +2.6 | +3.27 |
| 9 | R | g | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B (SFT) | \hrefhttps://huggingface.co/Qwen/Qwen3-4B-Instruct-2507Qwen3-4B-Instruct-2507 | NT | 4K | 62.9 | +2.4 | +2.05 |
| 10 | R | h | \hrefhttps://huggingface.co/Qwen/Qwen3-4BQwen3-4B (SFT) | \hrefhttps://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 63.1 | +0.9 | +1.50 |
| 11 | R | d | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B | \hrefhttps://huggingface.co/Qwen/Qwen3-4BQwen3-4B | NT | 4K | 70.0 | +1.1 | +1.35 |
| 12 | R | m | \hrefhttps://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7BR1-Distill-7B | \hrefhttps://huggingface.co/agentica-org/DeepCoder-14B-PreviewDeepCoder-14B | T | 16K | 73.9 | +1.5 | +0.97 |
| 13 | R | e | \hrefhttps://huggingface.co/Qwen/Qwen3-1.7BQwen3-1.7B | \hrefhttps://huggingface.co/Qwen/Qwen3-8BQwen3-8B | NT | 4K | 69.4 | +0.8 | +0.54 |
| 14 | R | j | \hrefhttps://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5BR1-Distill-1.5B | \hrefhttps://huggingface.co/POLARIS-Project/Polaris-7B-PreviewPolaris-7B | T | 16K | 69.7 | +0.1 | +0.24 |
| 15 | R | q | Cascade-2-30B-A3B | Cascade-2-Math-Expert† | T | 16K | 89.3 | -0.1 | +0.09 |
| 16 | R | l | \hrefhttps://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7BR1-Distill-7B | \hrefhttps://huggingface.co/qihoo360/Light-R1-14B-DSLight-R1-14B | T | 16K | 72.0 | -1.7 | -0.30 |
| 17 | R | k | \hrefhttps://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7BR1-Distill-7B | \hrefhttps://huggingface.co/POLARIS-Project/Polaris-7B-PreviewPolaris-7B | T | 16K | 86.8 | -2.6 | -0.68 |
| 18 | R | i | \hrefhttps://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5BR1-Distill-1.5B | \hrefhttps://huggingface.co/hbx/JustRL-DeepSeek-1.5BJustRL-1.5B | T | 16K | 79.7 | +1.4 | -1.36 |

### P11-T3 (pins failed)

| r | f | c0 | c1 | c2 | c3 |
|---|---|---|---|---|---|
| 0 | H | Method [rs=2] | Omni-MATH-2 | KernelBench [cs=2] | < |
| 1 | H | ^ | Acc. | Acc. | Fast1 |
| 2 | R | Student | 34.3 | 9.2 | 12 |
| 3 | R | SeqKD | 53.5 | 18.8 | 18 |
| 4 | R | Fine-tune-CoT | 39.5 | 41.8 | 28 |
| 5 | R | RSR | 51.5 | 22.6 | 19 |
| 6 | R | LUFFY | 55.2 | 11.4 | 13 |
| 7 | R | UTT (Ours) | 62.4 | 50.0 | 32 |

### 2610.11312v1 T1 (parse problems)

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H | Model [rs=2] | Task-Space Review [cs=6] | < | < | < | < | < | Evidence |
| 1 | H | ^ | TP | FP | FN | P↑ | R↑ | F1↑ | EMA↑ |
| 2 | R | DeepSeek-V4-Flash | 19 | 8 | 2 | 70.4 | 90.5 | 79.2 | 100.0 |
| 3 | R | Qwen3.5-9B | 19 | 8 | 2 | 70.4 | 90.5 | 79.2 | 100.0 |
| 4 | R | MedGemma-27B | 20 | 9 | 1 | 69.0 | 95.2 | 80.0 | 100.0 |
| 5 | R | DeepSeek-V4-Flash + T0 | 20 | 6 | 1 | 76.9 | 95.2 | 85.1 | 100.0 |
| 6 | R | MedBenchAgent | 20 | 3 | 1 | 87.0 | 95.2 | 90.9 | 100.0 |

