"""Unit tests for eval/replay_audit.py's zero-LLM-call paths and the
_generate_with_fallback instrumentation's finally-restore guarantee.

These tests never touch Postgres or the real PDFs - they exercise the
in-process logic only (target loading, instrumentation lifecycle, the
--max-inr cap, cached paper-text loading).
"""
import argparse
import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

from eval import replay_audit
from extraction import engine, grounding
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
    # No cache dir exists: --estimate must not read paper text at all.
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", tmp_path / "no_cache")

    targets = replay_audit._load_targets(None, None)
    replay_audit._print_estimate(targets, "high", 1)

    out = capsys.readouterr().out
    assert "estimated cost" in out
    assert "suggested --max-inr (1.3x estimate): " in out


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
        tmp_path, [_call_record()], [_grounding_usage(model="acme/mystery-1"), _grounding_usage(model="acme/mystery-2")],
    )

    out = capsys.readouterr().out
    assert "grounding acme/mystery-1: 1 calls" in out
    assert "UNPRICED grounding models" in out
    assert "(excl. unpriced grounding)" in out

    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    by_model = summary["grounding"]["by_model"]
    assert by_model["acme/mystery-1"]["usd"] == "unpriced"
    assert by_model["acme/mystery-1"]["prompt_tokens"] == 500
    assert summary["grounding"]["unpriced_models"] == ["acme/mystery-1", "acme/mystery-2"]
    assert summary["total_cost_excludes_unpriced_grounding"] is True


def test_summary_prices_groq_and_flash_lite_grounding_from_the_table(tmp_path, capsys):
    usages = [
        _grounding_usage(model="openai/gpt-oss-20b", prompt=1_000_000, output=1_000_000, total=2_000_000, cached=0, thought=0),
        _grounding_usage(model="gemini-3.1-flash-lite", prompt=1_000_000, output=1_000_000, total=2_000_000, cached=0, thought=0),
    ]
    replay_audit._print_summary(tmp_path, [_call_record()], usages)

    out = capsys.readouterr().out
    assert "UNPRICED" not in out
    assert "excl. unpriced grounding" not in out
    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    by_model = summary["grounding"]["by_model"]
    assert by_model["openai/gpt-oss-20b"]["usd"] == round(0.075 + 0.30, 4)
    assert by_model["gemini-3.1-flash-lite"]["usd"] == round(0.25 + 1.50, 4)
    assert summary["total_cost_excludes_unpriced_grounding"] is False


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


def test_summary_gemini_cost_is_cached_aware_and_counts_unknown_model_calls(tmp_path, capsys):
    records = [_call_record(prompt=1_000_000, output=0, thought=0, cached=400_000),
               _call_record(model_used="acme/mystery-1", prompt=0, output=0, thought=0)]
    replay_audit._print_summary(tmp_path, records)

    assert "WARNING" in capsys.readouterr().out
    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert summary["cost_usd"] == round(0.6 * 0.75 + 0.4 * 0.075, 4)
    assert summary["total_cached_tokens"] == 400_000
    assert summary["gemini_calls_not_priced_at_own_model_rate"] == {"acme/mystery-1": 1}


def test_flash_lite_fallback_call_is_priced_at_flash_lite_rates(tmp_path, capsys):
    records = [_call_record(model_used="gemini-3.1-flash-lite", prompt=1_000_000, output=1_000_000, thought=0)]
    replay_audit._print_summary(tmp_path, records)

    assert "WARNING" not in capsys.readouterr().out
    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert summary["cost_usd"] == round(0.25 + 1.50, 4)  # not 0.75 + 3.75
    assert summary["gemini_calls_not_priced_at_own_model_rate"] == {}


def test_record_with_missing_model_is_priced_at_flash_rates_and_counted(tmp_path):
    records = [_call_record(model_used=None, prompt=1_000_000, output=1_000_000, thought=0)]
    replay_audit._print_summary(tmp_path, records)

    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert summary["cost_usd"] == round(0.75 + 3.75, 4)
    assert summary["gemini_calls_not_priced_at_own_model_rate"] == {"unknown": 1}


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


# --- --max-inr cap ----------------------------------------------------------

_PAPER = "arxiv-9999.00001v1"


def _fake_gemini_response(prompt=100_000):
    """100k prompt tokens at gemini-3.6-flash = USD 0.075 = INR 7.5."""
    return SimpleNamespace(usage_metadata=SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=0, thoughts_token_count=0,
        total_token_count=prompt, cached_content_token_count=0, tool_use_prompt_token_count=0,
    ))


def _install_fake_gemini(monkeypatch, model="gemini-3.6-flash"):
    calls: list[str] = []

    async def fake(client, contents, config, chat_id, model_name, fallback_model, correlation_id=None):
        calls.append(chat_id)
        return _fake_gemini_response(), model

    monkeypatch.setattr(engine, "_generate_with_fallback", fake)
    return calls


def _fake_litellm_response(output=1_000_000, model="openai/gpt-oss-20b"):
    """1M output tokens at gpt-oss-20b = USD 0.30 = INR 30."""
    return SimpleNamespace(
        model=model,
        usage=SimpleNamespace(
            prompt_tokens=0, completion_tokens=output, total_tokens=output,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
    )


def test_cap_is_not_swallowed_by_a_retrying_caller_and_blocks_further_calls(monkeypatch):
    calls = _install_fake_gemini(monkeypatch)
    guard = replay_audit._CostGuard(max_inr=10)

    async def retrying_caller():
        for _ in range(3):
            try:
                return await engine._generate_with_fallback(None, [], None, "c", "m", "f")
            except Exception:  # the same shape as engine._call_gemini's retry loop
                continue

    async def run():
        with replay_audit._Instrumentation(guard):
            await retrying_caller()  # INR 7.5, under the cap
            await retrying_caller()  # INR 15, crosses it

    with pytest.raises(replay_audit.CapExceeded):
        asyncio.run(run())
    assert len(calls) == 2  # the crossing call was made once, never retried
    assert guard.cap_hit and guard.overshoot_inr == pytest.approx(5.0)

    async def after_cap():
        with replay_audit._Instrumentation(guard):
            await engine._generate_with_fallback(None, [], None, "c", "m", "f")

    with pytest.raises(replay_audit.CapExceeded):
        asyncio.run(after_cap())
    assert len(calls) == 2  # no new request once the cap has tripped


def test_cap_passes_through_grounding_usage_report_and_retry_loop(monkeypatch):
    guard = replay_audit._CostGuard(max_inr=1)
    requests: list[int] = []

    async def fake_acompletion(**kwargs):
        requests.append(1)
        return _fake_litellm_response()

    monkeypatch.setattr(grounding.litellm, "acompletion", fake_acompletion)

    async def audit():
        return await grounding._call_litellm_audit(
            messages=[], audit_model="m", fallback_model="f", gemini_api_key="k", span_source_section="s",
        )

    async def run_twice():
        with replay_audit._Instrumentation(guard):
            with pytest.raises(replay_audit.CapExceeded):
                await audit()  # through _report_usage and the real retry loop
            with pytest.raises(replay_audit.CapExceeded):
                await audit()  # blocked before any request

    asyncio.run(run_twice())
    assert len(requests) == 1


def test_unpriced_grounding_model_is_charged_at_flash_rates_for_the_cap():
    usd = replay_audit._grounding_record_cost_usd(
        {"model": "acme/mystery-1", "prompt_tokens": 1_000_000, "output_tokens": 0, "cached_tokens": 0},
    )
    assert usd == pytest.approx(0.75)
    assert replay_audit._grounding_record_cost_usd(
        {"model": "openai/gpt-oss-20b", "prompt_tokens": 1_000_000, "output_tokens": 0, "cached_tokens": 0},
    ) == pytest.approx(0.075)


def test_instrumentation_restores_all_patched_entry_points_with_a_guard():
    original_engine = engine._generate_with_fallback
    original_observer = grounding._usage_observer
    original_audit = grounding._call_litellm_audit

    with pytest.raises(RuntimeError):
        with replay_audit._Instrumentation(replay_audit._CostGuard(5)):
            assert grounding._call_litellm_audit is not original_audit
            raise RuntimeError("boom")

    assert engine._generate_with_fallback is original_engine
    assert grounding._usage_observer is original_observer
    assert grounding._call_litellm_audit is original_audit


def _write_run_files(tmp_path, monkeypatch, with_cache=True):
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / f"{_PAPER}.json").write_text(json.dumps({
        "header": {"title": "t"}, "matches": [],
        "claims": [
            {"index": 0, "claim_text_verbatim": "c0", "claim_summary": "s0"},
            {"index": 1, "claim_text_verbatim": "c1", "claim_summary": "s1"},
        ],
    }), encoding="utf-8")
    cache_dir = tmp_path / "raw_text_cache"
    cache_dir.mkdir()
    if with_cache:
        (cache_dir / "9999.00001v1.txt").write_text("fake paper text", encoding="utf-8")
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps([
        {"paper_id": _PAPER, "claim_index": 0}, {"paper_id": _PAPER, "claim_index": 1},
    ]), encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", cache_dir)
    monkeypatch.setattr(replay_audit, "OUTPUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(replay_audit, "get_prompt_version", lambda: replay_audit.EXPECTED_PROMPT_HASH)
    return claims_path


def _install_fake_replay(monkeypatch):
    """Replaces the model-facing parts of a replay with fakes that still go
    through the instrumented engine._generate_with_fallback."""

    async def fake_replay_claim(target, paper_text, level, instrumentation):
        assert paper_text == "fake paper text"
        await engine._generate_with_fallback(None, [], None, f"replay-{target.paper_id}", "m", "f")
        return SimpleNamespace(claim_index=target.claim_index)

    async def fake_ground(extraction, paper_text, chat_id, **kwargs):
        return [
            ClaimFinal(
                claim_text_verbatim="v", claim_summary="s", label=ClaimLabel.PARTIALLY_SUPPORTED,
                evidence_spans=[], grounding_status=GroundingStatus.PASS, missing=False, reason="r",
            )
            for _ in extraction
        ]

    monkeypatch.setattr(replay_audit, "_replay_claim", fake_replay_claim)
    monkeypatch.setattr(replay_audit, "ClaimsExtractionResponse", lambda claims: claims)
    monkeypatch.setattr(grounding, "ground_extraction", fake_ground)


def _args(claims_path, max_inr=None, dry_run=False):
    return argparse.Namespace(
        level="high", claims=str(claims_path), papers=None, repeat=1, estimate=False,
        dry_run=dry_run, max_inr=max_inr,
    )


def test_run_that_crosses_the_cap_writes_void_summary_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    claims_path = _write_run_files(tmp_path, monkeypatch)
    calls = _install_fake_gemini(monkeypatch)
    _install_fake_replay(monkeypatch)
    # No Postgres, no main.py: any such import fails the test.
    monkeypatch.setitem(sys.modules, "memory_db", None)
    monkeypatch.setitem(sys.modules, "main", None)

    rc = asyncio.run(replay_audit._main(_args(claims_path, max_inr=10)))

    assert rc == replay_audit.EXIT_CAP_HIT != 0
    assert len(calls) == 2  # claim 0 = INR 7.5, claim 1 crosses at INR 15; nothing after
    summary = json.loads((tmp_path / "out" / "exp1_high_1" / "_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "VOID_CAP_HIT"
    assert summary["cap"]["max_inr"] == 10
    assert summary["cap"]["overshoot_inr"] == pytest.approx(5.0)
    assert summary["cap"]["max_single_call_inr"] == pytest.approx(7.5)
    assert not (tmp_path / "out" / "exp1_high_1" / f"{_PAPER}.json").exists()
    assert "VOID_CAP_HIT" in capsys.readouterr().out


def test_run_under_the_cap_completes(tmp_path, monkeypatch):
    claims_path = _write_run_files(tmp_path, monkeypatch)
    calls = _install_fake_gemini(monkeypatch)
    _install_fake_replay(monkeypatch)
    monkeypatch.setitem(sys.modules, "memory_db", None)
    monkeypatch.setitem(sys.modules, "main", None)

    rc = asyncio.run(replay_audit._main(_args(claims_path, max_inr=100)))

    assert rc == 0
    assert len(calls) == 2
    out_dir = tmp_path / "out" / "exp1_high_1"
    summary = json.loads((out_dir / "_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "OK"
    assert summary["cap"]["overshoot_inr"] == 0
    assert (out_dir / f"{_PAPER}.json").exists()


def test_run_without_a_cap_has_no_cap_block(tmp_path, monkeypatch):
    claims_path = _write_run_files(tmp_path, monkeypatch)
    _install_fake_gemini(monkeypatch)
    _install_fake_replay(monkeypatch)

    assert asyncio.run(replay_audit._main(_args(claims_path))) == 0
    summary = json.loads((tmp_path / "out" / "exp1_high_1" / "_summary.json").read_text(encoding="utf-8"))
    assert "cap" not in summary


def test_cap_stop_cancels_other_grounding_tasks(tmp_path, monkeypatch):
    """gather re-raises the first failure but leaves the sibling span tasks
    running; the cap handler must cancel them."""
    _write_run_files(tmp_path, monkeypatch)
    _install_fake_gemini(monkeypatch)
    _install_fake_replay(monkeypatch)
    finished: list[int] = []

    async def fake_ground(extraction, paper_text, chat_id, **kwargs):
        async def worker(i):
            await asyncio.sleep(0.05 * i)
            grounding._report_usage(_fake_litellm_response())  # INR 30 each, cap is INR 20
            finished.append(i)

        await asyncio.gather(*(worker(i) for i in range(3)))

    monkeypatch.setattr(grounding, "ground_extraction", fake_ground)
    targets = replay_audit._load_targets(None, None)
    guard = replay_audit._CostGuard(max_inr=20)

    async def run():
        result = await replay_audit._run_once(targets, "high", 1, False, {_PAPER: "fake paper text"}, guard)
        await asyncio.sleep(0.2)  # long enough for a surviving stray to report
        return result

    _, _, grounding_records, status = asyncio.run(run())

    assert status == replay_audit.STATUS_VOID_CAP_HIT
    assert len(grounding_records) == 1  # only the first worker's response was ever seen
    assert finished == []


def test_missing_cache_file_aborts_before_any_call(tmp_path, monkeypatch, capsys):
    claims_path = _write_run_files(tmp_path, monkeypatch, with_cache=False)
    calls = _install_fake_gemini(monkeypatch)
    _install_fake_replay(monkeypatch)

    rc = asyncio.run(replay_audit._main(_args(claims_path, max_inr=100)))

    assert rc == 1
    assert calls == []
    out = capsys.readouterr().out
    assert "ABORT" in out and _PAPER in out


def test_dry_run_reports_cache_presence_and_issues_no_call(tmp_path, monkeypatch, capsys):
    claims_path = _write_run_files(tmp_path, monkeypatch, with_cache=False)
    calls = _install_fake_gemini(monkeypatch)

    assert asyncio.run(replay_audit._main(_args(claims_path, dry_run=True))) == 0
    assert calls == []
    assert "MISSING" in capsys.readouterr().out


def test_max_inr_cli_flag():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "high"]).max_inr is None
    assert parser.parse_args(["--level", "high", "--max-inr", "42.5"]).max_inr == 42.5
    with pytest.raises(SystemExit):
        parser.parse_args(["--level", "high", "--max-inr", "0"])


# --- cached paper text ------------------------------------------------------


def test_cache_file_name_drops_one_leading_arxiv_prefix():
    assert replay_audit._cache_file_name("arxiv-2610.10590v1") == "2610.10590v1.txt"
    assert replay_audit._cache_file_name("paperA") == "paperA.txt"
    assert replay_audit._cache_file_name("arxiv-arxiv-1") == "arxiv-1.txt"


def test_load_paper_text_reads_the_mapped_file(tmp_path, monkeypatch):
    fixture_dir = tmp_path / "run1"
    cache_dir = tmp_path / "cache"
    fixture_dir.mkdir()
    cache_dir.mkdir()
    for pid in ("arxiv-2610.10590v1", "paperA"):
        (fixture_dir / f"{pid}.json").write_text("{}", encoding="utf-8")
    (cache_dir / "2610.10590v1.txt").write_text("text one", encoding="utf-8")
    (cache_dir / "paperA.txt").write_text("text two", encoding="utf-8")
    (cache_dir / "arxiv-2610.10590v1.txt").write_text("WRONG: unstripped name", encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", cache_dir)
    monkeypatch.setitem(sys.modules, "memory_db", None)
    monkeypatch.setitem(sys.modules, "main", None)

    assert replay_audit._load_paper_text("arxiv-2610.10590v1") == "text one"
    assert replay_audit._load_paper_text("paperA") == "text two"
    assert replay_audit._load_paper_texts(["paperA"]) == {"paperA": "text two"}


def test_load_paper_text_missing_or_empty_file_names_the_paper_id(tmp_path, monkeypatch):
    fixture_dir = tmp_path / "run1"
    cache_dir = tmp_path / "cache"
    fixture_dir.mkdir()
    cache_dir.mkdir()
    for pid in ("arxiv-1.1v1", "arxiv-2.2v1"):
        (fixture_dir / f"{pid}.json").write_text("{}", encoding="utf-8")
    (cache_dir / "2.2v1.txt").write_text("   \n", encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", cache_dir)

    with pytest.raises(replay_audit.PaperTextError, match="arxiv-1.1v1"):
        replay_audit._load_paper_text("arxiv-1.1v1")
    with pytest.raises(replay_audit.PaperTextError, match="arxiv-2.2v1.*empty"):
        replay_audit._load_paper_text("arxiv-2.2v1")


def test_load_paper_text_rejects_ids_without_a_run1_dev_fixture(tmp_path, monkeypatch):
    fixture_dir = tmp_path / "run1"
    cache_dir = tmp_path / "cache"
    fixture_dir.mkdir()
    cache_dir.mkdir()
    (cache_dir / "heldout-1.txt").write_text("should never be read", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("should never be read", encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", cache_dir)

    for bad in ("heldout-1", "../secret", "a/b", "a\\b", "..", ""):
        with pytest.raises(replay_audit.PaperTextError):
            replay_audit._load_paper_text(bad)


def test_importing_replay_audit_and_the_legacy_loader_does_not_import_memory_db_or_main():
    """The legacy Postgres loader (kept for replay_exp3/replay_clean/replay_extract)
    imports memory_db and main only when called, never at import time."""
    import subprocess

    code = (
        "import sys; import eval.replay_audit, eval.legacy_paper_text; "
        "assert 'memory_db' not in sys.modules and 'main' not in sys.modules, sorted(sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
