"""Typed progress events for the extraction pipeline.

There is no separate SignalR broadcaster in the Python service - the
existing DocumentProcessed completion message main.py publishes is a
plain JSON message sent straight to the "document_processed_queue"
RabbitMQ queue via the channel's default exchange, consumed by
Prism.ApiService's RabbitMqListenerService and forwarded to SignalR
clients from there. ProgressEmitter reuses that exact path: it
publishes to the same queue over the same channel, so no new RabbitMQ
wiring is needed. The C# listener only needs a new branch that
recognizes payloads carrying a "stage" field.
"""
import json
from typing import Literal, Optional, TypedDict

import aio_pika

QUEUE_NAME = "document_processed_queue"

Stage = Literal["preparing", "extracting", "grounding", "finalizing", "done", "failed"]


class ExtractionProgressEvent(TypedDict, total=False):
    fileId: str
    chatId: str
    stage: Stage
    completed: Optional[int]
    total: Optional[int]
    failedStage: Optional[Stage]
    detail: Optional[str]


class ProgressEmitter:
    """Publishes typed extraction-stage events to document_processed_queue.

    Injected per-message in main.py's processing loop and passed as the
    on_progress callback into ground_extraction for the per-claim counter.
    """

    def __init__(self, channel, file_id: str, chat_id: str):
        self._channel = channel
        self._file_id = file_id
        self._chat_id = chat_id

    async def _publish(self, payload: ExtractionProgressEvent) -> None:
        await self._channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(payload).encode()),
            routing_key=QUEUE_NAME,
        )

    async def emit_stage(self, stage: Stage) -> None:
        await self._publish({
            "fileId": self._file_id,
            "chatId": self._chat_id,
            "stage": stage,
        })

    async def emit_stage_detail(self, stage: Stage, detail: str) -> None:
        await self._publish({
            "fileId": self._file_id,
            "chatId": self._chat_id,
            "stage": stage,
            "detail": detail,
        })

    async def emit_grounding_progress(self, done: int, total: int) -> None:
        await self._publish({
            "fileId": self._file_id,
            "chatId": self._chat_id,
            "stage": "grounding",
            "completed": done,
            "total": total,
        })

    async def emit_failed(self, failed_stage: Stage) -> None:
        await self._publish({
            "fileId": self._file_id,
            "chatId": self._chat_id,
            "stage": "failed",
            "failedStage": failed_stage,
        })
