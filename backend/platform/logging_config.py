"""
Structured JSON logging to stdout.

Log record format:
  {"timestamp", "level", "service", "account_set_id", "user_id", "trace_id", "message"}

Usage:
    from platform.logging_config import get_logger
    logger = get_logger("svc-accounting")
    logger.info("something happened", extra={"account_set_id": "abc", "user_id": "u1"})
"""

import json
import logging
import sys
from typing import Any

from opentelemetry import trace


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        # Resolve current OTel trace id if available
        span = trace.get_current_span()
        ctx = span.get_span_context()
        trace_id = (
            format(ctx.trace_id, "032x") if ctx and ctx.is_valid else ""
        )

        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "timestamp": ts,
            "level": record.levelname,
            "service": self.service,
            "account_set_id": getattr(record, "account_set_id", ""),
            "user_id": getattr(record, "user_id", ""),
            "trace_id": trace_id,
            "message": record.getMessage(),
        }

        # Merge any extra fields the caller passed
        for key, value in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
                "account_set_id", "user_id",
            }:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service: str, level: int = logging.INFO) -> None:
    """Call once at application startup to configure root logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter(service))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(service: str) -> logging.Logger:
    """Return a logger pre-configured with JSON output for *service*."""
    configure_logging(service)
    return logging.getLogger(service)
