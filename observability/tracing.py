"""OpenTelemetry tracer configuration and span helpers."""

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from config.settings import get_settings

_log = logging.getLogger(__name__)


def configure_tracing() -> None:
    """Initialise the global OpenTelemetry TracerProvider.

    In production, spans are exported to the configured OTLP endpoint.
    In testing, the no-op provider is used (no export).
    """
    settings = get_settings()

    if settings.is_testing:
        return

    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: settings.observability.service_name,
            ResourceAttributes.SERVICE_VERSION: settings.observability.service_version,
            "deployment.environment": settings.env.value,
        }
    )

    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.observability.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:
        # OTel setup must never crash the application - log and continue without export.
        _log.warning("OTLP exporter unavailable; traces will not be exported.")

    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer from the global provider.

    Args:
        name: Instrumentation scope name, typically ``__name__``.
    """
    return trace.get_tracer(name)
