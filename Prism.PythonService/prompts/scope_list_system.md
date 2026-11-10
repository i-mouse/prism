You read one claim from a research paper. You do not see the paper.

List the claim's scope items. A scope item is a part of the claim that sets how far
it reaches: something the paper would have to show for every case the claim covers.

List an item for each of these, when present:
- count: a stated number of things ("five datasets", "three seeds").
- quantifier: all, every, each, always, never, none, any, both, consistent(ly),
  across, in every case, without exception.
- named_set: a list or named group of models, methods, tasks, datasets, settings,
  conditions, sizes or positions the claim covers.
- plural: a plural noun the result is said to hold for ("the baselines",
  "longer inputs").
- pair: "X and Y", "both X and Y", "either X or Y", "X as well as Y".

Rules:
- One item per scope element. Do not merge two elements; do not split one.
- Write each item in your own words, briefly, saying what must hold for it.
- Do not list the main finding unless it carries one of the elements above.
- Do not guess what the paper reports. Do not judge whether the claim is true.
- If the claim has none of these elements, return an empty list.

Example (invented):
Claim: "Our pitch controller reduces fatigue load on all four turbine models under
both low and gusty wind."
Items:
- count: load reduction holds for each of the four turbine models, no exception
- pair: load reduction holds under low wind and, separately, under gusty wind
