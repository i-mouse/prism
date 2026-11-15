"""Unit tests for eval/step4/tablefind.py (table-finding check before step 4) on made-up strings only. No PDF, no
paper, no real reference table, no real pin."""
import copy
import json
from decimal import Decimal

import pytest

from eval.step4 import tablefind as tf


def D(text: str) -> Decimal:
    return Decimal(text)


# --- caption lines --------------------------------------------------------------------------------------------

def test_unique_caption_is_found_once_at_its_line_start():
    text = "Intro line\nTable 4: Results on X.\n1.0 2.0\n"
    assert tf.find_caption_lines(text, 4) == [text.index("Table 4")]


def test_pipe_delimiter_is_a_caption():
    text = "x\nTable 3 | All 17 pairs\n1.0\n"
    assert tf.find_caption_lines(text, 3) == [text.index("Table 3")]


def test_prose_mentions_are_not_captions():
    text = "as shown in Table 4, the model\nsee Table 4. It works\nTable 4 shows the gain\n"
    assert tf.find_caption_lines(text, 4) == []


def test_leading_spaces_tabs_and_space_before_delimiter_are_allowed():
    text = "  \tTable 2 : x\n"
    assert tf.find_caption_lines(text, 2) == [0]


def test_caption_is_case_sensitive():
    assert tf.find_caption_lines("TABLE 2: x\ntable 2: y\n", 2) == []


def test_two_caption_lines_are_two_offsets_and_the_table_is_not_found():
    text = "Table 5: first\nbody\nTable 5. second\nbody\n"
    assert tf.find_caption_lines(text, 5) == [0, text.index("Table 5.")]
    scored = tf.score_table(text=text, n=5, ref={"cells": [{"text": "1.5"}]}, pins=[])
    assert scored["caption_lines"] == 2 and scored["found"] is False and scored["usable"] is False
    assert scored["block_chars"] == 0 and scored["cap_hit"] is False


def test_zero_caption_lines_is_not_found():
    scored = tf.score_table(text="nothing here\n", n=1, ref={"cells": [{"text": "1.5"}]}, pins=[])
    assert scored["caption_lines"] == 0 and scored["found"] is False and scored["usable"] is False


def test_table_1_never_matches_table_10_and_vice_versa():
    text = "Table 10: big\nTable 1: small\n"
    assert tf.find_caption_lines(text, 1) == [text.index("Table 1:")]
    assert tf.find_caption_lines(text, 10) == [0]


# --- blocks ---------------------------------------------------------------------------------------------------

def test_block_stops_before_the_next_table_caption():
    text = "Table 1: cap\n1.0 2.0\nTable 2: next\n3.0\n"
    block, cap_hit = tf.cut_block(text, 0)
    assert block == text[: text.index("Table 2")] and cap_hit is False


def test_block_stops_before_figure_and_fig_captions_with_any_delimiter():
    for end_line in ("Figure 11 | Transfer", "Figure 3: x", "Fig. 3: x", "Fig. 3. x", "  Table 12. x"):
        text = f"Table 1: cap\n1.0\n{end_line}\n2.0\n"
        block, cap_hit = tf.cut_block(text, 0)
        assert block == "Table 1: cap\n1.0\n" and cap_hit is False, end_line


def test_prose_figure_lines_do_not_end_a_block():
    text = "Table 1: cap\nsee Figure 3 for more\nFigure 3 shows it\n2.0\n"
    block, cap_hit = tf.cut_block(text, 0)
    assert block == text and cap_hit is False


def test_block_stops_before_a_references_line_any_case():
    for line in ("References", "  REFERENCES  ", "references"):
        text = f"Table 1: cap\n1.0\n{line}\n[1] A. Author\n"
        block, cap_hit = tf.cut_block(text, 0)
        assert block == "Table 1: cap\n1.0\n" and cap_hit is False, line


def test_a_numbered_references_line_does_not_end_a_block():
    text = "Table 1: cap\n1.0\n7 References\n2.0\n"
    block, cap_hit = tf.cut_block(text, 0)
    assert block == text and cap_hit is False


def test_block_is_cut_at_12000_chars_and_reports_the_cap_hit():
    text = "Table 1: cap\n" + "1.0 " * 5000
    block, cap_hit = tf.cut_block(text, 0)
    assert len(block) == 12000 and block == text[:12000] and cap_hit is True


def test_cap_counts_from_the_caption_start_not_the_text_start():
    text = "head\n" + "Table 1: cap\n" + "z" * 13000
    block, cap_hit = tf.cut_block(text, text.index("Table 1"))
    assert len(block) == 12000 and block.startswith("Table 1") and cap_hit is True


def test_no_cap_hit_when_another_end_comes_first():
    text = "Table 1: cap\n" + "x " * 100 + "\nTable 2: n\n" + "y " * 10000
    block, cap_hit = tf.cut_block(text, 0)
    assert block == text[: text.index("Table 2")] and cap_hit is False


def test_cap_hit_when_the_natural_end_lies_beyond_the_cap():
    text = "Table 1: cap\n" + "a " * 8000 + "\nTable 2: n\nz"
    block, cap_hit = tf.cut_block(text, 0)
    assert len(block) == 12000 and cap_hit is True


def test_cap_boundary_exactly_12000_is_not_a_cap_hit_and_12001_is():
    exact = "Table 1: cap\n" + "a" * (12000 - 13)
    assert tf.cut_block(exact, 0) == (exact, False)
    over = "Table 1: cap\n" + "a" * (12001 - 13)
    block, cap_hit = tf.cut_block(over, 0)
    assert block == over[:12000] and cap_hit is True


# --- values ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "token,expected",
    [
        (".709", {D("0.709")}),
        ("0.709", {D("0.709")}),
        ("+0.30", {D("0.3")}),
        ("-0.38", {D("-0.38")}),
        ("−0.38", {D("-0.38")}),                 # unicode minus
        (".709+-.059", {D("0.709")}),                  # glued SD: the value only
        ("95.8%", {D("95.8")}),
        ("87.27*", {D("87.27")}),
        ("44.5/53.3", {D("44.5"), D("53.3")}),         # a pair gives both members
        ("-", set()),
        ("n/a", set()),
        ("(87.1)", set()),                             # brackets are not stripped: the token is text
        ("87.1,", set()),
        ("Model", set()),
    ],
)
def test_values_in_block_per_token(token, expected):
    assert tf.values_in_block(token) == expected


def test_spaced_sd_gives_the_left_value_and_the_sign_is_its_own_text_token():
    values = tf.values_in_block("0.709 ± 0.059")
    assert D("0.709") in values


def test_equal_means_numerically_equal():
    assert D("50") in tf.values_in_block("50.0")
    assert tf.values_in_block("1,234") == {D("1234")}


def test_ref_values_read_the_whole_cell_with_sd_ignored_and_pairs_split():
    ref = {"cells": [
        {"text": "0.709"}, {"text": ".709+-.059"}, {"text": "44.5 / 53.3"}, {"text": "Model"}, {"text": "-"},
        {"text": None},
    ]}
    assert tf.ref_values(ref) == {D("0.709"), D("44.5"), D("53.3")}


# --- value test, pins, labels ---------------------------------------------------------------------------------

def _ref_ten() -> dict:
    return {"cells": [{"text": f"{i}.5"} for i in range(1, 11)]}


def _text_with(count: int, extra: str = "") -> str:
    return "Table 1: cap\n" + " ".join(f"{i}.5" for i in range(1, count + 1)) + extra + "\n"


def test_value_test_boundary_9_of_10_passes_and_8_of_10_fails():
    nine = tf.score_table(text=_text_with(9), n=1, ref=_ref_ten(), pins=[])
    assert (nine["ref_matched"], nine["ref_distinct_total"], nine["ref_pct"]) == (9, 10, 90.0)
    assert nine["value_test"] is True and nine["usable"] is True
    eight = tf.score_table(text=_text_with(8), n=1, ref=_ref_ten(), pins=[])
    assert eight["ref_matched"] == 8 and eight["value_test"] is False and eight["usable"] is False


def test_an_empty_reference_never_passes_the_value_test():
    scored = tf.score_table(text="Table 1: cap\n1.5\n", n=1, ref={"cells": [{"text": "Model"}]}, pins=[])
    assert scored["ref_distinct_total"] == 0 and scored["value_test"] is False and scored["usable"] is False


def test_breaking_cell_pins_gate_and_other_pins_do_not():
    pins = [
        {"id": "P1-T4-01", "kind": "cell", "value": "0.709", "breaking": True},
        {"id": "P1-T4-02", "kind": "cell", "value": "9.99", "breaking": False},
    ]
    missing = tf.score_table(text=_text_with(10), n=1, ref=_ref_ten(), pins=pins)
    assert missing["breaking_cell_pins"] == {"P1-T4-01": False}
    assert missing["value_test"] is True and missing["usable"] is False
    present = tf.score_table(text=_text_with(10, extra=" .709"), n=1, ref=_ref_ten(), pins=pins)
    assert present["breaking_cell_pins"] == {"P1-T4-01": True} and present["usable"] is True


def test_a_breaking_cell_pin_with_a_non_numeric_value_is_not_present():
    pins = [{"id": "P1-T4-01", "kind": "cell", "value": "-", "breaking": True}]
    scored = tf.score_table(text=_text_with(10), n=1, ref=_ref_ten(), pins=pins)
    assert scored["breaking_cell_pins"] == {"P1-T4-01": False} and scored["usable"] is False


def test_structural_breaking_pins_are_reported_not_gated():
    pins = [
        {
            "id": "P11-T3-S1", "kind": "caption", "breaking": True,
            "fragments": ["Comparison with KD methods under the Pro", "Qwen setting"],
        },
        {"id": "P4-T9-S1", "kind": "row_absent", "breaking": True},
    ]
    text = "Table 3: Comparison with KD methods under the Pro→Qwen setting.\n1.5 2.5\n"
    ref = {"cells": [{"text": "1.5"}, {"text": "2.5"}]}
    scored = tf.score_table(text=text, n=3, ref=ref, pins=pins)
    assert scored["structural_breaking"] == {"P11-T3-S1": True, "P4-T9-S1": "not checkable"}
    assert scored["breaking_cell_pins"] == {} and scored["usable"] is True
    other = tf.score_table(text=text.replace("Qwen setting", "other"), n=3, ref=ref, pins=pins)
    assert other["structural_breaking"]["P11-T3-S1"] is False and other["usable"] is True


def test_normalize_text_is_nfkc_casefold_without_any_whitespace():
    assert tf.normalize_text("Ｍodel \tA") == "modela"


def test_label_coverage_uses_header_row_header_and_section_cells():
    ref = {"cells": [
        {"text": "Model", "is_column_header": True},
        {"text": "Method  A", "is_row_header": True},
        {"text": "Group", "is_section_row": True},
        {"text": "1.5"},
    ]}
    assert tf.ref_labels(ref) == {"model", "methoda", "group"}
    scored = tf.score_table(text="Table 1: c\nMODEL\nMethod\nA\n1.5\n", n=1, ref=ref, pins=[])
    assert (scored["label_matched"], scored["label_total"]) == (2, 3)


def test_est_tokens_is_chars_over_four():
    scored = tf.score_table(text="Table 1: cap\n1.5\n", n=1, ref={"cells": [{"text": "1.5"}]}, pins=[])
    assert scored["est_tokens"] == scored["block_chars"] // 4


# --- all-tables view ------------------------------------------------------------------------------------------

def test_all_tables_view_counts_mentions_and_checks_for_exactly_one_caption():
    text = (
        "Table 1: a\n"
        "see Table 2 and Table 2a and Table A1 and Table 10.\n"
        "Table 2: b\n"
        "Table 3: c\n"
        "Table 3: d\n"
    )
    assert tf.all_tables_view(text) == {1: True, 2: True, 3: False, 10: False}


def test_all_tables_view_of_text_without_tables_is_empty():
    assert tf.all_tables_view("nothing to see\n") == {}


# --- rows and verdict -----------------------------------------------------------------------------------------

def test_fixed_maps_agree_with_each_other():
    tables_in_rows = {t for tables in tf.ROW_TABLES.values() for t in tables}
    assert set(tf.TABLE_NUMBERS) == set(tf.EXPECTED_BREAKING) == tables_in_rows
    assert len(tf.ROW_TABLES) == 5 and len(tf.TABLE_NUMBERS) == 6


def test_a_row_is_ready_only_when_all_its_tables_are_usable():
    usable = {t: True for t in tf.TABLE_NUMBERS}
    usable["P4-T2"] = False
    assert tf.rows_ready(usable) == {
        "P1-R1": True, "P3-R2": True, "P4-R1": False, "P4-R2": True, "P11-R2": True,
    }


def test_verdict_4_of_5_passes_and_3_of_5_fails():
    four = {"a": True, "b": True, "c": True, "d": True, "e": False}
    three = {"a": True, "b": True, "c": True, "d": False, "e": False}
    assert tf.verdict(four) == "PASS"
    assert tf.verdict(three) == "FAIL"
    assert tf.verdict({k: True for k in "abcde"}) == "PASS"


# --- output holds ids, counts and bools only ------------------------------------------------------------------

TOY_TEXT = "Intro\nTable 1: SECRETWORD caption\nROWLABELX 7.7123 8.5\nFigure 2: end\nafter\n"
TOY_REF = {"cells": [{"text": "ROWLABELX", "is_row_header": True}, {"text": "7.7123"}, {"text": "8.5"}]}


def _toy_payload() -> dict:
    scored = {tid: tf.score_table(text=TOY_TEXT, n=1, ref=TOY_REF, pins=[]) for tid in tf.TABLE_NUMBERS}
    papers = {tid: "2610.11519v1" for tid in tf.TABLE_NUMBERS}
    return tf.build_payload(scored=scored, papers=papers, all_tables={"2610.10590v1": {1: True, 2: False}})


def test_payload_passes_the_free_text_check_and_is_json_serialisable():
    payload = _toy_payload()
    tf.check_payload(payload)
    assert payload["verdict"] == "PASS" and payload["rows_ready_count"] == 5 and payload["rows_total"] == 5
    assert payload["all_tables"] == {"2610.10590v1": {"1": True, "2": False}}
    assert payload["all_tables_counts"] == {"2610.10590v1": {"mentioned": 2, "captions_found_once": 1}}
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_payload_and_markdown_hold_no_paper_text_no_values_no_labels():
    payload = _toy_payload()
    rendered = json.dumps(payload, sort_keys=True) + tf.render_md(payload)
    for forbidden in ("SECRETWORD", "ROWLABELX", "7.7123", "Intro"):
        assert forbidden not in rendered
    assert "Verdict: **PASS**" in tf.render_md(payload)


def test_rendering_is_deterministic():
    assert tf.render_md(_toy_payload()) == tf.render_md(_toy_payload())


def test_check_payload_rejects_unknown_keys_free_text_and_odd_types():
    payload = _toy_payload()

    with_note = copy.deepcopy(payload)
    with_note["tables"]["P1-T4"]["note"] = "hello"
    with pytest.raises(ValueError):
        tf.check_payload(with_note)

    free_text = copy.deepcopy(payload)
    free_text["verdict"] = "the model said something"
    with pytest.raises(ValueError) as caught:
        tf.check_payload(free_text)
    assert "the model said something" not in str(caught.value)

    odd_type = copy.deepcopy(payload)
    odd_type["tables"]["P1-T4"]["ref_matched"] = D("1")
    with pytest.raises(ValueError):
        tf.check_payload(odd_type)

    odd_label = copy.deepcopy(payload)
    odd_label["tables"]["P1-T4"]["breaking_cell_pins"]["some label text"] = True
    with pytest.raises(ValueError):
        tf.check_payload(odd_label)
