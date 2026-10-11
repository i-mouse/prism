# Paper 9 - OnTrack (arXiv 2610.12375v1) - DRAFT dev labels
Status: DRAFT. Labelled under docs/LABEL_RUBRIC.md before any Prism output. Verified against the PDF.
Row format: id | claim | section/page | deciding evidence | label | rule | confidence

## Refusal-family rows (1, partial; 0 not_supported)

P9-R1 | Sec 6.3: "Third, LinUOT tracks OnTrack within 0.003-0.010 AUROC everywhere: the quadratic term contributes essentially nothing to ranking on this corpus ..." | Sec 6.3 p11; Table 5 p11 | Table 5 OnTrack vs LinUOT: k=5 .612 vs .595 (gap .017); k=8 .631 vs .628 (.003); k=10 .622 vs .614 (.008); k=15 .635 vs .626 (.009); k=20 .648 vs .638 (.010). "Everywhere" is broken at k=5 (.017 exceeds the stated .010 ceiling); the other four cells fit. Gap is small, so the main point (quadratic term adds little to ranking) stands. | partially_supported | R3 (cell-by-cell on "everywhere") | 0.80

## Supported rows (8)

P9-S1 | At k=8 OnTrack ranks failing trajectories below succeeding ones better than cosine (+0.057 AUROC) | Abstract p1; Table 5 p11 | OnTrack .631, cosine .574, delta +.057 [.033, .080]. | supported | plain read | 1.0
P9-S2 | "The delta CI excludes zero for k <= 10" and the advantage is gone by k=15 | Table 5 caption and Sec 6.3 | k=5 [.037,.083]; k=8 [.033,.080]; k=10 [.007,.057]; k=15 cosine .633 vs OnTrack .635 (delta +.002 [-.022,.027]). | supported | R3 | 1.0
P9-S3 | Component attribution on real traces: removing the mask changes almost nothing (13/40 -> 14/40 false-positive traces); removing the GW term more than doubles the benign false-alarm count (29/40), near L1-only 31/40 and rule baseline 32/40 | Sec 6.1 p10; Table 4 | 29/40 > 2 x 13/40 = 26/40; counts as stated. | supported | plain read | 1.0
P9-S4 | At abort threshold 0.60 the policy saves about 18% of compute with 83% precision at the corpus base rate | Abstract p1; Table 6 p12 | Cost saved 17.9%; precision 83%; true stop 23.3%, false stop 20.7% (n=150 per class, balanced). Threshold selection disclosed as candidate policy, not calibrated on held-out data. | supported | plain read | 0.85
P9-S5 | False blocks on valid irreversible calls: 0/50 (95% bound about 6%) | Table 3 p10; Sec 6.1 | 0/50. Disclosed: G-a initially failed (first gate read a stale frontier, blocked 50/50) and was fixed. | supported | plain read | 1.0
P9-S6 | Randomized campaign: loop recall 100% at latency 0; hallucination recall 100% at latency 2; causal-inversion recall 94.1% at latency 0; 0 false interventions over 200 benign runs (one-sided 95% bound 1.5%) | Sec 6.1 pp10-11 | As stated in the text (40 random-DAG tasks x 7 conditions, seeded). | supported | plain read | 0.95
P9-S7 | Fast path runs at p50 0.85 ms / p95 1.6 ms per event at t=m=40, K=3 (Apple M5 Max core) | Sec 5 p9; Sec 6.1 p10 | As stated. | supported | plain read | 0.95
P9-S8 | At the earliest checkpoint trace length alone is the single best signal (n steps .622 at k=5); OnTrack leads every content- and structure-aware method but not the length prior | Sec 6.3 p11; Table 5 | k=5: n steps .622 > OnTrack .612 > LinUOT .595 > cosine .552 (GED .574). | supported | R3 | 1.0

## Rejected from AG (do not add as rows)
- Reference-provenance tiers (Sec 3 / 4.6, Fig. 2: gold/mined enable intervention, axiomatic warn, generated inform) as not_supported: design policy, no result claimed; see open items.
- Sec 7 "quadratic structure term ... expected to emerge on structurally diverse corpora": author-disclosed limitation, hedged as an expectation.
- Abstract "content similarity-based approaches (+0.057)": the delta is exactly the cosine margin.
- "Reversible actions are never blocked" and "never punished for being early": design descriptions of the L3 gate and frontier masking (Prop. 2 conditions in Sec 5).

## Open items
- Reference-provenance tiers (mined, axiomatic, planner-generated references) are described but never experimentally varied; SWE-bench uses 5 hand-picked reference instances. Design policy, so not a row.
- Abstract "83% of interrupted runs were heading to failure (5 of 6 aborts correct)": the figure is precision at the corpus base rate where 81% of traces are unresolved (Table 6 caption), so an abort-everything policy would score about 81%. Numbers match; interpretive gap only. Not a row.
- L3 irreversible-action gate was tested only on synthetic scenarios and 50 benign runs; the SWE-bench corpus has no irreversible-annotated tools (disclosed in Sec 6.1).
- Paper is carefully scoped and discloses its own negative results (splice detection near floor, outcome correlation mediated by length); low yield for refusal rows.
