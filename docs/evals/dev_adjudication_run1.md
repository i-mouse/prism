# Dev baseline run 1 - adjudication of refusal rows (all 12 papers)
 
Date: 2026-10-12
Status: hand-adjudicated (Nitin + Claude chat), refusal-family rows 31/31. Supported rows: only the
false-rejection check (Part B) so far.
Source: draft fixtures in docs/evals/fixtures/dev/run1/ (matcher-matched, not official), committed
before adjudication. Rules pre-registered in docs/decisions.md (2026-10-12) before the 20-row pack
was opened.
 
## Context
 
- Pipeline config frozen for run 1. Verified from DB: prompt_version cb3272cce551 and model
  gemini-3.6-flash identical across all 12 papers. Thinking setting and span-grounding model
  actually used are not persisted.
- Models: extractor + auditor + structurer gemini-3.6-flash (thinking not set = default medium);
  span grounding groq/openai/gpt-oss-20b (fallback gemini-3.1-flash-lite); eval matcher gemini-3.6-flash.
- Cost: run 1 ingestion INR 1,250.00 -> 2,298.40 (INR 1,048.40 for 12 papers, about INR 87/paper).
  Fixture dump for 8 papers: 10 matcher calls, INR 11.38 (about INR 1.1/call; 2 extra calls because
  --dry-run in dump_fixture.py still calls the matcher).
- Prism labels, all 12 papers (effective_status): 362 claims, 325 S, 24 PS, 13 NS.
  7 of 13 NS are grounding demotions (raw label S, missing=true). 0 demotions on the first 4 papers.
- Hit rule used: on a refusal row, Prism effective_status PS or NS counts as a hit (scorer's
  _REFUSAL_LABELS). No row depended on PS/NS cross-matching.
## Paper map
 
| Dev id | File |
|---|---|
| P1 | 2610.11519v1 |
| P2 | 2610.11132v1 |
| P3 | 2610.11135v1 |
| P4 | 2610.10871v1 |
| P5 | 2610.11291v1 |
| P6 | 2610.11312v1 |
| P7 | 2610.10590v1 |
| P8 | 2610.12124v1 |
| P9 | 2610.12375v1 |
| P10 | 2610.12176v1 |
| P11 | 2610.12114v1 |
| P12 | 2610.12168v1 |
 
## Adjudicated refusal rows (31)
 
| Row | Expected | Correct match (claim index) | Prism | Verdict | Pattern |
|---|---|---|---|---|---|
| P7-R1 | PS | #5 (exact) | S | audit miss | A1 |
| P7-R2 | PS | none | - | extraction miss | E1 |
| P4-R1 | PS | #2 (same claim, other sentence) | S | audit miss | A1 |
| P4-R2 | PS | #30 (exact) | S | audit miss | A1 |
| P4-R3 | PS | none (1) | - | extraction miss | E3 |
| P2-R1 | NS | none | - | extraction miss | E1 |
| P2-R3 | PS | none (2) | - | extraction miss | E2 |
| P2-R4 | PS | none | - | extraction miss | E2 |
| P2-R5 | PS | #24 (exact) | PS | HIT | |
| P3-R1 | PS | none (1) | - | extraction miss | E3 |
| P3-R2 | PS | #3 (exact) | S | audit miss | A1 |
| P1-R1 | PS | #32 (exact) | S | audit miss | A1 |
| P1-R2 | PS | none (#7 carries only the bound/fading half) | - | extraction miss | E1 |
| P1-R3 | PS | #7 (same claim, other sentence) | PS | HIT | |
| P5-R1 | PS | #33 (the transfer claim; #32 is its evidence sentence) | S | audit miss | A1 |
| P5-R2 | PS | #1 (3) | S | audit miss | A1 |
| P5-R3 | PS | none (#27 is a narrower Fig 5 result) | - | extraction miss | E3 |
| P6-R1 | PS | #4 (exact) | PS | HIT | |
| P6-R2 | PS | #3 (exact) | S | audit miss | A1 |
| P8-R1 | PS | #6 (same claim, other sentence) | PS | HIT | |
| P8-R2 | PS | #7 (4) | S | audit miss | A1 |
| P8-R3 | PS | none (#9 is the accurate "exceeds four of six" sibling) | - | extraction miss | E3 |
| P9-R1 | PS | none (#15 is fast-path vs finalization, not LinUOT vs OnTrack) | - | extraction miss | E2 |
| P10-R1 | PS | #3 (exact) | PS | HIT | |
| P10-R2 | PS | #4 (exact) | PS | HIT | |
| P10-R3 | PS | #16 (exact) | PS | HIT | |
| P11-R1 | PS | none | - | extraction miss | E4 |
| P11-R2 | PS | #7 (exact) | S | audit miss | A1 |
| P11-R3 | NS | none | - | extraction miss | E5 |
| P12-R1 | NS | none (#0 is the R2 "learning opportunity" claim, not the asymmetry) | - | extraction miss | E1 |
| P12-R2 | NS | #0 (same claim, other sentence) | NS | HIT | |
 
(1) Judgment call. Prism extracted a sibling sentence carrying only the safe half of the claim
(P4-R3: #10; P3-R1: #6). The overreaching half was never extracted, so counted as extraction miss.
(2) #25 is a narrower math/coding claim, not the Table 10 title claim.
(3) Judgment call. #1 ("Across 17 teacher-student pairs ... outperforms OPD in 14 cases") carries the
17-pair count the rubric marks as overstated (15 distinct pairs), but not "most commonly used".
Counted as audit miss because #1 contains part of the overreach, not only the safe half.
(4) Judgment call. #7 ("This natural dynamic of use and disuse unifies the recovery of past
experience with learning...") asserts the disuse half that the paper's own appendix disclaims.
Counted as audit miss.
 
## Matcher errors found
 
- P3-R2: matcher #17, correct #3 (exact copy).
- P4-R1: matcher #9, correct #2. Verdict unchanged.
- P5-R1: matcher #32 (PS), correct #33 (S). FLIPS a draft hit into an audit miss.
- P5-R2: matcher no match, correct #1.
- P8-R2: matcher no match, correct #7.
- P9-R1: matcher #15, correct none (different quantity).
- P10-R2: matcher #9, correct #4 (exact copy). Verdict unchanged.
- Conclusion stands: the live LLM matcher is not reliable enough for official numbers; one error
  inflated the hit count. Official numbers come only from the adjudicated match map.
## Result (run 1, 12 papers, 31 refusal rows)
 
- Refusal hits: 8 / 31 (26%).
- Audit misses: 10. Extraction misses: 13. Grounding misses: 0.
- Auditor-only ceiling (perfect auditor, today's extractor): 18 / 31 (58%).
- Floor is 22 / 31 (70%). Pre-registered rule: hits + audit + grounding misses = 18 < 22, so the
  floor needs extractor work. Extraction misses 13 > 9.
- Judgment calls P5-R2 and P8-R2 do not change the conclusion (ceiling 16-18 either way).
## Failure patterns (confirmed on 12 papers)
 
Auditor (10 misses, all one pattern):
- A1: headline "consistent / every / across settings / count" claim contradicted by a specific table
  cell, a table's scope, or the paper's own caveat/appendix. The auditor accepts the headline and
  supporting text and does not search tables or appendices for counter-examples.
  Target of experiment 1 (thinking_level=high on the auditor).
Extractor (13 misses):
- E1 hedged / "in principle" / premise or mechanism claims (P7-R2, P2-R1, P1-R2, P12-R1): 4
- E2 table titles, captions and table-derived quantities (P2-R3, P2-R4, P9-R1): 3
- E3 overreach dropped, safer sibling kept (P4-R3, P3-R1, P5-R3, P8-R3): 4
- E4 method/setup statements not treated as claims (P11-R1): 1
- E5 unreported "we observed" statements (P11-R3): 1
## False-rejection check (Part B, draft)
 
- 37 Prism PS/NS claims on 12 papers (24 PS + 13 NS).
- 5 sit on dev rows labelled S by draft match: P1 #17 (grounding-demoted), P5 #9, P8 #26, P9 #2,
  P10 #19. P1, P8, P9, P10 are exact text matches.
- P5 #9 match to P5-S3 is weak (tsr 64.5, r 36.7): still to confirm.
- Draft false rejections: 4-5 / 88 S rows (4.5-5.7%), under the 10% cap. One is caused by grounding.
## Open items
 
- Confirm P5 #9 vs P5-S3.
- Positives (S-row hits) not adjudicated; needs the S-row match map for full coverage.
- Official fixtures: re-dump with --match-map after the map is written (no LLM call).
- Set the push rupee cap in decisions.md. AI Studio monthly cap has about INR 490 left until Nov 1;
  one 12-paper experiment costs about INR 1,050 and there is no audit-only rerun path.
- Ticket after the freeze: persist thinking setting, grounding model used, per-call cost; fix
  --dry-run so it skips the matcher call.
- P5 #9 vs P5-S3: confirmed not a match. Draft false rejections 4/88 (4.5%), one caused by grounding.