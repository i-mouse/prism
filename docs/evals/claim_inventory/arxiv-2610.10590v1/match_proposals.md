# Match proposals - arxiv-2610.10590v1

Matching/banding per docs/decisions.md's "Answer-key labelling and Phase B
method for 2610.10590v1 - 2026-10-18": fuzz.ratio >= 90 auto; fuzz.ratio
60-89 OR partial_ratio >= 90 borderline; else no match. One-to-one per arm,
greedy by score, matched against Key B (the 78-item superset answer key;
Key A's own numbers are a restriction of these same matches, applied at B2).

## Auto matches - pass1 (33)

| key sentence | pipeline sentence |
|---|---|
| Our contract preserves user, system and assistant messages and returns exact archived payloads on recovery. | Our contract preserves user, system and assistant messages and returns exact archived payloads on recovery. |
| A Python harness exposes batch archival and explicit recovery without task-specific model training, while protecting user instructions and assistant messages from these operations. | A Python harness exposes batch archival and explicit recovery without task-specific model training, while protecting user instructions and assistant messages from these operations. |
| In the central noisy debugging case, reversible curation accompanies a 75% smaller final measured prompt, 50% less cumulative input, and substantially lower estimated API cost, while both arms pass the same two primary behavioral cases. | In the central noisy debugging case, reversible curation accompanies a 75% smaller final measured prompt, 50% less cumulative input, and substantially lower estimated API cost, while both arms pass the same two primary behavioral cases. |
| An earlier browser-based workflow-design continuation used 63% fewer total tokens with the method but received a manual score of 4/12 versus 6/12 for retained. | An earlier browser-based workflow-design continuation used 63% fewer total tokens with the method but received a manual score of 4/12 versus 6/12 for retained. |
| In an exploratory OpenTelemetry debugging case followed by an unrelated implementation task, the method ended with 231,951 provider-reported prompt tokens versus 912,492 under retained history, used 50% fewer cumulative input tokens, and had an estimated API cost of $1.28–$1.44 versus approximately $4.38. | In an exploratory OpenTelemetry debugging case followed by an unrelated implementation task, the method ended with 231,951 provider-reported prompt tokens versus 912,492 under retained history, used 50% fewer cumulative input tokens, and had an estimated API cost of $1.28–$1.44 versus approximately $4.38. |
| Both arms passed the two-case primary behavioral oracle; neither fully satisfied the follow-up evaluation. | Both arms passed the two-case primary behavioral oracle; neither fully satisfied the follow-up evaluation. |
| The method made more requests and took 17% longer. | The method made more requests and took 17% longer. |
| A contrasting application-development pair produced no context or cost saving, and an earlier continuation exhibited lower manually assessed quality despite reduced context. | A contrasting application-development pair produced no context or cost saving, and an earlier continuation exhibited lower manually assessed quality despite reduced context. |
| These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload dependence as a central consideration for reversible context management. | These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload dependence as a central consideration for reversible context management. |
| Its potential benefit lies in reducing repeated input and leaving less obsolete material in subsequent requests. | Its potential benefit lies in reducing repeated input and leaving less obsolete material in subsequent requests. |
| Post-exposure curation gives the agent a further choice over continued retention without requiring changes to the source tool. | Post-exposure curation gives the agent a further choice over continued retention without requiring changes to the source tool. |
| The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors. | The central case demonstrates substantial reductions in active context and repeated input while preserving success on the tested primary behaviors. |
| Both arms submit both tasks normally, without recorded provider errors. | Both arms submit both tasks normally, without recorded provider errors. |
| Table 1 shows substantial reduction in active and cumulative input under the method despite more requests. | Table 1 shows substantial reduction in active and cumulative input under the method despite more requests. |
| At primary submission the method carries 124,746 prompt tokens versus 847,674 for retained, an 85% reduction. | At primary submission the method carries 124,746 prompt tokens versus 847,674 for retained, an 85% reduction. |
| After the follow-up, the method carries 231,951 versus 912,492 prompt tokens, a 75% reduction. | After the follow-up, the method carries 231,951 versus 912,492 prompt tokens, a 75% reduction. |
| The method peak is 381,299 versus 912,492 tokens. | The method peak is 381,299 versus 912,492 tokens. |
| Cumulative input decreases by 50%, and input plus completion tokens decrease by 50%. | Cumulative input decreases by 50%, and input plus completion tokens decrease by 50%. |
| The estimated cost is approximately 67–71% lower, even after reported cache usage is included. | The estimated cost is approximately 67–71% lower, even after reported cache usage is included. |
| The method generates more than twice as many completion tokens and takes 17% longer. | The method generates more than twice as many completion tokens and takes 17% longer. |
| Both primary candidates pass the two-case behavioral oracle. | Both primary candidates pass the two-case behavioral oracle. |
| For the follow-up, both candidates compile. | For the follow-up, both candidates compile. |
| The method exits with status 0 after SIGTERM in 8.43 seconds and after SIGINT in 8.85 seconds. | The method exits with status 0 after SIGTERM in 8.43 seconds and after SIGINT in 8.85 seconds. |
| Retained fails both probes and is killed with status 137. | Retained fails both probes and is killed with status 137. |
| Conversely, retained passes the occupied-port startup-failure probe with status 1; the method’s second process does not finish within 30 seconds. | Conversely, retained passes the occupied-port startup-failure probe with status 1; the method’s second process does not finish within 30 seconds. |
| The method therefore shows stronger tested signal handling but weaker tested startup-failure handling. | The method therefore shows stronger tested signal handling but weaker tested startup-failure handling. |
| The frozen mixed grader reports 3/6 for method and 2/6 for retained. | The frozen mixed grader reports 3/6 for method and 2/6 for retained. |
| In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters. | In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters. |
| All 26 archived text payloads and image lists match their recorded tool returns exactly. | All 26 archived text payloads and image lists match their recorded tool returns exactly. |
| Planroom yields no context or cost saving: the method ends with 6% more prompt tokens (283,105 versus 265,965) and uses less than 1% more total tokens (68,136,934 versus 67,669,624). | Planroom yields no context or cost saving: the method ends with 6% more prompt tokens (283,105 versus 265,965) and uses less than 1% more total tokens (68,136,934 versus 67,669,624). |
| Archival of 34 results removes only 69,685 net history characters; this does not offset the differing generated trajectories and method overhead. | Archival of 34 results removes only 69,685 net history characters; this does not offset the differing generated trajectories and method overhead. |
| The Sphinx batch contains two final 24/24 method outcomes and one retained 24/24 outcome. | The Sphinx batch contains two final 24/24 method outcomes and one retained 24/24 outcome. |
| Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps. | Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps. |

## Auto matches - raw_pass2 (17)

| key sentence | pipeline sentence |
|---|---|
| Gold/baseline separation validates the instrument against its reference candidates but does not eliminate these limits. | Gold/baseline separation validates the instrument against its reference candidates but does not eliminate these limits. |
| We study how this operation behaves in real coding and browser trajectories, including a case in which retained history exceeds 900,000 reported prompt tokens. | We study how this operation behaves in real coding and browser trajectories, including a case in which retained history exceeds 900,000 reported prompt tokens. |
| The method also requires more actions and time, and follow-up correctness remains incomplete. | The method also requires more actions and time, and follow-up correctness remains incomplete. |
| Our interface restricts edits to individual tool-result occurrences, automatically archives exact originals, and preserves user, system, and assistant messages. | Our interface restricts edits to individual tool-result occurrences, automatically archives exact originals, and preserves user, system, and assistant messages. |
| Contrasting application development and an adverse continuation show that neither resource savings nor quality preservation follows automatically from a smaller active history. | Contrasting application development and an adverse continuation show that neither resource savings nor quality preservation follows automatically from a smaller active history. |
| The practical result is that an agent can complete noisy tool-driven work with substantially less active context and repeated input, using explicit archival decisions during the task. | The practical result is that an agent can complete noisy tool-driven work with substantially less active context and repeated input, using explicit archival decisions during the task. |
| Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual tool-result occurrences, not a claim to invent agent-controlled memory. | Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual tool-result occurrences, not a claim to invent agent-controlled memory. |
| The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where the mechanism is useful. | The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where the mechanism is useful. |
| Human instructions therefore remain a verbatim task anchor under our context operations. | Human instructions therefore remain a verbatim task anchor under our context operations. |
| These are resource savings without a speed advantage in this case. | These are resource savings without a speed advantage in this case. |
| The archive verifies exact payload preservation while the agent repeatedly curates context and continues working; this pair does not test retrieval behavior because no recovery is requested. | The archive verifies exact payload preservation while the agent repeatedly curates context and continues working; this pair does not test retrieval behavior because no recovery is requested. |
| The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing difference. | The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing difference. |
| The original result therefore remains an observed quality loss alongside a resource saving. | The original result therefore remains an observed quality loss alongside a resource saving. |
| Protecting user messages prevents direct archival of the task text. | Protecting user messages prevents direct archival of the task text. |
| The OpenTelemetry archive illustrates that the agent can act on this distinction. | The OpenTelemetry archive illustrates that the agent can act on this distinction. |
| It shows that the method can continue implementing after context edits while retained history continues to grow. | It shows that the method can continue implementing after context edits while retained history continues to grow. |
| Curation frequency is consequently not a useful success metric on its own. | Curation frequency is consequently not a useful success metric on its own. |

## Auto matches - filtered_pass2 (15)

| key sentence | pipeline sentence |
|---|---|
| We study how this operation behaves in real coding and browser trajectories, including a case in which retained history exceeds 900,000 reported prompt tokens. | We study how this operation behaves in real coding and browser trajectories, including a case in which retained history exceeds 900,000 reported prompt tokens. |
| The method also requires more actions and time, and follow-up correctness remains incomplete. | The method also requires more actions and time, and follow-up correctness remains incomplete. |
| Our interface restricts edits to individual tool-result occurrences, automatically archives exact originals, and preserves user, system, and assistant messages. | Our interface restricts edits to individual tool-result occurrences, automatically archives exact originals, and preserves user, system, and assistant messages. |
| Contrasting application development and an adverse continuation show that neither resource savings nor quality preservation follows automatically from a smaller active history. | Contrasting application development and an adverse continuation show that neither resource savings nor quality preservation follows automatically from a smaller active history. |
| Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual tool-result occurrences, not a claim to invent agent-controlled memory. | Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual tool-result occurrences, not a claim to invent agent-controlled memory. |
| The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where the mechanism is useful. | The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where the mechanism is useful. |
| Human instructions therefore remain a verbatim task anchor under our context operations. | Human instructions therefore remain a verbatim task anchor under our context operations. |
| These are resource savings without a speed advantage in this case. | These are resource savings without a speed advantage in this case. |
| The archive verifies exact payload preservation while the agent repeatedly curates context and continues working; this pair does not test retrieval behavior because no recovery is requested. | The archive verifies exact payload preservation while the agent repeatedly curates context and continues working; this pair does not test retrieval behavior because no recovery is requested. |
| The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing difference. | The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing difference. |
| The original result therefore remains an observed quality loss alongside a resource saving. | The original result therefore remains an observed quality loss alongside a resource saving. |
| Protecting user messages prevents direct archival of the task text. | Protecting user messages prevents direct archival of the task text. |
| The OpenTelemetry archive illustrates that the agent can act on this distinction. | The OpenTelemetry archive illustrates that the agent can act on this distinction. |
| It shows that the method can continue implementing after context edits while retained history continues to grow. | It shows that the method can continue implementing after context edits while retained history continues to grow. |
| Curation frequency is consequently not a useful success metric on its own. | Curation frequency is consequently not a useful success metric on its own. |

## Borderline review (blind to arm, shuffled, seed 20261018)

**Borderline: 2**

No arm label and no scores are shown, to avoid anchoring the review. Mark
each row "match" or "no".

| id | key sentence | pipeline sentence | match / no |
|---|---|---|---|
| R001 | All 26 archived text payloads and image lists match their recorded tool returns exactly. | This enables comparison of archived payloads against recorded tool returns. | no |
| R002 | All 26 archived text payloads and image lists match their recorded tool returns exactly. | This enables comparison of archived payloads against recorded tool returns. | no |

