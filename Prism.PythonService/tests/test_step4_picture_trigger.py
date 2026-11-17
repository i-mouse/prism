"""Unit tests for eval/step4/picture_trigger.py on a made-up reference table and made-up row ids. No paper, no
real reference table, no model call."""
from types import SimpleNamespace

from eval import score_a1, score_screen
from eval.step4 import picture_trigger as pt
from eval.step4 import tablefind


def _cell(text, row, col, header=False, row_header=False):
    return {"text": text, "row": row, "col": col, "row_span": 1, "col_span": 1,
            "is_column_header": header, "is_row_header": row_header, "is_section_row": False}


# Gadget | Small | Large
# Alpha  | 41.5  | 38.2
# Bravo  | 44.0  | 36.9
REF = {
    "caption_number": 1, "n_rows": 3, "n_cols": 3,
    "cells": [
        _cell("Gadget", 0, 0, header=True), _cell("Small", 0, 1, header=True), _cell("Large", 0, 2, header=True),
        _cell("Alpha", 1, 0, row_header=True), _cell("41.5", 1, 1), _cell("38.2", 1, 2),
        _cell("Bravo", 2, 0, row_header=True), _cell("44.0", 2, 1), _cell("36.9", 2, 2),
    ],
}


def _quoted(row="Bravo sorter", column="Small", value="44.0", table=1):
    return {"table": table, "row_label": row, "column_label": column, "value": value}


def test_a_value_in_its_own_row_and_column_is_a_match():
    assert pt.cell_reading(_quoted(), REF) == "match"
    assert pt.cell_reading(_quoted(row="bravo", column="SMALL load", value="44"), REF) == "match"


def test_a_value_quoted_under_another_row_or_column_is_a_layout_misread():
    assert pt.cell_reading(_quoted(row="Alpha sorter"), REF) == "misread"       # the value is Bravo's
    assert pt.cell_reading(_quoted(column="Large"), REF) == "misread"           # the value is in the Small column


def test_a_value_that_is_not_in_the_reference_or_is_not_numeric_is_not_a_misread():
    assert pt.cell_reading(_quoted(value="99.9"), REF) == "not_in_reference"
    assert pt.cell_reading(_quoted(value="n/a"), REF) == "not_numeric"
    assert pt.cell_reading(_quoted(value="fast"), REF) == "not_numeric"


def test_run_reading_counts_and_skips_cells_of_tables_without_a_reference():
    cells = [_quoted(), _quoted(row="Alpha sorter"), _quoted(value="99.9"), _quoted(table=8)]
    reading = pt.run_reading(cells, {1: REF})
    assert reading == {
        "quoted": 4, "with_reference": 3, "match": 1, "misread": 1, "not_in_reference": 1, "not_numeric": 0,
        "layout_misread": True,
    }
    assert pt.run_reading([_quoted()], {1: REF})["layout_misread"] is False
    assert pt.run_reading([], {1: REF})["quoted"] == 0


def test_quoted_cells_come_from_every_piece_of_the_trace():
    claim = {"table_check": {"pieces": [{"cells": [_quoted()]}, {"cells": []}, {"cells": [_quoted(value="36.9")]}]}}
    assert len(pt.quoted_cells(claim)) == 2
    assert pt.quoted_cells(None) == [] and pt.quoted_cells({"label": "supported"}) == []
    assert pt.quoted_cells({"table_check": {"routed": False}}) == []


def _patch_rows(monkeypatch, claims_per_run):
    """Three made-up target rows (X1 with a reference table, X2 without, X3 parked) and per-run claims for X1."""
    monkeypatch.setattr(score_a1, "MISS_ROWS", ("X1", "X2", "X3"))
    monkeypatch.setattr(score_screen, "PARKED_ROWS", ("X3",))
    monkeypatch.setattr(tablefind, "ROW_TABLES", {"X1": ("X1-TA",)})
    monkeypatch.setattr(tablefind, "TABLE_NUMBERS", {"X1-TA": 1})
    by_folder = dict(zip(("d1", "d2", "d3"), claims_per_run))
    monkeypatch.setattr(score_a1, "_row_claim", lambda row, folder: by_folder[folder])
    rows = {rid: SimpleNamespace(row_id=rid, paper_id=f"paper-{rid}", claim_index=0) for rid in ("X1", "X2")}
    return rows


def _claim(*cells):
    return {"table_check": {"routed": True, "pieces": [{"cells": list(cells)}]}}


def test_targets_are_the_miss_rows_minus_the_parked_rows(monkeypatch):
    _patch_rows(monkeypatch, [None, None, None])
    assert pt.target_rows() == ["X1", "X2"]


def test_trigger_needs_a_misread_in_two_of_three_runs(monkeypatch, capsys):
    misread, fine = _claim(_quoted(row="Alpha sorter")), _claim(_quoted())
    rows = _patch_rows(monkeypatch, [misread, misread, fine])
    report = pt.build_report(rows, ["d1", "d2", "d3"], {"X1-TA": REF})
    x1, x2 = report["rows"]
    assert (x1["has_reference"], x1["runs_with_layout_misread"], x1["layout_misread_voted"]) == (True, 2, True)
    assert (x2["has_reference"], x2["per_run"], x2["layout_misread_voted"]) == (False, [], False)
    assert report["trigger"] is True

    pt.print_report(report)
    out = capsys.readouterr().out
    assert any(line.split() == ["X2", "no", "reference", "table"] for line in out.splitlines()) and "Rows with no reference table: 1 of 2" in out
    assert out.rstrip().endswith("runs): y")
    assert "44.0" not in out and "Alpha" not in out and "Bravo" not in out     # ids, counts and y/n only


def test_one_run_with_a_misread_does_not_trigger(monkeypatch):
    rows = _patch_rows(monkeypatch, [_claim(_quoted(row="Alpha sorter")), _claim(_quoted()), None])
    report = pt.build_report(rows, ["d1", "d2", "d3"], {"X1-TA": REF})
    assert report["rows"][0]["runs_with_layout_misread"] == 1 and report["trigger"] is False


def test_run_refuses_a_wrong_folder_count(tmp_path, capsys):
    assert pt.run([tmp_path]) == 1
    assert "exactly 3 folders" in capsys.readouterr().out
