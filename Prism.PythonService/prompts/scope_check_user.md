NEW TASK FOR THIS REQUEST. Ignore the verdict and output format in the system
instructions. Do not give a verdict on the claim. Answer only in the requested JSON.

You have the full paper above. Below is one claim from it and its scope items.
Each item says what must hold for the claim to cover its full reach.

CLAIM:
{{CLAIM}}

SCOPE ITEMS:
{{ITEMS}}

For each item, in the order given:
1. reported: search the whole paper: body text, tables, figure and table captions,
   footnotes and appendices. Copy every value or entry the paper reports for this
   item, fitting or not. Each entry is a verbatim quote copied character for
   character: the full sentence that states it, or for a table the whole row as it
   appears in the text. Never a bare number.
2. status: choose one.
   - matches: the paper reports entries for this item and every entry fits the
     claim's wording.
   - contradicted: at least one entry does not fit: fewer cases than the claim's
     count or quantifier covers, an exception, a member or setting where the
     result is absent, smaller or reversed, or only one side of a pair holds.
   - not_reported: the paper reports no entry for this item.
3. contradicting_quote: if contradicted, the one quote from your reported list that
   shows it most directly. Otherwise null.

Rules:
- When the paper gives both a summary (an average, a total, a stated count, a word
  such as "consistently") and the entries behind it, the entries decide.
- Judge each entry against the claim's own wording, including any hedge ("most",
  "typically", "up to"). An entry the hedge allows is not a contradiction.
- Something the paper does not report is not_reported, never contradicted.
- Quote only text that is in the paper. Never paraphrase inside a quote; never join
  text from different places into one quote.
