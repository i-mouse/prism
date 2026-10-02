"""Grounding gate for table-row-like quotes (no LLM calls).

Table-row-like quotes must match as a contiguous run of WHOLE tokens in the paper
text; every other quote keeps the RapidFuzz gate. The PDF-backed tests rebuild
paper_text exactly as main.py does and skip when a PDF is not on disk.
"""
import asyncio
import random
import re
from pathlib import Path

import fitz
import pytest
from rapidfuzz import fuzz

from extraction import grounding
from extraction.schemas import AuditedSpan, ClaimLabel, GroundingStatus

DOWNLOADS = Path(__file__).parent.parent / "downloads"
PDFS = {
    "react": "2210.03629v3.pdf",
    "cot": "2201.11903v6.pdf",
    "reflexion": "2303.11366v4.pdf",
}

_PAPER_CACHE: dict[str, str] = {}
SEED = 20261002
WINDOWS_PER_PAPER = 300
END_TO_END_PER_PAPER = 40


def paper_text(name: str) -> str:
    """Same construction as main.py: page.get_text() of every page, concatenated."""
    if name not in _PAPER_CACHE:
        path = DOWNLOADS / PDFS[name]
        if not path.exists():
            pytest.skip(f"{path} not available")
        text = ""
        with fitz.open(path) as doc:
            for page in doc:
                text += page.get_text()
        _PAPER_CACHE[name] = text
    return _PAPER_CACHE[name]


_AUDIT_CALLS: list[dict] = []


@pytest.fixture(autouse=True)
def _stub_audit(monkeypatch):
    _AUDIT_CALLS.clear()

    async def fake_audit(claim_text, claim_label, span_source_text, span_context, **kwargs):
        _AUDIT_CALLS.append({"quote": span_source_text, "context": span_context})
        return grounding.SpanAuditResult(GroundingStatus.PASS, "supports", "r", "m")

    monkeypatch.setattr(grounding, "_audit_span_with_llm", fake_audit)


def ground(quote: str, text: str, role: str = "support"):
    """Runs the real _ground_span (audit stubbed). Returns (final span, passed gate)."""
    return asyncio.run(
        grounding._ground_span(
            claim_text="claim",
            claim_label=ClaimLabel.SUPPORTED,
            span=AuditedSpan(source_text=quote, source_section="s", role=role),
            paper_text=text,
            semaphore=asyncio.Semaphore(1),
            audit_model="m",
            fallback_model="f",
            gemini_api_key="k",
        )
    )


# --- quote type ---


@pytest.mark.parametrize(
    "quote,expected",
    [
        ("Act 25.7 58.9", True),
        ("ReAct (best of 6) 92 58 96 86 78 41 71", True),
        ("31 77 4 90 12 55 6", True),
        ("PaLM-540B reaches 27.4 EM on HotpotQA.", False),
        ("Table 1: PaLM-540B prompting results on HotpotQA and Fever.", False),
        ("Table 3 92 58 96 86 78", False),  # captions never use the token gate
        ("Figure 2 12 34 56", False),
        ("(a) 12 34 56", False),
        ("", False),
        ("   ", False),
    ],
)
def test_table_row_like_definition(quote, expected):
    assert grounding.is_table_row_like(quote) is expected


# --- synthetic whole-token behaviour (no PDF needed) ---

SYNTH = "Method\nScore\nAlpha\n12.5\n30.1\nReAlpha\n12.5\n30.1\nBeta (avg)\n7\n8\n9\n"


def test_whole_tokens_only_a_label_is_not_matched_inside_a_longer_label():
    assert grounding._find_token_exact("Alpha 12.5 30.1", SYNTH) is not None
    assert grounding._find_token_exact("ReAlpha 12.5 30.1", SYNTH) is not None
    # "lpha 12.5 30.1" is a substring of "Alpha"/"ReAlpha" rows but not a whole-token run.
    assert grounding._find_token_exact("lpha 12.5 30.1", SYNTH) is None
    assert grounding._find_token_exact("Alpha 12.5 30", SYNTH) is None
    assert grounding._find_token_exact("Alpha 30.1 12.5", SYNTH) is None


def test_any_whitespace_between_tokens_matches_and_offsets_point_into_the_original_text():
    m = grounding._find_token_exact("Beta (avg) 7 8 9", SYNTH)
    assert m is not None
    assert SYNTH[m.start() : m.end()] == "Beta (avg)\n7\n8\n9"


def test_regex_metacharacters_in_quotes_are_literal():
    assert grounding._find_token_exact("Beta (avg) 7 8 9", "x Beta (avg) 7 8 9 y") is not None
    assert grounding._find_token_exact("B.ta (avg) 7 8 9", "x Beta (avg) 7 8 9 y") is None


# --- fixed cases on the ReAct paper ---

REACT_PASS = [
    "Act 25.7 58.9",
    "ReAct 27.4 60.9",
    "ReAct (best of 6) 92 58 96 86 78 41 71",
    "ReAct-IM (best of 6) 62 68 87 57 39 33 53",
]
REACT_FAIL = [
    "ReAct (best of 6) 62 68 87 57 39 33 53",
    "ReAct-IM (best of 6) 92 58 96 86 78 41 71",
    "ReAct (avg) 55 59 60 55 23 24 48",
    "ReAct-IM (avg) 65 39 83 76 55 24 57",
    "Act 27.4 60.9",
    "Act 58.9 25.7",
    "ReAct 60.9 27.4",
    "31 77 4 90 12 55 6",  # a random number string
    "ReAct (best of 6) 92 58 96 86 78 41 72",  # a real row, one digit changed
]


@pytest.mark.parametrize("quote", REACT_PASS)
def test_genuine_table_rows_pass_the_gate_with_score_100(quote):
    text = paper_text("react")
    final, passed = ground(quote, text)
    assert passed is True
    assert final.gate == "token_exact" and final.fuzz_score == 100.0
    assert final.grounding_status == GroundingStatus.PASS  # stubbed audit ran


@pytest.mark.parametrize("quote", REACT_FAIL)
def test_wrong_rows_fail_the_gate(quote):
    text = paper_text("react")
    final, passed = ground(quote, text)
    assert passed is False
    assert final.gate == "token_exact"
    assert final.grounding_status == GroundingStatus.FAIL and final.stance is None
    assert final.fuzz_score is not None and final.fuzz_score < 100.0  # the fuzzy score is kept
    assert quote not in [c["quote"] for c in _AUDIT_CALLS]  # never reached the audit


def test_old_gate_would_have_passed_a_wrong_row_once_whitespace_is_collapsed():
    """Documents why the fuzzy gate is not enough: collapsing whitespace lifts both
    genuine and wrong rows over the threshold."""
    text = paper_text("react")
    collapsed = " ".join(text.split())
    for quote in ("Act 27.4 60.9", "ReAct-IM (best of 6) 92 58 96 86 78 41 71"):
        assert fuzz.partial_ratio(quote, collapsed) >= grounding.RAPIDFUZZ_THRESHOLD


def test_token_exact_context_is_taken_at_the_exact_offsets_with_the_usual_window():
    text = paper_text("react")
    quote = "ReAct (best of 6) 92 58 96 86 78 41 71"
    ground(quote, text)
    m = grounding._find_token_exact(quote, text)
    expected = grounding._extract_span_context(text, m.start(), m.end())
    [call] = _AUDIT_CALLS
    assert call["context"] == expected
    assert quote.split()[0] in call["context"] and "92" in call["context"]
    assert grounding.MIN_CONTEXT_CHARS <= len(call["context"]) <= grounding.MAX_CONTEXT_CHARS


# --- prose quotes still use the fuzzy gate ---

PROSE_PASS = [
    "Table 1: PaLM-540B prompting results on",  # caption -> fuzzy
    "search reformulation (“maybe I can search/look up x instead”), and synthesize the final answer",
]
PROSE_NEAR_MISS = [
    # one word changed: whatever the fuzzy gate says is what it said before
    "Table 1: PaLM-540B prompting outcomes on",
]
PROSE_FAIL = [
    "Zebras were observed to outperform every transformer variant in the zoological appendix.",
]


@pytest.mark.parametrize("quote", PROSE_PASS + PROSE_NEAR_MISS + PROSE_FAIL)
def test_prose_quotes_keep_the_fuzzy_gate_unchanged(quote):
    text = paper_text("react")
    assert grounding.is_table_row_like(quote) is False
    expected_score = fuzz.partial_ratio(quote, text)
    final, passed = ground(quote, text)
    assert final.gate == "fuzzy"
    assert passed is (expected_score >= grounding.RAPIDFUZZ_THRESHOLD)
    assert final.fuzz_score == expected_score  # never overwritten with 100.0 for prose


def test_prose_pass_and_fail_expectations_hold_on_the_react_paper():
    text = paper_text("react")
    for quote in PROSE_PASS:
        assert ground(quote, text)[1] is True, quote
    for quote in PROSE_FAIL:
        assert ground(quote, text)[1] is False, quote


# --- property tests over all three PDFs ---

_NUM = re.compile(r"\d")
_LET = re.compile(r"[A-Za-z]")


def _is_num(tok: str) -> bool:
    t = tok.strip("()[]{},.;:%")
    return bool(t) and bool(_NUM.search(t)) and not _LET.search(t)


def _sample_windows(tokens: list[str], rng: random.Random, n: int) -> list[list[str]]:
    windows: list[list[str]] = []
    attempts = 0
    while len(windows) < n and attempts < n * 400:
        attempts += 1
        length = rng.randint(3, 10)
        start = rng.randrange(0, len(tokens) - length)
        window = tokens[start : start + length]
        if grounding.is_table_row_like(" ".join(window)):
            windows.append(window)
    return windows


@pytest.mark.parametrize("name", list(PDFS))
def test_property_every_numeric_window_passes_and_mutations_fail(name):
    text = paper_text(name)
    tokens = text.split()
    rng = random.Random(f"{SEED}-{name}")
    windows = _sample_windows(tokens, rng, WINDOWS_PER_PAPER)
    assert len(windows) == WINDOWS_PER_PAPER, "paper has too few numeric windows to sample"

    label_pool = sorted({t for t in tokens if _LET.search(t) and len(t) > 1})
    counts = {
        "sampled": len(windows),
        "windows_passed": 0,
        "perm_tested": 0,
        "perm_skipped_no_distinct_permutation": 0,
        "perm_skipped_mutant_in_paper": 0,
        "label_tested": 0,
        "label_skipped_no_label_token": 0,
        "label_skipped_mutant_in_paper": 0,
        "end_to_end_checked": 0,
    }

    def appears(tok_list: list[str]) -> bool:
        return grounding._find_token_exact(" ".join(tok_list), text) is not None

    for i, window in enumerate(windows):
        quote = " ".join(window)
        assert appears(window), f"[{name}] genuine window failed the token gate: {quote!r}"
        counts["windows_passed"] += 1
        if i < END_TO_END_PER_PAPER:
            final, passed = ground(quote, text)
            assert passed and final.fuzz_score == 100.0 and final.gate == "token_exact", quote
            counts["end_to_end_checked"] += 1

        # (a) permute the numeric tokens inside the window
        num_idx = [k for k, t in enumerate(window) if _is_num(t)]
        values = [window[k] for k in num_idx]
        permuted = None
        if len(set(values)) >= 2:
            for _ in range(20):
                shuffled = values[:]
                rng.shuffle(shuffled)
                if shuffled != values:
                    permuted = window[:]
                    for k, v in zip(num_idx, shuffled):
                        permuted[k] = v
                    break
        if permuted is None:
            counts["perm_skipped_no_distinct_permutation"] += 1
        elif appears(permuted):
            counts["perm_skipped_mutant_in_paper"] += 1
        else:
            counts["perm_tested"] += 1
            if i < END_TO_END_PER_PAPER and grounding.is_table_row_like(" ".join(permuted)):
                assert ground(" ".join(permuted), text)[1] is False, permuted

        # (b) replace the first non-numeric token with a different label from the same paper
        first_label = next((k for k, t in enumerate(window) if not _is_num(t)), None)
        if first_label is None:
            counts["label_skipped_no_label_token"] += 1
        else:
            replacement = rng.choice(label_pool)
            while replacement == window[first_label]:
                replacement = rng.choice(label_pool)
            relabelled = window[:]
            relabelled[first_label] = replacement
            if appears(relabelled):
                counts["label_skipped_mutant_in_paper"] += 1
            else:
                counts["label_tested"] += 1
                if i < END_TO_END_PER_PAPER and grounding.is_table_row_like(" ".join(relabelled)):
                    assert ground(" ".join(relabelled), text)[1] is False, relabelled

    print(f"\n[property:{name}] {counts}")
    assert counts["windows_passed"] == WINDOWS_PER_PAPER
    assert counts["perm_tested"] > 0 and counts["label_tested"] > 0
