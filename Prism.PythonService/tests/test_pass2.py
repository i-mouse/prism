"""Unit tests for extraction/pass2.py's run_pass2: bounded concurrency and
per-window failure handling. No LLM calls - extraction.engine's
_call_gemini_structured is faked.
"""
import asyncio

from extraction import engine, pass2
from extraction.engine import AUDIT_STRUCTURE_CONCURRENCY
from extraction.pass2 import run_pass2


def test_one_failing_window_is_logged_counted_and_others_still_return(monkeypatch):
    windows = ["WINDOW_MARKER_0 text", "WINDOW_MARKER_1 text", "WINDOW_MARKER_2 text"]
    monkeypatch.setattr(pass2, "make_windows", lambda paper_text: windows)

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        if "WINDOW_MARKER_1" in user_msg:
            raise RuntimeError("simulated window failure")
        from extraction.pass2 import SentenceListLLM

        marker = "WINDOW_MARKER_0" if "WINDOW_MARKER_0" in user_msg else "WINDOW_MARKER_2"
        return SentenceListLLM(sentences=[f"sentence from {marker}"])

    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)

    sentences, failed_window_count = asyncio.run(run_pass2("irrelevant paper text", chat_id="chat-1"))

    assert failed_window_count == 1
    assert "sentence from WINDOW_MARKER_0" in sentences
    assert "sentence from WINDOW_MARKER_2" in sentences
    assert len(sentences) == 2


def test_concurrency_never_exceeds_audit_structure_concurrency(monkeypatch):
    # Enough windows to comfortably exceed the cap if it were unbounded.
    n_windows = AUDIT_STRUCTURE_CONCURRENCY * 3
    windows = [f"window {i}" for i in range(n_windows)]
    monkeypatch.setattr(pass2, "make_windows", lambda paper_text: windows)

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    async def fake_call_gemini_structured(messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        async with lock:
            in_flight -= 1
        from extraction.pass2 import SentenceListLLM

        return SentenceListLLM(sentences=["s"])

    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)

    sentences, failed_window_count = asyncio.run(run_pass2("irrelevant paper text", chat_id="chat-1"))

    assert failed_window_count == 0
    assert max_in_flight <= AUDIT_STRUCTURE_CONCURRENCY
    assert max_in_flight > 1  # sanity check: calls did run concurrently, just bounded
