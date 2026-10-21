"""Unit tests for eval/replay_exp3.py's Experiment 3 amendment 1 changes:
the mkdir-ordering crash fix, per-call NDJSON records, and
--pass1-from-fixture. No LLM calls, no DB, no real PDFs.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from eval import replay_exp3
from extraction import engine


def _fake_response(prompt_tokens=10, output_tokens=5, thought_tokens=0, total_tokens=15, finish_reason="STOP"):
    usage = SimpleNamespace(
        prompt_token_count=prompt_tokens,
        candidates_token_count=output_tokens,
        thoughts_token_count=thought_tokens,
        total_token_count=total_tokens,
    )
    candidate = SimpleNamespace(finish_reason=SimpleNamespace(value=finish_reason))
    return SimpleNamespace(text="{}", usage_metadata=usage, candidates=[candidate])


def test_aborted_run_does_not_crash_and_summary_exists(tmp_path, monkeypatch):
    """--max-inr 0 aborts before the first paper (0.0 >= 0.0), so no paper
    is ever written and out_dir would never have existed before the
    mkdir-at-top fix - _print_summary must not crash on this."""
    monkeypatch.setattr(replay_exp3, "OUTPUT_ROOT", tmp_path)

    out_dir, records = asyncio.run(replay_exp3._run_once(
        paper_ids=["paperX"], run_id="aborted_run", dry_run=False, max_inr=0.0,
    ))

    assert records == []
    assert out_dir.exists()

    replay_exp3._print_summary(out_dir, records)  # must not raise

    summary_path = out_dir / "_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["calls"] == 0


def test_ndjson_written_per_call_before_run_ends(tmp_path, monkeypatch):
    """A call's record must already be on disk right after that call
    completes, not only once the whole run finishes - so an abort or crash
    partway through a run (like the pilot 1 crash) doesn't lose it."""
    out_dir = tmp_path / "run1"
    out_dir.mkdir()
    instrumentation = replay_exp3._Instrumentation(out_dir)

    async def fake_original(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        return _fake_response(), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_original)

    with instrumentation:
        instrumentation.set_context("paperX", "pass2")
        asyncio.run(engine._generate_with_fallback(None, None, None, "chat-1", "m", "fb"))

        # Still inside the `with` block - the run has not ended - the record
        # must already be on disk.
        ndjson_path = out_dir / "_calls.ndjson"
        assert ndjson_path.exists()
        lines = ndjson_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["paper_id"] == "paperX"
        assert record["call_kind"] == "pass2"
        assert record["prompt_tokens"] == 10


def test_ndjson_write_failure_does_not_drop_record_or_crash(tmp_path, monkeypatch, capsys):
    """AG review fix: a disk-write problem on the NDJSON append must never
    lose a paid response or raise - the in-memory record (self.records,
    used by _print_summary at the end of the run) is the backstop."""
    out_dir = tmp_path / "nonexistent_subdir"  # never created -> open("a") raises FileNotFoundError
    instrumentation = replay_exp3._Instrumentation(out_dir)

    async def fake_original(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        return _fake_response(), model_name

    monkeypatch.setattr(engine, "_generate_with_fallback", fake_original)

    with instrumentation:
        instrumentation.set_context("paperX", "pass2")
        response, used_model = asyncio.run(
            engine._generate_with_fallback(None, None, None, "chat-1", "m", "fb")
        )

    assert used_model == "m"  # the paid response is still returned, not dropped
    assert len(instrumentation.records) == 1  # kept in memory despite the write failure
    assert "WARNING" in capsys.readouterr().out


def test_pass2_thinking_level_flag_restricts_to_known_choices():
    """AG review fix: --pass2-thinking-level must only accept
    config.PASS2_THINKING_LEVELS, not an arbitrary string."""
    parser = replay_exp3._build_parser()

    args = parser.parse_args(["--pass2-thinking-level", "low"])
    assert args.pass2_thinking_level == "low"

    with pytest.raises(SystemExit):
        parser.parse_args(["--pass2-thinking-level", "bogus"])


def test_pass1_claims_from_fixture_matches_fixture_two_key_shape():
    run1_fixture = {
        "claims": [
            {"index": 0, "label": "supported", "claim_text_verbatim": "v0", "claim_summary": "s0",
             "missing": False, "grounding_status": "Pass", "evidence_spans": []},
            {"index": 1, "label": "not_supported", "claim_text_verbatim": "v1", "claim_summary": "s1",
             "missing": True, "grounding_status": "Fail", "evidence_spans": []},
        ]
    }

    result = replay_exp3._pass1_claims_from_fixture(run1_fixture)

    assert result == [
        {"claim_text_verbatim": "v0", "claim_summary": "s0"},
        {"claim_text_verbatim": "v1", "claim_summary": "s1"},
    ]


def test_pass1_from_fixture_skips_pass1_call_in_run_once(tmp_path, monkeypatch):
    """--pass1-from-fixture must make zero pass-1 LLM calls and the written
    pass1 output must equal the fixture's claims reduced to the two-key
    shape."""
    monkeypatch.setattr(replay_exp3, "OUTPUT_ROOT", tmp_path)

    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    run1_fixture = {
        "header": {"filename": "paperX.pdf", "extraction_run_id": "run-1-id"},
        "claims": [
            {"index": 0, "label": "supported", "claim_text_verbatim": "v0", "claim_summary": "s0",
             "missing": False, "grounding_status": "Pass", "evidence_spans": []},
        ],
    }
    (fixture_dir / "paperX.json").write_text(json.dumps(run1_fixture), encoding="utf-8")
    monkeypatch.setattr(replay_exp3, "FIXTURE_DIR", fixture_dir)

    async def fake_hash_check_and_load_text(paper_id, fixture_header):
        return "the paper text, containing v0 somewhere."

    monkeypatch.setattr(replay_exp3, "_hash_check_and_load_text", fake_hash_check_and_load_text)
    monkeypatch.setattr(replay_exp3, "make_windows", lambda text: [])  # no pass-2 windows to call

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("pass-1 call must not be made when pass1_from_fixture=True")

    monkeypatch.setattr(replay_exp3, "_extract_pass1", fail_if_called)

    out_dir, records = asyncio.run(replay_exp3._run_once(
        paper_ids=["paperX"], run_id="fixture_run", dry_run=False, max_inr=100.0,
        pass1_from_fixture=True,
    ))

    assert records == []  # no pass-1 call, no pass-2 windows -> zero LLM calls total
    written = json.loads((out_dir / "paperX_pass1.json").read_text(encoding="utf-8"))
    assert written["claims"] == [{"claim_text_verbatim": "v0", "claim_summary": "s0"}]
