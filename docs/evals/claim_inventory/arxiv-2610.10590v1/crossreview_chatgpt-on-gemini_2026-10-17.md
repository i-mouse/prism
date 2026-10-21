```
1. Disagreements table
The attached audit PDF clips several table entries. For example, its claims
inventory jumps from C40 to C42 and from C62 to C66, and its limitations
inventory jumps from L23 to L29. Some advertised rows cannot be directly
adjudicated from the visible inventory.
Research Claim Audit Report.pdf
 Research Claim Audit Report.pdf
 Research Claim Audit Report.pdf
```

```
Item (their ID / my ID)PageSentence (first 12 words)IssueDecision
Reason
Their C01 / my C011A Python harness exposes batch archival and
explicit recovery without task-specific…labelWithdraw as a claim.This
describes implementation and protections; it reports no finding or evaluated
result. Neither type b nor type c is appropriate.
Their C07 / —1After observing a tool result, the same model that
performs the task…only-theirsNot a claim — setup/implementation. It
describes what the harness permits, not a result or contribution finding.
Their C08 / —1This decision can use knowledge gained during diagnosis,
including the fact…only-theirsAccept as claim, type b.It asserts that
post-exposure curation can use conclusions reached after inspecting evidence.
The hedge “can” does not exclude it.
Their C12 / —2We study how this operation behaves in real coding and
browser trajectories…only-theirsNot a claim — scope/setup.“We study”
describes the paper’s scope; the sentence does not itself state a finding.
Their C15 / —2Our evaluated operation targets selected tool outputs in
the current conversation…only-theirsNot a claim — implementation
description.It describes the unit of selection and where notes remain,
without asserting an evaluated outcome.
Their C16 / —2Our experiments use a prompted acting model without
additional training or…only-theirsNot a claim — experimental setup.It
identifies the model setup and absence of a separate manager.
Their C17 / —2Our operation can select already completed results
without requiring a branch boundary.only-theirsAccept as claim, type b.
It asserts a capability that distinguishes the interface from branch-
boundary-dependent approaches.
Their C19 / —3Our interface instead lets the acting model
retrospectively select individual tool results… only-theirsNot a claim —
implementation description.The sentence describes interface mechanics rather
than an outcome or evidence-backed comparison.
Their C20 / —3Our contract preserves user, system and assistant
messages and returns exact archived payloads…only-theirsNot a claim —
implementation description.It states the contract’s design. Exact
preservation is separately tested and reported in the Results section.
Their C21 / —3Our interface restricts edits to individual tool-result
occurrences, automatically archives exact originals…only-theirsNot a claim —
implementation description.It describes the interface boundaries and
mechanics, not an evaluated result.
Their C23 / —3Post-exposure curation can additionally exploit
conclusions reached after inspection.only-theirsAccept as claim, type b.
It asserts a capability of the proposed approach, with a different scope
from the narrower task-pivot examples.
Their C24 / —4The trace preserves original observations independently
of the active representation.only-theirsNot a claim — implementation
description.It describes how the trace is designed; the empirical archive-
integrity result is reported separately.
Their C25 / —4This enables comparison of archived payloads against
recorded tool returns.only-theirsNot a claim — method purpose.It states what
the trace makes possible, not a demonstrated finding.
Their C26 / —5We measure the resulting usage and tariff estimate,
without assuming either…only-theirsNot a claim — accounting method.It
describes how the paper calculates and reports usage.
Their C27 / —6Neither condition reaches those limits.only-theirsNot
a claim — experimental setup.It reports that configured limits were not
```

```
reached, rather than a finding about the method’s effectiveness.
Their C28 / —6Both baseline failure and gold success were checked.
only-theirsNot a claim — evaluation setup.It describes how the
evaluation instrument was checked.
```

```
Their C29 / —6The baseline scores 0/6 and the reference 6/6.only-
theirsAccept as claim, type a.These are concrete measured scores for
the paper’s evaluation instrument, which a reviewer can check against the
grading evidence.
Their C50 / —8Both candidates contain remaining-budget calculations.
only-theirsNot a claim — implementation description. It describes a code
property without asserting that the property works correctly or produces a
result.
```

```
Their C51 / —8Method’s startup-failure branch joins a signal-waiting
thread without first arranging its termination… only-theirsAccept as claim, type
a.It is a technical diagnosis tied to the observed timeout, not merely a
description of the intended implementation.
Their C54 / —8Archived material includes large observability responses
and completed diagnostic or verification output.only-theirsAccept as
claim, type a.In the Results section, this reports what the executed method
actually archived; it is a checkable observation.
Their C67 / —10Large tool outputs can be necessary for discovering an
explanation but redundant…only-theirsAccept as claim, type d.It states
the underlying premise motivating the distinction between initial exposure and
later retention.
```

```
Their C69 / —10If subsequent work is short, or if most observations
remain relevant…only-theirsAccept as claim, type b.It asserts a
conditional boundary on the method’s resource benefit; “can” does not make it
non-claim material.
Their C71 / —10The retention operation acts on recorded observations,
so an upstream tool need…only-theirsAccept as claim, type b.It
asserts an architectural advantage: the source tool need not provide its own
compaction controls.
Their C73 / —10Its value depends on whether the agent can retain the
useful evidence…only-theirsAccept as claim, type b.It makes an explicit
assertion about the condition determining the method’s usefulness.
Their C74 / —10Filtering and curation can be combined: one limits
initial exposure, while…only-theirsAccept as claim, type b.It
asserts compatibility between two context-management approaches, even though
their combination is not evaluated here.
Their C75 / —10For example, after a diagnosis is complete, the agent
can retain the finding…only-theirsAccept as claim, type b.The example
asserts a task-pivot capability of the method rather than an unrelated
hypothetical.
Their C76 / —10Batch selection permits a separate note for each result,
preserving the surrounding conversation…only-theirsAccept as claim, type b.
It claims that batch selection preserves context and recoverability
relative to replacing the whole session with one summary.
Their C80 / my L3510Our accounting includes reported cache usage; the
different workloads and models preclude…labelNot a claim; retain as a
limitation.The sentence’s main point is the limitation on numerical comparison.
Its first clause describes accounting practice, not a result that turns the
sentence into a claim.
```

```
Their C81 / —10Protecting user messages prevents direct archival of the
task text.only-theirsAccept as claim, type b.It asserts a specific
safeguard of the authors’ context operations.
Their C82 / my L4511Task trajectories also differ: retained
OpenTelemetry has 275 logical image occurrences…labelMove from limitations
to claim, type a.The sentence includes a concrete measured difference between
conditions and then explains it as a confound. Under the mixed-result rule, it
is a claim.
Their C83 / my L5511Gold/baseline separation validates the instrument
against its reference candidates but does not…labelMove from limitations to
claim, type a.It states a validation result and adds a caveat; the mixed-
result rule makes it a claim. The source sentence is truncated in their PDF
```

```
table.
```

```
My C24 / their C41 row not visible8The largest retained-context jump
follows a 2,478,818-character browser_find result at primary step…only-mine
Keep as claim.It reports a concrete, checkable event in the observed
trajectory. The corresponding part of the other PDF’s table is clipped, so its
classification cannot be confirmed.
My C43 / their C63 row not visible9An earlier browser-based workflow-
design continuation used 63% fewer total tokens…only-mineKeep as claim.
It reports a measured resource difference alongside a lower manual score.
The relevant row is not visible in the other PDF.
My C44 / their C64 row not visible9Both answers had substantive state-
machine errors.only-mineKeep as claim.It reports an observed quality
defect in both evaluated answers. The relevant row is not visible in the other
PDF.
My C45 / their C65 row not visible9An explicitly requested method-only
repetition later scored 6/12.only-mineKeep as claim.It reports a concrete
score from the selected repeat. The relevant row is not visible in the other
PDF.
My C53 / —10Curation frequency is consequently not a useful success metric
on its own.only-mineKeep as claim, type b.It is an explicit methodological
conclusion drawn from the different cost outcomes, not a bare implementation
description.
```

```
My C54 / their C84 row not visible11Agent-controlled forgetting provides
an explicit way for a tool-using model to distinguish…only-mineKeep as
claim.This is the conclusion’s central capability statement. The
corresponding row is not visible in the other PDF.
My C55 / their C85 row not visible11In the central noisy debugging case,
reversible curation accompanies a 75% smaller final…only-mineKeep as claim.
```

```
It summarizes measured results and the primary behavioral outcome. The
corresponding row is not visible in the other PDF.
```

```
My C56 / their C86 row not visible11The method also requires more actions
and time, and follow-up correctness remains incomplete.only-mineKeep as
claim, type a.It is a compact summary of observed resource and quality
outcomes. The corresponding row is not visible in the other PDF.
My C57 / their C87 row not visible11Contrasting application development
and an adverse continuation show that neither resource savings…only-mine
Keep as claim.It draws a paper-level conclusion from the contrasting
and adverse observations. The corresponding row is not visible in the other PDF.
My C58 / their C88 row not visible11The practical result is that an agent
can complete noisy tool-driven work…only-mineKeep as claim.This is
the authors’ practical conclusion about the demonstrated noisy-task case. The
corresponding row is not visible in the other PDF.
```

```
My C11 / their C142The central case demonstrates substantial
reductions in active context and repeated input…labelKeep as claim, but
change type from c to a.Its main point is an empirical result about
reductions and primary-task success, not the act of contributing the work.
Their C03 / my C03 and C251, 8Both arms passed the two-case primary
behavioral oracle; neither fully satisfied…groupKeep separate groups.The
abstract sentence also reports incomplete follow-up performance; the Results
sentence only reports primary-oracle success. Their scopes differ under the
stated grouping rule.
```

```
Their C021In an exploratory OpenTelemetry debugging case followed by an
unrelated implementation task…verbatimCorrect the cost-range
punctuation.The report uses $1.28-$1.44; the paper prints $1.28–$1.44.
Their C408These are reso rce sa ings itho t a speed ad antage in this
case.verbatimRestore the exact sentence.The table’s text is garbled and
clipped; the paper reads: “These are resource savings without a speed advantage
in this case.”
```

```
Their C468Conversely, retained passes ses the occupied-port startup-
failure probe with status…verbatimRemove the extra “ses”.The paper
reads: “Conversely, retained passes the occupied-port startup-failure probe with
status 1; the method’s second process does not finish within 30 seconds.”
Their C629Every method session has a smaller final prompt than every
retained…verbatimRestore the missing ending.The full paper sentence is:
```

```
“Every method session has a smaller final prompt than every retained session,
while cumulative usage overlaps.”
```

```
Their C8211Task trajectories also differ: retained Open Telemetry has 275
logical image occurrences…verbatimCorrect “Open Telemetry” to
“OpenTelemetry”.The paper uses “OpenTelemetry”.
Their C8311Gold/baseline separation validates the instrument against its
reference candidates but does not…verbatimRestore the complete sentence.
The paper reads: “Gold/baseline separation validates the instrument
against its reference candidates but does not eliminate these limits.”
My L35 / their C8010The different workloads and models preclude a
direct numerical comparison.verbatimRestore the complete sentence in my
limitations list.I cut off the first clause. The exact paper sentence is: “Our
accounting includes reported cache usage; the different workloads and models
preclude a direct numerical comparison.”
```

```
Their L235The last prompt measurement precedes generation of the final
submission; it is not…verbatimRestore the missing ending.The paper
continues: “an exact tokenization of the post-answer history.” This limitation
sentence was missing from my earlier list.
Their L7811Run-start configuration and tariffs are recorded, but exact
model and environment…verbatimRestore the missing ending.The paper
completes it with: “determinism is not guaranteed.”
Their C18, C41, C63–C65, C84–C88; L24–L28, L53–L55, L79–L82—Rows named in
the inventory headings but not legible in the attached PDF…verbatimCannot
adjudicate the missing rows themselves.The rows are clipped or absent from
the visible tables. I have kept my corresponding claims where the full sentence
is present in the source paper, without assuming what those unseen rows
contained.
```

```
Their L02 / —2This motivates measuring context use, but does not imply
a universal token threshold…only-theirsAccept as limitation.It explicitly
rules out inferring a universal degradation threshold from the cited motivation.
Their L06 / —3Our interface targets individual tool-result occurrences
selected by the acting model and returns… only-theirsAccept as limitation.Its
main point is that the shared use of briefs, external originals, and recovery is
not a novelty claim.
Their L08 / —3ACM evaluates both an untrained management framework and
a post-trained policy; absence…only-theirsAccept as limitation.It limits
novelty claims based on lack of task-specific training.
Their L12 / —3This timing distinction does not imply that filters are
intrinsically inferior: iterative retrieval…only-theirsAccept as limitation.
It explicitly cautions against an unsupported general superiority claim
over filtering.
Their L15 / —4Recovery does not rerun the original tool: an archived
browser page or test…only-theirsAccept as limitation.It limits what a
recovered result can establish about the current environment.
Their L18 / —4Likewise, forgetting here is eviction from the active
request, not deletion from…only-theirsAccept as limitation.It explicitly
limits the meaning of “forgetting” and rules out privacy erasure.
Their L20 / —4The provider projection also handles API representation
constraints, so preservation of stored assistant…only-theirsAccept as
limitation.It cautions that stored-response preservation does not guarantee
byte-identical wire serialization in every error case.
Their L33 / —6Live telemetry, browsing choices, and generated code are
not identical across conditions.only-theirsAccept as limitation.Different
trajectories constrain causal attribution to the context-curation operation
alone.
```

```
Their L34 / —6No fixed provider sampling seed or explicit temperature
is supplied in this runner.only-theirsAccept as limitation.It limits
reproducibility and deterministic interpretation of the comparison.
Their L37 / —6Version 01 had a compromised follow-up build surface and
an incompletely specified primary…only-theirsNot a limitation sentence —
development history/setup.It describes an earlier version’s state; it does
not itself state what the final study cannot establish.
Their L38 / —6A retained-only version-02 development episode exposed
further deadline-contract ambiguity.only-theirsNot a limitation sentence —
```

```
development history/setup.It reports a prior development episode rather than
a limitation of the final comparison.
Their L39 / —6Model-written test counts differ and are not comparable
accuracy denominators.only-theirsAccept as limitation.It explicitly limits
how Planroom test counts may be interpreted.
Their L47 / —8No recovery is used in this pair, and no image payload
is archived.only-theirsAccept as limitation.It identifies a scope
boundary: the main pair does not exercise recovery and does not evaluate image-
payload archival.
Their L48 / —9These six sessions characterize variation on one
authored task under the older configuration…only-theirsAccept as limitation.
It explicitly rules out interpreting the six sessions as general non-
inferiority evidence.
Their L50 / —9Earlier development also encountered step caps,
truncated output, invalid historical tool arguments…only-theirsNot a
limitation sentence — development history/setup.It inventories past
development failures; the following sentence makes the explicit limitation about
causation.
Their L52 / —10Repeated input savings arise only after the initial
exposure.only-theirsAccept as limitation.It bounds the method’s savings:
it cannot avoid the initial cost of reading the result.
Their L64 / —11These are repeated input occurrences, not 275 unique
screenshots.only-theirsAccept as limitation.It restricts the
interpretation of the image-occurrence count.
Their L72 / —11The primary oracle covers two specific behaviors; the
currency score combines dynamic checks…only-theirsAccept as limitation.It
identifies limits in what the paper’s different quality measurements establish.
— / —12Archival preserves information rather than erasing it, and a
deployed system must account…both-missedAdd as limitation.This is an
explicit warning about persistence and sensitive inputs, present in the
disclosure section.  2610.10590v1.pdf
```

```
— / —12AI assistance was also used in experiment construction and analysis,
so author review…both-missedAdd as limitation.The authors explicitly say
the interpretation and evaluation code requires review before submission.
2610.10590v1.pdf
```

`2. Revised counts` 

```
- Total claim sentences: 72
```

- `Distinct claim groups: 72` 

- `Total limitation sentences: 77` 

`3. Other reviewer points accepted/rejected` 

```
Among the 30 readable sentences they placed in their Claims table that I omitted
or classified differently, I accept 16 as claims and reject 14 as claims; the
rejected C80 sentence is retained as a limitation instead. The clipped rows in
the supplied PDF are not included in that tally.
```

