"""Custom ASGI middleware for request correlation and timing."""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a unique request-ID and trace-ID to every incoming request.

    The IDs are injected into structlog context so every log line emitted
    during the request carries them automatically.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process a single request: stamp IDs, log timing, clear context."""
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id

        logger.info(
            "request_completed",
            status_code=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        return response
