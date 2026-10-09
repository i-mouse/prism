# Task

You will be given the full text of a research paper. Produce an inventory of the things the paper uses or compares, as a structured list. The inventory is a reference list for a later step; it is not an evaluation.

# What to list

One item per distinct entry, with a `kind`:

- `model`: each named model, system or model variant the paper runs, including every size or version listed separately (a family evaluated at three sizes is three items).
- `dataset`: each named dataset or benchmark.
- `task`: each distinct task or problem type the paper evaluates, when the paper names it as a task apart from its dataset.
- `baseline`: each method the paper compares against, including the ablated variants of its own method that it reports as comparison rows.
- `setting`: each named experimental configuration or condition: prompting style, shot count, data split, training regime, hardware tier, and similar.

# Rules

- Read the whole paper, appendices included. Be exhaustive: a missing item is worse than an extra one.
- `name` is the paper's own name for the item, as written. Do not rename, merge or generalise.
- `group` is the paper's own category for the item when it gives one (for example a table section heading such as "lightweight statistical baselines"). Use null when the paper gives none. Do not invent categories.
- Names only. Never include scores, percentages, counts of results, or any word that judges an item (better, worse, strong, weak, fails, wins).
- Do not decide what the paper's claims are, and do not drop an item because it seems minor.
- Ids are I1, I2, I3, ... in order of first appearance.

# Example (invented paper)

For a paper on a flood-forecasting system called Rivulet that is compared on two named catchment datasets against Persistence, Linear Regression and a published Operational Ensemble, and that is run in a nowcast-input setting and a no-nowcast setting, a correct inventory is:

I1 Rivulet (model, group null)
I2 Persistence (baseline, group "statistical baselines")
I3 Linear Regression (baseline, group "statistical baselines")
I4 Operational Ensemble (baseline, group "published systems")
I5 Ashgrove catchment (dataset, group null)
I6 Millbrook catchment (dataset, group null)
I7 Flood warning lead time (task, group null)
I8 Nowcast-input (setting, group null)
I9 No-nowcast (setting, group null)
