"""OpenTelemetry span attribute helpers.

Provides a single function that stamps common Veriducta attributes onto any
OTel span.  All pipeline stages call this after computing their outputs so
every span carries the same standard set of fields for querying in Tempo or
Jaeger.
"""

from __future__ import annotations

from opentelemetry.trace import Span


def record_span_attributes(
    span: Span,
    *,
    config_hash: str = "",
    latency_ms: float = 0.0,
    model: str = "",
    trace_id: str = "",
    error: str = "",
) -> None:
    """Stamp standard Veriducta attributes on *span*.

    Call this inside the span context after the operation completes (or fails).
    All arguments are keyword-only to prevent positional mistakes.

    Args:
        span: Active :class:`opentelemetry.trace.Span` to annotate.
        config_hash: SHA-256 of the :class:`ConfigurationSnapshot` for this call.
        latency_ms: Wall-clock latency of the operation in milliseconds.
        model: Model identifier used for the operation, e.g.
               ``"claude-sonnet-4-6"`` or ``"BAAI/bge-large-en-v1.5"``.
        trace_id: Internal Veriducta trace ID (distinct from the OTel trace ID).
        error: Non-empty string when the operation failed; becomes the OTel
               ``error.message`` attribute and marks the span as an error.
    """
    if config_hash:
        span.set_attribute("veriducta.config_hash", config_hash)
    if latency_ms:
        span.set_attribute("veriducta.latency_ms", latency_ms)
    if model:
        span.set_attribute("veriducta.model", model)
    if trace_id:
        span.set_attribute("veriducta.trace_id", trace_id)
    if error:
        span.set_attribute("error.message", error)
        span.set_attribute("error", True)
