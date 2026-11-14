# Prism and the field: how claim checking performs today

Written 2026-11-14. Field figures are as reported by each source. Prism figures come from the project's recorded evaluation runs.

## 1. Why this document exists

Prism checks whether a research paper's own claims are backed by the paper's own evidence. This document puts Prism's measured results next to published benchmarks and live tools. It is the project's single reference for "how does Prism compare, and where does it fall short". Prism is an experimental system with measured weak points. It is not yet a reliable automatic auditor.

## 2. Two kinds of task

| Kind | What the system is given | What it must do |
|---|---|---|
| Easy: evidence handed over | One claim plus the right table or figure | Judge only |
| Hard: whole paper | The whole paper | Find the claims, find the evidence, then judge |

Prism does the hard kind, on plain text taken from PDFs. Scores from the two kinds cannot be compared directly, and different sources use different measures. Each row below names its measure.

Measures used:
- Recall: share of real problems the system finds.
- Precision: share of flagged items that are real problems.
- F1: one score combining precision and recall.
- Pair accuracy: share of claim pairs where both versions are labelled correctly.
- Balanced accuracy: accuracy that gives equal weight to each class.

## 3. Field results: easy task (evidence handed over)

| Source | Data | Result | What to know |
|---|---|---|---|
| SciClaimEval (LREC 2026) | 1,664 claims, 180 papers | Baseline o4-mini: 68.2 pair accuracy (development set). Best single-claim accuracy on tables: about 87 (development set) | Refuted cases are made by editing the table or figure, not by real author overclaims |
| SciTrue, winning team (NTCIR-19, 2026) | SciClaimEval | 98.4 pair accuracy on the official test | Most of the gain comes from the pairing in the data: each claim appears twice (real and edited evidence), and comparing the two versions alone raised development pair accuracy from 72.2 to 93.5. It is not a measure of general auditing skill |
| SciLens (2026) | 747 SciClaimEval development cases | 30B open model. Tables: 80.6 to 81.7 F1, 62.7 to 67.4 pair accuracy. Figures: 66.6 to 74.3 F1, 38.8 to 54.3 pair accuracy. Overall: 76.0 to 79.2 F1, 54.8 to 63.1 pair accuracy | Splits each claim into parts and checks each part against the evidence. Larger gains on figures than tables. About 26K to 53K generated tokens per case |
| SciTab (EMNLP 2023) | 1,225 claims | All models except GPT-4 barely above random. Best open model 63.62 F1 (2-class). Humans 92.46 (2-class), 84.73 (3-class) | Reading scientific tables is hard even when the table is given |
| MiniCheck (EMNLP 2024) | 13K general test cases | 74.7 balanced accuracy, about GPT-4 level | A small fine-tuned checker, over 400 times cheaper than GPT-4 at inference. A possible component, not a paper auditor |
| Fine-tuning example inside SciTrue (2026) | SciClaimEval | QLoRA on Qwen2.5-VL-7B: 77.8 to 84.7 pair accuracy | Fine-tuning helps; still below the best large-model system |

## 4. Field results: hard task (whole paper)

| Source | Data | Result | What to know |
|---|---|---|---|
| SPOT (2025) | 83 papers, 91 known errors serious enough for corrections or retractions | Best model (o3): 21.1% recall, 6.1% precision, averaged over 8 runs | Targets serious errors (for example maths and figure errors), not overclaims. Not directly comparable with Prism |
| CLAIMCHECK (EMNLP Findings 2025) | 41 NeurIPS papers, 154 disputed claims | Frontier models below human experts | The disputed claim is given; the system does not find claims itself |
| PRISMM-Bench (ICLR 2026) | 384 inconsistencies, 353 papers | Best model 53.9%, open models about 40%, averaged over three multiple-choice tasks | Multiple choice, so random guessing already scores about 25% |
| Black Spatula Project (live tool) | About 500 papers | About 10% false alarms, as reported by the project | Reported figure, not a standard measured rate. 15 cents to a few US dollars per paper |
| YesNoError (live tool) | Over 37,000 papers in two months | An outside researcher reported 14 false alarms among 40 flagged papers | Small sample, reported in the press; not a standard rate |

## 5. Prism's measured results (hard task, 12 hand-labelled papers)

Test set: 31 bad claims and 88 good claims.

### 5.1 Where bad claims are lost

| Stage | Result |
|---|---|
| Bad claims in the test set | 31 |
| Found by the extractor | 18 of 31 (13 never extracted) |
| Caught by the auditor, of those found | 8 of 18 (10 judged as supported) |
| Caught, whole job | 8 of 31 |

Both stages lose claims. Extra extraction alone does not help yet: when the auditor was given 7 bad claims that a second extraction pass had recovered, it caught 2 of 7, with the same labels in all 3 runs.

### 5.2 Bad claims by kind (only where recorded)

The 10 auditor misses, by failure type:

| Type | Count |
|---|---|
| Table number breaks the claim | 2 |
| Claim wider than the cited table | 3 |
| Meaning of the claim | 2 |
| Caveat stated in the text | 2 |
| Figure | 1 |

The 13 extraction misses, by paper section: introduction 2, conclusion 3, body 5, appendix 3. Their kind (table, text, figure) is not recorded. The kind of the 8 caught claims is not recorded.

### 5.3 Good claims

| Measure | Result |
|---|---|
| Good claims wrongly rejected, recorded baseline run | 4 of 88 |
| Same run, counting only good claims the extractor found | 4 of 67 (21 good claims were never extracted, so they could not be rejected) |
| A later fresh run of the same setup | 1 of 88 |

### 5.4 Other recorded numbers

| Measure | Result |
|---|---|
| Golden set: bad claims caught | 5 of 16 |
| Golden set: good claims confirmed | 11 of 21 |
| Cost per paper, today (estimate) | About INR 102 |
| Cost per paper at 2027 list prices (estimate) | About INR 196, because Gemini Flash list prices double on 2027-01-01 |

### 5.5 How sure these numbers are

- One bad claim is about 3 points out of 31.
- Re-running the same setup gave 8, 7 and 5 of 31, so small changes can be noise. Later checks use 3 runs per setup.
- For 8 of 31, the 95% range is roughly 14% to 43%.

## 6. What Prism's own tests show

- The auditor often trusts summary sentences over the table numbers.
- Some misses are about what a claim means, which better reading alone does not fix.
- Clean-table test: tables were built from arXiv LaTeX source and checked against the PDFs, with hand-written checks, under pre-registered marks. Code fixed 4 of 10 auditor misses; of 10 good claims tested, none was rejected and 2 were sent to Needs review. This is a ceiling, never a Prism score.
- Standard PDF table tools read only 5 of 8 test tables correctly. Finding and reading the right table in a PDF is a main unsolved step.
- Stricter judging, including stronger models, caught more bad claims but also rejected more good claims. No auditor change has passed the project's no-regression rule.

## 7. What the field tells us

1. When the right evidence is handed over, top models do well. Finding the evidence in a whole paper is the hard part.
2. The very top easy-task score (98.4) depends mainly on the pairing in that dataset, not on general skill.
3. Splitting a claim into parts helps, more on figures than tables, and costs many tokens.
4. Small fine-tuned checkers can be far cheaper, but they only judge; they do not find claims or evidence.
5. Whole-paper tools still need human experts to confirm each flag.

## 8. Where Prism is, and what comes next

| | Now | Next expected | Release bar |
|---|---|---|---|
| Bad claims caught (dev) | 8 of 31 | 9 to 11, if the table checker test passes (estimate) | 22 of 31, under review |
| Cost per paper, 2027 prices | About INR 196 (estimate) | Must stay at or below INR 200 | At or below INR 200 |

Planned outside measurements (step 5, only if the table checker passes on the dev set):
- SciTab sample: judging with the table given, scored the same way as the field.
- SciClaimEval Supported table claims: good claims wrongly rejected.
- PRISMM-Bench table-text cases (about 46): bad claims caught.

No release with the current auditor.

## 9. Limits of this comparison

- Each source uses its own task, data and measure. Rows are context, not rankings.
- Live-tool figures come from press reports, not standard tests.
- Prism's test set is small: 31 bad claims from 12 papers.
- No public dataset matches Prism's exact task: real overclaims, expert labels, text-only evidence.

## 10. Sources

- SciClaimEval: https://arxiv.org/abs/2602.07621
- SciTrue (NTCIR-19 SciClaimEval): https://arxiv.org/pdf/2609.00654
- SciLens: https://arxiv.org/pdf/2606.20873
- SciTab: https://arxiv.org/pdf/2305.13186
- MiniCheck: https://arxiv.org/abs/2404.10774
- PRISMM-Bench: https://arxiv.org/abs/2510.16505
- SPOT: https://arxiv.org/abs/2505.11855
- CLAIMCHECK: https://arxiv.org/pdf/2503.21717
- Black Spatula and YesNoError (news report): https://heise.de/-10321469
- YesNoError false alarms (news summary of the Nature report): https://news.hada.io/topic?id=19634
