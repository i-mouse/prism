| ROW_ID | MATCH_INDEX or NO_MATCH | confidence | Reason |
| --- | --- | --- | --- |
| P7-S1 | 1 | high | Both the row and Claim 1 state verbatim that in the "OpenTelemetry debugging case followed by an unrelated implementation task, the method ended with 231,951 provider-reported prompt tokens versus 912,492 under retained history, used 50% fewer cumulative input tokens, and had an estimated API cost of $1.28–$1.44 versus approximately $4.38".

 |
| P7-S2 | 2 | high | Both the row and Claim 2 state verbatim that "Both arms passed the two-case primary behavioral oracle; neither fully satisfied the follow-up evaluation".

 |
| P7-S3 | 3 | high | Both the row and Claim 3 state verbatim that "The method made more requests and took 17% longer".

 |
| P7-S4 | 16 | medium | The row sentence and Claim 16 both state verbatim that "At primary submission the method carries 124,746 prompt tokens versus 847,674 for retained, an 85% reduction", though the row gloss also references the "75% at the final step" from Claim 17.

 |
| P7-S5 | 20 | high | Both the row and Claim 20 state verbatim that "The estimated cost is approximately 67–71% lower, even after reported cache usage is included".

 |
| P7-S6 | 27 | high | Both the row and Claim 27 state verbatim that "The method therefore shows stronger tested signal handling but weaker tested startup-failure handling".

 |
| P7-S8 | 34 | high | Both the row and Claim 34 state verbatim that "Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps".

 |
| P4-S1 | 14 | high | Both the row and Claim 14 state verbatim that "MASA improves all eight matched average scores across three sparse methods, three benchmark suites, and both Llama- and Qwen-family backbones".

 |
| P4-S2 | 19 | high | Both the row and Claim 19 state verbatim that "Across the four RULER configurations at 32K, 64K, and 128K, MASA improves 11 of 12 matched length-level scores".

 |
| P4-S3 | 20 | high | Both the row and Claim 20 state verbatim that "For every configuration, the mean gain over these longer contexts at 32K–128K exceeds that at 4K–16K".

 |
| P4-S4 | 21 | medium | The row sentence and Claim 21 both state verbatim that "At 128K, MASA improves MInference, SeerAttention, FlexPrefill-Llama, and FlexPrefill-Qwen by 1.28, 0.48, 1.45, and 2.16 points, respectively", while the 64K mention in the row gloss appears separately in Claim 22.

 |
| P4-S5 | 15 | high | Both the row and Claim 15 state verbatim that "On InfiniteBench, MASA raises FlexPrefill-Llama from 47.14 to 47.99 against a full-attention score of 48.06, recovering approximately 92% of the original average-score deficit".

 |
| P4-S6 | 16 | high | Both the row and Claim 16 state verbatim that "On RULER, MASA raises SeerAttention from 87.60 to 88.09, moving it from below the dense reference to above it".

 |
| P4-S7 | 17 | high | Both the row and Claim 17 state verbatim that "For FlexPrefill-Llama on RULER, replacing the ranking score adds 0.76 points, exceeding the original method’s 0.48-point advantage over full attention and increasing that advantage to 1.24 points".

 |
| P4-S8 | 31 | high | The row states that "Attention-output error decreases across all four evaluated framework–backbone pairs" with "all confidence intervals excluding zero", matching Claim 31's assertion of "lower attention-output error in every evaluated framework–backbone pair, with all four reported paired confidence intervals above zero".

 |
| P2-S2 | 2 | high | Both the row and Claim 2 state verbatim that "Across 19 parent-SFT model pairs and 11 benchmarks, SFT-as-context remains close to the SFT models on fine-tuned capabilities, with gaps of only 2.2 and 2.1 percentage points on AIME 2024 and LiveCodeBench and 2.0 macro MAE on NutriBench-English, while staying within 2.2 percentage points of the parent models on general capabilities on average".

 |
| P2-S3 | 9 | medium | The row sentence and Claim 9 both state verbatim that "Using SFT checkpoints collected from Hugging Face, SFT-as-context achieves 95.0% and 94.1% recovery rates of the fine-tuning gains on AIME 2024 and LiveCodeBench (Jain et al., 2025), respectively", while the "94.2% average on general capabilities" in the row gloss is in Claim 10.

 |
| P2-S4 | NO_MATCH | high | None of the extracted claims for this paper mention the row's assertion that "SFT causes substantial forgetting of general capabilities, reducing general capability scores by 33.2 percentage points on average".

 |
| P2-S5 | NO_MATCH | high | No extracted claim mentions the row's specific finding that "Qwen3-8B shows the largest drop in acknowledging non-food queries, from 99.6% to 10.7%".

 |
| P2-S6 | NO_MATCH | high | No extracted claim mentions the row's comparison between the "32B parent" and "7B ones (an average gap of −1.8 versus −7.5)".

 |
| P2-S7 | 22 | high | Both the row and Claim 22 state verbatim that "As shown in Table 2, using responses from open-source SFT models as context consistently improves the performance of a strong proprietary model on NutriBench-English, achieving lower MAE than either model alone".

 |
| P2-S8 | 25 | high | Both the row and Claim 25 state verbatim that "Specifically, the ratio of second-pass to first-pass response tokens is at most 13.0%".

 |
| P3-S1 | NO_MATCH | medium | The row combines "Jev0-shot reaches .706 mean AUC" with beating "both LOKT (.671) and the best deep knowledge-tracing model trained on 8 learners (.689), winning on 5 of 7 datasets", whereas Claim 13 omits ".706" and Claims 0 and 4 omit "LOKT (.671)" and "5/7 datasets".

 |
| P3-S2 | 15 | high | Both the row and Claim 15 state verbatim that "JevKT is ahead of the best deep KT model by +.033, +.023 and +.016 mean AUC at N=8, 16 and 32 (on 7/7, 7/7 and 7/7 datasets); the mean difference is +.004 at N=64, −.002 at N=128, −.008 at N=256 and −.028 with the full training data".

 |
| P3-S4 | 32 | high | Both the row and Claim 32 state verbatim that "A reasoning budget of 1024 or 2048 tokens never improves AUC significantly over the same model without reasoning, while one Jev pass beats Thinking-KT on all seven datasets (Holm-corrected, ∆AUC +.038 to +.073 against the budget of 2048)".

 |
| P3-S5 | 37 | high | Both the row and Claim 37 state verbatim that "One JevKT prediction takes 325 ms in a single call and costs $886 per million predictions, about 1/5 of Thinking-KT, which needs $4,360 and 41.7 s per prediction even with its ten votes issued in parallel; Jev0-shot costs $44".

 |
| P3-S6 | 29 | high | Both the row and Claim 29 state verbatim that "At N=16 the similar-learner statistic alone raises Jev0-shot from .706 to .729, 64 KC-matched shots alone to .724, and both together to .730".

 |
| P3-S7 | 18 | high | Both the row and Claim 18 state verbatim that "JevKT (.713) and Jev0-shot (.704) stay well above LOKT (.664), but the best deep KT model, trained on all learners and chosen on test, is ahead (.729; JevKT is better on 1/7 datasets; Table 10)".

 |
| P5-S1 | 1 | high | Both the row and Claim 1 state verbatim that "Across 17 teacher–student pairs ranging from 1.5B to 235B parameters, Semi-OPD outperforms OPD in 14 cases, with up to +13.6% accuracy and 11.4× training speedup".

 |
| P5-S2 | 16 | high | Both the row and Claim 16 state verbatim that "On the remaining three pairs, Semi-OPD still achieves comparable performance, with gaps of 0.1–2.6%".

 |
| P5-S3 | NO_MATCH | medium | The row states generally that "Semi-OPD outperforms standard OPD when the initial teacher–student overlap is low", whereas Claim 15 is broader with specific numbers ("14 of 17 pairs with improvements of up to ∼13% over OPD") and Claim 9 frames the comparison around "misaligned pairs" and "training efficiency".

 |
| P5-S4 | 21 | high | Both the row and Claim 21 state verbatim that "The two quantities are strongly correlated (Pearson’s 𝑟= −0.73 across 17 pairs): pairs with lower initial overlap ratios tend to benefit substantially more from Semi-OPD, while OPD is only needed for pairs with high overlap ratios".

 |
| P5-S5 | 18 | high | Both the row and Claim 18 state verbatim that "on the Qwen3-1.7B (non-thinking) and Qwen3-4B (non-thinking) students, which have low teacher–student overlap ratios, Semi-OPD outperforms all other baselines in accuracy while also being the most efficient, e.g., achieving +7.1% and +8.8% higher accuracy with 35× and 19.5× less training time than Relay-OPD".

 |
| P5-S6 | 19 | high | Both the row and Claim 19 state verbatim that "On the Nemotron-Cascade-2 pair, which has a high overlap ratio of approximately 89%, our Semi-OPD remains competitive with other OPD baselines and falls only slightly behind the best baseline by 0.7% accuracy, while reducing the training time by 2.2x as compared to FastOPD and 4.5x compared to OPD".

 |
| P5-S7 | 20 | high | Both the row and Claim 20 state verbatim that "The overall accuracy–training-efficiency trade-off is shown in Fig. 1, where Semi-OPD achieves up to an 11.4× speedup over standard OPD and a 2.7× speedup over the fastest baseline, FastOPD".

 |
| P6-S1 | 2 | high | Both the row and Claim 2 state verbatim that "MedBenchAgent achieves a Task-Space F1 of 90.9%, outperforming direct task induction (79.2–80.0%) and prior-guided induction (85.1%); 994 of 1,000 sampled items from correctly identified tasks pass human audit".

 |
| P6-S2 | 15 | high | Both the row and Claim 15 state verbatim that "Table 2 shows that 994 items pass, yielding a 99.4% consistency rate".

 |
| P6-S3 | 13 | high | Both the row and Claim 13 state verbatim that "Providing T0 improves direct DeepSeek-V4-Flash induction to 85.1% F1, while MedBenchAgent further increases precision from 76.9% to 87.0% at the same 95.2% recall, reducing false positives from six to three".

 |
| P6-S4 | 14 | high | Both the row and Claim 14 state verbatim that "All methods achieve 100% EMA on matched tasks".

 |
| P6-S5 | 16 | high | Both the row and Claim 16 state verbatim that "As shown in Table 3, medical VLMs outperform general-purpose VLMs by 6.23 points in Overall Acc. but trail by 2.48 points on AC, indicating that the aggregate advantage is not uniform across tasks".

 |
| P6-S8 | NO_MATCH | high | No extracted claim mentions the row's numbers or metrics that "FA improves by 27.09 points, while AA, FT, AC, DX, and PS decrease by 9.37, 1.22, 0.53, 4.85, and 7.50 points, respectively".

 |
| P1-S1 | 8 | medium | The row's core assertion that "Across two students, two estimators, and three mathematical benchmarks, RA improves all 24 three-seed benchmark means of its base estimator" ("RA improves over the base algorithm in every one of 24 tested comparisons") matches Claim 8's "24 comparisons of RA with its base estimator (two students, two estimators, three benchmarks, two metrics), and RA improves all 24 three-seed means", though the row's source sentence also appends clauses on OPD and Co-RA.

 |
| P1-S2 | 3 | high | Both the row and Claim 3 state verbatim that "With Qwen3-1.7B-Base and Qwen3-4B-Base students and a Qwen3-8B teacher, RA combined with GRPO or REINFORCE++ improves the underlying sequence-advantage algorithm in all 24 comparisons on three mathematical benchmarks, raising macro Avg@8 by 1.7–3.6 points and Pass@8 by 3.9–6.3 points".

 |
| P1-S3 | 4 | high | Both the row and Claim 4 state verbatim that "Both combinations surpass teacher-only OPD, and Co-RA adds a further 1.0–1.5 Avg@8 points".

 |
| P1-S4 | 14 | high | Both the row and Claim 14 state verbatim that "Co-RA adds 1.03–1.45 macro Avg@8 points to the four RA runs, and Avg@8 rises in all twelve benchmark means".

 |
| P1-S5 | 17 | high | Both the row and Claim 17 state verbatim that "From K = 8 to K = 512 for the 1.7B REINFORCE++ runs (Appendix D.7), the macro margin of RA over the untrained student grows from 13.4 to 16.9 points, and its margins over REINFORCE++ and OPD from 5.8 to 10.4 and from 3.9 to 6.8, while that of verifier-only training narrows from 7.6 to 6.6".

 |
| P1-S6 | NO_MATCH | high | The row states that "Every residual variant improves on verifier-only training at every tested weight, and full RA stays above every control at every matched weight", whereas Claim 22 is narrower ("All tested weights improve both macro scores over verifier-only training") and Claim 24 only compares against the "full-vocabulary squared-distance loss".

 |
| P1-S7 | NO_MATCH | medium | The row states that "The probability residual with both baselines is the best construction, and no log-ratio variant reaches it at any swept weight", whereas Claim 23 adds different numbers ("by 1.21 Avg@8 and 1.70 Pass@8 points over the best log variant", "clipped to [−5, 5]") and compares the log ratio to "verifier-only training" rather than stating that full RA is the best construction overall.

 |
| P1-S8 | 16 | high | Both the row and Claim 16 state verbatim that "Yet each adapted teacher scores 0.8–2.3 macro Avg@8 and 0.7–3.5 Pass@8 points below the frozen teacher (Appendix D.9), while the students it guides improve: it is a better guide, not a better solver".

 |
| P1-S9 | NO_MATCH | high | No extracted claim mentions the row's figures that "On the 256 offline responses of Appendix C.2, the local advantages average to 3 × 10−4 per token" or "an SD below 0.03".

 |
| P11-S1 | 6 | high | Both the row and Claim 6 state verbatim that "Relative to the unprimed Student baselines, UTT improves KernelBench accuracy from 9.4% to 48.6%, Fast1 from 9% to 35%, and mathematical reasoning accuracy from 27.6% to 51.7%".

 |
| P11-S2 | 16 | high | Both the row and Claim 16 state verbatim that "The Flash-derived Primer improves Qwen by 32.0, 25, and 25.8 percentage points in KernelBench accuracy, Fast1, and Math accuracy, respectively".

 |
| P11-S3 | 17 | high | Both the row and Claim 17 state verbatim that "The Qwen-derived Primer improves Flash by 34.4, 21, and 16.1 percentage points on the same metrics".

 |
| P11-S4 | 19 | high | Both the row and Claim 19 state verbatim that "It improves Flash by 38.8, 30, and 19.0 percentage points on the three metrics, demonstrating that UTT remains effective with different Teachers".

 |
| P11-S6 | NO_MATCH | high | No extracted claim mentions the row's baseline finding that "Teacher summary improves Flash but is inconsistent on Qwen".

 |
| P11-S7 | 28 | high | Both the row and Claim 28 state verbatim that "With Student parameters fixed, UTT exceeds the strongest baseline by 7.2, 8.2, and 4 percentage points on Omni-MATH-2 accuracy, KernelBench accuracy, and Fast1, respectively".

 |
| P11-S8 | NO_MATCH | high | No extracted claim mentions "Table 5" or "MathVerse" or that "the Primer yields positive gains for every source and transfer Student" on that benchmark.

 |
| P8-S1 | NO_MATCH | high | No extracted claim states the row's assertion that "Across the three benchmarks, most methods outperform Plain, although some match or fall below it".

 |
| P8-S2 | 9 | high | Both the row and Claim 9 state verbatim that "Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods".

 |
| P8-S3 | 10 | high | Both the row and Claim 10 state verbatim that "On StreamBench, it achieves the highest mean accuracy of 81.7%, narrowly ahead of Letta’s 81.3%".

 |
| P8-S4 | 14 | high | Both the row and Claim 14 state verbatim that "Hippocam achieves 78.9% mean progress, improving over Plain by 30.1 pp and exceeding the strongest baseline, ACE, by 16.2 pp".

 |
| P8-S5 | 15 | high | Both the row and Claim 15 state verbatim that "On FEVER, Frozen scores cluster around Plain’s 59.3%, with Hippocam and HiAgent reaching 61.8%".

 |
| P8-S6 | 16 | high | Both the row and Claim 16 state verbatim that "Only Hippocam and ACE achieve positive gains on both domain transitions, while the remaining methods show mixed, unchanged, or reduced performance".

 |
| P8-S7 | 26 | high | Both the row and Claim 26 state verbatim that "Prefix consolidation thus supports more effective subsequent work with a smaller active context".

 |
| P8-S8 | 27 | high | Both the row and Claim 27 state verbatim that "Disabling recall on the same post-ingestion MemoryAgentBench 64k snapshot reduces accuracy from 41.0% to 27.0%".

 |
| P12-S1 | 3 | high | Both the row and Claim 3 state verbatim that "We give a formal specification of our method and a concrete instantiation for interactive theorem proving in the Lean theorem prover; empirical evaluation remains future work".

 |
| P12-S2 | NO_MATCH | high | No extracted claim states the row's caveat that "The example texts are hand-written illustrations, not model outputs or empirical observations".

 |
| P12-S3 | NO_MATCH | high | No extracted claim mentions the "seed dataset" or that "the teacher is only used for the generation of the seed dataset, i.e., does not appear in the subsequent training loop".

 |
| P12-S4 | 15 | high | Both the row and Claim 15 state verbatim that "Consequently, every triple returned by Algorithm 2 contains a valid solution discovered by the solver under the triple’s hierarchy".

 |
| P12-S5 | NO_MATCH | medium | The row states definitively that "All three components are implemented using a single underlying language model with shared parameters, and we distinguish between components using role-specific prompt templates", whereas Claim 5 is weaker and conditional ("All three components share a backbone network; for example, when their inputs and outputs can be represented as text, we may use a shared language model with role-specific prompt templates").

 |
| P12-S6 | NO_MATCH | high | No extracted claim states the row's formula that "each mini-batch contains a total of b = bS + (n + 1)(bF + bH) prompt-response pairs".

 |
| P12-S7 | NO_MATCH | high | No extracted claim mentions the row's specifics that "The concrete prompt templates in Appendix A.3 use two levels (n = 1): a detailed plan z0 and a coarse proof idea z1; neither is required to consist of executable Lean commands".

 |
| P12-S8 | NO_MATCH | high | No extracted claim states the row's point that "it is a priori not clear that solution ideas derived in hindsight are suitable targets for foresight prediction".

 |
| P10-S1 | 2 | high | Both the row and Claim 2 state verbatim that "Over two MASS cycles with Qwen3.6-27B, the model achieves 1.2–1.6× higher performance per output tokens on four open-ended public benchmarks".

 |
| P10-S2 | 19 | high | Both the row and Claim 19 state verbatim that "More directly, M + reaches 68.3% with 28.82M processed supervised tokens, 4.3 points above S++ while using 31.4% fewer tokens".

 |
| P10-S3 | NO_MATCH | high | The row gives three level-specific figures ("The agreement increases from 0.73 for L(0) to 0.91 for L(1) and 0.93 for L(2)"), whereas Claim 7 omits the intermediate 0.91 L(1) value and adds workflow speed ("The trained model discovers high-quality workflows faster, and the evaluator accuracy increases from 73% to 93%").

 |
| P10-S4 | 20 | high | Both the row and Claim 20 state verbatim that "Delegation rises from 1/110 trajectories for L(0) to 48/110 for L(1) and 87/110 for L(2), while code handoffs rise from 1/110 to 42/110 and 83/110, respectively".

 |
| P10-S5 | NO_MATCH | high | No extracted claim mentions the row's audit numbers that "Among 114 audited teacher trajectories, 98 contain code handoffs and 57 contain subagent revisions; 79 and 37 of these trajectories, respectively, were sampled for SFT".

 |
| P10-S6 | NO_MATCH | high | No extracted claim states that "Multi-agent executions generate approximately 2.4× more tokens on average than single-agent executions and are preferred in 85.1% of external judgments overall".

 |
| P10-S7 | NO_MATCH | high | No extracted claim states that "Among the 10 episode pairs with similar generated trace lengths, the multi-agent preference remains 80.0%".

 |
| P10-S8 | NO_MATCH | high | No extracted claim mentions that "None of the 180 MLR-Bench executions calls the delegation tool".

 |
| P9-S1 | 1 | high | Both the row and Claim 1 state verbatim that "Evaluating based on the first 8 steps, the proposed method ranked the failing trajectories below succeeding ones better than content similarity-based approaches (+0.057 AUROC)".

 |
| P9-S2 | 16 | high | Both the row and Claim 16 state verbatim that "First, the ∆CI excludes zero at k ≤10, and the advantage is gone by k=15, where cosine catches up (.633 vs. .635): the claim is an early-trajectory advantage, precisely the regime an in-flight monitor operates in".

 |
| P9-S3 | NO_MATCH | high | No extracted claim mentions the row's ablation counts on "removing the mask" ("13/40 →14/40 false-positive traces") versus "removing the GW term" ("29/40").

 |
| P9-S4 | 2 | high | Both the row and Claim 2 state verbatim that "Additionally, by deploying an abort policy on top of it, we save ∼18% of the compute that would have been burned on agents heading to failure, and 83% of runs that were interrupted were actually heading to failure (5 out of every 6 aborts were correct)".

 |
| P9-S6 | 14 | high | Both the row and Claim 14 state verbatim that "Beyond the eight unit scenarios, a randomized campaign (40 random-DAG tasks × 7 conditions, seeded) yields: loop recall 100% at detection latency 0; hallucination recall 100% at latency 2 (the grace window); causal-inversion recall 94.1% at latency 0 via the premature-step check; and 0 false interventions over 200 benign runs".

 |
| P9-S7 | 11 | high | Both the row and Claim 11 state verbatim that "Measured on an Apple M5 Max core, the fast path runs at p50 0.85 ms / p95 1.6 ms per event at t=m=40, K=3 (p50 0.5 / p95 0.7 ms at t=m=20; p50 1.6 / p95 3.9 ms at t=80); the escalated solve matches the batch-solve runtime (≈30 ms) and is invoked only ahead of interventions".

 |
| P9-S8 | NO_MATCH | high | No extracted claim mentions the row's finding that "at the earliest checkpoint trace length alone is the single best signal (n steps .622 at k=5)" or the "k=8–10" regime comparison.

 |

### Rows with Hesitation Between Claims

* **P7-S4 (Claim 16 vs. Claim 17):** Claim 16 matches the row's primary sentence verbatim (124,746 vs. 847,674 prompt tokens, an 85% reduction at primary submission), whereas the row's right-hand summary adds "and 75% at the final step", which is stated separately in Claim 17.


* **P4-S4 (Claim 21 vs. Claim 22):** Claim 21 matches the row's 128K gains sentence verbatim (1.28, 0.48, 1.45, and 2.16 points), whereas the row's right-hand summary mentions both 128K and 64K context lengths, with the 64K gains appearing in Claim 22.


* **P4-S8 (Claim 31 vs. Claim 24):** Both Claim 31 and Claim 24 report reduced output error across all four evaluated framework–backbone pairs, but Claim 31 was chosen because it includes the qualifier that all four paired confidence intervals are above/exclude zero.


* **P2-S3 (Claim 9 vs. Claim 10):** Claim 9 matches the row's sentence verbatim (95.0% and 94.1% recovery rates on AIME 2024 and LiveCodeBench), whereas the row's right-hand summary also includes the 94.2% average recovery rate on general capabilities from Claim 10.


* **P3-S1 (Claim 13 vs. Claim 0 and Claim 4):** The row combines the .706 mean AUC figure from the first sentence of the passage with the LOKT (.671) and 8-learner deep KT (.689 on 5/7 datasets) comparisons from the following sentence; Claim 13 has the LOKT (.671) and 5/7 datasets comparison but omits .706, while Claims 0 and 4 include .706 and .689 but compare against Thinking-KT (.650) instead of LOKT (.671) and omit the 5/7 dataset count, leading to `NO_MATCH`.


* **P5-S1 and P5-S2 (Claim 1 and Claim 16 vs. Claim 8):** Claim 1 matches P5-S1 verbatim and Claim 16 matches P5-S2 verbatim, whereas Claim 8 merges both assertions into a single combined sentence.


* **P5-S3 (Claim 9 vs. Claim 15 and Claim 2):** All three claims touch on teacher–student overlap, but Claim 15 adds specific statistics (14 of 17 pairs and ~13% gain), Claim 9 frames the claim around misaligned pairs and training efficiency, and Claim 2 focuses on when OPD is beneficial, resulting in `NO_MATCH`.


* **P6-S1 (Claim 2 vs. Claim 9):** Claim 2 matches the full row sentence verbatim (including the 994 of 1,000 human audit clause), while Claim 9 covers only the F1 comparison (90.9% vs. 79.2–80.0% and 85.1%) summarized on the right side of the row.


* **P6-S2 (Claim 15 vs. Claim 10):** Claim 15 matches the row sentence verbatim (994 items pass, 99.4% consistency rate in Table 2), while Claim 10 states that 994 of 1,000 sampled items pass human audit without the 99.4% figure.


* **P1-S1 (Claim 8 vs. Claim 3):** Claim 8 matches the 24 three-seed benchmark means across two students, two estimators, and three benchmarks summarized in the row, while Claim 3 adds model names and Avg@8/Pass@8 point ranges; however, if the trailing clauses on OPD and Co-RA in the row's source sentence are required, Claim 8 is narrower.


* **P1-S2 (Claim 3 vs. Claim 9):** Claim 3 is a verbatim match to the row (with 1.7–3.6 Avg@8 and 3.9–6.3 Pass@8), whereas Claim 9 states only the two-decimal macro gains (1.74–3.58 and 3.89–6.33) without naming the student/teacher models or estimators.


* **P11-S1 (Claim 6 vs. Claim 1 and Claim 14):** Claim 6 matches the row sentence verbatim, while Claim 1 and Claim 14 report the same percentage jumps (9.4% to 48.6%, 9% to 35%, and 27.6% to 51.7%) with additional framing or percentage-point deltas.


* **P10-S1 (Claim 2 vs. Claim 5):** Claim 2 matches the row sentence verbatim, while Claim 5 combines the 1.2–1.6× token-efficiency figure with the test-task win rate increase from 53.9% to 69.9%.


* **P10-S2 (Claim 19 vs. Claim 9):** Claim 19 matches the row sentence verbatim (68.3% with 28.82M tokens, 4.3 points above S++ with 31.4% fewer tokens), whereas Claim 9 reports the same comparison in different terms (68.3% vs. 64.0% on ~1.4× more tokens).


* **P9-S4 (Claim 2 vs. Claim 18 and Claim 19):** Claim 2 matches the row sentence verbatim (~18% compute saved and 83% precision / 5 out of 6 aborts), whereas Claims 18 and 19 split the 0.60 threshold/17.9% savings and the ~83% precision across two separate claims.