"""
SQLAlchemy event hooks that emit OTel spans for every DB query.

Span attributes: query_hash, duration_ms, tenant_db

Usage:
    from platform.db_instrumentation import instrument_engine
    instrument_engine(engine, tenant_db="tenant_abc")
"""

import hashlib
import time
from typing import Any

from opentelemetry import trace
from sqlalchemy import event
from sqlalchemy.engine import Engine

from platform.logging_config import get_logger

logger = get_logger("db_instrumentation")


def instrument_engine(engine: Engine, tenant_db: str = "") -> None:
    """Attach before/after cursor execute hooks to emit DB query spans."""

    tracer = trace.get_tracer("sqlalchemy")
    _spans: dict[int, tuple[Any, float]] = {}  # cursor_id → (span, start_time)

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        query_hash = hashlib.md5(statement.encode(), usedforsecurity=False).hexdigest()[:12]
        span = tracer.start_span(f"db.query.{query_hash}")
        span.set_attribute("query_hash", query_hash)
        span.set_attribute("tenant_db", tenant_db)
        _spans[id(cursor)] = (span, time.monotonic())

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        entry = _spans.pop(id(cursor), None)
        if entry is None:
            return
        span, start = entry
        duration_ms = (time.monotonic() - start) * 1000
        span.set_attribute("duration_ms", round(duration_ms, 2))
        span.end()

    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        statement = getattr(exception_context, "statement", "")
        query_hash = hashlib.md5(
            (statement or "").encode(), usedforsecurity=False
        ).hexdigest()[:12]
        logger.error(
            "DB query error",
            extra={"query_hash": query_hash, "tenant_db": tenant_db},
        )
