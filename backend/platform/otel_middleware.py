"""
OpenTelemetry middleware for FastAPI.

Instruments every request with a span carrying:
  account_set_id, user_id, operation, duration_ms, status_code

Jaeger export is best-effort: local/dev starts even when the exporter or
agent is unavailable (version skew / missing Docker Jaeger).
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


def _setup_tracer(service_name: str) -> trace.Tracer:
    """Configure TracerProvider; attach Jaeger exporter when available."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        jaeger_exporter = JaegerExporter(
            agent_host_name="jaeger",
            agent_port=6831,
        )
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Jaeger exporter unavailable (%s); continuing with local TracerProvider only",
            exc,
        )

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


class OTelSpanMiddleware(BaseHTTPMiddleware):
    """Emit an OTel span for every HTTP request with accounting context attributes."""

    def __init__(self, app: ASGIApp, tracer: trace.Tracer) -> None:
        super().__init__(app)
        self.tracer = tracer

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        operation = f"{request.method} {request.url.path}"
        start = time.monotonic()

        # Extract context from JWT claims if already decoded by auth middleware
        account_set_id = request.headers.get("x-account-set-id", "")
        user_id = request.headers.get("x-user-id", "")

        with self.tracer.start_as_current_span(operation) as span:
            span.set_attribute("account_set_id", account_set_id)
            span.set_attribute("user_id", user_id)
            span.set_attribute("operation", operation)

            response = await call_next(request)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("duration_ms", round(duration_ms, 2))
            span.set_attribute("status_code", response.status_code)

        return response


def add_otel_middleware(app: FastAPI, service_name: str) -> None:
    """Wire up OTel tracing to a FastAPI app."""
    tracer = _setup_tracer(service_name)
    app.add_middleware(OTelSpanMiddleware, tracer=tracer)
