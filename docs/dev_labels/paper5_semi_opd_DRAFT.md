# Dev labels - paper 5: Semi-OPD, "When Do We Need On-Policy Distillation? Distilling on Offline Student Rollouts Is Often Better" (arXiv 2610.11291v1) - DRAFT

Status: DRAFT. Labels follow docs/LABEL_RUBRIC.md. Numbers checked against the PDF
text and by recomputation (Tables 1, 3, 4; Figures 4, 11).

## Refusal-family rows (3)
| id | claim | where | label | rule | conf | note |
| P5-R1 | "The gains transfer beyond the training domain." and "This suggests that the gains are not limited to fitting the math training distribution but transfer to broader reasoning tasks." (one row) | Sec 5, p8 | partially_supported | R5 | 0.75 | Figure 11 caption: one pair only (Qwen3-1.7B <- Qwen3-4B-Instruct-2507), coding only (HumanEval, HumanEval+). All other pairs trained and evaluated on DAPO-Math. |
| P5-R2 | "...covering the most commonly used student-teacher pairs in the OPD literature." and "we evaluate 17 diverse model pairs" | Sec 1, p2; Sec 6, p9 | partially_supported | R5 | 0.55 | judgment call. Table 3 rows g and h are SFT-warm-started variants of pairs a and f (15 distinct pairs). One training domain (math). No survey of "most commonly used" pairs. The SFT variants are disclosed in Sec 2.1. |
| P5-R3 | "This cannot be addressed by simple truncation, as we empirically show the importance of covering supervision signals from different reasoning stages." | Sec 1, p3 | partially_supported | R3 | 0.60 | judgment call. Table 1: FastOPD (4K truncation) beats Standard OPD by +4.5 (1.7B: 30.7 vs 26.2) and +7.6 (4B: 52.5 vs 44.9) and beats Semi-OPD on Cascade-2 (74.8 vs 74.1); it trails Semi-OPD only at low overlap. |

## Supported rows to keep (8)
| id | claim | where | evidence | conf |
| P5-S1 | Semi-OPD outperforms OPD on 14 of 17 pairs with up to +13.6% accuracy | Abstract p1; Sec 2.3 p5 | Table 1: 39.8 vs 26.2; Table 3: 14 pairs with positive last-step gain | 0.95 |
| P5-S2 | On the remaining three pairs Semi-OPD is comparable, with gaps of 0.1-2.6% | Sec 2.3, p5 | Table 3 last-step: -0.1 (Cascade-2), -1.7 (R1-Distill-7B <- Light-R1), -2.6 (R1-Distill-7B <- Polaris) | 0.95 |
| P5-S3 | "Semi-OPD outperforms standard OPD when the initial teacher-student overlap is low" | Fig 2 caption, p2 | Table 3: all 11 pairs with overlap < 70% have positive AUC gain (+0.24 to +7.57) | 0.95 |
| P5-S4 | Pearson r = -0.73 between Semi-OPD gain and initial overlap across 17 pairs | Fig 2; Sec 3 | Recomputed from Table 3: r = -0.735 (AUC gain); -0.78 without the two SFT-variant pairs | 0.95 |
| P5-S5 | On Qwen3-1.7B and 4B, Semi-OPD gets +7.1% and +8.8% higher accuracy with 35x and 19.5x less training time than Relay-OPD | Sec 2.3, p5 | Table 1: 39.8-32.7, 57.4-48.6; Table 4: 173.3/5.0 = 34.7x, 604.4/31.0 = 19.5x | 0.95 |
| P5-S6 | On Nemotron-Cascade-2 (overlap ~89%), Semi-OPD falls 0.7% behind the best baseline while cutting training time 2.2x vs FastOPD and 4.5x vs OPD | Sec 2.3, p5 | Table 1: 74.8 vs 74.1; Table 4: 147.5/66.4, 301.4/66.4 | 0.95 |
| P5-S7 | Up to 11.4x speedup over standard OPD and 2.7x over the fastest baseline FastOPD | Abstract; Sec 2.3 | Table 4: 56.8/5.0 = 11.4x; 169.8/63.0 = 2.7x | 0.95 |
| P5-S8 | SFT on teacher rollouts followed by Semi-OPD still outperforms OPD but underperforms Semi-OPD alone (+2.05 and +1.50 vs +7.09 and +4.61) | Sec 3, p6; Fig 4 | Fig 4(b); Table 3 rows g, h | 0.90 |

## Open items
- Rejected AG label: "SFT on teacher rollouts has negative effects" is not contradicted by
  Fig 4(c,d): OPD from SFT init and OPD from the original student end at about the
  same accuracy (~35% and ~60%); the negative effect appears with Semi-OPD, as the
  caption says.
- Headline 11.4x compares Semi-OPD with Standard OPD at the 16K-style cap used in
  Table 4; against FastOPD (4K) it is 2.3x on the same pair, and the body reports
  2.7x as the maximum vs FastOPD. Carved out in the body; not used as a row.
- Not rows: "OPD is only useful for aligned pairs" (read as comparative to Semi-OPD),
  one-pair exception in Fig 14 (disclosed 15 of 16), cache reuse across teachers
  (true by design, not an empirical claim).
- No not_supported claims found.
