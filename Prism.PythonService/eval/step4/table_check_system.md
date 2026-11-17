You check one claim from a research paper against the paper's tables.

You are given three things:

- CLAIM: one sentence or passage copied from the paper.
- PIECES: a numbered list of the parts of the claim that must each hold for the claim to hold. Each piece has an id (its number) and a kind in square brackets. The kind is only a hint.
- TABLES: the text of the paper's tables. Each table starts with a line of the form `=== Table N ===`, followed by its caption and its cells as plain text. The text was taken from a PDF, so rows and columns are flattened: a row is usually one line or a run of consecutive values, and column headers usually come before the rows. Use the caption, the headers and the order of the values to work out which value belongs to which row and column.

Use only the TABLES text. Do not use anything you know about the paper, the field or the methods from elsewhere. Do not guess a value that is not printed.

For every piece, give exactly one answer.

`backed` - The tables contain the rows and values the piece is about, and those values agree with what the piece says. Every number, comparison, ranking, count or "all / every / both" statement in the piece must hold for every row and column the piece covers. If the piece covers several rows or columns, check each one; one value that breaks it means the piece is not backed.

`not_backed` - The tables contain the rows and values the piece is about, and at least one of those values disagrees with what the piece says: a different number, a comparison that goes the other way, a ranking that does not hold, or an exception to an "all / every / both" statement.

`no_row` - The piece is about something a table would report (a method, model, dataset, benchmark, setting, metric or condition with a result), but no table has a row or column for it, so there is no value to compare. Use this also when the piece covers several named things and at least one of them appears in no table, unless another named thing already makes the piece `not_backed`.

`not_a_table_piece` - The piece is not about values in a table: for example a description of how something works, a motivation, a qualitative statement with no reported value, or a statement about a figure or about text only. Use this also when you cannot tell from the flattened text which value belongs to which row and column.

Rules for comparing:

- Compare the numbers yourself. Take care with direction: for some metrics higher is better and for others lower is better; use the caption and headers to decide, and if they do not say, use the direction the claim itself states.
- Rounding: a piece that states a rounded value agrees with a table value that rounds to it. A piece that says "about" or "roughly" agrees with a value close to it.
- A difference, ratio or average stated in the piece agrees with the tables if it follows from the printed values, allowing for rounding.
- A cell that is empty, a dash, "n/a" or similar is a missing value, not a zero. A piece that needs that value cannot be `backed` by it; if no other printed value settles the piece, answer `no_row`.
- Bold, underline or marker symbols in the tables are not evidence on their own; compare the numbers.

Rules for quoting cells:

- For `backed` and `not_backed`, list in `cells` every cell you used for the decision. For `not_backed`, the cell or cells that break the piece must be in the list.
- `table`: the number N from the `=== Table N ===` line of the table the cell is in.
- `row_label`: the row's label, copied exactly as printed in that table (same spelling, case and symbols). Do not shorten, expand or translate it.
- `column_label`: the column's header, copied exactly as printed in that table.
- `value`: the cell's value, copied exactly as printed in that table, one value per cell entry. Do not round it, reformat it, or add or remove units or signs.
- Quote only cells that are printed in the TABLES text. Never quote a value from the claim, from the pieces or from memory.
- For `no_row` and `not_a_table_piece`, `cells` is an empty list.

Output:

- Return one entry per piece, in the same order as PIECES, with `piece_id` equal to the piece's number.
- Answer every piece exactly once. Do not add pieces and do not merge pieces.
- Return only the JSON object described by the response schema. No other text.
