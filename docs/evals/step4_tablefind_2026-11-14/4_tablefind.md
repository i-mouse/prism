# Table-finding check before step 4 (code only, INR 0) - result

Verdict: **PASS** - 5 of 5 rows ready (PASS needs >= 4).
Rule: block cap 12000 chars; a table needs >= 90% of the reference table's distinct values in the block. Ids, counts and y/n only; no paper text.

## Rows

| row | tables | ready |
|---|---|---|
| P1-R1 | P1-T4 | yes |
| P3-R2 | P3-T9 | yes |
| P4-R1 | P4-T1, P4-T2 | yes |
| P4-R2 | P4-T9 | yes |
| P11-R2 | P11-T3 | yes |

## Tables

| table | paper | caption lines | found | breaking cell pins present | ref values matched | pct | value test | usable | block chars | est. tokens (ESTIMATED) | cap hit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1-T4 | 2610.11519v1 | 1 | yes | 1/1 | 14/14 | 100.0 | yes | yes | 6870 | 1717 | no |
| P3-T9 | 2610.11135v1 | 1 | yes | 2/2 | 105/105 | 100.0 | yes | yes | 4562 | 1140 | no |
| P4-T1 | 2610.10871v1 | 1 | yes | 1/1 | 88/88 | 100.0 | yes | yes | 1102 | 275 | no |
| P4-T2 | 2610.10871v1 | 1 | yes | 2/2 | 92/92 | 100.0 | yes | yes | 4589 | 1147 | no |
| P4-T9 | 2610.10871v1 | 1 | yes | 4/4 | 82/82 | 100.0 | yes | yes | 1039 | 259 | no |
| P11-T3 | 2610.12114v1 | 1 | yes | 0/0 | 18/18 | 100.0 | yes | yes | 2462 | 615 | no |

## Breaking cell pins

| table | pin | value in block |
|---|---|---|
| P1-T4 | P1-T4-01 | yes |
| P3-T9 | P3-T9-01 | yes |
| P3-T9 | P3-T9-02 | yes |
| P4-T1 | P4-T1-01 | yes |
| P4-T2 | P4-T2-01 | yes |
| P4-T2 | P4-T2-02 | yes |
| P4-T9 | P4-T9-03 | yes |
| P4-T9 | P4-T9-04 | yes |
| P4-T9 | P4-T9-05 | yes |
| P4-T9 | P4-T9-06 | yes |

## Structural breaking pins (reported, not gated)

| table | pin | reported |
|---|---|---|
| P4-T9 | P4-T9-S1 | not checkable |
| P11-T3 | P11-T3-S1 | yes |

## Label coverage (reported, not gated)

| table | labels matched | pct |
|---|---|---|
| P1-T4 | 8/10 | 80.0 |
| P3-T9 | 18/18 | 100.0 |
| P4-T1 | 16/17 | 94.1 |
| P4-T2 | 19/20 | 95.0 |
| P4-T9 | 14/14 | 100.0 |
| P11-T3 | 11/11 | 100.0 |

## All-tables view (12 dev papers; reported, not gated)

| paper | tables mentioned | caption found exactly once | numbers not found exactly once |
|---|---|---|---|
| 2610.10590v1 | 3 | 3 | - |
| 2610.10871v1 | 11 | 11 | - |
| 2610.11132v1 | 11 | 11 | - |
| 2610.11135v1 | 42 | 41 | 12 |
| 2610.11291v1 | 4 | 4 | - |
| 2610.11312v1 | 15 | 15 | - |
| 2610.11519v1 | 31 | 30 | 1 |
| 2610.12114v1 | 8 | 8 | - |
| 2610.12124v1 | 13 | 13 | - |
| 2610.12168v1 | 0 | 0 | - |
| 2610.12176v1 | 15 | 14 | 12 |
| 2610.12375v1 | 9 | 8 | 2 |
