"""
OpenTelemetry setup for OpenEMR Agent per PRD §6.2.

Traces are compatible with Datadog, CloudWatch, and other OTLP backends.
Set OTEL_EXPORTER_OTLP_ENDPOINT for production (e.g., Datadog agent).
"""

import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.config import settings

logger = logging.getLogger(__name__)

TRACER = trace.get_tracer("openemr-agent", "0.1.0")


def _create_span_processor() -> BatchSpanProcessor:
    """Create span processor: OTLP if endpoint configured, else console for dev."""
    endpoint = settings.otel_exporter_otlp_endpoint or ""
    if endpoint:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        return BatchSpanProcessor(exporter)
    return BatchSpanProcessor(ConsoleSpanExporter())


def setup_telemetry(app: Any) -> None:
    """
    Initialize OpenTelemetry and instrument FastAPI.
    Call once at startup (e.g., in main.py).
    """
    resource = Resource.create(
        {
            "service.name": "openemr-agent",
            "service.version": "0.1.0",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(_create_span_processor())
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,/,/health",
    )
    logger.info("Telemetry initialized (OTLP endpoint: %s)", settings.otel_exporter_otlp_endpoint or "console")


def get_tracer() -> trace.Tracer:
    """Return the app tracer for custom spans (e.g., LLM invocation)."""
    return TRACER
