"""Checklist parser and post-grounding verdict cap (extraction/verdict_rules.py)."""
import itertools

import pytest

from extraction.schemas import AuditChecklist, ClaimLabel, GroundingStatus
from extraction.verdict_rules import UNSPECIFIED_SECTION, apply_verdict_cap, parse_audit_checklist

WELL_FORMED = """Some reasoning prose about the claim. It even mentions the word VERDICT inline.

SUPPORT_QUOTE: Table 4 shows a 31% reduction.
SUPPORT_SECTION: Table 4
LIMIT_QUOTE: The saving vanishes on the longest sequences.
LIMIT_SECTION: Appendix B
CLAIM_SETTING: LatchNet vs baseline transformer, peak training memory, eight benchmark tasks
LIMIT_SAME_SETTING: yes
SCOPE_MATCH: no
COMPARISON_TESTED: yes
VERDICT: partially_supported"""


# --- parser ---


def test_well_formed_checklist_parses():
    parsed = parse_audit_checklist(WELL_FORMED, model_used="m1")
    c = parsed.checklist
    assert c.checklist_status == "parsed"
    assert c.problems == []
    assert c.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED
    assert c.scope_match == "no"
    assert c.comparison_tested == "yes"
    assert c.claim_setting == "LatchNet vs baseline transformer, peak training memory, eight benchmark tasks"
    assert c.limit_same_setting == "yes"
    assert c.has_limit_quote is True
    assert c.support_section == "Table 4"
    assert c.limit_section == "Appendix B"
    assert c.model_used == "m1"
    assert [(s.role, s.source_text, s.source_section) for s in parsed.spans] == [
        ("support", "Table 4 shows a 31% reduction.", "Table 4"),
        ("limit", "The saving vanishes on the longest sequences.", "Appendix B"),
    ]


def test_none_values_produce_no_spans():
    text = (
        "Prose.\nSUPPORT_QUOTE: NONE\nSUPPORT_SECTION: NONE\nLIMIT_QUOTE: NONE\nLIMIT_SECTION: NONE\n"
        "SCOPE_MATCH: yes\nCOMPARISON_TESTED: n/a\nVERDICT: supported"
    )
    parsed = parse_audit_checklist(text)
    assert parsed.checklist.checklist_status == "parsed"
    assert parsed.spans == []
    assert parsed.checklist.has_limit_quote is False
    assert parsed.checklist.support_section is None
    assert parsed.checklist.limit_section is None
    assert parsed.checklist.comparison_tested == "n/a"


@pytest.mark.parametrize("none_form", ["none", "None", "NONE.", " none "])
def test_none_is_case_and_punctuation_tolerant(none_form):
    text = WELL_FORMED.replace("LIMIT_QUOTE: The saving vanishes on the longest sequences.", f"LIMIT_QUOTE: {none_form}")
    parsed = parse_audit_checklist(text)
    assert parsed.checklist.has_limit_quote is False
    assert [s.role for s in parsed.spans] == ["support"]


def test_extra_whitespace_and_wrong_casing():
    text = (
        "Prose.\n"
        "  support_quote :   Some exact quote.   \n"
        "Support_Section:Table 1\n"
        "LIMIT_QUOTE:   none\n"
        "limit_section: NONE\n"
        "scope_match:   YES  \n"
        "Comparison_Tested: N/A\n"
        "  Verdict:   Supported  \n"
    )
    parsed = parse_audit_checklist(text)
    c = parsed.checklist
    assert c.checklist_status == "parsed", c.problems
    assert c.scope_match == "yes"
    assert c.comparison_tested == "n/a"
    assert c.auditor_verdict == ClaimLabel.SUPPORTED
    assert parsed.spans[0].source_text == "Some exact quote."
    assert parsed.spans[0].source_section == "Table 1"


def test_markdown_decoration_is_tolerated():
    text = WELL_FORMED.replace("VERDICT: partially_supported", "**VERDICT:** partially_supported")
    assert parse_audit_checklist(text).checklist.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED


def test_quote_may_wrap_onto_continuation_lines_until_blank_or_next_key():
    text = (
        "Prose.\n"
        "SUPPORT_QUOTE: First half of a quote\n"
        "second half of the quote.\n"
        "SUPPORT_SECTION: Section 3\n"
        "LIMIT_QUOTE: NONE\nLIMIT_SECTION: NONE\nSCOPE_MATCH: yes\nCOMPARISON_TESTED: n/a\nVERDICT: supported"
    )
    parsed = parse_audit_checklist(text)
    assert parsed.spans[0].source_text == "First half of a quote second half of the quote."


def test_last_occurrence_of_a_duplicated_line_wins():
    text = WELL_FORMED.replace("Some reasoning", "VERDICT: supported\nSome reasoning") + ""
    assert parse_audit_checklist(text).checklist.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED


@pytest.mark.parametrize(
    "missing_key",
    ["SUPPORT_QUOTE", "LIMIT_QUOTE", "SCOPE_MATCH", "COMPARISON_TESTED"],
)
def test_missing_hard_line_marks_unparsed_but_keeps_verdict_and_other_spans(missing_key):
    lines = [ln for ln in WELL_FORMED.splitlines() if not ln.startswith(missing_key + ":")]
    parsed = parse_audit_checklist("\n".join(lines))
    c = parsed.checklist
    assert c.checklist_status == "unparsed"
    assert f"missing:{missing_key}" in c.problems
    assert c.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED


def test_missing_verdict_leaves_verdict_none():
    text = "\n".join(ln for ln in WELL_FORMED.splitlines() if not ln.startswith("VERDICT:"))
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "unparsed"
    assert c.auditor_verdict is None
    assert "missing:VERDICT" in c.problems


@pytest.mark.parametrize(
    "line,field",
    [
        ("SCOPE_MATCH: maybe", "SCOPE_MATCH"),
        ("COMPARISON_TESTED: partially", "COMPARISON_TESTED"),
        ("VERDICT: kind of supported", "VERDICT"),
    ],
)
def test_invalid_enum_values_are_flagged_not_raised(line, field):
    key = line.split(":")[0]
    lines = [line if ln.startswith(key + ":") else ln for ln in WELL_FORMED.splitlines()]
    c = parse_audit_checklist("\n".join(lines)).checklist
    assert c.checklist_status == "unparsed"
    assert any(p.startswith(f"invalid:{field}") for p in c.problems)


def test_empty_quote_value_is_flagged_and_makes_no_span():
    text = WELL_FORMED.replace("SUPPORT_QUOTE: Table 4 shows a 31% reduction.", "SUPPORT_QUOTE:")
    parsed = parse_audit_checklist(text)
    assert "empty:SUPPORT_QUOTE" in parsed.checklist.problems
    assert [s.role for s in parsed.spans] == ["limit"]


@pytest.mark.parametrize("missing_key,role", [("SUPPORT_SECTION", "support"), ("LIMIT_SECTION", "limit")])
def test_missing_section_is_a_soft_problem_status_stays_parsed(missing_key, role):
    text = "\n".join(ln for ln in WELL_FORMED.splitlines() if not ln.startswith(missing_key + ":"))
    parsed = parse_audit_checklist(text)
    c = parsed.checklist
    assert c.checklist_status == "parsed"
    assert c.problems == [f"missing:{missing_key}"]
    span = next(s for s in parsed.spans if s.role == role)
    assert span.source_section == UNSPECIFIED_SECTION
    # The checklist is still usable by the cap.
    assert c.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED and c.scope_match == "no"


def test_soft_problem_plus_hard_problem_is_unparsed_and_records_both():
    lines = [ln for ln in WELL_FORMED.splitlines() if not ln.startswith(("LIMIT_SECTION:", "SCOPE_MATCH:"))]
    c = parse_audit_checklist("\n".join(lines)).checklist
    assert c.checklist_status == "unparsed"
    assert "missing:LIMIT_SECTION" in c.problems and "missing:SCOPE_MATCH" in c.problems


def test_cap_still_applies_when_only_a_section_line_is_missing():
    text = "\n".join(ln for ln in WELL_FORMED.splitlines() if not ln.startswith("LIMIT_SECTION:"))
    text = text.replace("VERDICT: partially_supported", "VERDICT: supported")
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "parsed"
    assert apply_verdict_cap(S, c, PASS) == (P, "limit")


# --- same-setting lines (B2) ---


def _without(*keys: str, text: str = WELL_FORMED) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith(tuple(k + ":" for k in keys)))


def test_new_lines_sit_before_scope_match_and_verdict_in_the_well_formed_example():
    lines = [ln.split(":")[0] for ln in WELL_FORMED.splitlines() if ":" in ln and ln.split(":")[0].isupper()]
    order = [k for k in lines if k in ("CLAIM_SETTING", "LIMIT_SAME_SETTING", "SCOPE_MATCH", "VERDICT")]
    assert order == ["CLAIM_SETTING", "LIMIT_SAME_SETTING", "SCOPE_MATCH", "VERDICT"]


def test_missing_limit_same_setting_is_soft_status_stays_parsed_and_scope_cap_still_fires():
    text = _without("LIMIT_SAME_SETTING").replace("VERDICT: partially_supported", "VERDICT: supported")
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "parsed"
    assert c.problems == ["missing:LIMIT_SAME_SETTING"]
    assert c.limit_same_setting is None
    assert c.has_limit_quote is True and c.scope_match == "no"
    # The limit quote is grounded, but without a usable same-setting value it does not count;
    # the scope rule (SCOPE_MATCH == no) still caps on this same checklist.
    assert apply_verdict_cap(S, c, PASS) == (P, "scope")


def test_missing_limit_same_setting_still_lets_the_comparison_cap_fire():
    text = _without("LIMIT_SAME_SETTING").replace("COMPARISON_TESTED: yes", "COMPARISON_TESTED: no")
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "parsed"
    assert apply_verdict_cap(S, c, PASS) == (N, "comparison")


@pytest.mark.parametrize("value", ["maybe", "yes | no | n/a", "sometimes", "same"])
def test_invalid_limit_same_setting_is_soft_and_does_not_count(value):
    text = WELL_FORMED.replace("LIMIT_SAME_SETTING: yes", f"LIMIT_SAME_SETTING: {value}")
    text = text.replace("SCOPE_MATCH: no", "SCOPE_MATCH: yes")
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "parsed"
    assert c.limit_same_setting is None
    assert any(p.startswith("invalid:LIMIT_SAME_SETTING=") for p in c.problems)
    assert apply_verdict_cap(S, c, PASS) == (S, None)


@pytest.mark.parametrize(
    "line,expected",
    [
        ("LIMIT_SAME_SETTING: yes", "yes"),
        ("LIMIT_SAME_SETTING: NO", "no"),
        ("LIMIT_SAME_SETTING: no (that caveat is about the 7B model)", "no"),
        ("LIMIT_SAME_SETTING: **yes**", "yes"),
    ],
)
def test_limit_same_setting_accepts_a_valid_leading_token(line, expected):
    text = WELL_FORMED.replace("LIMIT_SAME_SETTING: yes", line)
    c = parse_audit_checklist(text).checklist
    assert c.limit_same_setting == expected
    assert c.problems == [] and c.checklist_status == "parsed"


def test_n_a_next_to_a_real_limit_quote_is_soft_recorded_and_does_not_count():
    text = WELL_FORMED.replace("LIMIT_SAME_SETTING: yes", "LIMIT_SAME_SETTING: n/a").replace(
        "SCOPE_MATCH: no", "SCOPE_MATCH: yes"
    )
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "parsed"
    assert c.limit_same_setting == "n/a" and c.has_limit_quote is True
    assert any(p.startswith("inconsistent:LIMIT_SAME_SETTING") for p in c.problems)
    assert apply_verdict_cap(S, c, PASS) == (S, None)


def test_n_a_with_no_limit_quote_is_clean():
    text = WELL_FORMED.replace("LIMIT_QUOTE: The saving vanishes on the longest sequences.", "LIMIT_QUOTE: NONE")
    text = text.replace("LIMIT_SAME_SETTING: yes", "LIMIT_SAME_SETTING: n/a")
    c = parse_audit_checklist(text).checklist
    assert c.problems == [] and c.limit_same_setting == "n/a" and c.has_limit_quote is False


@pytest.mark.parametrize("missing", [["CLAIM_SETTING"], ["CLAIM_SETTING", "LIMIT_SAME_SETTING"]])
def test_missing_claim_setting_is_soft_and_trace_only(missing):
    c = parse_audit_checklist(_without(*missing)).checklist
    assert c.checklist_status == "parsed"
    assert c.claim_setting is None
    assert all(f"missing:{k}" in c.problems for k in missing)


def test_empty_claim_setting_is_soft():
    text = WELL_FORMED.replace(
        "CLAIM_SETTING: LatchNet vs baseline transformer, peak training memory, eight benchmark tasks", "CLAIM_SETTING:   "
    )
    c = parse_audit_checklist(text).checklist
    assert c.checklist_status == "parsed"
    assert c.claim_setting is None and "empty:CLAIM_SETTING" in c.problems


def test_a_checklist_without_the_new_lines_never_caps_on_limit_but_other_rules_work():
    old_style = AuditChecklist(checklist_status="parsed", scope_match="yes", comparison_tested="n/a", has_limit_quote=True)
    assert old_style.limit_same_setting is None and old_style.claim_setting is None
    assert apply_verdict_cap(S, old_style, PASS) == (S, None)


# --- leading-token enum parsing ---


@pytest.mark.parametrize(
    "line,field,expected",
    [
        ("SCOPE_MATCH: no (only two toy tasks)", "scope_match", "no"),
        ("SCOPE_MATCH: YES - covers all tasks", "scope_match", "yes"),
        ("COMPARISON_TESTED: N/A.", "comparison_tested", "n/a"),
        ("COMPARISON_TESTED: n/a (the claim is not comparative)", "comparison_tested", "n/a"),
        ("COMPARISON_TESTED: No, the baseline was never run", "comparison_tested", "no"),
        ("SCOPE_MATCH: **yes**", "scope_match", "yes"),
        ('SCOPE_MATCH: "no"', "scope_match", "no"),
        ("VERDICT: partially_supported — because the appendix narrows it", "auditor_verdict", ClaimLabel.PARTIALLY_SUPPORTED),
        ("VERDICT: NOT_SUPPORTED.", "auditor_verdict", ClaimLabel.NOT_SUPPORTED),
        ("VERDICT: supported (see Table 4)", "auditor_verdict", ClaimLabel.SUPPORTED),
    ],
)
def test_enum_lines_accept_a_valid_leading_token_with_trailing_text(line, field, expected):
    key = line.split(":")[0]
    lines = [line if ln.startswith(key + ":") else ln for ln in WELL_FORMED.splitlines()]
    c = parse_audit_checklist("\n".join(lines)).checklist
    assert getattr(c, field) == expected
    assert c.checklist_status == "parsed", c.problems


@pytest.mark.parametrize(
    "line",
    [
        "SCOPE_MATCH: nothing was tested",
        "SCOPE_MATCH: yesterday",
        "SCOPE_MATCH: yes | no",
        "SCOPE_MATCH: yes/no",
        "SCOPE_MATCH: maybe, yes",
        "COMPARISON_TESTED: partially",
        "COMPARISON_TESTED: na",
        "VERDICT: kind of supported",
        "VERDICT: unsupported",
        "VERDICT: supported_ish",
    ],
)
def test_enum_lines_without_a_valid_leading_token_stay_invalid(line):
    key = line.split(":")[0]
    lines = [line if ln.startswith(key + ":") else ln for ln in WELL_FORMED.splitlines()]
    c = parse_audit_checklist("\n".join(lines)).checklist
    assert c.checklist_status == "unparsed"
    assert any(p.startswith(f"invalid:{key}=") for p in c.problems), c.problems


def test_partially_supported_with_trailing_text_is_not_misread_as_supported():
    lines = [("VERDICT: partially_supported (mostly fine)" if ln.startswith("VERDICT:") else ln) for ln in WELL_FORMED.splitlines()]
    assert parse_audit_checklist("\n".join(lines)).checklist.auditor_verdict == ClaimLabel.PARTIALLY_SUPPORTED


# --- quote wrapping ---


@pytest.mark.parametrize(
    "wrapped",
    ['"NONE"', "“NONE”", "'none'", "‘None’", '"NONE".', "`NONE`"],
)
def test_wrapped_none_is_still_none(wrapped):
    text = WELL_FORMED.replace("LIMIT_QUOTE: The saving vanishes on the longest sequences.", f"LIMIT_QUOTE: {wrapped}")
    parsed = parse_audit_checklist(text)
    assert parsed.checklist.checklist_status == "parsed"
    assert parsed.checklist.has_limit_quote is False
    assert [s.role for s in parsed.spans] == ["support"]


@pytest.mark.parametrize(
    "wrapped",
    [
        '"Table 4 shows a 31% reduction."',
        "“Table 4 shows a 31% reduction.”",
        "'Table 4 shows a 31% reduction.'",
        '  " Table 4 shows a 31% reduction. "  ',
    ],
)
def test_one_pair_of_surrounding_quotes_is_stripped_from_quote_text(wrapped):
    text = WELL_FORMED.replace("SUPPORT_QUOTE: Table 4 shows a 31% reduction.", f"SUPPORT_QUOTE: {wrapped}")
    support = next(s for s in parse_audit_checklist(text).spans if s.role == "support")
    assert support.source_text == "Table 4 shows a 31% reduction."


def test_only_one_pair_is_stripped_and_unbalanced_quotes_are_left_alone():
    nested = WELL_FORMED.replace("SUPPORT_QUOTE: Table 4 shows a 31% reduction.", 'SUPPORT_QUOTE: ""Reduction" was 31%"')
    assert next(s for s in parse_audit_checklist(nested).spans if s.role == "support").source_text == '"Reduction" was 31%'

    unbalanced = WELL_FORMED.replace("SUPPORT_QUOTE: Table 4 shows a 31% reduction.", 'SUPPORT_QUOTE: "Reduction" was 31%')
    assert next(s for s in parse_audit_checklist(unbalanced).spans if s.role == "support").source_text == '"Reduction" was 31%'


def test_quote_that_is_only_a_quote_pair_is_empty_and_hard():
    text = WELL_FORMED.replace("SUPPORT_QUOTE: Table 4 shows a 31% reduction.", 'SUPPORT_QUOTE: ""')
    parsed = parse_audit_checklist(text)
    assert parsed.checklist.checklist_status == "unparsed"
    assert "empty:SUPPORT_QUOTE" in parsed.checklist.problems
    assert [s.role for s in parsed.spans] == ["limit"]


def test_garbage_and_empty_input_never_raise():
    for text in ["", "no checklist at all", "VERDICT:", ":::", "\n\n\n"]:
        parsed = parse_audit_checklist(text)
        assert parsed.checklist.checklist_status == "unparsed"
        assert parsed.checklist.problems


# --- cap ---


def _checklist(*, status="parsed", scope="yes", comparison="n/a", has_limit=False, same_setting="yes") -> AuditChecklist:
    return AuditChecklist(
        checklist_status=status,
        scope_match=scope,
        comparison_tested=comparison,
        has_limit_quote=has_limit,
        limit_same_setting=same_setting,
    )


S, P, N = ClaimLabel.SUPPORTED, ClaimLabel.PARTIALLY_SUPPORTED, ClaimLabel.NOT_SUPPORTED
PASS, PARTIAL, FAIL, SKIPPED = (
    GroundingStatus.PASS,
    GroundingStatus.PARTIAL,
    GroundingStatus.FAIL,
    GroundingStatus.SKIPPED,
)


def test_comparison_not_tested_forces_not_supported_from_any_verdict():
    assert apply_verdict_cap(S, _checklist(comparison="no"), None) == (N, "comparison")
    assert apply_verdict_cap(P, _checklist(comparison="no"), None) == (N, "comparison")


def test_comparison_not_tested_on_already_not_supported_is_unchanged_with_no_reason():
    assert apply_verdict_cap(N, _checklist(comparison="no"), None) == (N, None)


def test_comparison_takes_precedence_over_limit_and_scope():
    cl = _checklist(comparison="no", scope="no", has_limit=True)
    assert apply_verdict_cap(S, cl, PASS) == (N, "comparison")


@pytest.mark.parametrize("limit_status", [PASS, PARTIAL])
def test_grounded_limit_quote_caps_supported_to_partial(limit_status):
    assert apply_verdict_cap(S, _checklist(has_limit=True), limit_status) == (P, "limit")


@pytest.mark.parametrize("limit_status", [FAIL, SKIPPED, None])
def test_limit_quote_that_does_not_ground_never_caps(limit_status):
    assert apply_verdict_cap(S, _checklist(has_limit=True), limit_status) == (S, None)


@pytest.mark.parametrize("limit_status", [PASS, PARTIAL])
def test_limit_from_a_different_setting_does_not_cap(limit_status):
    assert apply_verdict_cap(S, _checklist(has_limit=True, same_setting="no"), limit_status) == (S, None)


@pytest.mark.parametrize("same_setting", ["no", "n/a", None])
def test_limit_that_does_not_count_falls_through_to_scope_and_comparison(same_setting):
    scope_no = _checklist(scope="no", has_limit=True, same_setting=same_setting)
    assert apply_verdict_cap(S, scope_no, PASS) == (P, "scope")
    comparison_no = _checklist(comparison="no", has_limit=True, same_setting=same_setting)
    assert apply_verdict_cap(S, comparison_no, PASS) == (N, "comparison")


def test_same_setting_limit_caps_as_before():
    assert apply_verdict_cap(S, _checklist(has_limit=True, same_setting="yes"), PASS) == (P, "limit")


def test_scope_mismatch_caps_supported_to_partial():
    assert apply_verdict_cap(S, _checklist(scope="no"), None) == (P, "scope")


def test_limit_reason_takes_precedence_over_scope():
    assert apply_verdict_cap(S, _checklist(scope="no", has_limit=True), PASS) == (P, "limit")


def test_ungrounded_limit_falls_through_to_scope():
    assert apply_verdict_cap(S, _checklist(scope="no", has_limit=True), FAIL) == (P, "scope")


def test_clean_supported_is_untouched():
    assert apply_verdict_cap(S, _checklist(comparison="yes"), None) == (S, None)
    assert apply_verdict_cap(S, _checklist(comparison="n/a"), None) == (S, None)


@pytest.mark.parametrize("verdict", [P, N])
def test_limit_and_scope_never_touch_non_supported_verdicts(verdict):
    cl = _checklist(scope="no", has_limit=True)
    assert apply_verdict_cap(verdict, cl, PASS) == (verdict, None)


def test_unparsed_checklist_never_caps():
    cl = _checklist(status="unparsed", scope="no", comparison="no", has_limit=True)
    assert apply_verdict_cap(S, cl, PASS) == (S, None)


def test_cap_never_raises_a_label_full_truth_table():
    rank = {N: 0, P: 1, S: 2}
    for verdict, scope, comparison, has_limit, same_setting, limit_status, status in itertools.product(
        [S, P, N],
        ["yes", "no", None],
        ["yes", "no", "n/a", None],
        [True, False],
        ["yes", "no", "n/a", None],
        [PASS, PARTIAL, FAIL, SKIPPED, None],
        ["parsed", "unparsed"],
    ):
        cl = _checklist(
            status=status, scope=scope, comparison=comparison, has_limit=has_limit, same_setting=same_setting
        )
        final, reason = apply_verdict_cap(verdict, cl, limit_status)
        assert rank[final] <= rank[verdict]
        assert (reason is None) == (final == verdict)
