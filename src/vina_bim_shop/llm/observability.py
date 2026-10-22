"""Content-free OpenTelemetry export for the compact EDAI2 runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_CONFIGURED = False


def configure_tracing(
    service_name: str,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Export spans to the configured OTLP/HTTP endpoint once per process.

    No endpoint means no provider is installed, which keeps unit tests and
    local runs free of network side effects.
    """

    global _CONFIGURED
    settings = os.environ if environ is None else environ
    endpoint = settings.get("EDAI2_OTEL_ENDPOINT")
    if not endpoint or _CONFIGURED:
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _CONFIGURED = True
    return True


__all__ = ["configure_tracing"]
