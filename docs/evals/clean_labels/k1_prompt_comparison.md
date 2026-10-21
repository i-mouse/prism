# K1 recall comparison: exp3 OLD pass-2 prompt vs clean attempt's NEW v2 prompt

**EXPLORATORY - not a mark.**

## Interpretation rule (fixed before running)
The v2 prompt lost recall on these rows if OLD S1 >= NEW S1 + 2 in BOTH pairings at the LOW bound. Otherwise, no clear recall loss from the prompt change. The high bound is reported alongside and never changes this rule.

## Confound check
Confound check: same model (gemini-3.6-flash) both sides; both sides ran pass-2 with thinking LOW (decisions.md: Experiment 3 amendment 1, 2026-10-15; run settings 2026-10-19), consistent with thought-token counts exp3 pass2_r1=9,234, exp3 pass2_r2=7,713, clean clean_r1=13,947, clean clean_r2=13,961 (total pass-2 thought tokens per run). Thinking level is not stored in fixture headers (logging gap).

## pass2_r1 (old) vs clean_r1 (new)
### low bound
| stage | old | new |
|---|---|---|
| s0 | 0 | 0 |
| s1 | 6 | 5 |
| s2 | 6 | 5 |
- found by old, not new (S1): P11-R3(E5), P7-R2(E1)
- found by new, not old (S1): P4-R3(E3)
### high bound
| stage | old | new |
|---|---|---|
| s0 | 0 | 0 |
| s1 | 6 | 5 |
| s2 | 6 | 5 |
- found by old, not new (S1): P11-R3(E5), P7-R2(E1)
- found by new, not old (S1): P4-R3(E3)

## pass2_r2 (old) vs clean_r2 (new)
### low bound
| stage | old | new |
|---|---|---|
| s0 | 0 | 0 |
| s1 | 6 | 6 |
| s2 | 6 | 6 |
- found by old, not new (S1): P11-R3(E5), P2-R1(E1)
- found by new, not old (S1): P2-R3(E2), P4-R3(E3)
### high bound
| stage | old | new |
|---|---|---|
| s0 | 0 | 0 |
| s1 | 6 | 6 |
| s2 | 6 | 6 |
- found by old, not new (S1): P11-R3(E5), P2-R1(E1)
- found by new, not old (S1): P2-R3(E2), P4-R3(E3)

## 7 stable rows found in both of each side's own runs (S1)
- low bound: old=5/7, new=4/7
- high bound: old=5/7, new=4/7

## Rule outcome
- low bound: deltas=[1, 0] -> no clear recall loss from the prompt change
- high bound: deltas=[1, 0] -> no clear recall loss from the prompt change
