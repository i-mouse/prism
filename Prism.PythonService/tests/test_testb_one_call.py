"""eval/testb/one_call.py: backend check, cost reuse, retry/abort/cap rules, output-dir
refusal, --estimate/--smoke. Offline only: a fake genai client, made-up papers, no
network (conftest.py already makes the real genai client factory refuse to build)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import errors

from eval import pricing
from eval.replay_audit import CallRecord, _gemini_record_cost_usd
from eval.testb import one_call
from eval.testb.one_call_schemas import OneCallClaim, OneCallResult
from extraction import llm_backend


# --------------------------------------------------------------------------- fakes

class _FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"kind": "generate_content", "model": model})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def count_tokens(self, *, model, contents):
        self.calls.append({"kind": "count_tokens", "model": model})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses=(), vertexai=False):
        self.vertexai = vertexai
        self.models = _FakeModels(responses)


def _usage(prompt=100, output=50, thought=10, cached=0):
    return SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=output,
        thoughts_token_count=thought, cached_content_token_count=cached,
    )


def _ok_response(claim_quote="made-up claim quote text that is long enough to anchor against, over thirty chars",
                  verdict="partially_supported", finish_reason="STOP", usage=None, model_version="gemini-4-carbon-001"):
    parsed = OneCallResult(claims=[OneCallClaim.model_validate({
        "claim_quote": claim_quote, "location": "Section 1", "evidence": "Table 1: made-up evidence quote",
        "verdict": verdict, "reason": "made-up reason",
    })])
    return SimpleNamespace(
        parsed=parsed, text=json.dumps(parsed.model_dump()),
        usage_metadata=usage or _usage(),
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value=finish_reason))],
        model_version=model_version,
    )


def _api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"message": "made-up", "status": "X", "code": code}})


def _install_fake_client(monkeypatch, responses, vertexai=False):
    fake = FakeClient(responses, vertexai=vertexai)
    monkeypatch.setattr(llm_backend, "_client_factory", lambda **kw: fake)
    return fake


def _no_sleep(monkeypatch):
    calls = []
    monkeypatch.setattr(one_call, "_sleep", lambda seconds: calls.append(seconds))
    return calls


def _fake_papers(monkeypatch, paper_ids):
    papers = [SimpleNamespace(paper_id=pid) for pid in paper_ids]
    monkeypatch.setattr(one_call, "_dev_papers", lambda: papers)
    monkeypatch.setattr(one_call, "_paper_text", lambda paper_id: f"made-up paper text for {paper_id}")


# --------------------------------------------------------------------------- backend check

def test_wrong_backend_raises_before_any_call(monkeypatch):
    _install_fake_client(monkeypatch, responses=[], vertexai=True)
    with pytest.raises(one_call.WrongBackendError):
        one_call._build_client()


def test_aistudio_backend_passes():
    client = FakeClient([], vertexai=False)
    one_call._ensure_aistudio(client)  # does not raise


def test_never_calls_set_backend():
    source = Path(one_call.__file__).read_text(encoding="utf-8")
    assert "set_backend(" not in source


# --------------------------------------------------------------------------- cost reuse

def test_cost_matches_replay_audit_exactly():
    usage = {"prompt_tokens": 123456, "output_tokens": 7890, "thought_tokens": 321, "cached_tokens": 50000}
    expected_record = CallRecord(
        stage="x", paper_id="p", claim_index=0, thinking_level="medium", model_used="gemini-4-carbon",
        prompt_tokens=usage["prompt_tokens"], output_tokens=usage["output_tokens"],
        thought_tokens=usage["thought_tokens"], total_tokens=0, latency_s=0.0, cached_tokens=usage["cached_tokens"],
    )
    expected_usd, _ = _gemini_record_cost_usd(expected_record)
    expected_inr = expected_usd * pricing.INR_PER_USD
    assert one_call._cost_inr(usage) == pytest.approx(expected_inr)


def test_cost_never_double_counts_cached_tokens():
    # cached tokens are part of prompt_tokens (both SDKs report it that way); a buggy
    # implementation that bills prompt + cached separately would overcharge.
    usage = {"prompt_tokens": 100000, "output_tokens": 1000, "thought_tokens": 0, "cached_tokens": 100000}
    inr = one_call._cost_inr(usage)
    rates = pricing.rates_for_model("gemini-4-carbon")
    expected_usd = (0 / 1e6 * rates.in_usd + 100000 / 1e6 * rates.cached_rate) + (1000 / 1e6 * rates.out_usd)
    assert inr == pytest.approx(expected_usd * pricing.INR_PER_USD)


# --------------------------------------------------------------------------- per-call error handling

def test_403_aborts_whole_run_immediately(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1", "arxiv-FAKE2"])
    fake = _install_fake_client(monkeypatch, responses=[_api_error(403)])
    out_dir = tmp_path / "out"
    status = one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    assert status == "ACCESS_DENIED"
    assert len(fake.models.calls) == 1  # never reached the second paper
    summary = json.loads((out_dir / "run_1" / "_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ACCESS_DENIED"


def test_400_aborts_whole_run_as_api_error(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1", "arxiv-FAKE2"])
    fake = _install_fake_client(monkeypatch, responses=[_api_error(400)])
    out_dir = tmp_path / "out"
    status = one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    assert status == "API_ERROR"
    assert len(fake.models.calls) == 1


def test_429_then_success_retries_once(monkeypatch, tmp_path):
    sleeps = _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    _install_fake_client(monkeypatch, responses=[_api_error(429), _ok_response()])
    out_dir = tmp_path / "out"
    status = one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    assert status == "OK"
    assert sleeps == [30]
    record = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    assert record["status"] == "OK" and record["attempts"] == 2


def test_second_failure_marks_paper_failed_and_continues(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1", "arxiv-FAKE2"])
    _install_fake_client(monkeypatch, responses=[_api_error(429), _api_error(503), _ok_response()])
    out_dir = tmp_path / "out"
    status = one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    assert status == "OK"
    rec1 = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    rec2 = json.loads((out_dir / "run_1" / "arxiv-FAKE2.json").read_text(encoding="utf-8"))
    assert rec1["status"] == "FAILED" and rec1["attempts"] == 2
    assert rec2["status"] == "OK"
    summary = json.loads((out_dir / "run_1" / "_summary.json").read_text(encoding="utf-8"))
    assert summary["papers_failed"] == 1 and summary["papers_ok"] == 1


def test_max_tokens_finish_reason_treated_as_failure(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    _install_fake_client(monkeypatch, responses=[
        _ok_response(finish_reason="MAX_TOKENS"), _ok_response(finish_reason="MAX_TOKENS"),
    ])
    out_dir = tmp_path / "out"
    one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    record = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED"


def test_invalid_json_treated_as_retryable_then_failed(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    bad = SimpleNamespace(
        parsed=None, text="not json", usage_metadata=_usage(),
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))], model_version="v1",
    )
    _install_fake_client(monkeypatch, responses=[bad, bad])
    out_dir = tmp_path / "out"
    one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    record = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED"


def _none_text_response():
    return SimpleNamespace(
        parsed=None, text=None, usage_metadata=_usage(),
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))], model_version="v1",
    )


def test_response_text_none_retries_then_failed(monkeypatch, tmp_path):
    sleeps = _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    _install_fake_client(monkeypatch, responses=[_none_text_response(), _none_text_response()])
    out_dir = tmp_path / "out"
    one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    record = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED" and record["attempts"] == 2
    assert sleeps == [30]


def test_response_text_empty_string_retries_then_failed(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    empty = SimpleNamespace(
        parsed=None, text="", usage_metadata=_usage(),
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))], model_version="v1",
    )
    _install_fake_client(monkeypatch, responses=[empty, empty])
    out_dir = tmp_path / "out"
    one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    record = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED"


def test_response_parsed_property_raising_typeerror_never_escapes(monkeypatch, tmp_path):
    """The real SDK's `.parsed` can itself raise instead of returning None (e.g. trying
    to parse a blocked/empty response). That must never crash the run - it is treated
    exactly like invalid JSON."""
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])

    class _RaisingParsedResponse:
        text = None
        usage_metadata = _usage()
        candidates = [SimpleNamespace(finish_reason=SimpleNamespace(value="STOP"))]
        model_version = "v1"

        @property
        def parsed(self):
            raise TypeError("boom: cannot parse blocked response")

    _install_fake_client(monkeypatch, responses=[_RaisingParsedResponse(), _RaisingParsedResponse()])
    out_dir = tmp_path / "out"
    one_call.run_index_cmd(1, out_dir, max_inr=1000.0)  # must not raise
    record = json.loads((out_dir / "run_1" / "arxiv-FAKE1.json").read_text(encoding="utf-8"))
    assert record["status"] == "FAILED"


def test_smoke_text_none_clean_failed_status_no_crash(monkeypatch, capsys):
    _no_sleep(monkeypatch)
    _install_fake_client(monkeypatch, responses=[_none_text_response(), _none_text_response()])
    status = one_call.run_smoke_cmd()  # must not raise
    assert status == "FAILED"
    out = capsys.readouterr().out
    assert "status=FAILED" in out


# --------------------------------------------------------------------------- cap

def test_cap_stops_run_with_capped_status(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1", "arxiv-FAKE2"])
    _install_fake_client(monkeypatch, responses=[_ok_response(), _ok_response()])
    out_dir = tmp_path / "out"
    status = one_call.run_index_cmd(1, out_dir, max_inr=0.0)  # any real cost exceeds a 0 cap
    assert status == "CAPPED"
    assert not (out_dir / "run_1" / "arxiv-FAKE2.json").exists()


# --------------------------------------------------------------------------- output dir refusal

def test_refuses_out_dir_inside_repo():
    with pytest.raises(ValueError, match="inside the git repo"):
        one_call._validate_out_dir(one_call.REPO_ROOT / "docs" / "evals" / "testb_scratch")


def test_out_dir_itself_may_already_exist(tmp_path):
    existing = tmp_path / "already_here"
    existing.mkdir()
    one_call._validate_out_dir(existing)  # does not raise


def test_run_dir_refused_when_it_already_exists(tmp_path):
    out_dir = tmp_path / "out"
    run_dir = out_dir / "run_1"
    run_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        one_call._validate_run_dir(run_dir)


def test_run_2_allowed_when_dir_and_run_1_already_exist(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    out_dir = tmp_path / "out"
    (out_dir / "run_1").mkdir(parents=True)  # run 1 already happened
    (out_dir / "run_1" / "_summary.json").write_text("{}", encoding="utf-8")
    _install_fake_client(monkeypatch, responses=[_ok_response()])
    status = one_call.run_index_cmd(2, out_dir, max_inr=1000.0)
    assert status == "OK"
    assert (out_dir / "run_2" / "_summary.json").exists()


def test_run_k_refused_when_its_own_run_dir_exists(monkeypatch, tmp_path):
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    out_dir = tmp_path / "out"
    (out_dir / "run_1").mkdir(parents=True)
    fake = _install_fake_client(monkeypatch, responses=[])
    with pytest.raises(ValueError, match="already exists"):
        one_call.run_index_cmd(1, out_dir, max_inr=1000.0)
    assert fake.models.calls == []  # refused before any call was made


def test_estimate_creates_no_folder(monkeypatch, tmp_path):
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    count_result = SimpleNamespace(total_tokens=10)
    _install_fake_client(monkeypatch, responses=[count_result])
    would_be_dir = tmp_path / "estimate_out"
    assert one_call.main(["--estimate", "--out", str(would_be_dir)]) == 0
    assert not would_be_dir.exists()


def test_smoke_creates_no_folder(monkeypatch, tmp_path):
    _install_fake_client(monkeypatch, responses=[_ok_response()])
    would_be_dir = tmp_path / "smoke_out"
    assert one_call.main(["--smoke", "--out", str(would_be_dir)]) == 0
    assert not would_be_dir.exists()


# --------------------------------------------------------------------------- model pin

def test_fake_client_only_ever_receives_gemini_4_carbon(monkeypatch, tmp_path):
    _no_sleep(monkeypatch)
    _fake_papers(monkeypatch, ["arxiv-FAKE1", "arxiv-FAKE2"])
    fake = _install_fake_client(monkeypatch, responses=[_ok_response(), _ok_response()])
    one_call.run_index_cmd(1, tmp_path / "out", max_inr=1000.0)
    assert fake.models.calls
    assert all(call["model"] == "gemini-4-carbon" for call in fake.models.calls)


# --------------------------------------------------------------------------- --estimate

def test_estimate_makes_no_generate_call(monkeypatch, capsys):
    _fake_papers(monkeypatch, ["arxiv-FAKE1", "arxiv-FAKE2"])
    count_result = SimpleNamespace(total_tokens=4242)
    fake = _install_fake_client(monkeypatch, responses=[count_result, count_result])
    status = one_call.run_estimate_cmd()
    assert status == "OK"
    assert all(call["kind"] == "count_tokens" for call in fake.models.calls)
    out = capsys.readouterr().out
    assert "4242" in out
    assert "suggested run-1 --max-inr" in out


# --------------------------------------------------------------------------- --smoke

def test_smoke_success_prints_metrics_no_text(monkeypatch, capsys):
    _install_fake_client(monkeypatch, responses=[_ok_response()])
    status = one_call.run_smoke_cmd()
    assert status == "OK"
    out = capsys.readouterr().out
    assert "claims=1" in out and "cost_inr=" in out and "finish_reason=" in out and "model_version=" in out
    assert one_call.SMOKE_PAPER_TEXT not in out
    assert "made-up claim quote" not in out


def test_smoke_403_stops_with_access_denied(monkeypatch, capsys):
    _install_fake_client(monkeypatch, responses=[_api_error(403)])
    status = one_call.run_smoke_cmd()
    assert status == "ACCESS_DENIED"


def test_smoke_400_stops_with_api_error(monkeypatch, capsys):
    _no_sleep(monkeypatch)
    _install_fake_client(monkeypatch, responses=[_api_error(400)])
    status = one_call.run_smoke_cmd()
    assert status == "API_ERROR"


# --------------------------------------------------------------------------- console hygiene

def test_console_output_never_prints_paper_or_claim_text(monkeypatch, capsys, tmp_path):
    _no_sleep(monkeypatch)
    secret_quote = "THIS EXACT CLAIM QUOTE MUST NEVER REACH THE CONSOLE " + "x" * 40
    _fake_papers(monkeypatch, ["arxiv-FAKE1"])
    _install_fake_client(monkeypatch, responses=[_ok_response(claim_quote=secret_quote)])
    one_call.run_index_cmd(1, tmp_path / "out", max_inr=1000.0)
    out = capsys.readouterr().out
    assert secret_quote not in out
    assert "made-up paper text" not in out
