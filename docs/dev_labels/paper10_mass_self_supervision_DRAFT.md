# Paper 10 - MASS, Recursive Self-Improvement through Multi-Agent Self-Supervision (arXiv 2610.12176v1) - DRAFT dev labels
Status: DRAFT. Labelled under docs/LABEL_RUBRIC.md before any Prism output. Verified against the PDF.
Row format: id | claim | section/page | deciding evidence | label | rule | confidence

## Refusal-family rows (3, all partial; 0 not_supported)

P10-R1 | Abstract: "Because the improved model subsequently acts as a better optimizer and evaluator, this alternating framework enables a continuous, recursive bootstrapping of the model's capabilities." | Abstract p1; Table 7 App C; Sec J p38 | Only two MASS cycles were run (L0 -> L1 -> L2). Table 7: Terminal-Bench 2.0 pass 37.5 / 35.3 / 35.2; SWE-bench Verified 62.6 / 61.8 / 61.1 (both fall); DSBench 0.473 / 0.465 / 0.482 (non-monotone); the four research benchmarks do rise (e.g. ScienceAgentBench 28.8 / 30.4 / 31.7). Sec J: "The recursive loop here is empirical. ... it provides no guarantee that every future cycle improves." "Continuous" is untested beyond two cycles and "the model's capabilities" includes coding/CLI tasks that declined. | partially_supported | R3 and R5 | 0.65 (Reading 2 = not_supported)

P10-R2 | Abstract: "multi-agent traces are also more training-efficient: a student trained on them outperforms a single-agent student trained on 1.4x more training tokens." (also Sec 1 p3) | Abstract p1; Sec 4.4 p8; Table 8 and Sec D.1 p22 | Numbers match: M+ 68.3% win share at 28.82M processed tokens vs S++ 64.0% at 42.00M (42.00/28.82 = 1.46x; 31.4% fewer tokens; +4.3 pp; 50 rollout pairs). Table 8 caption: "M+ has broader training-task coverage and a different sampler, so it is not a matched-data control." Sec D.1: differences in sampling, data and checkpoint selection "limit what can be attributed to teacher composition alone"; M+ uses validation-loss checkpoint selection, S+ and others use a different rule; S++ shared-train and task-60 columns are not reported. The abstract still credits the multi-agent traces. | partially_supported | R3 | 0.75

P10-R3 | Sec 4.3 Claim 1: "Optimized workflows increasingly place task-specific information in what agents communicate and how they are routed, while reducing redundant information across workflow components." | Sec 4.3 p7; Fig. 5 p8; Table 13 and Sec F.3 | Unconditional redundancy TC(Z) falls in all four estimator configurations from iteration 3 to 11. Task-centered TC(Z|T) falls in three and rises for permutation-adjusted MPNet (2.39 -> 2.57, peak 2.80 at i=9). Sec F.3: the decrease "concerns the retained path and does not hold for every proposed iterate"; estimates are descriptive text statistics from 43-51 agents. The body text hedges ("generally decreases") but the formal Claim 1 box is unhedged. | partially_supported | R3 (cell-by-cell) | 0.55

## Supported rows (8)

P10-S1 | Over two cycles the model achieves 1.2-1.6x higher score per output token on four open-ended benchmarks | Abstract p1; Fig. 2 p3 | MLR-Bench 1.60x, DSBench 1.35x, AstaBench E2E-Hard 1.28x, ScienceAgentBench 1.20x. The sentence is scoped to the four benchmarks; Terminal-Bench 0.96x and SWE-bench 0.94x are shown in the same figure. | supported | plain read | 0.95
P10-S2 | M+ reaches 68.3% with 28.82M processed tokens, 4.3 points above S++ while using 31.4% fewer tokens | Sec 4.4 p8; Table 8 | 68.3 - 64.0 = 4.3; (42.00 - 28.82) / 42.00 = 31.4%. | supported | plain read | 1.0
P10-S3 | Evaluator agreement increases from 0.73 for L0 to 0.91 for L1 and 0.93 for L2 | Sec 4.2 p7; Fig. 3c | As stated. | supported | plain read | 0.95
P10-S4 | Delegation rises 1/110 -> 48/110 -> 87/110; code handoffs 1/110 -> 42/110 -> 83/110 under bare task prompts | Sec 5.2 p9; Table 2a p10 | As stated. | supported | plain read | 1.0
P10-S5 | Among 114 audited teacher trajectories, 98 contain code handoffs and 57 contain subagent revisions; 79 and 37 were sampled for SFT | Sec 5.2 p9; Table 2b p10 | Recorded 98 / 57; sampled 79 / 37. | supported | plain read | 1.0
P10-S6 | Multi-agent executions generate about 2.4x more tokens on average and are preferred in 85.1% of external judgments overall | Sec 4.4 p8; Sec D.3 / Table 9 p23 | Mean generated tokens 141,844 vs 59,355 (ratio 2.39); all pairs 701-123 = 85.1%. Disclosed: equal task weighting gives 79.3%. | supported | plain read | 0.95
P10-S7 | Among the 10 episode pairs with similar generated trace lengths, the multi-agent preference remains 80.0% | Sec 4.4 p8; Table 9 | Comparable length: 32-8 = 80.0%. | supported | plain read | 0.95
P10-S8 | "None of the 180 MLR-Bench executions calls the delegation tool, so this result does not establish delegation as the mechanism of public-benchmark transfer" and the evidence for improvement "depends on the aggregation unit" | App C.5 p21 | 0 of 180 executions; Welch p = 0.0053 and Fisher p = 0.0004 for L2 vs L0, but paired sign test over 12 task means p = 0.2266. | supported | plain read | 0.95

## Rejected from AG (do not add as rows)
- Abstract "continuous, recursive bootstrapping" as not_supported: improvement over two cycles on four research benchmarks is real, so partial.
- Sec 1 "Optimizing inter-agent information flow can elicit collective capabilities ... other than incorporating stronger reasoning chains" and "Jointly training ... enjoys greater learning efficiency": both stated under "Two hypotheses guide us", worded as hypotheses ("can elicit"), not as results.
- Sec 4.2 "28.7% to 31.8%" vs Table 7 28.8 / 31.7: looks like a rounding artifact, no row.
- Fig. 3 caption "two research benchmarks" vs table contents: caption nit.
- Abstract "discovering the most effective distinct roles and information routing": wording strength with no clean rubric rule (Sec 3 says w*_t is the best self-judged workflow, not a certified optimum).

## Open items
- Sec 4.4 Claim 2 ("may provide more effective RSI supervision than ... a single agent's long-horizon trajectories"): single-agent controls (S, S+, S++) were trained once from L0 and never run through the RSI loop (Sec D.1). Hedged and overlaps P10-R2, not added.
- Abstract final sentence ("findings suggest ... can provide an effective signal for RSI"): hedged.
- All results use one base model (Qwen3.6-27B); external judges GPT-5.5 and Claude Opus 4.8; three test tasks.
- Figure-read values (Fig. 3b win rates, Fig. 7a curves) were not re-verified from the PDF for this draft.
