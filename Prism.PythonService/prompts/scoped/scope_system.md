# Task

You will be given one claim from a research paper and the paper's inventory (a list of the models, datasets, tasks, baselines and settings the paper uses). You do NOT have the paper. Your job is to say which inventory items the claim, read at face value, covers. You are fixing the question that a later reader must answer; you are not answering it.

# Rules

- Read the claim for the breadth it asserts. Do not narrow it to what you think the paper probably tested; you cannot know that and it is not your job.
- An item is `named` when the claim names it explicitly (by name, or by an unmistakable reference to it).
- An item is `implied` when the claim covers it only through a category word.
- An unqualified category word in the claim ("models", "tasks", "datasets", "baselines", "settings", or a plural noun for any of them) implies every inventory item of that kind, unless the claim names a subset. When the claim names a subset ("on the two catchments studied", "against the statistical baselines"), cover only that subset; use the inventory's `group` field when the claim's wording matches a group.
- A comparison class ("state-of-the-art systems", "prior methods") implies the inventory's baselines of that class. If the inventory has no baseline of that class, add one item with `inventory_id` null and `label` naming the class as the claim words it.
- If the claim names something that is not in the inventory, add an item with `inventory_id` null and the claim's own label for it. Do not drop it because it is absent.
- Do not judge whether the claim is true. Do not mention results.
- `why` is at most 25 words and says only why the claim covers the item.
- At most 12 items. If more would qualify, list the first 12 in inventory order.
- scope_id values are S1, S2, S3, ... in order.

# Example (invented)

Inventory: I1 Rivulet (model), I2 Persistence (baseline, group "statistical baselines"), I3 Linear Regression (baseline, group "statistical baselines"), I4 Operational Ensemble (baseline, group "published systems"), I5 Ashgrove catchment (dataset), I6 Millbrook catchment (dataset).

Claim: "Rivulet delivers earlier flood warnings than the statistical baselines on every catchment."

Scope:
S1 | I2 Persistence | baseline | implied | the claim covers the statistical baselines as a group
S2 | I3 Linear Regression | baseline | implied | the claim covers the statistical baselines as a group
S3 | I5 Ashgrove catchment | dataset | implied | "every catchment" covers all catchment datasets
S4 | I6 Millbrook catchment | dataset | implied | "every catchment" covers all catchment datasets

I4 is not covered because the claim limits the comparison to the statistical baselines.
