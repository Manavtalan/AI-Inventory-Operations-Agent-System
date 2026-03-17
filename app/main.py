"""
AI Inventory & Operations Intelligence System — FastAPI Application Entry Point

Phase 0, Step 0.4 — Settings & Secrets Management:
  - All configuration now sourced from app.core.config.settings (Pydantic BaseSettings)
  - No raw os.getenv() calls — missing required vars crash at import with a clear error

Phase 0, Step 0.3 — Core Application Setup:
  - Application factory pattern (create_app)
  - Structured JSON logging via structlog
  - Request ID middleware (X-Request-ID tracing)
  - Global exception handlers
  - Startup validation (Postgres + Redis connectivity)
  - Enhanced /health endpoint with service status
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler, global_exception_handler
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware

# Configure logging immediately — must happen before any get_logger() call
# so that cache_logger_on_first_use captures the correct configuration.
configure_logging(log_level=settings.log_level, json_logs=settings.json_logs)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Service connectivity checks
# ---------------------------------------------------------------------------


async def _check_postgres() -> bool:
    """Attempt a lightweight Postgres connection. Returns True if reachable."""
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            timeout=5,
        )
        await conn.close()
        return True
    except Exception as exc:
        logger.warning("service_check", service="database", status="unavailable", error=str(exc))
        return False


async def _check_redis() -> bool:
    """Attempt a Redis PING. Returns True if reachable."""
    try:
        client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            socket_connect_timeout=5,
        )
        await client.ping()
        await client.aclose()
        return True
    except Exception as exc:
        logger.warning("service_check", service="redis", status="unavailable", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


async def _validate_startup() -> None:
    """Check service connectivity on startup and log results.

    Pydantic already enforces required env vars at import time (missing vars
    raise ValidationError before we get here). This function only checks
    that Postgres and Redis are actually reachable.

    In production, unreachable services abort startup. In development,
    they log a warning and continue so local work can proceed without Docker.
    """
    db_ok = await _check_postgres()
    redis_ok = await _check_redis()

    logger.info(
        "startup_complete",
        app_env=settings.app_env,
        database="ok" if db_ok else "degraded",
        redis="ok" if redis_ok else "degraded",
    )

    if settings.is_production and not (db_ok and redis_ok):
        raise RuntimeError("Critical services unreachable — refusing to start in production.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle: startup validation and graceful shutdown."""
    await _validate_startup()
    yield
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """Application factory — build and configure the FastAPI instance."""
    app = FastAPI(
        title="AI Inventory & Operations Intelligence System",
        description="Automated inventory reconciliation and reporting for D2C brands.",
        version="0.1.0",
        lifespan=lifespan,
        # Hide interactive docs in production
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    # Middleware
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Routers (additional routers registered here as phases progress)
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routes on the FastAPI instance."""

    @app.get("/health", tags=["system"], summary="Service health check")
    async def health_check() -> JSONResponse:
        """Check application and dependent service health.

        Returns 200 when all services are reachable, 503 when any are degraded.
        """
        db_ok = await _check_postgres()
        redis_ok = await _check_redis()

        all_ok = db_ok and redis_ok
        payload = {
            "status": "ok" if all_ok else "degraded",
            "version": "0.1.0",
            "services": {
                "database": "ok" if db_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
            },
        }
        http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(content=payload, status_code=http_status)


# ---------------------------------------------------------------------------
# Module-level app instance (used by uvicorn / Docker CMD)
# ---------------------------------------------------------------------------

app = create_app()
