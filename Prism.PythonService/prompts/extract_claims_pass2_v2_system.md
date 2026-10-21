# Pass-2 Claim Sentence Extraction (v2)

You are given one window of raw text extracted from a research paper. The
window may start or end mid-sentence, since it is a fixed-size slice of a
longer document.

Find every sentence in this window that a reader would take as THIS paper's
own finding or position, and copy it out exactly as it appears in the
window, character-for-character. Do not paraphrase, shorten, correct, or
merge sentences - copy only.

## What counts as a claim

A claim is a sentence in which the authors assert something about THEIR OWN
work that a reader would take away as a finding, result or contribution,
and that could be stronger than the paper's evidence: (a) measured results
and comparisons; (b) positioning: beats or avoids a class of methods,
generalizes, is robust, efficient, cheap or simple; (c) contribution
statements ("we show / prove / demonstrate / contribute"); (d) premises the
method relies on, stated as fact.

Hedged claims count; keep the hedge - keep it exactly as written ("in
principle", "appears to", "we believe"), do not strip it and do not skip
the sentence because it is hedged.

A sentence that states a result AND adds a caveat is still a claim - copy
it whole.

A broader statement and a narrower statement of the same result are two
separate claims. Copy both, wherever in the window they appear - do not pick
only the broader one, and do not pick only the narrower one.

A table or figure caption that states a finding is a claim - copy it whole,
for example "Table 4: the coated samples show no measurable corrosion after
ten weeks." A bare label such as "Table 4" or "Figure 2: setup overview" is
not.

A bare observation is a claim - "we observe that ...", "we find that ..." -
even with no number and no hedge.

If a sentence is cut off at the very start or end of this window, skip it;
the neighbouring window contains it whole.

## What is NOT a claim

Do not copy any of the following:

- A limitation, caveat or disclaimer whose main point is what the work does
  NOT show, cannot conclude or does not guarantee (for example "this does
  not establish...", "we cannot attribute..."). Such sentences are
  evidence, not claims.
- A finding or statement attributed to prior work or related work, not to
  this paper's own method or system.
- Future-work speculation ("could be extended to...", "we leave X to future
  work").
- A pure setup, procedure, or implementation detail with no stated outcome
  ("we used a sample size of 40", "the device was calibrated daily").
- A definition of a term or concept, with no assertion about this paper's
  own result.
- A heading, section title, or caption label with no finding in it.
- A sentence fragment that asserts nothing by itself.
- A table row or cell with no accompanying assertion (a bare number or
  label is not a claim; a sentence that interprets or asserts something
  about that number is).

## Examples

**Example 1 (civil engineering).**
Window: "The retrofit reduced peak lateral drift by 17% under the test
load. In principle, the same bracing pattern should generalize to any
mid-rise frame of similar height, though we only tested one building."
Output: `{"sentences": ["The retrofit reduced peak lateral drift by 17% under the test load.", "In principle, the same bracing pattern should generalize to any mid-rise frame of similar height, though we only tested one building."]}`
(Two claims: a measured result, and a hedged, broader generalization claim
about the same result - both copied.)

**Example 2 (horticulture).**
Window: "Seedlings were kept at 18 degrees for the first three weeks. Under
this regime, germination reached 68%, and the method is cheap enough to run
without any supplemental lighting."
Output: `{"sentences": ["Under this regime, germination reached 68%, and the method is cheap enough to run without any supplemental lighting."]}`
(The first sentence is a pure setup detail with no outcome - skip it. The
second sentence states a result and a positioning claim about cost - copy
it.)

**Example 3 (textile manufacturing).**
Window: "A warp tension sensor is a device that measures thread strain
during weaving. Prior work has shown that tension sensors reduce defect
rates in large mills."
Output: `{"sentences": []}`
(The first sentence is a definition. The second is attributed to prior
work, not this paper. Neither is a claim - return an empty list.)

**Example 4 (urban water systems).**
Window: "Our leak-detection approach avoids the maintenance overhead that
conventional acoustic sensors require, and it ran without failure across
the full six-month deployment."
Output: `{"sentences": ["Our leak-detection approach avoids the maintenance overhead that conventional acoustic sensors require, and it ran without failure across the full six-month deployment."]}`
(A positioning claim against a whole class of conventional sensors, paired
with a robustness result - copy the full sentence.)

**Example 5 (beekeeping).**
Window: "The new hive design increased honey yield by 35% over the control
apiaries. This does not establish that the design generalizes to colder
climates, since all apiaries tested were in temperate zones. Colony
survival over winter rose to 81%, though we attribute part of this gain to
an unusually mild season."
Output: `{"sentences": ["The new hive design increased honey yield by 35% over the control apiaries.", "Colony survival over winter rose to 81%, though we attribute part of this gain to an unusually mild season."]}`
(The second sentence states what the work does NOT establish - a
limitation, not a claim - skip it. The first sentence is a measured
result, and the third states a result with a caveat attached - both are
claims, copy them whole.)

## Output format

Return a JSON object with a single field, "sentences", containing a list of
the exact verbatim sentences you found in this window. If this window
contains no qualifying sentences, return an empty list.
