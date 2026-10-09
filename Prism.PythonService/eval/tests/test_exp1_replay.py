"""Offline tests for the Experiment 1 replay helpers (no LLM calls, no PDFs)."""
import pytest

from eval import exp1_replay
from eval.exp1_common import parse_verdict


def test_parse_verdict_takes_last_line_and_handles_markdown():
    assert parse_verdict("text\nVERDICT: supported\n") == "supported"
    assert parse_verdict("**VERDICT: partially_supported** - some prose\n") == "partially_supported"
    assert parse_verdict("VERDICT: not_supported — reason\n") == "not_supported"
    assert parse_verdict("VERDICT: supported\nmore\nVERDICT: not_supported\n") == "not_supported"


def test_parse_verdict_unparsed():
    assert parse_verdict("no verdict here") is None
    assert parse_verdict("") is None


def test_cost_inr_uses_price_constants():
    # 1M input + 1M output tokens = $0.75 + $3.75 = $4.50 = INR 427.5 at 95
    assert exp1_replay.cost_inr(1_000_000, 1_000_000, 95.0) == pytest.approx(427.5)


def test_tally_stops_at_ninety_percent_of_cap():
    t = exp1_replay.Tally(cap_inr=100.0, inr_per_usd=95.0)
    assert not t.over_budget()
    # INR 89 of spend: 89 / 95 = $0.9368 -> all as output tokens at $3.75/1M
    t.add({"input_tokens": 0, "output_tokens": int(0.9368 / 3.75 * 1_000_000), "thinking_tokens": 0})
    assert t.inr < 90 and not t.over_budget()
    t.add({"input_tokens": 0, "output_tokens": 20_000, "thinking_tokens": 0})
    assert t.over_budget() and t.stopped


def test_execute_requires_cap(capsys):
    with pytest.raises(SystemExit):
        exp1_replay.main(["--execute"])


# ----------------------------------------------------- pilot-round behaviours
import asyncio
from types import SimpleNamespace


def _claim(i=0):
    return {"index": i, "fingerprint": "f" * 64, "claim_text_verbatim": "A claim.", "claim_summary": "s", "label": "supported"}


def test_primary_only_generate_never_falls_back(monkeypatch):
    from extraction import engine

    calls = {"fallback": 0}

    class FakeModels:
        async def generate_content(self, **kw):
            calls["fallback"] += 1

    client = SimpleNamespace(aio=SimpleNamespace(models=FakeModels()))

    async def boom(*a, **k):
        raise TimeoutError("transport")

    monkeypatch.setattr(engine, "_call_gemini", boom)
    with pytest.raises(TimeoutError):
        asyncio.run(exp1_replay.primary_only_generate(client, [], None, "c", "primary-model", "fallback-model"))
    assert calls["fallback"] == 0


def test_scope_failure_is_recorded_as_error_without_legacy_fallback(monkeypatch):
    from extraction import engine

    freetext_log_subdirs = []

    async def failing_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        raise RuntimeError("scope blew up")

    async def spy_freetext(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        freetext_log_subdirs.append(log_subdir)
        return "VERDICT: supported"

    monkeypatch.setattr(engine, "_call_gemini_structured", failing_structured)
    monkeypatch.setattr(engine, "_call_gemini_freetext", spy_freetext)
    rec = asyncio.run(exp1_replay.run_one_claim(
        "A", 1, "scoped", "arxiv-x", "paper", _claim(), ["ROW-1"], {"ROW-1": "supported"},
        {"inventory_hash": "h", "items": [{"id": "I1", "name": "n", "kind": "model", "group": None}]},
    ))
    assert rec["error_kind"] == "scope" and rec["final"] == "error"
    assert freetext_log_subdirs == []  # no legacy audit, no scoped audit either


def _rec(set_id, row, frozen, final, golden="supported", **kw):
    return {"set": set_id, "run": 1, "mode": "scoped", "golden_rows": [row], "golden_labels": {row: golden},
            "fixture_label": frozen, "final": final, "lowered": kw.get("lowered", False), "verdict": final, **kw}


def test_evaluate_pilot_pass_and_fail():
    labels = {}
    negatives = {"REACT-M14", "REFLEX-M09", "COT-M08", "COT-M02"}
    recs = [
        _rec("A", "REACT-M14", "supported", "partially_supported", lowered=True),
        _rec("A", "REFLEX-M09", "supported", "not_supported"),
        _rec("A", "REFLEX-M02", "supported", "supported"),
        _rec("B", "COT-M04", "supported", "supported"),
        _rec("B", "COT-M08", "supported", "supported"),
        _rec("B", "COT-M02", "partially_supported", "partially_supported"),
    ]
    ev = exp1_replay.evaluate_pilot(recs, labels, negatives)
    assert ev["P1"]["value"] == 2 and ev["P1"]["pass"]
    assert ev["P2"]["pass"] and ev["P3"]["value"] == 0 and ev["P4"]["pass"]
    # one baseline-refused row flipping to supported is allowed, two are not
    recs.append(_rec("A", "COT-M08", "partially_supported", "supported"))
    recs.append(_rec("B", "REFLEX-M09", "partially_supported", "supported"))
    ev = exp1_replay.evaluate_pilot(recs, labels, negatives)
    assert ev["P3"]["value"] == 2 and not ev["P3"]["pass"]
    # P2 fails when a must-stay-supported row is lowered; P4 fails with >2 errors
    recs.append(_rec("A", "REACT-M10", "supported", "partially_supported"))
    for n in range(3):
        recs.append({**_rec("A", f"X{n}", "supported", "error"), "error": "e", "error_kind": "model"})
    ev = exp1_replay.evaluate_pilot(recs, labels, negatives)
    assert not ev["P2"]["pass"] and not ev["P4"]["pass"] and ev["P4"]["value"] == 3


def test_baseline_frozen_is_scoped_only(capsys):
    with pytest.raises(SystemExit):
        exp1_replay.main(["--baseline", "frozen", "--mode", "legacy"])
    exp1_replay.main(["--baseline", "frozen", "--runs", "1"])
    out = capsys.readouterr().out
    assert "scoped audit" in out and "legacy audit" not in out and "(no calls were made)" in out
