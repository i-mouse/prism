from decimal import Decimal

import pytest

from eval.auditor_v2.cell_parser import parse_cell, values_equal


def num(text):
    p = parse_cell(text)
    assert p.kind == "number", (text, p)
    return p


@pytest.mark.parametrize(
    "text,expected",
    [
        ("12.3", "12.3"),
        (".709", "0.709"),
        ("0.709", "0.709"),
        ("-.5", "-0.5"),
        ("+0.30", "0.30"),
        ("-0.38", "-0.38"),
        ("−0.38", "-0.38"),  # unicode minus
        ("–5", "-5"),  # en dash as sign before a digit
        ("265,965", "265965"),
        ("68,136,934", "68136934"),
        ("1,234", "1234"),
        ("12", "12"),
        ("  97.93  ", "97.93"),
    ],
)
def test_plain_numbers(text, expected):
    assert num(text).value == Decimal(expected)


def test_percent_unit_is_recorded_and_ignored_in_value():
    p = num("95.8%")
    assert p.value == Decimal("95.8") and p.unit == "%"
    assert values_equal(p, parse_cell("95.8"))


@pytest.mark.parametrize("text", [".709+-.059", ".709 +- .059", "0.709 ± 0.059", ".709±.059", "0.709 +/- 0.059"])
def test_sd_formats(text):
    p = num(text)
    assert p.value == Decimal("0.709") and p.sd == Decimal("0.059")


def test_sd_is_ignored_unless_requested():
    a, b = parse_cell(".709+-.059"), parse_cell(".709+-.103")
    assert values_equal(a, b)
    assert not values_equal(a, b, with_sd=True)
    assert values_equal(parse_cell(".709+-.059"), parse_cell("0.709 ± 0.059"), with_sd=True)


@pytest.mark.parametrize("text,markers", [("87.27*", ("*",)), ("87.27†", ("†",)), ("87.27‡", ("‡",)), ("87.27 *†", ("*", "†"))])
def test_trailing_markers_recorded_and_stripped(text, markers):
    p = num(text)
    assert p.value == Decimal("87.27") and p.markers == markers


def test_bold_markers():
    p = num("**81.57**")
    assert p.value == Decimal("81.57") and p.bold
    p = num("<b>81.57</b>")
    assert p.value == Decimal("81.57") and p.bold
    p = num("**81.57***")  # bold plus a trailing marker is still not text
    assert p.kind == "number"


@pytest.mark.parametrize("text", ["-", "—", "–", "−", "N/A", "n/a", "OOM", "oom", "", "   "])
def test_missing_tokens(text):
    assert parse_cell(text).kind == "missing"


def test_missing_with_marker_or_bold():
    assert parse_cell("-*").kind == "missing"
    assert parse_cell("**-**").kind == "missing"


def test_missing_is_not_zero_and_not_a_number():
    assert not values_equal(parse_cell("-"), parse_cell(".0"))
    assert values_equal(parse_cell("-"), parse_cell("—"))
    assert values_equal(parse_cell("N/A"), parse_cell("OOM"))


def test_pairs():
    p = parse_cell("44.5 / 53.3")
    assert p.kind == "pair" and p.pair == (Decimal("44.5"), Decimal("53.3"))
    p = parse_cell("12/12")
    assert p.kind == "pair" and p.pair == (Decimal("12"), Decimal("12"))
    assert values_equal(parse_cell("44.5/53.3"), parse_cell("44.5 / 53.3"))
    assert not values_equal(parse_cell("44.5 / 53.3"), parse_cell("44.5 / 53.4"))


def test_pair_vs_number_not_equal():
    assert not values_equal(parse_cell("12/12"), parse_cell("12"))


@pytest.mark.parametrize("text", ["1.2.3", "abc", "+-", "+", "1,23", "12 apples", "x / y"])
def test_malformed_is_text(text):
    assert parse_cell(text).kind == "text"


def test_numeric_equality_ignores_trailing_zeros_and_sign_plus():
    assert values_equal(parse_cell("50.0"), parse_cell("50"))
    assert values_equal(parse_cell("+0.30"), parse_cell("0.3"))
    assert values_equal(parse_cell(".709"), parse_cell("0.709"))
    assert not values_equal(parse_cell("0.30"), parse_cell("0.31"))


def test_unicode_minus_equals_hyphen_minus():
    assert values_equal(parse_cell("−0.38"), parse_cell("-0.38"))


def test_negative_zero():
    assert values_equal(parse_cell("-0.0"), parse_cell("0.0"))


def test_nbsp_and_non_string():
    assert num(" 97.7 ").value == Decimal("97.7")
    assert parse_cell(None).kind == "missing"


def test_huge_thousands():
    assert num("1,234,567,890,123").value == Decimal("1234567890123")


def test_text_equality_is_exact_stripped():
    assert values_equal(parse_cell(" abc "), parse_cell("abc"))
    assert not values_equal(parse_cell("abc"), parse_cell("abd"))
