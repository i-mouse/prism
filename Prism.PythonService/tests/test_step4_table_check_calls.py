"""Unit tests for eval/step4/table_check_calls.py: the lister retry, the checker request, its retry and the
per-claim sequence. Offline: the engine call and the scope lister are replaced by fakes; made-up strings only."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from google.genai import types

from eval.step4 import table_check as tc
from eval.step4 import table_check_calls as calls
from eval.step4.table_check_schemas import TableCheckResponse
from extraction import engine, scope_check

PAPER = (
    "Table 1: Speed of gadgets\n"
    "Gadget Small Large\n"
    "Alpha sorter 41.5 38.2\n"
    "Bravo sorter 44.0 36.9\n"
)
CLAIM = "Table 1 shows the Bravo sorter is fastest on small loads and on large loads."
ITEMS = [
    SimpleNamespace(text="the Bravo sorter is fastest on small loads", kind="pair"),
    SimpleNamespace(text="the Bravo sorter is fastest on large loads", kind="pair"),
]
GOOD = json.dumps({"pieces": [
    {"piece_id": 1, "answer": "backed",
     "cells": [{"table": 1, "row_label": "Bravo sorter", "column_label": "Small", "value": "44.0"}]},
    {"piece_id": 2, "answer": "not_backed",
     "cells": [{"table": 1, "row_label": "Bravo sorter", "column_label": "Large", "value": "36.9"}]},
]})


class Stop(BaseException):
    """Stands in for a cost-cap stop: a BaseException that no retry may swallow."""


class Fakes:
    def __init__(self, monkeypatch, lister=None, checker=None):
        self.lister_script = list(lister if lister is not None else [ITEMS])
        self.checker_script = list(checker if checker is not None else [GOOD])
        self.lister_calls = 0
        self.checker_calls: list[dict] = []
        monkeypatch.setattr(scope_check, "list_scope_items", self._list)
        monkeypatch.setattr(engine, "_build_client", lambda: "client")
        monkeypatch.setattr(engine, "_generate_with_fallback", self._generate)
        monkeypatch.setattr(engine, "_extract_usage_and_finish_reason", lambda response: (None, None))
        monkeypatch.setattr(engine, "_write_structured_log", lambda **kwargs: None)

    async def _list(self, claim_text, chat_id, correlation_id=None):
        self.lister_calls += 1
        step = self.lister_script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step

    async def _generate(self, client, contents, config, chat_id, model_name, fallback_model, correlation_id=None, **kwargs):
        self.checker_calls.append({
            "contents": contents, "config": config, "model": model_name, "fallback_model": fallback_model, **kwargs,
        })
        step = self.checker_script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return SimpleNamespace(text=step, parsed=None, usage_metadata=None), model_name


def _check(level="medium"):
    blocks = tc.build_table_blocks(PAPER)
    return asyncio.run(calls.check_claim(CLAIM, (1,), blocks, level, "chat", claim_ref="made-up#0"))


def test_one_lister_call_and_one_checker_call_give_the_claim_result(monkeypatch):
    fakes = Fakes(monkeypatch)
    trace = _check()
    assert (fakes.lister_calls, len(fakes.checker_calls)) == (1, 1)
    assert [p.state for p in trace.pieces] == [tc.PASSED, tc.FAILED]
    assert (trace.label, trace.use_fallback, trace.n_failed) == (tc.LABEL_PARTIAL, False, 1)
    assert trace.checker_model_served == calls.CHECKER_MODEL and trace.cited == [1]
    assert not trace.lister_failed and not trace.checker_failed


def test_the_checker_request_shape(monkeypatch):
    fakes = Fakes(monkeypatch)
    _check(level="medium")
    call = fakes.checker_calls[0]
    assert call["model"] == call["fallback_model"] == calls.CHECKER_MODEL == "gemini-3.6-flash"
    assert call["allow_fallback"] is False and call["call_kind"] == calls.CHECKER_CALL_KIND == "table_checker"
    config = call["config"]
    assert config.response_schema is TableCheckResponse and config.response_mime_type == "application/json"
    assert config.system_instruction == tc.checker_system_prompt()
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MEDIUM   # the auditor's level, not "low"
    sent = "\n".join(part.text for content in call["contents"] for part in content.parts)
    assert sent == tc.build_checker_user_text(CLAIM, tc.pieces_from_items(ITEMS), tc.build_table_blocks(PAPER).text)
    assert "=== Table 1 ===" in sent and "Bravo sorter 44.0 36.9" in sent


def test_lister_is_retried_once_then_succeeds(monkeypatch):
    fakes = Fakes(monkeypatch, lister=[RuntimeError("boom"), ITEMS])
    trace = _check()
    assert fakes.lister_calls == 2 and not trace.lister_failed and trace.label == tc.LABEL_PARTIAL


def test_lister_failing_twice_falls_back_to_the_auditor_without_a_checker_call(monkeypatch):
    fakes = Fakes(monkeypatch, lister=[RuntimeError("boom"), ValueError("not json")])
    trace = _check()
    assert fakes.lister_calls == 2 and fakes.checker_calls == []
    assert trace.lister_failed and trace.use_fallback and trace.fallback_reason == tc.FALLBACK_LISTER_FAILED
    assert trace.label is None and trace.pieces == []


def test_zero_pieces_fall_back_to_the_auditor_without_a_checker_call(monkeypatch):
    fakes = Fakes(monkeypatch, lister=[[]])
    trace = _check()
    assert fakes.checker_calls == [] and not trace.lister_failed
    assert trace.use_fallback and trace.fallback_reason == tc.FALLBACK_ZERO_PIECES


@pytest.mark.parametrize("first", [RuntimeError("api down"), "not json", json.dumps({"pieces": "nope"})])
def test_checker_is_retried_once_on_a_call_failure_or_invalid_json(monkeypatch, first):
    fakes = Fakes(monkeypatch, checker=[first, GOOD])
    trace = _check()
    assert len(fakes.checker_calls) == 2 and not trace.checker_failed and trace.label == tc.LABEL_PARTIAL


def test_checker_failing_twice_is_could_not_check_and_falls_back(monkeypatch):
    fakes = Fakes(monkeypatch, checker=["not json", RuntimeError("api down")])
    trace = _check()
    assert len(fakes.checker_calls) == 2 and trace.checker_failed
    assert [(p.state, p.reason) for p in trace.pieces] == [(tc.COULD_NOT_CHECK, tc.CNC_CHECKER_FAILED)] * 2
    assert trace.use_fallback and trace.fallback_reason == tc.FALLBACK_COULD_NOT_CHECK and trace.label is None
    assert trace.n_failed == 0   # could-not-check never counts as failed


def test_repeated_or_unknown_piece_ids_are_treated_like_invalid_json(monkeypatch):
    repeated = json.dumps({"pieces": [
        {"piece_id": 1, "answer": "no_row", "cells": []}, {"piece_id": 1, "answer": "no_row", "cells": []},
    ]})
    unknown = json.dumps({"pieces": [{"piece_id": 5, "answer": "no_row", "cells": []}]})
    fakes = Fakes(monkeypatch, checker=[repeated, unknown])
    trace = _check()
    assert len(fakes.checker_calls) == 2 and trace.checker_failed and trace.use_fallback


def test_a_piece_the_checker_left_out_is_could_not_check_not_a_failed_call(monkeypatch):
    partial = json.dumps({"pieces": [{"piece_id": 2, "answer": "no_row", "cells": []}]})
    fakes = Fakes(monkeypatch, checker=[partial])
    trace = _check()
    assert len(fakes.checker_calls) == 1 and not trace.checker_failed
    assert [(p.state, p.reason) for p in trace.pieces] == [
        (tc.COULD_NOT_CHECK, tc.CNC_MISSING_ANSWER), (tc.FAILED, None),
    ]
    assert trace.label == tc.LABEL_PARTIAL and not trace.use_fallback


def test_a_guard_failure_is_could_not_check(monkeypatch):
    invented = json.dumps({"pieces": [
        {"piece_id": 1, "answer": "not_backed",
         "cells": [{"table": 1, "row_label": "Bravo sorter", "column_label": "Small", "value": "12.3"}]},
        {"piece_id": 2, "answer": "backed",
         "cells": [{"table": 1, "row_label": "Bravo sorter", "column_label": "Large", "value": "36.9"}]},
    ]})
    Fakes(monkeypatch, checker=[invented])
    trace = _check()
    assert trace.pieces[0].state == tc.COULD_NOT_CHECK and trace.pieces[0].guard_reasons == [tc.GUARD_VALUE_MISSING]
    assert trace.n_failed == 0 and trace.use_fallback and trace.fallback_reason == tc.FALLBACK_COULD_NOT_CHECK


def test_a_base_exception_is_never_retried_or_swallowed(monkeypatch):
    fakes = Fakes(monkeypatch, checker=[Stop(), GOOD])
    with pytest.raises(Stop):
        _check()
    assert len(fakes.checker_calls) == 1

    fakes = Fakes(monkeypatch, lister=[Stop(), ITEMS])
    with pytest.raises(Stop):
        _check()
    assert fakes.lister_calls == 1
