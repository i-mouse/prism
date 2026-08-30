"""Correlation ID threading across the Python service.

Both entry points (api.py's FastAPI middleware, main.py's RabbitMQ consumer
loop) set this ContextVar for the duration of one request/message, so every
downstream call - including plain print() logging, which is what this
codebase uses everywhere instead of a structured logger - can read it back
without threading it through every function signature.
"""
from contextvars import ContextVar

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str | None) -> None:
    correlation_id_var.set(correlation_id)
