"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware import RequestContextMiddleware
from api.routes.health import router as health_router
from config.settings import get_settings
from core.exceptions import BaseError, NotFoundError, ValidationError
from core.logging import configure_logging
from observability.middleware import ObservabilityMiddleware
from observability.tracing import configure_tracing

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    settings = get_settings()
    configure_logging()
    configure_tracing()
    logger.info(
        "veriducta_startup",
        env=settings.env.value,
        host=settings.api.host,
        port=settings.api.port,
    )
    yield
    logger.info("veriducta_shutdown")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        Fully configured FastAPI instance ready to serve requests.
    """
    settings = get_settings()

    app = FastAPI(
        title="Veriducta",
        description=(
            "RAG pipeline observability - causal root-cause attribution for answer failures."
        ),
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    return app


def _register_middleware(app: FastAPI) -> None:
    """Attach all middleware to *app*."""
    settings = get_settings()

    # Middleware is applied in reverse registration order (last registered = outermost).
    # RequestContextMiddleware must wrap every request so correlation IDs are
    # present in all log lines, including those from CORSMiddleware itself.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(ObservabilityMiddleware)


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(BaseError)
    async def base_error_handler(request: Request, exc: BaseError) -> JSONResponse:
        logger.error("unhandled_domain_error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=500,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
        )


def _register_routers(app: FastAPI) -> None:
    """Mount all API routers."""
    app.include_router(health_router, prefix="/api/v1", tags=["health"])


def main() -> None:
    """Entry-point for running the server via ``uvicorn``."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host=settings.api.host,
        port=settings.api.port,
        workers=settings.api.workers,
        reload=settings.api.reload,
    )


if __name__ == "__main__":
    main()
