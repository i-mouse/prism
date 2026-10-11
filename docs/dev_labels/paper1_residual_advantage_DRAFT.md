# Dev labels - paper 1: Residual Advantage (arXiv 2610.11519) - DRAFT

Status: DRAFT. Labels follow docs/LABEL_RUBRIC.md. Page numbers and numbers were
checked against the PDF text and by arithmetic on the tables. Rows marked judgment
call are Nitin's final decision once confirmed.

## Refusal-family rows (3)
| id | claim | where | label | rule | conf | note |
| P1-R1 | "Removing either baseline, replacing the residual by the log ratio, or adding direct supervision of the teacher's top token lowers performance." | Conclusion, p9 | partially_supported | R3 | 0.80 | Table 4: adding the branch to sampled OPD raises Avg +0.30 and Pass +0.64. |
| P1-R2 | "...an elegant property that helps RA preserve exploration in RL." | Conclusion, p9 | partially_supported | R1/R5 | 0.55 | judgment call. No exploration measure in the paper; Sec 4.4 calls the mechanism a conjecture. |
| P1-R3 | "The guidance term decreases ... as the student approaches the teacher" / guidance fades as the two converge (Appendix C.1) | Sec 2.2, p4; Fig 5a, p28 | partially_supported | R3 | 0.50 | judgment call. Single seed, single 4B run; Appendix A.6/A.9 say the bounds do not show how guidance evolves in training. |

## Supported rows to keep (9)
| id | claim | where | evidence | conf |
| P1-S1 | RA improves the base algorithm "in all 24 comparisons" | Abstract p1; Table 1 p5 | all 24 pairwise comparisons increase (R3 cell by cell) | 0.90 |
| P1-S2 | Macro gains 1.7-3.6 Avg@8 and 3.9-6.3 Pass@8 | Table 10 p22 | 1.74-3.58 and 3.89-6.33 | 0.95 |
| P1-S3 | Co-RA "adds a further 1.0-1.5 Avg@8 points" | Abstract; Table 10 | 1.03 to 1.45 | 0.95 |
| P1-S4 | Co-RA Avg@8 rises in all twelve means | Table 1 | 12 of 12 | 0.95 |
| P1-S5 | Pass@512 margin over untrained student grows 13.4 -> 16.9 | Sec 3 p6; Table 28 p36 | 13.35 -> 16.92 | 0.85 |
| P1-S6 | Every residual variant beats verifier-only; full RA beats every control at every matched weight | Table 2 p7 | all columns checked | 0.90 |
| P1-S7 | No log-ratio variant reaches full RA | Tables 3 p7, 24 p34 | best log variant 28.04/43.50 below full RA 29.25/45.20 | 0.90 |
| P1-S8 | Adapted teacher is a worse solver by 0.8-2.3 Avg and 0.7-3.5 Pass | Table 30 p37 | 0.79-2.31 and 0.70-3.49 | 0.90 |
| P1-S9 | "the local advantages average to 3 x 10^-4 per token" | Sec 4.1 p7; Appendix C.2 | Table 16 reports the mean over responses (+0.03 = 0.003 per token), which is a different measurement from the token-pooled mean the text states, so no conflict (R4 same-measurement check) | 0.75 |

## Open items
- Dropped: the Pass@512 conclusion sentence ("Up to Pass@512 the margin ... grows while
  that of verifier-only training narrows"). Numbers hold, but Table 28 covers only
  1.7B with REINFORCE++, and whether the sentence overclaims depends on context.
- No not_supported claims found: the paper scopes itself to Qwen3 and math.
- This paper is mostly a source of supported rows.
