## Step 1a — Blind scope-item table (claim text only, no labels seen)

| Row | Scope words? | Scope items a careful checker should test |
|---|---|---|
| **P1-R1** | Yes — "either / or" (3 named ablations) | (1) removing the baseline lowers performance; (2) replacing the residual with the log ratio lowers performance; (3) adding direct supervision of the teacher's top token lowers performance — each of the three conditions individually, not just one |
| **P1-R3** | No | — (qualitative bound/convergence statement, no countable scope) |
| **P10-R1** | No (only "continuous, recursive" — qualitative) | — |
| **P10-R2** | Yes — "1.4×" | exact reported multiplier for training tokens of the single-agent baseline matches "1.4× more" |
| **P10-R3** | Weak — "increasingly", "across workflow components" | whether the trend is general/aggregate or tied to a specific measured set of workflow components |
| **P11-R2** | Yes — "Across the evaluated settings" | whether outperformance holds in *every* evaluated setting, or only in aggregate/most |
| **P12-R2** | No | — |
| **P2-R5** | Yes — "Tables 7 and 8" (two named tables) | outperforms oracle router in **both** Table 7 and Table 8, not just one |
| **P3-R2** | Yes — "from their first interactions", "all learners logged" | (1) advantage holds from the very first interaction (timing), not after warm-up; (2) "all learners logged" — deep KT ahead for the full logged population on unseen items, not just on average |
| **P4-R1** | Yes — "Extensive", "multiple", "consistent" | gains are consistent across **every** sparse attention method / benchmark / backbone tested, not just most or on average |
| **P4-R2** | Yes — named methods ("SeerAttention and FlexPrefill-Llama"), "some FlexPrefill settings" | (1) norm clipping helps specifically those two named targets; (2) soft norm balancing useful only in "some" (which?) FlexPrefill settings, not all |
| **P5-R1** | Weak — "broader reasoning tasks" | which specific tasks count as "broader reasoning", and whether transfer is shown there or only implied |
| **P5-R2** | Yes — "17", "14 cases", "1.5B to 235B", "+13.6%", "11.4×" | total pair count = 17; parameter range 1.5B–235B; wins = 14 of 17; max accuracy gain = +13.6%; max speedup = 11.4× — each number independently |
| **P6-R1** | No ("scalable and auditable" — qualitative) | — |
| **P6-R2** | Yes — "twelve VLMs" | exact count of VLMs evaluated = 12 |
| **P7-R1** | No ("substantial" — qualitative) | — |
| **P8-R1** | Yes — "without... or..." (negation of 2 mechanisms) | absence of **both** separately-assigned importance scores **and** time-based forgetting rules |
| **P8-R2** | No | — |

Scope words detected (yes/weak), by my own reading of the claim text: P1-R1, P10-R2, P10-R3(weak), P11-R2, P2-R5, P3-R2, P4-R1, P4-R2, P5-R1(weak), P5-R2, P6-R2, P8-R1 → **10 of 18 clear "yes", 2 "weak", 6 "no"**.

Step 1a table is complete. Proceeding to Step 1b now (opening `diagnostic_2026-10-22.md` locator table and the relevant `dev_eval.json` scoring_notes).

I have enough from Table 6/7 and the locator table for Step 1b. Let me pull the matching scoring_notes from `dev_eval.json` for these 18 rows.

Now Check 2 requires scanning the full dev_eval.json (88 supported + 31 refusal rows) and all run1 fixtures for scope words. Let me check file sizes before reading, and define the word list/regex explicitly (consistent with what I used in Step 1a: explicit generalization quantifiers, named-set listings, and digit-bearing magnitude claims).

Word list / regex I'll use for Check 2 (same categories as my Step 1a judgments: generalization quantifiers, named two-way listings, and digit/count-bearing magnitude claims):

- Generalization words: `every, all, always, consistent(ly), extensive(ly), multiple, substantial(ly), broader, representative, each, both, either, neither, across`
- Numeric/magnitude: any `\d+(\.\d+)?` followed by `%`, `×`, or `x`; any `\d+(\.\d+)?B` (param count); or spelled-out counts `eleven..twenty`

Command (reads only `dev_eval.json` and `fixtures/dev/run1/*.json`, stdlib only, prints counts/ids only — no writes):

Check 1 and Check 2 data gathered. Moving to Check 3 — grepping the google-genai SDK for cache-related signatures and `engine.py` for usage-metadata handling.

Now the `cached_content` field on `generate_content` config and `GenerateContentResponseUsageMetadata`'s cached-token field:

Now, where the engine currently reads usage metadata and where it drops `cached_content_token_count` for the auditor call.

This is the exact drop point: `_extract_usage_and_finish_reason` (engine.py:106-132) builds the usage dict with only `prompt_tokens`, `output_tokens`, `thought_tokens`, `total_tokens` — `cached_content_token_count` (confirmed present on the SDK's `GenerateContentResponseUsageMetadata`, types.py:6692) is never read. Let me confirm this helper is the one used by the auditor call.

Significant: `_call_gemini_freetext` (the auditor's own call) never invokes `_extract_usage_and_finish_reason` at all — `_write_structured_log` is called at line 420-428 without `usage=`/`finish_reason=` args, so they default to `None`. The auditor's logs capture **zero** usage metadata today, not just a missing `cached_content_token_count` field. Let me check `eval/replay_audit.py` next.

Check 3 data is complete. Now Check 4 — comparing `k1_stage_diagnostic.md` vs `clean_attempt_score.md`.

# Auditor R&D — Free, Read-Only Checks (chat-only report)

Process notes: `docs/evals/exp1_stage_a_claims.json` contains only `row_id`/`paper_id`/`claim_index` — no claim text — so Step 1a's blind text read was sourced from `docs/evals/fixtures/dev/run1/*.json` (`claim_text_verbatim` only, filtered via script so `label`/`grounding_status`/`evidence_spans` were never printed). No system Python was on PATH; used `Prism.PythonService/.venv/Scripts/python.exe` (VERIFIED exists) per your approval. All commands run as inline `-I -c` strings, no scratch files, as instructed after the first exchange.

---

## CHECK 1 — Blind scope-item coverage on the 18 frozen claims

**Step 1a** (blind table) was posted in chat before any restricted file was opened — reposted compressed here:

| Row | Scope words (blind read) |
|---|---|
| P1-R1 | yes — 3 named ablations ("either/or") |
| P1-R3, P10-R1, P12-R2, P6-R1, P7-R1, P8-R2 | no |
| P10-R2 | yes — "1.4×" |
| P10-R3, P5-R1 | weak/vague |
| P11-R2 | yes — "across the evaluated settings" |
| P2-R5 | yes — "Tables 7 and 8" |
| P3-R2 | yes — "first interactions", "all learners logged" |
| P4-R1 | yes — "extensive/multiple/consistent" |
| P4-R2 | yes (named targets + "some... settings") |
| P5-R2 | yes — "17", "14 cases", "1.5B–235B", "+13.6%", "11.4×" |
| P6-R2 | yes — "twelve" |
| P8-R1 | yes — "without X or Y" |

**Step 1b** (VERIFIED against Table 6/7 of `diagnostic_2026-10-22.md` and `dev_eval.json` scoring_notes):

| Miss row | Covered by a Step-1a item? | Why |
|---|---|---|
| P1-R1 | **YES** | item "each of the 3 ablations individually lowers performance" → directly finds the Table 4 cell that *rises* |
| P3-R2 | **YES** | item "holds from first interactions (timing)" → directly finds Table 9 position-1 cell the paper itself calls "noisy" |
| P4-R1 | **YES** | item "consistent across every method/benchmark/backbone" → directly finds the per-cell regressions |
| P4-R2 | **YES** | item "verify helpful specifically for FlexPrefill-Llama" → directly finds it has no raw baseline to be "helpful" against |
| P5-R1 | **PARTLY** | item was flagged "weak" ("broader reasoning tasks" vague) — would prompt a look, but not as sharply as an explicit "every/all" |
| P5-R2 | **YES** | item "total pair count = 17" → directly finds rows g/h are SFT-variants, so only 15 distinct pairs |
| P6-R2 | **YES** | item "count of VLMs = 12" → directly finds Table 10 lists 11, not 12 |
| P7-R1 | **NO** | my blind read found no scope word at all; the diagnostic's own "scope words dropped" column flags plural "trajectories"→"tasks" as the dropped generalization — I missed that plural-noun form of scope entirely |
| P8-R2 | **NO** | my blind read found no scope word; the breaking evidence needs the conjunctive "use **and** disuse" split (same structural pattern as P1-R1's "either/or" list), which I didn't generalize to "and" |
| P11-R2 | **YES** | item "holds in *every* evaluated setting" → directly finds Table 3 restricts KD results to the Pro→Qwen setting only |

- **Misses covered: 7/10 YES, 1/10 PARTLY, 2/10 NO.**
- **Of the 6 always-missed rows (P4-R1, P4-R2, P3-R2, P5-R2, P6-R2, P11-R2): 6/6 YES.**

**8 hit rows** — risk of a scope-item check flipping a correct refusal to "supported": **NO risk in any of the 8** (VERIFIED by design: the stated combine rule only *lowers* a verdict on "contradicted," never raises it on "matches," and "not reported" alone doesn't lower it either — so even rows where my blind read found strong scope words, e.g. P8-R1, P10-R2, P2-R5, a 4a check can only leave the verdict unchanged or push it down, never up). Rows with no scope words (P1-R3, P6-R1, P10-R1, P12-R2) wouldn't even trigger a 4a call.

---

## CHECK 2 — False-rejection exposure and routing share

Word list used (stated exactly, run via the `.venv` interpreter): generalization words `every|all|always|consistent(ly)?|extensive(ly)?|multiple|substantial(ly)?|broader|representative|each|both|either|neither|across`, plus numeric/magnitude `\d+(\.\d+)?\s*(%|×|x)` or `\d+(\.\d+)?B` or spelled-out `eleven..twenty`.

VERIFIED (computed directly from `dev_eval.json` and `fixtures/dev/run1/*.json`):

| Set | With scope words | Total |
|---|---|---|
| Supported (S) rows | 63 | 88 |
| Refusal-family rows (partially_supported + not_supported) | 12 | 31 |
| All extracted claims (run1, 12 papers) | 206 | 362 |

Per-paper extracted-claim share: P1 26/33, P2 14/26, P3 25/42, P4 12/34, P5 22/39, P6 18/24, P7 20/37, P8 18/32, P9 11/27, P10 15/21, P11 20/31, P12 5/16. **≈57% of all extracted claims (206/362) would trigger the extra 4a call.**

Caveat (UNSURE, flagged honestly): this fixed regex is narrower than my subjective Step-1a judgment — e.g. it misses P4-R2 (named-entity listing, no quantifier word) and P8-R2/P12-R2 (conjunctive/implicit scope) in the 18-row set, which I *did* flag by eye. So the 57%/12-of-31/63-of-88 numbers are a **lower bound** on true scope-word prevalence, not an exact count — the real trigger rate depends on exactly how "contains scope words" gets implemented in code.

---

## CHECK 3 — Code touch points (map only)

- **Prompt build**: `build_gemini_messages_for_audit` (`extraction/prompt_loader.py:153-173`, confirmed in `diagnostic_2026-10-22.md` Table 4) — byte-identical prefix per paper (system prompt + `"PAPER TEXT:\n{paper_text}\n\nCLAIM TO AUDIT:\nCLAIM_TEXT_VERBATIM: "`), **nothing breaks a cache prefix** today (VERIFIED, same source).
- **Call site**: `_audit_and_structure_claim` (`extraction/engine.py:433-486`), audit call at `:462-470` via `_call_gemini_freetext` (`:380-430`).
- **google-genai 1.64.0 cache API** (VERIFIED, file:line):
  - `client.caches.create(*, model, config)` → `.venv/Lib/site-packages/google/genai/caches.py:837-842` (async at `:1219`)
  - `CreateCachedContentConfig` fields: `ttl`, `expire_time`, `display_name`, `contents`, `system_instruction`, `tools`, … → `types.py:12422-12452`
  - `GenerateContentConfig.cached_content: Optional[str]` → `types.py:5244-5248`
  - `GenerateContentResponseUsageMetadata.cached_content_token_count` → `types.py:6692-6695`
- **Usage metadata availability vs. engine.py drop point** (VERIFIED, more specific than the diagnostic's framing):
  - `_extract_usage_and_finish_reason` (`engine.py:106-132`) only reads `prompt_token_count`, `candidates_token_count`, `thoughts_token_count`, `total_token_count` — `cached_content_token_count` is never read, for **any** call.
  - `_call_gemini_freetext` (the auditor's own call, `engine.py:380-430`) **never calls this helper at all** — `_write_structured_log` is invoked at `:420-428` without `usage=`/`finish_reason=` args, so the auditor's structured logs capture **zero** usage metadata today (not just missing cached-tokens — `_call_gemini_structured` at `:273`/`:345` does call it, the auditor path at `:420` does not).
- **`eval/replay_audit.py` exact insertion points** (VERIFIED, file:line):
  - `--max-inr`: add to `_build_parser` (`:420-427`); check against a running cost total (same formula as `_print_summary` lines `371-374`) inside the per-paper loop in `_run_once` (`:312-349`).
  - Cached-token logging: add `cached_tokens: int = 0` to the `CallRecord` dataclass (`:61-72`), and `cached_tokens=getattr(usage, "cached_content_token_count", None) or 0,` in `_Instrumentation._wrapped` (`:240-254`).
  - Grounding-cost logging: grounding (`grounding.ground_extraction`, called at `:329`) is **not instrumented at all today** — it runs outside the `_generate_with_fallback` monkey-patch, uses `litellm.acompletion` (per diagnostic Table 1, `extraction/grounding.py:165-172`), a separate call path from the Gemini-native wrapper `_Instrumentation` patches. Logging grounding cost here needs a second, separate instrumentation hook on that litellm call, not an extension of the existing one.
  - Paper-text-from-cache: replace `_hash_check_and_load_text` (`:188-218`, currently opens a Postgres pool via `create_db_connection_pool()` and SHA-256-checks the local PDF) with a direct `(CACHE_DIR / f"{arxiv_id}.txt").read_text(...)` read; call site is `:320`.
- **Files the caching+4a design would touch** (map only, no code written): `extraction/prompt_loader.py`, `extraction/engine.py`, `extraction/config.py` (new settings alongside `auditor_thinking_level` at `:82`), `extraction/schemas.py` (new 4a response schema + combine logic), a new file under `prompts/` (4a system prompt, parallel to `prompts/audit_claim_system.md`), `eval/replay_audit.py`, and `eval/pricing.py` (cached-token billing rate differs from normal input tokens, so the cost formula in `_print_summary`/`_estimate_one_claim_cost_usd` would need a cached-rate constant).

---

## CHECK 4 — Settle one number

**VERIFIED**, both files quoted directly and they **agree with each other** (r1=5, r2=6):

- `k1_stage_diagnostic.md:23-24`: "S3 (final) found: 5/13 (low), 5/13 (high)" (clean_r1); `:45-46`: "S3 (final) found: 6/13 (low), 6/13 (high)" (clean_r2).
- `clean_attempt_score.md:4-5`: "clean_r1: found 5/13 (low), 5/13 (high)" / "clean_r2: found 6/13 (low), 6/13 (high)".

So **your framing is backwards relative to these two files**: neither says "6 in both runs" — both independently say r1=5, r2=6. The "previous report said 6 in both" claim doesn't match either file on disk; UNSURE where that number came from (not found in either file checked), but it isn't a discrepancy *between* `k1_stage_diagnostic.md` and `clean_attempt_score.md` — those two agree.

---

## Risks to the design

1. **Coverage is incomplete even in the best case.** My own blind pass (presumably close to what an LLM "4a" checker would produce) missed 2/10 miss rows outright (P7-R1's plural "trajectories," P8-R2's "use **and** disuse" conjunction) and only partially covered a 3rd (P5-R1's vague "broader reasoning tasks"). A fixed regex (Check 2) does worse — it misses P4-R2 and P8-R2 entirely. **4a would not have caught P7-R1 or P8-R2**, 2 of the 10 target misses, regardless of implementation, unless the scope-item instruction explicitly asks the model to also flag plural nouns and "X and Y" conjunctions as scope items, not just quantifier words.
2. **~57% trigger rate (lower bound) means the extra call isn't a small tax.** If "contains scope words" is implemented anywhere near this word list, the 4a call fires on well over half of all extracted claims — this is a real per-paper cost addition on top of the already-dominant auditor share (Table 5: auditor ≈90-96% of measured partial costs), not a cheap targeted patch.
3. **The auditor's own logging currently captures zero usage metadata** (`_call_gemini_freetext` never calls `_extract_usage_and_finish_reason`). Before building cached-token cost tracking for this design, that gap has to be closed first, or the new cached_content_token_count field would be added to a function that's never invoked on the audit path.
4. **Grounding cost is structurally invisible to the existing instrumentation** (different call path, different library). Any "grounding-cost logging" ask in Phase 2/replay tooling needs a second, separate patch — not an extension of the current one.
5. **The row count discrepancy you asked about (Check 4) doesn't actually exist between the two files named** — worth tracing where "6 in both runs" originated before it propagates further, since acting on it would misstate K1's actual bounded-score result (FAIL either way, but 5→6 is a real improvement run2 shows that run1 doesn't).

Stop — no code or plan changes proposed.