# Clean-extraction attempt - K1 blind target-row matching pack

Do not open k1_key.json before scoring.

## Rules

- "Same claim, other sentence" = match.
- A "safe half only" sibling claim (broader or narrower version only) = no match.
- Several ids per row are allowed.
- "none" is allowed.

## P1-R2 (arxiv-2610.11519v1) - shape: E1
**Target claim:** The guidance term decreases both as the student approaches the teacher and as the student becomes confident in its own choice, an elegant property that helps RA preserve exploration in RL.

Candidates:
- **K1C0700**: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit among the steps within it.
- **K1C0294**: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- **K1C0595**: The two teachers differ in both the expected logit update and the response-centered guidance term (Table 8).
- **K1C0494**: Co-RA further updates a teacher LoRA with verifier advantages on the same scored student batch and uses the updated teacher in the next iteration’s residual, adapting guidance to the student’s attempts.
- **K1C0177**: The guidance is thus student-relative twice over, as an advantage under the student’s own next-token distribution and as a deviation within the student’s own response.
- **K1C0620**: The two label components are orthogonal, but these two parameter directions need not be, so the mean identity fixes the teacher’s share of the label and not of the update.
- **K1C0521**: Teacher adaptation thus preserves the mean identity, bounded guidance, and uniform vanishing with distributional agreement at each scoring step, and the fixed-prefix expected-gradient identity holds with q = qϕk.
- **K1C0425**: What distinguishes RA is its restraint: the teacher acts not as a distillation target, as in these works, but as a critic-like signal within RL.

## P2-R1 (arxiv-2610.11132v1) - shape: E1
**Target claim:** In principle, the same inference-time approach could be applied to a model fine-tuned with reinforcement learning (RLFT) by providing its response as context to the parent model.

Candidates:
- **K1C0244**: This flexibility allows responses from a small open-source SFT model to serve as context for a stronger closed-source model, even when the latter is not the parent of the SFT model.
- **K1C0337**: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.
- **K1C0709**: Instead, we propose a training-free method, SFT-as-context, which leverages the in-context learning capability of language models by providing a fine-tuned model’s response as context to its parent model and prompting the parent model to generate the final answer.
- **K1C0599**: More importantly, SFT-as-context requires only standard text input-output interfaces, making it applicable to closed-source models without access to their parameters.
- **K1C0003**: Figure 1(d) shows that the parent model attends more to useful SFT responses than hallucinated ones, with a 22.33 percentage point difference in the average share of attention allocated to the SFT responses.
- **K1C0323**: For the nutrition estimation task, however, the parent model generates relatively longer responses during the second pass, as it performs additional reasoning to compare the SFT-generated reference with its own estimate.
- **K1C0079**: We introduce SFT-as-context, a training-free method in which the parent model uses the SFT model’s response as context to answer the query.
- **K1C0365**: This approach also extends beyond parent-SFT pairs: responses from a small open-source SFT model can improve a strong closed-source LLM, outperforming either model alone.

## P2-R3 (arxiv-2610.11132v1) - shape: E2
**Target claim:** SFT-as-context incurs modest overhead compared with SFT.

Candidates:
- **K1C0202**: This highlights that SFT-as-context can mitigate severe forgetting while preserving substantial fine-tuning gains.
- **K1C0723**: Comprehensive experiments across domains, tasks, and model sizes demonstrate the effectiveness of SFT-as-context.
- **K1C0247**: Table 10: SFT-as-context incurs modest overhead compared with SFT.
- **K1C0462**: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- **K1C0380**: Overall, these results suggest that the additional generation overhead introduced by SFT-as-context is modest.
- **K1C0667**: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- **K1C0734**: SFT-as-context preserves the correct derivation and result, while using lowercase prose and notation r.
- **K1C0332**: The SFT-as-context method generates a response with the correct answer and formatting, outperforming both parent and SFT models.

## P2-R4 (arxiv-2610.11132v1) - shape: E2
**Target claim:** RL-trained models do not show forgetting of instruction-following capability compared to their parent, as measured by IFEval.

Candidates:
- **K1C0463**: In other words, when fine-tuned and general capabilities conflict, the parent model follows the fine-tuned capability under SFT-as-context.
- **K1C0332**: The SFT-as-context method generates a response with the correct answer and formatting, outperforming both parent and SFT models.
- **K1C0098**: For example, among the three nutrition SFT models, Qwen3-8B shows the largest drop in acknowledging non-food queries, from 99.6% to 10.7%, catastrophically forgetting the instruction-following capability of its parent model.
- **K1C0393**: Repeating the original task prompt in the SFT-as-context instructions helps instruction-following.
- **K1C0288**: At the same time, it achieves an average recovery rate of 94.2% for general capabilities across instruction-following, multilingual tasks, question answering, and planning.
- **K1C0070**: This result also shows that the proprietary model does not merely copy the SFT response during inference.
- **K1C0525**: Table 5: RL-trained models do not show forgetting of instruction-following capability compared to their parent, as measured by IFEval.
- **K1C0132**: Table 1: SFT-as-context successfully mitigates the forgetting of general capabilities and maintains high fine-tuned capabilities compared to SFT across all benchmarks.

## P3-R1 (arxiv-2610.11135v1) - shape: E3
**Target claim:** Among the readers we tested, the gain comes from the model rather than the typed format; the input recipe helps other LLMs as much as it helps Jev.

Candidates:
- **K1C0395**: For the weights and readers we tested, the typed format does not produce the gain; the model does.
- **K1C0232**: With few learners the prior carries the prediction and the evidence adds to it; as N grows the evidence becomes reliable, and supervised KT, which learns from the same evidence, catches up.
- **K1C0472**: Among the readers we tested, the gain is specific to Jev, since three other LLMs queried with the byte-identical typed request through the official System-One adapter fall below it on all seven datasets, and reader swaps and contamination checks find no evidence that the input format or memorised data explain the gain.
- **K1C0461**: Unseen items alone therefore do not reverse the full-data result, and the advantage of the System-One model comes from having few learners, not from unseen items.
- **K1C0504**: Among the readers we tested, the gain comes from the model rather than the typed format; the input recipe helps other LLMs as much as it helps Jev.
- **K1C0200**: Controlled analyses (reader swap, other LLMs behind the same interface, contamination checks) find that the gain comes from the model rather than from the typed format or memorised data.
- **K1C0477**: Among the readers we tested, the gain comes from the model, as other LLMs reading the identical input, directly or through the vendor’s System-One adapter, are worse on every dataset, and contamination checks find no sign of memorised data.
- **K1C0002**: For the Qwen3.5-9B backbone of Thinking-KT, reasoning does not help, as it is never significantly better than the same model without reasoning.

## P4-R3 (arxiv-2610.10871v1) - shape: E3
**Target claim:** MASA does not change the sparse kernels, candidate sparse units, or budget rules of existing methods, making it orthogonal to low-level attention kernels and other LLM acceleration techniques as discussed in Appendix A.

Candidates:
- **K1C0303**: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matrix-approximation view of sparse attention.
- **K1C0324**: MASA keeps the sparse units, kernels, and budgets of existing sparse attention methods, but replaces their raw attention-mass ranking with a closed-form score derived from matrix-product approximation error.
- **K1C0536**: MASA does not change the sparse kernels, candidate sparse units, or budget rules of existing methods, making it orthogonal to low-level attention kernels and other LLM acceleration techniques as discussed in Appendix A.
- **K1C0357**: MASA keeps the same candidate sparse units and the same budget as the baseline, such as blocks, vertical lines, slash lines, or query-aware index groups.
- **K1C0191**: Under matched settings with the original baselines, MASA gives consistent accuracy gains, supporting both the proposed method and the matrix-approximation view of sparse attention.
- **K1C0522**: MASA can be integrated into existing sparse attention baselines while keeping their sparse kernels and budgets unchanged.
- **K1C0182**: As a theory-grounded plug-in correction, MASA can be added to existing sparse attention frameworks without changing their sparse kernels or budgets.
- **K1C0642**: MASA keeps their sparse unit definitions, sparse kernels, and budget rules unchanged, and only replaces the score used to rank candidate sparse units.

## P5-R3 (arxiv-2610.11291v1) - shape: E3
**Target claim:** This cannot be addressed by simple truncation, as we empirically show the importance of covering supervision signals from different reasoning stages.

Candidates:
- **K1C0533**: We show that a simple alternative, Semi-OPD, which distills from offline rollouts generated by the initial student, can often outperform OPD in both accuracy and training efficiency.
- **K1C0616**: In contrast, Semi-OPD on initial student rollouts usually distills over shorter contexts while covering full trajectories, making it more stable.
- **K1C0619**: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferred tokens.
- **K1C0570**: Together, these findings suggest that Semi-OPD benefits from preserving student-anchored rollouts that remain effective teacher supervision and broad coverage of the reasoning process.
- **K1C0423**: This suggests that the gains are not limited to fitting the math training distribution but transfer to broader reasoning tasks.
- **K1C0207**: As shown in Fig. 5(c, d), restricting supervision to the first quarter substantially slows convergence and reduces final accuracy, whereas training on full trajectories achieves the best peak accuracy.
- **K1C0383**: These advantages can outweigh the benefits of fully on-policy sampling under large teacher–student mismatch.
- **K1C0698**: For a fixed student, the same rollout cache can also be reused across different teachers; evaluating a new teacher only requires computing its log-probabilities on the cached rollouts.

## P7-R2 (arxiv-2610.10590v1) - shape: E1
**Target claim:** In principle, the same contract can cover documentation, diagnostic logs, browser text, and images.

Candidates:
- **K1C0042**: The OpenTelemetry archive illustrates that the agent can act on this distinction.
- **K1C0274**: The same-session continuation exercises the mechanism beyond one isolated answer.
- **K1C0023**: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- **K1C0554**: Our contract preserves user, system and assistant messages and returns exact archived payloads on recovery.
- **K1C0268**: Selecting the high-noise case after earlier experiments makes it a development-informed case study rather than a held-out confirmatory benchmark.
- **K1C0592**: The method makes five successful archival batches in the primary phase and four in the follow-up.
- **K1C0651**: It shows that the method can continue implementing after context edits while retained history continues to grow.
- **K1C0068**: In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters.

## P8-R3 (arxiv-2610.12124v1) - shape: E3
**Target claim:** These gains demonstrate more effective learning from accumulated experience than the compared methods.

Candidates:
- **K1C0543**: These observations support intent-aware selection of both relevant content and the detail needed for ongoing work.
- **K1C0617**: Thus cache reuse between updates coexists with a substantial cost of periodically reorganizing experience.
- **K1C0718**: Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods.
- **K1C0185**: Unlike MemTree, our tree emerges from the organization and consolidation of ongoing work.
- **K1C0597**: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- **K1C0483**: Access to underlying evidence therefore improves reasoning beyond what the consolidated context alone supports.
- **K1C0426**: These gains demonstrate more effective learning from accumulated experience than the compared methods.
- **K1C0724**: These results demonstrate how our use-and-disuse cycle supports memory and learning through interaction history.

## P9-R1 (arxiv-2610.12375v1) - shape: E2
**Target claim:** Third, LinUOT tracks OnTrack within 0.003–0.010 AUROC everywhere: the quadratic term contributes essentially nothing to ranking on this corpus, consistent with its role as a false-alarm suppressor rather than a ranker (Table 4); the mask-free variant is AUROC-identical to the full system, confirming the mask’s null ranking effect here as well.

Candidates:
- **K1C0552**: The relevant distinction is when and how the signal is usable: a raw step count offers no principled stopping rule mid-trace (any length cutoff is a per-task guess), whereas the severe-flag density that drives Table 6 is a calibrated, task-agnostic trigger that identifies the loop/flounder behavior producing the cost overrun while budget remains to save.
- **K1C0574**: Point estimates are unstable at this sample size — an independent draw of the evaluation sample yields OnTrack 0.666 vs. cosine 0.657, reversing the ordering — so the only conclusion the data support is that neither process alignment nor content similarity predicts patch correctness from the trajectory alone.
- **K1C0211**: Empirically this is a nega- tive result: at γeff = 0.3 the coupling quality degrades across ablations (on a held-out tool-calling corpus, mean ablation AUROC drops from 0.825 to 0.715), because observations are high-variance — correct and incorrect executions of the same step both produce textually dif- ferent outputs every time, so the effect term dilutes the action/tool signal that correctly drives the alignment.
- **K1C0535**: Third, LinUOT tracks OnTrack within 0.003–0.010 AUROC everywhere: the quadratic term contributes essentially nothing to ranking on this corpus, consistent with its role as a false-alarm suppressor rather than a ranker (Table 4); the mask-free variant is AUROC-identical to the full sys- tem, confirming the mask’s null ranking effect here as well.
- **K1C0484**: First, threshold stability: cosine-cutoff’s frontier is pathologically sensitive — moving its threshold from 0.40 to 0.55 swings the false-stop rate from 3.3% to 28% to 73% to 95%, so a miscalibration of 0.05 turns it from inert into a kill-everything switch — whereas flag density degrades gracefully across its entire range (29% to 19% false stops over thresholds 0.2–0.7).
- **K1C0124**: OnTrack keeps the true objective by observing that the standard batch UFGW solver — conditional gradient (CG) — is already an iterative linearization scheme, and amortizing it: one warm-started CG iteration per event; the coupling tracks the moving optimum the way stochastic gradient descent tracks a drifting loss.
- **K1C0630**: The component study clarifies what the transport machinery changes on real traces: not recall — L1 heuristics and even a prerequisite-rule baseline match or exceed it there — but the operating point: at shipped thresholds the quadratic structure term selects a point with less than half the benign false-alarm rate of every reference-free variant (13/40 vs. 29–32/40 benign traces flagged; removing the frontier mask instead shifts the count by one trace); establishing curve-level dominance remains open, and we do not claim generally superior detection precision.
- **K1C0564**: The same information is useful downstream of the cou- pling: a mass-weighted content-divergence signal (does the observation match what the reference saw at the coupled node?) contributes to struggling-agent detection without touching the transport.

## P11-R1 (arxiv-2610.12114v1) - shape: E4
**Target claim:** Only the training set is used for Primer synthesis, while all other subsets are reserved for final evaluation; namely, the training and testing sets do not overlap, following the standard machine learning setting.

Candidates:
- **K1C0726**: Although the gain mag- nitude varies across configurations, the same Primer remains effective without resynthesis under the evaluated changes to quantization and thinking mode.
- **K1C0224**: This trade-off suggests that direct Teacher demonstrations fit the synthesis problems more strongly, whereas the Prompter helps transfer the acquired knowledge to problems not used for synthesis.
- **K1C0062**: Notably, although the Primer is synthesized with a 32k maximum output-token budget, it continues to improve the Student at larger budgets, indicating that its knowledge and solution strategies are not tied to the specific output-token budget used during synthesis.
- **K1C0699**: On the distillation training set, Pro→Flash accuracy on KernelBench increases from 6.7% to 65.2%, indicating that the synthesized Primer effectively improves Student performance on knowledge-gap samples.
- **K1C0280**: As both curves approach saturation, UTT retains its advantage, suggesting that the Primer is particularly beneficial when the inference budget is con- strained and provides a higher effective performance ceiling within the evaluated range.
- **K1C0721**: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the observed capability frontier.
- **K1C0489**: These results suggest that selecting synthesis problems according to the Teacher–Student knowledge gap provides more targeted teaching signals and a more consistent overall improvement.
- **K1C0728**: Its distinction lies in using the observed Teacher-Student knowledge gap to guide teaching-content selection and text synthesis, while examining whether the resulting knowledge transfers to other Students without resynthesis.

## P11-R3 (arxiv-2610.12114v1) - shape: E5
**Target claim:** We observed that the training losses of the KD baselines had largely stabilized by the end of their respective update budgets.

Candidates:
- **K1C0437**: This indicates that the Primer largely preserves the Student’s existing capabilities while improving performance on knowledge-gap samples.
- **K1C0638**: These results show that knowledge distilled into text can generalize to unseen problems, with benefits extending beyond the samples used for synthesis.
- **K1C0095**: As shown in Table 6, parameter training for the three supervised KD baselines requires 1.2–7.5 hours, while the reinforcement-learning-based LUFFY requires 22.0 hours on eight GPUs.
- **K1C0721**: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the observed capability frontier.
- **K1C0241**: Notably, the resulting Primer can improve the performance of the source Student and other Students that are not involved in creating the Primer.
- **K1C0442**: These results suggest that an intermediate batch size provides a better balance between the amount of teaching evidence consolidated in each update and the frequency of Primer refinement.
- **K1C0530**: These results validate the effectiveness of UTT and demonstrate its applicability to Students from different model families.
- **K1C0090**: As shown in Figure 4, errors caused by truncation gradually decrease as the output-token budget increases.

## P12-R1 (arxiv-2610.12168v1) - shape: E1
**Target claim:** Our method is inspired by the following asymmetry in problem solving: It is, in general, harder to solve a problem from scratch than to reverse engineer the idea underlying a known solution.

Candidates:
- **K1C0214**: We provide a formal specification of our method for a general problem setting, together with the optional refinement for verifiable problem domains.
- **K1C0675**: The loop alternates between reverse engineering such ideas from problems with supplied solutions and using these ideas as additional supervision for joint training of all three capabilities.
- **K1C0328**: We also give a concrete instantiation for interactive theorem proving in the Lean theorem prover [2], where natural language proof ideas guide tactic generation during proof search.
- **K1C0115**: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-engineering ideas from problems and known solutions, and solving problems using provided ideas.
- **K1C0586**: We introduce a self-improvement loop for reasoning models based on the following observation: Even when the difficulty of a problem exceeds the model’s current solving abilities, an additionally supplied solution might enable the model to extract useful solution ideas in hindsight.
- **K1C0406**: We give a formal specification of our method and a concrete instantiation for interactive theorem proving in the Lean theorem prover; empirical evaluation remains future work.
- **K1C0411**: The ideas reverse-engineered by the hindsight component are intended to provide guidance that could plausibly be followed from the problem alone, rather than merely describe the supplied solution or reflect hindsight bias.
- **K1C0236**: Finally, in verifiable problem domains, we additionally assess the reverse-engineered hierarchies through separate solving attempts, in which the model receives the problem and hierarchy while the reference solution is withheld.

## Appendix - arxiv-2610.10590v1 - full candidate pool
- **K1C0300**: The provider projection also handles API representation constraints, so preservation of stored assistant responses should not be confused with byte-identical wire serialization in every error case.
- **K1C0460**: Prompt size includes the request representation and is an operational proxy for active context, not a direct measure of usable reasoning capacity.
- **K1C0604**: Both arms submit both tasks normally, without recorded provider errors.
- **K1C0334**: Contrasting application development and an adverse continuation show that neither resource savings nor quality preservation follows automatically from a smaller active history.
- **K1C0217**: Both arms support the twelve journeys at the available assessment resolution, with the gaps described above.
- **K1C0452**: The method peak is 381,299 versus 912,492 tokens.
- **K1C0055**: An earlier browser-based workflow-design continuation used 63% fewer total tokens with the method but received a manual score of 4/12 versus 6/12 for retained.
- **K1C0591**: This enables comparison of archived payloads against recorded tool returns.
- **K1C0189**: The practical result is that an agent can complete noisy tool-driven work with substantially less active context and repeated input, using explicit archival decisions during the task.
- **K1C0184**: The archive verifies exact payload preservation while the agent repeatedly curates context and continues working; this pair does not test retrieval behavior because no recovery is requested.
- **K1C0116**: The method also requires more actions and time, and follow-up correctness remains incomplete.
- **K1C0651**: It shows that the method can continue implementing after context edits while retained history continues to grow.
- **K1C0271**: For the follow-up, both candidates compile.
- **K1C0317**: The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing difference.
- **K1C0625**: The backend validates the entire batch before committing a change.
- **K1C0384**: Our accounting includes reported cache usage; the different workloads and models preclude a direct numerical comparison.
- **K1C0029**: Both primary candidates pass the two-case behavioral oracle.
- **K1C0593**: Cumulative input decreases by 50%, and input plus completion tokens decrease by 50%.
- **K1C0045**: A Python harness exposes batch archival and explicit recovery without task-specific model training, while protecting user instructions and assistant messages from these operations.
- **K1C0592**: The method makes five successful archival batches in the primary phase and four in the follow-up.
- **K1C0223**: Both arms passed the two-case primary behavioral oracle; neither fully satisfied the follow-up evaluation.
- **K1C0343**: All 26 archived text payloads and image lists match their recorded tool returns exactly.
- **K1C0274**: The same-session continuation exercises the mechanism beyond one isolated answer.
- **K1C0612**: The estimated cost is approximately 67–71% lower, even after reported cache usage is included.
- **K1C0156**: Planroom provides a concrete boundary case.
- **K1C0033**: In the central noisy debugging case, reversible curation accompanies a 75% smaller final measured prompt, 50% less cumulative input, and substantially lower estimated API cost, while both arms pass the same two primary behavioral cases.
- **K1C0584**: Retained fails both probes and is killed with status 137.
- **K1C0188**: The method made more requests and took 17% longer.
- **K1C0110**: The trace preserves original observations independently of the active representation.
- **K1C0379**: No recovery is used in this pair, and no image payload is archived.
- **K1C0454**: The frozen mixed grader reports 3/6 for method and 2/6 for retained.
- **K1C0042**: The OpenTelemetry archive illustrates that the agent can act on this distinction.
- **K1C0665**: These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload dependence as a central consideration for reversible context management.
- **K1C0346**: Our interface restricts edits to individual tool-result occurrences, automatically archives exact originals, and preserves user, system, and assistant messages.
- **K1C0582**: The archive audit establishes byte-exact preservation, not the suﬀiciency of every note or the dispensability of every removed result.
- **K1C0308**: Conversely, retained passes the occupied-port startup-failure probe with status 1; the method’s second process does not finish within 30 seconds.
- **K1C0629**: Post-exposure curation gives the agent a further choice over continued retention without requiring changes to the source tool.
- **K1C0588**: The method therefore shows stronger tested signal handling but weaker tested startup-failure handling.
- **K1C0268**: Selecting the high-noise case after earlier experiments makes it a development-informed case study rather than a held-out confirmatory benchmark.
- **K1C0554**: Our contract preserves user, system and assistant messages and returns exact archived payloads on recovery.
- **K1C0359**: These are resource savings without a speed advantage in this case.
- **K1C0341**: In an exploratory OpenTelemetry debugging case followed by an unrelated implementation task, the method ended with 231,951 provider-reported prompt tokens versus 912,492 under retained history, used 50% fewer cumulative input tokens, and had an estimated API cost of $1.28–$1.44 versus approximately $4.38.
- **K1C0105**: The retention operation acts on recorded observations, so an upstream tool need not expose its own compaction controls.
- **K1C0037**: The method exits with status 0 after SIGTERM in 8.43 seconds and after SIGINT in 8.85 seconds.
- **K1C0225**: Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual tool-result occurrences, not a claim to invent agent-controlled memory.
- **K1C0510**: Agent-controlled forgetting provides an explicit way for a tool-using model to distinguish information it needed to inspect from information it still needs to carry.
- **K1C0677**: The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where the mechanism is useful.
- **K1C0646**: Both candidates contain remaining-budget calculations.
- **K1C0140**: The Sphinx batch contains two final 24/24 method outcomes and one retained 24/24 outcome.
- **K1C0705**: User, system, and assistant messages are not selectable through the context tools.
- **K1C0549**: The method generates more than twice as many completion tokens and takes 17% longer.
- **K1C0024**: Unknown, duplicate, already archived, or otherwise unavailable identifiers produce a corrective error without partial mutation.
- **K1C0233**: Its potential benefit lies in reducing repeated input and leaving less obsolete material in subsequent requests.
- **K1C0135**: Table 1 shows substantial reduction in active and cumulative input under the method despite more requests.
- **K1C0399**: At primary submission the method carries 124,746 prompt tokens versus 847,674 for retained, an 85% reduction.
- **K1C0072**: We report the repaired OpenTelemetry pair as the central case, the completed Planroom pair as a workload contrast, and the earlier six-session Sphinx batch as descriptive supporting evidence.
- **K1C0068**: In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters.
- **K1C0023**: The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors.
- **K1C0468**: Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps.
- **K1C0362**: Archival of 34 results removes only 69,685 net history characters; this does not offset the differing generated trajectories and method overhead.
- **K1C0708**: A contrasting application-development pair produced no context or cost saving, and an earlier continuation exhibited lower manually assessed quality despite reduced context.
- **K1C0736**: Planroom yields no context or cost saving: the method ends with 6% more prompt tokens (283,105 versus 265,965) and uses less than 1% more total tokens (68,136,934 versus 67,669,624).
- **K1C0130**: We do not infer energy savings from token or price reductions.
- **K1C0208**: Such equality checks validate storage integrity; they do not validate the semantic adequacy of notes.
- **K1C0430**: Method’s startup-failure branch joins a signal-waiting thread without first arranging its termination, consistent with the observed timeout.
- **K1C0020**: We study how this operation behaves in real coding and browser trajectories, including a case in which retained history exceeds 900,000 reported prompt tokens.
- **K1C0080**: After the follow-up, the method carries 231,951 versus 912,492 prompt tokens, a 75% reduction.

## Appendix - arxiv-2610.10871v1 - full candidate pool
- **K1C0605**: These results support the value of matrix-approximation ranking for long-context sparse prefill under the original frameworks’ sparse budgets and kernels.
- **K1C0459**: Appendix C shows that weighted output metrics can be written in the same form by choosing an appropriate probe X, and that the Frobenius matrix-product error controls the spectral matrix-product error.
- **K1C0358**: Based on this view, we propose Matrix Approximation Sparse Attention (MASA).
- **K1C0660**: Norm control improves the best tested MInference and SeerAttention results, while its effect varies across FlexPrefill configurations.
- **K1C0623**: This distinction is the main novelty of MASA: it connects a structured matrix-approximation objective to a common ranking mechanism within existing sparse attention systems.
- **K1C0573**: It only replaces the score used to rank these units.
- **K1C0626**: We argue that this is the core conceptual issue: sparse attention should be formulated as matrix approximation, not as blindly choosing the largest values from a bag of entries.
- **K1C0496**: MASA nevertheless delivers substantial gains relative to the dense-reference differences in several settings.
- **K1C0668**: On RULER, MASA raises SeerAttention from 87.60 to 88.09, moving it from below the dense reference to above it.
- **K1C0378**: MASA replaces raw attention-mass ranking with a closed-form score that measures how much each sparse unit reduces matrix-product approximation error.
- **K1C0307**: Second, norm control can further improve the score in settings where value-norm outliers affect sparse-unit ranking.
- **K1C0658**: This covers raw value probes, projected value probes, and weighted value-space metrics under the same matrix-product view.
- **K1C0128**: Therefore, MASA improves accuracy without weakening the practical efficiency of the underlying sparse attention method.
- **K1C0075**: These trends match the probe design: MASA should preserve value directions while preventing a small number of high-norm value vectors from dominating the selection score.
- **K1C0550**: At 64K, the gains reach 2.16 points for FlexPrefill-Llama and 3.65 points for FlexPrefill-Qwen.
- **K1C0717**: At 128K, MASA improves MInference, SeerAttention, FlexPrefill-Llama, and FlexPrefill-Qwen by 1.28, 0.48, 1.45, and 2.16 points, respectively.
- **K1C0001**: The evaluated MASA configurations reduce normalized squared output error in all four framework–backbone pairs, providing direct empirical support for matrix-product preservation.
- **K1C0349**: Thus, MASA improves already strong sparse systems without increasing their sparse budgets or changing their kernels.
- **K1C0266**: The relative reductions are 0.41% for MInference, 2.10% for SeerAttention, and 2.34% and 7.17% for FlexPrefill on Llama and Qwen, respectively.
- **K1C0392**: Thus, squared-magnitude ranking is only the identity-Gram special case of MASA.
- **K1C0182**: As a theory-grounded plug-in correction, MASA can be added to existing sparse attention frameworks without changing their sparse kernels or budgets.
- **K1C0153**: This computation only uses matrix products and score matrices at the profile resolution, without materializing the N × N × r contribution tensor.
- **K1C0628**: We pro-
vide a matrix-approximation view that
gives the correct selection objective.
- **K1C0357**: MASA keeps the same candidate sparse units and the same budget as the baseline, such as blocks, vertical lines, slash lines, or query-aware index groups.
- **K1C0306**: MASA
selects u2 and reduces the error to 3%.
- **K1C0121**: The overhead also stays negligible at 128K, the main regime where sparse attention is needed.
- **K1C0409**: When X = V , Eq. (6) becomes exactly the attention output error in Eq. (2).
- **K1C0644**: We propose MASA, a theory-grounded plug-in scoring method that ranks sparse units by their closed-form reduction in matrix-product approximation error.
- **K1C0418**: Across MInference, SeerAttention, FlexPrefill-Llama, and FlexPrefill-Qwen, replacing the original ranking score with MASA adds empirically negligible overhead relative to the sparse attention runtime and remains far below the dense attention cost.
- **K1C0303**: Extensive experiments across multiple sparse attention methods, benchmarks, and LLM backbones show consistent accuracy gains, supporting both MASA and the matrix-approximation view of sparse attention.
- **K1C0018**: For FlexPrefill-Llama on RULER, replacing the ranking score adds 0.76 points, exceeding the original method’s 0.48-point advantage over full attention and increasing that advantage to 1.24 points.
- **K1C0371**: Thus, MASA changes sparse selection from preserving large entries of A to preserving the matrix product AX.
- **K1C0536**: MASA does not change the sparse kernels, candidate sparse units, or budget rules of existing methods, making it orthogonal to low-level attention kernels and other LLM acceleration techniques as discussed in Appendix A.
- **K1C0429**: For every configuration, the mean gain over these longer contexts at 32K–128K exceeds that at 4K–16K.
- **K1C0118**: All MASA scores are computed at the same profile resolution as the baselines.
- **K1C0052**: Table 11 reports the LongBench ablation for SeerAttention, where clipping at p = 87.5 gives the highest average among the tested configurations.
- **K1C0279**: Norm clipping is helpful for SeerAttention and FlexPrefill-Llama, while soft norm balancing is useful in some FlexPrefill settings.
- **K1C0261**: This paper identifies a fundamental selection mismatch in sparse attention.
- **K1C0267**: This changes the selection target from preserving
large entries of the attention matrix to preserving the matrix action that determines the attention
output.
- **K1C0237**: The evaluated MASA configurations produce outputs closer to dense attention, providing empirical support for the matrix-approximation view alongside the downstream accuracy results.
- **K1C0138**: MASA improves all eight matched average scores across three sparse methods, three benchmark suites, and both Llama- and Qwen-family backbones.
- **K1C0117**: Therefore, reducing the Frobenius matrix-product error also reduces an upper bound on stronger matrix-action errors such as the spectral norm.
- **K1C0063**: We identify a long-standing selection mismatch in sparse attention: existing magnitude-based rules approximate the attention matrix entrywise, while the Transformer uses attention through matrix multiplication.
- **K1C0443**: MASA instead ranks framework-defined masks over query–key interactions for structured sparse attention computation.
- **K1C0659**: On LongBench, MASA improves SeerAttention’s 8K+ score from 52.69 to 53.16.
- **K1C0637**: MASA therefore does not require a new full-resolution dense attention map beyond the information used for sparse-unit ranking.
- **K1C0325**: On InfiniteBench, MASA raises FlexPrefill-Llama from 47.14 to 47.99 against a full-attention score of 48.06, recovering approximately 92% of the original average-score deficit.
- **K1C0642**: MASA keeps their sparse unit definitions, sparse kernels, and budget rules unchanged, and only replaces the score used to rank candidate sparse units.
- **K1C0636**: MASA can be used with the same sparse unit family as the baseline.
- **K1C0282**: We propose Matrix Approximation Sparse Attention (MASA), a theory-grounded plug-in correction for sparse attention.
- **K1C0215**: Therefore, V V ⊤cannot be an identity matrix over the N token positions.
- **K1C0255**: Table 8 shows lower attention-output error in every evaluated framework–backbone pair, with all four reported paired confidence intervals above zero.
- **K1C0685**: As a result, MASA can be added to diverse sparse attention frameworks without changing their implementation interface.
- **K1C0703**: Across the four RULER configurations at 32K, 64K, and 128K, MASA improves 11 of 12 matched length-level scores.
- **K1C0385**: Under the same one-column budget, conventional mass-
based ranking selects u1, whose mass is 66× larger
but incurs 98% relative matrix-product error.
- **K1C0356**: This shows that entrywise magnitude ranking is correct only when V V ⊤behaves like an identity matrix over token positions.
- **K1C0531**: The second term keeps the interaction among entries inside the same block, so the block is scored by matrix-product error reduction rather than by entry magnitude.
- **K1C0732**: Within sparse attention, MASA also retains the candidate pattern family and budget rule.
- **K1C0522**: MASA can be integrated into existing sparse attention baselines while keeping their sparse kernels and budgets unchanged.
- **K1C0228**: MASA uses the Frobenius objective because it gives the closed-form unit score in Sec. 3.2, while still measuring a matrix-product error rather than an entrywise attention-map error.
- **K1C0511**: MASA avoids this tensor.
- **K1C0428**: It therefore complements advances in sparse execution and memory management with a theory-grounded correction to the selection principle.
- **K1C0191**: Under matched settings with the original baselines, MASA gives consistent accuracy gains, supporting both the proposed method and the matrix-approximation view of sparse attention.
- **K1C0324**: MASA keeps the sparse units, kernels, and budgets of existing sparse attention methods, but replaces their raw attention-mass ranking with a closed-form score derived from matrix-product approximation error.
- **K1C0654**: First, raw MASA already improves the original sparse baseline in several settings, which supports the matrix-product scoring objective itself.

## Appendix - arxiv-2610.11132v1 - full candidate pool
- **K1C0715**: The SFT response is correct but fully ignores the instruction of using 3 comments.
- **K1C0151**: These results suggest that SFT-as-context can address certain shifts in token probability distributions that are difficult to correct through token-level manipulation.
- **K1C0132**: Table 1: SFT-as-context successfully mitigates the forgetting of general capabilities and maintains high fine-tuned capabilities compared to SFT across all benchmarks.
- **K1C0155**: Language consistency and acknowledgment of non-food queries are only 1.3% and 17.9%, compared with 73.7% and 98.0% for SFT-as-context.
- **K1C0168**: Although SFT-as-context adds a second inference pass after the first inference pass of the SFT model, only a small number of additional tokens is generated in the second pass for most benchmarks.
- **K1C0089**: As shown in Table 1, SFT causes substantial forgetting of general capabilities, reducing general capability scores by 33.2 percentage points on average.
- **K1C0422**: On NutriBench-English, using the context from Qwen3-4B achieves the best macro MAE.
- **K1C0414**: First, we use a Bayesian framework for in-context learning (Xie et al., 2022; Hu et al., 2024) to provide theoretical guarantees that bound the differences in error between parent models, SFT models, and SFT-as-context.
- **K1C0213**: Notably, this holds for a strong proprietary model: providing responses from a fine-tuned Qwen3-4B as context to Gemini 3.5 Flash reduces macro MAE from 17.44 to 14.08 on NutriBench-English, outperforming either model alone.
- **K1C0247**: Table 10: SFT-as-context incurs modest overhead compared with SFT.
- **K1C0393**: Repeating the original task prompt in the SFT-as-context instructions helps instruction-following.
- **K1C0513**: Conversely, the SFT model with its own context retains most of its nutrition estimation gains but fails to recover general capabilities.
- **K1C0205**: The parent response has three comment lines but sorts integers descending with nums.sort(reverse=True).
- **K1C0221**: In addition, we visualize the attention weights and find that the parent model attends more to useful SFT responses and less to irrelevant ones, suggesting that selective attention helps the parent model use the SFT response through in-context learning.
- **K1C0667**: As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router.
- **K1C0056**: As shown in Table 2, using responses from open-source SFT models as context consistently improves the performance of a strong proprietary model on NutriBench-English, achieving lower MAE than either model alone.
- **K1C0508**: This is effectively mitigated by a larger parent: the 32B parent exhibits this failure far less often, yielding a smaller remaining gap for the 32B models than for the 7B ones (an average gap of −1.8 versus −7.5).
- **K1C0714**: Despite its simplicity, SFT-as-context achieves performance close to the parent model on general capabilities while remaining close to the SFT model on fine-tuned capabilities, effectively combining the strengths of SFT and parent models, as shown in Table 1.
- **K1C0723**: Comprehensive experiments across domains, tasks, and model sizes demonstrate the effectiveness of SFT-as-context.
- **K1C0166**: Additionally, SFT-as-context combines fine-tuned and general capabilities within the same response, going beyond what either model can achieve alone.
- **K1C0525**: Table 5: RL-trained models do not show forgetting of instruction-following capability compared to their parent, as measured by IFEval.
- **K1C0337**: This allows the parent model to acquire fine-tuned capabilities from the SFT response through in-context learning while preserving its own general capabilities.
- **K1C0319**: For example, the fallback rate of MathIF is only 3.73%, corresponding to 376 of 10,080 responses, across eight model pairs and seeds 0, 1, and 2.
- **K1C0088**: Furthermore, we use a Bayesian framework to derive theoretical guarantees that bound the error of SFT-as-context relative to the SFT model on fine-tuned capabilities and to the parent model on general capabilities.
- **K1C0463**: In other words, when fine-tuned and general capabilities conflict, the parent model follows the fine-tuned capability under SFT-as-context.
- **K1C0405**: Despite its simplicity, SFT-as-context preserves fine-tuning gains while mitigating forgetting across all 19 evaluated parent-fine-tuned model pairs and 11 benchmarks, spanning mathematical reasoning, coding, nutrition estimation, and general capabilities.
- **K1C0647**: Specifically, the ratio of second-pass to first-pass response tokens is at most 13.0%.
- **K1C0473**: The SFT model significantly improves math correctness, from 40.6% to 65.0%, but fails to follow the format constraints.
- **K1C0650**: Even with oracle selection between the parent and SFT models, neither model alone can reliably satisfy requirements that depend on both sets of capabilities.
- **K1C0179**: The gaps on fine-tuned and general capabilities are over 20 percentage points, much larger than 3.73%.
- **K1C0301**: The theorem identifies sufficient conditions under which SFT-as-context improves in-domain per- formance compared to the parent model while limiting degradation compared to the SFT model.
- **K1C0493**: For the benchmark MathIF, repeating the instruction significantly helps the instruction-following (Hard IF and Soft IF) accuracies of SFT-as-context.
- **K1C0295**: Crucially, SFT-as-context is a novel, training-free approach to mitigating forgetting that requires neither access to model weights nor the fine-tuning process.
- **K1C0050**: We provide two examples where Qwen2.5-7B-Instruct fails to follow the original task instructions during SFT-as-context and only outputs a boxed answer.
- **K1C0600**: We find that the parent model selectively attends to the SFT output based on its effectiveness.
- **K1C0310**: The parent model places greater attention on tokens in the original instruction specifying that non- food queries should be flagged as irrelevant.
- **K1C0462**: Table 6 shows that SFT-as-context largely preserves the harmful responses produced by the abliterated model.
- **K1C0695**: For OCR-Nemotron-1.1-14B, SFT reduces CoQA performance by 73.4 percentage points relative to the parent model, indicating severe forgetting in conversational question answering.
- **K1C0534**: Words like “unrelated” and “irrelevant” are more attended to when the query does not contain a food, demonstrating that the parent model is not distracted by hallucinated context and adheres to the original task instructions.
- **K1C0046**: Remarkably, it can solve queries requiring both fine-tuned and general capabilities, even when neither the parent nor SFT model succeeds alone.
- **K1C0481**: Table 10 shows that, for all math and coding model pairs, the second pass incurs only modest overhead relative to the typically long responses generated by the SFT model in the first pass.
- **K1C0041**: Subfigure (d) shows that the parent model attends more to useful English SFT responses than to hallucinated SFT responses to non-food queries, suggesting that selective attention helps the parent model use the SFT response through in-context learning.
- **K1C0734**: SFT-as-context preserves the correct derivation and result, while using lowercase prose and notation r.
- **K1C0059**: These results highlight a fundamental limitation of routing.
- **K1C0070**: This result also shows that the proprietary model does not merely copy the SFT response during inference.
- **K1C0476**: In the first example below, only outputting the boxed answer violates the requirement of using the word “number.”
- **K1C0375**: Taken together, fine-tuning substantially improves performance on the task the model is fine-tuned on, but at the expense of forgetting general capabilities that the parent model already possesses, e.g., instruction-following and multilingual understanding.
- **K1C0202**: This highlights that SFT-as-context can mitigate severe forgetting while preserving substantial fine-tuning gains.
- **K1C0365**: This approach also extends beyond parent-SFT pairs: responses from a small open-source SFT model can improve a strong closed-source LLM, outperforming either model alone.
- **K1C0684**: Using SFT checkpoints collected from Hugging Face, SFT-as-context achieves 95.0% and 94.1% recovery rates of the fine-tuning gains on AIME 2024 and LiveCodeBench (Jain et al., 2025), respectively.
- **K1C0305**: SFT-as-context brings this performance back to near the parent model’s level, with a gap of only 0.8 percentage points, while preserving most of the gains on LiveCodeBench (39.8 out of 41.8 percentage points).
- **K1C0302**: The SFT-as-context response keeps the same executable Python structure from the SFT context and adds exactly three comment lines.
- **K1C0583**: For example, on NutriBench-Non-English (Dhaliwal et al., 2025), as shown in Figure 1(c), SFT-as-context achieves recovery rates of 84.6% for nutrition estimation and 95.2% for language consistency.
- **K1C0369**: Across 19 parent-fine-tuned model pairs and 11 benchmarks, SFT-as-context preserves 92.0% of the fine-tuning gains on average, while recovering 94.2% of the general-capability performance gap between parent and SFT models.
- **K1C0332**: The SFT-as-context method generates a response with the correct answer and formatting, outperforming both parent and SFT models.
- **K1C0709**: Instead, we propose a training-free method, SFT-as-context, which leverages the in-context learning capability of language models by providing a fine-tuned model’s response as context to its parent model and prompting the parent model to generate the final answer.
- **K1C0466**: For example, as shown in Figure 1(d), the parent model allocates substantially more attention to the SFT response for nutrition queries than for unrelated queries (37.44% versus 15.11%).
- **K1C0159**: Theorem 4 (Closeness to SFT). Under the preceding SAC realizability and posterior concentration assumptions, and Assumption K.3, we have log(1 −ϵ′) ≤ESFT −ESAC ≤−log(1 −η).
- **K1C0288**: At the same time, it achieves an average recovery rate of 94.2% for general capabilities across instruction-following, multilingual tasks, question answering, and planning.
- **K1C0244**: This flexibility allows responses from a small open-source SFT model to serve as context for a stronger closed-source model, even when the latter is not the parent of the SFT model.
- **K1C0380**: Overall, these results suggest that the additional generation overhead introduced by SFT-as-context is modest.
- **K1C0716**: However, with this prompt for training and inference, SFT models fail to preserve these general capabilities.
- **K1C0682**: As shown in Table 3, the parent model with its own context preserves strong general capabilities, but its English and non-English macro MAE remain at 36.6 and 77.4, compared with 18.4 and 63.6 for SFT-as-context.
- **K1C0327**: Here, we extend SFT-as-context to a strong proprietary model, showing that responses from open-source SFT models can further improve its performance with only text input-output access (Section 5.1).
- **K1C0354**: These two examples show that the mean share of prompt-directed attention is higher for useful context (29.95%) than for hallucinated context (15.61%).
- **K1C0374**: The fallback rate is generally low under the permissive token budget.
- **K1C0079**: We introduce SFT-as-context, a training-free method in which the parent model uses the SFT model’s response as context to answer the query.
- **K1C0092**: When a query requires both fine-tuned nutrition estimation capability and general multilingual capability, only SFT-as-context satisfies both requirements.
- **K1C0003**: Figure 1(d) shows that the parent model attends more to useful SFT responses than hallucinated ones, with a 22.33 percentage point difference in the average share of attention allocated to the SFT responses.
- **K1C0066**: LiveCodeBenchIF is a benchmark we constructed, in a similar fashion to MathIF, where we append a short formatting requirement to the end of the original questions from LiveCodeBench.
- **K1C0323**: For the nutrition estimation task, however, the parent model generates relatively longer responses during the second pass, as it performs additional reasoning to compare the SFT-generated reference with its own estimate.
- **K1C0181**: Across 19 parent-SFT model pairs and 11 benchmarks, SFT-as-context remains close to the SFT models on fine-tuned capabilities, with gaps of only 2.2 and 2.1 percentage points on AIME 2024 and LiveCodeBench and 2.0 macro MAE on NutriBench-English, while staying within 2.2 percentage points of the parent models on general capabilities on average.
- **K1C0482**: Thus, the modeled improvement arises from assigning greater probability to an existing domain capability.
- **K1C0596**: Nevertheless, the absolute number of generated tokens remains comparable to that of the other tasks, ranging from a few hundred to slightly over one thousand tokens.
- **K1C0672**: Consistent with prior observations of forgetting after SFT (Chen et al., 2026; Huan et al., 2026), we find that the improvement of fine-tuned capabilities comes at the expense of general capabilities.
- **K1C0599**: More importantly, SFT-as-context requires only standard text input-output interfaces, making it applicable to closed-source models without access to their parameters.
- **K1C0360**: Theorem 5 (Error guarantees for out-of-domain queries). Under Equation 18, Assumption K.4, and the conditional-output model described above, ESAC −Eparent ≤−log(1 −ρo).
- **K1C0248**: Unlike the improvement guarantee over the parent model, this closeness guarantee does not require output separability.
- **K1C0098**: For example, among the three nutrition SFT models, Qwen3-8B shows the largest drop in acknowledging non-food queries, from 99.6% to 10.7%, catastrophically forgetting the instruction-following capability of its parent model.
- **K1C0047**: Table 9 shows that, although both token-level baselines sometimes outperform SFT-as-context on fine-tuned capabilities, neither successfully mitigates forgetting of general capabilities.
- **K1C0102**: Instead, it can combine task-specific information from the SFT response with its own capabilities to produce a more accurate final answer.
- **K1C0627**: Thus, when the SFT context only weakly suppresses the parent posterior, the additional out-of- domain error is small: −log(1−ρo) = ρo +O(ρ2 o) as ρo →0.
- **K1C0652**: These results suggest that the gains of SFT-as-context cannot be explained solely by the SFT-as-context instructions or an additional inference pass.
- **K1C0170**: This selective attention suggests that the parent model can use useful information from SFT responses through in-context learning while limiting the influence of irrelevant context, providing a possible explanation for how SFT-as-context mitigates forgetting while preserving fine-tuned capabilities.
- **K1C0576**: However, we identify a failure case for these methods.

## Appendix - arxiv-2610.11135v1 - full candidate pool
- **K1C0506**: JevKT is significantly better than the counting kNN statistic alone on only 1/7 datasets with full data, i.e., with all learners available the statistic carries most of the signal; the LLM’s contribution appears when learners are few (Figure 3).
- **K1C0027**: On the A state itself Jev reaches .761 against .752 for A, higher on all seven datasets (by .002 to .021); the longer JevKT state helps Jev (.776) but not Qwen3.5-9B (.727).
- **K1C0314**: Every form of evidence improves on Jev0-shot (.706), and the similar-learner statistic alone (.729) is almost as good as the full JevKT input (.730).
- **K1C0309**: JevKT (.713) and Jev0-shot (.704) stay well above LOKT (.664), but the best deep KT model, trained on all learners and chosen on test, is ahead (.729; JevKT is better on 1/7 datasets; Table 10).
- **K1C0523**: These vote frequencies are also poorly calibrated (Figure 5, Table 13).
- **K1C0183**: With the state alone (N=0) the predicted probabilities correlate at Pearson .995–.999 (mean absolute difference .008), AUC changes by −.001 on average, and none of 21 dataset–metric pairs differs significantly; with the JevKT input at N=8 the correlation is .991–.998 and 1/21 pairs differs (an F1 change of .004).
- **K1C0350**: Second, shots help only when they are KC-matched; random shots are neutral or slightly harmful at every k.
- **K1C0464**: JevKT leads on average up to N=64 (on 7/7 datasets at N=8 and 4/7 at N=64); the lead shrinks with N and disappears between N=64 and 128 on average, at different N for different datasets.
- **K1C0263**: Without any data from the target platform, Jev beats deep KT trained on 8 learners on average and prompted System-Two LLM-KT on every dataset, at a fraction of its cost; with evidence from the logged learners, JevKT stays ahead until super- vised KT catches up between 64 and 128 learners.
- **K1C0304**: First, the similar-learner statistic is the largest single gain, larger than item and KC population statistics.
- **K1C0054**: (ii) Row continuation of the original public files shows no dataset-specific recall.
- **K1C0694**: At N=16 the similar-learner statistic alone raises Jev0-shot from .706 to .729, 64 KC-matched shots alone to .724, and both together to .730.
- **K1C0015**: They pile up at 0 and 1, and the mean ECE of Thinking-KT is .253 (LOKT .209), against .084 for the single Jev0-shot pass.
- **K1C0448**: With evidence from the logged learners, JevKT stays significantly ahead of the best deep KT model up to 16 learners (+.033 AUC at N=8, 7/7 datasets) and on average up to 64; supervised KT catches up between 64 and 128 learners.
- **K1C0194**: Only DLKT and CLST need gradient training; Jev0-shot and JevKT predict for a new course immediately.
- **K1C0687**: At N=0, Jev0-shot is significantly better than LOKT and Thinking-KT on all seven datasets.
- **K1C0005**: At N=8 the prior alone reaches .706, the similar-learner statistic alone .595, and both together .722, against .689 for the best deep KT model (Table 1).
- **K1C0258**: The lead is largest for learners with very low or very high accuracy so far.
- **K1C0408**: With N=8 learners, JevKT is as well calibrated as the best deep KT model (ECE .070 vs. .076; Brier .182 vs. .192), without any post-hoc scaling such as temperature scaling (Guo et al., 2017).
- **K1C0402**: Yes, an off-the-shelf System-One LLM already per- forms KT when few or no learners are logged.
- **K1C0444**: Long reasoning marks hard cases rather than fixing them.
- **K1C0395**: For the weights and readers we tested, the typed format does not produce the gain; the model does.
- **K1C0391**: Holding the Qwen3.5-9B weights fixed, a typed one-pass head (B0) lowers AUC relative to the plain readout (A), and a Jev-distilled student (C) does not exceed A, with full data or at N=8.
- **K1C0108**: One JevKT prediction takes 325 ms in a single call and costs $886 per million predictions, about 1/5 of Thinking-KT, which needs $4,360 and 41.7 s per prediction even with its ten votes issued in parallel; Jev0-shot costs $44.
- **K1C0551**: Figure 7: The cold-start advantage of training-free JevKT (Jev + 64-shot + kNN) shrinks as more learners are logged.
- **K1C0031**: It also beats System-Two Thinking-KT (.650) on all seven datasets with one call instead of ten, at about 1/100 of its API cost (Section 5.4).
- **K1C0674**: As a rough proxy for a different Jev-family model, replacing Jev with its distilled student JEV-9B on the same inputs lowers AUC by .007–.074, which bounds how much our numbers could move under a weaker version.
- **K1C0287**: Under cold start (Table 15), JevKT is significantly better than the best deep KT model on 7/7 datasets at N=8, and the number of significant datasets falls as N grows, to 1/7 at N=256.
- **K1C0633**: JevKT leads in every slice with enough targets.
- **K1C0002**: For the Qwen3.5-9B backbone of Thinking-KT, reasoning does not help, as it is never significantly better than the same model without reasoning.
- **K1C0635**: All examples and statistics come from U and the target’s past; a leak audit (including a test that the input is unchanged when rt is flipped) passes in every setting.
- **K1C0431**: On the A state itself Jev reaches .761 against .752 for A, higher on all seven datasets (by .002
- **K1C0008**: The lead is Holm-significant on 7/7 datasets at N=8 and 6/7 at N=16, 3/7 at N=32 and 2/7 at N=64 (Table 15).
- **K1C0014**: Tables 34–41 (Appendix M) give the mean over datasets per position for every model at each N: with N=64 JevKT is still above every deep KT model at positions 2–49, and with all learners it is behind the strongest deep KT models at every position, as in P1.
- **K1C0417**: KC-matched shots help less than the statistic (.720 with 16 shots, .724 with 64), and combining the two is sub-additive: the gain over the statistic alone is clear only on DBE-KT22.
- **K1C0333**: CLST is below JevKT in 12/12 cells with N≥8 and be- low the best of the eleven core deep KT models in 11/12, so fine-tuning an LLM on a few learners does not reach what the off-the-shelf System-One model achieves without training.
- **K1C0082**: At N=0, Jev0-shot is the strongest training-free method on every dataset.
- **K1C0086**: Feeding the identical serialised state to Jev instead of Qwen3.5-9B raises AUC in all 35 cells.
- **K1C0172**: On six synthetic datasets generated after the model release, JevKT is still at or above the best deep KT model at N=8.
- **K1C0107**: JevKT is above the best deep KT model at every position, already for the second to fifth interactions (.714 vs. .691), when the new learner has shown little evidence, and in 33/35 dataset–position cells (Table 9).
- **K1C0671**: No dataset is flagged (Table 17).
- **K1C0126**: The vote-frequency readouts of LOKT and Thinking-KT are the worst calibrated on every dataset; Jev0-shot is calibrated far better without any training data, and with eight learners JevKT and the best deep KT model are comparable.
- **K1C0039**: (i) ID-only probes: asked to predict item difficulty or the skill of an item from its ID alone, Jev and three open LLMs are no better with the real ID than with a format-matched fake ID on any dataset after Holm correction.
- **K1C0262**: Its limit is not cost but data, as it must be retrained for every course and needs logged learners to train on.
- **K1C0278**: Vote frequencies of System-Two LLM-KT pile up at 0 and 1, while the single-pass readout of Jev follows the diagonal with a slight underconfidence.
- **K1C0577**: Distilling Jev into these weights (C, JEV-9B) does not beat A (.679 and .741), and the same holds at N=8 (A .700, B0 .659, C .699).
- **K1C0335**: The statistic therefore carries almost all of the gain, and the shots add to it clearly only on DBE-KT22; we keep both because they never hurt and match the configuration selected on full data.
- **K1C0034**: On identical targets the JevKT input adds a similar, small amount to Jev (+.016) and to DeepSeek (+.010), significant on 2/7 and 1/7 datasets, and the two gains never differ significantly; the gap between the models (.077 at N=0) is set by the model, not by the input.
- **K1C0416**: With no learners logged, Jev0-shot reaches a mean AUC of .706, above the best deep KT model trained on 8 learners (.689) and above Thinking-KT on all seven datasets.
- **K1C0363**: Third, repeats, paraphrases, formats, longer histories and option weights do not change AUC, so JevKT keeps the simplest state.
- **K1C0407**: On identical targets the evidence adds +.016 AUC to Jev, significantly on 2/7 datasets (DBE-KT22 and Algebra05), so its contribution is real but small.
- **K1C0503**: LOKT, whose only use of the logged learners is answer-option weights, barely moves with N (.672 at N=8 and .672 with all learners, against .671 at N=0) and stays below both.
- **K1C0515**: A leak audit passes in every setting, including a test that the input does not change when the target out- come is flipped.
- **K1C0737**: The ranking of the inputs is the same as with full data.
- **K1C0331**: The crossover therefore lies between 64 and 128 learners on average and varies by dataset (Figure 7, Appendix D).
- **K1C0143**: A cold-start evaluation on identical targets (7 datasets; few training learners, new learners, new items) shows how long the lead lasts as learners are logged (RQ2, RQ3); a training-free input recipe (JevKT), whose gain comes mostly from one similar-learner statistic, keeps it until supervised KT takes over.
- **K1C0273**: Longer reasoning does not help either.
- **K1C0504**: Among the readers we tested, the gain comes from the model rather than the typed format; the input recipe helps other LLMs as much as it helps Jev.
- **K1C0232**: With few learners the prior carries the prediction and the evidence adds to it; as N grows the evidence becomes reliable, and supervised KT, which learns from the same evidence, catches up.
- **K1C0601**: This is above the strongest training-free LLM-KT baseline, LOKT (.671), and above the best deep KT model trained on 8 learners (.689; higher on 5/7 datasets).
- **K1C0467**: JevKT is ahead of the best deep KT model by +.033, +.023 and +.016 mean AUC at N=8, 16 and 32 (on 7/7, 7/7 and 7/7 datasets); the mean difference is +.004 at N=64, −.002 at N=128, −.008 at N=256 and −.028 with the full training data.
- **K1C0230**: Classical KT models (BKT, PFA) fitted on the same learners are below both (Ap- pendix D).
- **K1C0413**: KC-matched shots help and saturate at k≈64, random shots do not, and the similar-learner statistic adds on top; the ranking on the development split transfers to test.
- **K1C0297**: Asked about an item’s difficulty or skill from its ID alone, Jev and three open LLMs do no better with real IDs than with format-matched fake IDs on any dataset, and continuing rows of the public files shows no recall.
- **K1C0322**: Within each dataset, the third of targets with the longest reasoning has lower AUC than the shortest third (.668 vs. .719 at budget 2048; .675 vs. .726 at 1024), and reasoning length correlates with the absolute error (Spearman +.29), also among targets on which all ten votes agree.
- **K1C0186**: Table 3: Reasoning does not help Qwen3.5-9B on KT; a single System-One pass does better.
- **K1C0176**: The development-split ranking transfers to test (Figure 2).
- **K1C0664**: Jev0-shot is already within .03 of the best deep KT model without any training data, and both Jev variants are far above LOKT and Thinking-KT (.657).
- **K1C0222**: The gain is not confined to easy cases (Table 14, Appendix I).
- **K1C0421**: Conversely, when the identical serialised input is read by Jev instead of Qwen3.5-9B, AUC rises in all 35 cells (7 datasets × 5 conditions), e.g. from .727 to .776 with the JevKT input.
- **K1C0477**: Among the readers we tested, the gain comes from the model, as other LLMs reading the identical input, directly or through the vendor’s System-One adapter, are worse on every dataset, and contamination checks find no sign of memorised data.
- **K1C0618**: A typed one-pass head without training (B0) is worse than reading the label probability directly (A), .630 vs. .688 AUC, and .701 vs. .752 with the similar-learner statistic.
- **K1C0212**: Only Jev and the Jev-distilled JEV-9B (.687 at N=0, .699 at N=8) come close to or exceed the best deep KT model trained on 8 learners (.689), while Laya, an open-source model that reproduces Jev’s typed interface with a small encoder, stays near chance (.536).
- **K1C0404**: At N=0, GPT-4o-mini (.680), Gemini-2.5-Flash-Lite (.670) and DeepSeek-V4-Flash (.626) are below Jev0-shot (.706) on every dataset (paired bootstrap, p<.01).
- **K1C0199**: Priced at the same GPU rental rate, DLKT is far cheaper, since training on all learners costs at most $0.08 and a million predictions well under $1.
- **K1C0093**: Without training data, Jev0-shot is above LLM-based KT on all seven datasets and above deep KT trained on 8 learners on average; JevKT stays ahead of deep KT up to N=64 on average.
- **K1C0154**: With no learner logs, an off-the-shelf System-One LLM (Jev) outperforms deep KT trained on 8 learners on average and prompted System-Two LLM-KT on all seven datasets (RQ1).
- **K1C0249**: For new learners the advantage holds from their first interactions, whereas on unseen items with all learners logged, deep KT remains ahead.
- **K1C0252**: Because the best deep KT model is chosen on test in every cell, these margins are conservative.
- **K1C0053**: Without any data from the target platform, Jev0-shot reaches .706 mean AUC (first block of Table 1).
- **K1C0348**: On seven datasets, Jev without any data from the target platform reaches a mean AUC of .706, above the best of 28 deep KT models trained on 8 learners (.689) and above System-Two Thinking-KT on all seven datasets (.650) at about 1/100 of its API cost.
- **K1C0472**: Among the readers we tested, the gain is specific to Jev, since three other LLMs queried with the byte-identical typed request through the official System-One adapter fall below it on all seven datasets, and reader swaps and contamination checks find no evidence that the input format or memorised data explain the gain.
- **K1C0048**: A reasoning budget of 1024 or 2048 tokens never improves AUC significantly over the same model without reasoning, while one Jev pass beats Thinking-KT on all seven datasets (Holm-corrected, ∆AUC +.038 to +.073 against the budget of 2048).
- **K1C0257**: At N=8 JevKT leads both on items that the logged learners answered (+.036) and on items none of them answered (+.028), and the lead is largest for learners whose accuracy so far is very low or very high (+.050 and +.063), where eight learners give a supervised model little to learn from.
- **K1C0676**: JevKT is ahead of the best deep KT model only on Junyi; averaged over datasets the gap (.713 vs. .729) is close to the full-data gap of P1, so unseen items do not by themselves favour the System-One model.
- **K1C0594**: With few learners, training-free JevKT outperforms the best of 28 DLKT models and stays at or above Jev0-shot (dashed); supervised KT catches up between N=64 and 128 on average and leads with full data.
- **K1C0245**: BKT and PFA stay well below JevKT and the best deep KT model at every N.
- **K1C0434**: Adding examples and a similar-learner statistic from the logged learners (JevKT) raises this to .722; JevKT stays significantly ahead of deep KT up to 16 learners and ahead on average up to 64, and supervised KT catches up between 64 and 128 learners.
- **K1C0461**: Unseen items alone therefore do not reverse the full-data result, and the advantage of the System-One model comes from having few learners, not from unseen items.
- **K1C0264**: Items that no logged learner answered are where an ID-based deep KT model has no item-specific signal; JevKT keeps most of its lead there.
- **K1C0587**: Third, Laya is an open-source reproduction of Jev’s typed interface built on a ModernBERT encoder; it stays near chance, consistent with its own model card.
- **K1C0200**: Controlled analyses (reader swap, other LLMs behind the same interface, contamination checks) find that the gain comes from the model rather than from the typed format or memorised data.
- **K1C0455**: Relabelling IDs and removing names changes Jev0-shot AUC by at most .012, never significantly (Holm), and no dataset is flagged.
- **K1C0713**: With hyper-parameters tuned on the validation learners of each cell (four strong pyKT models, eight configurations each), deep KT stays below JevKT by +.070, +.042, +.030 and +.010 at N=8, 16, 32 and 64 (Holm-significant on 7/7, 7/7, 5/7 and 4/7 datasets), so default hyper-parameters do not explain the gap.
- **K1C0606**: JevKT’s 64 shots make its prompt long, so it costs more than Jev0-shot but still about one fifth of Thinking-KT, and it answers in one call instead of ten.
- **K1C0022**: Jev’s remaining error is a mild underconfidence, as observed accuracy is slightly above the predicted probability across the range.

## Appendix - arxiv-2610.11291v1 - full candidate pool
- **K1C0619**: In contrast, Semi-OPD is often more stable, as it distills on shorter contexts while covering full trajectories and exposing the student to more teacher-preferred tokens.
- **K1C0680**: Figure 4 | Teacher-rollout SFT improves overlap ratios but reduces final performance after Semi-OPD.
- **K1C0579**: Semi-OPD exactly satisfies the above requirement by providing full trajectory coverage with shorter rollout lengths.
- **K1C0692**: The difference is especially pronounced for Qwen3 thinking-mode pairs: OPD undergoes a substantial performance collapse during training, whereas Semi-OPD continues to improve.
- **K1C0712**: OPD is only useful for aligned teacher–student pairs with high overlap in output tokens; for misaligned pairs, Semi-OPD is a better alternative in both accuracy and training efficiency.
- **K1C0386**: We evaluate across 17 teacher–student pairs spanning 1.5B to 235B parameters and three model families in both thinking and non-thinking modes, covering the most commonly used student–teacher pairs in the OPD literature.
- **K1C0084**: Moreover, rather than focusing on a few model pairs, we evaluate 17 diverse model pairs and show that this benefit is strongly correlated with the initial teacher–student top-𝑘overlap, with lower-overlap pairs benefiting more.
- **K1C0537**: Over the last 10 shared steps, OPD’s rollouts are 7–113% longer than Semi-OPD’s in 15 of 16 pairs.
- **K1C0689**: We observe that Semi-OPD outperforms OPD on 14 of 17 pairs with improvements of up to ∼13% over OPD at the last step, and the largest gains are generally achieved on pairs with lower initial overlap.
- **K1C0544**: This indicates that Semi-OPD exposes the student to more teacher-preferred tokens, i.e., more on-policy w.r.t. the teacher, whereas OPD more often produces signals that suppress the student’s own sampled tokens.
- **K1C0655**: Semi-OPD is faster because rollout generation and teacher scoring are done once before training.
- **K1C0570**: Together, these findings suggest that Semi-OPD benefits from preserving student-anchored rollouts that remain effective teacher supervision and broad coverage of the reasoning process.
- **K1C0338**: Table 1 | Semi-OPD outperforms other OPD variants when the initial student–teacher overlap ratio is low, and remains comparable when the ratio is high.
- **K1C0017**: On non-thinking pairs, student entropy stays similar between the two methods, while teacher entropy is usually higher under OPD, indicating that OPD’s rollouts drift toward regions where the teacher is less certain.
- **K1C0698**: For a fixed student, the same rollout cache can also be reused across different teachers; evaluating a new teacher only requires computing its log-probabilities on the cached rollouts.
- **K1C0383**: These advantages can outweigh the benefits of fully on-policy sampling under large teacher–student mismatch.
- **K1C0175**: Figure 9 | Switching to OPD converges toward a rollout-determined equilibrium, largely independent of initialization.
- **K1C0566**: Since Semi-OPD trains only on rollouts from က0, the initial rollouts need to meet a minimum quality threshold for effective distillation.
- **K1C0364**: Our analyses highlight a
key principle: effective distillation requires balancing
on-policyness w.r.t. both the student and the teacher,
with the initial teacher–student overlap serving as a
practical indicator of when to use OPD or Semi-OPD.
- **K1C0133**: As shown in Fig. 4, we observe that (1) SFT on teacher rollouts slightly increases teacher–student overlap ratios, while Semi-OPD still outperforms OPD on both pairs, albeit by a smaller margin; and (2) Our Semi-OPD without the additional teacher-rollout SFT stage can outperform Semi-OPD with this stage, indicating that SFT on teacher rollouts is unnecessary.
- **K1C0533**: We show that a simple alternative, Semi-OPD, which distills from offline rollouts generated by the initial student, can often outperform OPD in both accuracy and training efficiency.
- **K1C0645**: As shown in Fig. 17, the top-64 overlap between the current student and the teacher on the training tokens generally rises under both methods as the student moves toward the teacher, but the ordering differs across different model pairs.
- **K1C0114**: This can further reduce the cost of comparing or selecting teachers in practice.
- **K1C0100**: We find that the gain of Semi-OPD over OPD is strongly correlated with the alignment between the initial teacher and student, which can be quantified by the teacher–student top-𝑘overlap ratio over output tokens, as shown in Fig. 2a.
- **K1C0479**: As shown in Fig. 11, models distilled only on math-heavy datasets [26] also improve on HumanEval and HumanEval+, with Semi-OPD remaining ahead of OPD.
- **K1C0298**: Importantly, Semi-OPD also outperforms OPD under top-𝑘reverse KL, as shown in Fig. 8, indicating that its advantage is not specific to the sampled-token objective.
- **K1C0196**: As shown in Figs. 15 and 16, on thinking pairs OPD drives both the student’s and the teacher’s next-token entropy on the training tokens well below Semi-OPD’s in 7 of 8 pairs (the exception is R1-Distill-7B ←DeepCoder-14B), i.e., OPD increasingly trains on tokens that both models already predict with high confidence.
- **K1C0491**: As shown in Fig. 9, on low-overlap pairs, regardless of initialization, all runs eventually converge to the performance level reached by OPD initialized from the initial student model under the same rollout cap, while the warm start only affects the convergence trajectory.
- **K1C0502**: (2) On the Nemotron-Cascade-2 pair, which has a high overlap ratio of approximately 89%, our Semi-OPD remains competitive with other OPD baselines and falls only slightly behind the best baseline by 0.7% accuracy, while reducing the training time by 2.2x as compared to FastOPD and 4.5x compared to OPD.
- **K1C0173**: The only exception is R1-Distill-1.5B ←JustRL-1.5B, whose OPD rollouts get shorter.
- **K1C0616**: In contrast, Semi-OPD on initial student rollouts usually distills over shorter contexts while covering full trajectories, making it more stable.
- **K1C0275**: In addition, rollout generation, teacher scoring, and student optimization are executed as separate phases, each of which can use the full GPU cluster rather than partitioning resources among concurrent student generation, teacher serving, and training.
- **K1C0435**: To answer this, we propose a simple and efficient alternative called semi-on-policy distillation (Semi-OPD), where rollouts are sampled once from the initial student before any training and reused throughout distillation, thus making both rollout and teacher logit generation offline.
- **K1C0312**: (c, d) SFT on teacher rollouts negatively impacts final performance when combined with Semi-OPD.
- **K1C0693**: We further find that the choice between OPD and Semi-OPD depends on the alignment between the initial teacher and student, quantified by an output-token overlap ratio: OPD is beneficial only when the two are highly aligned with high overlap ratios.
- **K1C0419**: Effective distillation requires both the on-policyness of training rollout w.r.t. the student and closeness to the teacher; OPD prioritizes the former but may sacrifice the latter.
- **K1C0235**: Beyond proposing Semi-OPD as an efficient alternative, our work motivates the community to rethink when to use OPD and to study stronger OPD variants with meaningful teacher–student pairs.
- **K1C0030**: In other words, Semi-OPD trades some student on-policyness for teacher on-policyness, which is also echoed by our observation that Semi-OPD exposes the student to more tokens preferred by the teacher.
- **K1C0076**: This suggests that repeated on-policy sampling drives distillation toward an equilibrium determined by the online rollout data distribution rather than the initial checkpoint.
- **K1C0127**: As shown in Fig. 14, Semi-OPD keeps a larger share of positively supervised tokens (𝑝𝑇> 𝑝𝑆) than OPD in 15 of 16 pairs.
- **K1C0081**: For example, as shown in Fig. 12, with a base student, the initial rollouts are too weak and Semi-OPD underperforms OPD; with an instruction-tuned student, Semi-OPD regains its advantage.
- **K1C0701**: We observe that (1) on the Qwen3-1.7B (non-thinking) and Qwen3-4B (non-thinking) students, which have low teacher–student overlap ratios, Semi-OPD outperforms all other baselines in accuracy while also being the most efficient, e.g., achieving +7.1% and +8.8% higher accuracy with 35× and 19.5× less training time than Relay-OPD on the two pairs, respectively, according to Fig. 1 and Tab. 4.
- **K1C0389**: Thus, Semi-OPD is most suitable when the initial student already produces meaningful trajectories.
- **K1C0226**: We also note that, while [16] frames fixed rollouts primarily as an efficient approximation to OPD, our results show that freezing the rollout cache can improve distillation when the initial teacher–student overlap is low.
- **K1C0725**: This indicates that the benefit of Semi-OPD does not come merely from using a fixed rollout cache.
- **K1C0707**: The two quantities are strongly correlated (Pearson’s 𝑟= −0.73 across 17 pairs): pairs with lower initial overlap ratios tend to benefit substantially more from Semi-OPD, while OPD is only needed for pairs with high overlap ratios.
- **K1C0007**: At low overlap, Semi-OPD outperforms OPD which can even degrade; at high overlap, Semi-OPD can slightly lag behind.
- **K1C0243**: Semi-OPD decouples data collection from optimization.
- **K1C0696**: In contrast, Relay-OPD requires interleaved student and teacher generation throughout training, leading to higher training cost.
- **K1C0678**: Similar to Lightning OPD [16], this removes online rollout generation and teacher inference from the training loop, so all GPUs can be used for rollout generation, teacher log-probability scoring, and student training.
- **K1C0078**: As shown in Fig. 7, Semi-OPD maintains a larger fraction of such tokens than OPD throughout training.
- **K1C0139**: Semi-OPD fails when the student is a base model
- **K1C0283**: OPD rollouts grow longer and use more self-correction words, eventually exceeding the teacher (dotted), while the frozen rollouts sampled once from the initial student 𝜋0 do not.
- **K1C0318**: As shown in Fig. 5(a, b), Semi-OPD consistently outperforms teacher-rollout distillation.
- **K1C0366**: Our Semi-OPD achieves much improved/comparable accuracy for teacher–student pairs with low/high overlap, respectively, while reducing training time by up to 11.4× over OPD.
- **K1C0702**: Switching to OPD can either decrease or improve performance (see Fig. 10), with trajectories approaching the performance level of OPD trained from scratch under the same rollout cap.
- **K1C0572**: (b) SFT on teacher rollouts followed by Semi-OPD still outperforms OPD but underperforms Semi-OPD alone.
- **K1C0146**: The accuracy evolution curves in Fig. 2b further show that (1) when this overlap ratio is low, continually regenerating rollouts from the evolving student can shift training toward increasingly teacher-misaligned trajectories, making strict on-policyness counterproductive; (2) OPD is only beneficial when the teacher and student are aligned with a high overlap ratio.
- **K1C0446**: Semi-OPD exposes the student to more tokens preferred by the teacher.
- **K1C0178**: Given the target domain and initial teacher–student pair, the choice between OPD and Semi-OPD should be guided by the measured overlap ratio, rather than blindly choosing OPD.
- **K1C0686**: We find that freezing rollouts can also improve accuracy.
- **K1C0609**: By systematically com-
paring OPD with the proposed Semi-OPD across di-
verse teacher–student pairs, we show that continually
regenerating student rollouts is often unnecessary and
can even be harmful, especially when the teacher and
student are poorly aligned.
- **K1C0069**: For misaligned pairs, student rollouts can become increasingly off-policy w.r.t. the teacher as context length grows, weakening the distillation signal.
- **K1C0457**: We find that Semi-OPD outperforms OPD on 14 of them, with up to +13.6% accuracy and 11.4× training speedup as shown in Fig. 1, and achieves comparable performance (within a 0.1%–2.6% gap) on the remaining three.
- **K1C0401**: We show in Sec. 2.3/ 3 that Semi-OPD outperforms Lightning OPD and that SFT on teacher rollouts has negative effects.
- **K1C0299**: The overall accuracy–training-efficiency trade-off is shown in Fig. 1, where Semi-OPD achieves up to an 11.4× speedup over standard OPD and a 2.7× speedup over the fastest baseline, FastOPD.
- **K1C0085**: Rather, retaining student-generated trajectories to maintain student on-policyness is also important.
- **K1C0400**: On the remaining three pairs, Semi-OPD still achieves comparable performance, with gaps of 0.1–2.6%.
- **K1C0260**: The growth is largest for the low-overlap non-thinking Qwen3 pairs, where OPD’s rollouts often exceed the teacher’s own length.
- **K1C0367**: As shown in Fig. 6, we vary the rollout length (i.e., the rollout cap) used for OPD training and observe that increasing the rollout cap can hurt the low-overlap pair while benefiting the higher-overlap pair.
- **K1C0207**: As shown in Fig. 5(c, d), restricting supervision to the first quarter substantially slows convergence and reduces final accuracy, whereas training on full trajectories achieves the best peak accuracy.
- **K1C0470**: Our deeper investigation suggests that effective distillation requires on-policyness w.r.t. both the student and the teacher.
- **K1C0691**: (a) SFT on teacher rollouts slightly increases the initial top-64 overlap.
- **K1C0169**: In contrast, for a high-overlap pair, as shown in Fig. 10, switching from Semi-OPD to OPD improves performance and closes most of the gap with OPD applied from scratch.
- **K1C0673**: Across 17 teacher–student pairs ranging from 1.5B to 235B parameters, Semi-OPD outperforms OPD in 14 cases, with up to +13.6% accuracy and 11.4× training speedup.
- **K1C0423**: This suggests that the gains are not limited to fitting the math training distribution but transfer to broader reasoning tasks.

## Appendix - arxiv-2610.11519v1 - full candidate pool
- **K1C0265**: This is the usual distinction between Q and Q−V ; in expectation, sampled OPD still follows the negative full-vocabulary reverse-KL gradient.
- **K1C0524**: The hypotheses of Proposition 4 thus describe the long responses, which carry most of the tokens, and the small gain of centering in Section 4.1, about half a point at every weight, is what acting on the rest is worth.
- **K1C0058**: Both RA combinations exceed teacher-only OPD in macro Avg@8 and Pass@8 at both sizes, by 1.80–2.96 and 2.73–3.90 points (Table 10).
- **K1C0521**: Teacher adaptation thus preserves the mean identity, bounded guidance, and uniform vanishing with distributional agreement at each scoring step, and the fixed-prefix expected-gradient identity holds with q = qϕk.
- **K1C0575**: The divergence between the uncentered label and the direct loss grows with the weight (update cosine 0.97, 0.91, and 0.83 at 5, 10, and 20), as does the margin of RA over the direct loss in Table 2, and it lies mostly on tokens with 0.1 ≤p(at) < 0.5 (55%), the forks of Section 4.3.
- **K1C0608**: Removing either baseline, replacing the residual by the log ratio, or adding direct supervision of the teacher’s top token lowers performance.
- **K1C0517**: Removing both operations costs 1.73 Avg@8 and 2.77 Pass@8 points; the state value then also enters the response mean, shifting it by −0.32 on average and beyond 0.5 on a quarter of the offline responses (Table 16).
- **K1C0520**: At its best weight, β = 0.2, it remains 1.97 Avg@8 and 2.70 Pass@8 points below full RA.
- **K1C0234**: Without the student value baseline this cancellation fails, and the disagreement levels of other prefixes enter each token's update through centering.
- **K1C0355**: None of this is imposed by hand.
- **K1C0486**: At one prefix the student value baseline leaves the expected update unchanged (Proposition 1(ii)).
- **K1C0152**: Since D/L →0, the residual pushes a confidently wrong mode more gently than the log ratio.
- **K1C0197**: With both operations, clipped to [−5, 5] or not, the log ratio stays above verifier-only training at every swept weight, and the probability residual is better still, by 1.21 Avg@8 and 1.70 Pass@8 points over the best log variant.
- **K1C0353**: RA then centers the local advantages within the response and adds them to the verifier advantage, At = AV + λ(Ad t −A d), where A d is the response mean and λ the guidance weight.
- **K1C0666**: Co-RA extends the construction to a teacher that learns from the student’s attempts.
- **K1C0613**: Yet each adapted teacher scores 0.8–2.3 macro Avg@8 and 0.7–3.5 Pass@8 points below the frozen teacher (Appendix D.9), while the students it guides improve: it is a better guide, not a better solver.
- **K1C0567**: Table 1: Residual guidance improves both RLVR estimators on every benchmark and metric, and the adapted teacher raises accuracy further.
- **K1C0505**: We propose Residual Advantage (RA), which treats the teacher–student probability residual as a bounded one-step reward, subtracts the corresponding state value under the student policy to form a standard advantage, and centers the result within each response before adding it to the verifier advantage.
- **K1C0568**: The verifier moves the response along its mean score direction and the teacher along the covariance between local advantages and scores.
- **K1C0469**: Table 2: Every residual variant improves on verifier-only training at every tested weight, and full RA stays above every control at every matched weight.
- **K1C0141**: The reward is immediate, so nothing is propagated to earlier positions; credit across positions comes from the verifier advantage.
- **K1C0569**: Across two students, two estimators, and three mathematical benchmarks, 2 Preprint RA improves all 24 three-seed benchmark means of its base estimator, both combinations surpass teacher-only OPD, and Co-RA raises accuracy further with mixed changes in coverage.
- **K1C0073**: At fixed Q and λ, the map q 7→p⋆is nonexpansive in ℓ2.
- **K1C0040**: The log ratio also vanishes at exact agreement but admits no such bound, since it diverges at a token of vanishing student probability while ∥p −q∥2 →0.
- **K1C0101**: RA maintains higher training accuracy than its verifier-only estimator over most of training.
- **K1C0320**: With Qwen3-1.7B-Base and Qwen3-4B-Base students and a Qwen3-8B teacher, RA combined with GRPO or REINFORCE++ improves the underlying sequence-advantage algorithm in all 24 comparisons on three mathematical benchmarks, raising macro Avg@8 by 1.7–3.6 points and Pass@8 by 3.9–6.3 points.
- **K1C0640**: Local advantages and scores are both martingale differences under the student's sampling, so every cross-position term vanishes.
- **K1C0064**: Table 30: The adapted teacher is a worse solver than the frozen teacher.
- **K1C0556**: Orthogonality of the label components does not extend to their parameter gradients (Appendix A.7).
- **K1C0187**: The teacher part pushes toward the peak apart from the shift by ¯hi, as the next proposition shows.
- **K1C0620**: The two label components are orthogonal, but these two parameter directions need not be, so the mean identity fixes the teacher’s share of the label and not of the update.
- **K1C0475**: At a fixed guidance weight, the guidance term therefore vanishes uniformly when student and teacher agree uniformly at the scored prefixes.
- **K1C0553**: In Table 7, the rare action supplies most of the expected update despite its low sampling probability.
- **K1C0538**: Verifier-only training lifts macro Avg@8 by 12 to 15 points over the untrained students; RA adds 1.7 to 3.6 points and Co-RA 2.8 to 5.0 over the corresponding estimator.
- **K1C0315**: To this end, we propose Residual Advantage (RA).
- **K1C0514**: Table 3: The probability residual with both baselines is the best construction, and no log-ratio variant reaches it at any swept weight.
- **K1C0113**: In training, OPD also starts more slowly than REINFORCE++ and stays below RA+REINFORCE++ over most of the shared budget (Appendix C).
- **K1C0700**: The guidance term has zero mean within each response, so the verifier advantage remains the response’s mean label and the teacher only redistributes credit among the steps within it.
- **K1C0284**: Every trained run exceeds the untrained student’s Pass@8 on every benchmark, and Appendix D.7 follows the 1.7B REINFORCE++ runs to Pass@512.
- **K1C0259**: Added to RA, it lowers macro Avg@8 by 2.05–2.16 points and Pass@8 by 3.41–3.91 points, and at every weight each seed falls below the same seed of RA, whereas doubling RA’s own weight does not (Table 2).
- **K1C0509**: Within the tested budget RA thus raises the coverage the student can reach.
- **K1C0051**: Removing the student value baseline lowers both macro scores, by 2.09 Avg@8 and 3.58 Pass@8 points at the reference weight and similarly at weights 5 and 20 (Table 2).
- **K1C0285**: The residual puts 59% of its guidance on the 12% of tokens with 0.1 ≤p(at) < 0.5, five times their share, where the student is choosing among live alternatives.
- **K1C0227**: Adding the raw log ratio improves both macro scores over plain REINFORCE++ at β ≤0.6 and lowers both at β ≥1.2, whereas the complete RA guidance term improves both at every tested weight (Tables 23 and 24).
- **K1C0330**: Bounded sensitivity is the bounded-influence property of the quadratic comparison (Hampel, 1974; Basu et al., 1998), and Appendix A.4 places it among the alternatives.
- **K1C0370**: On the next batch, RA's step raises the verifier objective 1.10–1.16 times as much as the direct loss's step and wins 66–74% of paired comparisons.
- **K1C0021**: The centered log ratio puts 50% of its total on the 4% of tokens the teacher assigns less than 10−4, where its label diverges.
- **K1C0451**: Under REINFORCE++, where λ scales only the branch, it lowers macro Avg@8 by 0.38–1.76 points and Pass@8 by 0.46–2.11 points, a loss that grows with the branch weight.
- **K1C0377**: At the fixed weight λ = 10, the recorded mean absolute guidance term falls from about 0.43 to about 0.30 over training (Figure 5a).
- **K1C0382**: On shorter responses, where few tokens set the average, its SD is 0.32, and 8% of all responses carry |λA d| > 0.5, the scale of a verifier advantage.
- **K1C0028**: Under the hypotheses of Proposition 4, centering therefore leaves the expected update almost unchanged, and the response mean it removes, A d, has zero expectation and fluctuation of order M −1/2.
- **K1C0111**: RA improves every matched comparison.
- **K1C0722**: At every weight, each seed of RA with the branch falls below the same seed of RA.
- **K1C0735**: Table 4: The same teacher-peak branch slightly helps sampled OPD but lowers both students trained with the verifier.
- **K1C0441**: Co-RA+GRPO is the most accurate run for both students.
- **K1C0289**: Its expected update at a prefix is the exact logit gradient of that distance, so the student’s own probability of a token scales how strongly the teacher can move it.
- **K1C0578**: The ordering RA, uncentered label, direct loss holds on every seed for the shared-path term, the outcome-compatible mass, the teacher share, and the cosine with the verifier's step.
- **K1C0077**: The residual thus weights the forks of the student’s own reasoning, consistent with the finding that a few high-entropy tokens carry most of the useful RL signal (Wang et al., 2025), whereas the log ratio puts it on tokens that one side considers nearly impossible.
- **K1C0565**: With REINFORCE++, each seed with the branch falls below the same verifier-only seed at the weights 5 and 10, and two of the three seeds do at 20.
- **K1C0190**: Coverage changes are mixed: Pass@8 rises in four benchmark means, is unchanged in two, and falls in six (Table 10).
- **K1C0669**: At a fixed student distribution, replacing a teacher by q + ∆q changes the local advantage by ⟨ea −p, ∆q⟩, as in Equation 26, so teacher adaptation changes the existing guidance without adding another student signal.
- **K1C0542**: On the closed simplex, this strictly concave function has the unique maximizer
p⋆= Π∆(q + Q/λ),
p⋆(v) = [q(v) + Q(v)/λ −τ]+,
where τ makes the entries sum to one.
- **K1C0339**: Restoring response centering at the same weight adds 0.54 Avg@8 and 0.46 Pass@8 points, a smaller gain that holds at all three weights (Table 2).
- **K1C0321**: A single sampled update can point against the expected one (Table 5), and in this setting the variance of the sampled estimate costs 2.65 macro Avg@8 points.
- **K1C0043**: The margin over the untrained student persists up to Pass@512.
- **K1C0294**: And it is bounded by the student–teacher distance times the probability the student leaves to other tokens, so guidance fades on its own as the two converge.
- **K1C0610**: The sampled gradient is noisier; for the uncentered label, most of its extra second moment relative to the direct loss is the estimator's own noise (75–90%), and 15–25% comes from sharing the verifier's sampled path: cos(gT , gV ) is +0.18 for RA on the sampled tokens and +0.02 on resampled ones, whereas the direct loss, which acts on every token, is uncorrelated with the verifier.
- **K1C0240**: The construction requires no schedule, threshold, or learned component.
- **K1C0177**: The guidance is thus student-relative twice over, as an advantage under the student’s own next-token distribution and as a deviation within the student’s own response.
- **K1C0621**: At a single prefix the student value baseline therefore has four times the raw trace variance whenever the latter is nonzero.
- **K1C0219**: The sampled variant reaches 24.80 macro Avg@8 and 38.60 Pass@8, 2.65 and 2.70 points below full-vocabulary OPD and 0.87 and 0.84 points below verifier-only REINFORCE++, and it is lower than full-vocabulary OPD on every benchmark score.
- **K1C0518**: At the same budget, OPD followed by REINFORCE++ reaches 28.39 and REINFORCE++ with an added reverse-KL loss 26.14, both below RA+REINFORCE++ (Appendix D.5), and sampling the log ratio at the generated token, with the same expected update at each prefix, drops OPD to 24.80 at 1.7B, below verifier-only training (Appendix D.6).
- **K1C0012**: Verifier plus teacher improves on teacher-only distillation.
- **K1C0519**: The second bounds the guidance amplitude by the student–teacher distance on the visited prefixes (Appendix A.6), so teacher guidance fades as the two converge, at a fixed weight and without a schedule; Appendix C.1 shows the mean absolute guidance declining over a training run.
- **K1C0425**: What distinguishes RA is its restraint: the teacher acts not as a distillation target, as in these works, but as a critic-like signal within RL.
- **K1C0336**: Both distributions and the visited prefixes move across iterations, and the identities above do not by themselves give monotone distance reduction, policy improvement, or declining guidance during training.
- **K1C0410**: It is chosen for the conditional zero mean that Proposition 4 requires, and that property has this variance cost.
- **K1C0563**: Correct-response mean length rises but stays below about 4,000 tokens.
- **K1C0711**: Teacher guidance adds variation to the actor label while preserving its response mean.
- **K1C0427**: Because RA’s teacher term acts on the tokens the verifier scores, 64% of its gradient mass raises correct or lowers incorrect responses, against 49% for the direct loss, and after clipping and Adam the teacher takes 0.28 of the update against 0.44, keeping RA’s update closer to the verifier’s direction (cosine 0.93 against 0.80).
- **K1C0540**: GRPO keeps the higher completion accuracy after guidance, but REINFORCE++ with RA has the higher macro Pass@8 at both sizes, a trade between accuracy and coverage that a single score would hide.
- **K1C0528**: Teaching the teacher on student rollouts raises accuracy in every tested setting.
- **K1C0150**: Confident tokens, with p(at) ≥0.9, are 61% of all tokens and receive under 1% of either label, as the factor 1−p(a) predicts.
- **K1C0527**: The relative comparison, the confidence scaling, the zero mean, and the bound are all read off one inner product.
- **K1C0497**: Co-RA adds 1.03–1.45 macro Avg@8 points to the four RA runs, and Avg@8 rises in all twelve benchmark means.
- **K1C0688**: The guidance transfers across estimators.
- **K1C0174**: Scaled in this way by the student’s own probability, it also stays small wherever the student is already sure, so the teacher mainly adjusts the choices the student is still weighing instead of imposing its preference on those the student has settled, and it does not inflate small disagreements into large labels.
- **K1C0025**: The sequential run improves on both stages, reaching 28.39 macro Avg@8 and 43.61 Pass@8, and stays 0.86 and 1.59 points below RA+REINFORCE++, which spends the same budget in one stage.
- **K1C0670**: The gains are larger for REINFORCE++, narrowing its macro Avg@8 deficit to GRPO at both sizes.
- **K1C0494**: Co-RA further updates a teacher LoRA with verifier advantages on the same scored student batch and uses the updated teacher in the next iteration’s residual, adapting guidance to the student’s attempts.
- **K1C0004**: A full-vocabulary squared-distance loss, whose gradient at each visited prefix equals the expected update of the uncentered residual label (Appendix A.2), beats verifier-only training but stays below RA and the uncentered control at every weight (Table 2).
- **K1C0424**: It is ahead of RA on AIME25 Avg@8 and behind on the other five benchmark scores, and every RA seed exceeds every sequential seed in macro Avg@8, whereas the Pass@8 seeds overlap.
- **K1C0720**: From K = 8 to K = 512 for the 1.7B REINFORCE++ runs (Appendix D.7), the macro margin of RA over the untrained student grows from 13.4 to 16.9 points, and its margins over REINFORCE++ and OPD from 5.8 to 10.4 and from 3.9 to 6.8, while that of verifier-only training narrows from 7.6 to 6.6, as Yue et al. (2025) report for RLVR.
- **K1C0137**: Under sampled OPD (Table 4) the branch raises macro Avg@8 from 24.80 to 25.10 and the Avg@8 of every seed.
- **K1C0420**: The local advantages average to 3 × 10−4 per token, so the student value baseline holds in practice and the response mean carries no systematic part, and on responses longer than 1,000 tokens λA d has an SD below 0.03, as the hypotheses predict.
- **K1C0611**: It does answer the question it was designed for: stronger and denser teacher supervision does not by itself yield better performance.
- **K1C0595**: The two teachers differ in both the expected logit update and the response-centered guidance term (Table 8).
- **K1C0229**: All tested weights improve both macro scores over verifier-only training (Table 2).
- **K1C0231**: With verifier feedback present in both guided runs, this comparison favors the complete RA construction over the raw log ratio.
- **K1C0246**: Table 1 contains 24 comparisons of RA with its base estimator (two students, two estimators, three benchmarks, two metrics), and RA improves all 24 three-seed means.
- **K1C0210**: Incorrect-response mean length rises more sharply and later fluctuates mostly between 9,000 and 12,000 tokens, close to the cap; the shaped reward penalizes length only for correct responses, so nothing in the reward opposes the growth of incorrect ones.
- **K1C0690**: Across seeds, full RA also varies less than the uncentered control in macro Avg@8 at every weight (Table 23).
- **K1C0657**: Both combinations surpass teacher-only OPD, and Co-RA adds a further 1.0–1.5 Avg@8 points.
- **K1C0731**: The most accurate 4B run, Co-RA+GRPO, ends 5.4 macro Avg@8 points below the teacher, 1.6 on MATH-500 and about 7 on each AIME set, and teacher-only OPD reaches 62% and 79% of the teacher’s macro Avg@8 at the two sizes.
- **K1C0516**: Response centering corrects the uncentered label mainly on responses shorter than 1,000 tokens (79% of the correction), in line with Section 4.1.
- **K1C0044**: The macro gains are 1.74–3.58 Avg@8 and 3.89–6.33 Pass@8 points (Table 10).
- **K1C0679**: It is the rate at which the squared distance 1 2∥p −q∥2 2 falls when the student moves probability toward a.
- **K1C0131**: Averaged over 64 resampled tokens, the sampled teacher gradient matches its analytic expectation (cosine 0.994 for RA, norm ratio 1.001), so the gap does not lie in the expected teacher gradient.
- **K1C0512**: Without it, a nonzero response mean in the teacher label would be indistinguishable from a change of AV , since both multiply the same mean score direction P t ctψt.
- **K1C0277**: The local advantage is a single inner product, Ad(a) = ⟨ea −p, q −p⟩, and three properties follow from it.

## Appendix - arxiv-2610.12114v1 - full candidate pool
- **K1C0220**: UTT consistently outperforms the unprimed Student across all evaluated budgets, with a more pronounced advantage under smaller budgets.
- **K1C0311**: These results show that knowledge distilled through interactions with one Student can transfer to another Student without resynthesizing the Primer.
- **K1C0697**: Across the evaluated settings, UTT also outperforms representative prompt engineering and parameter-updating knowledge distillation methods.
- **K1C0104**: Even when Qwen3.6-27B does not participate in the Primer synthesis, the absolute accuracy gains reach 41.8% and 31.5% (see the rightmost column) on KernelBench and Omni-MATH-2, respectively.
- **K1C0490**: These results indicate that UTT extends to multimodal reasoning tasks requiring joint understanding of images and text, and that its textual knowledge can be reused across models.
- **K1C0571**: UTT pursues knowledge distillation by identifying what to transfer from the paired performance and synthesizing a global Primer from Student attempts, evaluation feedback, and validated Teacher demonstrations.
- **K1C0253**: After replacing the Teacher with Claude Opus 5, Qwen3.6-27B improves from 41.5% to 80.5%, while applying the same Primer to DeepSeek-V4.1-Flash raises its accuracy from 54.0% to 57.5%.
- **K1C0347**: With Student parameters fixed, UTT exceeds the strongest baseline by 7.2, 8.2, and 4 percentage points on Omni-MATH-2 accuracy, KernelBench accuracy, and Fast1, respectively.
- **K1C0016**: Compared with knowledge implicitly encoded in model parameters, the Primer is interpretable and not tied to particular model weights, enabling direct transfer to other models.
- **K1C0532**: On the retention subset, the three KernelBench configurations show no decline in accuracy; instead, they improve from 34.0% to 74.0%, 27.0% to 81.0%, and 37.1% to 78.6%, respectively.
- **K1C0500**: Together, these fine-grained results further support the effectiveness of UTT in four respects: syn- thesis effectiveness, generalization to unseen problems, preservation of existing capabilities, and extension of capability frontiers.
- **K1C0280**: As both curves approach saturation, UTT retains its advantage, suggesting that the Primer is particularly beneficial when the inference budget is con- strained and provides a higher effective performance ceiling within the evaluated range.
- **K1C0489**: These results suggest that selecting synthesis problems according to the Teacher–Student knowledge gap provides more targeted teaching signals and a more consistent overall improvement.
- **K1C0580**: Compared with random selection, knowledge-gap selection improves distillation-training and distillation-test accuracy by 9.7 and 6.0 percentage points, respectively, maintains the same retention accuracy, and yields one additional correct response on the frontier subset.
- **K1C0342**: UTT performs best across all six combinations, with consistent gains across tasks and target models.
- **K1C0615**: Across math and code tasks, UTT demonstrates effectiveness and transferability, with Primers transferable across models without resynthesis.
- **K1C0474**: Keeping Pro as the Teacher, we further synthesize a new Primer for Qwen, which achieves 50.0%, 32%, and 62.4% on the same metrics.
- **K1C0097**: On the distillation test set, Pro→Qwen accuracy on the math task increases from 9.7% to 64.8%.
- **K1C0329**: We formulate LLM distillation as representing the Teacher-Student knowledge gap in natural language rather than encoding it in a specific Student’s parameters, making the distilled knowledge interpretable and reusable across models.
- **K1C0541**: On Omni-MATH-2, Pro→Flash improves accuracy from 58.0% to 69.0%, while Pro→Qwen and Opus→Flash decrease accuracy by 9.2 and 14.2 percentage points, respectively, yet still retain most of their baseline performance.
- **K1C0699**: On the distillation training set, Pro→Flash accuracy on KernelBench increases from 6.7% to 65.2%, indicating that the synthesized Primer effectively improves Student performance on knowledge-gap samples.
- **K1C0061**: The three KernelBench configurations achieve 11.7% to 18.6% accuracy, while Pro→Flash and Pro→Qwen achieve 5.3% and 30.0% on Omni-MATH-2, respectively.
- **K1C0403**: It improves Flash by 38.8, 30, and 19.0 percentage points on the three metrics, demonstrating that UTT remains effective with different Teachers.
- **K1C0009**: The Flash-derived Primer improves Qwen by 32.0, 25, and 25.8 percentage points in KernelBench accuracy, Fast1, and Math accuracy, respectively.
- **K1C0622**: Finally, applying this Primer unchanged to Qwen yields 51.0% KernelBench accuracy, 22% Fast1, and 65.8% Math accuracy.
- **K1C0663**: Relying solely on interactions among LLMs, the process requires no model training or parameter updates and supports both open-source and API-only commercial models.
- **K1C0096**: On the challenging math and code generation tasks (Omni-MATH-2 and KernelBench), UTT substantially improves the Student’s performance across various Teacher-Student settings.
- **K1C0555**: UTT shares with APO the use of natural-language text optimization to enhance models, but differs in its research objective and organization of supervision.
- **K1C0095**: As shown in Table 6, parameter training for the three supervised KD baselines requires 1.2–7.5 hours, while the reinforcement-learning-based LUFFY requires 22.0 hours on eight GPUs.
- **K1C0719**: Although batch size 32 maintains the retention and frontier results, its distillation-training and distillation-test accuracy decreases to 59.2% and 45.2%, respectively.
- **K1C0074**: These results suggest that text can serve as a universal medium for knowledge transfer among different LLMs for complex tasks.
- **K1C0442**: These results suggest that an intermediate batch size provides a better balance between the amount of teaching evidence consolidated in each update and the frequency of Primer refinement.
- **K1C0485**: Teacher summary improves Flash but is inconsistent on Qwen, suggesting that directly summarized Teacher knowledge may not transfer well across Students and Teacher-Student interaction is important for constructing an effective Primer.
- **K1C0488**: The Primer improves both accuracy and Fast1 in all four settings.
- **K1C0390**: Empirically, on the challenging math (Omni-MATH-2) and code generation (KernelBench) tasks, extensive results confirm the effectiveness of the method: UTT remarkably raises the Student’s accuracy from 9.4% to 48.6% and Fast1 accuracy from 9% to 35% on KernelBench, while increasing mathematical reasoning accuracy from 27.6% to 51.7%.
- **K1C0728**: Its distinction lies in using the observed Teacher-Student knowledge gap to guide teaching-content selection and text synthesis, while examining whether the resulting knowledge transfers to other Students without resynthesis.
- **K1C0548**: The full method improves over the Student without a Primer across all four knowledge-gap subsets.
- **K1C0415**: Under Qwen3.8-Max→Qwen3.6-27B, the source Student improves from 41.5% to 76.0%, while transferring the same Primer to DeepSeek-V4.1-Flash improves its accuracy from 54.0% to 59.0%.
- **K1C0562**: The smaller batch size of 8 performs worse across all four subsets.
- **K1C0313**: UTT completes Primer synthesis in 1.6 hours through 281 API model calls, approximately 0.68 million input tokens, and 5.57 million output tokens.
- **K1C0603**: Accuracy increases from 33.7%, 33.3%, 60.0%, and 0.0% to 65.3%, 56.0%, 72.5%, and 5.0% on the distillation-training, distillation-test, retention, and frontier subsets, respectively.
- **K1C0632**: The Primer yields substantial gains of 39.2, 26, and 24.1 percentage points over the Student baseline on KernelBench accuracy, Fast1, and Math accuracy, respectively, improving the corresponding scores from 9.4% to 48.6%, 9% to 35%, and 27.6% to 51.7%.
- **K1C0730**: Although the main experiments focus on LLMs, we also preliminarily confirm transfer to multimodal LLMs in Appendix B.1.
- **K1C0164**: Relative to the unprimed Student baselines, UTT improves KernelBench accuracy from 9.4% to 48.6%, Fast1 from 9% to 35%, and mathematical reasoning accuracy from 27.6% to 51.7%.
- **K1C0241**: Notably, the resulting Primer can improve the performance of the source Student and other Students that are not involved in creating the Primer.
- **K1C0590**: Among the three batch sizes, the default batch size of 16 performs best on the distillation-training and distillation-test subsets and ties batch size 32 on the retention and frontier subsets.
- **K1C0224**: This trade-off suggests that direct Teacher demonstrations fit the synthesis problems more strongly, whereas the Prompter helps transfer the acquired knowledge to problems not used for synthesis.
- **K1C0638**: These results show that knowledge distilled into text can generalize to unseen problems, with benefits extending beyond the samples used for synthesis.
- **K1C0729**: When DeepSeek-V4.1-Flash serves as the source Student, its accuracy increases from 54.0% to 56.0%, whereas transferring the resulting Primer to Qwen3.6-27B substantially improves accuracy from 41.5% to 72.0%.
- **K1C0119**: UTT also performs better than representative prompt engineering and parameter-based KD methods.
- **K1C0019**: Removing the Prompter yields the highest distillation-training accuracy of 72.4%, but reduces distillation-test and retention accuracy from 56.0% and 72.5% to 48.8% and 70.0%, respectively, while frontier accuracy remains at 5.0%.
- **K1C0530**: These results validate the effectiveness of UTT and demonstrate its applicability to Students from different model families.
- **K1C0529**: At the largest tested budget, APO approaches and even slightly underperforms the baseline, whereas UTT, although not reaching Teacher performance, remains between the baseline and the Teacher.
- **K1C0269**: The Qwen-derived Primer improves Flash by 34.4, 21, and 16.1 percentage points on the same metrics.
- **K1C0123**: Without validation gating, distillation-training, distillation-test, and frontier accuracy decrease from 65.3%, 56.0%, and 5.0% to 59.2%, 39.3%, and 3.8%, respectively, while retention accuracy in- creases from 72.5% to 80.0%.
- **K1C0726**: Although the gain mag- nitude varies across configurations, the same Primer remains effective without resynthesis under the evaluated changes to quantization and thinking mode.
- **K1C0631**: The different gain magnitudes on Qwen3.6-27B and DeepSeek-V4.1-Flash indicate that transfer effectiveness varies with the target Student.
- **K1C0721**: This shows that the Primer can help the Student solve some problems that neither the Teacher nor the Student solved during baseline evaluation, extending the observed capability frontier.
- **K1C0090**: As shown in Figure 4, errors caused by truncation gradually decrease as the output-token budget increases.
- **K1C0432**: For the target Student Qwen3.6-27B, Primers synthesized from the Teacher-Student pairs (shown at the bottom of the figure) consistently improve accuracy.
- **K1C0558**: On the frontier subset, the primed Student achieves nonzero accuracy in five of the six configura- tions.
- **K1C0602**: Empirically, across various Teacher-Student configurations in mathematical reasoning and code generation, the synthesized Primers consistently improve their source Students and remain effective when transferred to other Students without resynthesis, demonstrating both effectiveness and cross-model reusability.
- **K1C0653**: We introduce Universal Textual Teaching (UTT), a parameter-update-free framework that distills observed Teacher-Student knowledge gaps into a textual, interpretable, and reusable natural-language artifact called Primer.
- **K1C0453**: Of note, UTT is shown to be generalizable across different Teachers and Students: a Primer synthesized for one Teacher-Student pair can generalize to other Students that do not participate in the synthesis.
- **K1C0437**: This indicates that the Primer largely preserves the Student’s existing capabilities while improving performance on knowledge-gap samples.
- **K1C0498**: Figure 1: Left: We introduce Universal Textual Teaching (UTT), a parameter-update-free frame- work that distills an LLM’s knowledge into a textual Primer through multi-role LLM interaction.
- **K1C0648**: UTT identifies knowledge gaps through paired evaluation and iteratively synthesizes a deployable global Primer from Student attempts, Prompter feedback, and Teacher demonstrations, without updating any model parameters.
- **K1C0062**: Notably, although the Primer is synthesized with a 32k maximum output-token budget, it continues to improve the Student at larger budgets, indicating that its knowledge and solution strategies are not tied to the specific output-token budget used during synthesis.

## Appendix - arxiv-2610.12124v1 - full candidate pool
- **K1C0557**: On ToolBench, Hippocam makes modest further gains amid fluctuations and moves ahead of Letta, whereas A-Mem shows little sustained improvement in the extended evaluation.
- **K1C0293**: To address this, we propose Hippocam, a hierarchical memory and continual learning architecture.
- **K1C0478**: Excluding the Jokes category, whose grader can credit a list containing the requested joke, preserves the interleaved advantage (91.1% versus 72.8%).
- **K1C0598**: Disabling recall on the same post-ingestion MemoryAgentBench 64k snapshot reduces accuracy from 41.0% to 27.0%.
- **K1C0340**: Across methods, Fig. 9 shows a trade-off: several lower-scoring methods are cheaper, while Hippocam combines higher accuracy with lower cost than A-Mem and mem0 on ToolBench.
- **K1C0129**: Memory, knowledge development, and learning arise from the same use-and-disuse cycle over its interaction history, demonstrating the broad applicability of a unified mechanism rather than separate capability-specific mechanisms.
- **K1C0345**: Hippocam combines stronger conversational reasoning with 87.2% accuracy on unanswerable questions.
- **K1C0450**: Whereas competing methods show more uneven performance across these demands, Hippocam leads or matches the best compared method on seven of the eight measures in Fig. 1.
- **K1C0683**: In contrast, Hippocam maintains high performance in both conditions without degradation under interleaving, scoring 85.1% in isolation and 88.7% under interleaving (Fig. 5, left).
- **K1C0206**: ToolBench accuracy falls from 78.7% to 65.7% (Table 4).
- **K1C0649**: Across both intervals, its own calls account for 34.0% of Hippocam’s ToolBench cost, and the first subsequent main-agent and Janus calls account for another 10.8%.
- **K1C0157**: These comparisons highlight Hippocam’s stronger ability to use prior knowledge to support continued learning in a new domain.
- **K1C0161**: This nested chain organizes the multiple purposes jointly served by ongoing work in a form aligned with the linear context of LLM agents.
- **K1C0543**: These observations support intent-aware selection of both relevant content and the detail needed for ongoing work.
- **K1C0144**: Within this run, reusable knowledge persists as the details of individual episodes recede.
- **K1C0449**: When later asked to order, the former selected a listed dish and the latter named a dish absent from the menu.
- **K1C0057**: Experience that remains unused continues to recede in detail through recursive consolidation, without separately assigned importance scores or time-based forgetting rules.
- **K1C0256**: On FEVER, Frozen scores cluster around Plain’s 59.3%, with Hippocam and HiAgent reaching 61.8%.
- **K1C0397**: Only Hippocam and ACE achieve positive gains on both domain transitions, while the remaining methods show mixed, unchanged, or reduced performance.
- **K1C0067**: The interleaved score decreases from 88.7% to 65.6%, compared with 85.1% to 77.8% in isolation.
- **K1C0158**: Both forms of consolidation keep the agent’s recent context focused and high-signal, enabling accurate and coherent reasoning over long horizons.
- **K1C0163**: Hippocam achieves larger gains of 19.2 and 6.0 pp, respectively, with a narrower FEVER gap under the scoring sensitivity analysis (§ A.2).
- **K1C0447**: Experiments and analyses demonstrate its broad applicability and illuminate how retained knowledge evolves through use and disuse.
- **K1C0195**: Hippocam improves across all three benchmarks, achieving 97.8% ALFWorld success and tying ACE for the best result.
- **K1C0192**: Across the three input lengths, Hippocam achieves 71.7% mean accuracy, compared with 44.3% for Letta (Fig. 5, right).
- **K1C0396**: On LoCoMo, Hippocam achieves 77.6% overall accuracy, exceeding the strongest baseline, A-Mem, by 10.1 pp (Table 3).
- **K1C0185**: Unlike MemTree, our tree emerges from the organization and consolidation of ongoing work.
- **K1C0198**: In contrast, Hippocam not only uses explicit intent requirements rather than inferred future needs to guide suffix consolidation and retention granularity, but goes further by bringing earlier prefixes into context management.
- **K1C0560**: In SallyAnne cases, the variant incorporates the beginning of a story into a memory associated with another task, while later events remain in the active conversation.
- **K1C0624**: Hippocam combines this breadth with stronger overall performance, leading or tying on seven of the eight measures.
- **K1C0483**: Access to underlying evidence therefore improves reasoning beyond what the consolidated context alone supports.
- **K1C0681**: Hippocam achieves 78.9% mean progress, improving over Plain by 30.1 pp and exceeding the strongest baseline, ACE, by 16.2 pp.
- **K1C0216**: Evaluations show that Hippocam achieves strong performance across memory, knowledge use, and learning.
- **K1C0094**: This contrast highlights Hippocam’s stronger resilience to interference from interleaved tasks.
- **K1C0171**: Across both streams, Hippocam’s later interval has higher accuracy and about 10% lower mean cost per task (Table 12).
- **K1C0106**: Inducing a playbook therefore offers no clear advantage here over directly using retained facts and grounded lessons (Table 9).
- **K1C0316**: Prefix consolidation thus supports more effective subsequent work with a smaller active context.
- **K1C0099**: The corresponding shares on DDXPlus are 26.8% and 4.2%.
- **K1C0167**: Supplementation occurs in 28.4% of matched-call transitions and 11.7% of differing-call transitions, compared with 0.9% of transitions without detected use.
- **K1C0204**: Concrete-value updates are more frequent when the reference specifies a different call (3.4%) than when the call matches (0.3%) or no use is detected (0.1%).
- **K1C0724**: These results demonstrate how our use-and-disuse cycle supports memory and learning through interaction history.
- **K1C0546**: Hippocam does not build a memory bank separate from its interaction history, but remembers and learns by deliberately maintaining its context.
- **K1C0387**: The association is therefore clearer in ALFWorld than in ScienceWorld under this textual proxy.
- **K1C0439**: On ToolBench’s first 150 tasks, Hippocam reads 232.5k input tokens per task, compared with A-Mem’s 65.0k, but only 30.4k versus 52.7k are uncached.
- **K1C0727**: Through this memory dynamic of use and disuse, Hippocam connects working context, long-term memory, knowledge accumulation, and skill learning within a single continuously evolving experiential process.
- **K1C0010**: ALFWorld success remains near perfect, but mean actions increase from 9.62 to 11.74, and episode-start context grows from 19.7k to 50.7k tokens in the inspected stream.
- **K1C0718**: Its 81.9% mean ScienceWorld progress exceeds four of the six compared methods.
- **K1C0250**: Ablations and case analyses further show how consolidation and progressive recall support ongoing work and how knowledge develops through use and disuse.
- **K1C0147**: ACE improves ScienceWorld progress by 14.0 pp and FEVER accuracy by 2.0 pp.
- **K1C0398**: Holding recorded token usage fixed and varying only the cached-input price, Hippocam’s lower ToolBench cost per correct answer than A-Mem holds while a cache hit costs less than approximately 15% of a miss; the reporting schedule uses 2%.
- **K1C0251**: We inspect whether filler question–answer pairs remain in the memories that consolidate them; retention increases from 14% to 63% without intent conditioning.
- **K1C0160**: Under an alternative answer extraction, Hippocam’s sequential improvement decreases from six to two percentage points.
- **K1C0710**: On DDXPlus, Hippocam continues to improve after early fluctuations and maintains its lead, while Letta and A-Mem also improve.
- **K1C0480**: This natural dynamic of use and disuse unifies the recovery of past experience with learning that deepens what the agent knows, refines how it acts, and expands what it can accomplish.
- **K1C0276**: It matches HiAgent at 97.0% on 6k inputs and retains 77.0% and 41.0% accuracy at 32k and 64k, where no baseline exceeds 37.0% and 19.0%, respectively.
- **K1C0373**: These cases show that Hippocam adapts retrieval depth to the task, recovering sufficient evidence without expanding the entire history.
- **K1C0122**: The corresponding ScienceWorld difference is small (57.7% versus 59.1%).
- **K1C0634**: In ALFWorld, referenced items remain unchanged less often than items without detected textual reuse (41.6% versus 63.2%).
- **K1C0239**: Intent- consolidation calls themselves account for only 0.8% and 1.3%, respectively.
- **K1C0326**: Its cost per correct answer is consequently lower under the stated prices (0.0173 versus 0.0271 USD).
- **K1C0026**: In both streams, Hippocam also achieves higher accuracy with about 10% lower average cost per task in the later 150-task interval (§ A.9).
- **K1C0617**: Thus cache reuse between updates coexists with a substantial cost of periodically reorganizing experience.
- **K1C0112**: Thus the procedure unfolds detail until the current question is supported, while leaving unrelated children unopened.
- **K1C0035**: Intent-guided consolidation retained the individual dishes, while the variant without intent guidance retained one menu memory chiefly as category names and number ranges.
- **K1C0426**: These gains demonstrate more effective learning from accumulated experience than the compared methods.
- **K1C0125**: It leads or ties across all four answerable question categories, with temporal accuracy reaching 86.6% compared with A-Mem’s 67.6%.
- **K1C0071**: On GoodAI, filler retention rises from 14% to 63%, while scores fall by 23.1 pp under interleaving versus 7.3 pp in isolation (Table 4).
- **K1C0607**: Across the three benchmarks, most methods outperform Plain, although some match or fall below it.
- **K1C0011**: On StreamBench, it achieves the highest mean accuracy of 81.7%, narrowly ahead of Letta’s 81.3%.
- **K1C0120**: This selective consolidation reduces distraction, supports coherent reasoning, and keeps the context focused and efficient, while preserving the information needed to build on established results without repeating prior work.
- **K1C0597**: This enables agents to learn and evolve capabilities through their own experiences without parameter updates.
- **K1C0013**: Although longer histories remain challenging, Hippocam more effectively preserves and applies updated information.

## Appendix - arxiv-2610.12168v1 - full candidate pool
- **K1C0406**: We give a formal specification of our method and a concrete instantiation for interactive theorem proving in the Lean theorem prover; empirical evaluation remains future work.
- **K1C0433**: We express solution ideas at several levels of detail, forming a hierarchy from overarching strategies to detailed plans.
- **K1C0214**: We provide a formal specification of our method for a general problem setting, together with the optional refinement for verifiable problem domains.
- **K1C0675**: The loop alternates between reverse engineering such ideas from problems with supplied solutions and using these ideas as additional supervision for joint training of all three capabilities.
- **K1C0115**: We operationalize this by jointly training the same model to exhibit the following three capabilities: predicting solution ideas from problems alone, reverse-engineering ideas from problems and known solutions, and solving problems using provided ideas.
- **K1C0471**: Our Lean instantiation builds on language-model-guided proof search, conditioning tactic generation on learned hierarchies of proof ideas.
- **K1C0218**: All three components share a backbone network; for example, when their inputs and outputs can be represented as text, we may use a shared language model with role-specific prompt templates.
- **K1C0328**: We also give a concrete instantiation for interactive theorem proving in the Lean theorem prover [2], where natural language proof ideas guide tactic generation during proof search.
- **K1C0586**: We introduce a self-improvement loop for reasoning models based on the following observation: Even when the difficulty of a problem exceeds the model’s current solving abilities, an additionally supplied solution might enable the model to extract useful solution ideas in hindsight.
- **K1C0236**: Finally, in verifiable problem domains, we additionally assess the reverse-engineered hierarchies through separate solving attempts, in which the model receives the problem and hierarchy while the reference solution is withheld.
- **K1C0411**: The ideas reverse-engineered by the hindsight component are intended to provide guidance that could plausibly be followed from the problem alone, rather than merely describe the supplied solution or reflect hindsight bias.
- **K1C0203**: We operationalize this observation by jointly training a model on three tasks.
- **K1C0394**: We provide an optional refinement of our method which accomplishes this in the case of verifiable problem domains, i.e., when proposed solution candidates can be procedurally verified: For each problem and reference solution, we generate several candidate hierarchies in hindsight.
- **K1C0487**: This differs from the forward generation of thoughts and tactics in Lean-STaR’s expert iterations, and from DeepInsight’s retrospective rationale generation using a teacher model: our loop repeatedly performs retrospective hierarchy generation with the same backbone that learns to predict and use the resulting hierarchies.
- **K1C0193**: Our method makes retrospective generation of hierarchies (i.e., rationales at several levels of detail) an explicitly trained task.
- **K1C0456**: Consequently, every triple returned by Algorithm 2 contains a valid solution discovered by the solver under the triple’s hierarchy.
- **K1C0148**: This signal enters entirely through data selection; the training objective remains unchanged.
- **K1C0049**: As the three components share a backbone network, each of the individual training signals affects all three components.

## Appendix - arxiv-2610.12375v1 - full candidate pool
- **K1C0211**: Empirically this is a nega- tive result: at γeff = 0.3 the coupling quality degrades across ablations (on a held-out tool-calling corpus, mean ablation AUROC drops from 0.825 to 0.715), because observations are high-variance — correct and incorrect executions of the same step both produce textually dif- ferent outputs every time, so the effect term dilutes the action/tool signal that correctly drives the alignment.
- **K1C0704**: The dependence on the embedding model confirms that λ must be recalibrated whenever the encoder (and hence the cost scale) changes.
- **K1C0535**: Third, LinUOT tracks OnTrack within 0.003–0.010 AUROC everywhere: the quadratic term contributes essentially nothing to ranking on this corpus, consistent with its role as a false-alarm suppressor rather than a ranker (Table 4); the mask-free variant is AUROC-identical to the full sys- tem, confirming the mask’s null ranking effect here as well.
- **K1C0630**: The component study clarifies what the transport machinery changes on real traces: not recall — L1 heuristics and even a prerequisite-rule baseline match or exceed it there — but the operating point: at shipped thresholds the quadratic structure term selects a point with less than half the benign false-alarm rate of every reference-free variant (13/40 vs. 29–32/40 benign traces flagged; removing the frontier mask instead shifts the count by one trace); establishing curve-level dominance remains open, and we do not claim generally superior detection precision.
- **K1C0281**: For S4, decisions come from per-step signals with a short grace window for new steps, never from the aggregate score (Sec. 4.5).
- **K1C0352**: OnTrack instead assigns constant per-node agent mass µi = 1/ ¯m, ¯m = 1 K P k mk, (3) so one agent step carries the same nominal mass as an average reference step (exact for references of size ¯m), the agent total grows as t/ ¯m, and the per-node normalized leakage ℓi = h 1 −1 µi X j Tij i [0,1] (4) is a scale-free, calibrated trigger at every t; the clip to [0, 1] is part of the definition, since in unbalanced OT a row mass can exceed µi (over-transported rows are treated as fully matched).
- **K1C0445**: On a balanced sample (50 resolved, 50 unresolved), no method reliably separates outcomes (Table 8): OnTrack reaches 0.581, cosine 0.643, with widely overlapping bootstrap CIs.
- **K1C0484**: First, threshold stability: cosine-cutoff’s frontier is pathologically sensitive — moving its threshold from 0.40 to 0.55 swings the false-stop rate from 3.3% to 28% to 73% to 95%, so a miscalibration of 0.05 turns it from inert into a kill-everything switch — whereas flag density degrades gracefully across its entire range (29% to 19% false stops over thresholds 0.2–0.7).
- **K1C0162**: On SWE- agent traces, which follow a narrow search–read–edit–test template, a checkpoint-level ablation at k=5 and k=10 (5 seeds) shows Full OnTrack exceeds the No-GW (θ=0) variant by only +0.009 and +0.001 respectively — within sampling noise.
- **K1C0270**: Our contribution is making this alignment work on a live stream, which cannot be done by just re-running the batch method after each step due to the following structural challenges:
- **K1C0561**: Additionally, by deploying an abort policy on top of it, we save ∼18% of the compute that would have been burned on agents heading to failure, and 83% of runs that were interrupted were actually heading to failure (5 out of every 6 aborts were correct).
- **K1C0006**: For S2, a new step’s structural influence starts at zero and phases in as later steps use its output; edges discovered late are inserted into the graph in place (Sec. 4.4).
- **K1C0149**: Evaluating based on the first 8 steps, the proposed method ranked the failing trajectories below succeeding ones better than content similarity-based approaches (+0.057 AUROC).
- **K1C0372**: The end-of-stream discrepancy — the running fast-path diagnostic against the eventual finalization output, as defined in the remark after Prop. 1 — never exceeds 0.013 across the campaign (and is 0 after finalization); per-event runtime spans 0.2–1.6 ms.
- **K1C0032**: No intervention is ever taken on a stale linearization, and the converged-solve cost is paid exactly when it is cheapest relative to the tool call about to be prevented.
- **K1C0507**: To overcome this issue, we propose OnTrack, a streaming monitoring mechanism that, as the agent progresses in its task, compares its steps and the dependencies between them against recorded successful runs and alerts the user of potential issues or blocks the agent, taking about a millisecond per step.
- **K1C0038**: Scenario B finalizes to the in-order score exactly (0.913 = 0.913), the empirical face of Prop. 2.
- **K1C0381**: At a matched ≈20% false-stop rate, flag- density (17.9%) and an interpolated step-cutoff (≈16.5%) save comparable cost; at ≈29% false stops, blunt early policies save more (cosine-cutoff 37.9%, budget-cutoff 31.9%, vs. flag-density 28.0%), because savings track how early a policy fires and nothing fires earlier than a cutoff that barely looks at the trace (cosine-cutoff’s median abort is step 6, vs. 33–44 for flag density).
- **K1C0292**: With no reference at all, L2 is off and OnTrack degrades, explicitly, to L1 + L3.
- **K1C0103**: As the run unfolds, the monitor compares this growing graph against reference solutions using optimal transport and flags potential issues in about a millisecond per step.
- **K1C0438**: The references are optional, however—the monitor runs with whatever is available.
- **K1C0440**: The fix recomputes the frontier from the current coupling inside the gate; after it, G-a allows, G-b/H still block, the false-block rate is 0/50, and all prior results are unaffected (the SWE-bench corpus contains no irreversible-annotated tools, so the gate never fires there).
- **K1C0291**: First, the ∆CI excludes zero at k ≤10, and the advantage is gone by k=15, where cosine catches up (.633 vs. .635): the claim is an early-trajectory advantage, precisely the regime an in-flight monitor operates in.
- **K1C0065**: At the end of the run, one final solve makes the monitor’s output identical to the batch evaluator’s — provided the dependencies discovered online match what batch extraction would find (Prop. 1).
- **K1C0242**: The honest finding is that the savings-vs-false-stop frontier alone does not select a winner.
- **K1C0209**: For S1, the monitor only expects the parts of the reference the agent could have reached so far, so an agent is never punished for being early (Sec. 4.2).
- **K1C0036**: Second, actionability: a cutoff emits a bare kill signal, while a severe-flag trigger fires with a verdict (LOOP at step t, STALLED since step t−w) that supports graduated responses — replan, inject guidance, escalate to a human — of which aborting is only the bluntest.
- **K1C0412**: Injecting the controlled fault types into real resolved traces, flag-based AUROC is strongest on loops (0.699) and stalls (0.646), where structural repetition is pronounced; in-distribution hallucinations (0.572) and inversions (0.496) are near the floor for the same reason as the splice experiment — on homogeneous 30-step debugging traces, a locally plausible wrong step is indistinguishable from exploration without task-level semantics.
- **K1C0344**: At k=8, OnTrack achieves TPR 6.6% / 23.2% / 33.3% at FPR 1% / 5% / 10%, compared to cosine 1.5% / 9.6% / 20.7% and n steps 1.0% / 5.6% / 13.6%.
- **K1C0388**: On an earlier, independent draw of the profile sample the same threshold gave 25.3% true stops at 12.7% false stops and 17.0% savings: the savings figure is stable across trace mixes (≈17–18%), while the false-stop rate varies (13–21%) and should be validated on deployment traffic.
- **K1C0083**: Loops and stalls are also precisely the fault modes that dominate real cost-limit failures (Table 7), which is why the abort policy of Table 6 works despite the per-fault AUROC floor on the harder categories.
- **K1C0539**: Table 7 shows that OnTrack score (0.979) and flags (0.977) dominate cosine (0.557) and statistically match n steps (0.978).
- **K1C0501**: Independent coupling states are maintained per reference and aggregated by temperature-controlled soft-min [4]; K is small (3–10) and cost is linear in K.
- **K1C0109**: What we claim is a candidate policy: ≈18% savings at ≈20% balanced false stops at the illustrated point, not produc- tion readiness.
- **K1C0641**: We therefore claim the FPR contrast at deployed thresholds, not curve-level dominance.
- **K1C0376**: Beyond the eight unit scenarios, a randomized campaign (40 random-DAG tasks × 7 conditions, seeded) yields: loop recall 100% at detection latency 0; hallucination recall 100% at latency 2 (the grace window); causal-inversion recall 94.1% at latency 0 via the premature-step check; and 0 false interventions over 200 benign runs that include valid reorderings, retries, and parallel exploration (a one-sided 95% upper bound of 1.5% on the false-intervention rate).
- **K1C0662**: With tool schemas alone, it still catches loops and stalls and blocks an irreversible action whose declared prerequisites are missing; with nothing but the event stream, loop and stall detection remain.
- **K1C0589**: On 2,294 SWE-agent trajectories, OnTrack provides early-trajectory discrimination that outperforms cosine similarity where it matters most — the first ten steps (+0.057 AUROC at k=8 under the primary held-out pro- tocol, instance-level bootstrap 95% CI [+0.033, +0.080], excluding zero through k=10) — and a candidate flag- density abort policy stops roughly one in four failing runs, saving 17–18% of compute on the failed population at ≈83% deployment-adjusted precision.
- **K1C0124**: OnTrack keeps the true objective by observing that the standard batch UFGW solver — conditional gradient (CG) — is already an iterative linearization scheme, and amortizing it: one warm-started CG iteration per event; the coupling tracks the moving optimum the way stochastic gradient descent tracks a drifting loss.
- **K1C0060**: Second, at the earliest checkpoint trace length alone is the single best signal (n steps .622 at k=5); OnTrack leads every content- and structure-aware method there but not the length prior — its clearest regime is k=8–10, after the length prior fades and before content accumulates.
- **K1C0201**: Fourth, the balanced multi-seed protocol (Appendix A) agrees in direction with somewhat larger deltas; we cite the primary protocol’s numbers everywhere.
- **K1C0574**: Point estimates are unstable at this sample size — an independent draw of the evaluation sample yields OnTrack 0.666 vs. cosine 0.657, reversing the ordering — so the only conclusion the data support is that neither process alignment nor content similarity predicts patch correctness from the trajectory alone.
- **K1C0165**: The ∆CI excludes zero for k ≤10.
- **K1C0142**: The calibrated value falls below the batch default by roughly 3–10× across our two settings — λ = 0.1 on the controlled tasks with synthetic embeddings, λ = 0.3 on SWE-bench with all-MiniLM-L6-v2 (Sec. 6.2) — and with it, clean separation emerges.
- **K1C0254**: When resolved/unresolved pairs are matched within ±3 steps (50 pairs, mean 30.6 steps in both classes), all trajectory-level signals collapse toward chance: OnTrack score 0.526, cosine 0.540, n steps 0.500 by construction.
- **K1C0639**: We do not claim an edge over trace length here — at full-trace granularity, cost-limit detection is essentially length, and a step counter is equally available online.
- **K1C0559**: OnTrack shows that structure-aware optimal transport — until now a post-hoc instrument — can run inside the agent loop and act in real time, without surrendering the properties that made it worth having.
- **K1C0661**: OnTrack separates signals by their prerequisites into three decoupled layers: L1 vital signs (reference-free intrinsic diagnostics: loop detection, information gain, stall) run always; L2 transport alignment (the streaming UFGW machinery, Secs. 4.1–4.5) requires references; L3 pre-execution policy gate (tool-contract prerequisite checks plus a one-row proposal alignment, Sec. 4.5) requires schemas and is the only synchronous component — it evaluates the proposed action before the tool executes, exclusively for irreversible calls, so worst-case added latency is confined to the rare actions that warrant it.
- **K1C0643**: We therefore present the abort experiment as evidence that the verdict stream supports a candidate operating policy that is reasonably stable on this corpus, not that it dominates the savings frontier.
- **K1C0136**: Because the corpus base rate is heavily skewed toward failure (81% unresolved), the balanced-sample false-stop rates translate to ≈83% precision in deployment: five of six aborted runs would indeed have failed.
- **K1C0581**: The running arg min doubles as a live “which strategy is the agent following” diagnostic.
- **K1C0286**: Online, where the marginals are the signal, 2λ + ε acts as a soft cost threshold below which mass is destroyed rather than moved.
- **K1C0134**: All members of the currently executable antichain of R are active simultaneously, so an agent that executes independent reference steps in any topological order is never penalized for order (Prop. 2).
- **K1C0499**: The precise summary of the real-trace evidence is this: on homogeneous SWE-agent traces, OnTrack provides a modest early advantage over content similarity, and its main structural contribution is selecting a lower-false-alarm operating point rather than improving ranking.
- **K1C0296**: The honest result is that such splices sit near the detection floor on this corpus: AUC(score) = 0.546, AUC(flags) = 0.540, cosine 0.516, and the per-trace leakage delta between spliced and clean versions is not significant (p = 0.93).
- **K1C0368**: Table 2: all eight scenarios behave as designed.
- **K1C0526**: No transport mass is required — the gate is a schema-plus-proposal check, which is what makes synchronous operation possible.
- **K1C0656**: Every spliced trace raises at least one flag, but unspliced host traces of comparable length flag at nearly the same rate, so trace-level “detection rate” is not a meaningful metric here and we do not report it as one.
- **K1C0547**: All verdict thresholds are calibrated directly on the implemented quantities, so the deviations affect interpretation of the loss scale, not the calibrated behavior.
- **K1C0545**: At threshold 0.60 (Table 6), 23.3% of unresolved traces are stopped early at a 20.7% false-stop rate, yielding 17.9% cost savings on the unresolved population.
- **K1C0145**: Nothing is reconfigured across these regimes; parts of the monitor simply switch off as their inputs disappear.
- **K1C0564**: The same information is useful downstream of the cou- pling: a mass-weighted content-divergence signal (does the observation match what the reference saw at the coupled node?) contributes to struggling-agent detection without touching the transport.
- **K1C0458**: Agent-side leakage (Eq. 4) is the real-time signal — it means hallucination, digression, or prematurity now.
- **K1C0495**: At K=3 references, m=40, t ≤40, the fast path measures p50 0.85 ms / p95 1.6 ms per event (Apple M5 Max core).
- **K1C0091**: At low FPR operating points (balanced 100+100 sample), OnTrack achieves TPR 37% / 81% / 92% at FPR 1% / 5% / 10%, matching n steps (33% / 82% / 92%) and far exceeding cosine (0% / 3% / 9%).
- **K1C0436**: For S3, instead of re-solving the alignment at every step, we take one warm-started iteration of the batch solver per event — about a millisecond per step — and run the solver to convergence only before acting on an intervention (Sec. 4.3).
- **K1C0552**: The relevant distinction is when and how the signal is usable: a raw step count offers no principled stopping rule mid-trace (any length cutoff is a per-task guess), whereas the severe-flag density that drives Table 6 is a calibrated, task-agnostic trigger that identifies the loop/flounder behavior producing the cost overrun while budget remains to save.
- **K1C0492**: This confirms that the modest full-trajectory outcome correlation is largely mediated by trace length — unresolved traces are longer on average — and that OnTrack score is length-sensitive by construction (more steps →more accumulated transport cost).
- **K1C0585**: This extraction is deterministic string matching, not an LLM call — cheap and auditable — but it fails when a dependency leaves no matchable identifier.
- **K1C0238**: That combination, as far as we know, is new.
- **K1C0180**: Cost-limit failures are detected at 0.979 AUROC, on par with trace length post hoc but available as a calibrated trigger mid-trace.
- **K1C0733**: The severe-flag density trigger (th=0.60) fires on 90% of cost-limit traces, at a median of 58.6% of the trace elapsed — i.e., with ≈41% of the eventual trajectory steps still ahead at detection.
- **K1C0614**: OnTrack addresses all four challenges.
- **K1C0087**: Scenario B of Table 2, where a reordered run tracks and finalizes to the identical score, is its validation.
- **K1C0361**: Measured on an Apple M5 Max core, the fast path runs at p50 0.85 ms / p95 1.6 ms per event at t=m=40, K=3 (p50 0.5 / p95 0.7 ms at t=m=20; p50 1.6 / p95 3.9 ms at t=80); the escalated solve matches the batch-solve runtime (≈30 ms) and is invoked only ahead of interventions.
- **K1C0351**: The quadratic structure term survives through amortized conditional gradient; the prefix problem is solved by frontier-masked marginals that keep order-freedom where the DAG per- mits it and convert agent-side mass leakage into a real- time signal; and every intervention rests on per-node transport marginals, escalated to a converged solve be- fore action.
- **K1C0272**: Per-node leakage separates cleanly — injected hallucinated steps reach ℓ≥0.66 while valid steps stay ≤0.24, comfortably bracketing θleak = 0.6.
- **K1C0290**: Reversible actions are never blocked, preserving cheap exploration.
- **K1C0465**: The advantage is consis- tent across all three operating points.
- **K1C0706**: The hybrid tracks the step-cutoff frontier and adds nothing.
