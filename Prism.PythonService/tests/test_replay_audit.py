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
