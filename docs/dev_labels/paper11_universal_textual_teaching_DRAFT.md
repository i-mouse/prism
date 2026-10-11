# Paper 11 - Universal Textual Teaching (UTT) (arXiv 2610.12114v1) - DRAFT dev labels
Status: DRAFT. Labelled under docs/LABEL_RUBRIC.md before any Prism output. Verified against the PDF.
Row format: id | claim | section/page | deciding evidence | label | rule | confidence

## Refusal-family rows (3: 2 partial, 1 not_supported)

P11-R1 | Sec 3.2.1: "Only the training set is used for Primer synthesis, while all other subsets are reserved for final evaluation; namely, the training and testing sets do not overlap, following the standard machine learning setting." | Sec 3.2.1 p5; Table 1 caption p7; Abstract p1 | Table 1 caption: "All scores are computed over the full task pool D." Eq. (4): D = D_dist + D_ret + D_frt, and D_dist is split into a training set (used for Primer synthesis) and a test set. The headline numbers (abstract: KernelBench 9.4% -> 48.6%, Omni-MATH-2 27.6% -> 51.7%) therefore include the synthesis training samples. Non-overlapping evaluation is reported only in the split-wise breakdown (Fig. 3: e.g. Pro->Qwen math, distillation test set 9.7% -> 64.8%). | partially_supported | R3 | 0.75

P11-R2 | Sec 1: "Across the evaluated settings, UTT also outperforms representative prompt engineering and parameter-updating knowledge distillation methods." (also Abstract and Conclusion without the scope phrase) | Sec 1 p2; Table 2 p9; Table 3 p9; App A.4 | Table 2 (prompt methods) covers Flash and Qwen targets and UTT is best in all six columns. Table 3 (KD methods: SeqKD, Fine-tune-CoT, RSR, LUFFY) is titled "under the Pro->Qwen setting": KD baselines were never run for a Flash target or with Opus as teacher. UTT beats the strongest KD baseline there by 7.2, 8.2 and 4 pp. | partially_supported | R3 | 0.70

P11-R3 | App A.4: "We observed that the training losses of the KD baselines had largely stabilized by the end of their respective update budgets." | App A.4 p15 | No training-loss curve, final loss value or convergence metric for SeqKD, Fine-tune-CoT, RSR or LUFFY appears anywhere in the paper or appendices. The statement is the only support offered for the adequacy of the 100/200-update KD budgets. | not_supported | R5 | 0.60 (judgment call: Reading 2 = author testimony in an implementation note, not a result claim)

## Supported rows (8)

P11-S1 | UTT raises Flash KernelBench accuracy 9.4% -> 48.6%, Fast1 9% -> 35%, Omni-MATH-2 accuracy 27.6% -> 51.7% | Abstract p1; Table 1 group 1 | As stated (computed over full pool D; see P11-R1). | supported | plain read | 0.95
P11-S2 | The Flash-derived Primer improves Qwen by 32.0, 25 and 25.8 pp (KernelBench accuracy, Fast1, math accuracy) | Sec 4.2 p7; Table 1 group 3 | 9.2 -> 41.2; 12 -> 37; 34.3 -> 60.1. | supported | plain read | 1.0
P11-S3 | The Qwen-derived Primer improves Flash by 34.4, 21 and 16.1 pp | Sec 4.2 p7; Table 1 group 4 | 9.4 -> 43.8; 9 -> 30; 27.6 -> 43.7. | supported | plain read | 1.0
P11-S4 | Opus-derived Primer improves Flash by 38.8, 30 and 19.0 pp; applied unchanged to Qwen it yields 51.0% KernelBench accuracy, 22% Fast1 and 65.8% math accuracy | Sec 4.2 p7; Table 1 groups 5 and 6 | 9.4 -> 48.2; 9 -> 39; 27.6 -> 46.6; Qwen 51.0 / 22 / 65.8. | supported | plain read | 1.0
P11-S5 | "UTT performs best across all six combinations" of prompt engineering comparisons | Sec 4.4 p8; Table 2 | Checked all six columns: Omni-MATH-2 Flash 51.7 vs best baseline GEPA 41.1; Qwen 62.4 vs GEPA 61.9; KernelBench Flash accuracy 48.6 vs MIPROv2 45.0, Fast1 35 vs 30; Qwen accuracy 50.0 vs few-shot 46.6, Fast1 32 vs one-shot 31. | supported | R3 | 0.95
P11-S6 | Teacher summary improves Flash but is inconsistent on Qwen | Sec 4.4 p9; Table 2 | Flash: math 27.6 -> 36.7, KernelBench 9.4 -> 40.0, Fast1 9 -> 30. Qwen: math 34.3 -> 32.8, Fast1 12 -> 11, KernelBench 9.2 -> 10.2. | supported | plain read | 1.0
P11-S7 | Under Pro->Qwen UTT exceeds the strongest KD baseline by 7.2, 8.2 and 4 pp | Sec 4.4 p9; Table 3 | 62.4 - 55.2 (LUFFY); 50.0 - 41.8 (Fine-tune-CoT); 32 - 28 (Fine-tune-CoT). | supported | plain read | 1.0
P11-S8 | "Table 5 shows that the Primer yields positive gains for every source and transfer Student" (MathVerse) | App B.1 p15; Table 5 | All six target cells positive: +5.0, +34.5, +2.0, +30.5, +3.5, +39.0. | supported | R3 | 1.0

## Rejected from AG (do not add as rows)
- Sec 4.3 "these fine-grained results further support ... preservation of existing capabilities": the text states the Omni-MATH-2 retention drops (-9.2 and -14.2 pp) and says the Primer "largely preserves" capability, so the loss is carved out.
- App B.2 "APO approaches and even slightly underperforms the baseline": AG misread Fig. 4. At 96K: Flash about 81, APE about 79, GEPA about 80, UTT about 84.5; the claim is about right.
- Figure 1 "text can serve as a universal medium": hedged ("suggest that", "can serve"); four models, three tasks.

## Open items
- Headline Table 1 / 2 / 3 scores for all methods are computed over the full pool D including the distillation training split; KD baselines also train on that split, so the leak is symmetric for Table 3 but not for prompt-only baselines. See P11-R1.
- Table 1 Fast1 gain for the Opus->Flash Primer applied to Qwen is only +10 (12 -> 22); all other Fast1 cells gain 20 or more.
- Figure-read values (Fig. 3 split-wise bars, Fig. 4 curves) were checked only for Fig. 4 at 96K.
- All results use a single run per cell with no variance reported.
