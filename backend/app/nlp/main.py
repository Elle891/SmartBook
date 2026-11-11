"""svc-nlp — NLP Assistant Service FastAPI entry point."""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from platform.logging_config import get_logger
from platform.otel_middleware import add_otel_middleware

logger = get_logger("svc-nlp")

app = FastAPI(
    title="Smart Accounting — svc-nlp",
    description="NLP Assistant Service API",
    version="0.1.0",
)

# OpenTelemetry span middleware
add_otel_middleware(app, service_name="svc-nlp")

# Prometheus metrics — exposes /metrics
Instrumentator().instrument(app).expose(app)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
