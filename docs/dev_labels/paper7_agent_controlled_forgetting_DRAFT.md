# Paper 7 - Agent-Controlled Forgetting for Tool-Using Agents (arXiv 2610.10590v1) - DRAFT dev labels
Status: DRAFT. Labelled under docs/LABEL_RUBRIC.md before any Prism output. Verified against the PDF.
Row format: id | claim | section/page | deciding evidence | label | rule | confidence

## Refusal-family rows (2, both partial; 0 not_supported)

P7-R1 | Abstract: "These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload dependence as a central consideration for reversible context management." | Abstract p1; Sec 4.1 p5; Sec 7 p11 | Plural "trajectories" rests on one OpenTelemetry pair (Table 1). Sec 7: "one OpenTelemetry pair and one Planroom pair do not estimate the variance of the policy's effect". Sec 4.1: "development-informed case study rather than a held-out confirmatory benchmark". Sec 7: retained arm had 275 logical image occurrences, method none, so the saving cannot be attributed to text archival alone. | partially_supported | R3 (scope of generalization) | 0.55 (judgment call: Reading 2 = supported, the abstract carves out workload dependence via Planroom)

P7-R2 | Sec 6: "In principle, the same contract can cover documentation, diagnostic logs, browser text, and images." | Sec 6 p10; Sec 5.3 p8; Sec 7 p11 | Documentation (Planroom, Context7), diagnostic logs and browser text (OpenTelemetry) were archived. Sec 5.3: "no image payload is archived". The "in principle" hedge narrows scope but does not rescue the untested image modality. | partially_supported | R1 | 0.65

## Supported rows (8)

P7-S1 | Abstract/Table 1: 231,951 vs 912,492 final prompt tokens, 50% fewer cumulative input, cost $1.28-$1.44 vs ~$4.38 | Table 1 p7 | 22,988,240 vs 45,766,146 = -49.77%; costs 1.283-1.436 vs 4.378-4.379. | supported | plain read | 1.0
P7-S2 | Both arms passed the two-case primary oracle; neither fully satisfied the follow-up | Table 1; Sec 5.2 | 2/2 vs 2/2; follow-up 3/6 vs 2/6. | supported | plain read | 1.0
P7-S3 | Method made more requests and took 17% longer; more than twice the completion tokens | Table 1 | 185 vs 121 requests; 2,025 vs 1,730 s = +17.05%; 71,919 vs 33,834 = 2.126x. | supported | plain read | 1.0
P7-S4 | Primary submission 124,746 vs 847,674 (85% reduction); final 231,951 vs 912,492 (75%) | Sec 5.1 p7 | -85.28%; -74.58%. | supported | plain read | 1.0
P7-S5 | Estimated cost approximately 67-71% lower | Sec 5.1 p7 | (4.378-1.436)/4.378 = 67.2%; (4.379-1.283)/4.379 = 70.7%. | supported | plain read | 1.0
P7-S6 | Method shows stronger tested signal handling but weaker tested startup-failure handling | Sec 5.2 p8 | Method exits 0 after SIGTERM (8.43 s) and SIGINT (8.85 s); retained killed with 137; retained passes occupied-port probe (status 1), method's second process times out at 30 s. | supported | plain read | 1.0
P7-S7 | Planroom yields no context or cost saving: +6% prompt tokens, <1% more total tokens | Table 2 p9 | 283,105 vs 265,965 = +6.44%; 68,136,934 vs 67,669,624 = +0.69%. | supported | plain read | 1.0
P7-S8 | Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps | Sec 5.4; Table 3 p9 | Max method final 145,213 < min retained final 234,057 (cell-by-cell, R3). Totals overlap: method 8.29M-16.85M vs retained 12.27M-20.22M. | supported | R3 | 0.95

## Dropped (do not add as rows)
- Sec 1 "The mechanism originates in the author's Arios agent ... February 2026": provenance, not an empirical claim.
- Abstract "Tool-using agents repeatedly carry observations ...": motivating premise, backed by the paper's own data.
- Sec 2/9 "returns exact archived payloads on recovery": design property. Storage equality 26/26 verified; recovery never exercised (Sec 5.3, Sec 7). Kept as open item, not a row.

## Open items
- Whether to add the "returns exact archived payloads on recovery" claim as a partial row (recovery unmeasured per Sec 7).
- This paper is carefully scoped; it lists its own missing baselines (no ACON, ACM, CLM, provider-side editing comparison) and does not claim superiority. No not_supported rows.
