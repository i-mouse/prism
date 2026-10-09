"""Offline tests for the scoped auditor (AUDIT_MODE=scoped, Experiment 1). No LLM calls."""
import asyncio
import hashlib
import json

import pytest

from extraction import engine, scoped_audit
from extraction.prompt_loader import (
    build_gemini_messages_for_audit,
    build_messages_for_scope,
    build_messages_for_scoped_audit,
)
from extraction.prompt_version import get_prompt_version
from extraction.schemas import ClaimLabel, ClaimLLM, EvidenceSpanLLM
from extraction.scoped_audit import aggregate, parse_checks
from extraction.scoped_schemas import ClaimScope, InventoryItem, PaperInventory, ScopeItem

PAPER = (
    "Table 2 results.\nButt 0.81 0.88\nFillet 0.77 0.85\n"
    "On lap welds, WeldScan shows no improvement over the baseline and scores lower under the held-out split.\n"
    "Spot welds were left to future work.\n"
)
GROUNDED_QUOTE = "On lap welds, WeldScan shows no improvement over the baseline and scores lower under the held-out split."
UNGROUNDED_QUOTE = "Plug welds degrade sharply when the coolant temperature is varied across the full factory floor."
SCOPE_IDS = ["S1", "S2", "S3"]


def _checks(s1="holds", s2="holds", s3="fails", q3=GROUNDED_QUOTE):
    lines = [f'CHECK S1: {s1} | QUOTE: "Butt 0.81 0.88"' if s1 != "not_reported" else "CHECK S1: not_reported"]
    lines.append(f'CHECK S2: {s2} | QUOTE: "Fillet 0.77 0.85"' if s2 != "not_reported" else "CHECK S2: not_reported")
    lines.append(f'CHECK S3: {s3} | QUOTE: "{q3}"' if s3 != "not_reported" else "CHECK S3: not_reported")
    return "Reasoning.\n\n" + "\n".join(lines) + "\n"


def _agg(verdict, text, scope_ids=SCOPE_IDS):
    return aggregate(verdict, scope_ids, parse_checks(text, scope_ids), PAPER)


# ------------------------------------------------------------------ hashes
def test_legacy_prompt_hash_unchanged():
    assert get_prompt_version() == "cb3272cce551"


def test_scoped_hash_is_separate_and_stable():
    h = scoped_audit.get_scoped_prompt_version()
    assert len(h) == 12 and h != get_prompt_version()
    assert h == scoped_audit.get_scoped_prompt_version()


def test_legacy_audit_messages_snapshot():
    msgs = build_gemini_messages_for_audit("PAPER BODY", "claim text", "claim summary")
    digest = hashlib.sha256(json.dumps(msgs, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    assert digest == "1958a6310e5554dd"  # pinned from the unmodified legacy builder
    assert msgs[1]["content"].startswith("PAPER TEXT:\nPAPER BODY\n\nCLAIM TO AUDIT:\n")


# --------------------------------------------------------------- aggregation
def test_fails_grounded_in_scope_lowers():
    agg = _agg("supported", _checks())
    assert agg.final == "partially_supported" and agg.lowered
    assert agg.trigger_id == "S3" and agg.trigger_quote == GROUNDED_QUOTE


def test_fails_ungrounded_not_lowered():
    agg = _agg("supported", _checks(q3=UNGROUNDED_QUOTE))
    assert agg.final == "supported" and not agg.lowered
    assert agg.dropped_ungrounded == ["S3"]


def test_not_reported_in_scope_not_lowered():
    agg = _agg("supported", _checks(s3="not_reported"))
    assert agg.final == "supported" and not agg.lowered


def test_fails_out_of_scope_not_lowered():
    text = _checks(s3="holds") + f'CHECK S9: fails | QUOTE: "{GROUNDED_QUOTE}"\n'
    agg = _agg("supported", text)
    assert agg.final == "supported" and "unknown_id:S9" in agg.flags


@pytest.mark.parametrize("verdict", ["partially_supported", "not_supported"])
def test_never_raises_or_changes_lower_verdicts(verdict):
    agg = _agg(verdict, _checks(s1="fails", s2="holds", s3="holds"))
    assert agg.final == verdict and not agg.lowered


def test_all_holds_never_raises_a_verdict():
    for verdict in ("not_supported", "partially_supported"):
        agg = _agg(verdict, _checks(s3="holds"))
        assert agg.final == verdict


def test_unparsed_verdict_keeps_model_verdict_and_flags():
    agg = _agg(None, _checks())
    assert agg.final is None and agg.aggregation_skipped and "unparsed_verdict" in agg.flags


def test_no_check_lines_is_parse_failure():
    agg = _agg("supported", "Prose only.\nVERDICT: supported\n")
    assert agg.final == "supported" and agg.aggregation_skipped and "checks_unparsed" in agg.flags


# -------------------------------------------------------------------- parser
def test_missing_check_becomes_not_reported_and_flagged():
    p = parse_checks(f'CHECK S1: holds | QUOTE: "Butt 0.81 0.88"\n', SCOPE_IDS)
    assert p.checks["S2"].status == "not_reported" and p.checks["S3"].status == "not_reported"
    assert "missing_check:S2" in p.flags and "missing_check:S3" in p.flags


def test_unknown_id_ignored_and_flagged():
    p = parse_checks('CHECK S1: holds | QUOTE: "x"\nCHECK S7: fails | QUOTE: "y"\n', ["S1"])
    assert "S7" not in p.checks and "unknown_id:S7" in p.flags


def test_duplicate_id_first_wins_and_flagged():
    p = parse_checks('CHECK S1: holds | QUOTE: "first"\nCHECK S1: fails | QUOTE: "second"\n', ["S1"])
    assert p.checks["S1"].status == "holds" and p.checks["S1"].quote == "first"
    assert "duplicate_id:S1" in p.flags


def test_fails_without_quote_cannot_lower():
    text = "CHECK S1: holds | QUOTE: \"Butt 0.81 0.88\"\nCHECK S2: holds | QUOTE: \"Fillet 0.77 0.85\"\nCHECK S3: fails\n"
    p = parse_checks(text, SCOPE_IDS)
    assert "fails_no_quote:S3" in p.flags
    agg = aggregate("supported", SCOPE_IDS, p, PAPER)
    assert agg.final == "supported" and not agg.lowered


def test_parser_handles_markdown_and_curly_quotes():
    p = parse_checks("**CHECK S1: fails | QUOTE: “The lap result.”**\n", ["S1"])
    assert p.checks["S1"].status == "fails"


# ------------------------------------------------------------- scope messages
def test_scope_messages_contain_no_paper_text():
    inv = [InventoryItem(id="I1", name="WeldScan", kind="model", group=None)]
    msgs = build_messages_for_scope("WeldScan improves recall.", "WeldScan recall", inv)
    joined = "\n".join(m["content"] for m in msgs)
    assert "PAPER TEXT" not in joined and "Table 2 results" not in joined
    audit = build_messages_for_scoped_audit(
        PAPER, "claim", "summary", [ScopeItem(scope_id="S1", inventory_id=None, label="x", kind="task", basis="named", why="w")]
    )
    assert "Table 2 results" in audit[1]["content"] and "FIXED SCOPE LIST" in audit[1]["content"]
    # The model is never told that code may lower its verdict.
    sysmsg = audit[0]["content"].lower()
    for phrase in ("aggregat", "lower your", "lowered", "downgrad", "override"):
        assert phrase not in sysmsg


# ------------------------------------------------------------ pipeline (fakes)
EXTRACTOR = {"claims": [{"claim_text_verbatim": "WeldScan improves recall across weld types.", "claim_summary": "WeldScan recall"}]}


def _install_fakes(monkeypatch, tmp_path, audit_text, structured_label=ClaimLabel.SUPPORTED, counts=None):
    counts = counts if counts is not None else {}
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(engine.settings, "audit_mode", "scoped")

    async def fake_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return EXTRACTOR

    async def fake_free(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        counts["free"] = counts.get("free", 0) + 1
        assert log_subdir == "audit_scoped_raw"
        return audit_text

    async def fake_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        counts[response_schema.__name__] = counts.get(response_schema.__name__, 0) + 1
        user = next(m["content"] for m in messages if m["role"] == "user")
        if response_schema is PaperInventory:
            return PaperInventory(items=[InventoryItem(id="I1", name="WeldScan", kind="model", group=None)])
        if response_schema is ClaimScope:
            assert "Table 2 results" not in user
            return ClaimScope(items=[
                ScopeItem(scope_id=f"X{n}", inventory_id=None, label=l, kind="task", basis="named", why="named in claim")
                for n, l in enumerate(["butt welds", "fillet welds", "lap welds"], 1)
            ])
        return ClaimLLM(
            claim_text_verbatim=EXTRACTOR["claims"][0]["claim_text_verbatim"],
            claim_summary="WeldScan recall",
            label=structured_label,
            evidence_spans=[EvidenceSpanLLM(source_text="Butt 0.81 0.88", source_section="Table 3")],
        )

    monkeypatch.setattr(engine, "_call_gemini_json", fake_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_free)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_structured)
    return counts


def test_scoped_pipeline_lowers_label_and_leaves_spans_untouched(monkeypatch, tmp_path):
    counts = _install_fakes(monkeypatch, tmp_path, _checks() + "\nVERDICT: supported\n")
    res = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c1", correlation_id="r1"))
    claim = res.claims[0]
    assert claim.label == ClaimLabel.PARTIALLY_SUPPORTED
    assert [s.source_text for s in claim.evidence_spans] == ["Butt 0.81 0.88"]  # nothing appended
    assert counts["PaperInventory"] == 1 and counts["ClaimScope"] == 1 and counts["free"] == 1
    log = json.loads(next((tmp_path / "audit_scoped").iterdir()).read_text(encoding="utf-8"))
    assert log["trigger_quote"] == GROUNDED_QUOTE and log["trigger_id"] == "S3"
    assert log["lowered"] and log["model_verdict"] == "supported" and log["final_verdict"] == "partially_supported"
    assert log["inventory_hash"] and log["scoped_prompt_version"] and log["claim_text"]
    assert "Table 2 results" not in json.dumps(log)  # never logs paper text
    assert [s["scope_id"] for s in log["scope"]] == ["S1", "S2", "S3"]  # ids re-issued


def test_scoped_pipeline_ungrounded_not_lowered(monkeypatch, tmp_path):
    _install_fakes(monkeypatch, tmp_path, _checks(q3=UNGROUNDED_QUOTE) + "\nVERDICT: supported\n")
    res = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c1", correlation_id="r1"))
    assert res.claims[0].label == ClaimLabel.SUPPORTED and len(res.claims[0].evidence_spans) == 1


def test_scoped_pipeline_parse_failure_keeps_model_verdict(monkeypatch, tmp_path):
    _install_fakes(monkeypatch, tmp_path, "Prose with no check lines.\nVERDICT: supported\n")
    res = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c1", correlation_id="r1"))
    assert res.claims[0].label == ClaimLabel.SUPPORTED
    log = json.loads(next((tmp_path / "audit_scoped").iterdir()).read_text(encoding="utf-8"))
    assert log["aggregation_skipped"] is True


def test_inventory_cached_by_paper_hash(monkeypatch, tmp_path):
    counts = _install_fakes(monkeypatch, tmp_path, _checks() + "\nVERDICT: supported\n")
    asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c1", correlation_id="r1"))
    asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c2", correlation_id="r2"))
    assert counts["PaperInventory"] == 1  # second run reused the cache
    assert any((tmp_path / "inventory").iterdir())


def test_legacy_mode_makes_no_scoped_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(engine.settings, "audit_mode", "legacy")
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)
    seen = {"free_msgs": None, "structured": []}

    async def fake_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return EXTRACTOR

    async def fake_free(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        assert log_subdir == "audit"
        seen["free_msgs"] = messages
        return "Reasoning.\n\nVERDICT: supported\n\nQUOTE: Butt 0.81 0.88\nSECTION: Table 3\n"

    async def fake_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        seen["structured"].append(response_schema)
        return ClaimLLM(
            claim_text_verbatim="WeldScan improves recall across weld types.", claim_summary="WeldScan recall",
            label=ClaimLabel.SUPPORTED, evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="s")],
        )

    monkeypatch.setattr(engine, "_call_gemini_json", fake_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_free)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_structured)
    res = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c1", correlation_id="r1"))
    assert seen["free_msgs"] == build_gemini_messages_for_audit(
        PAPER, EXTRACTOR["claims"][0]["claim_text_verbatim"], EXTRACTOR["claims"][0]["claim_summary"]
    )
    assert seen["structured"] == [ClaimLLM]
    assert res.claims[0].label == ClaimLabel.SUPPORTED
    assert not (tmp_path / "audit_scoped").exists() and not (tmp_path / "inventory").exists()


def test_audit_mode_defaults_to_legacy():
    from config import PrismSettings

    assert PrismSettings.model_fields["audit_mode"].default == "legacy"
