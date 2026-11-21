# Test B score (one gemini-4-carbon call per dev paper)

- status: SCORED
- mode: 3-RUN (n_runs=3)
- caught: 9 / 31
- false_rejections: 17 / 88
- found: 79 / 119
- verdict: PRISM BETTER
- release bar (caught >= 22 and false_rejections <= 8): no
- failed_paper_runs: 0

## Caught breakdown (report only, never changes the verdict)

- auditor_miss: 3
- extraction_miss: 1
- prism_caught: 5
- unclassified_if_prism_caught_unavailable: 0

## Other report-only fields

- unmatched_claims_by_verdict: {'supported': 564, 'partially_supported': 205, 'not_supported': 12}
- duplicate_claim_matches: 10
- quote_grounding_rate: 0.9497
- tokens_and_cost_per_paper: {'n': 36.0, 'mean_prompt_tokens': 33236.416666666664, 'mean_output_tokens': 5472.138888888889, 'mean_thought_tokens': 6830.75, 'mean_cost_inr': 18.95017222222222, 'mean_cost_inr_after_2026_12_01': 37.90034444444444}

## Per-row table

| row_id | per_run_status | vote | best_score |
|---|---|---|---|
| P1-R1 | ['not_found', 'flagged', 'not_found'] | not_flagged | 100.0 |
| P1-R2 | ['not_found', 'not_found', 'flagged'] | not_flagged | 100.0 |
| P1-R3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 58.2 |
| P1-S1 | ['not_found', 'flagged', 'flagged'] | flagged | 100.0 |
| P1-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P1-S3 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P1-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P1-S5 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P1-S6 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P1-S7 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P1-S8 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P1-S9 | ['not_found', 'not_found', 'not_found'] | not_flagged | 75.4 |
| P2-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 51.1 |
| P2-R3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 61.7 |
| P2-R4 | ['not_found', 'not_found', 'not_found'] | not_flagged | 74.3 |
| P2-R5 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P2-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P2-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P2-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P2-S5 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P2-S6 | ['flagged', 'flagged', 'supported'] | flagged | 100.0 |
| P2-S7 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P2-S8 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P3-R1 | ['not_found', 'flagged', 'not_found'] | not_flagged | 100.0 |
| P3-R2 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P3-S1 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P3-S2 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P3-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P3-S5 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P3-S6 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P3-S7 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P4-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 64.4 |
| P4-R2 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P4-R3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 49.9 |
| P4-S1 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S5 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S6 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S7 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P4-S8 | ['not_found', 'not_found', 'not_found'] | not_flagged | 60.7 |
| P5-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 60.9 |
| P5-R2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 59.1 |
| P5-R3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 50.2 |
| P5-S1 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P5-S2 | ['supported', 'not_found', 'not_found'] | not_flagged | 100.0 |
| P5-S3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 61.0 |
| P5-S4 | ['not_found', 'not_found', 'flagged'] | not_flagged | 100.0 |
| P5-S5 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P5-S6 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P5-S7 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P6-R1 | ['not_found', 'flagged', 'flagged'] | flagged | 100.0 |
| P6-R2 | ['supported', 'supported', 'not_found'] | not_flagged | 100.0 |
| P6-S1 | ['supported', 'not_found', 'supported'] | not_flagged | 100.0 |
| P6-S2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 48.2 |
| P6-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P6-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P6-S5 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P6-S8 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-R1 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P7-R2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 49.5 |
| P7-S1 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-S5 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-S6 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P7-S8 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P8-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 51.5 |
| P8-R2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 58.0 |
| P8-R3 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P8-S1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 50.0 |
| P8-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P8-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P8-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P8-S5 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P8-S6 | ['flagged', 'flagged', 'supported'] | flagged | 100.0 |
| P8-S7 | ['supported', 'supported', 'flagged'] | not_flagged | 100.0 |
| P8-S8 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P9-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 45.8 |
| P9-S1 | ['supported', 'flagged', 'supported'] | not_flagged | 100.0 |
| P9-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P9-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P9-S4 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P9-S6 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P9-S7 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P9-S8 | ['not_found', 'not_found', 'not_found'] | not_flagged | 47.4 |
| P10-R1 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-R2 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-R3 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-S1 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-S2 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-S3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 65.4 |
| P10-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P10-S5 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-S6 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-S7 | ['flagged', 'flagged', 'flagged'] | flagged | 100.0 |
| P10-S8 | ['not_found', 'not_found', 'not_found'] | not_flagged | 45.2 |
| P11-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 49.4 |
| P11-R2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 79.3 |
| P11-R3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 51.6 |
| P11-S1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 71.1 |
| P11-S2 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P11-S3 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P11-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P11-S6 | ['not_found', 'supported', 'not_found'] | not_flagged | 100.0 |
| P11-S7 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P11-S8 | ['not_found', 'supported', 'not_found'] | not_flagged | 100.0 |
| P12-R1 | ['not_found', 'not_found', 'not_found'] | not_flagged | 53.2 |
| P12-R2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 66.5 |
| P12-S1 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P12-S2 | ['not_found', 'not_found', 'not_found'] | not_flagged | 49.7 |
| P12-S3 | ['not_found', 'not_found', 'not_found'] | not_flagged | 51.4 |
| P12-S4 | ['supported', 'supported', 'supported'] | not_flagged | 100.0 |
| P12-S5 | ['not_found', 'not_found', 'not_found'] | not_flagged | 49.0 |
| P12-S6 | ['not_found', 'not_found', 'not_found'] | not_flagged | 41.1 |
| P12-S7 | ['not_found', 'not_found', 'not_found'] | not_flagged | 48.2 |
| P12-S8 | ['not_found', 'not_found', 'not_found'] | not_flagged | 48.4 |
