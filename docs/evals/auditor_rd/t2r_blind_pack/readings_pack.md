# Readings pack (wording only)

## C01

Paper: JevKT: When Few or No Learners Are Logged?

Claim (verbatim):
> For new learners the advantage holds from their first interactions, whereas on unseen items with all learners logged, deep KT remains ahead.

### Table 9

Caption: P2 (new learners), every cell. AUC by the position of the target in a new learner's sequence with N=8 training learners (Jev0-shot uses none), mean±SD over 5 seeds (Jev0-shot: learner-bootstrap SD of its single run); same predictions as P1. Position 1 has only 41–50 targets per dataset, so its AUC is noisy; – = one class only. †Best of 28 pyKT models, chosen on the whole (N,dataset) cell. Best in bold, second best underlined.

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

## C02

Paper: Residual Advantage (RA)

Claim (verbatim):
> Every residual variant improves on verifier-only training at every tested weight, and full RA stays above every control at every matched weight.

### Table 2

Caption: Every residual variant improves on verifier-only training at every tested weight, and full RA stays above every control at every matched weight. Qwen3-1.7B-Base with REINFORCE++; three-seed macro means in %. The weight is λ, γx, γ raw, or α as marked, with 10 the reference weight; per-seed values and sample SD are in Table .

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

## C04

Paper: MASA: Matrix Approximation Sparse Attention

Claim (verbatim):
> Norm clipping is helpful for SeerAttention and FlexPrefill-Llama, while soft norm balancing is useful in some FlexPrefill settings.

### Table 9

Caption: Full RULER probe ablation. Clip p denotes norm clipping at percentile p, and Norm α denotes soft norm balancing. The case p=– and α=– is raw MASA without norm control. Bold Avg. marks the best MASA variant within each setting.

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

## C05

Paper: MedBenchAgent

Claim (verbatim):
> We further demonstrate portability to a specialized medical domain and evaluate twelve VLMs, revealing task- and setting-specific variation obscured by aggregate scores.

### Table 10

Caption: Evaluation performance on ISIC 2018. Choice tasks report Accuracy / Macro-F1 (%), while detection reports mIoU / Acc@IoU0.5 (%). Best results for each metric are shown in bold.

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

## C06

Paper: MASA: Matrix Approximation Sparse Attention

Claim (verbatim):
> Across multiple sparse baselines, benchmarks, and LLM backbones, MASA gives consistent gains under matched settings with negligible latency overhead.

### Table 1

Caption: RULER results under matched sparse-attention settings. Within each framework, Original and MASA use the same sparse implementation and differ only in the ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. between Original and MASA.

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

Caption: InfiniteBench results under matched sparse-attention settings. Within each framework, Original and MASA use the same sparse implementation and differ only in the ranking rule; Full Attention is the reference. ΔFull is the signed Avg. difference from Full Attention. Higher is better. Bold marks the better Avg. between Original and MASA.

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

## C13

Paper: Residual Advantage (RA)

Claim (verbatim):
> Removing either baseline, replacing the residual by the log ratio, or adding direct supervision of the teacher's top token lowers performance.

### Table 4

Caption: The same teacher-peak branch slightly helps sampled OPD but lowers both students trained with the verifier. Change in three-seed macro score when the branch is added, Qwen3-1.7B-Base, in points. The weight λ multiplies the branch's teacher part and, with RA, also the sampled guidance. Absolute, benchmark, and per-seed scores are in Appendix .

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

## C14

Paper: Universal Textual Teaching (UTT)

Claim (verbatim):
> Across the evaluated settings, UTT also outperforms representative prompt engineering and parameter-updating knowledge distillation methods.

### Table 3

Caption: Comparison with KD methods under the Pro→Qwen setting.

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

## C15

Paper: Residual Advantage (RA)

Claim (verbatim):
> Both combinations surpass teacher-only OPD, and Co-RA adds a further 1.0–1.5 Avg@8 points.

### Table 10

Caption: Macro differences among runs. Differences of three-seed macro means from Tables , , and , in percentage points. Each mean and difference is computed from raw counts before rounding; subtracting the displayed macro columns can differ by 0.01.

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

