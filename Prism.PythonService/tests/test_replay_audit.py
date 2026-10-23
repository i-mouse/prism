"""Unit tests for eval/replay_audit.py's zero-LLM-call paths and the
_generate_with_fallback instrumentation's finally-restore guarantee.

These tests never touch Postgres or the real PDFs - they exercise the
in-process logic only (target loading, instrumentation lifecycle).
"""
import json

import pytest

from eval import replay_audit
from extraction import engine
from extraction.schemas import ClaimFinal, ClaimLabel, EvidenceSpanFinal, GroundingStatus


def test_load_targets_from_claims_file(tmp_path, monkeypatch):
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / "paperA.json").write_text(json.dumps({
        "header": {}, "matches": [],
        "claims": [
            {"index": 0, "claim_text_verbatim": "c0", "claim_summary": "s0"},
            {"index": 1, "claim_text_verbatim": "c1", "claim_summary": "s1"},
            {"index": 2, "claim_text_verbatim": "c2", "claim_summary": "s2"},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)

    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps([{"paper_id": "paperA", "claim_index": 2}]), encoding="utf-8")

    targets = replay_audit._load_targets(claims_path, None)

    assert len(targets) == 1
    assert targets[0].paper_id == "paperA"
    assert targets[0].claim_index == 2
    assert targets[0].claim_text_verbatim == "c2"


def test_load_targets_without_claims_file_takes_every_claim(tmp_path, monkeypatch):
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / "paperA.json").write_text(json.dumps({
        "header": {}, "matches": [],
        "claims": [
            {"index": 0, "claim_text_verbatim": "c0", "claim_summary": "s0"},
            {"index": 1, "claim_text_verbatim": "c1", "claim_summary": "s1"},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)

    targets = replay_audit._load_targets(None, None)

    assert {t.claim_index for t in targets} == {0, 1}


def test_estimate_makes_zero_llm_calls(tmp_path, monkeypatch, capsys):
    """--estimate must never construct a Gemini client."""

    def _fail_if_constructed():
        raise AssertionError("genai.Client must not be constructed under --estimate")

    monkeypatch.setattr(engine, "_build_client", _fail_if_constructed)

    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / "paperA.json").write_text(json.dumps({
        "header": {"filename": "nonexistent.pdf"}, "matches": [],
        "claims": [{"index": 0, "claim_text_verbatim": "c0", "claim_summary": "s0"}],
    }), encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "PDF_DIR", tmp_path)  # pdf won't exist -> fallback length used

    targets = replay_audit._load_targets(None, None)
    replay_audit._print_estimate(targets, "high", 1)

    out = capsys.readouterr().out
    assert "estimated cost" in out


def test_instrumentation_restores_original_on_exception():
    original = engine._generate_with_fallback

    with pytest.raises(RuntimeError):
        with replay_audit._Instrumentation() as instrumentation:
            instrumentation.set_context("audit", "paperA", 0, "high")
            assert engine._generate_with_fallback is not original
            raise RuntimeError("boom")

    assert engine._generate_with_fallback is original


def test_claim_final_to_fixture_dict_preserves_requested_index():
    claim_final = ClaimFinal(
        claim_text_verbatim="verbatim", claim_summary="summary", label=ClaimLabel.PARTIALLY_SUPPORTED,
        evidence_spans=[
            EvidenceSpanFinal(source_text="quote", source_section="Section 1",
                               grounding_status=GroundingStatus.PASS, stance="supports"),
        ],
        grounding_status=GroundingStatus.PASS, missing=False, reason="1 pass",
    )

    out = replay_audit._claim_final_to_fixture_dict(claim_final, index=33)

    assert out["index"] == 33
    assert out["label"] == "partially_supported"
    assert out["missing"] is False
    assert out["evidence_spans"] == [
        {"source_text": "quote", "source_section": "Section 1", "grounding_status": "Pass", "stance": "supports"}
    ]


def test_instrumentation_restores_original_on_success():
    original = engine._generate_with_fallback

    with replay_audit._Instrumentation() as instrumentation:
        assert engine._generate_with_fallback is not original

    assert engine._generate_with_fallback is original


def _call_record(model_used="gemini-3.6-flash", prompt=1000, output=100, thought=50, cached=0):
    return replay_audit.CallRecord(
        stage="audit", paper_id="p", claim_index=0, thinking_level="high", model_used=model_used,
        prompt_tokens=prompt, output_tokens=output, thought_tokens=thought,
        total_tokens=prompt + output + thought, latency_s=1.0, cached_tokens=cached,
    )


def _grounding_usage(model="openai/gpt-oss-20b", prompt=500, output=40, total=540, cached=0, thought=10):
    return {
        "prompt_tokens": prompt, "output_tokens": output, "thought_tokens": thought, "total_tokens": total,
        "cached_tokens": cached, "model": model,
    }


def test_summary_includes_unpriced_grounding_line_and_label(tmp_path, capsys):
    replay_audit._print_summary(
        tmp_path, [_call_record()], [_grounding_usage(), _grounding_usage(model="gemini-3.1-flash-lite")],
    )

    out = capsys.readouterr().out
    assert "grounding openai/gpt-oss-20b: 1 calls" in out
    assert "UNPRICED grounding models" in out
    assert "gemini-3.1-flash-lite" in out
    assert "(excl. unpriced grounding)" in out

    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    by_model = summary["grounding"]["by_model"]
    assert by_model["openai/gpt-oss-20b"]["usd"] == "unpriced"
    assert by_model["openai/gpt-oss-20b"]["prompt_tokens"] == 500
    assert summary["grounding"]["unpriced_models"] == ["gemini-3.1-flash-lite", "openai/gpt-oss-20b"]
    assert summary["total_cost_excludes_unpriced_grounding"] is True


def test_summary_priced_grounding_has_usd_and_no_unpriced_label(tmp_path, capsys):
    usage = _grounding_usage(model="gemini-3.6-flash", prompt=1_000_000, output=0, total=1_000_000, cached=400_000, thought=0)
    replay_audit._print_summary(tmp_path, [_call_record()], [usage])

    out = capsys.readouterr().out
    assert "UNPRICED" not in out
    assert "excl. unpriced grounding" not in out

    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    usd = summary["grounding"]["by_model"]["gemini-3.6-flash"]["usd"]
    assert usd == round(0.6 * 0.75 + 0.4 * 0.075, 4)  # cached billed once, not twice
    assert summary["total_cost_excludes_unpriced_grounding"] is False


def test_summary_grounding_thought_tokens_are_never_billed(tmp_path):
    """thought_tokens is a sub-count of output_tokens for LiteLLM, so a priced
    model's grounding USD must equal the cost of output_tokens alone."""
    usage = _grounding_usage(model="gemini-3.6-flash", prompt=0, output=1_000_000, total=1_000_000, thought=900_000)
    replay_audit._print_summary(tmp_path, [_call_record()], [usage])

    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert summary["grounding"]["by_model"]["gemini-3.6-flash"]["usd"] == 3.75


def test_summary_groups_missing_model_as_unknown(tmp_path):
    replay_audit._print_summary(tmp_path, [_call_record()], [_grounding_usage(model=None)])

    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert list(summary["grounding"]["by_model"]) == ["unknown"]
    assert summary["grounding"]["by_model"]["unknown"]["usd"] == "unpriced"


def test_summary_without_grounding_records_reports_zero_calls(tmp_path, capsys):
    replay_audit._print_summary(tmp_path, [_call_record()])
    assert "grounding: 0 LLM calls recorded" in capsys.readouterr().out


def test_summary_gemini_cost_is_cached_aware_and_flags_fallback_models(tmp_path, capsys):
    records = [_call_record(prompt=1_000_000, output=0, thought=0, cached=400_000),
               _call_record(model_used="gemini-3.1-flash-lite", prompt=0, output=0, thought=0)]
    replay_audit._print_summary(tmp_path, records)

    assert "WARNING" in capsys.readouterr().out
    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert summary["cost_usd"] == round(0.6 * 0.75 + 0.4 * 0.075, 4)
    assert summary["total_cached_tokens"] == 400_000
    assert summary["gemini_calls_not_priced_at_own_model_rate"] == {"gemini-3.1-flash-lite": 1}


def test_instrumentation_sets_and_restores_grounding_observer():
    from extraction import grounding

    original = grounding._usage_observer
    with replay_audit._Instrumentation() as instrumentation:
        assert grounding._usage_observer is not original
        grounding._usage_observer({"model": "m", "prompt_tokens": 1})
        assert instrumentation.grounding_records == [{"model": "m", "prompt_tokens": 1}]
        assert instrumentation.records == []  # grounding never pollutes the Gemini audit/structure pairing
    assert grounding._usage_observer is original


def test_instrumentation_restores_grounding_observer_on_exception():
    from extraction import grounding

    original = grounding._usage_observer
    with pytest.raises(RuntimeError):
        with replay_audit._Instrumentation():
            raise RuntimeError("boom")
    assert grounding._usage_observer is original
