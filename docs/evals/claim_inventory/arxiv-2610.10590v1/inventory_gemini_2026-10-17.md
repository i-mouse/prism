SYSTEMATIC RESEARCH CLAIM & LIMITATION AUDIT 

# Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Target Paper: Jan-Peter Franke (arXiv:2610.10590v1 [cs.AI], 6 Oct 2026) • Total Pages Read: 13 



<!-- Start of picture text -->
13 Pages 88 Claims 82 Limitations 4 Categories<br>40 Mapped Headings 88 Distinct Groups (G01– Explicit Caveats (L01–L82) 55 (a) • 27 (b) • 5 (c) • 1 (d)<br>G88)<br><!-- End of picture text -->

## 1. Section Map 

Total pages read: 13 • All pages and sections readable 

Total pages read: 13. No pages or sections were unreadable or garbled (minor text-extraction artifacts such as passes ses on page 8 are preserved verbatim as extracted). 

|Section (Part 1)|Start<br>Page|Section (Part 2)|Start<br>Page|
|---|---|---|---|
|Abstract|1|4.3 Contrasting tasks|6|
|Introduction|1|4.3 Contrasting tasks—Planroom|6|
|2 Related work|2|4.3 Contrasting tasks—Sphinx publication|6|
|2 Related work—Memory tiers and agent-|2|manifest||
|directed editing||5 Results|7|
|2 Related work—Learned management policies|2|5.1 OpenTelemetry resource use|7|
|2 Related work—Structured reduction and<br>accumulated knowledge|2|5.2 Observed task quality|8|
|<br>2 Related work—Proactive folding and|3|5.3 What was archived|8|
|<br>recoverable transcripts||5.4 Workload contrast and repeated pilot|9|
|2 Related work—Retrieval and persistent-|3|5.5 Adverse and compromised observations|9|
|memory retention||6 Discussion|10|
|2 Related work—Compression policies and<br>archival|3|6 Discussion—Selection after diagnosis|10|
|2 Related work—Provider-side editing|3|6 Discussion—Working with verbose external<br>tools|10|
|2 Related work—Freely editable context<br>|3<br>|6 Discussion—Task pivots|10|
|2 Related work—Positioning|3|6 Discussion—Why retained historyfirst, and|10|
|3 Method|4|<br>context editing next||
|3.1 State and eligible operations|4|6 Discussion—Cache and control|10|
|3.2 Integrity and protocol boundaries|4|6 Discussion—Protected instructions and|10|
|3.3 Prompted selection|4|remaining risks||
|3.4 Resource accounting|5|7 Limitations and next experiments|11|
|4 Experimental design|5|8 Conclusion|11|
|4.1 Scope and development history|5|9 Reproducibility, provenance, and disclosure|12|
|4.2 OpenTelemetry debugging and task pivot|6|References|12|



Page 1 of 10 

Research Claim Audit Report • arXiv:2610.10590v1 

2. Claims (C01 – C18) 

Types: (a) Result, (b) Positioning, (c) Contribution, (d) Premise 

|ID|P<br>g|Section|Typ<br>e|Gro<br>up|Conf.|Sentence (verbatim)|
|---|---|---|---|---|---|---|
|C01|1|Abstract|b|G01|high|A Python harness exposes batch archival and explicit recovery<br>without task-specific model training, while protecting user<br>instructions and assistant messages from these operations.|
|C02|1|Abstract|a|G02|high|In an exploratory OpenTelemetry debugging case followed by an<br>unrelated implementation task, the method ended with 231,951<br>provider-reported prompt tokens versus 912,492 under retained<br>history, used 50% fewer cumulative input tokens, and had an<br>estimated API cost of $1.28-$1.44 versus approximately $4.38.|
|C03|1|Abstract|a|G03|high|Both arms passed the two-case primary behavioral oracle; neither<br>fully satisfied the follow-up evaluation.|
|C04|1|Abstract|a|G04|high|The method made more requests and took 17% longer.|
|C05|1|Abstract|a|G05|high|A contrasting application-development pair produced no context or<br>cost saving, and an earlier continuation exhibited lower manually<br>assessed quality despite reduced context.|
|C06|1|Abstract|c|G06|high|These observations demonstrate substantial resource savings in<br>noisy tool-use trajectories and identify workload dependence as a<br>central consideration for reversible context management.|
|C07|1|Introduction|b|G07|mediu<br>m|After observing a tool result, the same model that performs the task<br>can decide whether to keep that result verbatim or replace it with an<br>explicit note.|
|C08|1|Introduction|b|G08|mediu<br>m|This decision can use knowledge gained during diagnosis, including<br>the fact that a previously plausible cause has been ruled out or that<br>the user has moved to a different task.|
|C09|1|Introduction|b|G09|mediu<br>m|Its potential benefit lies in reducing repeated input and leaving less<br>obsolete material in subsequent requests.|
|C10|2|Introduction|b|G10|high|Post-exposure curation gives the agent a further choice over<br>continued retention without requiring changes to the source tool.|
|C11|2|Introduction|c|G11|high|Our contribution is an implementation and exploratory evaluation of<br>a restricted, auditable operation over individual tool-result<br>occurrences, not a claim to invent agent-controlled memory.|
|C12|2|Introduction|c|G12|high|We study how this operation behaves in real coding and browser<br>trajectories, including a case in which retained history exceeds<br>900,000 reported prompt tokens.|
|C13|2|Introduction|c|G13|high|The report contributes: (1) a concrete reversible tool-result contract<br>with stable identifiers, in-place notes, protected instruction<br>messages, and atomic batch validation; (2) an independently graded<br>debugging-and-pivot case with provider usage and cache-aware cost<br>accounting; and (3) contrasting and adverse observations that<br>delimit where the mechanism is useful.|
|C14|2|Introduction|a|G14|high|The central case demonstrates substantial reductions in active<br>context and repeated input while preserving success on the tested<br>primary behaviors.|
|C15|2|2 Related work—<br>Memory tiers and<br>agent-directed<br>editing|b|G15|mediu<br>m|Our evaluated operation targets selected tool outputs in the current<br>conversation, retaining a note at each original location.|
|C16|2|2 Related work—<br>Learned<br>management<br>policies|b|G16|mediu<br>m|Our experiments use a prompted acting model without additional<br>training or a separate manager.|
|C17|2|2 Related work—<br>Structured reduction|b|G17|high|Our operation can select already completed results without requiring<br>a branch boundary.|



Research Claim Audit Report • Section 2: Claims (C01–C18) 

Page 2 of 10 

Continued from previous page 

## 2. Claims (C19 – C41) 

|ID|P<br>g|Section|Typ<br>e|Gro<br>up|Conf.|Sentence (verbatim)|
|---|---|---|---|---|---|---|
|C19|3|2 Related work—<br>Compression<br>policies and archival|b|G19|high|Our interface instead lets the acting model retrospectively select<br>individual tool results and author their replacement notes.|
|C20|3|2 Related work—<br>Compression<br>policies and archival|b|G20|high|Our contract preserves user, system and assistant messages and<br>returns exact archived payloads on recovery.|
|C21|3|2 Related work—<br>Freely editable<br>context|b|G21|high|Our interface restricts edits to individual tool-result occurrences,<br>automatically archives exact originals, and preserves user, system,<br>and assistant messages.|
|C22|3|2 Related work—<br>Freely editable<br>context|b|G22|high|Human instructions therefore remain a verbatim task anchor under<br>our context operations.|
|C23|3|2 Related work—<br>Positioning|b|G23|mediu<br>m|Post-exposure curation can additionally exploit conclusions reached<br>after inspection.|
|C24|4|3.2 Integrity and<br>protocol boundaries|b|G24|mediu<br>m|The trace preserves original observations independently of the active<br>representation.|
|C25|4|3.2 Integrity and<br>protocol boundaries|b|G25|mediu<br>m|This enables comparison of archived payloads against recorded tool<br>returns.|
|C26|5|3.4 Resource<br>accounting|b|G26|mediu<br>m|We measure the resulting usage and tariff estimate, without<br>assuming either perfect cache preservation or complete cache loss.|
|C27|6|4.2 OpenTelemetry<br>debugging and task<br>pivot|a|G27|mediu<br>m|Neither condition reaches those limits.|
|C28|6|4.2 OpenTelemetry<br>debugging and task<br>pivot|a|G28|mediu<br>m|Both baseline failure and gold success were checked.|
|C29|6|4.2 OpenTelemetry<br>debugging and task<br>pivot|a|G29|mediu<br>m|The baseline scores 0/6 and the reference 6/6.|
|C30|7|5 Results|a|G30|high|Reversible curation reduces context in the noisy case, but not in<br>every task|
|C31|7|5.1 OpenTelemetry<br>resource use|a|G31|high|Both arms submit both tasks normally, without recorded provider<br>errors.|
|C32|7|5.1 OpenTelemetry<br>resource use|a|G32|high|Table 1 shows substantial reduction in active and cumulative input<br>under the method despite more requests.|
|C33|7|5.1 OpenTelemetry<br>resource use|a|G33|high|At primary submission the method carries 124,746 prompt tokens<br>versus 847,674 for retained, an 85% reduction.|
|C34|7|5.1 OpenTelemetry<br>resource use|a|G34|high|After the follow-up, the method carries 231,951 versus 912,492<br>prompt tokens, a 75% reduction.|
|C35|7|5.1 OpenTelemetry<br>resource use|a|G35|high|The method peak is 381,299 versus 912,492 tokens.|
|C36|7|5.1 OpenTelemetry<br>resource use|a|G36|high|Thus, the observed comparison reaches a substantially larger<br>retained context than the earlier coding tasks.|
|C37|7|5.1 OpenTelemetry<br>resource use|a|G37|high|Cumulative input decreases by 50%, and input plus completion<br>tokens decrease by 50%.|
|C38|7|5.1 OpenTelemetry<br>resource use|a|G38|high|The estimated cost is approximately 67-71% lower, even after<br>reported cache usage is included.|
|C39<br>~~C40~~|7<br>~~8~~|5.1 OpenTelemetry<br>resource use<br>~~5 1 OpenTelemetr~~|a<br>~~a~~|G39<br>~~G40~~|high<br>~~high~~|The method generates more than twice as many completion tokens<br>and takes 17% longer.<br>~~These are reso rce sa ings~~<br>~~itho t a speed ad antage in this case~~|



Research Claim Audit Report • Section 2: Claims (C19–C41) 

Page 3 of 10 

Continued from previous page 

## 2. Claims (C42 – C65) 

|ID|P<br>g|Section|Typ<br>e|Gro<br>up|Conf.|Sentence (verbatim)|
|---|---|---|---|---|---|---|
|C42|8|5.2 Observed task<br>quality|a|G42|high|Both primary candidates pass the two-case behavioral oracle.|
|C43|8|5.2 Observed task<br>quality|a|G43|high|For the follow-up, both candidates compile.|
|C44|8|5.2 Observed task<br>quality|a|G44|high|The method exits with status 0 after SIGTERM in 8.43 seconds and<br>after SIGINT in 8.85 seconds.|
|C45|8|5.2 Observed task<br>quality|a|G45|high|Retained fails both probes and is killed with status 137.|
|C46|8|5.2 Observed task<br>quality|a|G46|high|Conversely, retained passes ses the occupied-port startup-failure<br>probe with status 1; the method's second process does notfinish<br>within 30 seconds.|
|C47|8|5.2 Observed task<br>quality|a|G47|high|The method therefore shows stronger tested signal handling but<br>weaker tested startup-failure handling.|
|C48|8|5.2 Observed task<br>quality|a|G48|high|The frozen mixed grader reports 3/6 for method and 2/6 for retained.|
|C49|8|5.2 Observed task<br>quality|a|G49|high|Source inspection identifies false negatives in its static checks:<br>method calls server_ptr->Shutdown(...) rather than the expected<br>server->Shutdown(...), and retained uses signalfd rather than the<br>expected sigwait.|
|C50|8|5.2 Observed task<br>quality|a|G50|high|Both candidates contain remaining-budget calculations.|
|C51|8|5.2 Observed task<br>quality|a|G51|high|Method's startup-failure branch joins a signal-waiting thread without<br>first arranging its termination, consistent with the observed timeout.|
|C52|8|5.3 What was<br>archived|a|G52|high|The method makesfive successful archival batches in the primary<br>phase and four in the follow-up.|
|C53|8|5.3 What was<br>archived|a|G53|high|In total, 26 results containing 2,247,229 text characters are<br>represented by 9,709 note characters.|
|C54|8|5.3 What was<br>archived|a|G54|mediu<br>m|Archived material includes large observability responses and<br>completed diagnostic or verification output.|
|C55|8|5.3 What was<br>archived|a|G55|high|All 26 archived text payloads and image lists match their recorded<br>tool returns exactly.|
|C56|8|5.3 What was<br>archived|a|G56|high|The archive verifies exact payload preservation while the agent<br>repeatedly curates context and continues working; this pair does not<br>test retrieval behavior because no recovery is requested.|
|C57|9|5.4 Workload<br>contrast and<br>repeated pilot|a|G57|high|Planroom yields no context or cost saving: the method ends with 6%<br>more prompt tokens (283,105 versus 265,965) and uses less than 1%<br>more total tokens (68,136,934 versus 67,669,624).|
|C58|9|5.4 Workload<br>contrast and<br>repeated pilot|a|G58|high|Both arms support the twelve journeys at the available assessment<br>resolution, with the gaps described above.|
|C59|9|5.4 Workload<br>contrast and<br>repeated pilot|a|G59|high|Archival of 34 results removes only 69,685 net history characters;<br>this does not offset the differing generated trajectories and method<br>overhead.|
|C60|9|5.4 Workload<br>contrast and<br>repeated pilot|a|G60|high|The method completes in 24.29 rather than 31.78 minutes; this<br>single pair does not isolate the cause of the timing difference.|
|C61|9|5.4 Workload<br>contrast and<br>repeated pilot|a|G61|high|The Sphinx batch contains twofinal 24/24 method outcomes and<br>one retained 24/24 outcome.|
|C62|9|5.4 Workload|a|G62|high|Every method session has a smallerfinal prompt than every retained|



Research Claim Audit Report • Section 2: Claims (C42–C65) 

Page 4 of 10 

Continued from previous page 

## 2. Claims (C66 – C88) 

|ID|P<br>g|Section|Typ<br>e|Gro<br>up|Conf.|Sentence (verbatim)|
|---|---|---|---|---|---|---|
|C66|9|5.5 Adverse and<br>compromised<br>observations|a|G66|high|The original result therefore remains an observed quality loss<br>alongside a resource saving.|
|C67|10|6 Discussion—<br>Selection after<br>diagnosis|d|G67|mediu<br>m|Large tool outputs can be necessary for discovering an explanation<br>but redundant after that explanation is established.|
|C68|10|6 Discussion—<br>Selection after<br>diagnosis|a|G68|high|The OpenTelemetry archive illustrates that the agent can act on this<br>distinction.|
|C69|10|6 Discussion—<br>Selection after<br>diagnosis|b|G69|mediu<br>m|If subsequent work is short, or if most observations remain relevant,<br>the overhead of extra prompts, notes, and tool calls can outweigh the<br>reduction.|
|C70|10|6 Discussion—<br>Selection after<br>diagnosis|a|G70|mediu<br>m|Planroom provides a concrete boundary case.|
|C71|10|6 Discussion—<br>Working with<br>verbose external<br>tools|b|G71|high|The retention operation acts on recorded observations, so an<br>upstream tool need not expose its own compaction controls.|
|C72|10|6 Discussion—<br>Working with<br>verbose external<br>tools|b|G72|high|In principle, the same contract can cover documentation, diagnostic<br>logs, browser text, and images.|
|C73|10|6 Discussion—<br>Working with<br>verbose external<br>tools|b|G73|mediu<br>m|Its value depends on whether the agent can retain the useful<br>evidence after inspection, not merely on the size of a response.|
|C74|10|6 Discussion—<br>Working with<br>verbose external<br>tools|b|G74|mediu<br>m|Filtering and curation can be combined: one limits initial exposure,<br>while the other revisits retention as the task evolves.|
|C75|10|6 Discussion—Task<br>pivots|b|G75|high|For example, after a diagnosis is complete, the agent can retain the<br>finding and its source references while archiving the long<br>observations used to establish it.|
|C76|10|6 Discussion—Task<br>pivots|b|G76|high|Batch selection permits a separate note for each result, preserving<br>the surrounding conversation and access to the originals rather than<br>replacing the entire session with a single summary.|
|C77|10|6 Discussion—Task<br>pivots|a|G77|high|It shows that the method can continue implementing after context<br>edits while retained history continues to grow.|
|C78|10|6 Discussion—<br>Cache and control|a|G78|high|The cost result is compatible with reduced input outweighing cache<br>disruption, but it does not identify the provider's cache mechanics.|
|C79|10|6 Discussion—<br>Cache and control|a|G79|high|More model decisions can coexist with lower total cost, as in<br>OpenTelemetry, or with a small cost increase, as in Planroom.|
|C80|10|6 Discussion—<br>Cache and control|b|G80|mediu<br>m|Our accounting includes reported cache usage; the different<br>workloads and models preclude a direct numerical comparison.|
|C81|10|6 Discussion—<br>Protected<br>instructions and<br>remaining risks|b|G81|high|Protecting user messages prevents direct archival of the task text.|
|C82<br>~~C83~~|11<br>~~11~~|7 Limitations and<br>next experiments<br>~~7 Limitations and~~|a<br>~~a~~|G82<br>~~G83~~|mediu<br>m<br>~~mediu~~|Task trajectories also differ: retained Open Telemetry has 275 logical<br>image occurrences in requests while method has none.<br>~~Gold/baseline separation validates the instrument against its~~|



Research Claim Audit Report • Section 2: Claims (C66–C88) 

Page 5 of 10 

Not claims: explicit caveats, scope boundaries, and non-findings 

## 3. Limitations (L01 – L28) 

|ID|Pg|Section|Sentence (verbatim)|
|---|---|---|---|
|L01|1|Introduction|The mechanism does not avoid the initial cost of reading a result.|
|L02|2|Introduction|This motivates measuring context use, but does not imply a universal token<br>threshold at which an agent becomes unreliable.|
|L03|2|Introduction|A smaller prompt is also not a measurement of greater reasoning ability.|
|L04|2|2 Related work—Learned<br>management policies|They do not compare against either learned system.|
|L05|2|2 Related work—Structured<br>reduction and accumulated<br>knowledge|Maintaining reusable knowledge and reducing active observation payload are<br>complementary goals; we do not evaluate that combination here.|
|L06|3|2 Related work—Proactive<br>folding and recoverable<br>transcripts|Our interface targets individual tool-result occurrences selected by the acting model<br>and returns recovered payloads as new results; the shared use of briefs, external<br>originals, and recovery is not a novelty claim.|
|L07|3|2 Related work—Proactive<br>folding and recoverable<br>transcripts|We have not benchmarked against pi-fold.|
|L08|3|2 Related work—<br>Compression policies and<br>archival|ACM evaluates both an untrained management framework and a post-trained policy;<br>absence of task-specific training alone is therefore not a distinguishing feature.|
|L09|3|2 Related work—Provider-<br>side editing|Our model-selected notes and explicit recovery interface are choices within this<br>broader design space; no provider-side baseline is evaluated here.|
|L10|3|2 Related work—Freely<br>editable context|This preservation guarantee does not extend to a separate compaction process that<br>summarizes those messages, nor does it guarantee instruction compliance.|
|L11|3|2 Related work—Freely<br>editable context|We have not compared against CLM.|
|L12|3|2 Related work—<br>Positioning|This timing distinction does not imply thatfilters are intrinsically inferior: iterative<br>retrieval, query refinement, and programmatic processing can also adapt to task<br>state.|
|L13|3|2 Related work—<br>Positioning|Our retained-history comparator isolates a practical policy bundle, not the best<br>available context-management baseline.|
|L14|3|2 Related work—<br>Positioning|The targeted literature review does not establish novelty of the full combination of<br>archival, notes, identifiers, and recovery.|
|L15|4|3.1 State and eligible<br>operations|Recovery does not rerun the original tool: an archived browser page or test log<br>remains evidence of the earlier observation, not a fresh environmental<br>measurement.|
|L16|4|3.1 State and eligible<br>operations|The active representation is lossy because a note need not preserve every detail.|
|L17|4|3.1 State and eligible<br>operations|Reversibility refers to retrieval of the stored payload, not to lossless reasoning or<br>preservation of every future decision dependency.|
|L18|4|3.1 State and eligible<br>operations|Likewise, forgetting here is eviction from the active request, not deletion from<br>storage, model unlearning, or a privacy-erasure mechanism.|
|L19|4|3.2 Integrity and protocol<br>boundaries|Such equality checks validate storage integrity; they do not validate the semantic<br>adequacy of notes.|
|L20|4|3.2 Integrity and protocol<br>boundaries|The provider projection also handles API representation constraints, so preservation<br>of stored assistant responses should not be confused with byte-identical wire<br>serialization in every error case.|
|L21|5|3.3 Prompted selection|This percentage is neither an annotated dataset property nor an enforced classifier<br>threshold.|
|L22|5|3.3 Prompted selection|It does not show that an unprompted base model spontaneously discovers a need<br>to forget, and it does not involve parameter learning during the experiment.|
|L23|5|3.4 Resource accounting|The last prompt measurement precedes generation of thefinal submission; it is not|



Research Claim Audit Report • Section 3: Limitations (L01–L28) 

Page 6 of 10 

Continued from previous page 

## 3. Limitations (L29 – L55) 

|ID|Pg|Section|Sentence (verbatim)|
|---|---|---|---|
|L29|5|4.1 Scope and development<br>history|Selecting the high-noise case after earlier experiments makes it a development-<br>informed case study rather than a held-out confirmatory benchmark.|
|L30|5|4.1 Scope and development<br>history|The experiments are not pooled into an overall accuracy score: tasks, graders,<br>histories, and harness versions differ.|
|L31|6|4.2 OpenTelemetry<br>debugging and task pivot|The fraction of irrelevant material is not independently annotated.|
|L32|6|4.2 OpenTelemetry<br>debugging and task pivot|Consequently, the follow-up compares full trajectories, not an identical-history<br>intervention that isolates the effect of the pivot itself.|
|L33|6|4.2 OpenTelemetry<br>debugging and task pivot|Live telemetry, browsing choices, and generated code are not identical across<br>conditions.|
|L34|6|4.2 OpenTelemetry<br>debugging and task pivot|Nofixed provider sampling seed or explicit temperature is supplied in this runner.|
|L35|6|4.2 OpenTelemetry<br>debugging and task pivot|Passing those cases supports the tested error behavior, not exhaustive satisfaction<br>of every prose requirement.|
|L36|6|4.2 OpenTelemetry<br>debugging and task pivot|However, calibration on one reference cannot establish general grader validity:<br>alternative correct implementations may fail static patterns, and matching a pattern<br>does not prove semantics.|
|L37|6|4.2 OpenTelemetry<br>debugging and task pivot|Version 01 had a compromised follow-up build surface and an incompletely<br>specified primary error contract.|
|L38|6|4.2 OpenTelemetry<br>debugging and task pivot|A retained-only version-02 development episode exposed further deadline-contract<br>ambiguity.|
|L39|6|4.3 Contrasting tasks—<br>Planroom|Model-written test counts differ and are not comparable accuracy denominators.|
|L40|6|4.3 Contrasting tasks—<br>Planroom|File-picker behavior and deliberate persistence-failure injection remain evaluation<br>gaps.|
|L41|7|4.3 Contrasting tasks—<br>Sphinx publication manifest|Its different configuration prevents treatment as a replication of thefinal<br>OpenTelemetry interface.|
|L42|7|4.3 Contrasting tasks—<br>Sphinx publication manifest|Cases within each grader share requirements and are not independent statistical<br>samples.|
|L43|7|5 Results|These are individual trajectories, with no uncertainty bands.|
|L44|7|5 Results|The plotted endpoint is the input to thefinal response, not a post-answer context<br>measurement.|
|L45|8|5.1 OpenTelemetry resource<br>use|Because the arms encounter different observations and most primary<br>implementation precedes this jump, the pair measures complete retention<br>trajectories rather than controlled exposure to identical noise.|
|L46|8|5.2 Observed task quality|The frozen grades are preserved, but their mixture of process probes and syntax-<br>sensitive checks makes the individual runtime outcomes more informative than the<br>aggregate score.|
|L47|8|5.3 What was archived|No recovery is used in this pair, and no image payload is archived.|
|L48|9|5.4 Workload contrast and<br>repeated pilot|These six sessions characterize variation on one authored task under the older<br>configuration, rather than general non-inferiority.|
|L49|9|5.5 Adverse and<br>compromised observations|That repeat was selected after observing the weak answer and must not replace it<br>or count as a balanced replication.|
|L50|9|5.5 Adverse and<br>compromised observations|Earlier development also encountered step caps, truncated output, invalid historical<br>tool arguments, provider failures, and a faulty benchmark build surface.|
|L51|9|5.5 Adverse and<br>compromised observations|These failures explain subsequent harness changes and are not evidence of model<br>degradation caused by context size.|
|L52|10|6 Discussion—Selection<br>after diagnosis|Repeated input savings arise only after the initial exposure.|



Research Claim Audit Report • Section 3: Limitations (L29–L55) 

Page 7 of 10 

Continued from previous page 

## 3. Limitations (L56 – L82) 

|ID|Pg|Section|Sentence (verbatim)|
|---|---|---|---|
|L56|10|6 Discussion—Protected<br>instructions and remaining<br>risks|Notes can be incomplete, mistaken, or overly confident; the model may fail to notice<br>when recovery is necessary.|
|L57|10|6 Discussion—Protected<br>instructions and remaining<br>risks|Exact archive integrity addresses only one part of that problem.|
|L58|11|7 Limitations and next<br>experiments|The principal limitation is sampling: one OpenTelemetry pair and one Planroom pair<br>do not estimate the variance of the policy's effect.|
|L59|11|7 Limitations and next<br>experiments|The Sphinx batch has three sessions per arm but only one authored task and an<br>older configuration.|
|L60|11|7 Limitations and next<br>experiments|There is no preregistered held-out task distribution, no randomized Open Telemetry<br>order, and no evidence for a universal degradation threshold.|
|L61|11|7 Limitations and next<br>experiments|Confidence intervals over requests or individual grader cases would incorrectly treat<br>dependent observations as independent replicates.|
|L62|11|7 Limitations and next<br>experiments|No ablation separates these components, and no comparison tests provider-side<br>context editing, a learned manager, chronological eviction, summarization, or<br>programmaticfiltering.|
|L63|11|7 Limitations and next<br>experiments|The experiments therefore establish neither superiority over other context-<br>management systems nor novelty of the shared archival and recovery design.|
|L64|11|7 Limitations and next<br>experiments|These are repeated input occurrences, not 275 unique screenshots.|
|L65|11|7 Limitations and next<br>experiments|Provider usage is aggregate and does not expose a separate image-cost<br>decomposition.|
|L66|11|7 Limitations and next<br>experiments|We cannot attribute the entire between-arm resource difference to text archival<br>alone.|
|L67|11|7 Limitations and next<br>experiments|The archive audit establishes byte-exact preservation, not the sufficiency of every<br>note or the dispensability of every removed result.|
|L68|11|7 Limitations and next<br>experiments|With no recovery in the main pair, its effect on model decisions and the reliability of<br>downstream retrieval remain unmeasured.|
|L69|11|7 Limitations and next<br>experiments|The browser continuation also has different inherited histories and unblinded<br>coarse grading.|
|L70|11|7 Limitations and next<br>experiments|Smaller active context alone is not a measure of greater reasoning ability or a<br>guarantee of preserved quality.|
|L71|11|7 Limitations and next<br>experiments|Quality measurement is uneven.|
|L72|11|7 Limitations and next<br>experiments|The primary oracle covers two specific behaviors; the currency score combines<br>dynamic checks with syntax-sensitive static heuristics; Planroom includes trace-<br>based assessment; and the browser continuation is manually scored.|
|L73|11|7 Limitations and next<br>experiments|Shared checks and requirements make individual grader cases dependent; passing<br>the two-case primary oracle does not establish complete task correctness or<br>statistical equivalence.|
|L74|11|7 Limitations and next<br>experiments|Remaining-budget code in both follow-up solutions does not by itself establish a<br>correct end-to-end timeout bound.|
|L75|11|7 Limitations and next<br>experiments|Before interpreting follow-up score differences as capability improvements, broader<br>implementation-agnostic behavioral tests are needed.|
|L76|11|7 Limitations and next<br>experiments|The system is evaluated through one provider model identifier.|
|L77|11|7 Limitations and next<br>experiments|Provider-side checkpoint identity, inference hardware, cache internals, energy use,<br>and training-data overlap with public repositories are unavailable.|
|L78|11|7 Limitations and next|Run-start configuration and tariffs are recorded, but exact model and environment|



Research Claim Audit Report • Section 3: Limitations (L56–L82) 

Page 8 of 10 

## 4. Counts & Breakdown 

|Section (Claims > 0)|Claims|
|---|---|
|Abstract|6|
|Introduction|8|
|2 Related work—Memory tiers and agent-directed<br>editing|1|
|2 Related work—Learned management policies|1|
|2 Related work—Structured reduction and<br>accumulated knowledge|1|
|2 Related work—Retrieval and persistent-memory<br>retention|1|
|2 Related work—Compression policies and<br>archival|2|
|2 Related work—Freely editable context|2|
|2 Related work—Positioning|1|
|3.2 Integrity and protocol boundaries|2|
|3.4 Resource accounting|1|
|4.2 OpenTelemetry debugging and task pivot|3|
|5 Results|1|
|5.1 OpenTelemetry resource use|11|
|5.2 Observed task quality|10|
|5.3 What was archived|5|
|5.4 Workload contrast and repeated pilot|6|
|5.5 Adverse and compromised observations|4|
|6 Discussion—Selection after diagnosis|4|
|6 Discussion—Working with verbose external<br>tools|4|
|6 Discussion—Task pivots|3|
|6 Discussion—Cache and control|3|
|6 Discussion—Protected instructions and<br>remaining risks|1|
|7 Limitations and next experiments|2|
|8 Conclusion|5|



Quantitative summary of claims and limitations across the paper 

|Metric / Category|Count|
|---|---|
|Total claim sentences|88|
|Distinct claim groups|88|
|Type (a) RESULT|55|
|Type (b) POSITIONING|27|
|Type (c) CONTRIBUTION|5|
|Type (d) PREMISE|1|
|Total limitation sentences|82|



### Sections with 0 Claims (Verified) 

2 Related work (intro), 2 Related work — Proactive folding and recoverable transcripts, 2 Related work — Provider-side editing, 3 Method (intro), 3.1 State and eligible operations, 3.3 Prompted selection, 4 Experimental design (intro), 4.1 Scope and development history, 4.3 Contrasting tasks (intro, Planroom, Sphinx publication manifest), 6 Discussion (intro), 6 Discussion — Why retained history first, and context editing next, 9 Reproducibility, provenance, and disclosure, References. 

Page 9 of 10 

Research Claim Audit Report • Section 4: Counts & Breakdown 

Visual Distribution of Claims by Type 

Total = 88 Claims across 4 Categories 

Type (a) RESULT Type (b) POSITIONING 27 (30.7%) Type (c) CONTRIBUTION 5 (5.7%) Type (d) PREMISE 1 (1.1%) 

55 (62.5%) 

## 5. Borderline 

Items requiring close classification judgment 

- C07, C08, C09: Borderline between conceptual design description in the Introduction and positioning claims about what the acting model's post-exposure decision can leverage and achieve. 

- C15, C16, C18, C24, C25: Borderline between implementation/setup description and positioning claims contrasting the paper's auditable, training-free contract with prior work. 

- C27, C28, C29: Borderline between experimental setup checks and measured verification results of the benchmark runner and grading instruments. 

- C30: Appears as a bold banner/heading at the start of Section 5 (above Figure 1), but states a full sentence-level empirical finding ("Reversible curation reduces context in the noisy case, but not in every task"). 

- C56, C60, C78, C80, C83: Sentences that combine an empirical finding or method property with an explicit caveat; per the rules, mixing a result/positioning statement with a caveat makes the sentence a claim. 

- C67: Borderline between general domain motivation and a core premise (type d) that the method relies on to achieve token savings after diagnosis. 

- C82: Appears in Section 7 to explain a confounding factor, but states a concrete measured result from the trajectories (275 logical image occurrences in retained vs. 0 in method). 

- L06, L67: Both mention a feature or audit property ("returns recovered payloads as new results", "establishes byteexact preservation") while their main point is explicitly what the work does not claim or establish ("is not a novelty claim", "not the sufficiency of every note or the dispensability of every removed result"). 

Page 10 of 10 

Research Claim Audit Report • Section 5: Borderline 

