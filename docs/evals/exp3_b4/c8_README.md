# Experiment 3 B4 - C8 claim-quality sheet

Columns:
- `id`: opaque row id.
- `paper_id`: which dev paper this row's sentence came from.
- `claim_text`: the pass-2 (or pass-1 control) sentence to label.
- `context`: ~300 chars of surrounding paper text, located the same way grounding does.
- `similar_1..3`: the 3 most similar other claims from the same paper's pool (text only).
- `label`: claim | not_claim | unsure.
- `reason` (only when label is not_claim or unsure): method_setup | background_related_work | number_no_assertion | other.
- `duplicate` (only when label is claim): yes | no - yes means same claim as one of similar_1..3.
- `note`: free text.

Label against the claim definition recorded in the B4 method entry in docs/decisions.md.
`unsure` counts as `not_claim` for c8.