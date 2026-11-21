"""Unit tests for eval/step4/table_check.py (step 4 table checker, pure logic) on made-up strings only. No paper,
no real table, no model call."""
import hashlib
import re

import pytest

from eval.step4 import table_check as tc
from eval.step4.table_check_schemas import PieceAnswer, TableCell

PAPER = (
    "Intro. See Table 1 and Table 2 for results.\n"
    "Table 1: Speed of gadgets\n"
    "Gadget Small Large\n"
    "Alpha sorter 41.5 38.2\n"
    "Bravo sorter 44.0 36.9\n"
    "Table 2: Cost of gadgets\n"
    "Gadget Cost\n"
    "Alpha sorter 10\n"
    "Figure 1: drawing\n"
    "Closing words about Table 7.\n"
)
NO_TABLE_PAPER = "Intro. We mention Table 3 in passing but print no caption line.\n"


def _blocks():
    return tc.build_table_blocks(PAPER)


def _cell(table=1, row="Bravo sorter", column="Small", value="44.0"):
    return TableCell(table=table, row_label=row, column_label=column, value=value)


def _answer(piece_id, answer, cells=()):
    return PieceAnswer(piece_id=piece_id, answer=answer, cells=list(cells))


# --- table blocks: join and cap -------------------------------------------------------------------------------

def test_found_tables_are_joined_in_number_order_with_headers():
    blocks = _blocks()
    assert list(blocks.included) == [1, 2] and blocks.dropped == () and blocks.block_cap_hits == ()
    assert blocks.included[1].startswith("Table 1: Speed of gadgets\n") and "Bravo sorter 44.0 36.9" in blocks.included[1]
    assert "Cost of gadgets" not in blocks.included[1] and "Figure 1" not in blocks.included[2]
    expected = "=== Table 1 ===\n" + blocks.included[1] + "\n\n" + "=== Table 2 ===\n" + blocks.included[2]
    assert blocks.text == expected
    assert blocks.found == (1, 2)   # the table mentioned in prose only is not a found table


def test_a_paper_with_no_caption_line_has_no_block():
    blocks = tc.build_table_blocks(NO_TABLE_PAPER)
    assert blocks.included == {} and blocks.text == "" and blocks.dropped == ()


def test_cap_drops_the_later_table_and_lists_it(monkeypatch):
    full = _blocks()
    first = len("=== Table 1 ===\n" + full.included[1])
    monkeypatch.setattr(tc, "JOIN_CAP_CHARS", first)          # the first table fits exactly
    blocks = tc.build_table_blocks(PAPER)
    assert list(blocks.included) == [1] and blocks.dropped == (2,)
    assert blocks.text == "=== Table 1 ===\n" + full.included[1]

    monkeypatch.setattr(tc, "JOIN_CAP_CHARS", len(full.text))  # both fit exactly, separators counted
    assert tc.build_table_blocks(PAPER).dropped == ()
    monkeypatch.setattr(tc, "JOIN_CAP_CHARS", len(full.text) - 1)
    assert tc.build_table_blocks(PAPER).dropped == (2,)

    monkeypatch.setattr(tc, "JOIN_CAP_CHARS", first - 1)       # not even the first table fits
    blocks = tc.build_table_blocks(PAPER)
    assert blocks.included == {} and blocks.dropped == (1, 2) and blocks.text == ""


def test_cap_keeps_a_prefix_and_never_skips_ahead_to_a_smaller_later_table(monkeypatch):
    big_rows = "".join(f"Row{i} sorter {i}.5\n" for i in range(60))
    paper = (
        "Table 1: Small one\nAlpha sorter 1.0\n"
        "Table 2: Big one\n" + big_rows +
        "Table 3: Tiny one\nBravo sorter 2.0\n"
    )
    full = tc.build_table_blocks(paper)
    assert list(full.included) == [1, 2, 3]
    one = len("=== Table 1 ===\n" + full.included[1])
    three = len("=== Table 3 ===\n" + full.included[3])
    monkeypatch.setattr(tc, "JOIN_CAP_CHARS", one + 2 + three)   # tables 1 and 3 would fit together; 2 does not
    blocks = tc.build_table_blocks(paper)
    assert list(blocks.included) == [1] and blocks.dropped == (2, 3)


def test_per_table_cap_hit_of_the_finder_is_reported(monkeypatch):
    monkeypatch.setattr(tc.tablefind, "BLOCK_CAP_CHARS", 30)
    blocks = tc.build_table_blocks("Table 1: A long made-up caption line\n" + "1.0 2.0 3.0\n" * 20)
    assert blocks.block_cap_hits == (1,) and len(blocks.included[1]) == 30


# --- routing --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("as Table 2 shows", (2,)),
    ("see Table  12 and Table\t3.", (3, 12)),
    ("(Table 5)", (5,)),
    ("Table 6, row two", (6,)),
    ("Table 2a is a sub-table", ()),
    ("Tables 1 and 2", ()),
    ("table 4 in lower case", ()),
    ("Table4 without a space", ()),
    ("Table\n9 across a line break", ()),
    ("no mention at all", ()),
])
def test_cited_table_numbers_follow_the_finder_pattern(text, expected):
    assert tc.cited_table_numbers([text]) == expected


def test_cited_numbers_are_collected_over_all_texts_and_non_strings_are_ignored():
    assert tc.cited_table_numbers(["Table 2", None, "Table 1 and Table 2", 7]) == (1, 2)


def test_route_on_claim_text_span_section_and_span_text():
    blocks = _blocks()
    assert tc.route("Table 1 shows the gain.", (), blocks) == tc.RouteDecision(True, tc.ROUTED, (1,))
    by_section = tc.route("The gain is large.", [{"source_section": "Table 2", "source_text": "x"}], blocks)
    assert by_section.routed and by_section.cited == (2,)
    by_text = tc.route("The gain is large.", [{"source_section": "Results", "source_text": "see Table 1"}], blocks)
    assert by_text.routed and by_text.cited == (1,)


def test_route_refusals():
    blocks = _blocks()
    plain = tc.route("The gain is large.", [{"source_section": "Results", "source_text": "it is large"}], blocks)
    assert (plain.routed, plain.reason) == (False, tc.NO_TABLE_MENTION)
    none_found = tc.route("Table 3 shows it.", (), tc.build_table_blocks(NO_TABLE_PAPER))
    assert (none_found.routed, none_found.reason, none_found.cited) == (False, tc.NO_FOUND_TABLE, (3,))


def test_a_claim_citing_a_dropped_table_is_not_routed(monkeypatch):
    full = _blocks()
    monkeypatch.setattr(tc, "JOIN_CAP_CHARS", len("=== Table 1 ===\n" + full.included[1]))
    blocks = tc.build_table_blocks(PAPER)
    dropped = tc.route("Table 2 shows the cost.", (), blocks)
    assert (dropped.routed, dropped.reason) == (False, tc.CITES_DROPPED_TABLE)
    both = tc.route("Table 1 and Table 2 agree.", (), blocks)
    assert (both.routed, both.reason) == (False, tc.CITES_DROPPED_TABLE)
    assert tc.route("Table 1 shows the speed.", (), blocks).routed


def test_a_cited_table_that_was_not_found_does_not_block_routing():
    decision = tc.route("Table 7 shows it.", (), _blocks())
    assert decision.routed and decision.cited == (7,)


# --- checker input --------------------------------------------------------------------------------------------

def test_checker_user_text_holds_the_claim_the_numbered_pieces_and_the_blocks():
    pieces = [tc.Piece(1, "Bravo is fastest on small loads", "pair"), tc.Piece(2, "all gadgets", "quantifier")]
    text = tc.build_checker_user_text("A made-up claim.", pieces, "=== Table 1 ===\nrows")
    assert text == (
        "CLAIM:\nA made-up claim.\n\nPIECES:\n1. [pair] Bravo is fastest on small loads\n2. [quantifier] all gadgets\n\n"
        "TABLES:\n=== Table 1 ===\nrows\n"
    )


def test_invalid_answer_ids():
    assert tc.invalid_answer_ids(2, [_answer(1, "no_row"), _answer(2, "no_row")]) is None
    assert tc.invalid_answer_ids(2, [_answer(1, "no_row")]) is None            # a missing piece is not invalid
    assert "not one of" in tc.invalid_answer_ids(2, [_answer(3, "no_row")])
    assert "not one of" in tc.invalid_answer_ids(2, [_answer(0, "no_row")])
    assert "more than once" in tc.invalid_answer_ids(2, [_answer(1, "no_row"), _answer(1, "backed")])


# --- code guard -----------------------------------------------------------------------------------------------

PIECE_TEXT = "the Bravo sorter is the fastest gadget on small loads"


def test_guard_passes_on_a_true_quote_with_loose_label_spelling_and_number_format():
    blocks = _blocks()
    assert tc.guard_piece(PIECE_TEXT, [_cell()], blocks) == []
    assert tc.guard_piece(PIECE_TEXT, [_cell(row="bravo  SORTER", value="44")], blocks) == []
    assert tc.guard_piece(PIECE_TEXT, [_cell(), _cell(row="Alpha sorter", value="41.5")], blocks) == []


def test_guard_fails_when_the_value_is_not_in_that_tables_block():
    blocks = _blocks()
    assert tc.guard_piece(PIECE_TEXT, [_cell(value="99.9")], blocks) == [tc.GUARD_VALUE_MISSING]
    assert tc.guard_piece(PIECE_TEXT, [_cell(value="")], blocks) == [tc.GUARD_VALUE_MISSING]
    # 10 is printed in the other table only
    assert tc.guard_piece(PIECE_TEXT, [_cell(row="Alpha sorter", value="10")], blocks) == [tc.GUARD_VALUE_MISSING]
    # every token of a multi-token value must be found
    assert tc.guard_piece(PIECE_TEXT, [_cell(value="44.0 99.9")], blocks) == [tc.GUARD_VALUE_MISSING]


def test_guard_fails_when_the_row_label_is_not_in_that_tables_block():
    assert tc.guard_piece(PIECE_TEXT, [_cell(row="Delta sorter")], _blocks()) == [tc.GUARD_ROW_LABEL_MISSING]
    assert tc.guard_piece(PIECE_TEXT, [_cell(row="  ")], _blocks()) == [tc.GUARD_ROW_LABEL_MISSING]


def test_guard_name_check_needs_a_label_word_of_three_letters_in_the_piece():
    blocks = _blocks()
    assert tc.guard_piece("the quickest one wins", [_cell()], blocks) == [tc.GUARD_NAME_CHECK]
    # the column label alone can satisfy it
    assert tc.guard_piece("results on small loads", [_cell()], blocks) == []
    # a word must match whole: "sort" is not "sorter", and two-letter words never count
    assert tc.guard_piece("we sort it on an XL load", [_cell(column="XL")], blocks) == [tc.GUARD_NAME_CHECK]


def test_guard_fails_on_no_cells_and_on_a_table_that_was_not_sent():
    blocks = _blocks()
    assert tc.guard_piece(PIECE_TEXT, [], blocks) == [tc.GUARD_NO_CELLS]
    reasons = tc.guard_piece(PIECE_TEXT, [_cell(table=9)], blocks)
    assert tc.GUARD_TABLE_NOT_INCLUDED in reasons


# --- pieces ---------------------------------------------------------------------------------------------------

def _pieces(n):
    return [tc.Piece(i, PIECE_TEXT, "pair") for i in range(1, n + 1)]


def test_piece_outcomes_for_every_answer_kind():
    outcomes = tc.piece_outcomes(_pieces(6), [
        _answer(1, "backed", [_cell()]),
        _answer(2, "not_backed", [_cell()]),
        _answer(3, "no_row"),
        _answer(4, "not_a_table_piece"),
        _answer(5, "backed", [_cell(value="99.9")]),
    ], _blocks())
    assert [(o.state, o.reason) for o in outcomes] == [
        (tc.PASSED, None),
        (tc.FAILED, None),
        (tc.FAILED, None),                                  # no_row counts as failed (ruling 5)
        (tc.COULD_NOT_CHECK, tc.CNC_NOT_A_TABLE_PIECE),
        (tc.COULD_NOT_CHECK, tc.CNC_GUARD_FAILED),
        (tc.COULD_NOT_CHECK, tc.CNC_MISSING_ANSWER),
    ]
    assert outcomes[4].guard_reasons == [tc.GUARD_VALUE_MISSING] and outcomes[4].answer == "backed"
    assert outcomes[0].cells == [{"table": 1, "row_label": "Bravo sorter", "column_label": "Small", "value": "44.0"}]


def test_a_not_backed_answer_that_fails_the_guard_never_counts_as_failed():
    [outcome] = tc.piece_outcomes(_pieces(1), [_answer(1, "not_backed", [_cell(row="Delta sorter")])], _blocks())
    assert outcome.state == tc.COULD_NOT_CHECK and outcome.guard_reasons == [tc.GUARD_ROW_LABEL_MISSING]


def test_a_failed_checker_call_makes_every_piece_could_not_check():
    outcomes = tc.piece_outcomes(_pieces(2), None, _blocks())
    assert [(o.state, o.reason, o.answer) for o in outcomes] == [(tc.COULD_NOT_CHECK, tc.CNC_CHECKER_FAILED, None)] * 2


# --- claim result ---------------------------------------------------------------------------------------------

def _outcomes(*states):
    return [tc.PieceOutcome(i, "t", "pair", None, state) for i, state in enumerate(states, start=1)]


@pytest.mark.parametrize("states, label, fallback", [
    ((tc.FAILED,), tc.LABEL_NOT_SUPPORTED, False),
    ((tc.FAILED, tc.FAILED), tc.LABEL_NOT_SUPPORTED, False),             # all checked and all failed
    ((tc.FAILED, tc.PASSED), tc.LABEL_PARTIAL, False),                   # mixed
    ((tc.FAILED, tc.COULD_NOT_CHECK), tc.LABEL_PARTIAL, False),          # >= 1 failed, not all checked
    ((tc.FAILED, tc.FAILED, tc.COULD_NOT_CHECK), tc.LABEL_PARTIAL, False),
    ((tc.PASSED,), tc.LABEL_SUPPORTED, False),
    ((tc.PASSED, tc.PASSED), tc.LABEL_SUPPORTED, False),                 # 0 failed and all checked
    ((tc.PASSED, tc.COULD_NOT_CHECK), None, True),                       # 0 failed + could-not-check -> auditor
    ((tc.COULD_NOT_CHECK,), None, True),
    ((), None, True),                                                    # no piece at all -> auditor
])
def test_claim_result_branches(states, label, fallback):
    result = tc.claim_result(_outcomes(*states))
    assert (result.label, result.use_fallback) == (label, fallback)
    assert result.n_pieces == len(states)
    assert result.n_failed == states.count(tc.FAILED)
    assert result.n_could_not_check == states.count(tc.COULD_NOT_CHECK)


def test_could_not_check_never_lowers_a_label_on_its_own():
    for n in (1, 2, 5):
        assert tc.claim_result(_outcomes(*([tc.COULD_NOT_CHECK] * n))).label is None


# --- trace, counters, hashes ----------------------------------------------------------------------------------

def test_stats_count_routed_unrouted_answers_guards_and_fallbacks():
    stats = tc.TableCheckStats()
    stats.record_unrouted(tc.NO_TABLE_MENTION)
    outcomes = tc.piece_outcomes(_pieces(3), [
        _answer(1, "not_backed", [_cell()]), _answer(2, "backed", [_cell(value="99.9")]), _answer(3, "no_row"),
    ], _blocks())
    result = tc.claim_result(outcomes)
    stats.record_routed(tc.ClaimTrace(pieces=outcomes, label=result.label, n_failed=result.n_failed))
    stats.record_routed(tc.ClaimTrace(lister_failed=True, use_fallback=True, fallback_reason=tc.FALLBACK_LISTER_FAILED))
    assert (stats.claims, stats.routed_claims, stats.unrouted) == (3, 2, {tc.NO_TABLE_MENTION: 1})
    assert (stats.pieces, stats.failed_pieces, stats.guard_failures) == (3, 2, 1)
    assert stats.answers == {"not_backed": 1, "backed": 1, "no_row": 1}
    assert stats.guard_reasons == {tc.GUARD_VALUE_MISSING: 1}
    assert stats.checker_labels == {tc.LABEL_PARTIAL: 1}
    assert (stats.lister_failures, stats.fallback_claims) == (1, 1)
    assert stats.fallback_reasons == {tc.FALLBACK_LISTER_FAILED: 1}


def test_trace_fields_name_the_source():
    checker = tc.ClaimTrace(cited=[1], label=tc.LABEL_SUPPORTED).to_fields()
    assert (checker["routed"], checker["source"], checker["checker_label"]) == (True, "checker", tc.LABEL_SUPPORTED)
    fallback = tc.ClaimTrace(use_fallback=True, fallback_reason=tc.FALLBACK_ZERO_PIECES).to_fields()
    assert (fallback["source"], fallback["fallback_reason"]) == ("fallback_audit", tc.FALLBACK_ZERO_PIECES)
    unrouted = tc.unrouted_fields(tc.RouteDecision(False, tc.NO_TABLE_MENTION, ()))
    assert unrouted == {"routed": False, "source": "audit", "reason": tc.NO_TABLE_MENTION, "cited": []}


def test_hashes_are_twelve_hex_chars_of_the_named_files():
    expected_checker = hashlib.sha256(
        tc.CHECKER_PROMPT_PATH.read_bytes() + tc.CHECKER_SCHEMA_PATH.read_bytes()).hexdigest()[:12]
    expected_lister = hashlib.sha256(
        tc.LISTER_PROMPT_PATH.read_bytes() + tc.LISTER_SCHEMA_PATH.read_bytes()).hexdigest()[:12]
    assert tc.checker_hash() == expected_checker and tc.lister_hash() == expected_lister
    assert re.fullmatch(r"[0-9a-f]{12}", tc.checker_hash()) and tc.checker_hash() != tc.lister_hash()
    assert tc.LISTER_PROMPT_PATH.name == "scope_list_system.md" and tc.LISTER_SCHEMA_PATH.name == "scope_schemas.py"


def test_no_checker_code_or_prompt_names_an_eval_row_a_paper_or_a_table_number():
    step4 = tc.CHECKER_PROMPT_PATH.parent
    for name in ("table_check.py", "table_check_calls.py", "table_check_schemas.py", "table_check_system.md"):
        text = (step4 / name).read_text(encoding="utf-8")
        assert not re.search(r"\bP\d+-[RST]\d+", text), name          # eval row / table ids
        assert not re.search(r"\b\d{4}\.\d{4,5}(v\d+)?\b", text), name   # paper ids
        assert not re.search(r"\bTable[ \t]+\d", text), name          # a concrete table number
