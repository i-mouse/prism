"""Offline tests for the additive LLM-call logging: Gemini usage fields and
call_info, the run_extractor refactor, the claim-drop record, and Stage-2
per-span records/totals. Synthetic strings only; no network."""
import asyncio
import json
from types import SimpleNamespace

import litellm
from google.genai import types
from litellm.router_utils.add_retry_fallback_headers import add_fallback_headers_to_response

from extraction import engine, grounding
from extraction.prompt_loader import build_gemini_messages_for_extractor
from extraction.schemas import ClaimLabel, ClaimLLM, ClaimsExtractionResponse, EvidenceSpanLLM, GroundingStatus

PAPER = "SYNTHETIC PAPER. Widgets rotate clockwise in the blue chamber at dawn. Nothing else happens."
SPAN_IN_PAPER = "Widgets rotate clockwise in the blue chamber at dawn."
SPAN_NOT_IN_PAPER = "Gadgets hover silently above the purple fountain every evening."


def _genai_response(text='{"claims": []}', finish=types.FinishReason.STOP):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]),
                                    finish_reason=finish)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, cached_content_token_count=40, candidates_token_count=20,
            thoughts_token_count=7, total_token_count=127),
        model_version="synthetic-model-001",
    )


class _FakeModels:
    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    async def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.respond(model)


def _install_client(monkeypatch, tmp_path, respond):
    models = _FakeModels(respond)
    monkeypatch.setattr(engine, "_build_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=models)))
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(engine, "BACKOFF_SECONDS", (0, 0, 0))
    return models


# --- null safety -----------------------------------------------------------

def test_usage_fields_null_safe():
    empty = dict.fromkeys(engine._usage_fields(None))
    assert engine._usage_fields(None) == empty
    assert engine._usage_fields(object()) == empty
    assert engine._usage_fields(SimpleNamespace(usage_metadata=None, candidates=None)) == empty
    assert engine._usage_fields(SimpleNamespace(usage_metadata=None, candidates=[])) == empty
    assert engine._usage_fields(types.GenerateContentResponse()) == empty


def test_usage_fields_values():
    assert engine._usage_fields(_genai_response()) == {
        "prompt_token_count": 100, "cached_content_token_count": 40, "candidates_token_count": 20,
        "thoughts_token_count": 7, "total_token_count": 127, "finish_reason": "STOP",
        "model_version": "synthetic-model-001",
    }


def test_litellm_call_fields_null_safe():
    fields = grounding._litellm_call_fields(None)
    assert set(fields.values()) == {None}
    assert grounding._litellm_call_fields(litellm.ModelResponse(model="x"))["route"] is None
    assert grounding._litellm_call_fields(SimpleNamespace(usage=None, choices=None, _hidden_params=None))["prompt_tokens"] is None


def _litellm_response(attempted_fallbacks=0, content=None):
    content = content or json.dumps({"reasoning": "r", "stance": "supports", "verdict": "Pass", "reason": "ok"})
    response = litellm.ModelResponse(
        model="synthetic/primary",
        choices=[{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        usage={"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60,
               "prompt_tokens_details": {"cached_tokens": 5}, "completion_tokens_details": {"reasoning_tokens": 4}},
    )
    # The same helper LiteLLM's fallbacks= runner uses to mark the response.
    return add_fallback_headers_to_response(response=response, attempted_fallbacks=attempted_fallbacks)


def test_litellm_call_fields_values():
    fields = grounding._litellm_call_fields(_litellm_response(attempted_fallbacks=1))
    assert fields == {
        "answered_by": "synthetic/primary", "attempted_fallbacks": 1, "route": "fallback",
        "prompt_tokens": 50, "cached_tokens": 5, "completion_tokens": 10, "reasoning_tokens": 4,
        "total_tokens": 60, "finish_reason": "stop",
    }
    assert grounding._litellm_call_fields(_litellm_response(attempted_fallbacks=0))["route"] == "primary"


# --- run_extractor / call_info --------------------------------------------

def test_run_extractor_call_info_and_log_fields(monkeypatch, tmp_path):
    _install_client(monkeypatch, tmp_path, lambda model: _genai_response())
    raw, info = asyncio.run(engine.run_extractor(PAPER, chat_id="c1"))
    assert raw == {"claims": []}
    assert info["fallback_used"] is False and info["used_model"] == engine.settings.llm_extraction_model
    assert info["json_parse_ok"] is True and info["finish_reason"] == "STOP"
    assert info["thoughts_token_count"] == 7 and info["model_version"] == "synthetic-model-001"

    [log_file] = list((tmp_path / "extraction").glob("*.json"))
    record = json.loads(log_file.read_text(encoding="utf-8"))
    assert record["prompt_token_count"] == 100 and record["cached_content_token_count"] == 40
    assert record["finish_reason"] == "STOP" and record["model_version"] == "synthetic-model-001"
    assert record["model_used"] == engine.settings.llm_extraction_model


def test_run_extractor_records_fallback(monkeypatch, tmp_path):
    def respond(model):
        if model == engine.settings.llm_extraction_model:
            raise TimeoutError("synthetic timeout")
        return _genai_response()

    models = _install_client(monkeypatch, tmp_path, respond)
    _, info = asyncio.run(engine.run_extractor(PAPER, chat_id="c2"))
    assert info["fallback_used"] is True and info["used_model"] == engine.settings.llm_extraction_fallback_model
    assert len(models.calls) == engine.MAX_ATTEMPTS + 1


def test_run_extractor_parse_failure_keeps_call_info_and_exception(monkeypatch, tmp_path):
    _install_client(monkeypatch, tmp_path, lambda model: _genai_response(text="not json"))
    info: dict = {}
    try:
        asyncio.run(engine.run_extractor(PAPER, chat_id="c3", call_info=info))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "was not valid JSON" in str(exc)
    assert info["json_parse_ok"] is False and info["prompt_token_count"] == 100


def test_extract_claims_extractor_request_identical_to_direct_call(monkeypatch, tmp_path):
    """extract_claims (via run_extractor) sends exactly what the pre-refactor
    inline call sent: _call_gemini_json(build_gemini_messages_for_extractor(...))
    with the extraction model pair."""
    models = _install_client(monkeypatch, tmp_path, lambda model: _genai_response())

    asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c4"))
    asyncio.run(engine._call_gemini_json(
        messages=build_gemini_messages_for_extractor(PAPER), chat_id="c4", correlation_id=None,
        log_subdir="extraction", model_name=engine.settings.llm_extraction_model,
        fallback_model=engine.settings.llm_extraction_fallback_model,
    ))

    def serialise(call):
        return json.dumps({
            "model": call["model"],
            "config": call["config"].model_dump(mode="json", exclude_none=True),
            "contents": [c.model_dump(mode="json", exclude_none=True) for c in call["contents"]],
        }, sort_keys=True).encode("utf-8")

    via_extract_claims, direct = models.calls
    assert serialise(via_extract_claims) == serialise(direct)
    assert via_extract_claims["config"].system_instruction == direct["config"].system_instruction


# --- drop record -----------------------------------------------------------

def test_extract_claims_writes_drop_record(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)

    async def fake_json(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model, call_info=None):
        return {"claims": [{"claim_text_verbatim": "Alpha.", "claim_summary": "a"},
                           {"claim_text_verbatim": "Beta.", "claim_summary": "b"}]}

    async def fake_freetext(messages, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        return "VERDICT: supported"

    async def fake_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model):
        if "Beta." in messages[-1]["content"]:
            raise RuntimeError("synthetic structure failure")
        return ClaimLLM(claim_text_verbatim="Alpha.", claim_summary="a", label=ClaimLabel.SUPPORTED,
                        evidence_spans=[EvidenceSpanLLM(source_text="q", source_section="S")])

    monkeypatch.setattr(engine, "_call_gemini_json", fake_json)
    monkeypatch.setattr(engine, "_call_gemini_freetext", fake_freetext)
    monkeypatch.setattr(engine, "_call_gemini_structured", fake_structured)

    result = asyncio.run(engine.extract_claims(paper_text=PAPER, chat_id="c5"))
    assert [c.claim_text_verbatim for c in result.claims] == ["Alpha."]
    [drop_file] = list((tmp_path / "extraction").glob("*_drops.json"))
    record = json.loads(drop_file.read_text(encoding="utf-8"))
    assert record["total_claims"] == 2 and record["dropped_count"] == 1
    assert record["dropped"] == [
        {"claim_index": 1, "exception_type": "RuntimeError", "message": "synthetic structure failure"}
    ]


def test_drop_log_failure_never_raises(monkeypatch, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    monkeypatch.setattr(engine, "LOGS_DIR", blocker)
    engine._write_drop_log("c6", None, 1, [{"claim_index": 0, "exception_type": "E", "message": "m"}])


# --- grounding Stage 2 -----------------------------------------------------

def _extraction():
    return ClaimsExtractionResponse(claims=[
        ClaimLLM(claim_text_verbatim="Widgets rotate.", claim_summary="s", label=ClaimLabel.SUPPORTED,
                 evidence_spans=[EvidenceSpanLLM(source_text=SPAN_IN_PAPER, source_section="S1"),
                                 EvidenceSpanLLM(source_text=SPAN_NOT_IN_PAPER, source_section="S2")]),
    ])


def _grounding_log(tmp_path):
    [log_file] = list(tmp_path.glob("*.json"))
    return json.loads(log_file.read_text(encoding="utf-8"))


def test_grounding_logs_span_calls_and_totals(monkeypatch, tmp_path):
    monkeypatch.setattr(grounding, "LOGS_DIR", tmp_path)

    async def fake_acompletion(**kwargs):
        return _litellm_response(attempted_fallbacks=1)

    monkeypatch.setattr(grounding.litellm, "acompletion", fake_acompletion)
    final = asyncio.run(grounding.ground_extraction(_extraction(), PAPER, chat_id="g1"))
    assert [s.grounding_status for s in final[0].evidence_spans] == [GroundingStatus.PASS, GroundingStatus.FAIL]

    record = _grounding_log(tmp_path)
    assert record["stage2_spans_called"] == 1
    assert record["stage2_spans_answered_fallback"] == 1 and record["stage2_spans_answered_primary"] == 0
    assert record["stage2_spans_errored"] == 0
    assert record["stage2_prompt_tokens_total"] == 50 and record["stage2_reasoning_tokens_total"] == 4
    called, skipped = record["span_calls"]
    assert called["claim_index"] == 0 and called["span_index"] == 0 and called["stage2_called"] is True
    assert called["attempts"] == 1 and called["answered_by"] == "synthetic/primary"
    assert skipped == {"claim_index": 0, "span_index": 1, "stage2_called": False}
    assert SPAN_IN_PAPER not in json.dumps(record["span_calls"])


def test_grounding_logs_errored_span(monkeypatch, tmp_path):
    monkeypatch.setattr(grounding, "LOGS_DIR", tmp_path)

    async def failing_acompletion(**kwargs):
        raise ValueError("synthetic non-retryable")

    monkeypatch.setattr(grounding.litellm, "acompletion", failing_acompletion)
    final = asyncio.run(grounding.ground_extraction(_extraction(), PAPER, chat_id="g2"))
    assert final[0].evidence_spans[0].grounding_status == GroundingStatus.SKIPPED

    record = _grounding_log(tmp_path)
    assert record["stage2_spans_errored"] == 1 and record["stage2_spans_called"] == 1
    assert record["span_calls"][0]["error_type"] == "ValueError"
    assert record["stage2_total_tokens_total"] == 0
