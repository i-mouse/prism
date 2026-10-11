**Boundary notes, read before the report:**
- **Placeholder not filled in.** Your prompt still has `<SEALED_PATHS>` as a literal placeholder. I treated as sealed every held-out file, held-out run, `logs/` (it mixes held-out and golden runs) and `prism-evidence\`.
- **Sealed names I saw.** I opened no sealed content. But listing `docs/evals` showed the file names `heldout_eval.json` and `heldout_match_map.json`, and `git branch -a` showed the branch name `eval/heldout-paper`. I saw names only.
- **Golden PDF pages not read.** Rendering PDF pages needs poppler, which isn't installed. Running Python to read them would break the "no scripts" rule. So the PDF checks are marked not checked.
- **Git use.** I ran only the read-only git commands you allowed. PRISM_STATUS has a rule "CC never runs git", so I'm noting the conflict.

---

## 0. Divergences

| Item | Your snapshot | What I found |
|---|---|---|
| False rejections | 0/21 | **1/21** (COT-M01) [HISTORICAL PRISM_STATUS.md:20,35] |
| Exp 1 archive | branch `exp/1-scoped-auditor` | No such branch; it is a **tag**, `archive/exp1-scoped-auditor` [VERIFIED git tag -l] |
| Stop rule | in force | Matches PRISM_STATUS / decisions.md:1614. But FINDINGS.md:53 says "Decision 9 Oct: stop core changes; ship with honest numbers". That decision is not recorded in decisions.md |
| Prior diagnosis | auditor narrows scope | FINDINGS.md:31 says "5 of 6 wrongly affirmed", but only 4 rows are wrongly affirmed now. decisions.md:1607 says only **REACT-M14** is a clear auditor mistake, and withdraws "the auditor is the main lever" |
| `--estimate` | assumed on main | Only on the tag `archive/exp1-scoped-auditor` (`eval/exp1_replay.py`, $0.75 in / $3.75 out per 1M tokens, ₹95/$, prices unverified) [VERIFIED git diff] |
| Models | 3.6 Flash for extraction and audit | True, and the structurer also uses it. The grounding judge is Groq gpt-oss-20b, which fails, so **gemini-3.1-flash-lite** does that work in practice [HISTORICAL PRISM_STATUS.md:58] |
| Held-out | used 6× | Confirmed. It also has only **2 refusal rows**, and 9 rows rest on 4 claims [HISTORICAL PRISM_STATUS.md:21,39] |

## 1. Current reality

**Q1a — scope policy for the labels: unwritten.** Only fragments exist:
- decisions.md:24 has the rule "wording gap → partial only if it makes the claim stronger than the evidence".
- decisions.md:1265 has the rule "change a label only where the paper contradicts it".
- matrix_eval.json metadata and eval-harness-design.md:13 define the metric, not a label rubric.

The labels follow an implicit policy [VERIFIED matrix_eval.json]:
- A subset loss the claim doesn't carve out is labelled **partially_supported**, never not_supported (REFLEX-M08, COT-M02/M07/M09, REACT-M11/M13/M14).
- A comparison or generalization that was never tested is labelled not_supported.
- COT-M12 breaks the hedge policy from 10-01: it is hedged ("potentially … in principle") but still labelled not_supported.

**Q1b — positives that a "subset loss ⇒ not supported" rule would break:**
- **REACT-M10** ("consistently outperform CoT-SC across different number of samples"). The hand check found both hybrids above CoT-SC only "after n=1" [HISTORICAL decisions.md:1312]. The n=1 point isn't carved out, yet the row is labelled supported.
- **COT-M04** ("all sets … outperform … by a large margin"). It is scored on GSM8K only, but the robustness tables cover more datasets. Not checked: I couldn't render PDF pages.
- **REFLEX-M01 vs REFLEX-M09** is a different kind of inconsistency. M01 is supported using the 80% GPT-4 baseline. M09 is partial partly because the paper also states 82% for that same baseline.

REACT-M10 and COT-M04 are both among the 7 fragile hits. **Flipping both breaches the floor of 10.** Safe positives that carve out their losses: REACT-M05, REACT-M08, COT-M05.

**Q1c — the existing failure map plus one new column:**

| Row | Type | Label contestable? |
|---|---|---|
| REFLEX-M09 | D | **yes**: Table 1 gives +10.9 ≈ 11%; "partial" rests on the paper's own conflicting baseline; confidence 0.65 |
| REFLEX-M13 | C | **yes**: the verbatim text only says "we propose"; "arbitrary agents" appears only in the summary |
| COT-M08 | D | label no, **pairing yes**: extracted claim 22 keeps "sufficient scale", so supported is right [VERIFIED fixture cot:572] |
| REACT-M14 | D | no: Section 3.3 says ReAct prompting is worst on PaLM-8B/62B |
| COT-M07 | A | no (one cell in a table the claim cites) |
| COT-M10 | A | **yes**: hedged "can … sufficiently large"; Appendix A.2 narrows the wording, not a result |
| COT-M11 | A | no (also unmatchable because of the ellipsis) |
| COT-M12 | A | **yes**: explicit hedge, conflicts with the 10-01 hedge policy |
| REFLEX-M11 | B | **yes**: the comparison exists only in the summary |
| COT-M09 | B | no (mild) |
| REACT-M12 | B | no (unmatchable) |

So 5 of 11 labels are contestable, plus 1 doubtful pairing. **Only REACT-M14 is a clean auditor miss.**

**Q1d — interval arithmetic:**
- Your Wilson intervals are correct: 5/16 → 14.2–56.0%, and 11/21 → 32.4–71.7%.
- **Smallest detectable change** on the same 16 rows (exact McNemar test) is **≥6 rows moving in one direction with zero reverse flips**, i.e. 5/16 → 11/16. Compared as two separate samples, it's about +7 rows.
- Identical code already flips about 3 rows between runs [HISTORICAL decisions.md:1127-1134].
- Only 9 of the 16 rows ever reach the auditor.
- **The golden set cannot detect any auditor change smaller than a near-total fix.**

**Q2 — runtime config for each LLM call.** The extractor, auditor and structurer calls retry 3× with 1/2/4 s backoff, then make one fallback attempt.

| Call | Model → fallback | API / SDK | Thinking | Sampling | Schema | Max output |
|---|---|---|---|---|---|---|
| Metadata | 3.6-flash → 3.1-flash-lite | generateContent, google-genai 1.64.0 | none set | none | yes | unset |
| Extractor | same | same | none set | none | JSON mode, no schema | unset |
| **Auditor** | `LLM_CLAIM_AUDIT_MODEL` 3.6-flash → 3.1-flash-lite | same | **none set → API default (medium on 3.6)** | none | none (free text) | unset |
| Structurer | same variable as the auditor | same | none | none | `ClaimLLM` | unset |
| Grounding judge | groq gpt-oss-20b → gemini-3.1-flash-lite | LiteLLM 1.98.0 | n/a | temperature=0 | yes | **512** |
| Chat / router | 3.6-flash / 3.5-flash-lite | langchain-google-genai 4.2.1 | none | none | n/a | unset |
| Eval matcher | 3.6-flash → fallback | generateContent | none | **temperature=0 (ignored on 3.6, a silent no-op)** | yes | unset |

Sources: [VERIFIED engine.py:191-195, 257-260, 315-317, 367-382; grounding.py:165-172; matcher.py:155-160; agent.py:165-173; AppHost.cs:155-163; uv.lock].

Flags:
- There is no `thinking_budget` anywhere in the code.
- **Silent fallback:** any retryable error drops the call to flash-lite [VERIFIED engine.py:152-161]. This shows only in the per-call logs. The fixture header stamps the env var `LLM_EXTRACTION_MODEL`, not the model that actually ran [VERIFIED dump_fixture.py:348].
- **No finish_reason check:** if an auditor reply is truncated or empty, the structurer still has to emit a label (the schema forces one).

## 2. Root causes, ranked

1. **The instrument, not the auditor** [VERIFIED Q1]. 7 of 16 rows are never extracted. 3 of the 4 wrongly-affirmed rows are label or pairing problems. The smallest detectable change is about 6 rows.
2. **Extractor recall and variance** [HISTORICAL]. About 9 of 16 refusal rows are found per run; the union across 10 runs is 11.
3. **The auditor ignores implied scope**: 1 clean row, REACT-M14 [VERIFIED fixture react:853-872]. It cited only Appendix A.1 and Table 5, while the losing result is stated in Section 3.3 prose.
4. **The auditor breaks its own prompt rule.** For REFLEX-M13 it quoted Section 1 sentences as evidence for "supported" [VERIFIED fixture reflexion:17-36 vs audit_claim_system.md:24,29].

**Q3 — evidence representation:**
- **(a) What the auditor sees.** The system prompt plus the **whole paper**, from PyMuPDF `page.get_text()` over all pages, plus the claim text and its summary [VERIFIED prompt_loader.py:98-118; main.py:108-115]. There is no chunking or selection. That's roughly 35–40k tokens [HYPOTHESIS: from PR-1, 1.27M tokens / 30 calls]. Tables arrive as flattened text: headers and captions are there, but row and column structure is lost. Figures are absent except for captions.
- **(b) Was the deciding evidence present?** Note the auditor's inputs are not logged [VERIFIED engine.py:121-130], so this comes from the code plus the quotes it cited.
  - REFLEX-M09: **present**. The auditor quoted "80.1 (GPT-4)" and "91.0".
  - REACT-M14: **present** in Section 3.3 prose. The Figure 3 bars are absent.
  - COT-M08: present, but not relevant (pairing problem).
  - The 7 not-extracted rows: can't tell, because the auditor never saw them.
- **(c) Verdict: mixed, not "evidence absent".** Of the misses the auditor actually saw, only one is "evidence present, reasoned wrong". Confidence: medium.

**Q4 — defects on main:**
- **(a) Few-shot loader bug: still on main** [VERIFIED prompt_loader.py:58]. It affects only `extract_claims_fewshot.json`; the auditor uses no few-shots. #115 (`fix/extractor-fewshot-loader`, 6eab41e) changes:
  - prompt_loader (the fix)
  - engine and grounding (call logging)
  - prompt_version
  - a new `extractor_eval.py`
- **(b) Silent drops and rewrites:**
  - An audit or structure exception **drops the claim**, so it gets scored as not extracted [VERIFIED engine.py:459-467]. Historically 15 of 84 runs lost 76 claims [HISTORICAL decisions.md:48]; the PR-B runs had 0.
  - The structurer's label is never checked against the VERDICT line [VERIFIED engine.py:375-385].
  - Grounding does **not** drop refusals: a Fail still counts as refused [VERIFIED scorer.py:79-89]. It can only create false rejections.
  - The auditor prompt wrongly says paraphrased quotes cause the claim to be dropped [VERIFIED audit_claim_system.md:135 vs grounding.py:548].
  - I didn't count occurrences, because `logs/` mixes in held-out runs.

## 3. Retrospective (Q5)

| Attempt | Mechanism → result | Rules out | Does NOT rule out |
|---|---|---|---|
| B5.1 | Checklist fields plus a verdict cap; net 18/18/18; the cap fired 0 times | That output format alone moves the frontier | Model, thinking level, noise (2 runs) |
| Exp 1 | Paper inventory → named/implied scope items → scoped audit → code aggregation; 1 run; P3 failed | Scope-first decomposition on 3.6 Flash, as a screen | Single-run noise; thinking level; table facts computed by code |
| PR-1 | Extractor few-shot fix; FULL 20.4→20.6, grounding-negative 9.6→8.8 | Few-shot replay as the cause of recall misses | Other extractor fixes; sample-and-union |
| 2-call extractor | Estimated +0.2; never built | Nothing (it was never run) | — |
| De-leak | Prompts made synthetic; 6→5/16, and that one row was an extraction miss | Large leakage inflation (N=1) | A sub-row effect |

**Your statement: rejected as worded.** PR-1, the 2-call extractor and de-leak were not auditor changes. The rest holds: no attempt changed the auditor's thinking level or its evidence representation, and none of the five changed the model. The only model change came earlier: flash-lite → 3.6 on 09-04, and that swap flipped the gate (confounded) [HISTORICAL decisions.md:258-276].

## 4. Alternatives (Q6)

| Option | Tests | For | Against | ₹ (est.) | Risk |
|---|---|---|---|---|---|
| **A** thinking high | Medium thinking stops early | Untested; REACT-M14's evidence was present; no prompt change | Needs a small code edit (thinking isn't exposed); more caveats found may flip positives (the REACT-M03 pattern) | ~₹4.7 per audit vs ~₹3.9 → ~₹2.5k for 3 runs × 2 arms on a ~80-claim dev replay | Positives: medium; grounding: low; generalization: good |
| **B** Flash 3.7/3.8 | Model capability | Pure env change; the 09-04 swap moved the gate | Also changes the structurer (same env variable); default thinking may differ, so pin it | Price unknown, ~₹2–4k | Positives: unknown; generalization: good |
| **C** structured tables | Flattened tables hide subset losses | Literature; many refusal rows are table-based | On golden the auditor read the tables correctly; find_tables missed 2 of 4 tables [HISTORICAL decisions.md:1156]; figures not covered; cell references fail fuzzy grounding | Days of build + ~₹1.2k | Positives: **high**; grounding: **high**; generalization: medium |
| **D** atomic decomposition | — | — | **Drop**: Exp 1 already did named/implied scope items [VERIFIED scoped_schemas.py] | — | — |
| **E** rubric + relabel | The metric is noisy | 5/11 contestable; the M01/M09 inconsistency | Relabels move the number without changing the system | ₹0, about 1–2 human days | None. Note: putting overreach under partial changes strict-label only; partial already counts as a refusal |
| **F** subset-loss MUST rule | Prompt strength | Targets REACT-M14 | Largely **already in the prompt** (WeldScan example) [VERIFIED audit_claim_system.md:116-129]; breaks REACT-M10 and possibly COT-M04, which is enough to breach the floor | ~₹1.5k | Positives: **high** |

## 5. Proposed next phase (on paper)

**Q7a — dev set:**
- Size: **≥40 refusal-family rows and ≥40 positives**.
  - At n=40, an observed 60% has a Wilson lower bound of about 45%, which is your stop line.
  - If 2 or fewer rows flip back, 9 rows moving one way out of 40 is significant (exact p≈0.02).
  - 2–3 papers give only about 10–15 rows, with ±25-point intervals.
- Sources: about **8–10 papers**, with at most 6 refusal rows per paper. Use ML/NLP results-table papers posted after 2026-07, outside the agent domain.
- Labelling:
  - The rubric is written first.
  - You list every claim per section and label each one from the PDF, before seeing any Prism output.
  - A blind model pass, then you adjudicate.
- **SciClaimEval:** a ~150-item table-only slice can serve as an auditor-only check for options A and C. It does not cover extraction, natural overreach, or figures (Prism is text-only).
- **CLAIMCHECK:** gives independent labels for disputed claims. It gives no complete positive list or 3-way labels, its papers are likely in training data, and reviewer critiques may rely on outside knowledge. Use it as a sanity slice only.

**Q7b — baseline:** Freeze one extraction, then replay only the auditor **3–5×** per configuration. Since sampling parameters are ignored, run-to-run variance is all you can measure. Report mean and range and per-row flips in both directions. Each run needs:
- 0 fallback calls
- every finish_reason == STOP
- logged thinking tokens (the call logging from #115 or the Exp 1 tag provides this)

**Q7c — held-out:** The current held-out is **burnt as a gate**: 2 refusal rows and 6 uses. Keep it as a smoke test only. Build a new sealed set:
- ≥25 refusal rows
- labelled outside the repo
- the agent denied read access to its folder
- only a sha256 hash committed
- run once by you after Milestone A, counts only

**Q7d — gates per experiment:**
- A marks file written before any paid run (the exp1-marks pattern).
- A cap of about ₹1.5k per experiment and ₹6k in total.
- Positives at least the baseline minimum and the scaled floor.
- False rejections must not rise.
- Any grounding-negative row moving refused → affirmed (by majority vote) means FAIL and blocks the change.

**Q7e — success and stop:**
- Accept a change only if both hold:
  - the treatment's mean is at least 4 rows above the baseline's maximum
  - net flips are ≥6 with ≤2 reverse flips
- Stop: the existing rule (dev refusal under 45% after 4 experiments), the total cap, or 60% confirmed once on the new held-out.

**Stop rule, one paragraph:** The 45% line can't be decided on 10–15 rows; 6/13 = 46% has a lower bound of 23%. I'd keep the rule but add two conditions: an experiment counts toward the 4 only if the dev set has ≥40 refusal rows, and "under 45%" is judged on the mean of 3 runs.

## 6. One decision for you

**Recommendation:**
1. Write the rubric (E) first.
2. Grow the dev set to ≥40 refusal rows.
3. Baseline the unchanged pipeline 3×.
4. Then run **A (thinking_level=high)** as experiment 1 and **B** (with thinking pinned) as experiment 2.
5. Build C only if the dev baseline shows table-based misses where the evidence was present but the auditor reasoned wrong.
6. Drop D and F.

I'm not executing any of it.
