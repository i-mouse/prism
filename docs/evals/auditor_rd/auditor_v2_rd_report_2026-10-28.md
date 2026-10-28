> Status: reviewed, NOT decided. Frozen copy of the claude.ai doc
> (rev 50, 2026-10-28). Reviewed by ChatGPT, Gemini, DeepSeek, Perplexity.
> Decision record: decisions.md "A1 diagnosis results: Ship-honest
> (decisions.md option B) - 2026-10-28". The embedded diagram was lost on
> export (text placeholder).

# Prism Auditor R&D — Stable, Correct Claim Verdicts

Oct 28, 2026 · @nitin

## Bottom line

Prism's auditor fails because we ask one LLM to read tables from flat PDF text and judge the claim in one free-text pass. That design is both inaccurate (it trusts the paper's summary over the table cells) and unstable (the same model on the same input flips). More prompting, more thinking or a second LLM checker did not fix it in the variants we tested (B5.1, Experiment 1, A1).

The approach the research and the strongest systems point to is: **extract tables into real rows × columns once, let the LLM only map the claim to the right cells, and let code do the counting and comparing.** Add a "Needs review" verdict when the system is unsure, and store the brief per paper so a re-upload shows the same result.

| Question | Direct answer |
| --- | --- |
| Is the current auditor fixable with prompts? | No. Checklist (B5.1), higher thinking, voting and a scope checker all failed on the same rows. |
| What is the real cause? | Flat text loses table structure; the model takes the easy summary sentence; and the model is not deterministic. |
| What should Auditor v2 be? | Table-first, code-checked, abstain when unsure. |
| Will it fix all 10 misses? | Unproven. It targets the table-reading misses: code R in 3 of the 5 hard rows; P11-R2 is a different failure (S1). Prose-only claims still depend on the LLM. |
| Will it reach the release bar? | Not alone. Perfect auditor = 18/31; the bar is 22/31. Extraction work is still needed, or the bar must be restated before new results. |
| Next step | Two free, local tests (table fidelity, then a code-check ceiling) before any paid run. |

**Updated after outside review (2026-10-28).** Four reviewers (ChatGPT, Gemini, DeepSeek, Perplexity) said GO on the free tests. Their points were fact-checked; the corrections below are now in the report.

| What changed | Before | Now |
| --- | --- | --- |
| Hard rows v2 targets | About 4 of 5 | 3 of 5 (code R); P11-R2 is a different failure |
| What the mapper reads | Table headers only | The full table: row labels, caption, footnotes |
| How the mapper answers | Not defined | A strict check form, run by allowlisted code |
| Table-tool numbers | Docling's score quoted alone | Both tools' scores from the same benchmark; benchmarks disagree, T1 decides |
| Extractor rule | Two tools must agree | Each tool scored alone in T1; rule deferred |
| Token claim | Extraction costs 0 tokens | Local extraction is free; the vision tie-breaker is paid |
| Temperature | Grounding and matcher pin 0 | On gemini-3.6-flash temperature is ignored, so the pin does nothing |
| Option names | A to H, clashing with decisions.md | D1 to D8; decisions.md B is called Ship-honest |
| 2027 cost | Not computed | About INR 174 per paper before caching at list price, above the 130 gate |
| New risks | Not listed | Skipped rows, caveats outside the cells, messy cells, routing, Needs-review ceiling |
| Overclaims | "Nobody serious", "A1 just proved", "no LLM will" | Scoped to what we tested |

## The problem in plain terms

The auditor says "supported" to claims the paper's own tables contradict, and the same claim can get a different verdict on a re-run. Both problems are measured, not guessed.

| Fact | Number | Source |
| --- | --- | --- |
| Dev refusal rows caught today | 8 of 31 | dev baseline, single run |
| Auditor misses (claim extracted, wrongly called supported) | 10 | dev baseline |
| Extraction misses (claim never extracted) | 13 | dev baseline |
| Auditor-only ceiling | 18 of 31 | decisions.md |
| Release bar (dev) | 22 of 31, false rejections ≤ 8/88 | decisions.md |
| A1 scope checker: misses fixed reliably | 3 of 10 (P4-R1, P7-R1, P1-R1) | A1 results |
| A1 hard rows fixed | 1 of 6 | A1 results |
| A1 claims lowered across 3 identical runs | 6 / 3 / 2 | A1 results |
| Diagnosis: lister found the right scope word | 13 of 15 hard-row cells | A1 diagnosis |
| Diagnosis: checker read summaries, not table rows (R) | 9 of 15 hard-row cells | A1 diagnosis |
| Diagnosis: "lowered" cases resting on weak evidence | 3 of 10 | A1 diagnosis |

What this means:

- **The extraction of scope words works.** The break is in reading the table.
- **The checker repeated the auditor's habit.** Same model, same flat text, same blind spot.
- **Stability is a separate failure.** Three of the six-to-two drop came from the checker changing its own answer on identical input.
- **Some wins were luck.** The literature has a name for this: correct labels without faithful reasoning (see section on the field).

## What we already tried on the auditor

Auditor v2 must not repeat any of these. Each one is recorded in decisions.md or FINDINGS.md.

| Attempt | What it tried | Result | Lesson for v2 |
| --- | --- | --- | --- |
| Scoped-auditor pilot (tag archive/exp1-scoped-auditor, about INR 204) | Scope-first auditor design | Flipped 4 of 11 existing refusals to supported; lowered one positive wrongly | Scope logic inside the LLM can hurt as well as help; keep "can only lower" and always measure lost hits |
| B5.1 checklist (tag archive/b5.1-checklist-attempt) | Checklist fields, a code cap that can only lower, a token-exact gate for table-row quotes | Net unchanged (18); the same code gave different verdicts across runs | Instability is old, not new to A1; a code rule only helps if its input is right |
| Experiment 1: thinking high (INR 411.95) | More reasoning per audit | Fixed 1 of 10; run-to-run noise about ±3 rows | More thinking does not fix table reading |
| Numbered sentences + voting (2026-10-19 candidate) | Cite sentence IDs; majority vote | Dropped as the fix on 2026-10-22; voting kept for stability only | v2 uses agreement only on the small mapping step |
| A1 scope lister + checker (INR 136.16) | LLM lists scope items, LLM checks them | 3 of 10; lowered 6 / 3 / 2 | The checker read summaries, not table rows |
| Alternative readers (Experiment 3 pre-checks) | PyMuPDF4LLM, GROBID as the whole-paper reader | Lost claim rows: 77 and 81 of 119, vs 112 for raw PyMuPDF | Raw PyMuPDF stays the reader; table tools only feed a side store |
| Grounding text normalisation (merged, on) | Normalise text before fuzzy quote matching | 20 table-row quotes went fail → pass, 0 pass → fail | Table rows split across lines in raw text is a measured, known problem |

Other recorded findings that shape v2:

- **Named vs implied scope.** The auditor refuses when the breaking dimension is named in the claim ("all three tasks") and affirms when it is only implied (which models, baselines, tasks). In v2 the mapper must turn implied scope into explicit cells. That is the hardest LLM step left, and the one to watch in T3.
- **Loose quote matching.** A quote that skips table cells can still pass partial\_ratio 88 (a recorded ReAct row scored 90.0). An exact cell check removes this.
- **Headers can go missing.** A table with no paragraph breaks gets a 500-character context window, so a row can reach the auditor without its column headers.
- **Two hard rows have text problems.** P5-R2's claim sentence is one of the 7 rows raw PyMuPDF text cannot reproduce exactly (Check E), and its answer-key row letters differ from the raw text. P6-R2's answer key mentions a figure. T1 must check both by eye.
- **A newer model is still a later candidate.** FINDINGS keeps a newer-Flash-with-thinking auditor as an optional later experiment; it stays parked with the Gemini migration.

## Why the auditor keeps failing

Five causes stack on each other. Each one is documented outside Prism, not only in our runs.

| # | Cause | What we saw in Prism | What the research says |
| --- | --- | --- | --- |
| 1 | **Tables lose structure as flat text** | 10-22 check: column headers only by position, merged cells, merged header lines | How a table is written out changes LLM accuracy by several points; explicit structure (HTML, JSON, key-value) beats loose text, and the gap widens on complex tables ([Microsoft SUC](https://www.microsoft.com/en-us/research/blog/improving-llm-understanding-of-structured-data-and-exploring-advanced-prompting-methods/), [TabularMath](https://arxiv.org/pdf/2505.19563)) |
| 2 | **Scientific table claims are genuinely hard** | Hard rows need counting, "all models", per-cell comparison | On SciTab, every model except GPT-4 scored barely above random, and Chain-of-Thought gave little gain ([SciTab](https://arxiv.org/abs/2305.13186v1)) |
| 3 | **The model trusts the author** | Checker quoted the paper's summary line and said "matches" | LLM judges show truth-bias: they tend to judge statements as true; reasoning models reduce it but do not remove it ([Barkett et al.](https://arxiv.org/html/2506.21561v1)) |
| 4 | **Right label, wrong reason** | 3 of 10 lowered cases used off-target evidence | Most LLMs often get the label right on scientific tables but fail to point at the cells a human would, so the label is not from faithful reasoning ([Ho et al.](https://arxiv.org/abs/2506.10486v1)) |
| 5 | **The model is not deterministic** | Lowered 6 / 3 / 2 on identical input | Temperature 0 does not give determinism; batching and floating-point order change outputs. One team saw 29 of 103 cases flip on Gemini 3 Flash at temperature 0, and thinking mode adds more divergence points ([MemX](https://memx.app/blog/llm-determinism-is-a-lie-29-flapping-cases/)) |

Two honest notes:

- **Lowering temperature is not the fix.** Google strongly recommends leaving Gemini 3 at temperature 1.0 and warns lower values can cause looping or worse reasoning ([Gemini 3 guide](https://ai.google.dev/gemini-api/docs/gemini-3)). And on gemini-3.6-flash, which Prism uses, temperature, top\_p and top\_k are now deprecated and ignored, so the 0 that grounding and the eval matcher pin does nothing there; the eval matcher is not deterministic either, so some eval noise is judge noise. Which model each of those calls actually hits must be confirmed.
- **The MemX figure is one vendor blog on a classification task**, not a peer-reviewed study. Treat it as a direction, not a number for Prism. Our own 6 / 3 / 2 is the number that matters.

## What the field does

The consistent pattern across research and working systems: **give the model structured tables, and let code do the exact steps.** None of the approaches we found rely on one free-text LLM pass for numeric table claims.

| Approach | What it is | Evidence | Fit for Prism |
| --- | --- | --- | --- |
| **Program-aided table reasoning** (Text-to-SQL, Binder, Dater, TART) | LLM writes a small program or query; code runs it on the table | Standard family for table fact checking; TART pairs an LLM with table tools for precise data processing ([TART](https://aclanthology.org/people/xinyuan-lu/)) | High: counting and "all models" checks are exactly what code does well |
| **Chain-of-Table** | LLM picks table operations step by step (select rows, columns, group); code executes each and feeds back the smaller table | State of the art on TabFact (86.61) at publication, with the biggest gains on large tables ([Google Research](https://research.google/blog/chain-of-table-evolving-tables-in-the-reasoning-chain-for-table-understanding/)) | High, but more moving parts than we need |
| **Atomic reasoning** | Break verification into small skills (locate cell, compare, aggregate) | Beat GPT-4o + CoT on SciTab with a smaller specialised model ([SciAtomic](https://arxiv.org/html/2506.06972v1)) | Medium: the decomposition idea fits; training a model does not |
| **Decompose-then-verify** (FActScore, SAFE, VeriScore) | Split text into atomic claims, verify each against evidence | The common factuality pipeline ([VeriFastScore](https://arxiv.org/pdf/2505.16973)); but decomposition does not always help, depending on the verifier ([Decomposition Dilemmas](https://arxiv.org/html/2411.02400v2)) | Prism already does this (claims → scope items); it is not the missing piece |
| **Cell-level rationales** | Require the model to name the exact cells used | Adding table alignment improves verification ([Ho et al.](https://arxiv.org/abs/2506.10486v1)) | High: cited cells become our evidence and our grounding check |
| **Native PDF vision** | Send the PDF pages; the model sees tables as images | Gemini reads PDFs with native vision and can analyse tables ([Gemini docs](https://ai.google.dev/gemini-api/docs/document-processing?authuser=1)); but image tables score somewhat below text tables in studies ([TabularMath](https://arxiv.org/pdf/2505.19563), [TeleTables](https://arxiv.org/pdf/2601.04202)) | Medium: good as a second table source or cross-check, not as the judge |
| **Self-consistency + abstention** | Run several times; if answers disagree, say "unsure" | Agreement across samples is a reasonable proxy for errors; conformal abstention bounds the error rate ([Abbasi Yadkori et al.](https://arxiv.org/abs/2405.01563v1)); it cannot catch a model that is confidently wrong every time ([emergentmind summary](https://www.emergentmind.com/papers/2604.19444)) | High for stability and honesty; does not fix accuracy |
| **Working paper-error tools** (Black Spatula, YesNoError) | Extract tables and images, then prompt a reasoning model, often several passes | Black Spatula reported about 10% false alarms, and every flag still needs expert review ([Nature via lennxa](https://lennxa.bearblog.dev/ai-checks-papers-for-errors/)) | Confirms the shape: extract structure first, flag for humans, never claim certainty |

**What this tells us:** our A1 design (LLM lists items, LLM checks items) is the weakest form of decomposition. The field's stronger move is to take the exact step away from the LLM.

## Options compared

Design D6 is the only one likely to attack both accuracy and stability at the root (untested). D7 is a cheap product layer worth adding. Everything else is either already tried or out of scope. Labels are D1 to D8 so they do not clash with decisions.md's options A (one more experiment), B (Ship-honest) and C (extraction work).

| Option | Fixes reading? | Fixes stability? | Cost per paper | Effort | Main risk | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| D1. More prompt rules for auditor or checker | No (B5.1 failed) | No | Same | Low | Repeats a failed path | **Reject** |
| D2. Higher thinking or majority voting alone | No (10-22: cannot fix the 6 unanimous misses) | Partly | Up to 3× audit | Low | Pays more for the same blind spot | **Reject as a fix**; keep voting for stability only |
| D3. Bigger or newer model | Unknown | No | Higher | Low | Truth-bias persists; Gemini migration is parked | **Not now** |
| D4. Send PDF pages (vision) to the auditor | Partly | No | More input tokens | Low | Image tables score below text tables; still one LLM judgment | **Use as table source only** |
| D5. Structured tables as text to the LLM checker | Partly | No | Similar | Medium | Better reading, but the verdict is still a free LLM judgment | **Step toward D6**, not the end |
| **D6. Structured tables + LLM maps claim to cells + code checks** | **Likely, for table claims (untested)** | **Yes, for the code step** | Lower audit tokens (mapping sees one table, not the whole paper) | Medium to high | Table extraction quality on real papers | **Recommended** |
| **D7. Same-paper cache + "Needs review" on disagreement** | No | Yes, for the user | Small | Low | Hides flips unless paired with D6 | **Add with D6** |
| D8. Fine-tune a table verifier | Yes, in papers | Partly | Training cost | High | Solo dev, no labelled data at scale | **Out of scope** |

"Cost per paper" is directional. Prism measures cost; it does not estimate it. Any paid stage gets a measured `--estimate` and a cap first.

## Recommended design: Auditor v2

Tables are extracted once per paper into a store. For each claim, the LLM reads the relevant table in full (row labels, caption, footnotes) and fills a strict check form: which cells, and which rule. Code runs the check. If three mapping runs pick different cells or rules, the claim shows Needs review.

&#91;embedded content: Auditor v2 · tables once per paper, LLM maps, code checks\]

The LLM does not count or compare; it picks the cells and the rule. That removes the summary-for-cells swap that broke A1. But picking the right cells is itself hard for LLMs on scientific tables ([Ho et al.](https://arxiv.org/abs/2506.10486v1)), so the mapper stays the main risk, not a solved step.

**Three lenses:**

| Lens | Today | Auditor v2 |
| --- | --- | --- |
| State flow | Paper text cached; auditor writes free text; a structurer turns it into a label; scope items in the trace | New per-paper table store (table id, cells, caption, footnotes, source, extractor version) keyed by file hash and pipeline version; per claim a check form, a result and the cited cells; the brief stored for re-upload |
| Token efficiency | Each claim's checker reads the whole cached paper (up to about 95K tokens on P3) | Local extraction costs 0 tokens; the vision tie-breaker, if ever used, is paid. The mapper sees the claim plus one full table, still far smaller than the paper. The code check costs 0 tokens; 3-run agreement repeats only the mapping call. Direction is lower; measure before claiming |
| Retrieval accuracy (grounding) | Fuzzy quote match (partial\_ratio ≥ 88) on prose | Cited cells checked exactly against the store; a summary sentence can no longer stand in for a cell |

**Table sources, in order of trust** (versions must be re-checked as current before building):

1. **Two local extractors, each scored on its own** against hand-checked cells in T1: pymupdf4llm 1.28, from the PyMuPDF family Prism already uses, now with a layout-based table engine ([Artifex](https://artifex.com/blog/enhanced-table-extraction-in-pymupdf4llm-1-28)); and Docling. Benchmarks disagree sharply: on the public opendataloader-bench leaderboard (200 general PDFs, not ML papers) table structure scored Docling 0.887 and pymupdf4llm 0.401 ([Nutrient, checked 15 Oct 2026](https://www.nutrient.io/api/data-extraction-api/benchmarks/)), while another benchmark had them level, 84.8% vs 84.5% TEDS ([pdf-parser-benchmark](https://github.com/applied-artificial-intelligence/pdf-parser-benchmark)). Only T1 on our own papers decides. No must-agree rule until T1 data exists.
2. **Gemini PDF vision as a tie-breaker**, only for tables both extractors get wrong or disagree on; paid. Google suggests testing high media resolution for dense documents ([Gemini 3 guide](https://ai.google.dev/gemini-api/docs/gemini-3)).
3. **Dropped for now: the authors' LaTeX or arXiv HTML.** It needs a network fetch and may be a different paper version from the upload. About 90% of arXiv articles have TeX source ([ICMS 2026](https://icms-conference.org/2026/papers/paper02/main.pdf)), so it can return later if T1 shows PDF tables are the bottleneck.

**Already tested, so v2 does not repeat it:** in the Experiment 3 pre-checks (decisions.md, 2026-10-14), alternative readers were tried as the whole-paper text source for claim extraction. Raw PyMuPDF text kept 112 of 119 dev rows; GROBID kept 81; PyMuPDF4LLM kept 77. Both were rejected as the reader. Auditor v2 keeps that decision: raw PyMuPDF text stays the reader for extraction and prose audit. The table tools only feed a separate table store, and T1 tests them on table cells, which is a different job from finding claim sentences. The PyMuPDF4LLM version used in that test is not recorded, so T1 must pin and record versions.

**What stays from today:** the "can only lower" rule, the grounded-quote guard for prose claims, explicit caching (A0 passed), and every experiment flag off by default.

**Added after outside review** (ChatGPT, Gemini, DeepSeek and Perplexity reviewed this report; their points were fact-checked before adding):

- **Strict check form.** The mapper fills a schema: table id, row keys, column keys, a rule from a fixed list (all at least, count equals, best in column, beats baseline), polarity (higher or lower is better), unit and tolerance. Code runs only those listed rules; the LLM never writes code.
- **Agreement on the form, not the verdict.** Three runs agree only if they pick the same cells and the same rule. Different cells that happen to give the same verdict count as disagreement.
- **Coverage check.** Proving "all selected rows" is not proving "all relevant rows". The mapper must list every row it leaves out, with a reason, and code confirms every row of the claimed group is either checked or excluded on purpose. This is the old implied-scope failure, moved into the mapper.
- **Caveats outside the cells.** If a caption, footnote or nearby sentence limits the claim, code may not return Supported; the claim goes to Needs review or the prose auditor.
- **Cell parser.** A plain code parser, with unit tests, for messy cells: ±, \*, bold markers, OOM, dashes, percentages.
- **Router.** A written rule decides which claims take the table path and which the prose path. A misrouted claim must be visible in the trace.
- **Order of steps.** Code check, then the "can only lower" rule, then Needs review. Needs review never raises a verdict.
- **Cache key.** File hash + extractor version + mapper prompt hash + model + checker version + table schema version.
- **Agreement is not proof.** Three runs can agree and still be wrong; studies find self-consistent errors are hard to detect. T3 reports accuracy among unanimous mappings separately.

## Stability as a product feature

A reviewer tool that changes its verdict on re-upload is not usable. Senior teams do not try to make the LLM deterministic; they design the pipeline so the variance cannot reach the user unchecked.

| Layer | What it does | What it does not do |
| --- | --- | --- |
| **Code for exact steps** | Counting, "all of", comparing cells: same input, same answer, every time | Cannot decide which table a claim is about |
| **Structured output** | Fixes the answer's shape; Prism's auditor still writes free text that a structurer converts | Does not fix the answer itself ([MemX ladder](https://memx.app/blog/llm-determinism-is-a-lie-29-flapping-cases/)) |
| **Agreement check (3 runs) on the LLM step only** | If the claim-to-cells mapping disagrees, the claim shows **Needs review** instead of a guess | Cannot catch a model that is wrong the same way 3 times |
| **Same paper, same brief** | Store the brief by file hash + pipeline version; a re-upload returns the stored brief | Hides flips; it is consistency, not correctness |
| **Show the cells** | Every table verdict shows the exact rows and columns used | Prose-only claims still show quotes, as today |

Why "Needs review" is the honest move:

- **It matches how working tools ship.** Paper-error tools flag for human review rather than claiming certainty ([Nature via lennxa](https://lennxa.bearblog.dev/ai-checks-papers-for-errors/)).
- **It turns instability into a signal.** Disagreement across samples is one of the better available proxies for an error ([Abbasi Yadkori et al.](https://arxiv.org/abs/2405.01563v1)).
- **It costs coverage.** A rising "Needs review" share is a real cost and must be reported next to recall, not hidden.

What to keep from today: the "can only lower" rule and the grounded-quote guard. Both passed A1 (0 quote violations). With D6, the guard gets stronger, because cited cells can be checked exactly instead of by a fuzzy 88 match.

## Eval and marks

Two free, local tests decide whether design D6 is worth any money. If either fails, D6 stops and Prism ships with honest numbers (Ship-honest, decisions.md option B).

**Gate tests (free, written as a dated entry with marks before running):**

| Test | Question it answers | How | Cost |
| --- | --- | --- | --- |
| **T1. Table fidelity** | Can we get the breaking tables out of the dev PDFs as correct rows × columns? | Run two local extractors (pymupdf4llm 1.28 and Docling) on the dev PDFs; score each tool on its own, per cell (table, row, column, value, unit), against the values already pinned in the 10-22 diagnostic; no must-agree rule until T1 data exists | INR 0 |
| **T2. Code-check ceiling** | If the mapping were perfect, does code reach the right verdict? | Hand-write the check (table, rows, columns, rule) for the 5 hard rows, the 3 fixed rows and 8 to 10 dev S rows backed by a table (a free false-rejection check); classify P6-R2 (figure) before writing marks; run it on T1's tables | INR 0 |
| T3. LLM mapping (paid, only if T1 and T2 pass) | Can the LLM produce those checks itself, stably? | Mapping call on the frozen 18-claim set, 3 repeats, with a cap | Measured `--estimate` first |

Why these two first: T1 tests the riskiest part (PDF tables, the exact thing that broke). T2 gives the best possible result of the design before paying for any LLM. If T2 cannot fix the hard rows with perfect mapping, D6 is not worth paying for. A T2 pass cannot prove D6; it only allows a capped T3.

**Metrics to report from now on (every run, every stage):**

| Metric | Meaning | Why it matters |
| --- | --- | --- |
| Refusal-family recall | Refusal rows caught, of 31 | The current headline |
| False rejections | S rows wrongly lowered, of 88 | Keeps the auditor from becoming paranoid |
| **Flip rate** | Claims whose verdict differs across 3 identical runs | The stability number; today not reported |
| **Needs-review rate** | Share of claims the system declines to judge | The price of honesty; capped in the gate, so the system cannot pass by refusing to judge |
| **Evidence faithfulness** | Share of verdicts, lowered and Supported alike, whose cited cells are the right cells | Catches "right label, wrong reason" (the 3 of 10 OK† cases) |

The PDFs used in T1 are dev papers, not held-out or sealed files. The held-out set stays closed; the release number still comes from one sealed-set run only.

## Honest limits and risks

Design D6 is the right direction, not a proven fix. These are the ways it can fail or disappoint.

| Risk | Why it is real | What we do about it |
| --- | --- | --- |
| **PDF table extraction may be wrong on our papers** | Merged and spanning headers stay the hardest parsing problem; accuracy drops beyond simple grids ([Codesota](https://www.codesota.com/browse/computer-vision/document-parsing)). Benchmark scores do not predict results on your own corpus ([macmyths](https://macmyths.com/docling-alternatives-for-extracting-structured-data-from-documents/)) | T1 tests our actual dev tables before any spend; each extractor is scored per cell against hand-checked values |
| **Only table claims benefit** | Prose-only and figure claims still go through the LLM; figures are the hardest evidence type for all models ([SciClaimEval](https://aclanthology.org/people/yun-ang-wu/)) | Report table and prose claims separately; P6-R2's note even mentions a figure |
| **The LLM can map a claim to the wrong table** | Mapping is still an LLM judgment | Agreement check across 3 runs; disagreement → Needs review |
| **Hard rows are few** | 5 hard rows is a tiny sample; any gain is directional | No headline claims from dev; release number only from the sealed set |
| **Overfitting to 5 known rows** | We know the failing rows by name | Design targets the failure type (table scope checks), judged on all 88 S rows too |
| **The release bar stays out of reach** | Perfect auditor = 18/31 < 22/31 | Either extraction work later, or restate the bar (below) |
| **More components, more to maintain** | Extractor, table store, mapper, executor | One engine, one domain, flags off by default; no platform framing |

**The release-bar question (decide before any new result):** you said a missed claim is acceptable but a wrong verdict is not. That is a precision-first product. Note that the current bar (restated 2026-10-22) already has a stability part: fixes must hold in at least 2 of 3 repeats. If you agree, the bar should say so: for example, recall stays reported, but the ship gate is wrong-verdict rate, flip rate and false rejections. Changing it after seeing results would look like moving the goalposts. Changing it now, with the reason written down, is a product decision. Write the second reason down too: a precision-first bar also escapes the unreachable 22/31. Committing it before T1 is legitimate; hiding that motive is not. All four reviewers converged on the same shape: hard gates on wrong-verdict rate, flip rate and false rejections (at most 8/88); recall stays visible with a floor of never losing today's 8 catches; and a ceiling on Needs review.

## Build order and next steps

Work is ordered by dependency. Each step gates the next; nothing paid runs before the two free tests pass.

1. **Save the A1 diagnosis and the Ship-honest decision (decisions.md option B)** in decisions.md (docs only; already drafted).
2. **Decide the release bar** (recall-first or precision-first), in writing, before any new result.
3. **Write the Auditor v2 entry**: design D6 + D7, the marks for T1 and T2, and what counts as a pass. Commit and tag before running.
4. **Run T1 (table fidelity)**, free and local, on dev PDFs only.
5. **Run T2 (code-check ceiling)**, free, with hand-written checks for the 5 hard rows, the 3 fixed rows and 8 to 10 table-backed S rows.
6. **Stop or continue.** If T1 or T2 fails: ship with honest numbers (Ship-honest), write the negative-results report, move on. If both pass: a new dated entry with T3 marks and an INR cap.
7. **T3 (paid, capped)**: LLM mapping on the frozen 18-claim set, 3 repeats; report recall, false rejections, flip rate, needs-review rate and faithfulness.
8. **Only after T3 passes**: Stage B (false rejections on 88 S rows), then product wiring behind a flag, the same-paper cache and the Needs review state in the UI.

**Money and gates (from decisions.md):** the auditor stage total is INR 560, with INR 173.23 spent (A0 36.86, probe 0.21, A1 136.16). The Stage B cap of INR 250 is unused, and the sealed reserve of INR 300 is untouched. T1 and T2 cost INR 0. T3 needs its own dated entry with marks and a cap, committed and tagged, plus a measured `--estimate`; the run stops at 1.3× the estimate, and a capped run is void. Production cost is about INR 87 per paper measured before caching, against the INR 130 per paper gate used in earlier experiments, and gemini-3.6-flash prices double from 2027-01-01 (Prism pays a temporary USD 0.75 / 3.75 per 1M tokens; the list price is 1.50 / 7.50), so about INR 87 becomes roughly INR 174 per paper before caching, above the gate. Caching already cut audit cost per claim from 3.79 to 1.30 (A0). v2 must report cost per paper at 2027 prices against the same gate.

Out of scope throughout: Gemini migration, pass 2, MCP, multi-agent split, Foundry, held-out or sealed files.

**Questions for outside reviewers** (send these with this doc):

1. Is "structured tables + LLM maps claim to cells + code checks" the right decomposition for numeric scope claims, or is there a simpler design we missed?
2. For born-digital ML papers, which table extractor would you test first, and how would you score fidelity on about 16 known cells?
3. Is a 3-run agreement check on the mapping step a sound abstention rule, or should abstention use a calibrated threshold?
4. For a claim-auditing tool, should the ship gate be recall, or wrong-verdict rate plus flip rate?
5. Is 5 hard rows plus 3 fixed rows enough to decide go or stop on T2, given that the release number comes only from a sealed set?

## Sources

Prism internal: decisions.md ("Auditor phase diagnostic - 2026-10-22", "Stage A1 results: FAIL - 2026-10-28", "A1 diagnosis plan and reading rule - 2026-10-28"), the A1 diagnosis report, claude/handoff\_2026-10-28.md.

External (opened or searched 2026-10-28):

- [SciTab: claim verification on scientific tables](https://arxiv.org/abs/2305.13186v1)
- [Table-Text Alignment: cell-level rationales on SciTab](https://arxiv.org/abs/2506.10486v1)
- [SciClaimEval: cross-modal claim verification](https://aclanthology.org/people/yun-ang-wu/)
- [Atomic Reasoning for Scientific Table Claim Verification](https://arxiv.org/html/2506.06972v1)
- [Chain-of-Table (Google Research)](https://research.google/blog/chain-of-table-evolving-tables-in-the-reasoning-chain-for-table-understanding/)
- [TART and related work by Xinyuan Lu](https://aclanthology.org/people/xinyuan-lu/)
- [Table Meets LLM: table format study (Microsoft Research)](https://www.microsoft.com/en-us/research/blog/improving-llm-understanding-of-structured-data-and-exploring-advanced-prompting-methods/)
- [TabularMath: table representation and reasoning](https://arxiv.org/pdf/2505.19563)
- [TeleTables: table format comparison](https://arxiv.org/pdf/2601.04202)
- [VeriFastScore: decompose-then-verify pipelines](https://arxiv.org/pdf/2505.16973)
- [Decomposition Dilemmas](https://arxiv.org/html/2411.02400v2)
- [Reasoning Isn't Enough: truth-bias in LLM judges](https://arxiv.org/html/2506.21561v1)
- [Mitigating LLM Hallucinations via Conformal Abstention](https://arxiv.org/abs/2405.01563v1)
- [Distilling self-consistency for calibration (summary)](https://www.emergentmind.com/papers/2604.19444)
- [LLM Determinism Is a Lie: 29 flapping cases (MemX, vendor blog)](https://memx.app/blog/llm-determinism-is-a-lie-29-flapping-cases/)
- [Gemini 3 developer guide: temperature and PDF guidance](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Gemini document understanding](https://ai.google.dev/gemini-api/docs/document-processing?authuser=1)
- [PyMuPDF4LLM 1.28 table extraction](https://artifex.com/blog/enhanced-table-extraction-in-pymupdf4llm-1-28)
- [Docling alternatives and table TEDS scores (Nutrient)](https://www.nutrient.io/blog/docling-alternatives.md)
- [Document parsing overview (Codesota)](https://www.codesota.com/browse/computer-vision/document-parsing)
- [Docling alternatives: test on your own corpus (macmyths)](https://macmyths.com/docling-alternatives-for-extracting-structured-data-from-documents/)
- [AI checks papers for errors (Nature report, via lennxa)](https://lennxa.bearblog.dev/ai-checks-papers-for-errors/)
- [arXiv HTML conversion and coverage (ICMS 2026)](https://icms-conference.org/2026/papers/paper02/main.pdf)

Added after outside review (checked 2026-10-28):

- [What's new in Gemini 3.6 Flash: sampling parameters ignored, list price](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6)
- [Nutrient benchmarks page, citing the opendataloader-bench leaderboard](https://www.nutrient.io/api/data-extraction-api/benchmarks/)
- [pdf-parser-benchmark (applied-artificial-intelligence)](https://github.com/applied-artificial-intelligence/pdf-parser-benchmark)
