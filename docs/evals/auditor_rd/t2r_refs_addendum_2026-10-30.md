# T2-R refs addendum, 2026-10-30

C11 (P2-S2) got no check form. Replacement = next row in the existing order (a-b-c-d rows not in the original selection, by row id, skipping rows whose tables are unidentified). Existing builder code (t2r_build_refs.Builder, latex_table) used unchanged; no identification, parser or matching rule changed.

| row | paper | table | identified | matched PDF caption start | size | parse problems |
|---|---|---|---|---|---|---|
| P1-S8 | 2610.11519v1 | 30 | yes (LaTeX index 30, 1 PDF caption) | The adapted teacher is a worse solver than the frozen teacher. Qwen3-8B in non- | 7 rows x 9 cols, 1 part | none (no source problems) |

P2-S7 (Table 2 of 2610.11132v1) was not tried: P1-S8 succeeded, and the rule stops at the first success.

Outcome: P1-S8 became C18 (PDF file: 2610.11519v1.pdf), because it is the first row after the rows already used (P1-S2, P1-S3, P1-S6; P1-S4 skipped as unidentified) whose cited table is identified with no parse problem.

Files: t2r_refs/2610.11519v1_T30.json and .md; t2r_blind_pack/pack_C18_2610.11519v1.md; t2r_blind_key_addendum_2026-10-30.json (C18 -> P1-S8).
