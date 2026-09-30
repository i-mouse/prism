"""B3.3 follow-up (PR 1): a failed paper leaves the progress stepper stuck.

Covers: ProgressEmitter.emit_failed carries stage="failed" plus a reason;
every terminal except-block in main.py's consumer loop calls it; the
generic catch-all only does so on the truly terminal attempt, never a
retryable one (Phase 1b Check 1). Manual end-to-end cases (corrupt PDF,
password-protected PDF, scanned PDF, through the real upload flow) are
listed in the PR report, not faked here - main()'s consumer loop itself has
no test harness (RabbitMQ/Postgres/blob storage), before or after this PR.
"""
import asyncio
import inspect
import json

import pytest

import main
from extraction.pipeline_events import ProgressEmitter


# ---------------------------------------------------------------------------
# ProgressEmitter.emit_failed: stage="failed" + reason reach the outgoing event
# ---------------------------------------------------------------------------

class _FakeExchange:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish(self, message, routing_key):
        self.published.append((routing_key, json.loads(message.body.decode())))


class _FakeChannel:
    def __init__(self):
        self.default_exchange = _FakeExchange()


def test_emit_failed_publishes_stage_failed_with_reason():
    channel = _FakeChannel()
    emitter = ProgressEmitter(channel, file_id="file-1", chat_id="chat-1")

    asyncio.run(emitter.emit_failed("extracting", reason="test reason"))

    assert len(channel.default_exchange.published) == 1
    routing_key, payload = channel.default_exchange.published[0]
    assert routing_key == "document_processed_queue"
    assert payload == {
        "fileId": "file-1",
        "chatId": "chat-1",
        "stage": "failed",
        "failedStage": "extracting",
        "reason": "test reason",
    }


# ---------------------------------------------------------------------------
# Reason constants: short, static, content-free (log hygiene - these now
# reach the screen via PaperClaimsResponse.FailureReason and the live
# ExtractionProgress event, not just server logs)
# ---------------------------------------------------------------------------

REASON_CONSTANTS = (
    "CORRUPT_PDF_REASON",
    "PASSWORD_PROTECTED_REASON",
    "SCANNED_PDF_REASON",
    "FK_VIOLATION_REASON",
    "GENERIC_FAILURE_REASON",
)


@pytest.mark.parametrize("name", REASON_CONSTANTS)
def test_reason_constant_is_short_static_string(name):
    reason = getattr(main, name)
    assert isinstance(reason, str)
    assert 0 < len(reason) < 80
    # Content-free: never built from an exception, so it can't contain
    # interpolated exception-message text at runtime.
    assert "{" not in reason and "}" not in reason


def test_password_protected_exception_message_matches_reason_constant(tmp_path):
    import fitz

    path = str(tmp_path / "encrypted.pdf")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret text")
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    doc.close()

    with pytest.raises(main.PdfPasswordProtectedError) as exc_info:
        main.extract_pdf_text_sync(path)
    assert str(exc_info.value) == main.PASSWORD_PROTECTED_REASON


def test_scanned_pdf_exception_message_matches_reason_constant():
    with pytest.raises(main.ScannedPdfError) as exc_info:
        main._raise_if_no_extractable_text("")
    assert str(exc_info.value) == main.SCANNED_PDF_REASON


# ---------------------------------------------------------------------------
# Source-level guards for main()'s consumer loop. main() itself has no test
# harness (needs a live RabbitMQ connection, Postgres pool, blob storage,
# and a compiled LangGraph agent before the loop it's even reachable) - these
# lock in the two invariants Phase 1b Check 1 and the Phase 1 report found
# broken, by inspecting the actual source of the running function rather
# than re-describing it by hand.
# ---------------------------------------------------------------------------

def _except_block_source(main_source: str, marker: str) -> str:
    start = main_source.index(marker)
    next_except = main_source.find("\n                            except ", start + 1)
    end = next_except if next_except != -1 else start + 3000
    return main_source[start:end]


@pytest.mark.parametrize("marker", [
    "except fitz.FileDataError as e:",
    "except PdfPasswordProtectedError as e:",
    "except ScannedPdfError as e:",
    "except psycopg.errors.ForeignKeyViolation as e:",
])
def test_terminal_branch_calls_emit_failed(marker):
    source = inspect.getsource(main.main)
    block = _except_block_source(source, marker)
    assert "emit_failed(" in block, f"{marker} does not call emitter.emit_failed(...)"


def test_generic_catchall_emits_failed_only_on_terminal_attempt():
    source = inspect.getsource(main.main)
    start = source.index("except Exception as e:", source.index("TRANSIENT ERROR"))
    block = source[start:]
    terminal_check_pos = block.index("if attempt >= MAX_ATTEMPTS:")
    emit_failed_pos = block.index("emit_failed(")
    assert emit_failed_pos > terminal_check_pos, (
        "emit_failed must fire only inside the terminal (attempt >= MAX_ATTEMPTS) "
        "branch - firing before that check would show a terminal failed state "
        "for an attempt that's about to be silently retried"
    )
