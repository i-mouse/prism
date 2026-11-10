import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    """No test may build a real google-genai client or call LiteLLM: Application Default
    Credentials exist on the dev machine, so a Vertex client built by mistake could reach
    the network. extraction/llm_backend.py builds every genai client through
    _client_factory and the grounding call goes through litellm.acompletion; both refuse
    here. A test that needs either installs its own fake (monkeypatch.setattr runs after
    this fixture and wins). The active backend is reset to AI Studio for every test."""
    import litellm

    from extraction import llm_backend

    def _forbidden_client(*args, **kwargs):
        raise AssertionError(
            f"a test tried to build a real google-genai client (args={args}, kwargs={sorted(kwargs)}); "
            f"patch extraction.llm_backend._client_factory or engine._build_client with a fake"
        )

    async def _forbidden_completion(*args, **kwargs):
        raise AssertionError("a test tried to call the real litellm.acompletion; patch it with a fake")

    monkeypatch.setattr(llm_backend, "_client_factory", _forbidden_client)
    monkeypatch.setattr(llm_backend, "_active", llm_backend.AISTUDIO)
    monkeypatch.setattr(litellm, "acompletion", _forbidden_completion)
