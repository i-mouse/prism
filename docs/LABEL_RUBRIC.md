# Golden/Dev Label Rubric

Written marking scheme for a human labeller producing or checking Prism's
golden/dev rows (`docs/evals/matrix_eval.json` and future dev-set additions).
This is **not** an auditor prompt. Nothing here is referenced from
`prompts/`, and nothing here changes how Prism itself grades a claim — it
only governs how a human assigns the `expected_label` that Prism is then
measured against.

## 1. Definitions

**supported** — The paper's own results back the claim at least as
strongly as it is stated. A claim weaker than the evidence (e.g. says
"read" when the paper's own numbers show the stronger "touched") is still
`supported`, per the wording-gap rule [decisions.md:24]: a wording gap only
counts against a claim when the wording makes the claim *stronger* than the
evidence, never when it makes the claim weaker or exactly as strong.

**partially_supported** — Some real result backs the claim, but the
paper's own numbers or text contradict, or never test, part of its stated
scope. The core finding holds; a named or implied sub-case does not.

**not_supported** — No result in the paper bears on the claim's central
assertion: either the comparison it names was never run, or the scope it
generalizes to was never tested. This is different from
`partially_supported`: there, some real result backs part of the claim;
here, no result backs any of it.

## 2. Rules

### R1 — Hedged claims

**Principle:** A hedge word the paper itself used ("can", "potentially", "in
principle") keeps the claim's scope *small*. It never turns an untested
claim into `partially_supported` — a hedge narrows what is being claimed,
it does not manufacture evidence for it.

**Decided 2026-10-10.** A hedge is read literally as part of the claim's
scope, so it must be preserved rather than dropped before grading. But a
hedge by itself cannot rescue a generalization- or comparison-without-a-test
claim (R5) into `partially_supported` — the missing experiment is still
missing. Example: a paper hedges "this approach may in principle apply to
any similar task", but no experiment tests any task beyond the two it
reports on — the claim stays `not_supported`; the hedge narrows what's
claimed, but nothing tests even the hedged version. If a hedge is dropped
before grading (e.g. an intro hedges a number "by as much as X%" but a
later section repeats it unhedged), that is a text-fidelity defect: correct
the quoted/summarized text to keep the hedge, then re-apply R1/R3/R5 to the
corrected wording. It is not itself a reason to change the label.

### R2 — Scope source: summary vs. verbatim paper text

**Principle:** Scope comes from the paper's exact words
(`claim_text_verbatim`), never from a summary of them.

**Decided 2026-10-10.** `claim_summary` is display-only paraphrase; it
must never supply scope the verbatim text doesn't contain. Example: a
summary describes a method as working for "any agent", but the verbatim
sentence only says the method was proposed, with no scope word at all — the
summary's added scope is a drafting defect to fix in the summary text, not
grounds for changing the label either direction.

### R3 — Hidden losses: grade at the level the claim speaks about

**Principle:** Grade the claim at the level it names. An aggregate claim
("overall", "on average") is judged on the aggregate. A claim that says
"all", "every", or "consistently" is checked cell by cell against every
case it names. A loss visible in the paper's own numbers that the claim's
wording does not carve out caps the label at `partially_supported` —
regardless of how small the losing cell is, because "all/every/
consistently" is itself the claim being tested, not a rounding margin.

**Decided 2026-10-10: the strict, cell-by-cell reading applies.** Example:
a claim says a method "consistently outperforms" a baseline across a swept
parameter, but the paper's own chart shows one setting where it does not
win; that one setting is a cell the word "consistently" names and the
claim does not carve out, so R3 caps the row at `partially_supported`. Same
for a claim that says "all configurations outperform" a baseline when one
configuration in the paper's own results table does not. See "Known
implications for golden rows" below for which existing rows this reading
affects. Flipping any `expected_label` to match is a separate relabelling
pass, logged in `decisions.md` per section 3, not part of this rubric
document.

### R4 — Two numbers for the same baseline

**Principle, in three steps:**
(a) Check whether the two numbers are actually the same measurement (same
    subset, same metric, same reporting point) before treating it as a
    real conflict.
(b) If they truly conflict, grade the claim by the number at the place
    *that claim* cites.
(c) Log the discrepancy as a paper defect in `decisions.md`; do not resolve
    it in either number's favor.

### R5 — Never-tested comparisons or generalizations

**Drafted from existing labels.** A comparative claim that names a
comparison group the paper never ran against (Pattern 1), or a
generalization claim that extends beyond what was actually tested with
nothing in the paper bearing on the untested part (Pattern 2), is
`not_supported`, with `expected_evidence_sections: []` and
`grounding_negative: true`.

**Example:** a paper proposes a new method and frames it in the intro as
cheaper than conventional training, but never runs or measures a
conventional-training baseline to compare against — there is no comparison
to check at all, so the claim is `not_supported`.

No decision needed here — this rule is already applied consistently and
nothing contests it.

## 3. Change control

Change a label only where the paper contradicts it, never to move a score.
Log each change in `decisions.md` (row, old/new label, page, date). This
mirrors the standing rule already in force [decisions.md:1263-1266,
decisions.md:1315].

## 4. Row checklist

The labeller fills one row of this checklist per claim, before seeing any
Prism output:

claim text | section/page | deciding evidence (numbers) | label | rule
applied | confidence

## 5. Known implications for golden rows (not part of the rules)

Golden labels in `matrix_eval.json` stay frozen as the regression gate.
This rubric governs new dev rows going forward; it does not itself change
any `expected_label`. The notes below are a record of where applying these
rules to existing golden rows would disagree with the current label — kept
here for the next relabelling pass, not acted on now.

- **COT-M12** — currently `not_supported`, hedged "potentially... in
  principle". R1 reading is contestable; some tasks were tested; not
  relabelled.
- **REFLEX-M13** — summary language ("arbitrary") is broader than the
  verbatim claim text per R2; flagged as a summary drafting defect, label
  unchanged.
- **REFLEX-M09** — an intro hedge on a stated percentage versus an
  unhedged restatement elsewhere in the paper; flagged under R1 as a
  text-fidelity question, label unchanged.
- **COT-M10** — a hedged "can... given sufficient scale" claim; same R1
  text-fidelity question as REFLEX-M09, label unchanged.
- **REACT-M10** and **COT-M04** — logged as known inconsistencies with R3:
  both are currently `supported` on a "consistently"/"all" wording with a
  cell-level exception the claim doesn't carve out (sources: unverified —
  pending re-check against the primary figure/table). To be recorded in
  `decisions.md` if and when relabelled; not changed by this document.
- **REFLEX-M01** — rests on a baseline percentage that the paper also
  states differently elsewhere (R4); whether this is a same-measurement
  question or a genuine conflict is unverified and unresolved here.
