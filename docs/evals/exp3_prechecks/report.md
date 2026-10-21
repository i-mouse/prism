# Experiment 3 pre-checks — report (2026-10-14)

Local only. No LLM/API calls, no git commands, no production-code changes.
Scripts and raw output live under `scratch/exp3/` (`lib.py`, `check_a.py`,
`check_b.py`, `check_c.py`, `check_a_output.txt`, `check_b_output.txt`).

**Known deviation (approved before running):** the task specified pysbd
`doc_type="pdf", clean=False`. The installed pysbd raises `ValueError` for
that exact combination — `doc_type="pdf"` requires `clean=True`. Check A/B
therefore run **three** splitters side by side, all on PyMuPDF text
extracted via `extract_pdf_text_sync`'s own logic (copied verbatim, not
imported — see below):
- `pysbd_pdf_clean` — `doc_type="pdf", clean=True` (pysbd's pdf-aware
  heuristics, but `clean=True` means pysbd may alter the text before
  segmenting, so segment text can diverge from the raw extracted text).
- `pysbd_text_noclean` — `doc_type="text", clean=False` (literal
  `clean=False`, but no pdf-specific heuristics).
- `regex` baseline — split on `. ? !` followed by whitespace + a capital
  letter, exactly as specified.

**Import-safety note:** `extract_pdf_text_sync` and `normalize_for_match`
were copied verbatim into `scratch/exp3/lib.py` (cited by source file:line)
instead of imported, because importing `main.py` or `extraction/grounding.py`
runs module-level side effects — `extraction/grounding.py` does
`from config import settings`, which instantiates `PrismSettings()`
(`config.py:118`) and raises `pydantic.ValidationError` without
`ConnectionStrings__messaging` / `ConnectionStrings__blobs` env vars;
`main.py` additionally builds telemetry/DB/RabbitMQ/LLM clients on import.
Page-joined text is measured exactly as the pipeline produces it:
`page.get_text()` concatenated in page order with no added separator.

---

## Check A — splitter survival

119 dev rows, 31 refusal-family (`not_supported` + `partially_supported`).
Pre-set bar: **≥95% WHOLE** (113/119). All three splitters **FAIL** the bar.

| splitter | WHOLE | SPLIT | MERGED | NOT_FOUND | WHOLE% | bar |
|---|---|---|---|---|---|---|
| pysbd_pdf_clean | 61 | 25 | 5 | 28 | 51.3% | FAIL |
| pysbd_text_noclean | 6 | 82 | 3 | 28 | 5.0% | FAIL |
| regex | 90 | 0 | 22 | 7 | 75.6% | FAIL |

Refusal-family only (31 rows):

| splitter | WHOLE | SPLIT | MERGED | NOT_FOUND |
|---|---|---|---|---|
| pysbd_pdf_clean | 18 | 2 | 3 | 8 |
| pysbd_text_noclean | 2 | 20 | 1 | 8 |
| regex | 19 | 0 | 11 | 1 |

NOT_FOUND is identical across both pysbd variants (same 8 refusal rows:
P2-R4, P5-R2, P5-R3, P6-R1, P8-R1, P9-R1, P10-R2, P10-R3) and a subset of
these fail under regex too (P5-R2 only). Full per-row detail with matched
segment text is in `check_a_output.txt`.

Observed failure patterns (from the printed segments, not tuned to fix):
- **regex** mostly MERGES — page-footer/next-section text runs into the
  claim sentence because the regex only splits on `[.?!]` + space + capital
  letter, so a line like "...lowers performance. 9 Preprint AI USE
  STATEMENT..." stays one segment.
- **pysbd_text_noclean** mostly SPLITS — it treats PDF column line-wraps as
  sentence boundaries (no pdf-dehyphenation/rejoin heuristics), breaking
  sentences roughly every line.
- **pysbd_pdf_clean** is between the two but still SPLITS/MERGES/misses on
  roughly half the rows.

## Check B — sentence counts (40/chunk)

Per paper, total sentences and sentences before the first standalone
"References"/"Bibliography" line; full table in `check_b_output.txt`.
Headline anomaly: `2610.11135v1.pdf` under `pysbd_pdf_clean` reports
**9,436** total sentences (236 chunks) vs. **586** for regex and **10,606**
for `pysbd_text_noclean` on the same paper — all three disagree by an order
of magnitude or more on several papers (e.g. `2610.10871v1.pdf`: 2,116 vs.
499 vs. 2,589). Pre-references sentence counts are smaller and more
consistent across splitters (e.g. `2610.11135v1.pdf`: 53 / 1,309 / 175) but
still vary by 5–25x between splitters. Chunks-needed-before-references
range from 2 to 54 depending on paper and splitter choice.

## Check C — union of past runs

13 target rows (run-1 extraction misses) and 13 in-scope matched rows,
counts matched the pre-registered 13/13 exactly (no adjustment needed).
Full per-row table in the script's stdout (reproduced below); source:
`docs/evals/dev_match_map.json` (run 1) and
`docs/evals/fixtures/dev/exp2/adjudication_template.json` (control_r1,
treatment_r1, treatment_r2).

- **Target rows found in ANY of the 4 runs: 3/13** (P1-R2, P12-R1, P3-R1).
- **Matched rows found in ANY of the 4 runs: 13/13.**

| row_id | run1 | ctrl_r1 | treat_r1 | treat_r2 | any |
|---|---|---|---|---|---|
| P1-R2 | False | True | False | False | **True** |
| P11-R1 | False | False | False | False | False |
| P11-R3 | False | False | False | False | False |
| P12-R1 | False | True | True | True | **True** |
| P2-R1 | False | False | False | False | False |
| P2-R3 | False | False | False | False | False |
| P2-R4 | False | False | False | False | False |
| P3-R1 | False | True | False | False | **True** |
| P4-R3 | False | False | False | False | False |
| P5-R3 | False | False | False | False | False |
| P7-R2 | False | False | False | False | False |
| P8-R3 | False | False | False | False | False |
| P9-R1 | False | False | False | False | False |

Matched rows (13/13, all True — see `check_c_output` for the per-run detail):
P1-R1, P1-R3, P11-R2, P12-R2, P2-R5, P3-R2, P4-R1, P4-R2, P5-R1, P5-R2,
P7-R1, P8-R1, P8-R2.

---

## Check D — reader bake-off (2026-10-14)

Goal: which input keeps dev claims whole as single units, after Check A
failed the 95% bar on raw PyMuPDF text with all three splitters (best:
regex 75.6%). Scripts: `check_d_grobid.py`, `check_d_pymupdf4llm.py`,
`check_d_windows.py`; raw output in `check_d_grobid_output.txt`,
`check_d_pymupdf4llm_output.txt`, `check_d_windows_output.txt`. No LLM/API
calls — the only network call is to the user-started local GROBID instance
(`http://localhost:8070`, version **0.9.0**, confirmed reachable via
`/api/isalive`→`true` before running). No reader/splitter/window tuning
against dev rows. Package versions used: `requests` 2.32.5, `pymupdf4llm`
1.28.2, `rapidfuzz` 3.14.5 (already a project dependency) — `requests` and
`pymupdf4llm` installed transiently via `uv run --with`, not added to
`pyproject.toml`/`uv.lock`.

Pre-set bar (unchanged): **PASS = ≥95% of 119 rows WHOLE (113/119)**.

### Candidate 1 — GROBID sentences

Segments from 4 sources per paper (counted separately): abstract `<s>`,
body `<s>` (excluding any already counted under note/caption), figure/table
caption (`<figDesc>`, `<head>`, `<label>` of each `<figure>`, one segment
each), and note `<s>` (or the note's own text if it has no `<s>` children) —
footnotes, added as a 4th source per your fix.

| overall | WHOLE | SPLIT | MERGED | NOT_FOUND | WHOLE% | bar |
|---|---|---|---|---|---|---|
| 119 rows | 64 | 8 | 9 | 38 | 53.8% | **FAIL** |

Refusal-family (31 rows): WHOLE=20, SPLIT=1, MERGED=3, NOT_FOUND=7.

Per-paper segment counts (abstract / body / caption / note) and runtime:

| paper | abstract | body | caption | note | total | runtime (s) |
|---|---|---|---|---|---|---|
| 2610.10590v1.pdf | 9 | 257 | 10 | 1 | 277 | 12.1 |
| 2610.10871v1.pdf | 9 | 313 | 37 | 18 | 377 | 6.2 |
| 2610.11132v1.pdf | 9 | 561 | 43 | 25 | 638 | 7.3 |
| 2610.11135v1.pdf | 9 | 778 | 105 | 27 | 919 | 4.4 |
| 2610.11291v1.pdf | 14 | 371 | 47 | 29 | 461 | 2.7 |
| 2610.11312v1.pdf | 9 | 433 | 51 | 17 | 510 | 7.3 |
| 2610.11519v1.pdf | 10 | 602 | 103 | 8 | 723 | 8.9 |
| 2610.12114v1.pdf | 0 | 429 | 38 | 20 | 487 | 7.7 |
| 2610.12124v1.pdf | 10 | 592 | 57 | 20 | 679 | 5.6 |
| 2610.12168v1.pdf | 4 | 394 | 14 | 9 | 421 | 4.3 |
| 2610.12176v1.pdf | 10 | 945 | 43 | 21 | 1019 | 7.5 |
| 2610.12375v1.pdf | 11 | 534 | 8 | 5 | 558 | 5.3 |

Note: `2610.12114v1.pdf` has **0** abstract `<s>` segments — GROBID
produced no `<s>`-segmented abstract for that paper (not investigated
further, reported as observed). 11 non-WHOLE refusal rows; full per-row
segment text is in `check_d_grobid_output.txt`. Half of the SPLIT/MERGED
cases (e.g. P2-R4, P4-R2) land on caption segments that concatenate an
entire table's worth of footnote-style caption text into one `<figDesc>`,
not sentence-split internally.

### Candidate 2 — PyMuPDF4LLM, headers/footers off

`pymupdf4llm.to_markdown(path, header=False, footer=False)` (kwargs
confirmed accepted by installed version 1.28.2 via a signature probe
before running — `inspect.signature` reports `(*args, **kwargs)` for this
function so a dry-run call was used to confirm, not a static signature
check). Strip rule applied **symmetrically** to both the cleaned markdown
(before splitting) and each dev row's `claim_text_verbatim` (before
`normalize_for_match`): remove a leading `-`/`+ ` or `<digits>.`/`<digits>)`
+ whitespace at line start (so `3.2` and `0.825` are never touched — the
character right after the digits there is another digit, not `.`/`)` +
whitespace), then strip bare `# * _ | `` ` chars anywhere.

| splitter | WHOLE | SPLIT | MERGED | NOT_FOUND | WHOLE% | bar |
|---|---|---|---|---|---|---|
| regex | 60 | 0 | 17 | 42 | 50.4% | **FAIL** |
| pysbd_pdf_clean | 70 | 2 | 5 | 42 | 58.8% | **FAIL** |

Refusal-family (31 rows):

| splitter | WHOLE | SPLIT | MERGED | NOT_FOUND |
|---|---|---|---|---|
| regex | 19 | 0 | 8 | 4 |
| pysbd_pdf_clean | 24 | 0 | 3 | 4 |

Per-paper segment counts (regex / pysbd_pdf_clean):

| paper | regex | pysbd_pdf_clean |
|---|---|---|
| 2610.10590v1.pdf | 356 | 443 |
| 2610.10871v1.pdf | 477 | 783 |
| 2610.11132v1.pdf | 798 | 1352 |
| 2610.11135v1.pdf | 592 | 1830 |
| 2610.11291v1.pdf | 368 | 692 |
| 2610.11312v1.pdf | 672 | 965 |
| 2610.11519v1.pdf | 738 | 1539 |
| 2610.12114v1.pdf | 578 | 961 |
| 2610.12124v1.pdf | 900 | 1262 |
| 2610.12168v1.pdf | 754 | 711 |
| 2610.12176v1.pdf | 966 | 1660 |
| 2610.12375v1.pdf | 436 | 701 |

Full non-WHOLE refusal-row detail (12 rows under regex, 7 under
pysbd_pdf_clean) is in `check_d_pymupdf4llm_output.txt`; the same
section-heading-bleed pattern seen in Check A's regex baseline recurs here
("...lowers performance. 1 Introduction Our method is inspired by...").

### Candidate 3 — fixed windows (6000 chars / 1500 overlap), no sentence splitting

On unchanged `extract_pdf_text_sync`-copy text. WHOLE = normalized claim is
a substring of some window; no SPLIT/MERGED categories (windows are fixed
blocks, not sentence units).

| overall | WHOLE | NOT_FOUND | WHOLE% | bar |
|---|---|---|---|---|
| 119 rows | 112 | 7 | **94.1%** | FAIL (by 1 row) |

Refusal-family (31 rows): WHOLE=30, NOT_FOUND=1 (P5-R2 — also NOT_FOUND
in every other candidate and in Check A's pysbd variants).

Among the 7 exact NOT_FOUND rows, **7/7** are found via
`rapidfuzz.fuzz.partial_ratio >= 95` against some window (reported
separately, not folded into WHOLE): P1-S1 (95.6), P3-S6 (99.3), P5-R2
(99.5), P5-S2 (99.0), P7-S1 (99.7), P9-S6 (99.4), P10-S6 (99.4) — all are
near-exact (fuzzy score ≥95), consistent with a PDF-extraction artifact
(ligature/whitespace/hyphenation) rather than content actually missing
from any window.

Per-paper window counts: 2610.10590v1.pdf=9, 2610.10871v1.pdf=15,
2610.11132v1.pdf=27, 2610.11135v1.pdf=34, 2610.11291v1.pdf=17,
2610.11312v1.pdf=22, 2610.11519v1.pdf=29, 2610.12114v1.pdf=19,
2610.12124v1.pdf=23, 2610.12168v1.pdf=18, 2610.12176v1.pdf=30,
2610.12375v1.pdf=18.

### Summary

| candidate | best WHOLE% | bar |
|---|---|---|
| GROBID sentences | 53.8% | FAIL |
| PyMuPDF4LLM + regex | 50.4% | FAIL |
| PyMuPDF4LLM + pysbd_pdf_clean | 58.8% | FAIL |
| fixed windows (6000/1500) | 94.1% | FAIL (closest, misses by 1 row exactly; 7/7 of its misses are fuzzy-near-exact) |

No candidate passes the pre-set 95% bar. No recommendations.

---

## Check E — failure diagnosis (2026-10-14)

Read-only analysis diagnosing *why* Check A and Check D missed rows. Does
not change any check's definitions or bars. No LLM/API calls; the only
network call was a GROBID re-run explicitly authorized mid-task (see Step
0) — scripts: `diag_lib.py`, `check_e_raw.py`, `check_e_pymupdf.py`,
`check_d_grobid_v2.py`, `check_e_grobid.py`, plus one-off audit helpers
(`audit_pymupdf4llm_escaping.py`, `check_note_fallback_hit.py`,
`sig_check.py`, `sig_check2.py`). Raw output in the matching
`*_output.txt` files.

### Step 0 — self-audit (reported before Steps 1-3 ran)

1. **GROBID TEI was not saved by the original Check D run.** Confirmed by
   listing `scratch/exp3/` — only `check_d_grobid_output.txt` (printed
   counts) existed, no XML. Per your direction, GROBID was re-run once
   (`check_d_grobid_v2.py`, after re-confirming `/api/isalive` → `true`,
   no docker) with every TEI response saved to
   `scratch/exp3/grobid_tei/*.tei.xml`, so Steps 1-3 use saved files, not a
   second re-fetch.
2. **`check_d_grobid.py`'s original note-fallback deviated from the
   approved spec** (whole-note `itertext()` instead of per-`<p>`
   segments). Fixed in `check_d_grobid_v2.py` only — the original script
   and its output are untouched. **Empirically verified the fix changed
   nothing**: of 165 `<note>` elements across the 12 papers, 130 lacked
   `<s>` children (so the fallback path fires often), but **none** had
   more than one `<p>` child — "whole note" and "per-`<p>`" text are
   identical whenever a note has at most one paragraph, which was true for
   every note here. v1 and v2 produced byte-identical classification
   counts (64/8/9/38 WHOLE/SPLIT/MERGED/NOT_FOUND, identical per-paper
   source counts) — confirmed, not assumed.
3. **GROBID `itertext()` joining risk** (possible lost space around
   `<ref>`/`<formula>`/`<hi>`): not directly falsifiable without deeper TEI
   inspection, but Step 2's GROBID causes below surface a **related,
   confirmed** issue: GROBID emits the Unicode minus sign U+2212 ("−") for
   negative numbers, which `normalize_for_match`'s quote/dash table does
   **not** map to ASCII "-" (it only handles `‘-‟`/en-dash/em-dash) —
   a genuine, confirmed source of GROBID-specific mismatches (3 rows
   tagged `ligature_or_unicode` below), independent of the itertext()
   question.
4. **PyMuPDF4LLM strip-rule symmetry**: confirmed symmetric (same function,
   same order, both sides). Specifically checked whether pymupdf4llm
   backslash-escapes `_`/`*` (which would make the "same function on both
   sides" claim misleading, since the claim side never has such escapes to
   strip) — spot-checked on one paper (`2610.10590v1.pdf`, not all 12):
   **zero** escaped characters found (46 un-escaped `_`, 168 un-escaped
   `*`, all stripped identically from both sides). No bug found, but this
   was a one-paper check, not exhaustive.
5. **Windows per-window vs whole-text normalisation**: not a separate bug —
   Step 2's raw-text cross-reference below (all 3 sources) shows this
   directly: Check D candidate 3's 7 NOT_FOUND rows are **identical** to
   raw-text's 7 reader-loss rows, meaning windowing itself added zero
   additional loss beyond what was already missing from the raw extracted
   text.

**Known limitation of Step 2's automated cause-tagging** (disclosed up
front, not discovered after the fact): `rapidfuzz.fuzz.partial_ratio_alignment`
finds the best-aligned region but its boundary can be a few characters
short/long of the true match, which spills a trailing or leading
fragment into the computed diff as a spurious insertion/deletion. This
inflates the `other` bucket in several cases that look, on inspection of
the printed diff, like pure whitespace or a single dropped trailing period
(e.g. `P5-R2`, `P1-S4`) rather than a real content difference. Cause tags
below should be read as a best-effort, rule-based classification of the
*visible diff text*, not a certified root cause per row — the raw diffs
are included precisely so this can be checked by eye.

### Step 1 — ceiling / splitter loss / reader loss, per source

| source | CEILING (119) | CEILING refusal (31) |
|---|---|---|
| raw_pipeline_text | 112 | 30 |
| pymupdf4llm | 77 | 27 |
| grobid | 81 | 24 |

**raw_pipeline_text** splitter loss (in ceiling, not WHOLE): pysbd_pdf_clean
51, pysbd_text_noclean 106, regex 22. Reader loss: 7
(`P1-S1, P3-S6, P5-R2, P5-S2, P7-S1, P9-S6, P10-S6`). These splitter-loss
and reader-loss counts reproduce Check A's original WHOLE counts exactly
(112−51=61, 112−106=6, 112−22=90) — a consistency check that passed.

**pymupdf4llm** splitter loss: regex 17, pysbd_pdf_clean 7. Reader loss: 42
rows (full list in `check_e_pymupdf_output.txt`). Reproduces Check D's
original WHOLE counts exactly (77−17=60, 77−7=70).

**grobid** splitter loss (one segmentation only): 17 rows. Reader loss: 38
rows (full list in `check_e_grobid_output.txt`). Reproduces Check D v2's
WHOLE count exactly (81−17=64).

**Windows (Check D candidate 3) cross-reference**: all 7 of its NOT_FOUND
rows (`P1-S1, P3-S6, P5-R2, P5-S2, P7-S1, P9-S6, P10-S6`) are in the
raw-text reader-loss set above — i.e. **identical sets**. Windowing added
no loss of its own; candidate 3's near-miss of the 95% bar (94.1%) is
entirely explained by the same 7 rows missing from the raw extracted text
itself, not by the window/overlap parameters.

### Step 1 — cause counts per source (reader-loss rows only)

| source | reader-loss rows | cause counts |
|---|---|---|
| raw_pipeline_text | 7 | other=3, hyphenation_or_linebreak=3, text_reordered=1 |
| pymupdf4llm | 42 | other=37, hyphenation_or_linebreak=2, text_dropped=3 |
| grobid | 38 | text_dropped=14, other=15, hyphenation_or_linebreak=4, ligature_or_unicode=3, text_reordered=2 |

Qualitative pattern visible in the pymupdf4llm diffs beyond the mechanical
tags (most landed in `other` due to the alignment-truncation limitation
above): the dominant, repeated pattern is pymupdf4llm inserting a space
around numbers/decimal-points (`1.03` → `1 . 03`) and emitting literal
`<sup>...</sup>` HTML tags for exponents/footnote markers — neither is
covered by the approved strip rule (`# * _ | \``, which has no HTML-tag
handling), so this is a real, visible contributor to pymupdf4llm's reader
loss that the mechanical cause-tagger under-counts.

### Step 2 — per-row lines, refusal-family rows only

**raw_pipeline_text** — reader loss (1 of 31 refusal rows not in ceiling):
| row | score | cause |
|---|---|---|
| P5-R2 (2610.11291v1.pdf) | 99.5 | other (diff is a dropped trailing period + 1 inserted space — likely `missing_or_extra_space` in substance, see Step 0 limitation) |

splitter-loss refusal rows (in ceiling, not WHOLE): pysbd_pdf_clean 12
(`P1-R2, P10-R2, P10-R3, P2-R1, P2-R3, P2-R4, P4-R1, P4-R3, P5-R3, P6-R1, P8-R1, P9-R1`);
pysbd_text_noclean 28 (`P1-R1, P1-R2, P1-R3, P10-R1, P10-R2, P10-R3, P11-R1, P11-R2, P11-R3, P12-R1, P12-R2, P2-R1, P2-R3, P2-R4, P3-R1, P3-R2, P4-R1, P4-R2, P4-R3, P5-R3, P6-R1, P6-R2, P7-R1, P7-R2, P8-R1, P8-R2, P8-R3, P9-R1`);
regex 11 (`P1-R1, P10-R3, P11-R1, P12-R1, P2-R1, P2-R3, P2-R4, P3-R2, P6-R1, P7-R1, P8-R2`).

**pymupdf4llm** — reader loss (4 of 31 refusal rows not in ceiling):
| row | score | cause |
|---|---|---|
| P10-R2 (2610.12176v1.pdf) | 99.4 | other (diff: 1 inserted space + 1 dropped period) |
| P11-R1 (2610.12114v1.pdf) | 92.0 | other (diff shows `<sup>`/`</sup>` tags inserted around "Primer" superscript text) |
| P5-R2 (2610.11291v1.pdf) | 99.5 | other (same near-exact diff as raw_pipeline_text's P5-R2) |
| P9-R1 (2610.12375v1.pdf) | 98.8 | other |

splitter-loss refusal rows: regex 8 (`P10-R3, P12-R1, P2-R3, P2-R4, P3-R2, P6-R1, P7-R1, P8-R2`);
pysbd_pdf_clean 3 (`P2-R3, P4-R1, P4-R3`).

**grobid** — reader loss (7 of 31 refusal rows not in ceiling):
| row | score | cause |
|---|---|---|
| P3-R1 (2610.11135v1.pdf) | 67.3 | text_dropped |
| P4-R1 (2610.10871v1.pdf) | 67.8 | text_dropped |
| P4-R3 (2610.10871v1.pdf) | 56.6 | text_dropped |
| P5-R1 (2610.11291v1.pdf) | 60.9 | text_dropped |
| P6-R2 (2610.11312v1.pdf) | 99.4 | hyphenation_or_linebreak (diff: `single[---]agent` — hyphen dropped at a GROBID sentence-boundary split) |
| P7-R2 (2610.10590v1.pdf) | 50.5 | text_dropped |
| P8-R2 (2610.12124v1.pdf) | 57.1 | text_dropped |

Five of these seven score well below 80 (`text_dropped`) with heavily
garbled diffs (large reordered/substituted spans) — visually consistent
with GROBID's sentence segmentation mis-handling dense numeric/table-like
prose (these rows are almost all results-section sentences packed with
percentages and comparisons), not a simple formatting artifact. This is an
observation from inspecting the diffs, not a certified cause.

splitter-loss refusal rows: 4 (`P2-R3, P2-R4, P4-R2, P9-R1`).

### Summary table (refusal-family rows, 31 total)

| source | ceiling | reader-loss (not in ceiling) | best splitter's non-WHOLE-but-in-ceiling |
|---|---|---|---|
| raw_pipeline_text | 30/31 | 1 | regex: 11 |
| pymupdf4llm | 27/31 | 4 | pysbd_pdf_clean: 3 |
| grobid | 24/31 | 7 | 4 |

STOP. No recommendations.
