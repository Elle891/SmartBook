"""
Celery application with OTel span instrumentation.

Every task that inherits from InstrumentedTask automatically emits a span with:
  task_name, account_set_id, duration_ms, status
"""

import time
from typing import Any

from celery import Celery, Task
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from platform.logging_config import get_logger

logger = get_logger("celery")

# ---------------------------------------------------------------------------
# Celery app
# ---------------------------------------------------------------------------

celery_app = Celery(
    "smart_accounting",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=[
        "app.tasks",  # populated as modules are added
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "bank-sync-daily": {
            "task": "bank.sync_scheduled",
            "schedule": 86400.0,
        },
        "payment-confirm-scheduled": {
            "task": "payment.confirm_scheduled",
            "schedule": 60.0,
        },
    },
)

# ---------------------------------------------------------------------------
# OTel tracer for Celery
# ---------------------------------------------------------------------------

def _get_celery_tracer() -> trace.Tracer:
    resource = Resource.create({"service.name": "celery-worker"})
    provider = TracerProvider(resource=resource)
    jaeger_exporter = JaegerExporter(agent_host_name="jaeger", agent_port=6831)
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    # Only set if not already configured (avoids overwriting FastAPI provider)
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(provider)
    return trace.get_tracer("celery-worker")


_tracer: trace.Tracer | None = None


def get_tracer() -> trace.Tracer:
    global _tracer
    if _tracer is None:
        _tracer = _get_celery_tracer()
    return _tracer


# ---------------------------------------------------------------------------
# Instrumented base task
# ---------------------------------------------------------------------------

class InstrumentedTask(Task):
    """Base Celery task that wraps execution in an OTel span."""

    abstract = True

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        task_name = self.name or self.__class__.__name__
        account_set_id = kwargs.get("account_set_id", "")
        tracer = get_tracer()
        start = time.monotonic()

        with tracer.start_as_current_span(f"celery.{task_name}") as span:
            span.set_attribute("task_name", task_name)
            span.set_attribute("account_set_id", str(account_set_id))
            try:
                result = super().__call__(*args, **kwargs)
                duration_ms = (time.monotonic() - start) * 1000
                span.set_attribute("duration_ms", round(duration_ms, 2))
                span.set_attribute("status", "success")
                logger.info(
                    "Celery task completed",
                    extra={
                        "task_name": task_name,
                        "account_set_id": account_set_id,
                        "duration_ms": round(duration_ms, 2),
                        "status": "success",
                    },
                )
                return result
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000
                span.set_attribute("duration_ms", round(duration_ms, 2))
                span.set_attribute("status", "error")
                span.record_exception(exc)
                logger.error(
                    "Celery task failed",
                    extra={
                        "task_name": task_name,
                        "account_set_id": account_set_id,
                        "duration_ms": round(duration_ms, 2),
                        "status": "error",
                        "error": str(exc),
                    },
                )
                raise
