"""Deterministic handling of the auditor's checklist (B5.1).

Two pure pieces, no LLM and no I/O:
  - parse_audit_checklist: reads the SUPPORT_QUOTE/.../VERDICT lines the
    auditor ends its reasoning with.
  - apply_verdict_cap: the post-grounding rule that can only LOWER the
    auditor's verdict. The grounder never feeds back into the auditor; this
    cap is a separate, deterministic step that runs after grounding.
"""
import re
from typing import NamedTuple, Optional

from extraction.schemas import (
    AuditChecklist,
    AuditedSpan,
    CapReason,
    ClaimLabel,
    GroundingStatus,
)

UNSPECIFIED_SECTION = "Unspecified"

_QUOTE_KEYS = ("SUPPORT_QUOTE", "LIMIT_QUOTE")
_SECTION_KEYS = ("SUPPORT_SECTION", "LIMIT_SECTION")
_ENUM_KEYS = ("SCOPE_MATCH", "COMPARISON_TESTED", "VERDICT")
_ALL_KEYS = _QUOTE_KEYS + _SECTION_KEYS + _ENUM_KEYS

# A checklist line: optional markdown/bullet noise, the key, a colon, the value.
_KEY_LINE = re.compile(
    r"^\s*(?:[*_#>\-]+\s*)?(" + "|".join(_ALL_KEYS) + r")\s*[*_]*\s*:\s*[*_]*\s*(.*?)\s*$",
    re.IGNORECASE,
)

_VERDICTS = {label.value: label for label in ClaimLabel}
_SCOPE_VALUES = ("yes", "no")
_COMPARISON_VALUES = ("yes", "no", "n/a")

# Markup and quote characters that may wrap or precede an enum value.
_ENUM_LEAD_NOISE = " \t*_`\"'“”‘’"
_QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))
_NONE_NOISE = " \t*_`.\"'“”‘’"


def _leading_token_pattern(allowed: tuple[str, ...]) -> re.Pattern[str]:
    """Matches one of `allowed` at the start of a value, at a token boundary:
    not followed by a word character, `|` or `/` (so "nothing" and the echoed
    template "yes | no" don't match). Trailing text after the token is fine."""
    alternatives = "|".join(re.escape(a) for a in sorted(allowed, key=len, reverse=True))
    return re.compile(rf"^(?:{alternatives})(?![A-Za-z0-9_|/])(?!\s*\|)", re.IGNORECASE)


_SCOPE_PATTERN = _leading_token_pattern(_SCOPE_VALUES)
_COMPARISON_PATTERN = _leading_token_pattern(_COMPARISON_VALUES)
_VERDICT_PATTERN = _leading_token_pattern(tuple(_VERDICTS))

# Lower rank = harsher label. The cap only ever moves a label down this scale.
_RANK = {
    ClaimLabel.NOT_SUPPORTED: 0,
    ClaimLabel.PARTIALLY_SUPPORTED: 1,
    ClaimLabel.SUPPORTED: 2,
}


class ParsedAudit(NamedTuple):
    checklist: AuditChecklist
    spans: list[AuditedSpan]


def _is_none(value: str) -> bool:
    return value.strip(_NONE_NOISE).upper() == "NONE"


def _leading_enum(value: str, pattern: re.Pattern[str]) -> Optional[str]:
    """Returns the lower-cased valid leading token of `value`, or None.

    "no (only two toy tasks)" -> "no"; "N/A." -> "n/a"; "maybe" -> None.
    """
    match = pattern.match(value.lstrip(_ENUM_LEAD_NOISE))
    return match.group(0).lower() if match else None


def _strip_quote_pair(value: str) -> str:
    """Strips ONE pair of surrounding quote characters (straight or curly)."""
    value = value.strip()
    for opening, closing in _QUOTE_PAIRS:
        if len(value) >= 2 and value.startswith(opening) and value.endswith(closing):
            return value[1:-1].strip()
    return value


def _collect_lines(audit_text: str) -> dict[str, str]:
    """Maps each checklist key to its value, last occurrence winning.

    A quote or section value may wrap onto following lines; continuation
    lines are joined with a space until a blank line or the next key line.
    Enum keys never continue.
    """
    values: dict[str, str] = {}
    current: Optional[str] = None
    for raw in audit_text.splitlines():
        match = _KEY_LINE.match(raw)
        if match:
            current = match.group(1).upper()
            values[current] = match.group(2)
        elif not raw.strip():
            current = None
        elif current is not None and current not in _ENUM_KEYS:
            values[current] = f"{values[current]} {raw.strip()}".strip()
    return values


def parse_audit_checklist(audit_text: str, model_used: Optional[str] = None) -> ParsedAudit:
    """Parses the auditor's checklist lines out of its free-text audit.

    Never raises and never drops the claim. Problems are recorded in
    checklist.problems in two tiers:
      - HARD (flips checklist_status to "unparsed"): VERDICT, SCOPE_MATCH or
        COMPARISON_TESTED missing/invalid; SUPPORT_QUOTE or LIMIT_QUOTE
        missing or empty.
      - SOFT (recorded, status stays "parsed"): SUPPORT_SECTION or
        LIMIT_SECTION missing - the quote is still usable, only its
        location label is lost (it falls back to UNSPECIFIED_SECTION).
    Whatever did parse (notably VERDICT and any quotes) is kept either way.
    Keys are matched case-insensitively. Enum lines accept a valid leading
    token followed by optional trailing text ("no (only two tasks)") and are
    lower-cased. One pair of surrounding quote characters is stripped from
    quote values.
    """
    values = _collect_lines(audit_text)
    problems: list[str] = []
    hard_problem = False

    for key in _ALL_KEYS:
        if key not in values:
            problems.append(f"missing:{key}")
            hard_problem = hard_problem or key not in _SECTION_KEYS

    verdict: Optional[ClaimLabel] = None
    if "VERDICT" in values:
        token = _leading_enum(values["VERDICT"], _VERDICT_PATTERN)
        verdict = _VERDICTS[token] if token is not None else None
        if verdict is None:
            problems.append(f"invalid:VERDICT={values['VERDICT']!r}")
            hard_problem = True

    scope_match: Optional[str] = None
    if "SCOPE_MATCH" in values:
        scope_match = _leading_enum(values["SCOPE_MATCH"], _SCOPE_PATTERN)
        if scope_match is None:
            problems.append(f"invalid:SCOPE_MATCH={values['SCOPE_MATCH']!r}")
            hard_problem = True

    comparison_tested: Optional[str] = None
    if "COMPARISON_TESTED" in values:
        comparison_tested = _leading_enum(values["COMPARISON_TESTED"], _COMPARISON_PATTERN)
        if comparison_tested is None:
            problems.append(f"invalid:COMPARISON_TESTED={values['COMPARISON_TESTED']!r}")
            hard_problem = True

    spans: list[AuditedSpan] = []
    sections: dict[str, Optional[str]] = {}
    has_quote: dict[str, bool] = {}
    for role, quote_key, section_key in (
        ("support", "SUPPORT_QUOTE", "SUPPORT_SECTION"),
        ("limit", "LIMIT_QUOTE", "LIMIT_SECTION"),
    ):
        quote = values.get(quote_key)
        section = values.get(section_key)
        sections[role] = None if section is None or _is_none(section) or not section else section
        has_quote[role] = False
        if quote is None:
            continue
        quote = _strip_quote_pair(quote)
        if not quote:
            problems.append(f"empty:{quote_key}")
            hard_problem = True
            continue
        if _is_none(quote):
            continue
        has_quote[role] = True
        spans.append(
            AuditedSpan(
                source_text=quote,
                source_section=sections[role] or UNSPECIFIED_SECTION,
                role=role,
            )
        )

    checklist = AuditChecklist(
        checklist_status="unparsed" if hard_problem else "parsed",
        auditor_verdict=verdict,
        support_section=sections["support"],
        limit_section=sections["limit"],
        has_limit_quote=has_quote["limit"],
        scope_match=scope_match,
        comparison_tested=comparison_tested,
        problems=problems,
        model_used=model_used,
    )
    return ParsedAudit(checklist=checklist, spans=spans)


def apply_verdict_cap(
    auditor_verdict: ClaimLabel,
    checklist: AuditChecklist,
    limit_grounding: Optional[GroundingStatus],
) -> tuple[ClaimLabel, Optional[CapReason]]:
    """Returns (final_label, cap_reason). Only ever lowers the verdict.

    Rules, in precedence order:
      - COMPARISON_TESTED == no            -> not_supported ("comparison")
      - auditor verdict is supported and
          (a limit quote exists and its span grounded Pass/Partial, or
           SCOPE_MATCH == no)              -> partially_supported ("limit"
                                              takes precedence over "scope")
    cap_reason is None whenever the label is unchanged. An unparsed checklist
    never caps, and a limit span that failed grounding or was Skipped
    (limit_grounding Fail/Skipped/None) does not trigger the limit cap.
    """
    if checklist.checklist_status != "parsed":
        return auditor_verdict, None

    final = auditor_verdict
    reason: Optional[CapReason] = None

    if checklist.comparison_tested == "no":
        final, reason = ClaimLabel.NOT_SUPPORTED, "comparison"
    elif auditor_verdict == ClaimLabel.SUPPORTED:
        limit_grounded = checklist.has_limit_quote and limit_grounding in (
            GroundingStatus.PASS,
            GroundingStatus.PARTIAL,
        )
        if limit_grounded:
            final, reason = ClaimLabel.PARTIALLY_SUPPORTED, "limit"
        elif checklist.scope_match == "no":
            final, reason = ClaimLabel.PARTIALLY_SUPPORTED, "scope"

    if _RANK[final] >= _RANK[auditor_verdict]:
        return auditor_verdict, None
    return final, reason
