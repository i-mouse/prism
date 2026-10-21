# Pass-2 Claim Sentence Extraction

You are given one window of raw text extracted from a research paper. The
window may start or end mid-sentence, since it is a fixed-size slice of a
longer document.

Find every sentence in this window that makes a claim about this paper's own
method or results, and copy it out exactly as it appears in the window,
character-for-character. Do not paraphrase, shorten, correct, or merge
sentences - copy only.

Pay particular attention to claims that are easy to skip past on a single
fast read of the whole paper:

- A claim that is hedged, or stated as something that holds only "in
  principle" rather than flatly asserted.
- A claim whose only supporting numbers live in a table caption or must be
  read off a table, rather than stated directly in running prose.
- A narrower, more cautious claim sitting right next to a broader claim
  about the same result - copy both, not only the broader one.
- A bare "we observed ..." statement, with no hedging word and no number
  attached to it.

Do not copy a sentence that only describes the method, the experimental
setup, or an implementation detail, with no claim about this paper's own
results or findings attached to it.

Return a JSON object with a single field, "sentences", containing a list of
the exact verbatim sentences you found in this window. If this window
contains no qualifying sentences, return an empty list.
