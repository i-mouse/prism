# Dev labels - paper 3: Jev for knowledge tracing, "When Few or No Learners Are Logged?" (arXiv 2610.11135v1) - DRAFT

Status: DRAFT. Labels follow docs/LABEL_RUBRIC.md. Numbers checked against the PDF
text (Table 1, Table 3, Table 4, Table 9, Section 5.1-5.2, Conclusion, Limitations).

## Refusal-family rows (2)
| id | claim | where | label | rule | conf | note |
| P3-R1 | "Among the readers we tested, the gain comes from the model rather than the typed format; the input recipe helps other LLMs as much as it helps Jev." | Conclusion, p8 | partially_supported | R3 | 0.70 | Only one other LLM (DeepSeek) was run with the JevKT input; GPT-4o-mini and Gemini-2.5-Flash-Lite have no N=8 results (Table 2). Gains +.016 (Jev) vs +.010 (DeepSeek); "never differ significantly" is not equivalence. |
| P3-R2 | "For new learners the advantage holds from their first interactions" | Abstract, p1 | partially_supported | R3 | 0.55 | judgment call. Table 9 position 1: JevKT loses to best deep KT on A09 (.709 vs .749) and XES3G5M (.512 vs .542); Jev0-shot below best deep KT on the mean (.580 vs .605); the paper calls position 1 "noisy" and its counts start at position 2. |

## Supported rows to keep (7)
| id | claim | where | evidence | conf |
| P3-S1 | Jev0-shot .706 mean AUC, above LOKT (.671) and above best deep KT trained on 8 learners (.689; higher on 5/7 datasets) | Sec 4.2, p5 | Table 1: .706, .671, .689; Jev loses on DBE (.742 vs .793) and Alg05 (.698 vs .711) | 0.95 |
| P3-S2 | JevKT ahead of best deep KT by +.033, +.023, +.016 at N=8, 16, 32 (7/7 datasets each) | Sec 4.2, p5 | Table 1: .722-.689, .730-.707, .739-.723 | 0.95 |
| P3-S3 | Mean difference +.004 at N=64, -.002 at N=128, -.008 at N=256, -.028 with full data | Sec 4.2, p5 | Recomputed from per-dataset values in Table 1 (unrounded means): +.0042, -.0023, -.0080, -.028. Table-printed averages differ by .001 at N=128 only from rounding; same-measurement check (R4), no conflict. | 0.85 |
| P3-S4 | One Jev pass beats Thinking-KT on all seven datasets (Holm-corrected, +.038 to +.073 against budget 2048) | Sec 5.3, p7; Table 3 | all seven values positive and marked significant | 0.95 |
| P3-S5 | Thinking-KT costs $4,360 per million predictions, Jev0-shot $44 ("about 1/100"); JevKT $886 ("about 1/5" of Thinking-KT) | Abstract; Sec 5.4, p7; Table 4 | 44/4360 = 1/99; 886/4360 = 0.203 | 0.95 |
| P3-S6 | At N=16 the similar-learner statistic alone raises Jev0-shot from .706 to .729, shots alone to .724, both to .730 ("the statistic carries almost all of the gain") | Sec 5.2, p7 | quoted figures in text; Table 6 | 0.85 |
| P3-S7 | On unseen items with all learners logged, best deep KT is ahead (.729 vs JevKT .713; JevKT better on 1/7) | Sec 4.2, p5 | Figure 3b and Table 10 | 0.90 |

## Open items
- No not_supported claims found: the Limitations section already scopes the finding
  ("Our finding concerns one closed System-One model").
- Candidate, dropped for low confidence (0.55): "Long reasoning marks hard cases rather
  than fixing them" (Sec 5.3). It reads causal intent from a correlation (Spearman +.29).
- Table 3 caption "Reasoning does not help" judged supported: means negative, 0/7
  significant, body text says "never significantly".
- AG audit of this paper ran shell commands despite a no-commands instruction; AG's own
  partial labels for rows C12 and C20 were overturned after checking the PDF.
