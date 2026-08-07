"""Observability infrastructure — Prometheus metrics, OpenTelemetry tracing, evidence log."""

from observability.context import (
    RequestContext,
    get_current_context,
    require_context,
    set_current_context,
)
from observability.evidence_log import EvidenceLogWriter
from observability.middleware import ObservabilityMiddleware
from observability.otel import record_span_attributes
from observability.rotation import LogRotator
from observability.sqlite_index import EvidenceIndex, IndexEntry
from observability.trace_store import TraceStore

__all__ = [
    "EvidenceIndex",
    "EvidenceLogWriter",
    "IndexEntry",
    "LogRotator",
    "ObservabilityMiddleware",
    "RequestContext",
    "TraceStore",
    "get_current_context",
    "record_span_attributes",
    "require_context",
    "set_current_context",
]
