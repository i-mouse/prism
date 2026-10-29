"""Synthetic-input tests for the T2-R LaTeX table parser and reference-table builder.
No network, no real papers, no PDFs."""
from pathlib import Path

import pytest

from eval.auditor_v2 import latex_table as lt
from eval.auditor_v2 import t2r_build_refs as br
from eval.auditor_v2 import table_keys as tk


def tab(inner: str, spec: str = "lcc") -> str:
    return r"\begin{tabular}{" + spec + "}" + inner + r"\end{tabular}"


def parse(body: str, defs_text: str = "", env: str = "table", base=None):
    defs = lt.collect_defs(defs_text) if defs_text else {}
    return lt.parse_table_body(body, env, defs, 10 ** 9, base)


def cell(pt, row, col):
    return next((c for c in pt.cells if c.row == row and c.col == col), None)


def texts(pt):
    out = {}
    for c in pt.cells:
        out.setdefault(c.row, []).append(c.text)
    return [out[r] for r in sorted(out)]


# ----------------------------------------------------------------- rows, cells, escapes

def test_basic_rows_and_cells():
    pt = parse(tab(r"\toprule A & B & C \\ \midrule x & 1 & 2 \\ y & 3 & 4 \\ \bottomrule"))
    assert (pt.n_rows, pt.n_cols) == (3, 3)
    assert texts(pt) == [["A", "B", "C"], ["x", "1", "2"], ["y", "3", "4"]]
    assert pt.header_rows == [0]
    assert pt.problems == []


def test_escaped_ampersand_and_percent_and_underscore():
    pt = parse(tab(r"A & B \\ R\&D & 5\% \\ a\_b & 1 \\", "ll"))
    assert texts(pt)[1] == ["R&D", "5%"]
    assert texts(pt)[2] == ["a_b", "1"]


def test_double_backslash_inside_braces_is_not_a_row_break():
    pt = parse(tab(r"A & B \\ \makecell{a\\b} & 1 \\", "ll"))
    assert pt.n_rows == 2
    assert texts(pt)[1] == ["a b", "1"]


def test_row_break_with_length_and_tabularnewline_and_spacer_rows():
    pt = parse(tab(r"a & 1 \\[3pt] b & 2 \tabularnewline c & 3 \\ \\ d & 4 \\", "ll"))
    assert texts(pt) == [["a", "1"], ["b", "2"], ["c", "3"], ["d", "4"]]


def test_nested_tabular_in_cell_is_flattened():
    pt = parse(tab(r"A & B \\ \begin{tabular}[c]{@{}c@{}}x\\y\end{tabular} & 1 \\", "ll"))
    assert pt.n_rows == 2
    assert texts(pt)[1] == ["x y", "1"]


def test_tabularx_in_wraptable_with_two_spec_args():
    body = r"\centering \begin{tabularx}{\linewidth}{lY} A & B \\ \midrule 1 & 2 \\ \end{tabularx}"
    pt = parse(body, env="wraptable")
    assert texts(pt) == [["A", "B"], ["1", "2"]]


def test_rule_commands_with_arguments_are_removed():
    body = tab(r"A & B \\ \hhline{~~*{9}{-}} \cmidrule(lr){1-2} \addlinespace[2pt] \cline{1-2} x & 1 \\", "ll")
    pt = parse(body)
    assert texts(pt) == [["A", "B"], ["x", "1"]]


# ----------------------------------------------------------------- spans

def test_multicolumn_sets_col_span_and_shifts_columns():
    pt = parse(tab(r"\multicolumn{2}{c}{Group} & Z \\ a & b & c \\"))
    g = cell(pt, 0, 0)
    assert (g.text, g.col_span) == ("Group", 2)
    assert cell(pt, 0, 2).text == "Z"
    assert pt.n_cols == 3 and pt.n_multicolumn == 1


def test_multirow_positive_consumes_empty_cells_below():
    pt = parse(tab(r"H & I & J \\ \midrule \multirow{2}{*}{G} & a & 1 \\ & b & 2 \\"))
    g = cell(pt, 1, 0)
    assert (g.text, g.row_span) == ("G", 2)
    assert cell(pt, 2, 0) is None
    assert cell(pt, 2, 1).text == "b"
    assert pt.problems == [] and pt.n_multirow == 1


def test_multirow_optional_arguments_either_side():
    body = tab(r"H & I \\ \midrule \multirow[c]{2}{0.5cm}{" "\n" r"\centering X} & a \\ & b \\ "
               r"\multirow{2}{*}[-2pt]{Y} & c \\ & d \\", "ll")
    pt = parse(body)
    assert (cell(pt, 1, 0).text, cell(pt, 1, 0).row_span) == ("X", 2)
    assert (cell(pt, 3, 0).text, cell(pt, 3, 0).row_span) == ("Y", 2)
    assert pt.problems == []


def test_multirow_negative_spans_upward_and_replaces_empty_placeholder():
    body = tab(r"& \multicolumn{2}{c}{VG} \\ \multirow{-2}{*}{Model} & Det & Acc \\ \midrule a & 1 & 2 \\")
    pt = parse(body)
    m = cell(pt, 0, 0)
    assert (m.text, m.row_span) == ("Model", 2)
    assert cell(pt, 1, 0) is None
    assert pt.header_rows == [0, 1]
    assert pt.problems == []


def test_multirow_nonempty_placeholder_is_reported():
    pt = parse(tab(r"H & I \\ \midrule \multirow{2}{*}{G} & a \\ oops & b \\", "ll"))
    assert any("not empty" in p for p in pt.problems)


def test_nested_multicolumn_multirow():
    pt = parse(tab(r"H & I & J \\ \midrule \multicolumn{2}{c}{\multirow{2}{*}{N}} & 1 \\ "
                   r"\multicolumn{2}{c}{} & 2 \\"))
    n = cell(pt, 1, 0)
    assert (n.text, n.col_span, n.row_span) == ("N", 2, 2)
    assert pt.n_multirow == 1 and pt.n_multicolumn == 2
    assert cell(pt, 2, 0) is None and pt.problems == []


def test_multirowcell():
    pt = parse(tab(r"H & I \\ \midrule \multirowcell{2}{p\\q} & a \\ & b \\", "ll"))
    assert (cell(pt, 1, 0).text, cell(pt, 1, 0).row_span) == ("p q", 2)


# ----------------------------------------------------------------- header, section, row headers

def test_header_by_midrule_with_two_header_rows_and_cmidrule_ignored():
    pt = parse(tab(r"\toprule & \multicolumn{2}{c}{G} \\ \cmidrule(lr){2-3} & a & b \\ \midrule r & 1 & 2 \\"))
    assert pt.header_rows == [0, 1]
    assert cell(pt, 2, 1).is_column_header is False
    assert cell(pt, 0, 1).is_column_header is True


def test_header_by_specialrule():
    pt = parse(tab(r"G & H \\ a & b \\ \specialrule{1pt}{1pt}{1pt} x & 1 \\", "ll"))
    assert pt.header_rows == [0, 1]


def test_header_by_hline_and_rule_before_row_zero_ignored():
    pt = parse(tab(r"\hline A & B \\ \hline x & 1 \\ \hline y & 2 \\ \hline", "ll"))
    assert pt.header_rows == [0]


def test_header_first_row_only_when_no_rule_after_first_row():
    pt = parse(tab(r"\toprule A & B \\ x & 1 \\ y & 2 \\ \bottomrule", "ll"))
    assert pt.header_rows == [0]


def test_hhline_and_cmidrule_do_not_close_the_header():
    pt = parse(tab(r"A & B \\ \hhline{--} x & 1 \\ \cmidrule{1-2} y & 2 \\ \midrule z & 3 \\", "ll"))
    assert pt.header_rows == [0, 1, 2]


def test_section_row_is_single_multicolumn_over_all_columns():
    pt = parse(tab(r"M & A & B \\ \midrule \multicolumn{3}{l}{\textit{Medical VLMs}} \\ x & 1 & 2 \\"))
    s = cell(pt, 1, 0)
    assert s.is_section_row and s.text == "Medical VLMs"
    k = tk.derive_keys(lt.to_schema(pt, "cap", 1) | {})
    assert k.section_rows == {1: "Medical VLMs"}
    assert k.row_paths[2] == ["Medical VLMs", "x"]


def test_partial_multicolumn_title_in_header_is_not_a_section_row():
    pt = parse(tab(r"\toprule & \multicolumn{2}{c}{Title} \\ & a & b \\ \midrule x & 1 & 2 \\"))
    assert not any(c.is_section_row for c in pt.cells)


def test_row_header_columns_skip_empty_column_and_stop_at_numbers():
    body = tab(r"Fw & Sp & Var & 4K \\ \midrule \multirow{2}{*}{MInfer} & & Original & 1.5 \\ & & MASA & 2.5 \\",
               "llll")
    pt = parse(body)
    rh = sorted({c.col for c in pt.cells if c.is_row_header})
    assert rh == [0, 2]
    k = tk.derive_keys(lt.to_schema(pt, "cap", 1))
    assert k.row_paths[1] == ["MInfer", "Original"]
    assert k.row_paths[2] == ["MInfer", "MASA"]


def test_row_header_run_ends_at_first_numeric_column():
    pt = parse(tab(r"N & V & T \\ \midrule a & 1 & foo \\ b & 2 & bar \\"))
    assert sorted({c.col for c in pt.cells if c.is_row_header}) == [0]


# ----------------------------------------------------------------- macros

def test_macro_expansion_zero_one_two_args_default_and_def():
    defs = (r"\newcommand{\RA}{\textsc{RA}}" "\n" r"\newcommand{\best}[1]{\textbf{#1}}" "\n"
            r"\newcommand{\pair}[2]{#1 / #2}" "\n" r"\newcommand{\dd}[2][d]{#1-#2}" "\n" r"\def\sd#1{$\pm$#1}")
    body = tab(r"\RA{} & \best{12.3} & \pair{1}{2} \\ \dd{x} & \dd[o]{x} & 4.0\sd{0.1} \\")
    pt = parse(body, defs)
    assert texts(pt) == [["RA", "12.3", "1 / 2"], ["d-x", "o-x", "4.0±0.1"]]
    assert {"RA", "best", "pair", "dd", "sd"} <= set(pt.macros_expanded)


def test_macro_positional_scope_uses_last_definition_before_the_table():
    text = "\\newcommand{\\v}{A}\nMARK\n\\renewcommand{\\v}{B}\nEND"
    defs = lt.collect_defs(text)
    p = []
    assert lt.expand_macros(r"\v", defs, text.index("MARK"), p) == "A"
    assert lt.expand_macros(r"\v", defs, len(text), p) == "B"


def test_nested_macro_expansion():
    defs = lt.collect_defs(r"\newcommand{\a}[1]{\b{#1}!}\newcommand{\b}[1]{<#1>}")
    assert lt.expand_macros(r"\a{x}", defs, 10 ** 9, []) == "<x>!"


def test_noalign_group_is_dropped_with_its_content():
    defs = r"\newcommand{\shade}[1]{\noalign{\color{#1}\hrule height 1pt}}"
    pt = parse(tab(r"A & B \\ \shade{red} x & 1 \\", "ll"), defs)
    assert texts(pt) == [["A", "B"], ["x", "1"]]


def test_color_commands_are_dropped():
    pt = parse(tab(r"\rowcolor{gray!10} \cellcolor{red}a & \cellcolor[gray]{0.9}1 \\", "ll"))
    assert texts(pt) == [["a", "1"]]


def test_sbox_input_measured_table_is_input_once(tmp_path):
    (tmp_path / "body.tex").write_text(tab(r"A & B \\ \midrule 1 & 2 \\", "ll"), encoding="utf-8")
    defs = (r"\newcommand{\mt}[1]{\sbox\bx{\input{#1}}\global\setlength\wd{\wd\bx}\input{#1}"
            r"\global\setlength\wd{\z@}}")
    pt = parse(r"\centering \mt{body}", defs, base=tmp_path)
    assert texts(pt) == [["A", "B"], ["1", "2"]]
    assert pt.problems == []


def test_unknown_macro_is_left_as_text_and_listed():
    pt = parse(tab(r"\foo & 1 \\", "ll"))
    assert "foo" in pt.unknown_macros
    assert cell(pt, 0, 0).text == "\\foo"


def test_cell_formatting_and_symbols():
    pt = parse(tab(r"\underline{.709}{\tiny$\pm$.059} & Best deep KT$^\dagger$ & $\Delta$ x & --", "llll"))
    assert [c.text for c in pt.cells] == [".709±.059", "Best deep KT†", "Δ x", "–"]


def test_longtable_repeated_heads_and_feet_dropped():
    body = (r"{ll} H1 & H1b \\ \midrule \endfirsthead H2 & H2b \\ \endhead \bottomrule \endlastfoot "
            r"a & b \\ c & d \\")
    pt = parse(body, env="longtable")
    assert texts(pt) == [["H1", "H1b"], ["a", "b"], ["c", "d"]]
    assert pt.header_rows == [0]


def test_no_tabular_is_a_problem():
    pt = parse(r"\centering just text")
    assert any("no tabular" in p for p in pt.problems)


# ----------------------------------------------------------------- caption normalise, identification

def test_caption_normalise_latex_and_pdf_agree():
    latex = r"\textbf{The same}~teacher-peak $\lambda$ branch\cite{x}\label{y} of $\Delta$ and \RA{}."
    defs = lt.collect_defs(r"\newcommand{\RA}{\textsc{RA}}")
    plain = lt.caption_to_plain(latex, defs, 10 ** 9)
    pdf = "The same teacher-peak λ branch of ∆ and RA."
    assert lt.normalise_caption(plain) == lt.normalise_caption(pdf) == "thesameteacherpeaklambdabranchofdeltaandra"


def test_find_captions_marker_number_and_continuation():
    lines = ["Table 4: The same teacher-", "peak branch slightly helps sampled OPD but lowers", "third line stays out",
             "Table 40: other", "see Table 4 shows", "Table 4. again the same"]
    caps = lt.find_captions_in_lines(lines, 4)
    assert caps[0] == "The same teacherpeak branch slightly helps sampled OPD but lowers"
    assert len(caps) == 2 and caps[1].startswith("again the same")
    assert lt.find_captions_in_lines(["Table 7 | Results on x"], 7) == ["Results on x"]
    assert lt.find_captions_in_lines(["Table 7 has no punctuation"], 7) == []


def test_identify_unique_ambiguous_none_and_short():
    a, b = "x" * 40, "y" * 40
    cands = [(1, a + "tail"), (2, b + "tail")]
    assert lt.identify([a + "zzz"], cands) == {"status": "identified", "index": 1, "matches": [1]}
    assert lt.identify([a + "zzz"], cands + [(3, a + "other")])["status"] == "latex-ambiguous"
    assert lt.identify(["z" * 45], cands)["status"] == "latex-none"
    assert lt.identify([], cands)["status"] == "pdf-none"
    assert lt.identify([a + "q", b + "q"], cands)["status"] == "pdf-ambiguous"
    short = [(7, "results"), (8, "other" + "k" * 40)]
    assert lt.identify(["results" + "o" * 50], short)["index"] == 7
    assert lt.identify(["abc"], [(1, "")])["status"] == "latex-none"


# ----------------------------------------------------------------- relaxed compare and pin check

def test_relax_label():
    assert br.relax_label("Norm α") == br.relax_label("Norm alpha") == "normalpha"
    assert br.relax_label("∆macro Avg@8") == br.relax_label("Δ macro Avg@8")
    assert br.relax_label("λ=5") == br.relax_label("lambda=5")
    assert br.relax_label("alpha") != br.relax_label("beta")


def _schema(body):
    pt = parse(body)
    return lt.to_schema(pt, "cap", 1)


def test_check_pin_strict_relaxed_and_mismatch():
    t = _schema(tab(r"\toprule & \multicolumn{2}{c}{Eff} \\ & Sampled OPD & $\lambda{=}5$ \\ \midrule "
                    r"$\Delta$ macro Avg@8 & $+0.30$ & $-0.38$ \\ \bottomrule"))
    base = {"table_id": "T", "kind": "cell", "key_columns": None, "breaking": True, "key_uncertain": False}
    strict = {**base, "id": "s", "row_key_path": ["Δ macro Avg@8"], "column_key_path": ["λ=5"], "value": "-0.38"}
    relaxed = {**base, "id": "r", "row_key_path": ["∆macro Avg@8"], "column_key_path": ["Sampled OPD"], "value": "+0.30"}
    bad = {**base, "id": "m", "row_key_path": ["∆macro Avg@8"], "column_key_path": ["Sampled OPD"], "value": "+0.31"}
    assert br.check_pin(t, strict)["status"] == "strict"
    assert br.check_pin(t, relaxed)["status"] == "relaxed"
    assert br.check_pin(t, bad)["status"] == "mismatch"
    s = br.check_table_pins(t, [strict, relaxed, bad])
    assert s["cell"] == [2, 3] and [r["id"] for r in s["relaxed"]] == ["r"]


def test_check_pin_key_columns_with_relaxed_glyph():
    t = _schema(tab(r"Setting & Clip p & Norm $\alpha$ & Avg. \\ \midrule MInf & - & - & 87.13 \\ "
                    r"Seer & 90 & 0.6 & 87.27 \\", "llll"))
    pin = {"id": "k", "table_id": "T", "kind": "cell", "row_key_path": ["Seer", "90", "0.6"],
           "column_key_path": ["Avg."], "key_columns": ["Setting", "Clip p", "Norm alpha"], "value": "87.27",
           "breaking": False, "key_uncertain": False}
    assert br.check_pin(t, pin)["status"] == "relaxed"
    absent = {"id": "a", "table_id": "T", "kind": "row_absent", "match": {"Setting": "Seer", "Clip p": "-",
              "Norm alpha": "-"}, "breaking": True, "key_uncertain": False}
    assert br.check_pin(t, absent)["status"] == "relaxed"


def test_check_pin_ambiguous_consistent_for_uncertain_pins_only():
    t = _schema(tab(r"Fw & V & 4K \\ \midrule \multirow{2}{*}{A} & Original & 1.0 \\ & New & 2.0 \\ "
                    r"\multirow{2}{*}{B} & Original & 3.0 \\ & New & 4.0 \\"))
    base = {"table_id": "T", "kind": "cell", "key_columns": None, "breaking": False,
            "row_key_path": ["Original"], "column_key_path": ["4K"]}
    ok = {**base, "id": "u1", "value": "3.0", "key_uncertain": True}
    no = {**base, "id": "u2", "value": "9.0", "key_uncertain": True}
    certain = {**base, "id": "c1", "value": "3.0", "key_uncertain": False}
    assert br.check_pin(t, ok)["status"] == "ambiguous-consistent"
    assert br.check_pin(t, no)["status"] == "mismatch"
    assert br.check_pin(t, certain)["status"] == "mismatch"


def test_check_pin_structural_kinds():
    t = _schema(tab(r"Student & Teacher & AUC \\ \midrule Q (SFT) & T1 & 1.0 \\ Q & T1 & 2.0 \\ R (SFT) & T2 & 3.0 \\"))
    pins = [
        {"id": "n", "kind": "row_count", "count": 3, "key_uncertain": False, "breaking": True},
        {"id": "c", "kind": "col_contains_count", "column": "Student", "contains": "(SFT)", "count": 2,
         "key_uncertain": False, "breaking": True},
        {"id": "e", "kind": "row_exists", "match": {"Student": "Q (SFT)", "Teacher": "T1"},
         "key_uncertain": False, "breaking": True},
    ]
    res = br.check_table_pins(t, pins)
    assert res["structural"] == [3, 3]


# ----------------------------------------------------------------- S rows: order and resolution

def _dev_eval():
    def row(i, label="supported", notes="Table 1", claim="across all runs"):
        return {"id": i, "expected_label": label, "scoring_notes": notes, "claim_text_verbatim": claim,
                "expected_evidence_sections": [], "why_this_case": ""}
    return {"papers": [
        {"paper_id": "pa", "expected_matrix": [row("P1-S1"), row("P1-S2"), row("P1-S3"),
                                               row("P1-R1", "partially_supported")]},
        {"paper_id": "pb", "expected_matrix": [row("P2-S1"), row("P2-S2", notes="no table"),
                                               row("P2-S3", claim="plain claim")]},
    ]}


def _match_map():
    return {"rows": {r: {"claim_fingerprint": "f_" + r} for r in ("P1-S1", "P1-S2", "P1-S3", "P2-S1", "P2-S2", "P2-S3")}
            | {"P1-R1": {"claim_fingerprint": "f_P1-S2"}}}


def test_row_infos_order_and_criteria():
    infos = br.row_infos(_dev_eval(), _match_map())
    by = {x["row_id"]: x for x in infos}
    assert by["P1-S2"]["d"] is False  # shares its claim with refusal-class row P1-R1
    assert by["P2-S2"]["b"] is False and by["P2-S3"]["c"] is False
    full = br.ordered_full_rows(infos)
    assert [x["row_id"] for x in full] == ["P1-S1", "P1-S3", "P2-S1"]
    assert br.reproduce_selection(full) == ["P1-S1", "P2-S1", "P1-S3"]


def test_resolve_s_rows_replaces_in_existing_order_and_skips_unidentified():
    def r(i, paper, tables):
        return {"row_id": i, "paper": paper, "tables_cited": tables}
    s_rows = {"selected": [r("P1-S1", "P1", ["1"]), r("P7-S2", "P7", ["1"]), r("P9-S4", "P9", ["6"])]}
    pool = [r("P1-S2", "P1", ["2"]), r("P1-S3", "P1", ["3"]), r("P1-S4", "P1", ["3", "4"])]
    bad = {("P7", 1), ("P1", 2), ("P9", 6)}
    ok = lambda p, n: ((p, n) not in bad, "no caption" if (p, n) in bad else "")  # noqa: E731
    out = br.resolve_s_rows(s_rows, pool, ok)
    assert out["selected_final"] == ["P1-S1", "P1-S3", "P1-S4"]
    assert [(x["old"], x["new"]) for x in out["replacements"]] == [("P7-S2", "P1-S3"), ("P9-S4", "P1-S4")]
    assert [x["row"] for x in out["skipped_candidates"]] == ["P1-S2"]
    assert {(x["paper"], x["table"]) for x in out["unidentified_tables"]} == {("P7", 1), ("P9", 6)}


def test_resolve_s_rows_no_replacement_available():
    s_rows = {"selected": [{"row_id": "P7-S2", "paper": "P7", "tables_cited": ["1"]}]}
    out = br.resolve_s_rows(s_rows, [], lambda p, n: (False, "x"))
    assert out["selected_final"] == [None] and out["replacements"][0]["new"] is None


# ----------------------------------------------------------------- paper source and builder (synthetic)

MAIN = r"""\documentclass{article}
\newcommand{\best}[1]{\textbf{#1}}
\begin{document}
\begin{table}
\caption{Results of the first experiment on the long benchmark suite with many words.}
\begin{tabular}{lc}\toprule M & S \\ \midrule a & \best{1.5} \\ b & 2.5 \\ \bottomrule\end{tabular}
\end{table}
\begin{table}
\caption{A second table with a different caption on the other benchmark suite entirely.}
\begin{tabular}{lc}\toprule M & S \\ \midrule c & 3 \\ \bottomrule\end{tabular}
\end{table}
\begin{table}
\begin{tabular}{lc} no & caption \\ \end{tabular}
\end{table}
\end{document}
"""


def _make_src(tmp_path, pid="2610.00001v1"):
    src = tmp_path / pid / "src"
    src.mkdir(parents=True)
    (src / "main.tex").write_text(MAIN, encoding="utf-8")
    return pid


def test_paper_tables_candidates_and_parse(tmp_path):
    pid = _make_src(tmp_path)
    pt = lt.PaperTables(tmp_path / pid / "src")
    assert [i for i, _ in pt.candidates()] == [1, 2]
    parsed = pt.parse(1)
    assert texts(parsed) == [["M", "S"], ["a", "1.5"], ["b", "2.5"]]
    assert pt.get(3)["caption_plain"] is None


def test_builder_identifies_by_caption_not_by_number(tmp_path):
    pid = _make_src(tmp_path)

    def reader(path, number):
        return {7: ["Results of the first experiment on the long benchmark suite with"],
                8: ["A second table with a different caption on the other"],
                9: [], 10: ["Table text that matches nothing in the source at all here"]}[number]

    b = br.Builder(pdf_dir=tmp_path, src_root=tmp_path, reader=reader)
    t7 = b.table(pid, 7)
    assert t7["identified"] and t7["latex_index"] == 1 and t7["table"]["caption_number"] == 7
    assert b.table(pid, 8)["latex_index"] == 2
    assert b.table(pid, 9)["status"] == "pdf-none"
    assert b.table(pid, 10)["status"] == "latex-none"
    assert b.table(pid, 9)["table"] is None


def test_schema_and_grid_render(tmp_path):
    t = _schema(tab(r"H & I & J \\ \midrule \multirow{2}{*}{G} & \multicolumn{2}{c}{w} \\ & 1 & 2 \\"))
    assert t["schema_version"] == 1 and t["row_keys"] and t["col_keys"]
    assert set(t["cells"][0]) == {"row", "col", "row_span", "col_span", "text", "is_column_header",
                                  "is_row_header", "is_section_row"}
    grid = lt.render_grid_md(t)
    assert "G [rs=2]" in grid and "w [cs=2]" in grid and "^" in grid and "<" in grid
