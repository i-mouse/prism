# Dev labels - paper 2: SFT-as-Context (arXiv 2610.11132v1) - DRAFT

Status: DRAFT. Labels follow docs/LABEL_RUBRIC.md. Numbers checked against the PDF
text (Table 1, Table 5, Tables 7-8, Table 10, Figure 2, Appendix E).

## Refusal-family rows (5)
| id | claim (verbatim, abbreviated) | where | label | rule | conf | note |
| P2-R1 | "In principle, the same inference-time approach could be applied to a model fine-tuned with reinforcement learning (RLFT)..." and Conclusion "the same framework could naturally extend beyond SFT to other post-training methods, such as reinforcement learning" | p9 Related Work; p10 Conclusion | not_supported | R1+R5 | 0.80 | One row. Never tested; Appendix E says "we do not apply SFT-as-context (or RL-as-context)". expected_evidence_sections: [], grounding_negative: true |
| P2-R2 | "Since SFT-as-context is agnostic to the post-training method used to obtain the context-providing model..." | Appendix E, p28 | not_supported | R5 | 0.70 | Only SFT-trained context providers were tested. expected_evidence_sections: [], grounding_negative: true |
| P2-R3 | Table 10 title: "SFT-as-context incurs modest overhead compared with SFT" | Appendix I, p31-33 | partially_supported | R3 | 0.65 | judgment call. NutriBench-English 198.1%, Non-English 143.9%; body text calls nutrition an outlier but the title does not. |
| P2-R4 | Table 5 caption: "RL-trained models do not show forgetting of instruction-following capability" | Appendix E, p28 | partially_supported | R3 | 0.60 | judgment call. Average -0.22 but FastCuRL-1.5B-Preview -3.51, Skywork-OR1-Math-7B -3.14, AceMath-RL-Nemotron-7B -2.03, Polaris-7B-Preview -2.03. |
| P2-R5 | "As shown in Tables 7 and 8, SFT-as-context outperforms even the oracle router." | Appendix G, p30 | partially_supported | R3 | 0.65 | judgment call. Table 7: Bespoke-Stratos-7B ties (0.0). Table 8: OlympicCoder-7B -1.9. The Table 8 caption itself names the exception, so that caption is supported. |

## Supported rows to keep (8)
| id | claim | where | evidence | conf |
| P2-S1 | Gaps of 2.2 (AIME 2024), 2.1 (LiveCodeBench), 2.0 macro MAE (NutriBench-English) | Abstract | Table 1: 56.0-53.8, 55.5-53.4, 18.4-16.4 | 0.97 |
| P2-S2 | "within 2.2 percentage points of the parent models on general capabilities on average" | Abstract | Table 1: 11 general gaps average 1.86 (aggregate claim) | 0.90 |
| P2-S3 | Recovery 95.0% (AIME 2024), 94.1% (LiveCodeBench); average 94.2% for general capabilities | p3 | Table 1 R column; 1036.5/11 = 94.2 | 0.97 |
| P2-S4 | SFT reduces general capability by 33.2 pp on average | Sec 2.2, p4 | Table 1: 11 gaps sum 364.9, mean 33.17 | 0.95 |
| P2-S5 | Qwen3-8B largest drop in acknowledging non-food, 99.6% to 10.7% | Sec 2.2, p4 | Figure 2(c): -88.9, the largest of the three | 0.90 |
| P2-S6 | 32B remaining gap smaller than 7B: average -1.8 vs -7.5 | Sec 3, p6 | Figure 2(a) Hard IF: 32B -4.4, +0.2, -1.3; 7B -6.8, -6.0, -10.5, -6.5 | 0.95 |
| P2-S7 | Open-source SFT context "consistently improves" a strong proprietary model on NutriBench-English | Sec 5.1, p9 | Table 2: all 3 tested contexts (14.13, 14.08, 14.41) below Gemini alone 17.44 (R3 cell by cell) | 0.88 |
| P2-S8 | Second pass ratio "at most 13.0%" for math and coding | Appendix I, p31 | Table 10: max 13.0 (IFEval, math); all other math and coding rows lower | 0.95 |

## Open items
- "SFT-as-context preserves fine-tuning gains while mitigating forgetting across all 19
  pairs and 11 benchmarks": supported (R3), conf 0.70, judgment call. Figure 2 was
  spot-checked, not scanned cell by cell.
- Dropped: Conclusion "showing that useful SFT responses can steer ..." (wording
  stronger than the body's "suggesting"; no clean rubric rule).
- EFT/Proxy-Tuning and CPR mentions are descriptive, not testable claims.
