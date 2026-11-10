"""engine._generate_with_fallback: the allow_fallback opt-out and the call_kind tag.

Defaults must leave every existing caller exactly as before; allow_fallback=False
removes only the switch to another model (same-model retries and backoff stay)."""
import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors

from extraction import engine

PRIMARY = "primary-model"
FALLBACK = "fallback-model"


def _api_error(code: int) -> errors.APIError:
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": f"boom {code}", "status": "UNAVAILABLE"}})


class _Client:
    def __init__(self, fail_models=(PRIMARY,), code=503):
        self.fail_models = set(fail_models)
        self.code = code
        self.models_requested: list[str] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        self.models_requested.append(model)
        if model in self.fail_models:
            raise _api_error(self.code)
        return SimpleNamespace(text="ok")


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(engine, "BACKOFF_SECONDS", (0, 0, 0))


def _call(client, **kwargs):
    return asyncio.run(engine._generate_with_fallback(client, [], None, "chat", PRIMARY, FALLBACK, None, **kwargs))


def test_default_still_falls_back_after_the_primary_retries():
    client = _Client()
    response, used = _call(client)
    assert used == FALLBACK and response.text == "ok"
    assert client.models_requested == [PRIMARY] * engine.MAX_ATTEMPTS + [FALLBACK]


def test_allow_fallback_true_is_the_default_behaviour():
    client = _Client()
    _, used = _call(client, allow_fallback=True)
    assert used == FALLBACK
    assert client.models_requested == [PRIMARY] * engine.MAX_ATTEMPTS + [FALLBACK]


def test_opt_out_retries_the_same_model_then_raises_without_switching():
    client = _Client()
    with pytest.raises(errors.ServerError):
        _call(client, allow_fallback=False)
    assert client.models_requested == [PRIMARY] * engine.MAX_ATTEMPTS


def test_opt_out_still_succeeds_on_a_same_model_retry():
    attempts = {"n": 0}
    client = _Client(fail_models=())

    async def flaky(*, model, contents, config):
        attempts["n"] += 1
        client.models_requested.append(model)
        if attempts["n"] < 3:
            raise _api_error(503)
        return SimpleNamespace(text="ok")

    client.aio.models.generate_content = flaky
    response, used = _call(client, allow_fallback=False)
    assert used == PRIMARY and client.models_requested == [PRIMARY] * 3


@pytest.mark.parametrize("allow_fallback", [True, False])
def test_a_non_retryable_error_is_raised_either_way(allow_fallback):
    client = _Client(code=400)
    with pytest.raises(errors.ClientError):
        _call(client, allow_fallback=allow_fallback)
    assert client.models_requested == [PRIMARY]


def test_call_kind_has_no_effect_on_the_call():
    plain, tagged = _Client(), _Client()
    _, used_plain = _call(plain)
    _, used_tagged = _call(tagged, call_kind="lister")
    assert used_plain == used_tagged == FALLBACK
    assert plain.models_requested == tagged.models_requested
    opt_out = _Client()
    with pytest.raises(errors.ServerError):
        _call(opt_out, allow_fallback=False, call_kind="checker")
    assert opt_out.models_requested == [PRIMARY] * engine.MAX_ATTEMPTS
