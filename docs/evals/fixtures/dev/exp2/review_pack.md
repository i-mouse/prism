# Experiment 2 Stage A review pack

13 target (extraction-miss) rows, 13 matched rows. This is a suggestion for review, not an adjudication - fill in the adjudication JSON by hand.

## Target rows (extraction misses)

### P1-R2 — control_r1 (arxiv-2610.11519v1)
- claim #35 score=100.0: The guidance term decreases both as the student approaches the teacher and as the student becomes confident in its own choice, an elegant property that helps RA
- claim #2 score=53.3: Co-RA further updates a teacher LoRA with verifier advantages on the same scored student batch and uses the updated teacher in the next iteration’s residual, ad
- claim #5 score=53.0: The guidance is thus student-relative twice over, as an advantage under the student’s own next-token distribution and as a deviation within the student’s own re

### P1-R2 — treatment_r1 (arxiv-2610.11519v1)
- claim #7 score=53.9: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- claim #2 score=53.3: Co-RA further updates a teacher LoRA with verifier advantages on the same scored student batch and uses the updated teacher in the next iteration’s residual, ad
- claim #5 score=53.0: The guidance is thus student-relative twice over, as an advantage under the student’s own next-token distribution and as a deviation within the student’s own re

### P1-R2 — treatment_r2 (arxiv-2610.11519v1)
- claim #7 score=53.9: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- claim #2 score=53.3: Co-RA further updates a teacher LoRA with verifier advantages on the same scored student batch and uses the updated teacher in the next iteration’s residual, ad
- claim #1 score=50.3: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit amon

### P2-R1 — control_r1 (arxiv-2610.11132v1)
- claim #1 score=59.8: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.
- claim #16 score=52.5: Figure 1(d) shows that the parent model attends more to useful SFT responses than hallucinated ones, with a 22.33 percentage point difference in the average sha
- claim #0 score=52.4: We introduce SFT-as-context, a training-free method in which the parent model uses the SFT model’s response as context to answer the query.

### P2-R1 — treatment_r1 (arxiv-2610.11132v1)
- claim #0 score=59.8: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.
- claim #17 score=52.5: Figure 1(d) shows that the parent model attends more to useful SFT responses than hallucinated ones, with a 22.33 percentage point difference in the average sha
- claim #3 score=52.3: This approach also extends beyond parent-SFT pairs: responses from a small open-source SFT model can improve a strong closed-source LLM, outperforming either mo

### P2-R1 — treatment_r2 (arxiv-2610.11132v1)
- claim #1 score=59.8: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.
- claim #7 score=57.5: Instead, we propose a training-free method, SFT-as-context, which leverages the in-context learning capability of language models by providing a fine-tuned mode
- claim #19 score=52.5: Figure 1(d) shows that the parent model attends more to useful SFT responses than hallucinated ones, with a 22.33 percentage point difference in the average sha

### P2-R3 — control_r1 (arxiv-2610.11132v1)
- claim #22 score=52.2: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- claim #21 score=47.6: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- claim #19 score=44.2: Language consistency and acknowledgment of non-food queries are only 1.3% and 17.9%, compared with 73.7% and 98.0% for SFT-as-context.

### P2-R3 — treatment_r1 (arxiv-2610.11132v1)
- claim #22 score=52.2: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- claim #21 score=47.6: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- claim #20 score=42.9: These results suggest that the gains of SFT-as-context cannot be explained solely by the SFT-as-context instructions or an additional inference pass.

### P2-R3 — treatment_r2 (arxiv-2610.11132v1)
- claim #23 score=52.2: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- claim #22 score=47.6: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- claim #21 score=42.9: These results suggest that the gains of SFT-as-context cannot be explained solely by the SFT-as-context instructions or an additional inference pass.

### P2-R4 — control_r1 (arxiv-2610.11132v1)
- claim #25 score=50.2: Table 11 shows that repeating the original task instructions significantly helps instruction-following, while barely affecting the fine-tuned math capability.
- claim #9 score=49.2: At the same time, it achieves an average recovery rate of 94.2% for general capabilities across instruction-following, multilingual tasks, question answering, a
- claim #1 score=47.7: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.

### P2-R4 — treatment_r1 (arxiv-2610.11132v1)
- claim #24 score=50.2: Table 11 shows that repeating the original task instructions significantly helps instruction-following, while barely affecting the fine-tuned math capability.
- claim #8 score=49.2: At the same time, it achieves an average recovery rate of 94.2% for general capabilities across instruction-following, multilingual tasks, question answering, a
- claim #0 score=47.7: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.

### P2-R4 — treatment_r2 (arxiv-2610.11132v1)
- claim #25 score=50.2: Table 11 shows that repeating the original task instructions significantly helps instruction-following, while barely affecting the fine-tuned math capability.
- claim #10 score=49.2: At the same time, it achieves an average recovery rate of 94.2% for general capabilities across instruction-following, multilingual tasks, question answering, a
- claim #1 score=47.7: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.

### P3-R1 — control_r1 (arxiv-2610.11135v1)
- claim #47 score=100.0: Among the readers we tested, the gain comes from the model rather than the typed format; the input recipe helps other LLMs as much as it helps Jev.
- claim #27 score=60.4: For the weights and readers we tested, the typed format does not produce the gain; the model does.
- claim #10 score=58.9: Controlled analyses (reader swap, other LLMs behind the same interface, contamination checks) find that the gain comes from the model rather than from the typed

### P3-R1 — treatment_r1 (arxiv-2610.11135v1)
- claim #10 score=58.0: Why. Controlled analyses (reader swap, other LLMs behind the same interface, contamination checks) find that the gain comes from the model rather than from the 
- claim #6 score=56.8: Among the readers we tested, the gain comes from the model, as other LLMs reading the identical input, directly or through the vendor’s System-One adapter, are 
- claim #2 score=51.0: Among the readers we tested, the gain is specific to Jev, since three other LLMs queried with the byte-identical typed request through the official System-One a

### P3-R1 — treatment_r2 (arxiv-2610.11135v1)
- claim #24 score=60.4: For the weights and readers we tested, the typed format does not produce the gain; the model does.
- claim #10 score=58.9: Controlled analyses (reader swap, other LLMs behind the same interface, contamination checks) find that the gain comes from the model rather than from the typed
- claim #6 score=56.8: Among the readers we tested, the gain comes from the model, as other LLMs reading the identical input, directly or through the vendor’s System-One adapter, are 

### P4-R3 — control_r1 (arxiv-2610.10871v1)
- claim #4 score=57.7: MASA keeps the sparse units, kernels, and budgets of existing sparse attention methods, but replaces their raw attention-mass ranking with a closed-form score d
- claim #1 score=52.9: As a theory-grounded plug-in correction, MASA can be added to existing sparse attention frameworks without changing their sparse kernels or budgets.
- claim #2 score=52.4: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matri

### P4-R3 — treatment_r1 (arxiv-2610.10871v1)
- claim #0 score=52.9: As a theory-grounded plug-in correction, MASA can be added to existing sparse attention frameworks without changing their sparse kernels or budgets.
- claim #1 score=52.4: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matri
- claim #4 score=50.6: Under matched settings with the original baselines, MASA gives consistent accuracy gains, supporting both the proposed method and the matrix-approximation view 

### P4-R3 — treatment_r2 (arxiv-2610.10871v1)
- claim #4 score=57.7: MASA keeps the sparse units, kernels, and budgets of existing sparse attention methods, but replaces their raw attention-mass ranking with a closed-form score d
- claim #12 score=53.1: MASA keeps their sparse unit definitions, sparse kernels, and budget rules unchanged, and only replaces the score used to rank candidate sparse units.
- claim #1 score=52.9: As a theory-grounded plug-in correction, MASA can be added to existing sparse attention frameworks without changing their sparse kernels or budgets.

### P5-R3 — control_r1 (arxiv-2610.11291v1)
- claim #5 score=48.3: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferr
- claim #16 score=47.5: restricting supervision to the first quarter substantially slows convergence and reduces final accuracy, whereas training on full trajectories achieves the best
- claim #0 score=45.3: We show that a simple alternative, Semi-OPD, which distills from offline rollouts generated by the initial student, can often outperform OPD in both accuracy an

### P5-R3 — treatment_r1 (arxiv-2610.11291v1)
- claim #5 score=48.3: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferr
- claim #21 score=47.4: As shown in Fig. 5(c, d), restricting supervision to the first quarter substantially slows convergence and reduces final accuracy, whereas training on full traj
- claim #0 score=45.3: We show that a simple alternative, Semi-OPD, which distills from offline rollouts generated by the initial student, can often outperform OPD in both accuracy an

### P5-R3 — treatment_r2 (arxiv-2610.11291v1)
- claim #4 score=48.3: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferr
- claim #18 score=47.4: As shown in Fig. 5(c, d), restricting supervision to the first quarter substantially slows convergence and reduces final accuracy, whereas training on full traj
- claim #0 score=45.3: We show that a simple alternative, Semi-OPD, which distills from offline rollouts generated by the initial student, can often outperform OPD in both accuracy an

### P7-R2 — control_r1 (arxiv-2610.10590v1)
- claim #5 score=45.5: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- claim #17 score=44.4: In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters.
- claim #18 score=43.9: All 26 archived text payloads and image lists match their recorded tool returns exactly.

### P7-R2 — treatment_r1 (arxiv-2610.10590v1)
- claim #6 score=45.5: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- claim #19 score=44.4: In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters.
- claim #20 score=43.9: All 26 archived text payloads and image lists match their recorded tool returns exactly.

### P7-R2 — treatment_r2 (arxiv-2610.10590v1)
- claim #4 score=45.5: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- claim #18 score=44.4: In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters.
- claim #6 score=44.2: User, system, and assistant messages are not selectable through the context tools.

### P8-R3 — control_r1 (arxiv-2610.12124v1)
- claim #0 score=50.2: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- claim #7 score=50.0: Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods.
- claim #4 score=46.2: Both forms of consolidation keep the agent’s recent context focused and high-signal, enabling accurate and coherent reasoning over long horizons.

### P8-R3 — treatment_r1 (arxiv-2610.12124v1)
- claim #6 score=52.3: These results demonstrate how our use-and-disuse cycle supports memory and learning through interaction history.
- claim #2 score=50.2: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- claim #14 score=50.0: Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods.

### P8-R3 — treatment_r2 (arxiv-2610.12124v1)
- claim #0 score=50.2: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- claim #8 score=50.0: Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods.
- claim #6 score=46.9: This natural dynamic of use and disuse unifies the recovery of past experience with learning that deepens what the agent knows, refines how it acts, and expands

### P9-R1 — control_r1 (arxiv-2610.12375v1)
- claim #24 score=46.1: Empirically this is a negative result: at γeff = 0.3 the coupling quality degrades across ablations (on a held-out tool-calling corpus, mean ablation AUROC drop
- claim #7 score=44.4: For S3, instead of re-solving the alignment at every step, we take one warm-started iteration of the batch solver per event — about a millisecond per step — and
- claim #25 score=43.9: On SWE-agent traces, which follow a narrow search–read–edit–test template, a checkpoint-level ablation at k=5 and k=10 (5 seeds) shows Full OnTrack exceeds the 

### P9-R1 — treatment_r1 (arxiv-2610.12375v1)
- claim #25 score=52.3: at shipped thresholds the quadratic structure term selects a point with less than half the benign false-alarm rate of every reference-free variant (13/40 vs. 29
- claim #24 score=46.1: Empirically this is a negative result: at γeff = 0.3 the coupling quality degrades across ablations (on a held-out tool-calling corpus, mean ablation AUROC drop
- claim #1 score=45.1: Naturally, the expectation of the monitoring capability of OnTrack is reduced as data access is reduced, ranging from the detection of any violation of the plan

### P9-R1 — treatment_r2 (arxiv-2610.12375v1)
- claim #15 score=52.1: Second, at the shipped threshold the quadratic structure term selects a lower-FPR operating point: removing the mask changes almost nothing (13/40 →14/40 false-
- claim #8 score=44.4: For S3, instead of re-solving the alignment at every step, we take one warm-started iteration of the batch solver per event — about a millisecond per step — and
- claim #22 score=43.0: Injecting the controlled fault types into real resolved traces, flag-based AUROC is strongest on loops (0.699) and stalls (0.646), where structural repetition i

### P11-R1 — control_r1 (arxiv-2610.12114v1)
- claim #36 score=49.1: Although the gain magnitude varies across configurations, the same Primer remains effective without resynthesis under the evaluated changes to quantization and 
- claim #30 score=49.1: Notably, although the Primer is synthesized with a 32k maximum output-token budget, it continues to improve the Student at larger budgets, indicating that its k
- claim #23 score=48.5: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the ob

### P11-R1 — treatment_r1 (arxiv-2610.12114v1)
- claim #24 score=49.1: Notably, although the Primer is synthesized with a 32k maximum output-token budget, it continues to improve the Student at larger budgets, indicating that its k
- claim #18 score=48.5: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the ob
- claim #13 score=46.6: On the distillation training set, Pro→Flash accuracy on KernelBench increases from 6.7% to 65.2%, indicating that the synthesized Primer effectively improves St

### P11-R1 — treatment_r2 (arxiv-2610.12114v1)
- claim #19 score=48.5: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the ob
- claim #15 score=45.6: These results show that knowledge distilled into text can generalize to unseen problems, with benefits extending beyond the samples used for synthesis.
- claim #6 score=45.0: Empirically, across various Teacher-Student configurations in mathematical reasoning and code generation, the synthesized Primers consistently improve their sou

### P11-R3 — control_r1 (arxiv-2610.12114v1)
- claim #12 score=48.1: Notably, the resulting Primer can improve the performance of the source Student and other Students that are not involved in creating the Primer.
- claim #23 score=47.3: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the ob
- claim #37 score=46.6: Together with Table 3, these results show that UTT outperforms all KD baselines without parameter updates.

### P11-R3 — treatment_r1 (arxiv-2610.12114v1)
- claim #18 score=47.3: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the ob
- claim #13 score=44.4: On the distillation training set, Pro→Flash accuracy on KernelBench increases from 6.7% to 65.2%, indicating that the synthesized Primer effectively improves St
- claim #4 score=44.1: Relying solely on interactions among LLMs, the process requires no model training or parameter updates and supports both open-source and API-only commercial mod

### P11-R3 — treatment_r2 (arxiv-2610.12114v1)
- claim #19 score=47.3: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the ob
- claim #17 score=46.2: This indicates that the Primer largely preserves the Student’s existing capabilities while improving performance on knowledge-gap samples.
- claim #15 score=46.2: These results show that knowledge distilled into text can generalize to unseen problems, with benefits extending beyond the samples used for synthesis.

### P12-R1 — control_r1 (arxiv-2610.12168v1)
- claim #35 score=66.3: Our central hypothesis is that reverse engineering the idea underlying a known solution is, in general, easier than discovering it from the problem alone.
- claim #28 score=57.4: A shared backbone is jointly trained on three tasks: reverse engineering hierarchies from problems and reference solutions; predicting such hierarchies from pro
- claim #1 score=56.4: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-en

### P12-R1 — treatment_r1 (arxiv-2610.12168v1)
- claim #20 score=66.3: Our central hypothesis is that reverse engineering the idea underlying a known solution is, in general, easier than discovering it from the problem alone.
- claim #1 score=56.4: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-en
- claim #10 score=52.4: The ideas reverse-engineered by the hindsight component are intended to provide guidance that could plausibly be followed from the problem alone, rather than me

### P12-R1 — treatment_r2 (arxiv-2610.12168v1)
- claim #22 score=66.3: Our central hypothesis is that reverse engineering the idea underlying a known solution is, in general, easier than discovering it from the problem alone.
- claim #1 score=56.4: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-en
- claim #4 score=52.6: Such a reconstructed idea can then provide additional supervision for learning to develop a solution idea from the problem alone, before attempting to solve it.

## Matched rows (regression check)

### P1-R1 — control_r1 (arxiv-2610.11519v1)
- claim #31 score=50.0: The centered log ratio puts 50% of its total on the 4% of tokens the teacher assigns less than 10−4, where its label diverges.
- claim #22 score=47.9: Removing the student value baseline lowers both macro scores, by 2.09 Avg@8 and 3.58 Pass@8 points at the reference weight and similarly at weights 5 and 20 (Ta
- claim #30 score=47.5: The residual puts 59% of its guidance on the 12% of tokens with 0.1 ≤ p(at) < 0.5, five times their share, where the student is choosing among live alternatives

### P1-R1 — treatment_r1 (arxiv-2610.11519v1)
- claim #7 score=50.2: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- claim #6 score=50.0: Its expected update at a prefix is the exact logit gradient of that distance, so the student’s own probability of a token scales how strongly the teacher can mo
- claim #20 score=47.9: Removing the student value baseline lowers both macro scores, by 2.09 Avg@8 and 3.58 Pass@8 points at the reference weight and similarly at weights 5 and 20 (Ta

### P1-R1 — treatment_r2 (arxiv-2610.11519v1)
- claim #7 score=50.2: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- claim #17 score=47.9: Removing the student value baseline lowers both macro scores, by 2.09 Avg@8 and 3.58 Pass@8 points at the reference weight and similarly at weights 5 and 20 (Ta
- claim #1 score=46.9: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit amon

### P1-R3 — control_r1 (arxiv-2610.11519v1)
- claim #10 score=100.0: The second bounds the guidance amplitude by the student–teacher distance on the visited prefixes (Appendix A.6), so teacher guidance fades as the two converge, 
- claim #9 score=52.7: The local advantage vanishes on a token the student has settled, whatever the teacher says, and by part (ii) logit b moves in expectation by p(b)(1 − p(b)) time
- claim #1 score=50.9: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit amon

### P1-R3 — treatment_r1 (arxiv-2610.11519v1)
- claim #7 score=53.8: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- claim #1 score=50.9: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit amon
- claim #10 score=50.6: Training on the student’s own rollouts with the verifier’s advantages lets the teacher adapt to the reasoning along the student’s solution paths, with the aim o

### P1-R3 — treatment_r2 (arxiv-2610.11519v1)
- claim #7 score=53.8: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- claim #1 score=50.9: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit amon
- claim #0 score=50.3: We propose Residual Advantage (RA), which treats the teacher–student probability residual as a bounded one-step reward, subtracts the corresponding state value 

### P2-R5 — control_r1 (arxiv-2610.11132v1)
- claim #22 score=100.0: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- claim #21 score=54.8: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- claim #19 score=48.1: Language consistency and acknowledgment of non-food queries are only 1.3% and 17.9%, compared with 73.7% and 98.0% for SFT-as-context.

### P2-R5 — treatment_r1 (arxiv-2610.11132v1)
- claim #22 score=100.0: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- claim #21 score=54.8: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- claim #20 score=46.7: These results suggest that the gains of SFT-as-context cannot be explained solely by the SFT-as-context instructions or an additional inference pass.

### P2-R5 — treatment_r2 (arxiv-2610.11132v1)
- claim #23 score=100.0: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- claim #22 score=54.8: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- claim #21 score=46.7: These results suggest that the gains of SFT-as-context cannot be explained solely by the SFT-as-context instructions or an additional inference pass.

### P3-R2 — control_r1 (arxiv-2610.11135v1)
- claim #3 score=100.0: For new learners the advantage holds from their first interactions, whereas on unseen items with all learners logged, deep KT remains ahead.
- claim #22 score=53.0: Unseen items alone therefore do not reverse the full-data result, and the advantage of the System-One model comes from having few learners, not from unseen item
- claim #4 score=51.1: With no learners logged, Jev0-shot reaches a mean AUC of .706, above the best deep KT model trained on 8 learners (.689) and above Thinking-KT on all seven data

### P3-R2 — treatment_r1 (arxiv-2610.11135v1)
- claim #3 score=100.0: For new learners the advantage holds from their first interactions, whereas on unseen items with all learners logged, deep KT remains ahead.
- claim #4 score=51.1: With no learners logged, Jev0-shot reaches a mean AUC of .706, above the best deep KT model trained on 8 learners (.689) and above Thinking-KT on all seven data
- claim #16 score=50.5: LOKT, whose only use of the logged learners is answer-option weights, barely moves with N (.672 at N=8 and .672 with all learners, against .671 at N=0) and stay

### P3-R2 — treatment_r2 (arxiv-2610.11135v1)
- claim #3 score=100.0: For new learners the advantage holds from their first interactions, whereas on unseen items with all learners logged, deep KT remains ahead.
- claim #20 score=53.0: Unseen items alone therefore do not reverse the full-data result, and the advantage of the System-One model comes from having few learners, not from unseen item
- claim #4 score=51.1: With no learners logged, Jev0-shot reaches a mean AUC of .706, above the best deep KT model trained on 8 learners (.689) and above Thinking-KT on all seven data

### P4-R1 — control_r1 (arxiv-2610.10871v1)
- claim #24 score=100.0: Across multiple sparse baselines, benchmarks, and LLM backbones, MASA gives consistent gains under matched settings with negligible latency overhead.
- claim #9 score=59.0: Under matched settings with the original baselines, MASA gives consistent accuracy gains, supporting both the proposed method and the matrix-approximation view 
- claim #2 score=53.1: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matri

### P4-R1 — treatment_r1 (arxiv-2610.10871v1)
- claim #4 score=59.0: Under matched settings with the original baselines, MASA gives consistent accuracy gains, supporting both the proposed method and the matrix-approximation view 
- claim #1 score=53.1: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matri
- claim #3 score=51.1: MASA can be integrated into existing sparse attention baselines while keeping their sparse kernels and budgets unchanged.

### P4-R1 — treatment_r2 (arxiv-2610.10871v1)
- claim #30 score=100.0: Across multiple sparse baselines, benchmarks, and LLM backbones, MASA gives consistent gains under matched settings with negligible latency overhead.
- claim #11 score=59.0: Under matched settings with the original baselines, MASA gives consistent accuracy gains, supporting both the proposed method and the matrix-approximation view 
- claim #2 score=53.1: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matri

### P4-R2 — control_r1 (arxiv-2610.10871v1)
- claim #18 score=47.8: At 64K, the gains reach 2.16 points for FlexPrefill-Llama and 3.65 points for FlexPrefill-Qwen.
- claim #23 score=47.4: The relative reductions are 0.41% for MInference, 2.10% for SeerAttention, and 2.34% and 7.17% for FlexPrefill on Llama and Qwen, respectively.
- claim #21 score=47.1: Across MInference, SeerAttention, FlexPrefill-Llama, and FlexPrefill-Qwen, replacing the original ranking score with MASA adds empirically negligible overhead r

### P4-R2 — treatment_r1 (arxiv-2610.10871v1)
- claim #21 score=100.0: Norm clipping is helpful for SeerAttention and FlexPrefill-Llama, while soft norm balancing is useful in some FlexPrefill settings.
- claim #14 score=47.8: At 64K, the gains reach 2.16 points for FlexPrefill-Llama and 3.65 points for FlexPrefill-Qwen.
- claim #23 score=47.4: The relative reductions are 0.41% for MInference, 2.10% for SeerAttention, and 2.34% and 7.17% for FlexPrefill on Llama and Qwen, respectively.

### P4-R2 — treatment_r2 (arxiv-2610.10871v1)
- claim #29 score=100.0: Norm clipping is helpful for SeerAttention and FlexPrefill-Llama, while soft norm balancing is useful in some FlexPrefill settings.
- claim #34 score=56.6: Norm control improves the best tested MInference and SeerAttention results, while its effect varies across FlexPrefill configurations.
- claim #22 score=47.8: At 64K, the gains reach 2.16 points for FlexPrefill-Llama and 3.65 points for FlexPrefill-Qwen.

### P5-R1 — control_r1 (arxiv-2610.11291v1)
- claim #14 score=34.9: Semi-OPD consistently outperforms teacher-rollout distillation.
- claim #10 score=32.6: The difference is especially pronounced for Qwen3 thinking-mode pairs: OPD undergoes a substantial performance collapse during training, whereas Semi-OPD contin
- claim #16 score=32.6: restricting supervision to the first quarter substantially slows convergence and reduces final accuracy, whereas training on full trajectories achieves the best

### P5-R1 — treatment_r1 (arxiv-2610.11291v1)
- claim #11 score=35.6: On the remaining three pairs, Semi-OPD still achieves comparable performance, with gaps of 0.1–2.6%.
- claim #18 score=35.6: As shown in Fig. 5(a, b), Semi-OPD consistently outperforms teacher-rollout distillation.
- claim #22 score=35.4: As shown in Fig. 7, Semi-OPD maintains a larger fraction of such tokens than OPD throughout training.

### P5-R1 — treatment_r2 (arxiv-2610.11291v1)
- claim #9 score=35.6: On the remaining three pairs, Semi-OPD still achieves comparable performance, with gaps of 0.1–2.6%.
- claim #16 score=35.6: As shown in Fig. 5(a, b), Semi-OPD consistently outperforms teacher-rollout distillation.
- claim #19 score=35.4: As shown in Fig. 7, Semi-OPD maintains a larger fraction of such tokens than OPD throughout training.

### P5-R2 — control_r1 (arxiv-2610.11291v1)
- claim #1 score=53.0: Across 17 teacher–student pairs ranging from 1.5B to 235B parameters, Semi-OPD outperforms OPD in 14 cases, with up to +13.6% accuracy and 11.4× training speedu
- claim #5 score=50.9: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferr
- claim #9 score=49.6: Effective distillation requires both the on-policyness of training rollout w.r.t. the student and closeness to the teacher; OPD prioritizes the former but may s

### P5-R2 — treatment_r1 (arxiv-2610.11291v1)
- claim #1 score=53.0: Across 17 teacher–student pairs ranging from 1.5B to 235B parameters, Semi-OPD outperforms OPD in 14 cases, with up to +13.6% accuracy and 11.4× training speedu
- claim #30 score=51.0: As shown in Figs. 15 and 16, on thinking pairs OPD drives both the student’s and the teacher’s next-token entropy on the training tokens well below Semi-OPD’s i
- claim #5 score=50.9: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferr

### P5-R2 — treatment_r2 (arxiv-2610.11291v1)
- claim #1 score=53.0: Across 17 teacher–student pairs ranging from 1.5B to 235B parameters, Semi-OPD outperforms OPD in 14 cases, with up to +13.6% accuracy and 11.4× training speedu
- claim #4 score=50.9: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferr
- claim #27 score=49.6: On thinking pairs OPD drives both the student’s and the teacher’s next-token entropy on the training tokens well below Semi-OPD’s in 7 of 8 pairs (the exception

### P7-R1 — control_r1 (arxiv-2610.10590v1)
- claim #5 score=54.2: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- claim #0 score=46.0: A Python harness exposes batch archival and explicit recovery without task-specific model training, while protecting user instructions and assistant messages fr
- claim #22 score=44.8: An earlier browser-based workflow-design continuation used 63% fewer total tokens with the method but received a manual score of 4/12 versus 6/12 for retained.

### P7-R1 — treatment_r1 (arxiv-2610.10590v1)
- claim #5 score=100.0: These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload dependence as a central consideration for rever
- claim #6 score=54.2: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- claim #7 score=46.0: Table 1 shows substantial reduction in active and cumulative input under the method despite more requests.

### P7-R1 — treatment_r2 (arxiv-2610.10590v1)
- claim #4 score=54.2: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- claim #27 score=48.0: In the central noisy debugging case, reversible curation accompanies a 75% smaller final measured prompt, 50% less cumulative input, and substantially lower est
- claim #22 score=47.9: Archival of 34 results removes only 69,685 net history characters; this does not offset the differing generated trajectories and method overhead.

### P8-R1 — control_r1 (arxiv-2610.12124v1)
- claim #4 score=45.6: Both forms of consolidation keep the agent’s recent context focused and high-signal, enabling accurate and coherent reasoning over long horizons.
- claim #3 score=44.1: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.
- claim #16 score=43.8: Hippocam combines stronger conversational reasoning with 87.2% accuracy on unanswerable questions.

### P8-R1 — treatment_r1 (arxiv-2610.12124v1)
- claim #9 score=45.6: Both forms of consolidation keep the agent’s recent context focused and high-signal, enabling accurate and coherent reasoning over long horizons.
- claim #10 score=44.4: Experience that remains unused continues to recede in detail through recursive consolidation, without separately assigned importance scores or time-based forget
- claim #8 score=44.1: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.

### P8-R1 — treatment_r2 (arxiv-2610.12124v1)
- claim #4 score=45.6: Both forms of consolidation keep the agent’s recent context focused and high-signal, enabling accurate and coherent reasoning over long horizons.
- claim #5 score=44.4: Experience that remains unused continues to recede in detail through recursive consolidation, without separately assigned importance scores or time-based forget
- claim #3 score=44.1: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.

### P8-R2 — control_r1 (arxiv-2610.12124v1)
- claim #3 score=49.6: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.
- claim #0 score=47.1: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- claim #1 score=45.8: Evaluations show that Hippocam achieves strong performance across memory, knowledge use, and learning.

### P8-R2 — treatment_r1 (arxiv-2610.12124v1)
- claim #6 score=100.0: These results demonstrate how our use-and-disuse cycle supports memory and learning through interaction history.
- claim #8 score=49.6: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.
- claim #0 score=49.0: To address this, we propose Hippocam, a hierarchical memory and continual learning architecture.

### P8-R2 — treatment_r2 (arxiv-2610.12124v1)
- claim #3 score=49.6: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.
- claim #0 score=47.1: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- claim #1 score=45.8: Evaluations show that Hippocam achieves strong performance across memory, knowledge use, and learning.

### P11-R2 — control_r1 (arxiv-2610.12114v1)
- claim #8 score=100.0: Across the evaluated settings, UTT also outperforms representative prompt engineering and parameter-updating knowledge distillation methods.
- claim #2 score=63.0: UTT also performs better than representative prompt engineering and parameter-based KD methods.
- claim #9 score=48.9: We formulate LLM distillation as representing the Teacher-Student knowledge gap in natural language rather than encoding it in a specific Student’s parameters, 

### P11-R2 — treatment_r1 (arxiv-2610.12114v1)
- claim #5 score=100.0: Across the evaluated settings, UTT also outperforms representative prompt engineering and parameter-updating knowledge distillation methods.
- claim #2 score=63.0: UTT also performs better than representative prompt engineering and parameter-based KD methods.
- claim #19 score=48.3: UTT performs best across all six combinations, with consistent gains across tasks and target models.

### P11-R2 — treatment_r2 (arxiv-2610.12114v1)
- claim #2 score=63.0: UTT also performs better than representative prompt engineering and parameter-based KD methods.
- claim #20 score=48.3: UTT performs best across all six combinations, with consistent gains across tasks and target models.
- claim #5 score=47.4: Relying solely on interactions among LLMs, the process requires no model training or parameter updates and supports both open-source and API-only commercial mod

### P12-R2 — control_r1 (arxiv-2610.12168v1)
- claim #4 score=100.0: For a reasoning model, this presents a learning opportunity: even when a problem exceeds its current solving abilities, a supplied solution may enable it to ext
- claim #0 score=66.9: We introduce a self-improvement loop for reasoning models based on the following observation: Even when the difficulty of a problem exceeds the model’s current 
- claim #1 score=54.9: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-en

### P12-R2 — treatment_r1 (arxiv-2610.12168v1)
- claim #0 score=66.9: We introduce a self-improvement loop for reasoning models based on the following observation: Even when the difficulty of a problem exceeds the model’s current 
- claim #1 score=54.9: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-en
- claim #2 score=50.6: The loop alternates between reverse engineering such ideas from problems with supplied solutions and using these ideas as additional supervision for joint train

### P12-R2 — treatment_r2 (arxiv-2610.12168v1)
- claim #0 score=66.9: We introduce a self-improvement loop for reasoning models based on the following observation: Even when the difficulty of a problem exceeds the model’s current 
- claim #1 score=54.9: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-en
- claim #4 score=50.9: Such a reconstructed idea can then provide additional supervision for learning to develop a solution idea from the problem alone, before attempting to solve it.
