```
### 1. Disagreements table
```

```
| item (their id / your id) | page | sentence (first 12 words) | issue |
decision | reason |
```

```
| --- | --- | --- | --- | --- | --- |
```

```
| - / C07 | 1 | After observing a tool result, the same model that performs the
task... | only-mine | Keep | It is a positioning claim (type b) explicitly
stating the method's capability. |
```

```
| - / C08 | 1 | This decision can use knowledge gained during diagnosis,
including the fact that... | only-mine | Keep | Asserts a premise/capability
that the authors' context curation relies on. |
```

```
| - / C12 | 2 | We study how this operation behaves in real coding and browser
trajectories... | only-mine | Keep | Contains a specific measured finding
("retained history exceeds 900,000 reported prompt tokens"). |
```

```
| - / C15 | 2 | Our evaluated operation targets selected tool outputs in the
current conversation, retaining... | only-mine | Keep | Positioning claim (type
b) contrasting their approach with memory tiers. |
| - / C16 | 2 | Our experiments use a prompted acting model without additional
training or a... | only-mine | Keep | Positioning claim (type b) highlighting
the lack of separate managers/training. |
```

```
| - / C17 | 2 | Our operation can select already completed results without
requiring a branch boundary. | only-mine | Keep | Positioning claim (type b)
about avoiding a structural requirement. |
```

```
| - / C18 | 3 | These systems manage retrieval candidates or persistent memory
representations, whereas our measured... | only-mine | Keep | Positioning claim
(type b) contrasting with persistent memory frameworks. |
```

```
| - / C19 | 3 | Our interface instead lets the acting model retrospectively
select individual tool results... | only-mine | Keep | Positioning claim (type
b) distinguishing their mechanism from compression policies. |
```

```
| - / C20 | 3 | Our contract preserves user, system and assistant messages and
returns exact archived... | only-mine | Keep | Method positioning and capability
guarantee (type b). |
```

```
| - / C21 | 3 | Our interface restricts edits to individual tool-result
occurrences, automatically archives exact originals... | only-mine | Keep |
Method positioning (type b) against fully editable contexts. |
```

```
| - / C23 | 3 | Post-exposure curation can additionally exploit conclusions
reached after inspection. | only-mine | Keep | Positioning (type b) explaining
the advantage over pre-exposure filters. |
```

```
| - / C24 | 4 | The trace preserves original observations independently of the
active representation. | only-mine | Keep | Asserts a method
guarantee/capability (type b). |
```

```
| - / C25 | 4 | This enables comparison of archived payloads against recorded
tool returns. | only-mine | Keep | States an audit capability enabled by the
authors' design (type b). |
```

```
| - / C26 | 5 | We measure the resulting usage and tariff estimate, without
assuming either perfect... | only-mine | Withdraw | This is an experimental
setup/accounting description, not a finding. |
```

```
| - / C27 | 6 | Neither condition reaches those limits. | only-mine | Withdraw |
An experimental sanity check, not a result of the agent's work. |
```

```
| - / C28 | 6 | Both baseline failure and gold success were checked. | only-mine
| Withdraw | Describes the validation of the evaluation instrument. |
| - / C29 | 6 | The baseline scores 0/6 and the reference 6/6. | only-mine |
Withdraw | Grader calibration result, not a finding of the tested method. |
| C16, C17 / C33, C34 | 7 | At primary submission the method carries 124,746
prompt tokens versus 847,674 for... | group | Reject theirs | The other reviewer
merged two separate result sentences into a single table cell. |
```

```
| C18 / C35 | 7 | The method peak is 381,299 versus 912,492 tokens. | verbatim |
Reject theirs | The other reviewer added a second trailing period ("tokens..").
|
```

```
| C29 / C46 | 8 | Conversely, retained passes ses the occupied-port startup-
failure probe with status 1; the... | verbatim | Reject theirs | The other
reviewer improperly corrected the "passes ses" text extraction artifact. |
| C31 / C48 | 8 | The frozen mixed grader reports 3/6 for method and 2/6 for
retained. | verbatim | Reject theirs | The other reviewer improperly wrapped the
```

```
fractions in LaTeX math delimiters. |
| C32 / C49 | 8 | Source inspection identifies false negatives in its static
checks: method calls server_ptr->Shutdown(...)... | verbatim | Reject theirs |
The other reviewer omitted the underscore in "server_ptr". |
```

```
| C36 / C56 | 8 | The archive verifies exact payload preservation while the
agent repeatedly curates context... | verbatim | Reject theirs | The other
reviewer incorrectly changed the semicolon after "working" to a colon. |
| - / C50 | 8 | Both candidates contain remaining-budget calculations. | only-
mine | Keep | Verified result of source code inspection. |
```

```
| - / C51 | 8 | Method's startup-failure branch joins a signal-waiting thread
without first arranging its termination... | only-mine | Keep | Verified result
of source code inspection. |
```

```
| - / C54 | 8 | Archived material includes large observability responses and
completed diagnostic or verification output. | only-mine | Keep | Measured
result characterizing what the agent archived. |
```

```
| C41 / C61 | 9 | The Sphinx batch contains two final 24/24 method outcomes and
one retained... | verbatim | Reject theirs | The other reviewer improperly
wrapped "24/24" in LaTeX math delimiters. |
```

```
| C43 / C63 | 9 | An earlier browser-based workflow-design continuation used 63%
fewer total tokens with the... | verbatim | Reject theirs | The other reviewer
improperly wrapped the fractions in LaTeX math delimiters. |
```

```
| C45 / C65 | 9 | An explicitly requested method-only repetition later scored
6/12. | verbatim | Reject theirs | The other reviewer improperly wrapped the
fraction in LaTeX math delimiters. |
```

```
| - / C67 | 10 | Large tool outputs can be necessary for discovering an
explanation but redundant... | only-mine | Keep | A foundational premise (type
d) that the authors' approach relies on. |
```

```
| - / C69 | 10 | If subsequent work is short, or if most observations remain
relevant, the... | only-mine | Keep | Positioning claim outlining the boundary
conditions for the method's value. |
```

```
| - / C71 | 10 | The retention operation acts on recorded observations, so an
upstream tool need... | only-mine | Keep | Positioning claim (type b)
contrasting with requiring tool compaction controls. |
```

```
| - / C73 | 10 | Its value depends on whether the agent can retain the useful
evidence... | only-mine | Keep | Positioning statement regarding the method's
core mechanism. |
```

```
| - / C74 | 10 | Filtering and curation can be combined: one limits initial
exposure, while the... | only-mine | Keep | Positioning claim (type b) about how
the methods stack. |
```

```
| - / C75 | 10 | For example, after a diagnosis is complete, the agent can
retain the... | only-mine | Withdraw | Describes a hypothetical use-case example
rather than an actual finding. |
```

```
| - / C76 | 10 | Batch selection permits a separate note for each result,
preserving the surrounding... | only-mine | Keep | Positioning (type b)
outlining benefits over single-summary approaches. |
```

```
| C53 / - | 10 | Curation frequency is consequently not a useful success metric
on its own. | only-theirs | Accept | A conclusion/finding derived directly from
the cost and cache analysis. |
```

```
| L35 / C80 | 10 | Our accounting includes reported cache usage; the different
workloads and models preclude... | label | Reject theirs (partially) | The
reviewer improperly truncated the first half of the sentence. I am withdrawing
my claim and adding the full verbatim sentence to limitations. |
```

```
| - / C81 | 10 | Protecting user messages prevents direct archival of the task
text. | only-mine | Keep | Method guarantee/premise. |
```

```
| L45 / C82 | 11 | Task trajectories also differ: retained Open Telemetry has
275 logical image occurrences... | label | Accept (withdraw mine) | The sentence
primarily bounds the attribution of the effect; moving to limitations. |
| L55 / C83 | 11 | Gold/baseline separation validates the instrument against its
reference candidates but does not... | label | Accept (withdraw mine) | The
sentence explicitly states a boundary of the validation instrument; moving to
limitations. |
```

```
| L05 / L07 | 3 | We have not benchmarked against pi-fold. | verbatim | Reject
theirs | The other reviewer incorrectly typed "pifold-" for "pi-fold.". |
```

```
### 2. Revised counts
```

- `**Total claim sentences:** 81` 

- `**Distinct claim groups:** 81` 

- `**Total limitation sentences:** 85` 

```
### 3. One line
```

```
I accepted 4 of the other reviewer's points (adding one missed claim and
reclassifying three to limitations) but rejected 38 of their points (primarily
due to numerous missed positioning claims and 10 unauthorized verbatim edits).
```

