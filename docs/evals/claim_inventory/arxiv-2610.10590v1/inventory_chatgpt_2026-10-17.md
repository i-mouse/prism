RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

# **Research Claim Extraction Report** 

Paper: _Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice_ Source file: 2610.10590v1.pdf | 13 pages read 



<!-- Start of picture text -->
CLAIM SENTENCES DISTINCT GROUPS LIMITATIONS PAGES REVIEWED<br>58 58 61 13 / 13<br><!-- End of picture text -->

### **Included in this report** 

Section map; verbatim claim sentences with type, group, confidence, page and section; limitations classified separately; section and type counts; and borderline decisions with brief rationales. 

### **Review basis** 

The attached paper, _Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice_ (2610.10590v1.pdf), was read across all 13 pages, including the figure, tables, discussion, conclusion, and references. 

Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 1 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

## **1. Section map** 

|**Section**|**Start page**|
|---|---|
|Abstract|1|
|1 Introduction|1|
|2 Related work|2|
|Memory tiers and agent-directed editing|2|
|Learned management policies|2|
|Structured reduction and accumulated knowledge|2|
|Proactive folding and recoverable transcripts|3|
|Retrieval and persistent-memory retention|3|
|Compression policies and archival|3|
|Provider-side editing|3|
|Freely editable context|3|
|Positioning|3|
|3 Method|4|
|3.1 State and eligible operations|4|
|3.2 Integrity and protocol boundaries|4|
|3.3 Prompted selection|4|
|3.4 Resource accounting|5|
|4 Experimental design|5|
|4.1 Scope and development history|5|
|4.2 OpenTelemetry debugging and task pivot|5|
|4.3 Contrasting tasks|6|
|Planroom|6|
|Sphinx publication manifest|6|
|5 Results|7|
|5.1 OpenTelemetry resource use|7|
|5.2 Observed task quality|8|
|5.3 What was archived|8|
|5.4 Workload contrast and repeated pilot|9|
|5.5 Adverse and compromised observations|9|
|6 Discussion|10|
|Selection after diagnosis|10|
|Working with verbose external tools|10|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 2 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

|**Section**|**Start page**|
|---|---|
|Task pivots|10|
|Why retained history first, and context editing next|10|
|Cache and control|10|
|Protected instructions and remaining risks|10|
|7 Limitations and next experiments|11|
|8 Conclusion|11|
|9 Reproducibility, provenance, and disclosure|12|
|References|12|



## **2. Claims** 

Verbatim candidate claims classified under the supplied decision test. The sentence wording and claim identifiers follow the report above. 

|**id**|**page**|**section**|**type (a/b/c/d**|**) group**|**confidence**|**sentence (verbatim)**|
|---|---|---|---|---|---|---|
|C01|1|Abstract|c|G01|high|A Python harness exposes batch archival and explicit recovery without task-specific model training, while protecting<br>user instructions and assistant messages from these operations.|
|C02|1|Abstract|a|G02|high|In an exploratory OpenTelemetry debugging case followed by an unrelated implementation task, the method ended<br>with 231,951 provider-reported prompt tokens versus 912,492 under retained history, used 50% fewer cumulative<br>input tokens, and had an estimated API cost of $1.28–$1.44 versus approximately $4.38.|
|C03|1|Abstract|a|G03|high|Both arms passed the two-case primary behavioral oracle; neither fully satisfied the follow-up evaluation.|
|C04|1|Abstract|a|G04|high|The method made more requests and took 17% longer.|
|C05|1|Abstract|a|G05|high|A contrasting application-development pair produced no context or cost saving, and an earlier continuation exhibited<br>lower manually assessed quality despite reduced context.|
|C06|1|Abstract|c|G06|medium|These observations demonstrate substantial resource savings in noisy tool-use trajectories and identify workload<br>dependence as a central consideration for reversible context management.|
|C07|1|1 Introduction|b|G07|medium|Its potential benefit lies in reducing repeated input and leaving less obsolete material in subsequent requests.|
|C08|2|1 Introduction|b|G08|medium|Post-exposure curation gives the agent a further choice over continued retention without requiring changes to the<br>source tool.|
|C09|2|1 Introduction|c|G09|high|Our contribution is an implementation and exploratory evaluation of a restricted, auditable operation over individual<br>tool-result occurrences, not a claim to invent agent-controlled memory.|
|C10|2|1 Introduction|c|G10|high|The report contributes: (1) a concrete reversible tool-result contract with stable identifiers, in-place notes, protected<br>instruction messages, and atomic batch validation; (2) an independently graded debugging-and-pivot case with<br>provider usage and cache-aware cost accounting; and (3) contrasting and adverse observations that delimit where<br>the mechanism is useful.|
|C11|2|1 Introduction|c|G11|medium|The central case demonstrates substantial reductions in active context and repeated input while preserving success<br>on the tested primary behaviors.|
|C12|3|2 Related work — Freely<br>editable context|b|G12|medium|Human instructions therefore remain a verbatim task anchor under our context operations.|
|C13|7|5 Results — Figure 1|a|G13|high|Reversible curation reduces context in the noisy case, but not in every task|
|C14|7|5.1 OpenTelemetry resource use|a|G14|high|Both arms submit both tasks normally, without recorded provider errors.|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 3 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

|**id**|**page**|**section**|**type (a/b**|**/c/d) group**|**confidence**|**sentence (verbatim)**|
|---|---|---|---|---|---|---|
|C15|7|5.1 OpenTelemetry resource use|a|G15|high|Table 1 shows substantial reduction in active and cumulative input under the method despite more requests.|
|C16|7|5.1 OpenTelemetry resource use|a|G16|high|At primary submission the method carries 124,746 prompt tokens versus 847,674 for retained, an 85% reduction.|
|C17|7|5.1 OpenTelemetry resource use|a|G17|high|After the follow-up, the method carries 231,951 versus 912,492 prompt tokens, a 75% reduction.|
|C18|7|5.1 OpenTelemetry resource use|a|G18|high|The method peak is 381,299 versus 912,492 tokens.|
|C19|7|5.1 OpenTelemetry resource use|a|G19|medium|Thus, the observed comparison reaches a substantially larger retained context than the earlier coding tasks.|
|C20|7|5.1 OpenTelemetry resource use|a|G20|high|Cumulative input decreases by 50%, and input plus completion tokens decrease by 50%.|
|C21|7|5.1 OpenTelemetry resource use|a|G21|high|The estimated cost is approximately 67–71% lower, even after reported cache usage is included.|
|C22|8|5.1 OpenTelemetry resource use|a|G22|high|The method generates more than twice as many completion tokens and takes 17% longer.|
|C23|8|5.1 OpenTelemetry resource use|a|G23|high|These are resource savings without a speed advantage in this case.|
|C24|8|5.1 OpenTelemetry resource use|a|G24|high|The largest retained-context jump follows a 2,478,818-character browser_find result at primary step 74, three<br>requests before primary submission; the follow-up then carries the accumulated history through 44 further requests.|
|C25|8|5.2 Observed task quality|a|G25|high|Both primary candidates pass the two-case behavioral oracle.|
|C26|8|5.2 Observed task quality|a|G26|high|For the follow-up, both candidates compile.|
|C27|8|5.2 Observed task quality|a|G27|high|The method exits with status 0 after SIGTERM in 8.43 seconds and after SIGINT in 8.85 seconds.|
|C28|8|5.2 Observed task quality|a|G28|high|Retained fails both probes and is killed with status 137.|
|C29|8|5.2 Observed task quality|a|G29|high|Conversely, retained passes the occupied-port startup-failure probe with status 1; the method’s second process does<br>not finish within 30 seconds.|
|C30|8|5.2 Observed task quality|a|G30|high|The method therefore shows stronger tested signal handling but weaker tested startup-failure handling.|
|C31|8|5.2 Observed task quality|a|G31|high|The frozen mixed grader reports 3/6 for method and 2/6 for retained.|
|C32|8|5.2 Observed task quality|a|G32|high|Source inspection identifies false negatives in its static checks: method calls server_ptr->Shutdown(...) rather than<br>the expected server->Shutdown(...), and retained uses signalfd rather than the expected sigwait.|
|C33|8|5.3 What was archived|a|G33|high|The method makes five successful archival batches in the primary phase and four in the follow-up.|
|C34|8|5.3 What was archived|a|G34|high|In total, 26 results containing 2,247,229 text characters are represented by 9,709 note characters.|
|C35|8|5.3 What was archived|a|G35|high|All 26 archived text payloads and image lists match their recorded tool returns exactly.|
|C36|8|5.3 What was archived|a|G36|high|The archive verifies exact payload preservation while the agent repeatedly curates context and continues working;<br>this pair does not test retrieval behavior because no recovery is requested.|
|C37|9|5.4 Workload contrast and<br>repeated pilot|a|G37|high|Planroom yields no context or cost saving: the method ends with 6% more prompt tokens (283,105 versus 265,965)<br>and uses less than 1% more total tokens (68,136,934 versus 67,669,624).|
|C38|9|5.4 Workload contrast and<br>repeated pilot|a|G38|medium|Both arms support the twelve journeys at the available assessment resolution, with the gaps described above.|
|C39|9|5.4 Workload contrast and<br>repeated pilot|a|G39|high|Archival of 34 results removes only 69,685 net history characters; this does not offset the differing generated<br>trajectories and method overhead.|
|C40|9|5.4 Workload contrast and<br>repeated pilot|a|G40|high|The method completes in 24.29 rather than 31.78 minutes; this single pair does not isolate the cause of the timing<br>difference.|
|C41|9|5.4 Workload contrast and<br>repeated pilot|a|G41|high|The Sphinx batch contains two final 24/24 method outcomes and one retained 24/24 outcome.|
|C42|9|5.4 Workload contrast and<br>repeated pilot|a|G42|high|Every method session has a smaller final prompt than every retained session, while cumulative usage overlaps.|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 4 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

|**id**<br>C43|**page**<br>9|**section**<br>5.5 Adverse and compromised<br>observations|**type (a/b**<br>a|**/c/d) group**<br>G43|**confidence**<br>high|**sentence (verbatim)**<br>An earlier browser-based workflow-design continuation used 63% fewer total tokens with the method but received a<br>manual score of 4/12 versus 6/12 for retained.|
|---|---|---|---|---|---|---|
|C44|9|5.5 Adverse and compromised<br>observations|a|G44|high|Both answers had substantive state-machine errors.|
|C45|9|5.5 Adverse and compromised<br>observations|a|G45|high|An explicitly requested method-only repetition later scored 6/12.|
|C46|9|5.5 Adverse and compromised<br>observations|a|G46|high|The original result therefore remains an observed quality loss alongside a resource saving.|
|C47|10|6 Discussion — Selection after<br>diagnosis|c|G47|medium|The OpenTelemetry archive illustrates that the agent can act on this distinction.|
|C48|10|6 Discussion — Selection after<br>diagnosis|a|G48|medium|Planroom provides a concrete boundary case.|
|C49|10|6 Discussion — Working with<br>verbose external tools|b|G49|low|In principle, the same contract can cover documentation, diagnostic logs, browser text, and images.|
|C50|10|6 Discussion — Task pivots|a|G50|medium|It shows that the method can continue implementing after context edits while retained history continues to grow.|
|C51|10|6 Discussion — Cache and<br>control|a|G51|medium|The cost result is compatible with reduced input outweighing cache disruption, but it does not identify the provider’s<br>cache mechanics.|
|C52|10|6 Discussion — Cache and<br>control|a|G52|medium|More model decisions can coexist with lower total cost, as in OpenTelemetry, or with a small cost increase, as in<br>Planroom.|
|C53|10|6 Discussion — Cache and<br>control|b|G53|medium|Curation frequency is consequently not a useful success metric on its own.|
|C54|11|8 Conclusion|c|G54|medium|Agent-controlled forgetting provides an explicit way for a tool-using model to distinguish information it needed to<br>inspect from information it still needs to carry.|
|C55|11|8 Conclusion|a|G55|high|In the central noisy debugging case, reversible curation accompanies a 75% smaller final measured prompt, 50% less<br>cumulative input, and substantially lower estimated API cost, while both arms pass the same two primary behavioral<br>cases.|
|C56|11|8 Conclusion|a|G56|high|The method also requires more actions and time, and follow-up correctness remains incomplete.|
|C57|11|8 Conclusion|c|G57|medium|Contrasting application development and an adverse continuation show that neither resource savings nor quality<br>preservation follows automatically from a smaller active history.|
|C58|11|8 Conclusion|c|G58|medium|The practical result is that an agent can complete noisy tool-driven work with substantially less active context and<br>repeated input, using explicit archival decisions during the task.|



## **3. Limitations (not claims)** 

Sentences whose main point is a limitation, uncertainty, scope boundary, or unmeasured outcome. 

|**id**<br>**page**|**section**|**sentence (verbatim)**|
|---|---|---|
|L01<br>1|1 Introduction|The mechanism does not avoid the initial cost of reading a result.|
|L02<br>2|1 Introduction|A smaller prompt is also not a measurement of greater reasoning ability.|
|L03<br>2|2 Related work — Learned management policies|They do not compare against either learned system.|
|L04<br>2|2 Related work — Structured reduction and<br>accumulated knowledge|Maintaining reusable knowledge and reducing active observation payload are complementary goals; we do not evaluate that combination<br>here.|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 5 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

|**id**<br>**page**|**section**|**sentence (verbatim)**|
|---|---|---|
|L05<br>3|2 Related work — Proactive folding and<br>recoverable transcripts|We have not benchmarked against pi-fold.|
|L06<br>3|2 Related work — Provider-side editing|Our model-selected notes and explicit recovery interface are choices within this broader design space; no provider-side baseline is evaluated<br>here.|
|L07<br>3|2 Related work — Freely editable context|This preservation guarantee does not extend to a separate compaction process that summarizes those messages, nor does it guarantee<br>instruction compliance.|
|L08<br>3|2 Related work — Freely editable context|We have not compared against CLM.|
|L09<br>3|2 Related work — Positioning|Our retained-history comparator isolates a practical policy bundle, not the best available context-management baseline.|
|L10<br>3|2 Related work — Positioning|The targeted literature review does not establish novelty of the full combination of archival, notes, identifiers, and recovery.|
|L11<br>4|3.1 State and eligible operations|The active representation is lossy because a note need not preserve every detail.|
|L12<br>4|3.1 State and eligible operations|Reversibility refers to retrieval of the stored payload, not to lossless reasoning or preservation of every future decision dependency.|
|L13<br>4|3.2 Integrity and protocol boundaries|Such equality checks validate storage integrity; they do not validate the semantic adequacy of notes.|
|L14<br>5|3.3 Prompted selection|This percentage is neither an annotated dataset property nor an enforced classifier threshold.|
|L15<br>5|3.3 Prompted selection|It does not show that an unprompted base model spontaneously discovers a need to forget, and it does not involve parameter learning during<br>the experiment.|
|L16<br>5|3.4 Resource accounting|Prompt size includes the request representation and is an operational proxy for active context, not a direct measure of usable reasoning<br>capacity.|
|L17<br>5|3.4 Resource accounting|Wall time includes tool activity; it cannot identify a causal time-to-first-token effect.|
|L18<br>5|4.1 Scope and development history|The principal comparisons use one fresh session per condition, not a random sample of independent tasks.|
|L19<br>5|4.1 Scope and development history|Selecting the high-noise case after earlier experiments makes it a development-informed case study rather than a held-out confirmatory<br>benchmark.|
|L20<br>5|4.1 Scope and development history|The experiments are not pooled into an overall accuracy score: tasks, graders, histories, and harness versions differ.|
|L21<br>6|4.2 OpenTelemetry debugging and task pivot|The fraction of irrelevant material is not independently annotated.|
|L22<br>6|4.2 OpenTelemetry debugging and task pivot|Consequently, the follow-up compares full trajectories, not an identical-history intervention that isolates the effect of the pivot itself.|
|L23<br>6|4.2 OpenTelemetry debugging and task pivot|Passing those cases supports the tested error behavior, not exhaustive satisfaction of every prose requirement.|
|L24<br>6|4.2 OpenTelemetry debugging and task pivot|However, calibration on one reference cannot establish general grader validity: alternative correct implementations may fail static patterns,<br>and matching a pattern does not prove semantics.|
|L25<br>6|4.3 Contrasting tasks — Planroom|File-picker behavior and deliberate persistence-failure injection remain evaluation gaps.|
|L26<br>6|4.3 Contrasting tasks — Sphinx publication<br>manifest|Its different configuration prevents treatment as a replication of the final OpenTelemetry interface.|
|L27<br>6|4.3 Contrasting tasks — Sphinx publication<br>manifest|Cases within each grader share requirements and are not independent statistical samples.|
|L28<br>7|5 Results — Figure 1|These are individual trajectories, with no uncertainty bands.|
|L29<br>7|5 Results — Figure 1|The plotted endpoint is the input to the final response, not a post-answer context measurement.|
|L30<br>8|5.1 OpenTelemetry resource use|Because the arms encounter different observations and most primary implementation precedes this jump, the pair measures complete<br>retention trajectories rather than controlled exposure to identical noise.|
|L31<br>8|5.2 Observed task quality|The frozen grades are preserved, but their mixture of process probes and syntax-sensitive checks makes the individual runtime outcomes<br>more informative than the aggregate score.|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 6 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

|**id**<br>**page**|**section**|**sentence (verbatim)**|
|---|---|---|
|L32<br>9|5.5 Adverse and compromised observations|That repeat was selected after observing the weak answer and must not replace it or count as a balanced replication.|
|L33<br>9|5.5 Adverse and compromised observations|These failures explain subsequent harness changes and are not evidence of model degradation caused by context size.|
|L34<br>10|6 Discussion — Why retained history first, and<br>context editing next|This baseline is a priority for the next study and has not been evaluated in the present experiments.|
|L35<br>10|6 Discussion — Cache and control|The different workloads and models preclude a direct numerical comparison.|
|L36<br>10|6 Discussion — Protected instructions and<br>remaining risks|It does not ensure that the agent follows those instructions or preserves the evidence needed to satisfy them.|
|L37<br>10|6 Discussion — Protected instructions and<br>remaining risks|Notes can be incomplete, mistaken, or overly confident; the model may fail to notice when recovery is necessary.|
|L38<br>10|6 Discussion — Protected instructions and<br>remaining risks|Exact archive integrity addresses only one part of that problem.|
|L39<br>11|7 Limitations and next experiments|The principal limitation is sampling: one OpenTelemetry pair and one Planroom pair do not estimate the variance of the policy’s effect.|
|L40<br>11|7 Limitations and next experiments|The Sphinx batch has three sessions per arm but only one authored task and an older configuration.|
|L41<br>11|7 Limitations and next experiments|There is no preregistered held-out task distribution, no randomized OpenTelemetry order, and no evidence for a universal degradation<br>threshold.|
|L42<br>11|7 Limitations and next experiments|Confidence intervals over requests or individual grader cases would incorrectly treat dependent observations as independent replicates.|
|L43<br>11|7 Limitations and next experiments|No ablation separates these components, and no comparison tests provider-side context editing, a learned manager, chronological eviction,<br>summarization, or programmatic filtering.|
|L44<br>11|7 Limitations and next experiments|The experiments therefore establish neither superiority over other context-management systems nor novelty of the shared archival and<br>recovery design.|
|L45<br>11|7 Limitations and next experiments|Task trajectories also differ: retained OpenTelemetry has 275 logical image occurrences in requests while method has none.|
|L46<br>11|7 Limitations and next experiments|Provider usage is aggregate and does not expose a separate image-cost decomposition.|
|L47<br>11|7 Limitations and next experiments|We cannot attribute the entire between-arm resource difference to text archival alone.|
|L48<br>11|7 Limitations and next experiments|The archive audit establishes byte-exact preservation, not the sufficiency of every note or the dispensability of every removed result.|
|L49<br>11|7 Limitations and next experiments|With no recovery in the main pair, its effect on model decisions and the reliability of downstream retrieval remain unmeasured.|
|L50<br>11|7 Limitations and next experiments|The browser continuation also has different inherited histories and unblinded coarse grading.|
|L51<br>11|7 Limitations and next experiments|Smaller active context alone is not a measure of greater reasoning ability or a guarantee of preserved quality.|
|L52<br>11|7 Limitations and next experiments|Quality measurement is uneven.|
|L53<br>11|7 Limitations and next experiments|Shared checks and requirements make individual grader cases dependent; passing the two-case primary oracle does not establish complete<br>task correctness or statistical equivalence.|
|L54<br>11|7 Limitations and next experiments|Remaining-budget code in both follow-up solutions does not by itself establish a correct end-to-end timeout bound.|
|L55<br>11|7 Limitations and next experiments|Gold/baseline separation validates the instrument against its reference candidates but does not eliminate these limits.|
|L56<br>11|7 Limitations and next experiments|Before interpreting follow-up score differences as capability improvements, broader implementation-agnostic behavioral tests are needed.|
|L57<br>11|7 Limitations and next experiments|The system is evaluated through one provider model identifier.|
|L58<br>11|7 Limitations and next experiments|Provider-side checkpoint identity, inference hardware, cache internals, energy use, and training-data overlap with public repositories are<br>unavailable.|
|L59<br>11|7 Limitations and next experiments|Run-start configuration and tariffs are recorded, but exact model and environment determinism is not guaranteed.|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 7 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

|**id**|**page**|**section**|**sentence (verbatim)**|
|---|---|---|---|
|L60|11|7 Limitations and next experiments|The hosted inference figures exclude local build, browser, evaluation, and researcher labor costs.|
|L61|12|9 Reproducibility, provenance, and disclosure|We do not infer energy savings from token or price reductions.|



## **4. Counts** 

### **Claim sentences** 

**Total claim sentences: 58** 

### **Distinct claim groups** 

#### **Distinct claim groups: 58** 

Each claim sentence has a distinct group because the extracted statements either have different scopes or combine results in different ways. In particular, the paper sometimes reports an exact measurement, then restates the result as a percentage or a broader conclusion; those have been kept separate where the scope differs. 

### **Claims per section** 

|**Section**|**Claim sentences**|
|---|---|
|Abstract|6|
|1 Introduction|5|
|2 Related work|1|
|3 Method|0|
|4 Experimental design|0|
|5 Results|34|
|6 Discussion|7|
|7 Limitations and next experiments|0|
|8 Conclusion|5|
|9 Reproducibility, provenance, and disclosure|0|
|Total|58|



### **Claims per type** 

|**Type**|**Meaning**|**Count**|
|---|---|---|
|a|Result|44|
|b|Positioning|5|
|c|Contribution|9|
|d|Premise|0|
|Total||58|



Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 8 

RESEARCH CLAIM EXTRACTION REPORT  |  2610.10590v1.pdf 

### **Limitation sentences** 

**Total limitation sentences: 61** 

## **5. Borderline** 

- **C07** — “Its potential benefit lies…” is hedged, but asserts an expected benefit of the authors’ approach rather than merely describing implementation. 

- **C08** — “Post-exposure curation gives…” describes an intended capability and comparative advantage; it is not a direct experimental result. 

- **C12** — “Human instructions therefore remain…” asserts a protection guarantee. The paper describes an implementation guarantee, but the sentence does not independently establish instruction compliance. 

- **C19** — “The observed comparison reaches a substantially larger retained context…” is a comparison with earlier coding tasks, not a controlled comparison under the same conditions. 

- **C24** — The sentence reports observed trajectory details, but its main significance is explanatory rather than a general performance finding. 

- **C32** — The sentence reports a diagnosis of grader false negatives. It is a claim about the evaluation instrument, not about the agent’s task success. 

- **C36** — The sentence explicitly combines an archival-integrity result with a retrieval caveat. It remains a claim under the supplied decision rule because the result is not merely incidental. 

- **C38** — “Both arms support the twelve journeys…” is qualified by the assessment resolution and evaluation gaps, so the scope of “support” is deliberately limited. 

- **C39** — The sentence combines an archival measurement with a qualified interpretation about why it does not offset the differing trajectories and overhead. 

- **C48** — “Planroom provides a concrete boundary case” is a short interpretive statement. It is included because the preceding results are being used to delimit the method’s usefulness. 

- **C49** — “In principle…” is explicitly hedged. The paper does not demonstrate the same behavior across every listed tool-output type. 

- **C50** — The sentence describes a demonstrated continuation behavior, but the paper itself notes that an identical-history comparison would be needed to isolate the causal effect of curation at the task pivot. 

- **C51** — This is an interpretation of the cost result with an explicit caveat about unknown cache mechanics, so it is treated as a claim rather than moved wholly to the limitations table. 

- **C53** — “Curation frequency is consequently not a useful success metric on its own” is a general recommendation drawn from a small number of workload-specific observations. 

- **C57** — The sentence generalizes from a contrasting application-development pair and an adverse continuation. Its wording is cautious (“does not follow automatically”), but it remains a conclusion about the method. 

- **C58** — The phrase “an agent can complete” is broader than the individual experiments. The sentence is retained as the authors’ practical conclusion, with medium confidence because the paper’s own limitations preclude a universal claim. 

Source reviewed: the attached 13-page paper, 2610.10590v1.pdf. This PDF reproduces the full report content, tables, counts, and borderline notes. 

Source: Agent-Controlled Forgetting for Tool-Using Agents: Reversible Context Curation in Practice 

Page 9 

