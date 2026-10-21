# Pass-2 Clean Filter

You are given a batch of candidate sentences copied from one research
paper by an earlier extraction pass, each with some surrounding context
and a short list of other sentences from the same paper ("neighbours")
that are textually similar to it. Your job is to judge each candidate on
its own, using its context, and to compare it against its listed
neighbours.

## Step 1: is this candidate the paper's own claim?

A claim is a sentence in which the authors assert something about THEIR OWN
work that a reader would take away as a finding, result or contribution,
and that could be stronger than the paper's evidence: (a) measured results
and comparisons; (b) positioning: beats or avoids a class of methods,
generalizes, is robust, efficient, cheap or simple; (c) contribution
statements ("we show / prove / demonstrate / contribute"); (d) premises the
method relies on, stated as fact.

Hedged claims count; keep the hedge - hedging is not a reason to say no.

A sentence that states a result AND adds a caveat is still a claim.

If the candidate is NOT a claim by this definition, set `is_paper_claim`
to false and pick the `reason_code` that best explains why:

- `limitation_or_caveat`: a limitation, caveat or disclaimer whose main
  point is what the work does NOT show, cannot conclude or does not
  guarantee (for example "this does not establish...", "we cannot
  attribute..."). Such sentences are evidence, not claims.
- `other_work`: a finding or statement attributed to prior or related work,
  not to this paper's own method or system.
- `future_work`: future-work speculation.
- `setup_or_method_detail`: a pure setup, procedure, or implementation
  detail with no stated outcome.
- `definition`: a definition of a term or concept, with no assertion about
  this paper's own result.
- `heading_or_fragment`: a heading, caption label, section title, or
  fragment that asserts nothing by itself.
- `other`: does not fit any of the above.

If the candidate IS a claim, set `is_paper_claim` to true and set
`reason_code` to `own_claim` for an (a)-type result claim, `positioning`
for a (b)-type positioning claim, `contribution` for a (c)-type
contribution statement, or `premise` for a (d)-type premise claim.

If you are unsure whether the candidate is a claim, set is_paper_claim to
true. Dropping a real claim is worse than keeping a weak one.

## Step 2: compare against each neighbour

For every neighbour listed, decide the relation between the candidate and
that neighbour:

- `same`: the two sentences say the same thing - same scope, same numbers
  (if any), same qualifiers and hedges. One is simply a different way of
  wording the other.
- `broader`: the candidate makes a more general or more sweeping version of
  the same underlying point than the neighbour does.
- `narrower`: the candidate makes a more specific or more cautious version
  of the same underlying point than the neighbour does.
- `different`: the two sentences are about different things, even if they
  share some words.

A broader statement and a narrower statement of the same result are NOT the
same claim - never mark that pair `same`. `same` requires matching scope,
matching numbers, and matching qualifiers, not just a related topic.

If you are unsure whether a relation is `same` or `broader`/`narrower`, do
not choose `same`. Choose `same` only when you are confident the two say
exactly the same thing.

## Output

For each candidate, in the order given, return an object with these fields
in this order:

- `reasoning`: one or two sentences explaining your judgment.
- `is_paper_claim`: true or false, per Step 1.
- `reason_code`: one of the codes above.
- `relations`: a list of `{"neighbour_id": ..., "relation": ...}`, one
  entry per listed neighbour, in the same order they were given.

## Examples

**Example 1 (dairy farming).**
Candidate: "Milk yield increased by 13% after the feed change." No
neighbours listed.
Output: `{"reasoning": "States a measured outcome of this paper's own intervention.", "is_paper_claim": true, "reason_code": "own_claim", "relations": []}`

**Example 2 (bridge inspection drones).**
Candidate: "A multirotor drone is an aircraft that uses several rotors to
generate lift." No neighbours listed.
Output: `{"reasoning": "Defines a term; no assertion about this paper's own result.", "is_paper_claim": false, "reason_code": "definition", "relations": []}`

**Example 3 (warehouse robotics).**
Candidate: "In principle, the routing method generalizes to any warehouse
layout, though we only tested two layouts." Neighbour N1: "The routing
method generalizes to any warehouse layout."
Output: `{"reasoning": "A hedged, narrower version of N1's broader generalization claim - same underlying point, different scope and hedge.", "is_paper_claim": true, "reason_code": "positioning", "relations": [{"neighbour_id": "N1", "relation": "narrower"}]}`

**Example 4 (solar panel coatings).**
Candidate: "After a year outdoors, efficiency of the film-coated panels fell
by just 3%." Neighbour N1: "Panels coated with the new film lost only 3%
efficiency after one year outdoors."
Output: `{"reasoning": "Different wording, but the same result, number, scope and qualifier as N1.", "is_paper_claim": true, "reason_code": "own_claim", "relations": [{"neighbour_id": "N1", "relation": "same"}]}`

**Example 5 (ceramics kiln firing).**
Candidate: "This does not establish that the glaze formula is stable at
higher firing temperatures, since all test batches used the same kiln
profile." No neighbours listed.
Output: `{"reasoning": "States what the work does not establish - a limitation on scope, not a finding about this paper's own result.", "is_paper_claim": false, "reason_code": "limitation_or_caveat", "relations": []}`
