"""ASGI observability middleware.

Creates a fresh :class:`RequestContext` for every incoming HTTP request,
binds it to the current task via :func:`set_current_context`, and records
the active request count in the ``ACTIVE_REQUESTS`` Prometheus gauge.

This middleware is the canonical place where per-request correlation IDs
originate.  Downstream pipeline components retrieve the context via
:func:`get_current_context` without requiring it as an explicit parameter.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from observability.context import RequestContext, set_current_context
from observability.metrics import ACTIVE_REQUESTS
from utils.hashing import sha256_str
from utils.ids import trace_id as new_trace_id


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for per-request context propagation and metrics.

    Registers one ``ACTIVE_REQUESTS`` gauge increment on request start and
    decrements it on completion (including errors).  Creates a
    :class:`RequestContext` seeded from the ``X-Request-Id`` and
    ``X-Trace-Id`` headers when present, or generates fresh IDs otherwise.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request and propagate observability context.

        Args:
            request: Incoming Starlette request.
            call_next: Next ASGI callable in the middleware stack.

        Returns:
            HTTP response from the downstream handler.
        """
        request_id = request.headers.get("X-Request-Id", new_trace_id())
        trace_id = request.headers.get("X-Trace-Id", new_trace_id())

        query_hash = ""
        body_bytes = await request.body()
        if body_bytes:
            query_hash = sha256_str(body_bytes.decode("utf-8", errors="replace"))

        ctx = RequestContext(
            request_id=request_id,
            trace_id=trace_id,
            query_hash=query_hash,
        )
        set_current_context(ctx)

        ACTIVE_REQUESTS.inc()
        try:
            response = await call_next(request)
        finally:
            ACTIVE_REQUESTS.dec()

        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        return response
