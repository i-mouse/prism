"""Combines a claim's scope-check result into its verdict (code only, no model call).

Runs at paper level as the LAST step of a replay, after grounding, so the
auditor, structurer and grounding see exactly the inputs they see with the scope
check off.

Rule: lower ONLY a "supported" label, to "partially_supported", when at least one
item the checker marked "contradicted" passes the guard below. The first passing
item, in item order, is the one reported. partially_supported and not_supported
never change; "matches" and "not_reported" items never lower anything. Nothing
here raises: on any internal error the verdict stays and the error is logged.

Guard for a contradicted item: its contradicting_quote is not null, its
normalised text is at least MIN_QUOTE_NORM_LEN characters, and it passes the same
Stage-1 match grounding applies to evidence spans, against the same paper text.

Item kinds come from the lister, paired with the checker's items by index (the
checker is not asked to echo them). When the two lists differ in length the
shorter one decides how many are paired, and the claim is counted as a mismatch.
Kinds are report-only: no code here branches on one.
"""
import logging
from dataclasses import dataclass, field

from extraction import grounding
from extraction.scope_check import ClaimScope, ScopeStats

logger = logging.getLogger(__name__)

MIN_QUOTE_NORM_LEN = 20
LOWERED_FROM = "supported"
LOWERED_TO = "partially_supported"


@dataclass
class ScopeTrace:
    """What the replay output records for one claim (flag on only)."""
    auditor_label: str
    label: str
    scope_lowered: bool = False
    scope_item: str | None = None
    scope_item_kind: str | None = None
    scope_quote: str | None = None
    scope_items: list[dict] = field(default_factory=list)

    def to_fields(self) -> dict:
        return {
            "auditor_label": self.auditor_label,
            "label": self.label,
            "scope_lowered": self.scope_lowered,
            "scope_item": self.scope_item,
            "scope_item_kind": self.scope_item_kind,
            "scope_quote": self.scope_quote,
            "scope_items": self.scope_items,
        }


def quote_passes_guard(quote: str | None, paper_text: str) -> bool:
    if quote is None:
        return False
    if len(grounding.normalize_for_match(quote)) < MIN_QUOTE_NORM_LEN:
        return False
    return bool(grounding._passes_rapidfuzz(quote, paper_text))


def combine_scope(
    label: str, scope: ClaimScope | None, paper_text: str, stats: ScopeStats, claim_ref: str = "",
) -> ScopeTrace:
    """Returns the claim's trace; trace.label is the final verdict. label is the
    auditor's label as a plain string."""
    trace = ScopeTrace(auditor_label=label, label=label)
    if scope is None or scope.checks is None:
        return trace
    try:
        if len(scope.items) != len(scope.checks):
            stats.item_count_mismatches += 1
            logger.warning(
                "scope item count mismatch for %s: lister %d, checker %d; pairing by index up to the shorter",
                claim_ref, len(scope.items), len(scope.checks),
            )
        first_passing: dict | None = None
        for listed, checked in zip(scope.items, scope.checks):
            entry = {
                "text": listed.text, "kind": listed.kind, "status": checked.status,
                "contradicting_quote": checked.contradicting_quote, "guard_passed": None,
            }
            if checked.status == "contradicted":
                stats.contradicted_items += 1
                passed = quote_passes_guard(checked.contradicting_quote, paper_text)
                entry["guard_passed"] = passed
                if not passed:
                    stats.guard_failed += 1
                logger.info(
                    "scope contradicted item for %s: kind=%s guard_passed=%s item=%r quote=%r",
                    claim_ref, listed.kind, passed, listed.text, checked.contradicting_quote,
                )
                if passed and first_passing is None:
                    first_passing = entry
            trace.scope_items.append(entry)

        if label == LOWERED_FROM and first_passing is not None:
            stats.verdicts_lowered += 1
            trace.label = LOWERED_TO
            trace.scope_lowered = True
            trace.scope_item = first_passing["text"]
            trace.scope_item_kind = first_passing["kind"]
            trace.scope_quote = first_passing["contradicting_quote"]
            logger.warning("scope check lowered %s from %s to %s", claim_ref, LOWERED_FROM, LOWERED_TO)
    except Exception:
        logger.error("SCOPE COMBINE FAILED for %s; verdict unchanged", claim_ref, exc_info=True)
        return ScopeTrace(auditor_label=label, label=label)
    return trace
