"""Synthetic tables only (no reference tables, no forms file, no labels)."""
import pytest

from eval.auditor_v2 import t2r_check as ck


def C(r, c, text, rs=1, cs=1, col_h=False):
    return {"row": r, "col": c, "row_span": rs, "col_span": cs, "text": text,
            "is_column_header": col_h, "is_row_header": False, "is_section_row": False}


def table(rows, n_header=1, spans=None):
    """rows: list of lists of strings. spans: {(r, c): (row_span, col_span)}; a None entry is covered."""
    spans = spans or {}
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text is None:
                continue
            rs, cs = spans.get((r, c), (1, 1))
            cells.append(C(r, c, text, rs=rs, cs=cs, col_h=r < n_header))
    return {"table_index": 0, "page": 1, "caption_text": "Table 1: x", "caption_number": 1, "footnotes": [],
            "n_rows": len(rows), "n_cols": max(len(r) for r in rows), "cells": cells}


BASE = table([
    ["Method", "A", "B"],
    ["Base", "1.0", "2.0"],
    ["Ours", "1.5", "2.5"],
    ["Other", "1.2", "2.0"],
])


def form(rule, rows=None, columns=None, rbc=None, excluded=None, **params):
    p = {"op": None, "constant": None, "polarity": None, "tolerance": 0, "k": None, "pairs": [],
         "count": None, "distinct_on": []}
    p.update(params)
    return {"table_ref": "T", "rule": rule, "reading": "only", "rows": rows or [], "rows_by_columns": rbc or [],
            "columns": columns or [], "params": p, "excluded_rows": excluded or [], "partial": False}


def run(f, t=BASE):
    return ck.check_form(f, lambda ref: t if ref == "T" else None)


# ----------------------------------------------------------------- all_cmp, tolerance

def test_all_cmp_holds():
    r = run(form("all_cmp", rows=["Ours"], columns=["A", "B"], op=">", constant=1))
    assert r["result"] == "holds"


def test_all_cmp_contradicted_records_exact_cells():
    r = run(form("all_cmp", rows=["Base", "Ours"], columns=["A", "B"], op=">", constant=1.2))
    assert r["result"] == "contradicted"
    cells = {(c["row_key"], c["column_key"], c["value"]) for c in r["breaking_cells"]}
    assert cells == {("Base", "A", "1.0")}
    c = r["breaking_cells"][0]
    assert c["table"] == "T" and c["row_index"] == 1 and c["column_index"] == 1


def test_all_cmp_less_than_constant():
    assert run(form("all_cmp", rows=["Base"], columns=["A"], op="<", constant=1.5))["result"] == "holds"
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op="<", constant=1.5))["result"] == "tie"
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op="<=", constant=1.5))["result"] == "holds"
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op="<", constant=1.4))["result"] == "contradicted"


def test_tolerance_equality_and_inequality():
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op="==", constant=1.52, tolerance=0.05))["result"] == "holds"
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op="==", constant=1.6, tolerance=0.05))["result"] == "contradicted"
    # >= with rounding slack: 1.0 >= 1.04 within 0.05
    assert run(form("all_cmp", rows=["Base"], columns=["A"], op=">=", constant=1.04, tolerance=0.05))["result"] == "holds"
    assert run(form("all_cmp", rows=["Base"], columns=["A"], op=">=", constant=1.2, tolerance=0.05))["result"] == "contradicted"


def test_equality_allowed_when_op_allows_it():
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op=">=", constant=1.5))["result"] == "holds"


# ----------------------------------------------------------------- beats_baseline, polarity, tie

PAIR_BASE = {"method": "Ours", "baseline": "Base"}


def test_beats_baseline_holds_and_contradicted():
    assert run(form("beats_baseline", columns=["A", "B"], op=">", polarity="higher", pairs=[PAIR_BASE]))["result"] == "holds"
    r = run(form("beats_baseline", columns=["A", "B"], op=">", polarity="higher",
                 pairs=[{"method": "Other", "baseline": "Ours"}]))
    assert r["result"] == "contradicted"
    # the breaking cells include method and baseline cells of every broken pair
    assert {(c["row_key"], c["column_key"]) for c in r["breaking_cells"]} == {
        ("Other", "A"), ("Ours", "A"), ("Other", "B"), ("Ours", "B")}


def test_polarity_lower_flips_direction():
    assert run(form("beats_baseline", columns=["A"], op=">", polarity="lower", pairs=[PAIR_BASE]))["result"] == "contradicted"
    assert run(form("beats_baseline", columns=["A"], op=">", polarity="lower",
                    pairs=[{"method": "Base", "baseline": "Ours"}]))["result"] == "holds"


def test_exact_tie_on_strict_comparison_is_tie():
    r = run(form("beats_baseline", columns=["B"], op=">", polarity="higher",
                 pairs=[{"method": "Other", "baseline": "Base"}]))
    assert r["result"] == "tie" and r["breaking_cells"] == []


def test_tie_on_non_strict_comparison_holds():
    assert run(form("beats_baseline", columns=["B"], op=">=", polarity="higher",
                    pairs=[{"method": "Other", "baseline": "Base"}]))["result"] == "holds"


def test_tie_with_a_contradiction_elsewhere_is_contradicted():
    r = run(form("beats_baseline", columns=["A", "B"], op=">", polarity="higher",
                 pairs=[{"method": "Other", "baseline": "Base"}, {"method": "Base", "baseline": "Ours"}]))
    assert r["result"] == "contradicted"


# ----------------------------------------------------------------- best_in_column

def test_best_in_column():
    assert run(form("best_in_column", rows=["Ours", "Base", "Other"], columns=["A", "B"], op=">",
                    polarity="higher"))["result"] == "holds"
    r = run(form("best_in_column", rows=["Other", "Base", "Ours"], columns=["A"], op=">", polarity="higher"))
    assert r["result"] == "contradicted"
    assert run(form("best_in_column", rows=["Base", "Ours"], columns=["A"], op=">", polarity="lower"))["result"] == "holds"


# ----------------------------------------------------------------- count_rows

def test_count_rows_listed_and_all():
    assert run(form("count_rows", rows=["Base", "Ours"], op="==", count=2))["result"] == "holds"
    assert run(form("count_rows", op="==", count=3))["result"] == "holds"
    assert run(form("count_rows", op="==", count=4))["result"] == "contradicted"


def test_count_rows_excluded_rows_leave_the_count():
    assert run(form("count_rows", excluded=["Base"], op="==", count=2))["result"] == "holds"


def test_count_rows_distinct_on():
    t = table([["Name", "Mode"], ["a", "T"], ["b", "T"], ["c", "NT"]])
    assert run(form("count_rows", op="==", count=2, distinct_on=["Mode"]), t)["result"] == "holds"
    assert run(form("count_rows", op="==", count=3, distinct_on=["Mode"]), t)["result"] == "contradicted"
    assert run(form("count_rows", op="==", count=3, distinct_on=["Nope"]), t)["result"] == "cannot_check"


def test_count_rows_unresolvable_listed_row_cannot_check():
    assert run(form("count_rows", rows=["Base", "Ghost"], op="==", count=2))["result"] == "cannot_check"


# ----------------------------------------------------------------- count_satisfying

def test_count_satisfying_constant_at_least_k():
    f = dict(rows=["Base"], columns=["A", "B"], op="<=", constant=1.0)
    assert run(form("count_satisfying", k=1, **f))["result"] == "holds"
    assert run(form("count_satisfying", k=2, **f))["result"] == "contradicted"


def test_count_satisfying_pairs_and_tie():
    pairs = [{"method": "Other", "baseline": "Base"}, {"method": "Ours", "baseline": "Base"}]
    assert run(form("count_satisfying", columns=["B"], op=">", polarity="higher", k=1, pairs=pairs))["result"] == "holds"
    assert run(form("count_satisfying", columns=["B"], op=">", polarity="higher", k=2, pairs=pairs))["result"] == "tie"
    assert run(form("count_satisfying", columns=["B"], op=">", polarity="higher", k=3, pairs=pairs))["result"] == "contradicted"


def test_count_satisfying_unreadable_cell_cannot_check():
    t = table([["Method", "A"], ["Base", "1.0"], ["Ours", "-"]])
    r = run(form("count_satisfying", columns=["A"], op=">", polarity="higher", k=1,
                 pairs=[{"method": "Ours", "baseline": "Base"}]), t)
    assert r["result"] == "cannot_check"


# ----------------------------------------------------------------- missing / unreadable

@pytest.mark.parametrize("cell", ["-", "—", "N/A", "OOM", "", "abc"])
def test_missing_blank_or_unparsable_cell_is_cannot_check(cell):
    t = table([["Method", "A"], ["Base", "1.0"], ["Ours", cell]])
    assert run(form("all_cmp", rows=["Ours"], columns=["A"], op=">", constant=0), t)["result"] == "cannot_check"
    assert run(form("beats_baseline", columns=["A"], op=">", polarity="higher", pairs=[PAIR_BASE]), t)["result"] == "cannot_check"


def test_missing_row_or_column_or_comparator_is_cannot_check():
    assert run(form("all_cmp", rows=["Ghost"], columns=["A"], op=">", constant=0))["result"] == "cannot_check"
    assert run(form("all_cmp", rows=["Ours"], columns=["Z"], op=">", constant=0))["result"] == "cannot_check"
    assert run(form("beats_baseline", columns=["A"], op=">", polarity="higher",
                    pairs=[{"method": "Ours", "baseline": "Ghost"}]))["result"] == "cannot_check"
    assert ck.check_form(form("all_cmp", rows=["Ours"], columns=["A"], op=">", constant=0).copy() | {"table_ref": "X"},
                         lambda ref: None)["result"] == "cannot_check"


def test_contradiction_beats_unreadable_inside_one_form():
    t = table([["Method", "A", "B"], ["Base", "1.0", "-"], ["Ours", "0.5", "2.0"]])
    r = run(form("beats_baseline", columns=["A", "B"], op=">", polarity="higher", pairs=[PAIR_BASE]), t)
    assert r["result"] == "contradicted"


# ----------------------------------------------------------------- rows_by_columns, spans, labels

def test_rows_by_columns_selector():
    t = table([["Setting", "Clip", "Avg"], ["S", "-", "1.0"], ["S", "85", "2.0"], ["M", "85", "3.0"]])
    sel = {"Setting": "S", "Clip": "85"}
    assert run(form("all_cmp", rbc=[sel], columns=["Avg"], op="==", constant=2.0), t)["result"] == "holds"
    # a selector that matches two rows is not a unique row
    assert run(form("all_cmp", rbc=[{"Clip": "85"}], columns=["Avg"], op=">", constant=0), t)["result"] == "cannot_check"
    # dashes are compared as one character ("–" in a form, "-" in the table)
    assert run(form("all_cmp", rbc=[{"Setting": "S", "Clip": "–"}], columns=["Avg"], op="==", constant=1.0), t)["result"] == "holds"


def test_spanning_cell_resolves_to_the_spanning_value_at_every_covered_column():
    t = table([["Method", "A", "B", "C"], ["Base", "1.0", "1.0", "1.0"], ["Span", "5.0", None, None]],
              spans={(2, 1): (1, 3)})
    r = run(form("beats_baseline", columns=["A", "B", "C"], op=">", polarity="higher",
                 pairs=[{"method": "Span", "baseline": "Base"}]), t)
    assert r["result"] == "holds"
    assert [e["cells"][0]["value"] for e in r["elements"]] == ["5.0", "5.0", "5.0"]
    r = run(form("all_cmp", rows=["Span"], columns=["C"], op="<", constant=2), t)
    assert r["result"] == "contradicted" and r["breaking_cells"][0]["column_index"] == 3


def test_label_glyph_and_spacing_differences_do_not_matter():
    t = table([["Method", "Δ stream"], ["Row A", "1.0"]])
    assert run(form("all_cmp", rows=["Row A"], columns=["∆stream"], op=">", constant=0), t)["result"] == "holds"


def test_row_path_with_section_and_marker_fallback():
    t = table([["Method", "A"], ["Best KT", "1.0"], ["Ours", "2.0"]])
    assert run(form("all_cmp", rows=["Best KT†"], columns=["A"], op=">", constant=0), t)["result"] == "holds"


def test_sd_pair_and_percent_cells_are_numbers():
    t = table([["Method", "A", "B"], ["Ours", "83.1 ± 0.4", "18%"]])
    assert run(form("all_cmp", rows=["Ours"], columns=["A", "B"], op=">", constant=17), t)["result"] == "holds"


# ----------------------------------------------------------------- claim order and merge

def _item(forms_results, members=(), caveats=()):
    return ck.claim_result({"id": "X", "paper": "p", "claimed_group": [{"member": m, "status": s} for m, s in members],
                            "caveat_refs": list(caveats)}, [{"result": r} for r in forms_results])


def test_claim_result_order():
    assert _item([])["code_result"] == ck.CODE_NONE
    assert _item(["holds", "contradicted", "cannot_check"], [("m", "absent")], ["c"])["code_result"] == ck.CODE_PS
    assert _item(["holds", "cannot_check"], [("m", "absent")], ["c"])["code_result"] == ck.CODE_NR
    assert _item(["holds", "tie"], [("m", "absent")], ["c"])["code_result"] == ck.CODE_PS
    assert _item(["holds"], [("m", "other_table: Table 3")])["code_result"] == ck.CODE_NR
    assert _item(["holds", "tie"])["code_result"] == ck.CODE_NR
    assert _item(["holds"], [("m", "covered")], ["a caveat"])["code_result"] == ck.CODE_NR
    assert _item(["holds"], [("m", "covered")])["code_result"] == ck.CODE_HOLDS


def test_absent_member_is_recorded():
    r = _item(["holds"], [("m1", "absent"), ("m2", "covered")])
    assert r["absent_members"] == ["m1"]


@pytest.mark.parametrize("run1,code,expected", [
    ("supported", "PS", "partially_supported"),
    ("supported", "Needs review", "needs_review"),
    ("supported", "holds", "supported"),
    ("supported", "no_code_result", "supported"),
    ("partially_supported", "PS", "partially_supported"),
    ("partially_supported", "Needs review", "partially_supported"),
    ("not_supported", "PS", "not_supported"),
    ("not_supported", "Needs review", "not_supported"),
    ("not_supported", "holds", "not_supported"),
    (None, "PS", None),
])
def test_merge_can_only_lower_and_needs_review_only_replaces_supported(run1, code, expected):
    assert ck.merge_label(run1, code) == expected
