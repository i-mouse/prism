import json

import pytest

from eval.auditor_v2 import t1_score
from eval.auditor_v2 import table_keys as tk


def C(r, c, text, rs=1, cs=1, col_h=False, row_h=False, sec=False):
    return {
        "row": r, "col": c, "row_span": rs, "col_span": cs, "text": text,
        "is_column_header": col_h, "is_row_header": row_h, "is_section_row": sec,
    }


def T(cells, n_rows, n_cols, caption="Table 1: x"):
    return {
        "table_index": 0, "page": 1, "caption_text": caption,
        "caption_number": tk.caption_number(caption), "footnotes": [],
        "n_rows": n_rows, "n_cols": n_cols, "cells": cells,
    }


def grid(rows, n_header=1, caption="Table 1: x", flag_sections=False):
    cells = []
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text is None:
                continue
            cells.append(C(r, c, text, col_h=r < n_header))
    return T(cells, len(rows), max(len(r) for r in rows), caption)


# ------------------------------------------------------------- normaliser

def test_normalize_label_nfkc_casefold_whitespace():
    assert tk.normalize_label("  Best Deep \n KT+ ") == "best deep kt+"
    assert tk.normalize_label("Ａ０９") == "a09"  # fullwidth
    assert tk.normalize_label("ﬁne") == "fine"  # ligature
    assert tk.normalize_label("STRASSE") == tk.normalize_label("Straße")  # casefold


def test_normalizer_does_not_map_greek_or_arrows():
    assert tk.normalize_label("Δmacro") != tk.normalize_label("deltamacro")
    assert tk.normalize_label("λ=5") != tk.normalize_label("lambda=5")
    assert tk.normalize_label("±") != tk.normalize_label("+-")


def test_marker_fallback_unique_match():
    paths = {0: ["Best deep KT"], 1: ["Other"]}
    assert tk._unique_match(paths, ["Best deep KT+"]) == [0]


def test_marker_fallback_ambiguous_is_no_match():
    paths = {0: ["Model*"], 1: ["Model†"]}
    assert tk._unique_match(paths, ["Model+"]) == []


def test_exact_match_wins_over_fallback():
    paths = {0: ["Model+"], 1: ["Model"]}
    assert tk._unique_match(paths, ["Model+"]) == [0]


@pytest.mark.parametrize(
    "caption,number",
    [("Table 3: foo", 3), ("Table 3 | foo", 3), ("Table 2. Planroom", 2), ("Tab. 3 foo", 3),
     ("TABLE 10: foo", 10), ("Table 10: foo", 10), ("Figure 3: foo", None), ("", None), (None, None)],
)
def test_caption_number_styles(caption, number):
    assert tk.caption_number(caption) == number


# ------------------------------------------------------------ column paths

def p1_t4_shape():
    # corner "Effect" spans two header rows; group headers over leaf headers
    cells = [
        C(0, 0, "Effect", rs=2, col_h=True),
        C(0, 1, "Sampled OPD", col_h=True), C(0, 2, "REINFORCE++", cs=3, col_h=True),
        C(1, 1, "no weight", col_h=True), C(1, 2, "lambda=5", col_h=True),
        C(1, 3, "lambda=10", col_h=True), C(1, 4, "lambda=20", col_h=True),
        C(2, 0, "deltamacro Avg@8"), C(2, 1, "+0.30"), C(2, 2, "-0.38"), C(2, 3, "-1.00"), C(2, 4, "-1.76"),
        C(3, 0, "deltamacro Pass@8"), C(3, 1, "+0.64"), C(3, 2, "-3.41"), C(3, 3, "-3.50"), C(3, 4, "-3.91"),
    ]
    return T(cells, 4, 5, "Table 4: The same teacher-peak branch")


def test_column_paths_with_spanned_headers():
    t = p1_t4_shape()
    k = tk.derive_keys(t)
    assert k.col_paths[1] == ["Sampled OPD", "no weight"]
    assert k.col_paths[2] == ["REINFORCE++", "lambda=5"]
    assert k.col_paths[4] == ["REINFORCE++", "lambda=20"]
    assert k.col_paths[0] == ["Effect"]


def test_cell_found_by_key_paths_not_position():
    t = p1_t4_shape()
    k = tk.derive_keys(t)
    pin = {"row_key_path": ["deltamacro Avg@8"], "column_key_path": ["Sampled OPD", "no weight"], "value": "+0.30"}
    assert tk.evaluate_cell(t, k, pin)["correct"]
    pin2 = dict(pin, value="+0.31")
    assert not tk.evaluate_cell(t, k, pin2)["correct"]
    # same value, wrong column path: not correct
    pin3 = dict(pin, column_key_path=["REINFORCE++", "lambda=5"])
    assert not tk.evaluate_cell(t, k, pin3)["correct"]


def test_label_column_is_not_a_data_column():
    t = p1_t4_shape()
    k = tk.derive_keys(t)
    assert 0 in k.label_cols
    assert tk.unique_col(t, k, ["Effect"]) is None


def p11_t3_shape():
    cells = [
        C(0, 0, "Method", rs=2, col_h=True), C(0, 1, "Omni-MATH-2", col_h=True), C(0, 2, "KernelBench", cs=2, col_h=True),
        C(1, 1, "Acc.", col_h=True), C(1, 2, "Acc.", col_h=True), C(1, 3, "Fast1", col_h=True),
        C(2, 0, "Student"), C(2, 1, "34.3"), C(2, 2, "9.2"), C(2, 3, "12"),
        C(3, 0, "SeqKD (Kim & Rush, 2016)"), C(3, 1, "40.1"), C(3, 2, "20.0"), C(3, 3, "20"),
        C(4, 0, "UTT (Ours)"), C(4, 1, "62.4"), C(4, 2, "50.0"), C(4, 3, "32"),
    ]
    return T(cells, 5, 4, "Table 3: Comparison with KD methods under the Pro→Qwen setting.")


def test_duplicate_leaf_header_disambiguated_by_group():
    t = p11_t3_shape()
    k = tk.derive_keys(t)
    assert k.col_paths[1] == ["Omni-MATH-2", "Acc."]
    assert k.col_paths[2] == ["KernelBench", "Acc."]
    assert k.col_paths[3] == ["KernelBench", "Fast1"]
    for rowkey, colkey, value in [
        (["Student"], ["KernelBench", "Acc."], "9.2"),
        (["UTT (Ours)"], ["KernelBench", "Fast1"], "32"),
        (["UTT (Ours)"], ["Omni-MATH-2", "Acc."], "62.4"),
    ]:
        pin = {"row_key_path": rowkey, "column_key_path": colkey, "value": value}
        assert tk.evaluate_cell(t, k, pin)["correct"], pin
    # a bare "Acc." is ambiguous -> no match
    assert tk.unique_col(t, k, ["Acc."]) is None


# ------------------------------------------------- equal / suffix path matching

def test_path_match_exact():
    paths = {0: ["A", "B"], 1: ["A", "C"]}
    assert tk._unique_match(paths, ["A", "B"]) == [0]


def test_path_match_suffix_under_title_row_p1_t4_shape():
    # a full-width title row sits above the group and leaf headers
    cells = [
        C(0, 0, "Effect of the teacher-peak branch", cs=5, col_h=True),
        C(1, 0, "Metric", col_h=True), C(1, 1, "Sampled OPD", col_h=True), C(1, 2, "REINFORCE++", cs=3, col_h=True),
        C(2, 1, "no weight", col_h=True), C(2, 2, "lambda=5", col_h=True),
        C(2, 3, "lambda=10", col_h=True), C(2, 4, "lambda=20", col_h=True),
        C(3, 0, "deltamacro Avg@8"), C(3, 1, "+0.30"), C(3, 2, "-0.38"), C(3, 3, "-1.00"), C(3, 4, "-1.76"),
    ]
    t = T(cells, 4, 5, "Table 4: x")
    k = tk.derive_keys(t)
    assert k.col_paths[1] == ["Effect of the teacher-peak branch", "Sampled OPD", "no weight"]
    pin = {"row_key_path": ["deltamacro Avg@8"], "column_key_path": ["Sampled OPD", "no weight"], "value": "+0.30"}
    assert tk.evaluate_cell(t, k, pin)["correct"]
    pin2 = dict(pin, column_key_path=["REINFORCE++", "lambda=5"], value="-0.38")
    assert tk.evaluate_cell(t, k, pin2)["correct"]
    # the full derived path still matches (equal)
    pin3 = dict(pin, column_key_path=["Effect of the teacher-peak branch", "Sampled OPD", "no weight"])
    assert tk.evaluate_cell(t, k, pin3)["correct"]


def test_path_match_suffix_under_spanning_group_header_p6_t10_shape():
    cells = [
        C(0, 0, "Model", rs=2, col_h=True), C(0, 1, "Finding Attribute", cs=3, col_h=True),
        C(1, 1, "Diagnosis", col_h=True), C(1, 2, "Globules", col_h=True), C(1, 3, "Detection", col_h=True),
        C(2, 0, "Medical VLMs"),
        C(3, 0, "Lingshu-32B"), C(3, 1, "83.0 / 73.0"), C(3, 2, "10.0 / 20.0"), C(3, 3, "44.5 / 53.3"),
    ]
    t = T(cells, 4, 4, "Table 10: x")
    k = tk.derive_keys(t)
    assert k.col_paths[3] == ["Finding Attribute", "Detection"]
    pin = {"row_key_path": ["Medical VLMs", "Lingshu-32B"], "column_key_path": ["Detection"], "value": "44.5 / 53.3"}
    assert tk.evaluate_cell(t, k, pin)["correct"]


def test_ambiguous_suffix_is_no_match():
    paths = {0: ["Omni", "Acc."], 1: ["Kernel", "Acc."]}
    assert tk._unique_match(paths, ["Acc."]) == []
    # equal path plus a suffix path: the equal path wins (tier 1), suffix candidates are ignored
    assert tk._unique_match({0: ["Acc."], 1: ["Kernel", "Acc."]}, ["Acc."]) == [0]
    # a suffix hit in only one path is unique
    assert tk._unique_match({0: ["Omni", "Acc."], 1: ["Kernel", "Fast1"]}, ["Acc."]) == [0]


def test_tiers_do_not_fall_through_when_a_tier_is_ambiguous():
    # tier 1 has two exact candidates -> no match (even though a suffix path is unique)
    assert tk._unique_match({0: ["A"], 1: ["A"], 2: ["X", "A"]}, ["A"]) == []
    # tier 2 has two suffix candidates -> no match (even though a marker path would be unique)
    assert tk._unique_match({0: ["X", "A"], 1: ["Y", "A"], 2: ["A+"]}, ["A"]) == []
    # tier 3 is used only when tiers 1-2 find none
    assert tk._unique_match({0: ["X", "A+"]}, ["A"]) == [0]
    assert tk._unique_match({0: ["A+"], 1: ["X", "A"]}, ["A"]) == [1]  # tier 2 hit beats the marker candidate


def test_longer_pin_never_matches():
    assert tk._unique_match({0: ["B"]}, ["A", "B"]) == []
    assert tk._unique_match({0: []}, ["A"]) == []
    assert tk._unique_match({0: ["A"]}, []) == []


def test_suffix_must_be_trailing_not_leading_or_middle():
    paths = {0: ["Title", "Group", "Leaf"]}
    assert tk._unique_match(paths, ["Group", "Leaf"]) == [0]
    assert tk._unique_match(paths, ["Title", "Group"]) == []
    assert tk._unique_match(paths, ["Group"]) == []


def test_suffix_rule_applies_to_columns_and_rows_alike():
    t = p6_t10_shape()
    k = tk.derive_keys(t)
    # rows: section + model; bare model name is a unique suffix
    assert tk.unique_row(t, k, ["MedGemma-4B"]) == 5
    # a duplicate model name under two sections is ambiguous for the bare name
    t["cells"].append(C(7, 0, "Lingshu-32B"))
    t["cells"].append(C(7, 1, "1 / 2"))
    t["n_rows"] = 8
    k = tk.derive_keys(t)
    assert tk.unique_row(t, k, ["Lingshu-32B"]) is None
    assert tk.unique_row(t, k, ["Medical VLMs", "Lingshu-32B"]) is None  # same section twice -> ambiguous


# --------------------------------------------------------------- row paths

def p6_t10_shape():
    rows = [
        ("Model", "Diagnosis", "Detection"),
    ]
    cells = [C(0, 0, "Model", col_h=True), C(0, 1, "Diagnosis", col_h=True), C(0, 2, "Detection", col_h=True),
             C(1, 0, "General-purpose VLMs"),
             C(2, 0, "InternVL3-8B"), C(2, 1, "80.0 / 70.0"), C(2, 2, "10.0 / 20.0"),
             C(3, 0, "Qwen3-VL-32B"), C(3, 1, "81.0 / 71.0"), C(3, 2, "11.0 / 21.0"),
             C(4, 0, "Medical VLMs"),
             C(5, 0, "MedGemma-4B"), C(5, 1, "82.0 / 72.0"), C(5, 2, "12.0 / 22.0"),
             C(6, 0, "Lingshu-32B"), C(6, 1, "83.0 / 73.0"), C(6, 2, "44.5 / 53.3")]
    return T(cells, 7, 3, "Table 10: Evaluation performance on ISIC 2018.")


def test_section_rows_prefix_following_rows():
    t = p6_t10_shape()
    k = tk.derive_keys(t)
    assert k.section_rows == {1: "General-purpose VLMs", 4: "Medical VLMs"}
    assert k.row_paths[2] == ["General-purpose VLMs", "InternVL3-8B"]
    assert k.row_paths[6] == ["Medical VLMs", "Lingshu-32B"]
    assert tk.count_data_rows(k) == 4


def test_pair_cell_pin_with_section_path():
    t = p6_t10_shape()
    k = tk.derive_keys(t)
    pin = {"row_key_path": ["Medical VLMs", "Lingshu-32B"], "column_key_path": ["Detection"], "value": "44.5 / 53.3"}
    assert tk.evaluate_cell(t, k, pin)["correct"]
    # model name without its section is a unique suffix of the full path
    pin2 = dict(pin, row_key_path=["Lingshu-32B"])
    assert tk.evaluate_cell(t, k, pin2)["correct"]


def p4_t1_shape():
    # no flags from the extractor: framework label spans the Original/MASA rows
    cells = [
        C(0, 0, "Variant", cs=2, col_h=True), C(0, 2, "4K", col_h=True), C(0, 3, "64K", col_h=True), C(0, 4, "Avg.", col_h=True),
        C(1, 0, "MInfer", rs=2), C(1, 1, "Original"), C(1, 2, "97.7"), C(1, 3, "82.3"), C(1, 4, "87.0"),
        C(2, 1, "MASA"), C(2, 2, "97.93"), C(2, 3, "81.57"), C(2, 4, "87.27"),
        C(3, 0, "Seer", rs=2), C(3, 1, "Original"), C(3, 2, "90.0"), C(3, 3, "80.0"), C(3, 4, "85.0"),
        C(4, 1, "MASA"), C(4, 2, "91.0"), C(4, 3, "81.0"), C(4, 4, "86.0"),
    ]
    return T(cells, 5, 5, "Table 1: RULER results.")


def test_row_label_spans_without_flags():
    t = p4_t1_shape()
    k = tk.derive_keys(t)
    assert k.label_cols == [0, 1]
    assert k.row_paths[2] == ["MInfer", "MASA"]
    assert k.row_paths[3] == ["Seer", "Original"]
    pin = {"row_key_path": ["MInfer", "MASA"], "column_key_path": ["64K"], "value": "81.57"}
    assert tk.evaluate_cell(t, k, pin)["correct"]
    # "Original" alone is ambiguous across frameworks -> no match
    assert tk.unique_row(t, k, ["Original"]) is None
    assert len(tk.rows_by_path(t, k, ["Original"])) == 0


def test_flagged_row_headers_are_used():
    cells = [
        C(0, 0, "Model", col_h=True), C(0, 1, "AUC", col_h=True),
        C(1, 0, "JevKT", row_h=True), C(1, 1, ".709+-.059"),
        C(2, 0, "Best deep KT+", row_h=True), C(2, 1, ".749+-.049"),
    ]
    t = T(cells, 3, 2, "Table 9: x")
    k = tk.derive_keys(t)
    assert k.row_paths == {1: ["JevKT"], 2: ["Best deep KT+"]}
    pin = {"row_key_path": ["Best deep KT+"], "column_key_path": ["AUC"], "value": ".749"}
    assert tk.evaluate_cell(t, k, pin)["correct"]
    # marker-insensitive fallback: extractor dropped the "+"
    t["cells"][4]["text"] = "Best deep KT"
    k = tk.derive_keys(t)
    assert tk.evaluate_cell(t, k, pin)["correct"]


def p4_t9_shape():
    head = [C(0, 0, "Setting", col_h=True), C(0, 1, "Clip p", col_h=True), C(0, 2, "Norm alpha", col_h=True),
            C(0, 3, "4K", col_h=True), C(0, 4, "Avg.", col_h=True)]
    data = [
        ("MInference", "-", "-", "97.66", "87.13"),
        ("SeerAttention", "85", "-", "97.0", "87.76"),
        ("SeerAttention", "90", "-", "97.1", "88.09"),
        ("FlexPrefill-Llama", "90", "-", "97.2", "89.26"),
        ("FlexPrefill-Qwen", "-", "-", "60.0", "72.16"),
    ]
    cells = list(head)
    for i, row in enumerate(data, start=1):
        cells += [C(i, c, v) for c, v in enumerate(row)]
    return T(cells, 6, 5, "Table 9: Full RULER probe ablation.")


def test_named_key_columns_with_literal_dash_keys():
    t = p4_t9_shape()
    k = tk.derive_keys(t)
    pin = {"key_columns": ["Setting", "Clip p", "Norm alpha"], "row_key_path": ["SeerAttention", "85", "-"],
           "column_key_path": ["Avg."], "value": "87.76"}
    assert tk.evaluate_cell(t, k, pin)["correct"]
    pin2 = dict(pin, row_key_path=["SeerAttention", "90", "-"])
    assert not tk.evaluate_cell(t, k, pin2)["correct"]  # 88.09 there
    pin3 = dict(pin, row_key_path=["MInference", "-", "-"], value="87.13")
    assert tk.evaluate_cell(t, k, pin3)["correct"]


def test_duplicate_rows_are_ambiguous_no_match():
    rows = [["Model", "AUC"], ["A", "1.0"], ["A", "2.0"]]
    t = grid(rows)
    k = tk.derive_keys(t)
    assert tk.unique_row(t, k, ["A"]) is None
    assert not tk.evaluate_cell(t, k, {"row_key_path": ["A"], "column_key_path": ["AUC"], "value": "1.0"})["correct"]


def test_missing_cell_pin_dash():
    rows = [["Method", "A09", "DBE"], ["JevKT", ".709", "-"]]
    t = grid(rows)
    k = tk.derive_keys(t)
    assert tk.evaluate_cell(t, k, {"row_key_path": ["JevKT"], "column_key_path": ["DBE"], "value": "-"})["correct"]
    assert not tk.evaluate_cell(t, k, {"row_key_path": ["JevKT"], "column_key_path": ["DBE"], "value": ".0"})["correct"]


def test_section_row_flagged_by_extractor():
    cells = [C(0, 0, "Method", col_h=True), C(0, 1, "A09", col_h=True),
             C(1, 0, "Position 1", sec=True), C(1, 1, ""),
             C(2, 0, "JevKT"), C(2, 1, ".709"),
             C(3, 0, "Positions 2-5", sec=True), C(3, 1, ""),
             C(4, 0, "JevKT"), C(4, 1, ".650")]
    t = T(cells, 5, 2, "Table 9: x")
    k = tk.derive_keys(t)
    assert k.row_paths[2] == ["Position 1", "JevKT"] and k.row_paths[4] == ["Positions 2-5", "JevKT"]
    pin = {"row_key_path": ["Position 1", "JevKT"], "column_key_path": ["A09"], "value": ".709"}
    assert tk.evaluate_cell(t, k, pin)["correct"]


# ------------------------------------------------------------- structural

def pin_struct(kind, **kw):
    return dict({"id": "X", "kind": kind, "breaking": True, "key_uncertain": False}, **kw)


def test_row_count_and_absent_row_helpers():
    t = p4_t9_shape()
    k = tk.derive_keys(t)
    assert t1_score.evaluate_pin(t, k, pin_struct("row_count", count=5))["correct"]
    assert not t1_score.evaluate_pin(t, k, pin_struct("row_count", count=6))["correct"]
    absent = pin_struct("row_absent", match={"Setting": "FlexPrefill-Llama", "Clip p": "-", "Norm alpha": "-"})
    assert t1_score.evaluate_pin(t, k, absent)["correct"]
    present = pin_struct("row_exists", match={"Setting": "FlexPrefill-Qwen", "Clip p": "-", "Norm alpha": "-"})
    assert t1_score.evaluate_pin(t, k, present)["correct"]
    # an unfindable key column cannot confirm absence
    bad = pin_struct("row_absent", match={"Nope": "x"})
    assert not t1_score.evaluate_pin(t, k, bad)["correct"]


def test_name_set_label_absent_group_counts_caption():
    t = p6_t10_shape()
    k = tk.derive_keys(t)
    ok = pin_struct("name_set", names=["InternVL3-8B", "Lingshu-32B"])
    assert t1_score.evaluate_pin(t, k, ok)["correct"]
    missing = pin_struct("name_set", names=["InternVL3-8B", "Nope"])
    assert not t1_score.evaluate_pin(t, k, missing)["correct"]
    assert t1_score.evaluate_pin(t, k, pin_struct("label_absent", contains="BreastGPT"))["correct"]
    assert not t1_score.evaluate_pin(t, k, pin_struct("label_absent", contains="medgemma"))["correct"]
    groups = pin_struct("group_counts", groups={"General-purpose VLMs": 2, "Medical VLMs": 2})
    assert t1_score.evaluate_pin(t, k, groups)["correct"]
    assert not t1_score.evaluate_pin(t, k, pin_struct("group_counts", groups={"Medical VLMs": 5}))["correct"]
    t11 = p11_t3_shape()
    k11 = tk.derive_keys(t11)
    cap = pin_struct("caption", fragments=["Comparison with KD methods under the Pro", "Qwen setting"])
    assert t1_score.evaluate_pin(t11, k11, cap)["correct"]
    assert not t1_score.evaluate_pin(t11, k11, pin_struct("caption", fragments=["Pro-Qwen setting"]))["correct"]


def test_col_contains_count_and_row_contains():
    cells = [C(0, 0, "Student", col_h=True), C(0, 1, "Teacher", col_h=True), C(0, 2, "AUC", col_h=True),
             C(1, 0, "Qwen3-1.7B"), C(1, 1, "T1"), C(1, 2, "1.0"),
             C(2, 0, "Qwen3-1.7B (SFT)"), C(2, 1, "T1"), C(2, 2, "2.0"),
             C(3, 0, "Qwen3-4B (SFT)"), C(3, 1, "T2"), C(3, 2, "3.0")]
    t = T(cells, 4, 3, "Table 3 | pairs")
    k = tk.derive_keys(t)
    sft = pin_struct("col_contains_count", column="Student", contains="(SFT)", count=2)
    assert t1_score.evaluate_pin(t, k, sft)["correct"]
    assert not t1_score.evaluate_pin(t, k, dict(sft, count=3))["correct"]
    pair = pin_struct("row_exists", match={"Student": "Qwen3-1.7B (SFT)", "Teacher": "T1"})
    assert t1_score.evaluate_pin(t, k, pair)["correct"]
    cells2 = [C(0, 0, "Row", col_h=True), C(0, 1, "a", col_h=True), C(0, 2, "b", col_h=True),
              C(1, 0, "M +"), C(1, 1, "119"), C(1, 2, "17.22")]
    t2 = T(cells2, 2, 3, "Table 8: x")
    k2 = tk.derive_keys(t2)
    rc = pin_struct("row_contains", row_key_path=["M +"], values=["119", "17.22"])
    assert t1_score.evaluate_pin(t2, k2, rc)["correct"]
    assert not t1_score.evaluate_pin(t2, k2, dict(rc, values=["119", "18"]))["correct"]


# ----------------------------------------------------------- table scoring

def tinfo(number=4, role="gate"):
    return {"table_id": "PX-T4", "caption_number": number, "role": role}


def cell_pin(pid, row, col, value, breaking=False, uncertain=False):
    return {"id": pid, "kind": "cell", "row_key_path": [row], "column_key_path": [col], "value": value,
            "breaking": breaking, "key_uncertain": uncertain}


def small_table(vals, caption="Table 4: x"):
    rows = [["Metric", "a", "b"], ["r1", vals[0], vals[1]], ["r2", vals[2], vals[3]]]
    return grid(rows, caption=caption)


def test_split_table_fails_detection():
    pins = [cell_pin("P1", "r1", "a", "1", breaking=True)]
    t1, t2 = small_table(["1", "2", "3", "4"]), small_table(["1", "2", "3", "4"])
    r = t1_score.score_table([t1, t2], tinfo(), pins)
    assert not r["detected_unique"] and not r["usable"] and r["n_candidates"] == 2


def test_missing_table_not_usable():
    r = t1_score.score_table([small_table(["1", "2", "3", "4"], caption="Table 5: x")], tinfo(), [cell_pin("P1", "r1", "a", "1")])
    assert not r["detected_unique"] and not r["usable"]
    r = t1_score.score_table(None, tinfo(), [cell_pin("P1", "r1", "a", "1")])
    assert not r["usable"]


def test_usable_requires_every_breaking_cell():
    pins = [cell_pin("B", "r1", "a", "1", breaking=True), cell_pin("O", "r2", "b", "4")]
    assert t1_score.score_table([small_table(["1", "2", "3", "4"])], tinfo(), pins)["usable"]
    assert not t1_score.score_table([small_table(["9", "2", "3", "4"])], tinfo(), pins)["usable"]


def test_other_gated_threshold_and_vacuous_clause():
    # 10 other gated cells -> 9 of 10 passes, 8 of 10 fails
    n = 10
    rows = [["Metric", "a"]] + [[f"r{i}", str(i)] for i in range(n)]
    pins = [cell_pin(f"O{i}", f"r{i}", "a", str(i)) for i in range(n)]
    t = grid(rows, caption="Table 4: x")
    assert t1_score.score_table([t], tinfo(), pins)["usable"]
    bad9 = [dict(p) for p in pins]
    bad9[0]["value"] = "99"
    assert t1_score.score_table([t], tinfo(), bad9)["usable"]
    bad8 = [dict(p) for p in pins]
    bad8[0]["value"] = "99"
    bad8[1]["value"] = "99"
    r = t1_score.score_table([t], tinfo(), bad8)
    assert not r["usable"] and r["other_gated"] == [8, 10]
    # zero other gated cells: vacuous, reported 0/0
    only_breaking = [cell_pin("B", "r1", "a", "1", breaking=True)]
    r = t1_score.score_table([grid([["Metric", "a"], ["r1", "1"]], caption="Table 4: x")], tinfo(), only_breaking)
    assert r["usable"] and r["other_gated"] == [0, 0]


def test_uncertain_pins_are_reported_not_gated():
    pins = [cell_pin("B", "r1", "a", "1", breaking=True), cell_pin("U", "r2", "b", "999", uncertain=True)]
    r = t1_score.score_table([small_table(["1", "2", "3", "4"])], tinfo(), pins)
    assert r["usable"] and r["uncertain"] == [0, 1]


# ----------------------------------------------------------- run-level logic

def write_norm(root, extractor, run, paper, tables):
    d = root / extractor / run / "normalised"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{paper}.json").write_text(json.dumps({"tables": tables}, sort_keys=True, indent=2), encoding="utf-8")


def pins_doc(n_tables):
    tables, pins = [], []
    for i in range(n_tables):
        tid = f"P1-T{i + 1}"
        tables.append({"table_id": tid, "paper": "P1", "paper_id": "paper1", "caption_number": i + 1, "role": "gate"})
        pins.append(dict(cell_pin(f"{tid}-01", "r1", "a", "1", breaking=True), table_id=tid))
    return {"papers": {"P1": "paper1"}, "tables": tables, "pins": pins}


def test_stability_pass_fail_and_first_differences(tmp_path):
    t = small_table(["1", "2", "3", "4"])
    for run in ("run_a", "run_b"):
        write_norm(tmp_path, "docling", run, "paper1", [t])
    assert t1_score.stability(tmp_path, "docling", ["run_a", "run_b"], ["paper1"])["stable"]
    t_b = small_table(["1", "2", "3", "5"])
    write_norm(tmp_path, "docling", "run_b", "paper1", [t_b])
    st = t1_score.stability(tmp_path, "docling", ["run_a", "run_b"], ["paper1"])
    assert not st["stable"] and "paper1" in st["first_differences"][0] and "'4' vs '5'" in st["first_differences"][0]
    assert not t1_score.stability(tmp_path, "docling", ["run_a", "run_b"], ["missing"])["stable"]


def test_pass_needs_stable_and_seven_of_eight_and_winner_rules(tmp_path):
    doc = pins_doc(8)
    good = [dict(small_table(["1", "2", "3", "4"], caption=f"Table {i + 1}: x")) for i in range(8)]
    bad = [dict(small_table(["9", "2", "3", "4"], caption=f"Table {i + 1}: x")) for i in range(8)]
    # pymupdf4llm: 7/8 usable, stable. docling: 8/8 usable but unstable.
    p_tables = good[:7] + bad[7:]
    for run in ("run_a", "run_b"):
        write_norm(tmp_path, "pymupdf4llm", run, "paper1", p_tables)
    write_norm(tmp_path, "docling", "run_a", "paper1", good)
    write_norm(tmp_path, "docling", "run_b", "paper1", good[:7] + [small_table(["1", "2", "3", "5"], caption="Table 8: x")])
    res = t1_score.score_all(doc, tmp_path, ["pymupdf4llm", "docling"], ["run_a", "run_b"])
    assert res["extractors"]["pymupdf4llm"]["passes"] and res["extractors"]["pymupdf4llm"]["gate_usable"] == 7
    assert not res["extractors"]["docling"]["passes"]  # unstable although 8/8
    assert res["overall_pass"] and res["winner"] == "pymupdf4llm"  # winner only among PASSing extractors


def test_fail_when_six_of_eight_and_no_winner(tmp_path):
    doc = pins_doc(8)
    good = [small_table(["1", "2", "3", "4"], caption=f"Table {i + 1}: x") for i in range(8)]
    bad = [small_table(["9", "2", "3", "4"], caption=f"Table {i + 1}: x") for i in range(8)]
    for e in ("pymupdf4llm", "docling"):
        for run in ("run_a", "run_b"):
            write_norm(tmp_path, e, run, "paper1", good[:6] + bad[6:])
    res = t1_score.score_all(doc, tmp_path, ["pymupdf4llm", "docling"], ["run_a", "run_b"])
    assert not res["overall_pass"] and res["winner"] is None


def test_winner_tie_goes_to_pymupdf4llm_then_pin_suspect(tmp_path):
    doc = pins_doc(8)
    good = [small_table(["1", "2", "3", "4"], caption=f"Table {i + 1}: x") for i in range(8)]
    for e in ("docling", "pymupdf4llm"):
        for run in ("run_a", "run_b"):
            write_norm(tmp_path, e, run, "paper1", good)
    res = t1_score.score_all(doc, tmp_path, ["pymupdf4llm", "docling"], ["run_a", "run_b"])
    assert res["winner"] == "pymupdf4llm" and res["pin_suspects"] == []
    # both extractors agree with each other and disagree with the pin -> suspect, listed only
    both = [small_table(["7", "2", "3", "4"], caption=f"Table {i + 1}: x") if i == 0 else good[i] for i in range(8)]
    for e in ("docling", "pymupdf4llm"):
        for run in ("run_a", "run_b"):
            write_norm(tmp_path, e, run, "paper1", both)
    res = t1_score.score_all(doc, tmp_path, ["pymupdf4llm", "docling"], ["run_a", "run_b"])
    assert [s["pin"] for s in res["pin_suspects"]] == ["P1-T1-01"]
    md = t1_score.render_markdown(doc, res, ["pymupdf4llm", "docling"])
    assert "Pin suspects" in md and "P1-T1-01" in md


def test_first_diffs_reports_path():
    d = t1_score.first_diffs({"a": [1, {"b": "x"}]}, {"a": [1, {"b": "y"}]})
    assert d == ["$.a[1].b: 'x' vs 'y'"]
