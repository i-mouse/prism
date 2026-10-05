"""Unit tests for extraction.grounding.normalize_for_match and the Stage-1
RapidFuzz score it feeds. Pure functions - no LLM, no DB."""
from pathlib import Path

import pytest
from rapidfuzz import fuzz

from extraction import grounding
from extraction.grounding import (
    RAPIDFUZZ_THRESHOLD,
    _audit_context,
    _extract_span_context,
    _normalized_alignment,
    _stage1_score,
    normalize_for_match,
    normalize_with_map,
)


def _passes(quote: str, paper: str) -> bool:
    return _stage1_score(quote, paper, normalize=True) >= RAPIDFUZZ_THRESHOLD


# --- individual rules -------------------------------------------------------

def test_nfkc_expands_ligature():
    assert normalize_for_match("\ufb01rst") == "first"
    assert normalize_for_match("e\ufb00ect") == "effect"


def test_removes_soft_hyphen():
    assert normalize_for_match("reason\u00ading") == "reasoning"


def test_joins_word_broken_across_lines_when_next_char_lowercase():
    assert normalize_for_match("exam-\nple") == "example"
    assert normalize_for_match("exam- \n  ple") == "example"


def test_keeps_hyphen_across_line_when_next_char_not_lowercase():
    assert normalize_for_match("GPT-\n4") == "GPT- 4"
    assert normalize_for_match("Chain-\nOf") == "Chain- Of"


def test_curly_quotes_become_straight():
    assert normalize_for_match("\u201cthink\u201d and \u2018act\u2019") == "\"think\" and 'act'"


def test_en_and_em_dash_become_hyphen():
    assert normalize_for_match("10\u201320 \u2014 roughly") == "10-20 - roughly"


def test_collapses_all_whitespace():
    assert normalize_for_match("  a\t\tb\n\nc\r\n d  ") == "a b c d"


# --- content must survive ---------------------------------------------------

def test_decimal_kept():
    assert normalize_for_match("accuracy of 91.5%") == "accuracy of 91.5%"


def test_inline_hyphenated_compound_kept():
    assert normalize_for_match("a state-of-the-art result") == "a state-of-the-art result"


def test_pipe_kept():
    assert normalize_for_match("| 52% | 60% |") == "| 52% | 60% |"


def test_digit_only_line_kept():
    # No page-number stripping: an integer table cell on its own line stays.
    assert normalize_for_match("ReAct\n71\nAct\n53") == "ReAct 71 Act 53"


# --- Stage-1 match behaviour ------------------------------------------------

def test_ligature_quote_matches_plain_paper_text():
    paper = "We \ufb01rst show that chain-of-thought prompting improves reasoning."
    assert _passes("We first show that chain-of-thought prompting improves reasoning.", paper)


def test_table_cells_split_by_newlines_match_space_separated_quote():
    paper = "Table 1: HotpotQA (EM)\nCoT\n25.7\n58.9\nReAct\n27.4\n60.9\n"
    assert _passes("25.7 58.9", paper)


def test_integer_table_cell_on_own_line_still_matches():
    paper = "Table 3\nReAct\n71\nReAct-IM\n53\n"
    assert _passes("ReAct 71 ReAct-IM 53", paper)


def test_swapped_digits_still_fail():
    paper = "Accuracy rises to 73% on GSM8K with chain-of-thought prompting."
    assert normalize_for_match("37%") != normalize_for_match("73%")
    assert not _passes("37%", paper)


def test_quote_with_added_pipes_still_fails():
    paper = "Table 3\nCoT\n52%\nBaseline\n60%\nReflexion\n68%\n"
    assert not _passes("| CoT | 52% | Baseline | 60% | Reflexion | 68% |", paper)


@pytest.mark.parametrize("text", [
    "We \ufb01rst ex-\nplain the \u201cReAct\u201d results\u2014see Table 1.",
    "25.7\n58.9\n\n91.5",
    "reason\u00ading about GPT-\n4 and state-of-the-art | 52% |",
    "a-\nb-\nc",
])
def test_idempotent(text):
    once = normalize_for_match(text)
    assert normalize_for_match(once) == once


# --- env flag ---------------------------------------------------------------

def test_flag_controls_stage1(monkeypatch):
    paper = "e\ufb00ective \ufb01ne-tuning of \ufb01ve \ufb02ows"
    quote = "effective fine-tuning of five flows"
    monkeypatch.setattr(grounding.settings, "grounding_normalize", False)
    assert not grounding._passes_rapidfuzz(quote, paper)
    monkeypatch.setattr(grounding.settings, "grounding_normalize", True)
    assert grounding._passes_rapidfuzz(quote, paper)


# --- normalize_with_map and audit-context alignment -------------------------

_FILLER = "Unrelated filler sentence about something else entirely. " * 30

_MAP_SAMPLES = [
    "We \ufb01rst ex-\nplain the \u201cReAct\u201d results\u2014see Table 1.",
    "Table 1\nAct\n25.7\n58.9\nReAct\n27.4\n60.9\n",
    "  leading and trailing  \r\n",
    "reason\u00ading about GPT-\n4 and state-of-the-art | 52% |",
    "caf\u00e9 vs cafe\u0301 vs \u00bd and non\u00a0breaking",
    "a-\nb-\nc",
    "",
]


@pytest.mark.parametrize("text", _MAP_SAMPLES)
def test_normalize_with_map_text_equals_normalize_for_match(text):
    assert normalize_with_map(text)[0] == normalize_for_match(text)


@pytest.mark.parametrize("text", _MAP_SAMPLES)
def test_normalize_with_map_round_trip(text):
    norm, idx_map = normalize_with_map(text)
    assert len(idx_map) == len(norm)
    assert list(idx_map) == sorted(idx_map)
    for i, raw_i in enumerate(idx_map):
        assert 0 <= raw_i < len(text)
        if norm[i] == " ":
            assert text[raw_i].isspace()
        else:
            # The raw cluster starting at raw_i normalises to (or contains) norm[i].
            cluster = text[raw_i:raw_i + 2]
            assert norm[i] in normalize_for_match(cluster) + normalize_for_match(text[raw_i])


def test_normalize_with_map_ligature_maps_both_chars_to_ligature():
    norm, idx_map = normalize_with_map("a \ufb01ne day")
    assert norm == "a fine day"
    assert idx_map[2] == idx_map[3] == 2


@pytest.mark.parametrize("pdf_name", ["cot.pdf", "react.pdf", "reflexion.pdf"])
def test_normalize_with_map_equals_normalize_for_match_on_paper_text(pdf_name):
    fitz = pytest.importorskip("fitz")
    pdf_path = Path(__file__).parent.parent.parent / "docs" / "research_papers" / pdf_name
    if not pdf_path.exists():
        pytest.skip(f"{pdf_path} not present")
    with fitz.open(pdf_path) as doc:
        text = "".join(page.get_text() for page in doc)
    norm, idx_map = normalize_with_map(text)
    assert norm == normalize_for_match(text)
    assert len(idx_map) == len(norm)


def test_ligature_span_gets_real_context_covering_the_ligature():
    paper = _FILLER + "\n\ne\ufb00ective \ufb01ne-tuning of \ufb01ve \ufb02ows\n\n" + _FILLER
    quote = "effective fine-tuning of five flows"
    context, source = _audit_context(quote, paper, normalize=True)
    assert source == "normalized"
    assert "e\ufb00ective \ufb01ne-tuning of \ufb01ve \ufb02ows" in context


def test_table_row_split_by_newlines_gets_real_context():
    paper = _FILLER + "\n\nTable 1: HotpotQA (EM)\nAct\n25.7\n58.9\nReAct\n27.4\n60.9\n\n" + _FILLER
    context, source = _audit_context("Act 25.7 58.9", paper, normalize=True)
    assert source == "normalized"
    assert "Table 1: HotpotQA (EM)\nAct\n25.7\n58.9" in context


def test_hyphen_join_maps_back_to_raw_hyphenated_span():
    paper = _FILLER + "we give an exam-\nple sentence here. " + _FILLER
    start, end = _normalized_alignment("an example sentence", paper)
    assert paper[start:end] == "an exam-\nple sentence"


def test_span_that_matched_raw_gets_identical_context():
    paper = _FILLER + "\n\nReAct outperforms Act on both HotpotQA and Fever.\n\n" + _FILLER
    quote = "ReAct outperforms Act on both HotpotQA and Fever."
    alignment = fuzz.partial_ratio_alignment(quote, paper)
    expected = _extract_span_context(paper, alignment.dest_start, alignment.dest_end)
    assert _audit_context(quote, paper, normalize=True) == (expected, "raw")
    assert _audit_context(quote, paper, normalize=False) == (expected, "raw")


def test_flag_off_keeps_quote_only_fallback():
    paper = _FILLER + "\n\nTable 1\nAct\n25.7\n58.9\n\n" + _FILLER
    assert _audit_context("Act 25.7 58.9", paper, normalize=False) == ("Act 25.7 58.9", "quote_only")
