"""PR 1 (Honest status): unit coverage for the failure-routing changes.

Everything here is testable in-process with no broker, DB, or live LLM.
The two manual-upload cases (real scanned PDF, real password-protected PDF
through the full upload flow) are intentionally NOT faked here - see
docs/observability-and-cost-plan.md §6 for the manual test steps.
"""
import asyncio
import os
import tempfile

import fitz
import pytest

import main
import paper_chat.tools as tools
from ai_service import AIService
from paper_chat.agent import check_empty


# ---------------------------------------------------------------------------
# main.py: password-protected / scanned PDF guards (B2.3, B2.4)
# ---------------------------------------------------------------------------

def _make_encrypted_pdf(tmp_path) -> str:
    path = os.path.join(tmp_path, "encrypted.pdf")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret text")
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner123", user_pw="user123")
    doc.close()
    return path


def test_extract_pdf_text_sync_raises_on_password_protected_pdf(tmp_path):
    path = _make_encrypted_pdf(str(tmp_path))
    with pytest.raises(main.PdfPasswordProtectedError):
        main.extract_pdf_text_sync(path)


def test_extract_pdf_text_sync_succeeds_on_normal_pdf(tmp_path):
    path = os.path.join(str(tmp_path), "plain.pdf")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "hello world")
    doc.save(path)
    doc.close()

    text, page_count = main.extract_pdf_text_sync(path)
    assert "hello world" in text
    assert page_count == 1


@pytest.mark.parametrize("blank_text", ["", "   ", "\n\t  \n"])
def test_raise_if_no_extractable_text_raises_on_blank(blank_text):
    with pytest.raises(main.ScannedPdfError):
        main._raise_if_no_extractable_text(blank_text)


def test_raise_if_no_extractable_text_allows_real_text():
    main._raise_if_no_extractable_text("real extracted text")  # must not raise


# ---------------------------------------------------------------------------
# ai_service.py: summary failure must raise, not return an error string (B1.5)
# ---------------------------------------------------------------------------

def test_analyize_text_raises_instead_of_returning_error_string():
    service = AIService()

    async def fake_create(*args, **kwargs):
        raise RuntimeError("upstream LLM failure")

    service.client.chat.completions.create = fake_create

    with pytest.raises(RuntimeError):
        asyncio.run(service.analyize_text(text="paper text"))


def test_analyize_text_raises_on_authentication_error():
    import httpx
    from openai import AuthenticationError

    service = AIService()

    async def fake_create(*args, **kwargs):
        response = httpx.Response(401, request=httpx.Request("POST", "https://example.invalid"))
        raise AuthenticationError("bad key", response=response, body=None)

    service.client.chat.completions.create = fake_create

    with pytest.raises(AuthenticationError):
        asyncio.run(service.analyize_text(text="paper text"))


# ---------------------------------------------------------------------------
# paper_chat/tools.py: a genuine retrieval failure must raise, not return []
# (B1.6-8)
# ---------------------------------------------------------------------------

def test_query_paper_claims_raises_retrieval_error_on_db_failure(monkeypatch):
    async def boom(active_file_id):
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(tools, "_resolve_document_extractor_id", boom)

    with pytest.raises(tools.RetrievalError):
        asyncio.run(tools.query_paper_claims.ainvoke({"active_file_id": "some-file-id"}))


def test_query_paper_chunks_scored_raises_retrieval_error_on_qdrant_failure(monkeypatch):
    async def boom():
        raise RuntimeError("qdrant unreachable")

    monkeypatch.setattr(tools, "_get_ragservice", boom)

    with pytest.raises(tools.RetrievalError):
        asyncio.run(tools.query_paper_chunks_scored(active_file_id="some-file-id", query="q", limit=5))


# ---------------------------------------------------------------------------
# paper_chat/agent.py: check_empty must route a retrieval failure to its own
# refusal, not the "out of scope for this paper" one (B1.6-8)
# ---------------------------------------------------------------------------

def test_check_empty_routes_retrieval_failed_to_refuse_retrieval_error():
    state = {
        "retrieval_failed": True,
        "retrieved_claims": [],
        "retrieved_chunks": [],
        "chunk_scores": [],
        "claim_lookup": "query",
    }
    assert check_empty(state) == "refuse_retrieval_error"


def test_check_empty_still_refuses_out_of_scope_when_retrieval_succeeded_but_empty():
    state = {
        "retrieval_failed": False,
        "retrieved_claims": [],
        "retrieved_chunks": [],
        "chunk_scores": [],
        "claim_lookup": "query",
    }
    assert check_empty(state) == "refuse_out_of_scope"
