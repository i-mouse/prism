# Dev baseline run 1 - adjudication of refusal rows (4 of 12 papers)

Date: 2026-10-12
Status: hand-adjudicated (Nitin + Claude chat), refusal-family rows only.
Scope: 4 dev papers ingested in baseline run 1. Remaining 8 papers in progress.
Source: draft fixtures in docs/evals/fixtures/dev/run1/ (matcher-matched, not official).

## Context

- Pipeline config frozen for run 1 (no .env / prompt / model change).
- Models: extractor + auditor + structurer gemini-3.6-flash (thinking not set = default medium);
  span grounding groq/openai/gpt-oss-20b (fallback gemini-3.1-flash-lite);
  eval matcher gemini-3.6-flash.
- Real cost: AI Studio INR 1,250.00 -> 1,655.55 for 4 papers = about INR 101 per paper
  (about 35 extracted claims per paper, not the 10 assumed in the estimate).
- Prism labels on these 4 papers: 139 claims, 135 S, 4 PS, 0 NS.

## Paper map

| Dev id | File |
|---|---|
| P7 | 2610.10590v1.pdf |
| P4 | 2610.10871v1.pdf |
| P2 | 2610.11132v1.pdf |
| P3 | 2610.11135v1.pdf |

## Adjudicated refusal rows

| Row | Expected | Correct match (claim index) | Prism label | Verdict |
|---|---|---|---|---|
| P7-R1 | PS | #5 (exact sentence) | S | audit miss |
| P7-R2 | PS | none | - | extraction miss |
| P4-R1 | PS | #2 (same claim, different sentence) | S | audit miss |
| P4-R2 | PS | #30 (exact sentence) | S | audit miss |
| P4-R3 | PS | none (1) | - | extraction miss |
| P2-R1 | NS | none | - | extraction miss |
| P2-R3 | PS | none (2) | - | extraction miss |
| P2-R4 | PS | none | - | extraction miss |
| P2-R5 | PS | #24 (exact sentence) | PS | HIT |
| P3-R1 | PS | none (1) | - | extraction miss |
| P3-R2 | PS | #3 (exact sentence) | S | audit miss |

(1) Judgment call. Prism extracted a sibling sentence carrying only the safe half of the claim
(P4-R3: #10 "kernels/budgets unchanged"; P3-R1: #6 "gain comes from the model"). The overreaching
half ("orthogonal to other LLM acceleration techniques"; "helps other LLMs as much as it helps Jev")
was never extracted, so counted as extraction miss.
(2) #25 ("ratio ... at most 13.0%") is a narrower math/coding claim, not the Table 10 title claim.

## Matcher errors found

- P3-R2: matcher matched #17; #3 is a character-exact copy of the expected sentence. Correct match is #3.
- P4-R1: matcher matched #9; #2 is the closer claim (multiple methods, benchmarks, backbones). Verdict unchanged (both S).
- P7-R2, P4-R3, P2-R1, P2-R3, P2-R4, P3-R1: matcher said "no match"; hand check agrees.
- Conclusion: the live LLM matcher is not reliable enough to produce official numbers.
  Official numbers come only from the adjudicated match map.

## Result (draft, 4 papers, 11 refusal rows)

- Refusal hits: 1 / 11 (9%).
- Extraction misses: 6. Audit misses: 4.
- Ceiling with a perfect auditor and today's extractor: 5 / 11 (45%).
  The 70% floor is unreachable without extractor changes.

## Failure patterns (hypotheses, to confirm on all 12 papers)

Extractor skips:
1. Hedged "in principle / could" claims (P7-R2, P2-R1).
2. Table titles and captions (P2-R3, P2-R4).
3. Conclusion restatements that add the overreach; it keeps the safer abstract/intro sibling
   (P4-R3, P3-R1).

Auditor misses hidden losses:
- All 4 audit misses are headline "consistent / every / plural" claims contradicted by specific
  table cells or resting on a single case (P7-R1, P4-R1, P4-R2, P3-R2).
- The auditor reads the headline and supporting text but does not search tables for counter-examples.
- This is the target of experiment 1 (thinking_level=high on the auditor).

## Open items

- Supported (S) rows on these 4 papers are not yet adjudicated (needed for 100% match-map coverage,
  false rejections and positives).
- Remaining 8 papers: ingest (run 1), dump draft fixtures, adjudicate refusal rows, then full failure map.
- Official fixtures: re-dump with --match-map after adjudication (no LLM call).
- No pipeline change until the full 12-paper failure map exists (the "before" number must come from
  today's frozen config).
