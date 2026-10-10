# Paper 6 - MedBenchAgent (arXiv 2610.11312v1) - DRAFT dev labels
Status: DRAFT. Labelled under docs/LABEL_RUBRIC.md before any Prism output. Verified against the PDF.
Row format: id | claim | section/page | deciding evidence | label | rule | confidence

## Refusal-family rows (2, both partial; 0 not_supported)

P6-R1 | Abstract: "These results establish constrained compilation as a scalable and auditable framework for medical VLM benchmark construction beyond question generation." | Abstract p1; Sec 5.4 p9; Conclusion/Limitations p10 | Two domains tested (breast imaging: 3 datasets; dermoscopy: 1 dataset). Planning checkpoints use researcher review (Sec 5.1); Limitations: "limited human involvement remains at planning checkpoints". No scaling, throughput, cost or time measurement anywhere. "Auditable" is backed (BIR, 994/1,000 audit); "scalable ... beyond question generation" is not tested. | partially_supported | R3 (scope of generalization) | 0.60

P6-R2 | Abstract: "We further demonstrate portability to a specialized medical domain and evaluate twelve VLMs ..." and Intro: "We further instantiate the workflow in a specialized medical domain under a different annotation schema and evaluate twelve VLMs on the resulting benchmark." | Abstract p1; Intro p2; Table 3 p8; App C.3 Table 10 p21 | Table 3 (breast imaging) lists 12 VLMs. Table 10 (ISIC 2018 dermoscopy, the specialized domain) lists 11: BreastGPT-8B is absent. Main-text Fig. 3 shows only 8 models. | partially_supported | R3 (hidden loss) | 0.60 (scope ambiguity: "resulting benchmark" could mean the breast benchmark, where 12 is correct)

## Supported rows (8)

P6-S1 | MedBenchAgent Task-Space F1 90.9% vs direct induction 79.2-80.0% and prior-guided 85.1% | Table 1; Sec 5.2 p7 | Values as in Table 1. | supported | plain read | 1.0
P6-S2 | 994 of 1,000 sampled items pass human audit (99.4%) | Table 2; Sec 5.2 p8 | 994 pass, 6 fail (4 VinDr BI-RADS finding-type, 2 BrEaST unsupported additions). | supported | plain read | 1.0
P6-S3 | Providing T0 gives 85.1% F1; MedBenchAgent raises precision 76.9% -> 87.0% at the same 95.2% recall, false positives six -> three | Table 1; Sec 5.2 p7 | P/R/FP as stated; consistent with TP=20, FN=1. | supported | plain read | 1.0
P6-S4 | "All methods achieve 100% EMA on matched tasks." | Table 1 | Checked cell by cell: all five rows 100.0%. | supported | R3 | 1.0
P6-S5 | Medical VLMs outperform general-purpose by 6.23 points Overall Acc. but trail by 2.48 on AC | Table 3 family summary p8 | 45.10 - 38.87 = 6.23; 26.89 - 29.37 = -2.48. | supported | plain read | 1.0
P6-S6 | Lingshu-7B has higher Overall Acc. than Qwen2.5-VL-32B (47.00 vs 44.65), while Qwen2.5-VL-32B is better on all six spatial measures | Tables 3-4 p8 | Checked all six: 9.70/6.10 vs 4.41/0.81; 10.83/7.32 vs 3.65/0.65; 40.63/37.52 vs 4.71/0.88. | supported | R3 | 1.0
P6-S7 | Under blurred images, across four medical VLMs Acc. drops 5.86-17.97 pp and F1 6.33-22.61 pp | Table 5 p9 | Delta column: Acc 12.48, 8.83, 5.86, 17.97; F1 6.97, 9.68, 6.33, 22.61. | supported | plain read | 1.0
P6-S8 | Qwen3-VL-8B thinking vs instruct: FA +27.09; AA, FT, AC, DX, PS -9.37, -1.22, -0.53, -4.85, -7.50 | Table 3; App D.3.2 | 56.93-29.84; 25.52-34.89; 15.09-16.31; 38.58-39.11; 35.13-39.98; 53.05-60.55. | supported | plain read | 1.0

## Dropped (do not add as rows)
- Sec 5.3 "The consistent degradation indicates benchmark performance remains sensitive to visual evidence": aggregate claim, all 4 models drop overall. Note for open items: some task-level cells rise under blur (Lingshu-7B AC 25.28->32.85, Hulu-Med-7B AC 22.75->31.07, BreastGPT-8B FT 35.73->42.01), but R3 grades at the level the claim speaks about.
- Sec 1 "general-purpose systems ... do not explicitly constrain medical benchmark specification ...": characterization of other papers, not the paper's own evidence.
- Sec 4.3 "accepted multiple-choice items are balanced with respect to option positions": pipeline description, no result claimed.

## Open items
- Conclusion "annotation-evidence mapping and item instantiation become substantially more reliable once benchmark semantics are fixed": no run without the locked specification, so no baseline for the "once fixed" comparison; the contrast is across different metrics (F1 vs pass rate). Low confidence (about 0.45), not added as a row.
- Sec 5.2 "These results show that the BIR-mediated design primarily improves ...": baselines are single-call direct induction; no ablation separates BIR from multi-step planning. Low confidence (about 0.50), not added as a row.
- Reference task space T* was authored by dataset-familiar researchers (the authors' side) with informal clinical input; F1 gap rests on 3 fewer false positives out of 21 reference tasks, single run.
