# Blind claim pack

17 items. Each item is one claim and the reference table(s) it concerns. Open the named PDF to read the claim in context.

---

## C01

Paper: JevKT: When Few or No Learners Are Logged?

arXiv: 2610.11135v1

PDF file: 2610.11135v1.pdf

Claim (verbatim):

> For new learners the advantage holds from their first interactions, whereas on unseen items with all learners logged, deep KT remains ahead.

### Table 9

PDF page: not recorded (find by caption)

Caption: P2 (new learners), every cell. AUC by the position of the target in a new learner's sequence with N=8 training learners (Jev0-shot uses none), mean±SD over 5 seeds (Jev0-shot: learner-bootstrap SD of its single run); same predictions as P1. Position 1 has only 41–50 targets per dataset, so its AUC is noisy; – = one class only. †Best of 28 pyKT models, chosen on the whole (N,dataset) cell. Best in bold, second best underlined.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

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

## Row key paths
- row 2: Position 1 > JevKT
- row 3: Position 1 > Jev0-shot (N=0)
- row 4: Position 1 > Best deep KT†
- row 6: Positions 2–5 > JevKT
- row 7: Positions 2–5 > Jev0-shot (N=0)
- row 8: Positions 2–5 > Best deep KT†
- row 10: Positions 6–10 > JevKT
- row 11: Positions 6–10 > Jev0-shot (N=0)
- row 12: Positions 6–10 > Best deep KT†
- row 14: Positions 11–15 > JevKT
- row 15: Positions 11–15 > Jev0-shot (N=0)
- row 16: Positions 11–15 > Best deep KT†
- row 18: Positions 16–30 > JevKT
- row 19: Positions 16–30 > Jev0-shot (N=0)
- row 20: Positions 16–30 > Best deep KT†
- row 22: Positions 31–49 > JevKT
- row 23: Positions 31–49 > Jev0-shot (N=0)
- row 24: Positions 31–49 > Best deep KT†

## Column key paths
- col 0: Method
- col 1: A09
- col 2: NIPS34
- col 3: XES3G5M
- col 4: DBE
- col 5: Alg05
- col 6: Junyi
- col 7: A17
- col 8: Mean

---

## C02

Paper: Residual Advantage (RA)

arXiv: 2610.11519v1

PDF file: 2610.11519v1.pdf

Claim (verbatim):

> Every residual variant improves on verifier-only training at every tested weight, and full RA stays above every control at every matched weight.

### Table 2

PDF page: not recorded (find by caption)

Caption: Every residual variant improves on verifier-only training at every tested weight, and full RA stays above every control at every matched weight. Qwen3-1.7B-Base with REINFORCE++; three-seed macro means in %. The weight is λ, γx, γ raw, or α as marked, with 10 the reference weight; per-seed values and sample SD are in Table .

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 |
|---|---|---|---|---|---|---|---|---|
| 0 | H | Variant (weight) [rs=2] | Macro Avg@8 at weight [cs=3] | < | < | Macro Pass@8 at weight [cs=3] | < | < |
| 1 | H | ^ | 5 | 10 | 20 | 5 | 10 | 20 |
| 2 | R | Full RA (λ) | 28.84 | 29.25 | 29.29 | 44.94 | 45.20 | 45.29 |
| 3 | R | w/o student value baseline (γx) | 26.96 | 27.16 | 26.53 | 41.93 | 41.62 | 40.76 |
| 4 | R | w/o response centering (λ) | 28.37 | 28.71 | 28.66 | 44.46 | 44.74 | 44.67 |
| 5 | R | Raw residual (w/o both, γ raw) | 27.48 | 27.52 | 26.96 | 42.63 | 42.43 | 40.96 |
| 6 | R | Direct L2 loss (α) | 27.83 | 28.02 | 27.71 | 43.39 | 43.44 | 42.96 |
| 7 | R | Verifier only (REINFORCE++) | 25.67 [cs=3] | < | < | 39.44 [cs=3] | < | < |

## Row key paths
- row 2: Full RA (λ)
- row 3: w/o student value baseline (γx)
- row 4: w/o response centering (λ)
- row 5: Raw residual (w/o both, γ raw)
- row 6: Direct L2 loss (α)
- row 7: Verifier only (REINFORCE++)

## Column key paths
- col 0: Variant (weight)
- col 1: Macro Avg@8 at weight > 5
- col 2: Macro Avg@8 at weight > 10
- col 3: Macro Avg@8 at weight > 20
- col 4: Macro Pass@8 at weight > 5
- col 5: Macro Pass@8 at weight > 10
- col 6: Macro Pass@8 at weight > 20

---

## C03

Paper: Hippocam: Use and Disuse

arXiv: 2610.12124v1

PDF file: 2610.12124v1.pdf

Claim (verbatim):

> Only Hippocam and ACE achieve positive gains on both domain transitions, while the remaining methods show mixed, unchanged, or reduced performance.

### Table 2

PDF page: not recorded (find by caption)

Caption: Cross-domain knowledge generalization and integration. ScienceWorld mean progress and FEVER accuracy (%). Δstream reports After minus Fresh in percentage points (pp).

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 |
|---|---|---|---|---|---|---|---|---|
| 0 | H |  | ALFWorld → ScienceWorld [cs=3] | < | < | HotpotQA → FEVER [cs=3] | < | < |
| 1 | H | Method | Frozen | Fresh → After | Δ stream | Frozen | Fresh → After | Δ stream |
| 2 | R | Plain | 48.8 | — | — | 59.3 | — | — |
| 3 | R | HiAgent | 42.7 | 49.6 → 49.7 | +0.1 | 61.8 | 57.9 → 52.1 | -5.8 |
| 4 | R | mem0 | 51.7 | 50.7 → 22.6 | -28.1 | 59.9 | 57.9 → 57.9 | +0.0 |
| 5 | R | A-Mem | 42.1 | 73.9 → 65.9 | -8.0 | 55.8 | 55.8 → 55.8 | +0.0 |
| 6 | R | Letta | 40.8 | 59.3 → 54.5 | -4.8 | 59.9 | 69.8 → 59.9 | -9.9 |
| 7 | R | ReasoningBank | 53.3 | 48.6 → 37.4 | -11.2 | 55.8 | 57.9 → 55.8 | -2.1 |
| 8 | R | ACE | 62.7 | 52.5 → 66.5 | +14.0 | 57.9 | 61.8 → 63.8 | +2.0 |
| 9 | R | Hippocam | 78.9 | 55.9 → 75.1 | +19.2 | 61.8 | 53.9 → 59.9 | +6.0 |

## Row key paths
- row 2: Plain
- row 3: HiAgent
- row 4: mem0
- row 5: A-Mem
- row 6: Letta
- row 7: ReasoningBank
- row 8: ACE
- row 9: Hippocam

## Column key paths
- col 0: Method
- col 1: ALFWorld → ScienceWorld > Frozen
- col 2: ALFWorld → ScienceWorld > Fresh → After
- col 3: ALFWorld → ScienceWorld > Δ stream
- col 4: HotpotQA → FEVER > Frozen
- col 5: HotpotQA → FEVER > Fresh → After
- col 6: HotpotQA → FEVER > Δ stream

---

## C04

Paper: MASA: Matrix Approximation Sparse Attention

arXiv: 2610.10871v1

PDF file: 2610.10871v1.pdf

Claim (verbatim):

> Norm clipping is helpful for SeerAttention and FlexPrefill-Llama, while soft norm balancing is useful in some FlexPrefill settings.

### Table 9

PDF page: not recorded (find by caption)

Caption: Full RULER probe ablation. Clip p denotes norm clipping at percentile p, and Norm α denotes soft norm balancing. The case p=– and α=– is raw MASA without norm control. Bold Avg. marks the best MASA variant within each setting.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

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

## Row key paths
- row 1: MInference
- row 2: MInference
- row 3: SeerAttention
- row 4: SeerAttention
- row 5: SeerAttention
- row 6: SeerAttention
- row 7: FlexPrefill-Llama
- row 8: FlexPrefill-Llama
- row 9: FlexPrefill-Llama
- row 10: FlexPrefill-Qwen
- row 11: FlexPrefill-Qwen
- row 12: FlexPrefill-Qwen

## Column key paths
- col 0: Setting
- col 1: Clip p
- col 2: Norm α
- col 3: 4K
- col 4: 8K
- col 5: 16K
- col 6: 32K
- col 7: 64K
- col 8: 128K
- col 9: Avg.

---

## C05

Paper: MedBenchAgent

arXiv: 2610.11312v1

PDF file: 2610.11312v1.pdf

Claim (verbatim):

> We further demonstrate portability to a specialized medical domain and evaluate twelve VLMs, revealing task- and setting-specific variation obscured by aggregate scores.

### Table 10

PDF page: not recorded (find by caption)

Caption: Evaluation performance on ISIC 2018. Choice tasks report Accuracy / Macro-F1 (%), while detection reports mIoU / Acc@IoU0.5 (%). Best results for each metric are shown in bold.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H | Model [rs=2] | Diagnosis [rs=2] | Finding Attribute [cs=5] | < | < | < | < | Detection [rs=2] |
| 1 | H | ^ | ^ | Globules | Milia-like | Neg. net. | Pigment net. | Streaks | ^ |
| 2 | S | General-purpose VLMs [cs=8] | < | < | < | < | < | < | < |
| 3 | R | InternVL3-8B | 20.7 / 15.3 | 31.4 / 31.1 | 70.7 / 56.6 | 45.3 / 35.0 | 72.4 / 63.4 | 39.3 / 35.7 | 50.5 / 52.2 |
| 4 | R | Qwen2.5-VL-7B | 24.2 / 14.6 | 57.8 / 53.7 | 80.8 / 55.5 | 83.8 / 47.4 | 59.5 / 59.3 | 33.6 / 30.7 | 75.1 / 86.6 |
| 5 | R | Qwen3-VL-8B-I | 53.2 / 22.8 | 28.4 / 27.5 | 80.2 / 61.8 | 80.2 / 47.3 | 59.5 / 58.4 | 58.0 / 44.7 | 80.3 / 91.4 |
| 6 | R | Qwen3-VL-8B-T† | 30.9 / 18.6 | 60.5 / 52.9 | 83.2 / 61.1 | 85.0 / 48.2 | 57.1 / 56.0 | 82.9 / 47.0 | 71.2 / 83.6 |
| 7 | R | Qwen2.5-VL-32B | 29.8 / 20.8 | 25.1 / 23.6 | 46.7 / 40.2 | 28.5 / 24.3 | 72.4 / 64.5 | 15.9 / 15.9 | 76.8 / 87.6 |
| 8 | R | Qwen3-VL-32B | 52.8 / 30.3 | 70.1 / 58.2 | 84.4 / 55.1 | 74.2 / 45.8 | 58.0 / 57.3 | 88.0 / 55.1 | 80.2 / 92.2 |
| 9 | S | Medical VLMs [cs=8] | < | < | < | < | < | < | < |
| 10 | R | MedGemma-4B | 47.8 / 31.5 | 25.7 / 24.0 | 66.8 / 52.5 | 45.3 / 33.5 | 79.0 / 71.7 | 59.5 / 47.7 | 31.8 / 29.1 |
| 11 | R | Lingshu-7B | 10.6 / 7.0 | 68.3 / 57.2 | 82.9 / 53.9 | 46.8 / 36.2 | 76.9 / 71.4 | 46.5 / 38.4 | 11.7 / 6.8 |
| 12 | R | Hulu-Med-7B | 56.3 / 34.4 | 75.4 / 47.4 | 83.8 / 59.0 | 95.2 / 48.8 | 40.8 / 38.6 | 76.6 / 48.9 | 0.7 / 0.2 |
| 13 | R | QoQ-Med-7B† | 49.5 / 21.4 | 69.2 / 48.2 | 84.7 / 55.6 | 90.7 / 47.6 | 41.1 / 39.2 | 75.7 / 46.8 | 25.8 / 11.3 |
| 14 | R | Lingshu-32B | 24.6 / 16.8 | 71.9 / 60.3 | 75.7 / 53.5 | 44.1 / 33.9 | 72.4 / 69.2 | 57.4 / 44.8 | 44.5 / 53.3 |

## Row key paths
- row 3: General-purpose VLMs > InternVL3-8B
- row 4: General-purpose VLMs > Qwen2.5-VL-7B
- row 5: General-purpose VLMs > Qwen3-VL-8B-I
- row 6: General-purpose VLMs > Qwen3-VL-8B-T†
- row 7: General-purpose VLMs > Qwen2.5-VL-32B
- row 8: General-purpose VLMs > Qwen3-VL-32B
- row 10: Medical VLMs > MedGemma-4B
- row 11: Medical VLMs > Lingshu-7B
- row 12: Medical VLMs > Hulu-Med-7B
- row 13: Medical VLMs > QoQ-Med-7B†
- row 14: Medical VLMs > Lingshu-32B

## Column key paths
- col 0: Model
- col 1: Diagnosis
- col 2: Finding Attribute > Globules
- col 3: Finding Attribute > Milia-like
- col 4: Finding Attribute > Neg. net.
- col 5: Finding Attribute > Pigment net.
- col 6: Finding Attribute > Streaks
- col 7: Detection

---

## C06

Paper: MASA: Matrix Approximation Sparse Attention

arXiv: 2610.10871v1

PDF file: 2610.10871v1.pdf

Claim (verbatim):

> Across multiple sparse baselines, benchmarks, and LLM backbones, MASA gives consistent gains under matched settings with negligible latency overhead.

### Table 1

PDF page: not recorded (find by caption)

Caption: RULER results under matched sparse-attention settings. Within each framework, Original and MASA use the same sparse implementation and differ only in the ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. between Original and MASA.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  | Variant | 4K | 8K | 16K | 32K | 64K | 128K | Avg. | ΔFull |
| 1 | R | MInfer [rs=3] |  | Full Attention | 97.2 | 91.8 | 87.3 | 80.8 | 77.4 | 72.2 | 84.4 | 0 |
| 2 | R | ^ |  | Original | 97.7 | 91.2 | 88.5 | 85.0 | 82.3 | 77.6 | 87.0 | +2.6 |
| 3 | R | ^ |  | MASA | 97.93 | 91.29 | 88.50 | 85.45 | 81.57 | 78.88 | 87.27 | +2.87 |
| 4 | R | SeerAttn [rs=3] |  | Full Attention | 95.53 | 92.37 | 92.01 | 87.63 | 84.39 | 76.26 | 88.01 | 0 |
| 5 | R | ^ |  | Original | 95.53 | 92.71 | 92.02 | 88.49 | 83.48 | 73.37 | 87.60 | -0.41 |
| 6 | R | ^ |  | MASA | 95.53 | 92.74 | 92.84 | 89.56 | 84.01 | 73.85 | 88.09 | +0.08 |
| 7 | R | FlexPrefill [rs=6] | Llama [rs=3] | Full Attention | 95.67 | 93.75 | 93.03 | 87.26 | 84.37 | 78.13 | 88.70 | 0 |
| 8 | R | ^ | ^ | Original | 95.43 | 93.51 | 94.71 | 89.42 | 82.93 | 79.09 | 89.18 | +0.48 |
| 9 | R | ^ | ^ | MASA | 95.43 | 93.99 | 94.95 | 89.66 | 85.09 | 80.54 | 89.94 | +1.24 |
| 10 | R | ^ | Qwen [rs=3] | Full Attention | 89.90 | 88.70 | 80.77 | 79.33 | 56.49 | 17.79 | 68.83 | 0 |
| 11 | R | ^ | ^ | Original | 90.39 | 89.91 | 83.17 | 81.25 | 59.14 | 20.67 | 70.75 | +1.92 |
| 12 | R | ^ | ^ | MASA | 90.88 | 88.94 | 84.85 | 82.64 | 62.79 | 22.83 | 72.16 | +3.33 |

## Row key paths
- row 1: MInfer > Full Attention
- row 2: MInfer > Original
- row 3: MInfer > MASA
- row 4: SeerAttn > Full Attention
- row 5: SeerAttn > Original
- row 6: SeerAttn > MASA
- row 7: FlexPrefill > Llama > Full Attention
- row 8: FlexPrefill > Llama > Original
- row 9: FlexPrefill > Llama > MASA
- row 10: FlexPrefill > Qwen > Full Attention
- row 11: FlexPrefill > Qwen > Original
- row 12: FlexPrefill > Qwen > MASA

## Column key paths
- col 0: 
- col 1: 
- col 2: Variant
- col 3: 4K
- col 4: 8K
- col 5: 16K
- col 6: 32K
- col 7: 64K
- col 8: 128K
- col 9: Avg.
- col 10: ΔFull

### Table 2

PDF page: not recorded (find by caption)

Caption: InfiniteBench results under matched sparse-attention settings. Within each framework, Original and MASA use the same sparse implementation and differ only in the ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. between Original and MASA.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13 | c14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  | Variant | En.Sum | En.QA | En.MC | En.Dia | Zh.QA | Code Debug | Math Find | Retr. PassKey | Retr. Number | Retr. KV | Avg. | ΔFull |
| 1 | R | MInfer [rs=3] |  | Full Attention | 20.2 | 12.4 | 67.3 | 6.0 | 12.9 | 22.1 | 26.6 | 100.0 | 100.0 | 14.4 | 38.2 | 0 |
| 2 | R | ^ |  | Original | 20.5 | 12.9 | 65.9 | 7.5 | 12.5 | 22.3 | 33.1 | 100.0 | 100.0 | 12.8 | 38.8 | +0.6 |
| 3 | R | ^ |  | MASA | 19.73 | 12.15 | 66.81 | 8.50 | 12.28 | 22.84 | 33.43 | 100.00 | 100.00 | 16.20 | 39.20 | +1.00 |
| 4 | R | FlexPrefill [rs=6] | Llama [rs=3] | Full Attention | 31.91 | 25.92 | 69.43 | 21.50 | 31.95 | 16.75 | 24.29 | 99.15 | 99.66 | 60.00 | 48.06 | 0 |
| 5 | R | ^ | ^ | Original | 31.82 | 24.82 | 69.43 | 19.50 | 35.46 | 16.75 | 31.14 | 98.64 | 99.83 | 44.00 | 47.14 | -0.92 |
| 6 | R | ^ | ^ | MASA | 32.10 | 26.25 | 66.81 | 19.50 | 33.66 | 20.05 | 29.14 | 98.31 | 99.66 | 54.40 | 47.99 | -0.07 |
| 7 | R | ^ | Qwen [rs=3] | Full Attention | 4.65 | 5.57 | 34.50 | 9.00 | 11.27 | 24.87 | 24.57 | 95.42 | 75.42 | 0.00 | 29.53 | 0 |
| 8 | R | ^ | ^ | Original | 14.27 | 6.55 | 34.06 | 13.50 | 11.51 | 20.81 | 30.86 | 96.95 | 72.20 | 0.00 | 30.07 | +0.54 |
| 9 | R | ^ | ^ | MASA | 15.55 | 6.38 | 32.31 | 16.50 | 13.09 | 21.07 | 30.29 | 94.41 | 74.58 | 0.00 | 30.42 | +0.89 |

## Row key paths
- row 1: MInfer > Full Attention
- row 2: MInfer > Original
- row 3: MInfer > MASA
- row 4: FlexPrefill > Llama > Full Attention
- row 5: FlexPrefill > Llama > Original
- row 6: FlexPrefill > Llama > MASA
- row 7: FlexPrefill > Qwen > Full Attention
- row 8: FlexPrefill > Qwen > Original
- row 9: FlexPrefill > Qwen > MASA

## Column key paths
- col 0: 
- col 1: 
- col 2: Variant
- col 3: En.Sum
- col 4: En.QA
- col 5: En.MC
- col 6: En.Dia
- col 7: Zh.QA
- col 8: Code Debug
- col 9: Math Find
- col 10: Retr. PassKey
- col 11: Retr. Number
- col 12: Retr. KV
- col 13: Avg.
- col 14: ΔFull

---

## C07

Paper: MedBenchAgent

arXiv: 2610.11312v1

PDF file: 2610.11312v1.pdf

Claim (verbatim):

> MedBenchAgent achieves a Task-Space F1 of 90.9%, outperforming direct task induction (79.2–80.0%) and prior-guided induction (85.1%); 994 of 1,000 sampled items from correctly identified tasks pass human audit.

### Table 1, part a

PDF page: not recorded (find by caption)

Caption: Task-space construction and evidence-mapping results. Task-Space Precision (P), Recall (R), and F1 measure agreement with researcher review; EMA measures agreement of supporting annotation fields (%).

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H | Model [rs=2] | Task-Space Review [cs=6] | < | < | < | < | < | Evidence |
| 1 | H | ^ | TP | FP | FN | P↑ | R↑ | F1↑ | EMA↑ |
| 2 | R | DeepSeek-V4-Flash | 19 | 8 | 2 | 70.4 | 90.5 | 79.2 | 100.0 |
| 3 | R | Qwen3.5-9B | 19 | 8 | 2 | 70.4 | 90.5 | 79.2 | 100.0 |
| 4 | R | MedGemma-27B | 20 | 9 | 1 | 69.0 | 95.2 | 80.0 | 100.0 |
| 5 | R | DeepSeek-V4-Flash + T0 | 20 | 6 | 1 | 76.9 | 95.2 | 85.1 | 100.0 |
| 6 | R | MedBenchAgent | 20 | 3 | 1 | 87.0 | 95.2 | 90.9 | 100.0 |

## Row key paths
- row 2: DeepSeek-V4-Flash
- row 3: Qwen3.5-9B
- row 4: MedGemma-27B
- row 5: DeepSeek-V4-Flash + T0
- row 6: MedBenchAgent

## Column key paths
- col 0: Model
- col 1: Task-Space Review > TP
- col 2: Task-Space Review > FP
- col 3: Task-Space Review > FN
- col 4: Task-Space Review > P↑
- col 5: Task-Space Review > R↑
- col 6: Task-Space Review > F1↑
- col 7: Evidence > EMA↑

### Table 1, part b

PDF page: not recorded (find by caption)

Caption: Task-space construction and evidence-mapping results. Task-Space Precision (P), Recall (R), and F1 measure agreement with researcher review; EMA measures agreement of supporting annotation fields (%).

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 |
|---|---|---|---|---|---|
| 0 | H | Criterion | Pass | Fail | Pass Rate |
| 1 | R | Reference groundedness | 1,000 | 0 | 100.0% |
| 2 | R | Task–query alignment | 996 | 4 | 99.6% |
| 3 | R | Unambiguity | 1,000 | 0 | 100.0% |
| 4 | R | Evaluation integrity | 994 | 6 | 99.4% |
| 5 | R | All criteria | 994 | 6 | 99.4% |

## Row key paths
- row 1: Reference groundedness
- row 2: Task–query alignment
- row 3: Unambiguity
- row 4: Evaluation integrity
- row 5: All criteria

## Column key paths
- col 0: Criterion
- col 1: Pass
- col 2: Fail
- col 3: Pass Rate

---

## C08

Paper: OnTrack

arXiv: 2610.12375v1

PDF file: 2610.12375v1.pdf

Claim (verbatim):

> Additionally, by deploying an abort policy on top of it, we save ∼18% of the compute that would have been burned on agents heading to failure, and 83% of runs that were interrupted were actually heading to failure (5 out of every 6 aborts were correct).

### Table 6

PDF page: not recorded (find by caption)

Caption: Abort threshold sweep on severe flag density (n=150 per class, balanced). Precision is reported at the corpus base rate (81% of traces unresolved), which is the deployment-relevant figure; on the balanced sample it is necessarily near 50%.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 |
|---|---|---|---|---|---|---|
| 0 | H | Threshold | True stop | False stop | Cost saved | Prec. (dep.) |
| 1 | R | 0.20 | 33.3% | 29.3% | 28.0% | 83% |
| 2 | R | 0.40 | 27.3% | 26.7% | 20.9% | 81% |
| 3 | R | 0.60 | 23.3% | 20.7% | 17.9% | 83% |
| 4 | R | 0.70 | 20.7% | 19.3% | 15.6% | 82% |

## Row key paths
- row 1: 0.20
- row 2: 0.40
- row 3: 0.60
- row 4: 0.70

## Column key paths
- col 0: Threshold
- col 1: True stop
- col 2: False stop
- col 3: Cost saved
- col 4: Prec. (dep.)

---

## C09

Paper: Semi-OPD: When Do We Need On-Policy Distillation?

arXiv: 2610.11291v1

PDF file: 2610.11291v1.pdf

Claim (verbatim):

> We evaluate across 17 teacher–student pairs spanning 1.5B to 235B parameters and three model families in both thinking and non-thinking modes, covering the most commonly used student–teacher pairs in the OPD literature.

### Table 3

PDF page: not recorded (find by caption)

Caption: All 17 teacher–student pairs, sorted by AUC gain of Semi-OPD\xspaceover OPD. Model names link to the exact Hugging Face checkpoints used. Mode: T = thinking / long chain-of-thought, NT = non-thinking. Cap: maximum response length of training rollouts, shared by both Semi-OPD\xspaceand OPD. Overlap: top-64 overlap between the initial student and the teacher, in %. Last-step: Semi-OPD\xspaceminus OPD at the last step both methods evaluated. AUC: signed area between the two accuracy curves over the steps both methods evaluated, divided by the length of that span. Gains are avg@32 points on the four-benchmark mean. R1-Distill = DeepSeek-R1-Distill-Qwen; Cascade-2 = Nemotron-Cascade-2 (SFT): the linked student after one epoch of SFT on teacher rollouts. †Evaluated with a 40,960-token response limit; all other pairs use 32,768.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  |  |  | Train Len | Init. | Gain [cs=2] | < |
| 1 | H | # | Student | Teacher | Mode | Cap | Overlap | Last-step | AUC |
| 2 | R | n | Qwen3-1.7B | Qwen3-30B-A3B-Thinking | T | 16K | 58.9 | +9.4 | +7.57 |
| 3 | R | a | Qwen3-1.7B | Qwen3-4B-Instruct-2507 | NT | 4K | 62.5 | +9.5 | +7.09 |
| 4 | R | p | Qwen3-4B | Qwen3-30B-A3B-Thinking | T | 16K | 63.8 | +6.2 | +6.22 |
| 5 | R | o | Qwen3-14B | Qwen3-235B-A22B-Thinking | T | 16K | 63.4 | +13.1 | +5.85 |
| 6 | R | b | Qwen3-1.7B | Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 59.8 | +6.8 | +5.18 |
| 7 | R | f | Qwen3-4B | Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 62.5 | +4.2 | +4.61 |
| 8 | R | c | Qwen3-1.7B | Qwen3-235B-A22B-Instruct-2507 | NT | 4K | 56.9 | +2.6 | +3.27 |
| 9 | R | g | Qwen3-1.7B (SFT) | Qwen3-4B-Instruct-2507 | NT | 4K | 62.9 | +2.4 | +2.05 |
| 10 | R | h | Qwen3-4B (SFT) | Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 63.1 | +0.9 | +1.50 |
| 11 | R | d | Qwen3-1.7B | Qwen3-4B | NT | 4K | 70.0 | +1.1 | +1.35 |
| 12 | R | m | R1-Distill-7B | DeepCoder-14B | T | 16K | 73.9 | +1.5 | +0.97 |
| 13 | R | e | Qwen3-1.7B | Qwen3-8B | NT | 4K | 69.4 | +0.8 | +0.54 |
| 14 | R | j | R1-Distill-1.5B | Polaris-7B | T | 16K | 69.7 | +0.1 | +0.24 |
| 15 | R | q | Cascade-2-30B-A3B | Cascade-2-Math-Expert† | T | 16K | 89.3 | -0.1 | +0.09 |
| 16 | R | l | R1-Distill-7B | Light-R1-14B | T | 16K | 72.0 | -1.7 | -0.30 |
| 17 | R | k | R1-Distill-7B | Polaris-7B | T | 16K | 86.8 | -2.6 | -0.68 |
| 18 | R | i | R1-Distill-1.5B | JustRL-1.5B | T | 16K | 79.7 | +1.4 | -1.36 |

## Row key paths
- row 2: n > Qwen3-1.7B > Qwen3-30B-A3B-Thinking > T > 16K
- row 3: a > Qwen3-1.7B > Qwen3-4B-Instruct-2507 > NT > 4K
- row 4: p > Qwen3-4B > Qwen3-30B-A3B-Thinking > T > 16K
- row 5: o > Qwen3-14B > Qwen3-235B-A22B-Thinking > T > 16K
- row 6: b > Qwen3-1.7B > Qwen3-30B-A3B-Instruct-2507 > NT > 4K
- row 7: f > Qwen3-4B > Qwen3-30B-A3B-Instruct-2507 > NT > 4K
- row 8: c > Qwen3-1.7B > Qwen3-235B-A22B-Instruct-2507 > NT > 4K
- row 9: g > Qwen3-1.7B (SFT) > Qwen3-4B-Instruct-2507 > NT > 4K
- row 10: h > Qwen3-4B (SFT) > Qwen3-30B-A3B-Instruct-2507 > NT > 4K
- row 11: d > Qwen3-1.7B > Qwen3-4B > NT > 4K
- row 12: m > R1-Distill-7B > DeepCoder-14B > T > 16K
- row 13: e > Qwen3-1.7B > Qwen3-8B > NT > 4K
- row 14: j > R1-Distill-1.5B > Polaris-7B > T > 16K
- row 15: q > Cascade-2-30B-A3B > Cascade-2-Math-Expert† > T > 16K
- row 16: l > R1-Distill-7B > Light-R1-14B > T > 16K
- row 17: k > R1-Distill-7B > Polaris-7B > T > 16K
- row 18: i > R1-Distill-1.5B > JustRL-1.5B > T > 16K

## Column key paths
- col 0: #
- col 1: Student
- col 2: Teacher
- col 3: Mode
- col 4: Train Len > Cap
- col 5: Init. > Overlap
- col 6: Gain > Last-step
- col 7: Gain > AUC

---

## C10

Paper: JevKT: When Few or No Learners Are Logged?

arXiv: 2610.11135v1

PDF file: 2610.11135v1.pdf

Claim (verbatim):

> Without any data from the target platform, Jev0-shot reaches .706 mean AUC (first block of Table 1).

### Table 1

PDF page: not recorded (find by caption)

Caption: Cold-start AUC (P1) of Jev against the best deep KT and the best LLM-based KT baseline with N training learners (mean over 5 seeds). Without training data, Jev0-shot is above LLM-based KT on all seven datasets and above deep KT trained on 8 learners on average; JevKT stays ahead of deep KT up to N=64 on average. Wins: datasets on which Jev beats every baseline in its block. †Best of 28 pyKT models, selected on test. ‡LOKT, the strongest LLM-based KT baseline. ∘N=0 value repeated (no answer options). §Reported by LLM-KT on its own split; not ranked. All models: Appendix . Best in bold, second best underlined.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H | N | Method | ASSIST09 | NIPS34 | XES3G5M | DBE-KT22 | Alg05 | Junyi | ASSIST17 | Avg | Wins |
| 1 | R | 0 [rs=3] | Best deep KT† | – | – | – | – | – | – | – | – |  |
| 2 | R | ^ | Best LLM-based KT‡ | .715 | .662 | .699 | .688 | .656 | .671 | .608 | .671 |  |
| 3 | R | ^ | Jev0-shot | .738 | .691 | .725 | .742 | .698 | .700 | .648 | .706 | 7/7 |
| 4 | R | 8 [rs=3] | Best deep KT† | .700 | .653 | .689 | .793 | .711 | .652 | .624 | .689 |  |
| 5 | R | ^ | Best LLM-based KT‡ | .707 | .662 | .699∘ | .699 | .656∘ | .671∘ | .608∘ | .672 |  |
| 6 | R | ^ | JevKT | .735 | .707 | .720 | .821 | .734 | .701 | .638 | .722 | 7/7 |
| 7 | R | 16 [rs=3] | Best deep KT† | .706 | .696 | .706 | .808 | .718 | .691 | .626 | .707 |  |
| 8 | R | ^ | Best LLM-based KT‡ | .707 | .663 | .699∘ | .701 | .656∘ | .671∘ | .608∘ | .672 |  |
| 9 | R | ^ | JevKT | .737 | .734 | .720 | .834 | .738 | .704 | .646 | .730 | 7/7 |
| 10 | R | 32 [rs=3] | Best deep KT† | .724 | .732 | .708 | .816 | .744 | .697 | .639 | .723 |  |
| 11 | R | ^ | Best LLM-based KT‡ | .707 | .660 | .699∘ | .701 | .656∘ | .671∘ | .608∘ | .672 |  |
| 12 | R | ^ | JevKT | .737 | .752 | .728 | .838 | .751 | .709 | .656 | .739 | 7/7 |
| 13 | R | 64 [rs=3] | Best deep KT† | .734 | .750 | .720 | .846 | .777 | .704 | .668 | .743 |  |
| 14 | R | ^ | Best LLM-based KT‡ | .703 | .660 | .699∘ | .699 | .656∘ | .671∘ | .608∘ | .671 |  |
| 15 | R | ^ | JevKT | .745 | .762 | .739 | .838 | .762 | .715 | .667 | .747 | 4/7 |
| 16 | R | 128 [rs=3] | Best deep KT† | .739 | .768 | .739 | .852 | .792 | .708 | .692 | .756 |  |
| 17 | R | ^ | Best LLM-based KT‡ | .704 | .658 | .699∘ | .697 | .656∘ | .671∘ | .608∘ | .670 |  |
| 18 | R | ^ | JevKT | .745 | .764 | .747 | .837 | .774 | .727 | .680 | .753 | 3/7 |
| 19 | R | 256 [rs=3] | Best deep KT† | .746 | .774 | .757 | .852 | .808 | .723 | .705 | .766 |  |
| 20 | R | ^ | Best LLM-based KT‡ | .706 | .659 | .699∘ | .692 | .656∘ | .671∘ | .608∘ | .670 |  |
| 21 | R | ^ | JevKT | .746 | .769 | .752 | .838 | .779 | .738 | .687 | .758 | 1/7 |
| 22 | R | all [rs=3] | Best deep KT† | .794 | .789 | .791 | .862 | .814 | .794 | .743 | .798 |  |
| 23 | R | ^ | Best LLM-based KT‡ | .705 | .666 | .699∘ | .700 | .656∘ | .671∘ | .608∘ | .672 |  |
| 24 | R | ^ | JevKT | .780 | .774 | .758 | .829 | .780 | .771 | .701 | .770 | 0/7 |
| 25 | R |  | LLM-KT (reported) | .887§ | – | – | – | – | – | – | – |  |

## Row key paths
- row 1: 0
- row 2: 0
- row 3: 0
- row 4: 8
- row 5: 8
- row 6: 8
- row 7: 16
- row 8: 16
- row 9: 16
- row 10: 32
- row 11: 32
- row 12: 32
- row 13: 64
- row 14: 64
- row 15: 64
- row 16: 128
- row 17: 128
- row 18: 128
- row 19: 256
- row 20: 256
- row 21: 256
- row 22: all
- row 23: all
- row 24: all
- row 25: LLM-KT (reported)

## Column key paths
- col 0: N
- col 1: Method
- col 2: ASSIST09
- col 3: NIPS34
- col 4: XES3G5M
- col 5: DBE-KT22
- col 6: Alg05
- col 7: Junyi
- col 8: ASSIST17
- col 9: Avg
- col 10: Wins

---

## C11

Paper: SFT-as-Context

arXiv: 2610.11132v1

PDF file: 2610.11132v1.pdf

Claim (verbatim):

> Across 19 parent-SFT model pairs and 11 benchmarks, SFT-as-context remains close to the SFT models on fine-tuned capabilities, with gaps of only 2.2 and 2.1 percentage points on AIME 2024 and LiveCodeBench and 2.0 macro MAE on NutriBench-English, while staying within 2.2 percentage points of the parent models on general capabilities on average.

### Table 1

PDF page: not recorded (find by caption)

Caption: SFT-as-context successfully mitigates the forgetting of general capabilities and maintains high fine-tuned capabilities compared to SFT across all benchmarks. Higher is better except for NutriBench macro MAE, where lower is better. For IFEval, we report prompt-level strict accuracy (PSA). † denotes joint-capability settings, where the same queries require both fine-tuned and general capabilities. The performance recovery rate (R) is defined in Equation and reported as a percentage. The metric results are averaged over 8 parent-SFT model pairs for mathematics, 8 for coding, and 3 for nutrition. Best results are bolded and second-best results are underlined.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 |
|---|---|---|---|---|---|---|---|
| 0 | H | Benchmark | Metric | Parent | SFT | SFT-as-Context | R (↑) |
| 1 | S | Mathematics [cs=6] | < | < | < | < | < |
| 2 | S | Fine-Tuned Capabilities [cs=6] | < | < | < | < | < |
| 3 | R | AIME 2024 | Accuracy | 11.3 | 56.0 | 53.8 | 95.0 |
| 4 | R | MathIF† | Math Correctness | 40.6 | 65.0 | 64.0 | 95.9 |
| 5 | S | General Capabilities [cs=6] | < | < | < | < | < |
| 6 | R | IFEval | PSA | 71.3 | 52.7 | 69.8 | 91.6 |
| 7 | R | MathIF† | Hard IF | 50.1 | 21.3 | 45.8 | 85.1 |
| 8 | R | MGSM | Answer-Prefix Accuracy | 90.6 | 50.2 | 87.5 | 92.2 |
| 9 | S | Coding [cs=6] | < | < | < | < | < |
| 10 | S | Fine-Tuned Capabilities [cs=6] | < | < | < | < | < |
| 11 | R | LiveCodeBench | Pass@1 | 20.1 | 55.5 | 53.4 | 94.1 |
| 12 | R | LiveCodeBenchIF† | Pass@1 | 17.3 | 53.8 | 51.2 | 92.9 |
| 13 | S | General Capabilities [cs=6] | < | < | < | < | < |
| 14 | R | IFEval | PSA | 75.0 | 45.1 | 74.8 | 99.4 |
| 15 | R | LiveCodeBenchIF† | Exactly 3 Comment Lines | 31.5 | 19.1 | 31.1 | 96.6 |
| 16 | R | SQuAD2.0 | Correctness | 86.1 | 62.5 | 83.3 | 88.3 |
| 17 | R | FQuAD2.0 | Correctness | 81.0 | 66.2 | 78.2 | 81.3 |
| 18 | R | CoQA | Correctness | 95.9 | 62.2 | 93.1 | 91.7 |
| 19 | R | ACPBench | Overall Accuracy | 77.0 | 65.9 | 78.8 | 116.2 |
| 20 | S | Nutrition [cs=6] | < | < | < | < | < |
| 21 | S | Fine-Tuned Capabilities [cs=6] | < | < | < | < | < |
| 22 | R | NutriBench-English | Macro MAE ↓ | 35.3 | 16.4 | 18.4 | 89.2 |
| 23 | R | NutriBench-Non-English† | Macro MAE ↓ | 85.6 | 59.6 | 63.6 | 84.6 |
| 24 | S | General Capabilities [cs=6] | < | < | < | < | < |
| 25 | R | NutriBench-Non-English† | Language Consistency | 77.3 | 1.9 | 73.7 | 95.2 |
| 26 | R | NutriBench-Non-Food | Acknowledge Non-Food | 98.8 | 22.6 | 98.0 | 98.9 |

## Row key paths
- row 3: Fine-Tuned Capabilities > AIME 2024 > Accuracy
- row 4: Fine-Tuned Capabilities > MathIF† > Math Correctness
- row 6: General Capabilities > IFEval > PSA
- row 7: General Capabilities > MathIF† > Hard IF
- row 8: General Capabilities > MGSM > Answer-Prefix Accuracy
- row 11: Fine-Tuned Capabilities > LiveCodeBench > Pass@1
- row 12: Fine-Tuned Capabilities > LiveCodeBenchIF† > Pass@1
- row 14: General Capabilities > IFEval > PSA
- row 15: General Capabilities > LiveCodeBenchIF† > Exactly 3 Comment Lines
- row 16: General Capabilities > SQuAD2.0 > Correctness
- row 17: General Capabilities > FQuAD2.0 > Correctness
- row 18: General Capabilities > CoQA > Correctness
- row 19: General Capabilities > ACPBench > Overall Accuracy
- row 22: Fine-Tuned Capabilities > NutriBench-English > Macro MAE ↓
- row 23: Fine-Tuned Capabilities > NutriBench-Non-English† > Macro MAE ↓
- row 25: General Capabilities > NutriBench-Non-English† > Language Consistency
- row 26: General Capabilities > NutriBench-Non-Food > Acknowledge Non-Food

## Column key paths
- col 0: Benchmark
- col 1: Metric
- col 2: Parent
- col 3: SFT
- col 4: SFT-as-Context
- col 5: R (↑)

---

## C12

Paper: Semi-OPD: When Do We Need On-Policy Distillation?

arXiv: 2610.11291v1

PDF file: 2610.11291v1.pdf

Claim (verbatim):

> The two quantities are strongly correlated (Pearson’s 𝑟= −0.73 across 17 pairs): pairs with lower initial overlap ratios tend to benefit substantially more from Semi-OPD, while OPD is only needed for pairs with high overlap ratios.

### Table 3

PDF page: not recorded (find by caption)

Caption: All 17 teacher–student pairs, sorted by AUC gain of Semi-OPD\xspaceover OPD. Model names link to the exact Hugging Face checkpoints used. Mode: T = thinking / long chain-of-thought, NT = non-thinking. Cap: maximum response length of training rollouts, shared by both Semi-OPD\xspaceand OPD. Overlap: top-64 overlap between the initial student and the teacher, in %. Last-step: Semi-OPD\xspaceminus OPD at the last step both methods evaluated. AUC: signed area between the two accuracy curves over the steps both methods evaluated, divided by the length of that span. Gains are avg@32 points on the four-benchmark mean. R1-Distill = DeepSeek-R1-Distill-Qwen; Cascade-2 = Nemotron-Cascade-2 (SFT): the linked student after one epoch of SFT on teacher rollouts. †Evaluated with a 40,960-token response limit; all other pairs use 32,768.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  |  |  | Train Len | Init. | Gain [cs=2] | < |
| 1 | H | # | Student | Teacher | Mode | Cap | Overlap | Last-step | AUC |
| 2 | R | n | Qwen3-1.7B | Qwen3-30B-A3B-Thinking | T | 16K | 58.9 | +9.4 | +7.57 |
| 3 | R | a | Qwen3-1.7B | Qwen3-4B-Instruct-2507 | NT | 4K | 62.5 | +9.5 | +7.09 |
| 4 | R | p | Qwen3-4B | Qwen3-30B-A3B-Thinking | T | 16K | 63.8 | +6.2 | +6.22 |
| 5 | R | o | Qwen3-14B | Qwen3-235B-A22B-Thinking | T | 16K | 63.4 | +13.1 | +5.85 |
| 6 | R | b | Qwen3-1.7B | Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 59.8 | +6.8 | +5.18 |
| 7 | R | f | Qwen3-4B | Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 62.5 | +4.2 | +4.61 |
| 8 | R | c | Qwen3-1.7B | Qwen3-235B-A22B-Instruct-2507 | NT | 4K | 56.9 | +2.6 | +3.27 |
| 9 | R | g | Qwen3-1.7B (SFT) | Qwen3-4B-Instruct-2507 | NT | 4K | 62.9 | +2.4 | +2.05 |
| 10 | R | h | Qwen3-4B (SFT) | Qwen3-30B-A3B-Instruct-2507 | NT | 4K | 63.1 | +0.9 | +1.50 |
| 11 | R | d | Qwen3-1.7B | Qwen3-4B | NT | 4K | 70.0 | +1.1 | +1.35 |
| 12 | R | m | R1-Distill-7B | DeepCoder-14B | T | 16K | 73.9 | +1.5 | +0.97 |
| 13 | R | e | Qwen3-1.7B | Qwen3-8B | NT | 4K | 69.4 | +0.8 | +0.54 |
| 14 | R | j | R1-Distill-1.5B | Polaris-7B | T | 16K | 69.7 | +0.1 | +0.24 |
| 15 | R | q | Cascade-2-30B-A3B | Cascade-2-Math-Expert† | T | 16K | 89.3 | -0.1 | +0.09 |
| 16 | R | l | R1-Distill-7B | Light-R1-14B | T | 16K | 72.0 | -1.7 | -0.30 |
| 17 | R | k | R1-Distill-7B | Polaris-7B | T | 16K | 86.8 | -2.6 | -0.68 |
| 18 | R | i | R1-Distill-1.5B | JustRL-1.5B | T | 16K | 79.7 | +1.4 | -1.36 |

## Row key paths
- row 2: n > Qwen3-1.7B > Qwen3-30B-A3B-Thinking > T > 16K
- row 3: a > Qwen3-1.7B > Qwen3-4B-Instruct-2507 > NT > 4K
- row 4: p > Qwen3-4B > Qwen3-30B-A3B-Thinking > T > 16K
- row 5: o > Qwen3-14B > Qwen3-235B-A22B-Thinking > T > 16K
- row 6: b > Qwen3-1.7B > Qwen3-30B-A3B-Instruct-2507 > NT > 4K
- row 7: f > Qwen3-4B > Qwen3-30B-A3B-Instruct-2507 > NT > 4K
- row 8: c > Qwen3-1.7B > Qwen3-235B-A22B-Instruct-2507 > NT > 4K
- row 9: g > Qwen3-1.7B (SFT) > Qwen3-4B-Instruct-2507 > NT > 4K
- row 10: h > Qwen3-4B (SFT) > Qwen3-30B-A3B-Instruct-2507 > NT > 4K
- row 11: d > Qwen3-1.7B > Qwen3-4B > NT > 4K
- row 12: m > R1-Distill-7B > DeepCoder-14B > T > 16K
- row 13: e > Qwen3-1.7B > Qwen3-8B > NT > 4K
- row 14: j > R1-Distill-1.5B > Polaris-7B > T > 16K
- row 15: q > Cascade-2-30B-A3B > Cascade-2-Math-Expert† > T > 16K
- row 16: l > R1-Distill-7B > Light-R1-14B > T > 16K
- row 17: k > R1-Distill-7B > Polaris-7B > T > 16K
- row 18: i > R1-Distill-1.5B > JustRL-1.5B > T > 16K

## Column key paths
- col 0: #
- col 1: Student
- col 2: Teacher
- col 3: Mode
- col 4: Train Len > Cap
- col 5: Init. > Overlap
- col 6: Gain > Last-step
- col 7: Gain > AUC

---

## C13

Paper: Residual Advantage (RA)

arXiv: 2610.11519v1

PDF file: 2610.11519v1.pdf

Claim (verbatim):

> Removing either baseline, replacing the residual by the log ratio, or adding direct supervision of the teacher's top token lowers performance.

### Table 4

PDF page: not recorded (find by caption)

Caption: The same teacher-peak branch slightly helps sampled OPD but lowers both students trained with the verifier. Change in three-seed macro score when the branch is added, Qwen3-1.7B-Base, in points. The weight λ multiplies the branch's teacher part and, with RA, also the sampled guidance. Absolute, benchmark, and per-seed scores are in Appendix .

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  | Effect of the teacher-peak branch [cs=7] | < | < | < | < | < | < |
| 1 | H |  | Sampled OPD | REINFORCE++ [cs=3] | < | < | RA+REINFORCE++ [cs=3] | < | < |
| 2 | H |  | no weight | λ=5 | λ=10 | λ=20 | λ=5 | λ=10 | λ=20 |
| 3 | R | Δ macro Avg@8 | +0.30 | -0.38 | -0.88 | -1.76 | -2.05 | -2.07 | -2.16 |
| 4 | R | Δ macro Pass@8 | +0.64 | -0.46 | -0.86 | -2.11 | -3.91 | -3.41 | -3.89 |

## Row key paths
- row 3: Δ macro Avg@8
- row 4: Δ macro Pass@8

## Column key paths
- col 0: 
- col 1: Effect of the teacher-peak branch > Sampled OPD > no weight
- col 2: Effect of the teacher-peak branch > REINFORCE++ > λ=5
- col 3: Effect of the teacher-peak branch > REINFORCE++ > λ=10
- col 4: Effect of the teacher-peak branch > REINFORCE++ > λ=20
- col 5: Effect of the teacher-peak branch > RA+REINFORCE++ > λ=5
- col 6: Effect of the teacher-peak branch > RA+REINFORCE++ > λ=10
- col 7: Effect of the teacher-peak branch > RA+REINFORCE++ > λ=20

---

## C14

Paper: Universal Textual Teaching (UTT)

arXiv: 2610.12114v1

PDF file: 2610.12114v1.pdf

Claim (verbatim):

> Across the evaluated settings, UTT also outperforms representative prompt engineering and parameter-updating knowledge distillation methods.

### Table 3

PDF page: not recorded (find by caption)

Caption: Comparison with KD methods under the Pro→Qwen setting.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

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

## Row key paths
- row 2: Student
- row 3: SeqKD
- row 4: Fine-tune-CoT
- row 5: RSR
- row 6: LUFFY
- row 7: UTT (Ours)

## Column key paths
- col 0: Method
- col 1: Omni-MATH-2 > Acc.
- col 2: KernelBench > Acc.
- col 3: KernelBench > Fast1

---

## C15

Paper: Residual Advantage (RA)

arXiv: 2610.11519v1

PDF file: 2610.11519v1.pdf

Claim (verbatim):

> Both combinations surpass teacher-only OPD, and Co-RA adds a further 1.0–1.5 Avg@8 points.

### Table 10

PDF page: not recorded (find by caption)

Caption: Macro differences among runs. Differences of three-seed macro means from Tables , , and , in percentage points. Each mean and difference is computed from raw counts before rounding; subtracting the displayed macro columns can differ by 0.01.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 |
|---|---|---|---|---|---|
| 0 | H | Student | Comparison (macro, pp) | Δ Avg@8 | Δ Pass@8 |
| 1 | R | 1.7B | RA+REINFORCE++ - REINFORCE++ | +3.58 | +5.76 |
| 2 | R | 1.7B | Co-RA+REINFORCE++ - RA+REINFORCE++ | +1.45 | +1.18 |
| 3 | R | 1.7B | RA+REINFORCE++ - OPD | +1.80 | +3.90 |
| 4 | R | 1.7B | Co-RA+REINFORCE++ - OPD | +3.25 | +5.08 |
| 5 | R | 1.7B | RA+REINFORCE++ with branch - RA+REINFORCE++ | -2.07 | -3.41 |
| 6 | R | 1.7B | RA+GRPO - GRPO | +2.37 | +4.35 |
| 7 | R | 1.7B | Co-RA+GRPO - RA+GRPO | +1.23 | -0.46 |
| 8 | R | 1.7B | RA+GRPO - OPD | +2.40 | +3.45 |
| 9 | R | 1.7B | Co-RA+GRPO - OPD | +3.63 | +2.99 |
| 10 | R | 4B | RA+REINFORCE++ - REINFORCE++ | +3.26 | +6.33 |
| 11 | R | 4B | Co-RA+REINFORCE++ - RA+REINFORCE++ | +1.27 | -2.24 |
| 12 | R | 4B | RA+REINFORCE++ - OPD | +2.51 | +3.84 |
| 13 | R | 4B | Co-RA+REINFORCE++ - OPD | +3.78 | +1.60 |
| 14 | R | 4B | RA+GRPO - GRPO | +1.74 | +3.89 |
| 15 | R | 4B | Co-RA+GRPO - RA+GRPO | +1.03 | +1.09 |
| 16 | R | 4B | RA+GRPO - OPD | +2.96 | +2.73 |
| 17 | R | 4B | Co-RA+GRPO - OPD | +3.99 | +3.82 |

## Row key paths
- row 1: 1.7B > RA+REINFORCE++ - REINFORCE++
- row 2: 1.7B > Co-RA+REINFORCE++ - RA+REINFORCE++
- row 3: 1.7B > RA+REINFORCE++ - OPD
- row 4: 1.7B > Co-RA+REINFORCE++ - OPD
- row 5: 1.7B > RA+REINFORCE++ with branch - RA+REINFORCE++
- row 6: 1.7B > RA+GRPO - GRPO
- row 7: 1.7B > Co-RA+GRPO - RA+GRPO
- row 8: 1.7B > RA+GRPO - OPD
- row 9: 1.7B > Co-RA+GRPO - OPD
- row 10: 4B > RA+REINFORCE++ - REINFORCE++
- row 11: 4B > Co-RA+REINFORCE++ - RA+REINFORCE++
- row 12: 4B > RA+REINFORCE++ - OPD
- row 13: 4B > Co-RA+REINFORCE++ - OPD
- row 14: 4B > RA+GRPO - GRPO
- row 15: 4B > Co-RA+GRPO - RA+GRPO
- row 16: 4B > RA+GRPO - OPD
- row 17: 4B > Co-RA+GRPO - OPD

## Column key paths
- col 0: Student
- col 1: Comparison (macro, pp)
- col 2: Δ Avg@8
- col 3: Δ Pass@8

---

## C16

Paper: MASA: Matrix Approximation Sparse Attention

arXiv: 2610.10871v1

PDF file: 2610.10871v1.pdf

Claim (verbatim):

> MASA improves all eight matched average scores across three sparse methods, three benchmark suites, and both Llama- and Qwen-family backbones.

### Table 1

PDF page: not recorded (find by caption)

Caption: RULER results under matched sparse-attention settings. Within each framework, Original and MASA use the same sparse implementation and differ only in the ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. between Original and MASA.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  | Variant | 4K | 8K | 16K | 32K | 64K | 128K | Avg. | ΔFull |
| 1 | R | MInfer [rs=3] |  | Full Attention | 97.2 | 91.8 | 87.3 | 80.8 | 77.4 | 72.2 | 84.4 | 0 |
| 2 | R | ^ |  | Original | 97.7 | 91.2 | 88.5 | 85.0 | 82.3 | 77.6 | 87.0 | +2.6 |
| 3 | R | ^ |  | MASA | 97.93 | 91.29 | 88.50 | 85.45 | 81.57 | 78.88 | 87.27 | +2.87 |
| 4 | R | SeerAttn [rs=3] |  | Full Attention | 95.53 | 92.37 | 92.01 | 87.63 | 84.39 | 76.26 | 88.01 | 0 |
| 5 | R | ^ |  | Original | 95.53 | 92.71 | 92.02 | 88.49 | 83.48 | 73.37 | 87.60 | -0.41 |
| 6 | R | ^ |  | MASA | 95.53 | 92.74 | 92.84 | 89.56 | 84.01 | 73.85 | 88.09 | +0.08 |
| 7 | R | FlexPrefill [rs=6] | Llama [rs=3] | Full Attention | 95.67 | 93.75 | 93.03 | 87.26 | 84.37 | 78.13 | 88.70 | 0 |
| 8 | R | ^ | ^ | Original | 95.43 | 93.51 | 94.71 | 89.42 | 82.93 | 79.09 | 89.18 | +0.48 |
| 9 | R | ^ | ^ | MASA | 95.43 | 93.99 | 94.95 | 89.66 | 85.09 | 80.54 | 89.94 | +1.24 |
| 10 | R | ^ | Qwen [rs=3] | Full Attention | 89.90 | 88.70 | 80.77 | 79.33 | 56.49 | 17.79 | 68.83 | 0 |
| 11 | R | ^ | ^ | Original | 90.39 | 89.91 | 83.17 | 81.25 | 59.14 | 20.67 | 70.75 | +1.92 |
| 12 | R | ^ | ^ | MASA | 90.88 | 88.94 | 84.85 | 82.64 | 62.79 | 22.83 | 72.16 | +3.33 |

## Row key paths
- row 1: MInfer > Full Attention
- row 2: MInfer > Original
- row 3: MInfer > MASA
- row 4: SeerAttn > Full Attention
- row 5: SeerAttn > Original
- row 6: SeerAttn > MASA
- row 7: FlexPrefill > Llama > Full Attention
- row 8: FlexPrefill > Llama > Original
- row 9: FlexPrefill > Llama > MASA
- row 10: FlexPrefill > Qwen > Full Attention
- row 11: FlexPrefill > Qwen > Original
- row 12: FlexPrefill > Qwen > MASA

## Column key paths
- col 0: 
- col 1: 
- col 2: Variant
- col 3: 4K
- col 4: 8K
- col 5: 16K
- col 6: 32K
- col 7: 64K
- col 8: 128K
- col 9: Avg.
- col 10: ΔFull

### Table 2

PDF page: not recorded (find by caption)

Caption: InfiniteBench results under matched sparse-attention settings. Within each framework, Original and MASA use the same sparse implementation and differ only in the ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. between Original and MASA.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | c9 | c10 | c11 | c12 | c13 | c14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | H |  |  | Variant | En.Sum | En.QA | En.MC | En.Dia | Zh.QA | Code Debug | Math Find | Retr. PassKey | Retr. Number | Retr. KV | Avg. | ΔFull |
| 1 | R | MInfer [rs=3] |  | Full Attention | 20.2 | 12.4 | 67.3 | 6.0 | 12.9 | 22.1 | 26.6 | 100.0 | 100.0 | 14.4 | 38.2 | 0 |
| 2 | R | ^ |  | Original | 20.5 | 12.9 | 65.9 | 7.5 | 12.5 | 22.3 | 33.1 | 100.0 | 100.0 | 12.8 | 38.8 | +0.6 |
| 3 | R | ^ |  | MASA | 19.73 | 12.15 | 66.81 | 8.50 | 12.28 | 22.84 | 33.43 | 100.00 | 100.00 | 16.20 | 39.20 | +1.00 |
| 4 | R | FlexPrefill [rs=6] | Llama [rs=3] | Full Attention | 31.91 | 25.92 | 69.43 | 21.50 | 31.95 | 16.75 | 24.29 | 99.15 | 99.66 | 60.00 | 48.06 | 0 |
| 5 | R | ^ | ^ | Original | 31.82 | 24.82 | 69.43 | 19.50 | 35.46 | 16.75 | 31.14 | 98.64 | 99.83 | 44.00 | 47.14 | -0.92 |
| 6 | R | ^ | ^ | MASA | 32.10 | 26.25 | 66.81 | 19.50 | 33.66 | 20.05 | 29.14 | 98.31 | 99.66 | 54.40 | 47.99 | -0.07 |
| 7 | R | ^ | Qwen [rs=3] | Full Attention | 4.65 | 5.57 | 34.50 | 9.00 | 11.27 | 24.87 | 24.57 | 95.42 | 75.42 | 0.00 | 29.53 | 0 |
| 8 | R | ^ | ^ | Original | 14.27 | 6.55 | 34.06 | 13.50 | 11.51 | 20.81 | 30.86 | 96.95 | 72.20 | 0.00 | 30.07 | +0.54 |
| 9 | R | ^ | ^ | MASA | 15.55 | 6.38 | 32.31 | 16.50 | 13.09 | 21.07 | 30.29 | 94.41 | 74.58 | 0.00 | 30.42 | +0.89 |

## Row key paths
- row 1: MInfer > Full Attention
- row 2: MInfer > Original
- row 3: MInfer > MASA
- row 4: FlexPrefill > Llama > Full Attention
- row 5: FlexPrefill > Llama > Original
- row 6: FlexPrefill > Llama > MASA
- row 7: FlexPrefill > Qwen > Full Attention
- row 8: FlexPrefill > Qwen > Original
- row 9: FlexPrefill > Qwen > MASA

## Column key paths
- col 0: 
- col 1: 
- col 2: Variant
- col 3: En.Sum
- col 4: En.QA
- col 5: En.MC
- col 6: En.Dia
- col 7: Zh.QA
- col 8: Code Debug
- col 9: Math Find
- col 10: Retr. PassKey
- col 11: Retr. Number
- col 12: Retr. KV
- col 13: Avg.
- col 14: ΔFull

### Table 3

PDF page: not recorded (find by caption)

Caption: LongBench results under matched sparse-attention settings. Within SeerAttention, Original and MASA differ only in the sparse-unit ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. and its ΔFull.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 | c4 | c5 |
|---|---|---|---|---|---|---|---|
| 0 | H | Variant | 0–4K | 4–8K | 8K+ | Avg. | ΔFull |
| 1 | R | Full Attention | 55.32 | 53.98 | 52.90 | 54.07 | 0 |
| 2 | R | Original | 55.43 | 54.49 | 52.69 | 54.20 | +0.13 |
| 3 | R | MASA | 55.45 | 54.48 | 53.16 | 54.37 | +0.30 |

## Row key paths
- row 1: Full Attention
- row 2: Original
- row 3: MASA

## Column key paths
- col 0: Variant
- col 1: 0–4K
- col 2: 4–8K
- col 3: 8K+
- col 4: Avg.
- col 5: ΔFull

---

## C17

Paper: Residual Advantage (RA)

arXiv: 2610.11519v1

PDF file: 2610.11519v1.pdf

Claim (verbatim):

> With Qwen3-1.7B-Base and Qwen3-4B-Base students and a Qwen3-8B teacher, RA combined with GRPO or REINFORCE++ improves the underlying sequence-advantage algorithm in all 24 comparisons on three mathematical benchmarks, raising macro Avg@8 by 1.7–3.6 points and Pass@8 by 3.9–6.3 points.

### Table 10

PDF page: not recorded (find by caption)

Caption: Macro differences among runs. Differences of three-seed macro means from Tables , , and , in percentage points. Each mean and difference is computed from raw counts before rounding; subtracting the displayed macro columns can differ by 0.01.

Flags: H = column-header row, S = section row, R = data row. `^` = covered by a row span above, `<` = covered by a column span.

| r | f | c0 | c1 | c2 | c3 |
|---|---|---|---|---|---|
| 0 | H | Student | Comparison (macro, pp) | Δ Avg@8 | Δ Pass@8 |
| 1 | R | 1.7B | RA+REINFORCE++ - REINFORCE++ | +3.58 | +5.76 |
| 2 | R | 1.7B | Co-RA+REINFORCE++ - RA+REINFORCE++ | +1.45 | +1.18 |
| 3 | R | 1.7B | RA+REINFORCE++ - OPD | +1.80 | +3.90 |
| 4 | R | 1.7B | Co-RA+REINFORCE++ - OPD | +3.25 | +5.08 |
| 5 | R | 1.7B | RA+REINFORCE++ with branch - RA+REINFORCE++ | -2.07 | -3.41 |
| 6 | R | 1.7B | RA+GRPO - GRPO | +2.37 | +4.35 |
| 7 | R | 1.7B | Co-RA+GRPO - RA+GRPO | +1.23 | -0.46 |
| 8 | R | 1.7B | RA+GRPO - OPD | +2.40 | +3.45 |
| 9 | R | 1.7B | Co-RA+GRPO - OPD | +3.63 | +2.99 |
| 10 | R | 4B | RA+REINFORCE++ - REINFORCE++ | +3.26 | +6.33 |
| 11 | R | 4B | Co-RA+REINFORCE++ - RA+REINFORCE++ | +1.27 | -2.24 |
| 12 | R | 4B | RA+REINFORCE++ - OPD | +2.51 | +3.84 |
| 13 | R | 4B | Co-RA+REINFORCE++ - OPD | +3.78 | +1.60 |
| 14 | R | 4B | RA+GRPO - GRPO | +1.74 | +3.89 |
| 15 | R | 4B | Co-RA+GRPO - RA+GRPO | +1.03 | +1.09 |
| 16 | R | 4B | RA+GRPO - OPD | +2.96 | +2.73 |
| 17 | R | 4B | Co-RA+GRPO - OPD | +3.99 | +3.82 |

## Row key paths
- row 1: 1.7B > RA+REINFORCE++ - REINFORCE++
- row 2: 1.7B > Co-RA+REINFORCE++ - RA+REINFORCE++
- row 3: 1.7B > RA+REINFORCE++ - OPD
- row 4: 1.7B > Co-RA+REINFORCE++ - OPD
- row 5: 1.7B > RA+REINFORCE++ with branch - RA+REINFORCE++
- row 6: 1.7B > RA+GRPO - GRPO
- row 7: 1.7B > Co-RA+GRPO - RA+GRPO
- row 8: 1.7B > RA+GRPO - OPD
- row 9: 1.7B > Co-RA+GRPO - OPD
- row 10: 4B > RA+REINFORCE++ - REINFORCE++
- row 11: 4B > Co-RA+REINFORCE++ - RA+REINFORCE++
- row 12: 4B > RA+REINFORCE++ - OPD
- row 13: 4B > Co-RA+REINFORCE++ - OPD
- row 14: 4B > RA+GRPO - GRPO
- row 15: 4B > Co-RA+GRPO - RA+GRPO
- row 16: 4B > RA+GRPO - OPD
- row 17: 4B > Co-RA+GRPO - OPD

## Column key paths
- col 0: Student
- col 1: Comparison (macro, pp)
- col 2: Δ Avg@8
- col 3: Δ Pass@8
