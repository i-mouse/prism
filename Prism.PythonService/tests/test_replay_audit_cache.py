"""Tests for eval/replay_audit.py's --cache mode: cost accounting (creation,
full-TTL storage, cached audit calls, the --max-inr cap), the stop on the first
cache failure, and the free --estimate --cache output.

No network and no real caches.create: the SDK client is a fake, and nothing
here runs replay_audit against a live model.
"""
import argparse
import asyncio
import json
import re
from types import SimpleNamespace

import pytest
from google.genai import errors

from eval import pricing, replay_audit
from extraction import engine, grounding
from extraction.schemas import ClaimFinal, ClaimLabel, ClaimLLM, EvidenceSpanLLM, GroundingStatus

PAPER = "arxiv-9999.00001v1"
MODEL = "gemini-3.6-flash"
CACHE_NAME = "cachedContents/replay1"
TOKENS = 40_000


def _api_error(code: int) -> errors.APIError:
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": f"boom {code}", "status": "INVALID_ARGUMENT"}})


class _FakeSdk:
    def __init__(self, create_error=None, cached_call_error=None, tokens=TOKENS):
        self.create_error = create_error
        self.cached_call_error = cached_call_error
        self.tokens = tokens
        self.created: list = []
        self.deleted: list[str] = []
        self.calls: list = []
        self.client = SimpleNamespace(aio=SimpleNamespace(
            caches=SimpleNamespace(create=self._create, delete=self._delete),
            models=SimpleNamespace(generate_content=self._generate),
        ))

    async def _create(self, *, model, config):
        if self.create_error is not None:
            raise self.create_error
        self.created.append(config)
        return SimpleNamespace(name=CACHE_NAME, usage_metadata=SimpleNamespace(total_token_count=self.tokens))

    async def _delete(self, *, name):
        self.deleted.append(name)

    async def _generate(self, *, model, contents, config):
        self.calls.append(config)
        cached = bool(config.cached_content)
        if cached and self.cached_call_error is not None:
            raise self.cached_call_error
        # 40k prompt tokens, 39.5k of them cached when the cache is referenced
        usage = SimpleNamespace(
            prompt_token_count=TOKENS, candidates_token_count=0, thoughts_token_count=0,
            total_token_count=TOKENS, cached_content_token_count=39_500 if cached else 0,
            tool_use_prompt_token_count=0,
        )
        return SimpleNamespace(text="VERDICT: supported", usage_metadata=usage)


def _setup(tmp_path, monkeypatch, sdk, n_claims=2):
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    (fixture_dir / f"{PAPER}.json").write_text(json.dumps({
        "header": {"title": "t"}, "matches": [],
        "claims": [
            {"index": i, "claim_text_verbatim": f"c{i}", "claim_summary": f"s{i}"} for i in range(n_claims)
        ],
    }), encoding="utf-8")
    cache_dir = tmp_path / "raw_text_cache"
    cache_dir.mkdir()
    (cache_dir / "9999.00001v1.txt").write_text("fake paper text", encoding="utf-8")
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps([{"paper_id": PAPER, "claim_index": i} for i in range(n_claims)]), encoding="utf-8")
    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", cache_dir)
    monkeypatch.setattr(replay_audit, "OUTPUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(replay_audit, "get_prompt_version", lambda: replay_audit.EXPECTED_PROMPT_HASH)
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(engine, "BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr(engine.settings, "llm_claim_audit_model", MODEL)
    monkeypatch.setattr(engine, "_build_client", lambda: sdk.client)

    async def fake_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return ClaimLLM(
            claim_text_verbatim="v", claim_summary="s", label=ClaimLabel.SUPPORTED,
            evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="S")],
        )

    async def fake_ground(extraction, paper_text, chat_id, **kwargs):
        return [
            ClaimFinal(
                claim_text_verbatim="v", claim_summary="s", label=ClaimLabel.SUPPORTED, evidence_spans=[],
                grounding_status=GroundingStatus.PASS, missing=False, reason="r",
            )
            for _ in extraction
        ]

    monkeypatch.setattr(engine, "_call_gemini_structured", fake_structured)
    monkeypatch.setattr(grounding, "ground_extraction", fake_ground)
    monkeypatch.setattr(replay_audit, "ClaimsExtractionResponse", lambda claims: claims)
    return claims_path


def _args(claims_path, cache=True, max_inr=None):
    return argparse.Namespace(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=False,
        dry_run=False, max_inr=max_inr, cache=cache,
    )


def _summary(tmp_path) -> dict:
    return json.loads((tmp_path / "out" / "exp1_medium_1" / "_summary.json").read_text(encoding="utf-8"))


# --- cost math -------------------------------------------------------------------

def test_cache_overhead_is_creation_at_input_rate_plus_full_ttl_storage_and_hits_the_guard():
    guard = replay_audit._CostGuard()
    ledger = replay_audit._new_cache_ledger()
    paper_cache = SimpleNamespace(name=CACHE_NAME, token_count=TOKENS, ttl_s=2678)

    replay_audit._record_and_charge_cache(ledger, guard, PAPER, 42, paper_cache)

    creation = TOKENS / 1e6 * 0.75
    storage = TOKENS / 1e6 * (2678 / 3600) * 0.50
    record = ledger.papers[0]
    assert record.creation_usd == pytest.approx(creation) == pytest.approx(pricing.cache_creation_cost_usd(TOKENS))
    assert record.storage_usd == pytest.approx(storage) == pytest.approx(pricing.storage_cost_usd(TOKENS, 2678 / 3600))
    assert not record.tokens_assumed
    assert guard.running_usd == pytest.approx(creation + storage)


def test_missing_token_count_charges_the_measured_average_and_says_so():
    guard = replay_audit._CostGuard()
    ledger = replay_audit._new_cache_ledger()
    paper_cache = SimpleNamespace(name=CACHE_NAME, token_count=None, ttl_s=300)

    replay_audit._record_and_charge_cache(ledger, guard, PAPER, 2, paper_cache)

    record = ledger.papers[0]
    assert record.tokens_assumed and record.tokens_charged == ledger.assumed_tokens > 0
    assert guard.running_usd > 0


def test_cache_overhead_trips_the_cap_but_is_booked_first():
    guard = replay_audit._CostGuard(max_inr=1)  # creation alone is INR 3
    ledger = replay_audit._new_cache_ledger()
    paper_cache = SimpleNamespace(name=CACHE_NAME, token_count=TOKENS, ttl_s=300)

    with pytest.raises(replay_audit.CapExceeded):
        replay_audit._record_and_charge_cache(ledger, guard, PAPER, 2, paper_cache)

    assert len(ledger.papers) == 1 and guard.cap_hit


# --- a --cache run -----------------------------------------------------------------

def test_cache_run_books_creation_storage_and_cached_audit_calls(tmp_path, monkeypatch, capsys):
    sdk = _FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk, n_claims=2)

    rc = asyncio.run(replay_audit._main(_args(claims_path)))

    assert rc == 0
    assert len(sdk.created) == 1 and sdk.deleted == [CACHE_NAME]
    # 2 audit calls carried cached_content, no system_instruction
    assert [bool(c.cached_content) for c in sdk.calls] == [True, True]
    assert all(c.system_instruction is None for c in sdk.calls)

    summary = _summary(tmp_path)
    cache = summary["cache"]
    assert summary["status"] == "OK"
    assert cache["papers_cached"] == 1 and cache["creation_failures"] == 0
    assert cache["cached_call_api_failures"] == 0 and cache["cache_fallbacks"] == 0
    assert cache["claims_per_paper"] == {PAPER: 2}
    assert cache["total_cached_tokens"] == 2 * 39_500
    assert cache["audit_calls"] == 2 and cache["audit_calls_zero_cached"] == 0
    assert cache["papers"][0]["ttl_s"] == 300 and cache["papers"][0]["audit_calls_zero_cached"] == 0

    creation = TOKENS / 1e6 * 0.75
    storage = TOKENS / 1e6 * (300 / 3600) * 0.50
    assert cache["creation_usd_ASSUMED_at_normal_input_rate"] == pytest.approx(creation, abs=1e-4)
    assert cache["storage_usd_full_ttl"] == pytest.approx(storage, abs=1e-4)
    # audit calls: 500 uncached at the input rate + 39,500 cached at the cached rate
    per_call = 500 / 1e6 * 0.75 + 39_500 / 1e6 * 0.075
    assert summary["cost_usd"] == pytest.approx(2 * per_call, abs=1e-4)
    assert summary["total_cost_usd"] == pytest.approx(2 * per_call + creation + storage, abs=1e-4)
    assert cache["audit_cost_per_claim_inr_incl_cache_overhead"] > cache["audit_cost_per_claim_inr_excl_cache_overhead"]

    out = capsys.readouterr().out
    assert "ASSUMPTION" in out and "full TTL" in out
    assert "guaranteed" not in out.lower()


def test_cap_counts_cache_creation_and_storage(tmp_path, monkeypatch, capsys):
    sdk = _FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk, n_claims=2)

    rc = asyncio.run(replay_audit._main(_args(claims_path, max_inr=2)))  # creation alone is INR 3

    assert rc == replay_audit.EXIT_CAP_HIT
    assert sdk.calls == []  # stopped before any audit call
    assert sdk.deleted == [CACHE_NAME]  # and the cache was still deleted
    summary = _summary(tmp_path)
    assert summary["status"] == "VOID_CAP_HIT"
    assert summary["cache"]["papers_cached"] == 1


def test_creation_failure_stops_the_run_with_void_cache_failed(tmp_path, monkeypatch, capsys):
    sdk = _FakeSdk(create_error=_api_error(400))
    claims_path = _setup(tmp_path, monkeypatch, sdk)

    rc = asyncio.run(replay_audit._main(_args(claims_path)))

    assert rc == replay_audit.EXIT_CAP_HIT == 2
    assert sdk.calls == [] and sdk.deleted == []
    summary = _summary(tmp_path)
    assert summary["status"] == "VOID_CACHE_FAILED"
    assert summary["cache"]["creation_failures"] == 1
    assert "boom 400" in summary["cache"]["stop_reason"]
    assert "VOID_CACHE_FAILED" in capsys.readouterr().out


def test_first_cached_call_error_stops_the_run_without_an_uncached_retry(tmp_path, monkeypatch, capsys):
    sdk = _FakeSdk(cached_call_error=_api_error(400))
    claims_path = _setup(tmp_path, monkeypatch, sdk, n_claims=3)

    rc = asyncio.run(replay_audit._main(_args(claims_path)))

    assert rc == 2
    assert len(sdk.calls) == 1  # the one cached call; no retry, no second claim
    assert sdk.deleted == [CACHE_NAME]
    summary = _summary(tmp_path)
    assert summary["status"] == "VOID_CACHE_FAILED"
    assert summary["cache"]["cached_call_api_failures"] == 1
    assert "status=400" in summary["cache"]["stop_reason"]


def test_without_the_flag_no_cache_call_is_made_and_no_cache_block_written(tmp_path, monkeypatch):
    sdk = _FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk, n_claims=2)

    rc = asyncio.run(replay_audit._main(_args(claims_path, cache=False)))

    assert rc == 0
    assert sdk.created == [] and sdk.deleted == []
    assert all(c.cached_content is None and c.system_instruction for c in sdk.calls)
    assert "cache" not in _summary(tmp_path)


def test_cache_flag_defaults_off():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "high"]).cache is False
    assert parser.parse_args(["--level", "high", "--cache"]).cache is True


# --- --estimate --cache --------------------------------------------------------------

def _targets(n_claims):
    return [
        replay_audit.ReplayTarget(paper_id=PAPER, claim_index=i, claim_text_verbatim="c", claim_summary="s")
        for i in range(n_claims)
    ]


def test_estimate_cache_prints_assumptions_cached_vs_uncached_and_a_suggested_cap(monkeypatch, capsys):
    def _fail():
        raise AssertionError("--estimate must not build a client")

    monkeypatch.setattr(engine, "_build_client", _fail)

    replay_audit._print_estimate(_targets(30), "medium", 1, cache=True)

    out = capsys.readouterr().out
    assert "ASSUMPTION: 500 uncached tokens per claim" in out
    assert "ASSUMPTION: cache creation is billed at the normal input rate" in out
    assert f"{PAPER}': 30" in out  # claims per paper
    assert f"{PAPER}': {replay_audit.ttl_for_claims(30)}" in out  # TTL for 30 claims
    uncached = re.search(r"\] uncached total: USD ([\d.]+)-([\d.]+)", out)
    cached = re.search(r"\] cached total:\s+USD ([\d.]+)-([\d.]+)", out)
    cap = re.search(r"suggested --max-inr with --cache \(1.3x the high end\): ([\d.]+)", out)
    assert uncached and cached and cap
    assert float(cached.group(2)) < float(uncached.group(2))  # 30 claims per paper: cheaper cached
    assert float(cap.group(1)) == pytest.approx(float(cached.group(2)) * 100 * 1.3, abs=0.2)
    assert "guaranteed" not in out.lower()


def test_estimate_without_cache_flag_is_unchanged(capsys):
    replay_audit._print_estimate(_targets(3), "high", 1)

    out = capsys.readouterr().out
    assert "estimated cost" in out and "suggested --max-inr (1.3x estimate): " in out
    assert "cached total" not in out


def test_estimate_one_claim_cost_with_no_cached_tokens_is_the_old_figure():
    stats = replay_audit._FALLBACK_MEASURED_STATS
    low, high = replay_audit._estimate_one_claim_cost_usd(stats, "high")
    cached_low, cached_high = replay_audit._estimate_one_claim_cost_usd(stats, "high", cached_audit_tokens=36_889)
    assert 0 < cached_low < low and 0 < cached_high < high
