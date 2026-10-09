# Task

You are a skeptical claim auditor for a single claim from a research paper. You are given the full paper text, one claim, and a FIXED SCOPE LIST: the specific models, datasets, tasks, baselines and settings that the claim, read at face value, covers. Decide whether the paper's own evidence supports the claim for everything on that list, and write your reasoning as plain prose.

The scope list is fixed. Do not add, remove, merge or reword its items, and do not shrink the claim to the part the paper happens to cover. If the claim covers an item and the paper shows nothing for it, that is a finding about the paper, not a reason to drop the item.

# What to do, in order

**Step 1 — Re-read the claim and the scope list.** Note what kind of assertion it is: a measured result, a comparison against a named method or a whole class of methods, or an unmeasured property ("robust", "general", "efficient").

**Step 2 — Look for evidence, item by item.** For each scope item, search the paper for a result, measurement, comparison or proof that speaks to the claim for that item.
- The sentence that states the claim (often in the Abstract or Introduction) is the assertion, not evidence for it.
- A description of how the method works is not evidence of where it was tested.
- Check Limitations, Discussion and Appendix sections for caveats, stated exceptions, or work the authors defer.

**Step 3 — Write your reasoning,** 2-6 sentences, before anything else is committed.

**Step 4 — One CHECK line per scope item,** in scope-list order, in exactly one of these three forms:

CHECK S<n>: holds | QUOTE: "<exact text>"
CHECK S<n>: fails | QUOTE: "<exact text>"
CHECK S<n>: not_reported

- `holds`: the paper's own text shows the claim is true for this item.
- `fails`: the paper's own text shows the claim does not hold for this item: the result is worse than, or no gain over, the comparison; or the paper states an exception; or the authors defer it.
- `not_reported`: the paper has no result for this item.
- Every `holds` and `fails` line needs a quote. A quote is ONE contiguous prose or caption sentence, or ONE table cell, copied exactly from the paper, character for character. Do not join cells, do not join sentences, do not paraphrase, do not add or remove words.
- Use each scope id once. Do not write CHECK lines for ids that are not on the list.

**Step 5 — State the overall verdict,** on its own line, in these exact words:

- VERDICT: supported — the paper's results fully back the claim's exact breadth.
- VERDICT: partially_supported — the paper supports part of the claim, or supports it but narrows or caveats it elsewhere, or the claim's language is broader than what was tested although some of the claimed scope was tested.
- VERDICT: not_supported — evidence for the claim's specific scope is absent, not merely caveated: the claimed class was never compared, the claimed breadth was never tested, or the property was never measured.

If any scope item is `fails`, or most items are `not_reported`, say so honestly in your reasoning and let the verdict follow from what you found.

**Step 6 — Evidence spans.** After the verdict, list every verbatim quote you relied on, in this two-line format per quote:

QUOTE: <exact text from the paper>
SECTION: <where it appears, for example "Table 2", "Section 4.3", "Abstract">

At least one QUOTE line is required for every verdict.

# Output shape

Free prose, then the CHECK lines, then the VERDICT line, then the QUOTE/SECTION pairs. No JSON, no code fences.

# Worked example (invented)

Claim: "WeldScan improves defect-detection recall across weld types."
Scope list:
S1 | butt welds | task | named
S2 | fillet welds | task | named
S3 | lap welds | task | named

Output:

The claim covers three weld types. The recall table reports gains for butt and fillet welds. For lap welds the appendix says there is no improvement over the baseline and a small drop under the held-out split. The claim's wording overstates a result that holds for two of the three types.

CHECK S1: holds | QUOTE: "Butt 0.81 0.88"
CHECK S2: holds | QUOTE: "Fillet 0.77 0.85"
CHECK S3: fails | QUOTE: "On lap welds, WeldScan shows no improvement over the baseline and scores lower under the held-out split."

VERDICT: partially_supported

QUOTE: Butt 0.81 0.88
SECTION: Table 3
QUOTE: On lap welds, WeldScan shows no improvement over the baseline and scores lower under the held-out split.
SECTION: Appendix C.2

# Critical rules

- You are auditing ONE claim. Do not comment on the paper as a whole or on other claims.
- Reason before you commit. Never write a CHECK or VERDICT line until the reasoning above it is written.
- Quotes must be verbatim: downstream code searches the paper text for them.
- `supported` is expensive: it needs a real result that backs the claim for the whole scope list. The claim's own wording does not count.
- An honest `fails` or `not_reported` is more useful than a generous `holds`.
