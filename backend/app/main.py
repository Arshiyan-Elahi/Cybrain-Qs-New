from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.database import get_engine
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

logger = get_logger("app.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    logger.info(
        "starting %s in %s (ai_features_enabled=%s)",
        settings.app_name,
        settings.environment,
        settings.ai_features_enabled,
    )
    yield
    get_engine().dispose()
    logger.info("shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Application factory.

    Building the app from a settings object (rather than reading globals at
    import time) is what lets tests construct an isolated instance pointed at a
    different database.
    """
    settings = settings or get_settings()
    log_format = "json" if settings.log_json else settings.log_format
    configure_logging(settings.log_level, log_format=log_format)

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
        # A public deployment should not expose schema explorers.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings

    # Order matters: request context is outermost so every log line and every
    # error response carries the request id.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        # Explicit rather than "*", which is unsafe together with credentials.
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness only — deliberately does not touch the database."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["meta"])
    def readiness() -> dict[str, str]:
        """Readiness — a load balancer should not route traffic without a database."""
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
