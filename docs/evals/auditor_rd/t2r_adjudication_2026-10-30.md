# T2-R adjudication, 2026-10-30

Final check forms: `t2r_forms_final_2026-10-30.json` (17 items, C11 excluded: no form, replaced by C18).

## Files used

- 2610.10871v1: ChatGPT 2610.10871v1_chatgpt.txt [ok]; Gemini 2610.10871v1_gemini.json [ok]
- 2610.11132v1: ChatGPT 2610.11132v1_chatgpt.txt [ok]; Gemini 2610.11132v1_gemini.json [ok]
- 2610.11135v1: ChatGPT pack_2610.11135v1_chatgpt.txt [ok]; Gemini 2610.11135v1_gemini.json [ok]
- 2610.11291v1: ChatGPT pack_2610.11291v1_chatgpt.txt [ok after curly-quote repair]; Gemini 2610.11291v1_gemini.json [ok]
- 2610.11312v1: ChatGPT pack_2610.11312v1_chatgpt.txt [ok]; Gemini 2610.11312v1_gemini.json [ok]
- 2610.11519v1: ChatGPT pack_2610.11519v1_chatgpt.txt [ok]; Gemini 2610.11519v1_gemini.json [ok]
- 2610.12114v1: ChatGPT 2610.12114v1_chatgpt.txt [ok]; Gemini 2610.12114v1_gemini.json [ok]
- 2610.12124v1: ChatGPT pack_2610.12124v1_chatgpt.txt [ok]; Gemini gemini_2610.12124v1_medium.json [ok]
- 2610.12375v1: ChatGPT pack_2610.12375v1_chatgpt.txt [ok]; Gemini gemini_2610.12375v1_medium.json [ok]
- chatgpt_C18.json: ok
- gemini_C18.json: unparsable (Unterminated string starting at: line 206 column 5 (char 574); 3 complete forms salvageable
- wording_chatgpt.json: ok
- wording_gemini.json: ok

## Per item

### C01 (2610.11135v1)
- Judge forms used: Both judges (narrow Mean form).
- Decision: C01 (2610.11135v1 T9): the "narrow" Mean form (both judges): pairs "<block> > JevKT" vs "<block> > Best deep KT†" for the 6 Position blocks, column Mean, higher, strict. partial true. Member "unseen items, all learners logged (P3)" -> other_table: Table 10. Caveat: Table 9 caption "Position 1 has only 41–50 targets per dataset, so its AUC is noisy".
- Forms in output: 1; caveat_refs: 1.

### C02 (2610.11519v1)
- Judge forms used: ChatGPT round-2.
- Decision: C02 (2610.11519v1 T2): ChatGPT round-2 forms: (A) Full RA, w/o student value baseline, w/o response centering, Raw residual each beats "Verifier only (REINFORCE++)" on the 6 weight columns; (B) Full RA beats each of w/o student value baseline, w/o response centering, Raw residual, Direct L2 loss, Verifier only on the 6 columns. No caveats.
- Forms in output: 2; caveat_refs: 0.

### C03 (2610.12124v1)
- Judge forms used: ChatGPT round-2.
- Decision: C03 (2610.12124v1 T2): ChatGPT round-2 forms: Hippocam all_cmp > 0 and ACE all_cmp > 0 on both "Δ stream" columns; HiAgent, mem0, A-Mem, Letta, ReasoningBank each count_satisfying at least 1 of the 2 Δ stream cells <= 0. Plain excluded (no Δ values). No caveats.
- Forms in output: 7; caveat_refs: 0.

### C04 (2610.10871v1)
- Judge forms used: ChatGPT round-2 form, with Nitin's existence checks.
- Decision: C04 (2610.10871v1 T9): count_satisfying at least 1 of 3 comparisons: SeerAttention rows with Clip p 85, 90, 95 (Norm α –) each compared on Avg. against {Setting: SeerAttention, Clip p: –, Norm α: –}, higher, strict (count_satisfying with a baseline cell instead of a constant). Members: "norm clipping vs raw MASA for FlexPrefill-Llama" -> absent (Nitin checked Tables 4, 9, 10: no raw FlexPrefill-Llama row); "soft norm balancing in FlexPrefill settings" -> other_table: Table 10. partial true. No caveats.
- Forms in output: 1; caveat_refs: 0.

### C05 (2610.11312v1)
- Judge forms used: No form (wording judges).
- Decision: C05 (2610.11312v1 T10): no form (wording judges: "twelve VLMs" refers to the main evaluation). Member "twelve VLMs incl. BreastGPT-8B" -> other_table: Table 3. no_rule_reason: portability and variation claims are qualitative.
- Forms in output: 0; caveat_refs: 0.

### C06 (2610.10871v1)
- Judge forms used: ChatGPT forms widened to every column (Nitin).
- Decision: C06 (2610.10871v1 T1, T2): reading (b) every column (Nitin). T1: beats_baseline MASA vs Original for MInfer, SeerAttn, FlexPrefill>Llama, FlexPrefill>Qwen on 4K, 8K, 16K, 32K, 64K, 128K, Avg. T2: same for MInfer, FlexPrefill>Llama, FlexPrefill>Qwen on En.Sum ... Retr. KV and Avg. ΔFull excluded; Full Attention rows excluded. Members: LongBench (SeerAttention) -> other_table: Table 3; latency -> other_table: Figure 2. No caveats.
- Forms in output: 2; caveat_refs: 0.

### C07 (2610.11312v1)
- Judge forms used: ChatGPT forms; Gemini claimed group (adds All criteria).
- Decision: C07 (2610.11312v1 T1a, T1b; T1b is the PDF's Table 2): T1a: MedBenchAgent "Task-Space Review > F1↑" == 90.9 (tol 0.05); MedBenchAgent beats each of DeepSeek-V4-Flash, Qwen3.5-9B, MedGemma-27B, DeepSeek-V4-Flash + T0 on that column; the 3 direct baselines >= 79.2 and <= 80.0 (tol 0.05); "DeepSeek-V4-Flash + T0" == 85.1 (tol 0.05). T1b: "All criteria" Pass == 994 and Fail == 6 (tol 0.5). partial true ("correctly identified tasks" not encodable). No caveats.
- Forms in output: 7; caveat_refs: 0.

### C08 (2610.12375v1)
- Judge forms used: Both judges agree.
- Decision: C08 (2610.12375v1 T6): row 0.60: "Cost saved" == 18 (tol 1); "Prec. (dep.)" == 83 (tol 0.5). Caveat: Sec 6.3 "0.60 is an illustrative threshold selected for exposition after the sweep".
- Forms in output: 2; caveat_refs: 1.

### C09 (2610.11291v1)
- Judge forms used: Gemini forms (ChatGPT file malformed).
- Decision: C09 (2610.11291v1 T3): count_rows == 17 (all data rows); count_rows of distinct Mode == 2. partial true. "most commonly used" is not a member.
- Forms in output: 2; caveat_refs: 0.

### C10 (2610.11135v1)
- Judge forms used: Both judges.
- Decision: C10 (2610.11135v1 T1): rows_by_columns {N: 0, Method: Jev0-shot}, column Avg, all_cmp == .706 (tol 0.0005).
- Forms in output: 1; caveat_refs: 0.

### C12 (2610.11291v1)
- Judge forms used: Gemini form (ChatGPT file malformed).
- Decision: C12 (2610.11291v1 T3): count_rows == 17. partial true (correlation not encodable).
- Forms in output: 1; caveat_refs: 0.

### C13 (2610.11519v1)
- Judge forms used: ChatGPT forms; both wording judges: all methods.
- Decision: C13 (2610.11519v1 T4, T2): T4: all_cmp < 0 on rows "Δ macro Avg@8" and "Δ macro Pass@8", all 7 columns (both wording judges: all methods). T2: Full RA beats "w/o student value baseline" and "w/o response centering" on the 6 columns. Member "log ratio" -> other_table: Table 3. Caveat: Table 4 caption "slightly helps sampled OPD but lowers both students trained with the verifier". partial true.
- Forms in output: 2; caveat_refs: 1.

### C14 (2610.12114v1)
- Judge forms used: ChatGPT form.
- Decision: C14 (2610.12114v1 T3): beats_baseline UTT (Ours) vs SeqKD, Fine-tune-CoT, RSR, LUFFY on the 3 columns; Student excluded. Members: prompt-engineering methods -> other_table: Table 2; "KD methods in evaluated settings other than Pro→Qwen" -> absent (Nitin checked Tables 3, 6). Caveat: Table 3 caption "under the Pro→Qwen setting". partial true.
- Forms in output: 1; caveat_refs: 1.

### C15 (2610.11519v1)
- Judge forms used: ChatGPT forms.
- Decision: C15 (2610.11519v1 T10): the 4 "RA+X - OPD" rows (1.7B, 4B x REINFORCE++, GRPO) all_cmp > 0 on Δ Avg@8 and Δ Pass@8; the 4 "Co-RA+X - RA+X" rows Δ Avg@8 >= 1.0 and <= 1.5 (tol 0.05). No caveats.
- Forms in output: 3; caveat_refs: 0.

### C16 (2610.10871v1)
- Judge forms used: ChatGPT forms.
- Decision: C16 (2610.10871v1 T1, T2, T3): beats_baseline MASA vs Original on Avg.: T1 4 pairs, T2 3 pairs, T3 1 pair. Full Attention excluded.
- Forms in output: 3; caveat_refs: 0.

### C17 (2610.11519v1)
- Judge forms used: ChatGPT bound forms plus the > 0 form added per decision.
- Decision: C17 (2610.11519v1 T10): the 4 "RA+X - X" rows: Δ Avg@8 > 0, >= 1.7, <= 3.6; Δ Pass@8 > 0, >= 3.9, <= 6.3 (tol 0.05). Member "24 benchmark-level comparisons" -> other_table: Table 1. partial true.
- Forms in output: 5; caveat_refs: 0.

### C18 (2610.11519v1)
- Judge forms used: Both judges (ChatGPT file used; Gemini file truncated).
- Decision: C18 (2610.11519v1 T30): beats_baseline "Frozen q0" vs each of the 4 Adapter rows on "Macro > Avg@8" and "Macro > Pass@8" (narrow, macro). Member "student improvement" -> other_table: Table 1. Gap range not encodable (arithmetic). partial true.
- Forms in output: 1; caveat_refs: 0.

## Decisions by Nitin

- C06 = (b) every column (wording only).
- C14 KD other settings = absent (Tables 3, 6).
- C04 FlexPrefill-Llama raw comparison = absent (Tables 4, 9, 10).
- C03 ChatGPT encoding accepted (logically equivalent).
- Caveats: strict rule (both judges cite it and it limits scope). Only C01, C08, C13, C14 keep a caveat; all others caveat_refs = [].

## Notes

- Gemini final answers ran Argon at medium thinking.
- 2 Flash-Lite answers (2610.12124v1, 2610.12375v1) were replaced by the Gemini re-runs.
- The adjudicator could infer item identities, so readings were set by blind wording judges and Nitin.
- Nitin saw table values only for existence checks (C04, C14), not for C06.

## Validation

- Items 17, forms 41, pins checked 361; every row/column/selector pin resolves uniquely via table_keys tiers; problems: none.
- Relaxed glyph pins: none.
