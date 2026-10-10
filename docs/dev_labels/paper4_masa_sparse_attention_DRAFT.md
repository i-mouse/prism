# Dev labels - paper 4: MASA, Matrix Approximation Sparse Attention (arXiv 2610.10871v1) - DRAFT

Status: DRAFT. Labels follow docs/LABEL_RUBRIC.md. Numbers checked against the PDF
text (Tables 1-3, Tables 8-11, Sections 4.1-4.4, Conclusion, Appendices A, E, F).

## Refusal-family rows (3)
| id | claim | where | label | rule | conf | note |
| P4-R1 | "...show consistent accuracy gains..." / "MASA gives consistent accuracy gains under matched settings with negligible latency overhead" (one row) | Abstract p1; Intro p2; Conclusion p9 | partially_supported | R3 | 0.75 | Table 1: MInference 64K 82.3 -> 81.57; FlexPrefill-Qwen 8K 89.91 -> 88.94. Table 2: MInference En.Sum 20.5 -> 19.73, En.QA 12.9 -> 12.15; FlexPrefill-Llama En.MC 69.43 -> 66.81. Body text itself says "11 of 12"; abstract/conclusion do not carve out the losses. |
| P4-R2 | "Norm clipping is helpful for SeerAttention and FlexPrefill-Llama, while soft norm balancing is useful in some FlexPrefill settings." | Sec 4.4, p9 | partially_supported | R3/R5 | 0.70 | FlexPrefill-Llama has no raw MASA result in Tables 9/10, so "helpful" was never measured against raw. SeerAttention RULER: clip 85 = 87.76 and clip 95 = 87.79 are below raw 87.88; only clip 90 (88.09) helps. |
| P4-R3 | "MASA does not change the sparse kernels, candidate sparse units, or budget rules of existing methods, making it orthogonal to low-level attention kernels and other LLM acceleration techniques as discussed in Appendix A." | Conclusion, p9 | partially_supported | R5 | 0.60 | judgment call. Kernel side exercised (three frameworks, official kernels). Never combined with any other acceleration technique; Appendix A argues orthogonality by design only. |

## Supported rows to keep (8)
| id | claim | where | evidence | conf |
| P4-S1 | "MASA improves all eight matched average scores across three sparse methods, three benchmark suites, and both Llama- and Qwen-family backbones" | Sec 4.2, p8 | Tables 1-3: 87.0->87.27, 87.60->88.09, 89.18->89.94, 70.75->72.16, 38.8->39.20, 47.14->47.99, 30.07->30.42, 54.20->54.37 | 0.90 |
| P4-S2 | Across four RULER configurations at 32K/64K/128K, MASA improves 11 of 12 matched length-level scores | Sec 4.2, p8 | Table 1: only loss is MInference 64K | 0.95 |
| P4-S3 | For every configuration, mean gain at 32K-128K exceeds mean gain at 4K-16K | Sec 4.2, p8 | Table 1: .333>.107, .693>.283, 1.283>.240, 2.40>.40 | 0.90 |
| P4-S4 | At 128K gains 1.28, 0.48, 1.45, 2.16; at 64K gains 2.16 (FlexPrefill-Llama) and 3.65 (FlexPrefill-Qwen) | Sec 4.2, p8 | Table 1 columns | 0.95 |
| P4-S5 | FlexPrefill-Llama on InfiniteBench 47.14 -> 47.99 vs full attention 48.06, "recovering approximately 92%" of the deficit | Sec 4.2, p8 | Table 2: deficit .92, recovered .85, 92.4% | 0.95 |
| P4-S6 | SeerAttention on RULER 87.60 -> 88.09, "from below the dense reference to above it" | Sec 4.2, p8 | Table 1: dense 88.01 | 0.95 |
| P4-S7 | FlexPrefill-Llama on RULER: +0.76 gain, original advantage over full 0.48, new advantage 1.24 | Sec 4.2, p8 | Table 1: 89.94-89.18, 89.18-88.70, 89.94-88.70 | 0.95 |
| P4-S8 | "Table 8 shows lower attention-output error in every evaluated framework-backbone pair, with all four reported paired confidence intervals above zero" (+0.41, +2.10, +2.34, +7.17 %) | Appendix E, p18 | Table 8; note 64K RULER only, 8 prespecified layers, paper says intervals are selected-setting comparisons | 0.90 |

## Open items
- Appendix F: "the main results use the tested probe configuration with the highest
  aggregate score on that benchmark". Main-table MASA numbers are best of 2-4 probe
  variants chosen on the evaluated benchmark; baselines are single configurations.
  Raw MASA beats Original in all six settings where raw is reported (RULER:
  MInference +0.13, SeerAttention +0.28, FlexPrefill-Qwen +1.41; InfiniteBench:
  MInference +0.25, FlexPrefill-Qwen +0.35; LongBench SeerAttention +0.04), but
  FlexPrefill-Llama raw is never reported, so its +0.76 RULER gain is best-of-3.
  Not used as a row: it does not contradict a claim as worded.
- No not_supported claims found.
- The efficiency claim ("negligible overhead") reads from bar chart Figure 2 labels,
  not a table; judged supported.
- AG's output for this paper matched the PDF on 15 of 20 rows; its three "consistent"
  rows were merged into P4-R1.
