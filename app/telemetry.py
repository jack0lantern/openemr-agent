"""
OpenTelemetry setup for OpenEMR Agent per PRD §6.2.

Traces are compatible with Datadog, CloudWatch, and other OTLP backends.
Set OTEL_EXPORTER_OTLP_ENDPOINT for production (e.g., Datadog agent).

LangGraph/LangChain instrumentation via OpenInference captures LLM calls,
tool invocations, and agent workflow spans (OpenInference semantic conventions).
"""

import logging
import os  # AI-generated
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

logger = logging.getLogger(__name__)

TRACER = trace.get_tracer("openemr-agent", "0.1.0")


def _create_span_processor() -> BatchSpanProcessor:
    """Create span processor: OTLP if endpoint configured, else console for dev."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")  # AI-generated
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

    # Instrument LangGraph/LangChain when openinference-instrumentation-langchain is installed
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor

        LangChainInstrumentor().instrument()
        langgraph_instrumented = True
    except ImportError:
        langgraph_instrumented = False

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,/,/health",
    )
    logger.info(
        "Telemetry initialized (OTLP endpoint: %s, LangGraph instrumented: %s)",
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "console",  # AI-generated
        langgraph_instrumented,
    )


def get_tracer() -> trace.Tracer:
    """Return the app tracer for custom spans (e.g., LLM invocation)."""
    return TRACER
