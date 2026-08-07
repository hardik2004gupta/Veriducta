"""Per-request correlation context propagated via contextvars.

Every request flowing through the pipeline binds a :class:`RequestContext`
to the current async task.  All pipeline components can read it without
requiring explicit parameter threading.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime

from utils.ids import trace_id as new_trace_id


@dataclass
class RequestContext:
    """Correlation context for a single pipeline request.

    Args:
        request_id: Unique identifier for the HTTP request.
        trace_id: Distributed trace identifier (propagated via X-Trace-Id header).
        query_hash: SHA-256 of the query string for deduplication.
        started_at: UTC timestamp when the request was received.
        metadata: Optional caller-supplied key-value pairs.
    """

    request_id: str = field(default_factory=new_trace_id)
    trace_id: str = field(default_factory=new_trace_id)
    query_hash: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = field(default_factory=dict)

    def elapsed_ms(self) -> float:
        """Return milliseconds elapsed since :attr:`started_at`."""
        return (datetime.now(UTC) - self.started_at).total_seconds() * 1000.0


_ctx_var: ContextVar[RequestContext | None] = ContextVar("veriducta_request_context", default=None)


def get_current_context() -> RequestContext | None:
    """Return the active :class:`RequestContext` for the current async task.

    Returns:
        :class:`RequestContext` or ``None`` if called outside a request.
    """
    return _ctx_var.get()


def set_current_context(ctx: RequestContext) -> None:
    """Bind *ctx* to the current async task.

    Args:
        ctx: :class:`RequestContext` to activate.
    """
    _ctx_var.set(ctx)


def require_context() -> RequestContext:
    """Return the active :class:`RequestContext`.

    Raises:
        RuntimeError: If called outside an active request context.
    """
    ctx = _ctx_var.get()
    if ctx is None:
        raise RuntimeError(
            "No active RequestContext — ensure ObservabilityMiddleware is registered."
        )
    return ctx
