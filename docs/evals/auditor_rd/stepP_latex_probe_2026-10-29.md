# Step P - arXiv LaTeX probe (facts only)

## Readings

How the probe read its inputs (as built):

1. **S-row criteria (a) and (d) use `claim_fingerprint`.** `persisted_claim_id` is null for all 119 rows of
   `docs/evals/dev_match_map.json`. A row counts as matching a run-1 claim when `claim_fingerprint` is non-null
   and `confirmed_no_match` is false; two rows share a claim when their fingerprints are equal. This was changed
   after the first `select-s-rows` run, which used `persisted_claim_id` and matched 0 of 88 S rows. The results
   below are from the run with `claim_fingerprint`.
2. **Appendix table numbering is read as continuous.** Caption number = order of table captions in the resolved
   document; `\appendix` is recorded but does not restart or restyle the count. The "Problems" section lists every
   paper with `\appendix` and any `\thetable` / table-counter change found (none was flagged).
3. **Redirect rule.** A redirect is followed only if its target is https and its host is `arxiv.org` or ends in
   `.arxiv.org`. Any other target is refused, not followed, and not retried; the download record shows
   status `failed` with the redirect's HTTP status and the error `redirect outside arxiv.org refused (host: <host>)`.

Date: 2026-10-29. INR 0. No LLM, no pipeline or eval run. Source: arxiv.org/e-print for the 15 approved ids.
Pin check compares values only (Decimal equality of cell/token values); labels and structural pins are not checked.
A value match can be coincidental (small integers, repeated values); the check does not tie a value to a row or column.

## Downloads

| paper | id | status | http | bytes | sha256 (16) | format | source | rejected members |
|---|---|---|---|---|---|---|---|---|
| P1 | 2610.11519v1 | downloaded | 200 | 583891 | c42bc82d4250f8b7 | tar.gz | y | 0 |
| P2 | 2610.11132v1 | downloaded | 200 | 250118 | 0f49bf6d76477f60 | tar.gz | y | 0 |
| P3 | 2610.11135v1 | downloaded | 200 | 84202 | 91479e4c52e87fcd | tar.gz | y | 0 |
| P4 | 2610.10871v1 | downloaded | 200 | 231645 | eae8b45881dacc95 | tar.gz | y | 0 |
| P5 | 2610.11291v1 | downloaded | 200 | 1072099 | 5f80d3489fb9aeb1 | tar.gz | y | 0 |
| P6 | 2610.11312v1 | downloaded | 200 | 8061247 | 488151079279d710 | tar.gz | y | 0 |
| P7 | 2610.10590v1 | downloaded | 200 | 39020 | 63324d21d6372378 | tar.gz | y | 0 |
| P8 | 2610.12124v1 | downloaded | 200 | 792708 | 8a5276fca9a9a298 | tar.gz | y | 0 |
| P9 | 2610.12375v1 | downloaded | 200 | 37462 | fd931abe4f2b95b4 | tar.gz | y | 0 |
| P10 | 2610.12176v1 | downloaded | 200 | 419445 | ce7b40cf6cf2f198 | tar.gz | y | 0 |
| P11 | 2610.12114v1 | downloaded | 200 | 356737 | 277ab29a1f96b679 | tar.gz | y | 0 |
| P12 | 2610.12168v1 | downloaded | 200 | 36199 | 33bd21d21cf3d10d | tar.gz | y | 0 |
| reflexion | 2303.11366v4 | downloaded | 200 | 395034 | d70b771f527d912c | tar.gz | y | 0 |
| cot | 2201.11903v6 | downloaded | 200 | 313261 | 5f3a38e27058b534 | tar.gz | y | 0 |
| react | 2210.03629v3 | downloaded | 200 | 1286049 | c81c6344ddae91fc | tar.gz | y | 0 |

## Per paper

| paper | id | version | source | format | main file(s) | \input count | tables found | with multirow | with multicolumn | as image (includegraphics) | custom macros in tabulars |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 2610.11519 | v1 | y | tar.gz | main.tex | 43 | 31 | 4 | 12 | 0 | \CoRA, \RA, \begingroup, \cos, \dimexpr, \endgroup, \extracolsep, \fill, \langle, \log, \measuredtable, \modelgrouprule, \modelindent, \norm, \overline (+9) |
| P2 | 2610.11132 | v1 | y | tar.gz | iclr2027_conference.tex | 1 | 11 | 0 | 6 | 0 | \Consistency, \MAE, \Non, \extracolsep, \fill |
| P3 | 2610.11135 | v1 | y | tar.gz | main.tex | 50 | 42 | 1 | 31 | 0 | \JevZ, \cmark, \ps, \xmark |
| P4 | 2610.10871 | v1 | y | tar.gz | main.tex | 1 | 11 | 6 | 0 | 0 | \Debug, \Find, \KV, \Number, \PassKey, \avgcell, \basecell, \benchlabel, \best, \dash, \fullbblabel, \fullblocksep, \fullfirstsep, \fullfwlabel, \hhline (+22) |
| P5 | 2610.11291 | v1 | y | tar.gz | main_tech_report.tex | 12 | 4 | 0 | 4 | 0 | \cref, \else, \fi, \hf, \ifdim, \method, \normalfont, \width |
| P6 | 2610.11312 | v1 | y | tar.gz | main.tex | 31 | 14 | 10 | 12 | 0 | \clsresult, \cmidrulewidth, \hrule, \hsize, \path, \spresult, \vrule, \vskip |
| P7 | 2610.10590 | v1 | y | tar.gz | main.tex | 0 | 3 | 0 | 0 | 0 | \real |
| P8 | 2610.12124 | v1 | y | tar.gz | hippocam.tex | 43 | 13 | 0 | 4 | 0 | \dimexpr, \fboxsep, \hsize, \intextsep, \makebox, \min, \put, \relax, \sysname, \to, \unitlength |
| P9 | 2610.12375 | v1 | y | tar.gz | main.tex | 0 | 9 | 0 | 1 | 0 | \OtapS, \arg, \bar, \cos, \eqref, \leak, \max, \min |
| P10 | 2610.12176 | v1 | y | tar.gz | iclr2027_conference.tex | 8 | 15 | 0 | 6 | 0 | \cL, \mid, \oplus, \varnothing, \widehat |
| P11 | 2610.12114 | v1 | y | tar.gz | main.tex | 1 | 8 | 4 | 6 | 0 | \begingroup, \endgroup, \extracolsep, \fill, \parskip, \textcircled |
| P12 | 2610.12168 | v1 | y | tar.gz | preprint_hindsight_hierarchies.tex | 0 | 0 | 0 | 0 | 0 | - |
| reflexion | 2303.11366 | v4 | y | tar.gz | main.tex | 4 | 6 | 0 | 1 | 0 | \greencheck, \redcross |
| cot | 2201.11903 | v6 | y | tar.gz | neurips_2022.tex | 33 | 30 | 0 | 5 | 0 | \calc, \cell, \dataset, \diff, \hl, \jgr, \jred, \lamda, \palm, \stanchain, \xmark |
| react | 2210.03629 | v3 | y | tar.gz | iclr2023 2_arXiv/iclr2023_conference.tex | 23 | 28 | 3 | 6 | 1 | \act, \actA, \actB, \actC, \actD, \cellalign, \cotA, \cotB, \cotC, \cotD, \cotfp, \cothallucination, \cotlabel, \cotre, \cottp (+19) |
| react | 2210.03629 | v3 | y | tar.gz | iclr2023_conference.tex | 23 | 28 | 3 | 6 | 1 | \act, \actA, \actB, \actC, \actD, \cellalign, \cotA, \cotB, \cotC, \cotD, \cotfp, \cothallucination, \cotlabel, \cotre, \cottp (+19) |

## Gate tables

| gate table | found | caption (first 80) | multirow | pin values present x/y (all cell pins) | x/y (excluding key_uncertain) | missing pin ids |
|---|---|---|---|---|---|---|
| P1-T4 | y | The same teacher-peak branch slightly helps sampled OPD but lowers both students | n | 3/3 | 1/1 | - |
| P3-T9 | y | P2 (new learners), every cell. AUC by the position of the target in a new learne | n | 12/12 | 3/3 | - |
| P4-T1 | y | RULER hsieh2024ruler results under matched sparse-attention settings. Within eac | y | 15/15 | 7/7 | - |
| P4-T2 | y | InfiniteBench zhang2024bench results under matched sparse-attention settings. Wi | y | 3/3 | 2/2 | - |
| P4-T9 | y | Full RULER probe ablation. Clip p denotes norm clipping at percentile p, and Nor | n | 11/11 | 11/11 | - |
| P5-T3 | y | All 17 teacher--student pairs, sorted by AUC gain of over OPD. Model names link  | n | 0/0 | 0/0 | - |
| P6-T10 | y | Multiple-choice evaluation on BrEaST by task type. Results are reported as Accur | y | 0/1 | 0/1 | P6-T10-01 |
| P11-T3 | y | Comparison with KD methods under the Pro Qwen setting. | y | 6/6 | 6/6 | - |

Note: P6-T10 row above maps to the wrong table: caption-order position 10 is the BrEaST table; the PDF's Table 10
(ISIC dermoscopy, no BreastGPT row) is caption-order position 9, where the pin 44.5 / 53.3 is present via
\spresult. Caption-order numbering is off by one in P6 (cause not found). Numbering by caption order is therefore
not used to identify tables later; 6 of the other 7 gate tables are supported by all pin values present; P5 T3
has only structural pins (0/0 value pins), so its identity is not value-checked here and must be confirmed by
caption text in the T2-R reference-table builder.

## T2-R S rows (select-s-rows)

S rows: 88; (a): 67; (a,b): 58; (a,b,c): 29; (a,b,c,d): 28; selected: 10; criterion (c) relaxed: n.

| row id | paper | tables cited | found in LaTeX (table:y/n) | selected via | scope words | tables named in why_this_case (not used to select) |
|---|---|---|---|---|---|---|
| P1-S1 | P1 | 1 | 1:y | first-per-paper | across, all, both | - |
| P2-S2 | P2 | 1 | 1:y | first-per-paper | across | - |
| P3-S1 | P3 | 1 | 1:y | first-per-paper | any | - |
| P4-S1 | P4 | 1, 2, 3 | 1:y, 2:y, 3:y | first-per-paper | across, all, both | - |
| P5-S4 | P5 | 3 | 3:y | first-per-paper | across | - |
| P6-S1 | P6 | 1 | 1:y | first-per-paper | outperforming | - |
| P7-S2 | P7 | 1 | 1:n | first-per-paper | both | - |
| P8-S6 | P8 | 2 | 2:y | first-per-paper | both | - |
| P9-S4 | P9 | 6 | 6:y | first-per-paper | every | - |
| P11-S8 | P11 | 5 | 5:y | first-per-paper | every | - |

Shared-claim rows (pass a, b, c; fail d), reported apart:

| row id | paper | tables cited | found in LaTeX (table:y/n) | shares claim with |
|---|---|---|---|---|
| P5-S1 | P5 | 1, 3 | 1:y, 3:y | P5-R2 |

P7-S2: pending. Its Table 1 has no \caption in LaTeX. Replacement (next in order: P1-S2) applies only if the
T2-R reference-table builder cannot identify the table by content. Next rows in the existing order: P1-S2, P1-S3,
P1-S4.

## Multirow prevalence (papers with exactly one main file)

| set | tables with multirow / all tables |
|---|---|
| dev | 25/161 |
| golden | 0/36 |
| total | 25/197 |

## Problems

- P1 (2610.11519v1): numbering: \appendix present; 27 captioned table(s) after it, numbering taken as continuous
- P2 (2610.11132v1): numbering: \appendix present; 8 captioned table(s) after it, numbering taken as continuous
- P3 (2610.11135v1): numbering: \appendix present; 38 captioned table(s) after it, numbering taken as continuous
- P4 (2610.10871v1): numbering: \appendix present; 7 captioned table(s) after it, numbering taken as continuous
- P5 (2610.11291v1): numbering: \appendix present; 3 captioned table(s) after it, numbering taken as continuous
- P6 (2610.11312v1): numbering: \appendix present; 10 captioned table(s) after it, numbering taken as continuous
- P7 (2610.10590v1): numbering: 3 table instance(s) without \caption (not numbered): index [1, 2, 3]
- P8 (2610.12124v1): numbering: \appendix present; 9 captioned table(s) after it, numbering taken as continuous
- P8 (2610.12124v1): numbering: 2 table instance(s) without \caption (not numbered): index [1, 4]
- P9 (2610.12375v1): numbering: \appendix present; 1 captioned table(s) after it, numbering taken as continuous
- P10 (2610.12176v1): numbering: \appendix present; 13 captioned table(s) after it, numbering taken as continuous
- P11 (2610.12114v1): numbering: \appendix present; 5 captioned table(s) after it, numbering taken as continuous
- P12 (2610.12168v1): numbering: \appendix present; 0 captioned table(s) after it, numbering taken as continuous
- reflexion (2303.11366v4): numbering: \appendix present; 2 captioned table(s) after it, numbering taken as continuous
- reflexion (2303.11366v4): numbering: 1 table instance(s) without \caption (not numbered): index [1]
- cot (2201.11903v6): numbering: \appendix present; 30 captioned table(s) after it, numbering taken as continuous
- react (2210.03629v3): 2 main file(s): ['iclr2023 2_arXiv/iclr2023_conference.tex', 'iclr2023_conference.tex']
- react (2210.03629v3): numbering: \appendix present; 6 captioned table(s) after it, numbering taken as continuous
- react (2210.03629v3): numbering: 19 table instance(s) without \caption (not numbered): index [5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28]
- react (2210.03629v3): numbering: \appendix present; 6 captioned table(s) after it, numbering taken as continuous
- react (2210.03629v3): numbering: 19 table instance(s) without \caption (not numbered): index [5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28]

