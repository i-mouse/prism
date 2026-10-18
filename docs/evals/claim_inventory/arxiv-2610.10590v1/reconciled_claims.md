# Reconciled claims — arxiv-2610.10590v1

Claims both reviewers keep after cross-review (ChatGPT final list ∩ Gemini final
list), paired by source sentence via rapidfuzz `token_set_ratio` on
`normalize_for_match`-normalized text, confirmed by reading each pair. Built
blind to the pipeline's own output — no pipeline/replay/fixture file was opened
while building this file.

**Reconciled: 60**

| id | verbatim sentence | section | source reviewer ids |
|---|---|---|---|
| K001 | This decision can use knowledge gained during diagnosis, including the fact that a previously plausible cause has been ruled out or that the user has moved to a different task. | Introduction | gpt:ADD-C08 / gem:C08 |
| K002 | In an exploratory OpenTelemetry debugging case followed by an unrelated implementation task, the method ended with 231,951 provider-reported prompt tokens versus 912,492 under retained history, used 50% fewer cumulative input tokens, and had an estimated API cost of $1.28–$1.44 versus approximately $4.38. | Abstract | gpt:C02 / gem:C02 |
| K003 | Both arms passed the two-case primary behavioral oracle; neither fully satisfied the follow-up evaluation. | Abstract | gpt:C03 / gem:C03 |
| K004 | The method made more requests and took 17% longer. | Abstract | gpt:C04 / gem:C04 |
| K005 | A contrasting application-development pair produced no context or cost saving, and an earlier continuation exhibited lower manually assessed quality despite reduced context. | Abstract | gpt:C05 / gem:C05 |
| K006 | These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload dependence as a central consideration for reversible context management. | Abstract | gpt:C06 / gem:C06 |
| K007 | Its potential benefit lies in reducing repeated input and leaving less obsolete material in subsequent requests. | 1 Introduction | gpt:C07 / gem:C09 |
| K008 | Our operation can select already completed results without requiring a branch boundary. | 2 Related work— Structured reduction | gpt:ADD-C17 / gem:C17 |
| K009 | Post-exposure curation gives the agent a further choice over continued retention without requiring changes to the source tool. | 1 Introduction | gpt:C08 / gem:C10 |
| K010 | Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual tool-result occurrences, not a claim to invent agent-controlled memory. | 1 Introduction | gpt:C09 / gem:C11 |
| K011 | The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where the mechanism is useful. | 1 Introduction | gpt:C10 / gem:C13 |
| K012 | The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors. | 1 Introduction | gpt:C11 / gem:C14 |
| K013 | Post-exposure curation can additionally exploit conclusions reached after inspection. | 2 Related work— Positioning | gpt:ADD-C23 / gem:C23 |
| K014 | Human instructions therefore remain a verbatim task anchor under our context operations. | 2 Related work — Freely editable context | gpt:C12 / gem:C22 |
| K015 | Reversible curation reduces context in the noisy case, but not in every task | 5 Results — Figure 1 | gpt:C13 / gem:C30 |
| K016 | Both arms submit both tasks normally, without recorded provider errors. | 5.1 OpenTelemetry resource use | gpt:C14 / gem:C31 |
| K017 | Table 1 shows substantial reduction in active and cumulative input under the method despite more requests. | 5.1 OpenTelemetry resource use | gpt:C15 / gem:C32 |
| K018 | At primary submission the method carries 124,746 prompt tokens versus 847,674 for retained, an 85% reduction. | 5.1 OpenTelemetry resource use | gpt:C16 / gem:C33 |
| K019 | After the follow-up, the method carries 231,951 versus 912,492 prompt tokens, a 75% reduction. | 5.1 OpenTelemetry resource use | gpt:C17 / gem:C34 |
| K020 | The method peak is 381,299 versus 912,492 tokens. | 5.1 OpenTelemetry resource use | gpt:C18 / gem:C35 |
| K021 | Thus, the observed comparison reaches a substantially larger retained context than the earlier coding tasks. | 5.1 OpenTelemetry resource use | gpt:C19 / gem:C36 |
| K022 | Cumulative input decreases by 50%, and input plus completion tokens decrease by 50%. | 5.1 OpenTelemetry resource use | gpt:C20 / gem:C37 |
| K023 | The estimated cost is approximately 67–71% lower, even after reported cache usage is included. | 5.1 OpenTelemetry resource use | gpt:C21 / gem:C38 |
| K024 | Method's startup-failure branch joins a signal-waiting thread without first arranging its termination, consistent with the observed timeout. | 5.2 Observed task quality | gpt:ADD-C51 / gem:C51 |
| K025 | Archived material includes large observability responses and completed diagnostic or verification output. | 5.3 What was archived | gpt:ADD-C54 / gem:C54 |
| K026 | The method generates more than twice as many completion tokens and takes 17% longer. | 5.1 OpenTelemetry resource use | gpt:C22 / gem:C39 |
| K027 | These are resource savings without a speed advantage in this case. | 5.1 OpenTelemetry resource use | gpt:C23 / gem:C40 |
| K028 | Both primary candidates pass the two-case behavioral oracle. | 5.2 Observed task quality | gpt:C25 / gem:C42 |
| K029 | For the follow-up, both candidates compile. | 5.2 Observed task quality | gpt:C26 / gem:C43 |
| K030 | The method exits with status 0 after SIGTERM in 8.43 seconds and after SIGINT in 8.85 seconds. | 5.2 Observed task quality | gpt:C27 / gem:C44 |
| K031 | Retained fails both probes and is killed with status 137. | 5.2 Observed task quality | gpt:C28 / gem:C45 |
| K032 | Conversely, retained passes the occupied-port startup-failure probe with status 1; the method’s second process does not finish within 30 seconds. | 5.2 Observed task quality | gpt:C29 / gem:C46 |
| K033 | The method therefore shows stronger tested signal handling but weaker tested startup-failure handling. | 5.2 Observed task quality | gpt:C30 / gem:C47 |
| K034 | The frozen mixed grader reports 3/6 for method and 2/6 for retained. | 5.2 Observed task quality | gpt:C31 / gem:C48 |
| K035 | Source inspection identifies false negatives in its static checks: method calls server_ptr->Shutdown(...) rather than the expected server->Shutdown(...), and retained uses signalfd rather than the expected sigwait. | 5.2 Observed task quality | gpt:C32 / gem:C49 |
| K036 | The method makes five successful archival batches in the primary phase and four in the follow-up. | 5.3 What was archived | gpt:C33 / gem:C52 |
| K037 | In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters. | 5.3 What was archived | gpt:C34 / gem:C53 |
| K038 | All 26 archived text payloads and image lists match their recorded tool returns exactly. | 5.3 What was archived | gpt:C35 / gem:C55 |
| K039 | The archive verifies exact payload preservation while the agent repeatedly curates context and continues working; this pair does not test retrieval behavior because no recovery is requested. | 5.3 What was archived | gpt:C36 / gem:C56 |
| K040 | Planroom yields no context or cost saving: the method ends with 6% more prompt tokens (283,105 versus 265,965) and uses less than 1% more total tokens (68,136,934 versus 67,669,624). | 5.4 Workload contrast and repeated pilot | gpt:C37 / gem:C57 |
| K041 | Both arms support the twelve journeys at the available assessment resolution, with the gaps described above. | 5.4 Workload contrast and repeated pilot | gpt:C38 / gem:C58 |
| K042 | Archival of 34 results removes only 69,685 net history characters; this does not offset the differing generated trajectories and method overhead. | 5.4 Workload contrast and repeated pilot | gpt:C39 / gem:C59 |
| K043 | The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing difference. | 5.4 Workload contrast and repeated pilot | gpt:C40 / gem:C60 |
| K044 | The Sphinx batch contains two final 24/24 method outcomes and one retained 24/24 outcome. | 5.4 Workload contrast and repeated pilot | gpt:C41 / gem:C61 |
| K045 | Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps. | 5.4 Workload contrast and repeated pilot | gpt:C42 / gem:C62 |
| K046 | The original result therefore remains an observed quality loss alongside a resource saving. | 5.5 Adverse and compromised observations | gpt:C46 / gem:C66 |
| K047 | Large tool outputs can be necessary for discovering an explanation but redundant after that explanation is established. | 6 Discussion— Selection after diagnosis | gpt:ADD-C67 / gem:C67 |
| K048 | If subsequent work is short, or if most observations remain relevant, the overhead of extra prompts, notes, and tool calls can outweigh the reduction. | 6 Discussion— Selection after diagnosis | gpt:ADD-C69 / gem:C69 |
| K049 | The retention operation acts on recorded observations, so an upstream tool need not expose its own compaction controls. | 6 Discussion— Working with verbose external tools | gpt:ADD-C71 / gem:C71 |
| K050 | Its value depends on whether the agent can retain the useful evidence after inspection, not merely on the size of a response. | 6 Discussion— Working with verbose external tools | gpt:ADD-C73 / gem:C73 |
| K051 | Filtering and curation can be combined: one limits initial exposure, while the other revisits retention as the task evolves. | 6 Discussion— Working with verbose external tools | gpt:ADD-C74 / gem:C74 |
| K052 | Batch selection permits a separate note for each result, preserving the surrounding conversation and access to the originals rather than replacing the entire session with a single summary. | 6 Discussion—Task pivots | gpt:ADD-C76 / gem:C76 |
| K053 | Protecting user messages prevents direct archival of the task text. | 6 Discussion— Protected instructions and remaining risks | gpt:ADD-C81 / gem:C81 |
| K054 | The OpenTelemetry archive illustrates that the agent can act on this distinction. | 6 Discussion — Selection after diagnosis | gpt:C47 / gem:C68 |
| K055 | Planroom provides a concrete boundary case. | 6 Discussion — Selection after diagnosis | gpt:C48 / gem:C70 |
| K056 | In principle, the same contract can cover documentation, diagnostic logs, browser text, and images. | 6 Discussion — Working with verbose external tools | gpt:C49 / gem:C72 |
| K057 | It shows that the method can continue implementing after context edits while retained history continues to grow. | 6 Discussion — Task pivots | gpt:C50 / gem:C77 |
| K058 | The cost result is compatible with reduced input outweighing cache disruption, but it does not identify the provider’s cache mechanics. | 6 Discussion — Cache and control | gpt:C51 / gem:C78 |
| K059 | More model decisions can coexist with lower total cost, as in OpenTelemetry, or with a small cost increase, as in Planroom. | 6 Discussion — Cache and control | gpt:C52 / gem:C79 |
| K060 | Curation frequency is consequently not a useful success metric on its own. | 6 Discussion — Cache and control | gpt:C53 / gem:ADD-C53 |

## Pairing notes

- **gpt:C42 / gem:C62** (score 89.1, below the 90 auto-accept threshold): same
  sentence ("Every method session has a smaller final prompt than every retained
  session, while cumulative usage overlaps."); Gemini's copy has an OCR-dropped
  space ("smallerfinal"). Confirmed a match by reading both; included above.
- **gpt:C23 / gem:C40** (no automatic score — fell below the 60 shortlist floor):
  same sentence ("These are resource savings without a speed advantage in this
  case."). Gemini's own inventory row is a garbled, strikethrough-marked PDF-table
  artifact (`C39<br>~~C40~~` with text `~~These are reso rce sa ings~~<br>~~itho t a
  speed ad antage in this case~~`). Checked with Nitin: the strikethrough is a
  rendering artifact of the source PDF's table extraction, not an edit mark — the
  cross-review document (`crossreview_chatgpt-on-gemini_2026-10-17.md`) itself
  confirms C40 is a separate, live claim and gives the restoration: "the table's
  text is garbled and clipped; the paper reads: 'These are resource savings
  without a speed advantage in this case.'" ChatGPT's clean sentence is used as
  the verbatim text above. The other merged row in Gemini's inventory
  (`C82<br>~~C83~~`) was checked the same way: both C82 and C83 are separate, live
  claims (confirmed by both cross-reviews treating them individually) — no
  content change needed there, since both ultimately end up in disputed_for_review
  (see below), not reconciled.

## Known gap — untraceable claim

- **Gemini's C18** (section "2 Related work — Retrieval and persistent-memory
  retention") has no legible text anywhere in either inventory file (its own row
  is blank/clipped in the source PDF) and ChatGPT's inventory has no claim in that
  subsection to cross-reference. It is part of Gemini's stated 81-claim revised
  total but its text cannot be recovered from any file this task is allowed to
  read. It appears in neither this file nor disputed_for_review.md — there is no
  sentence to show. Flagged here rather than silently dropped.

