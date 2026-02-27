"""
AI Inventory & Operations Intelligence System — FastAPI Application Entry Point

Phase 0, Step 0.3 — Core Application Setup:
  - Application factory pattern (create_app)
  - Structured JSON logging via structlog
  - Request ID middleware (X-Request-ID tracing)
  - Global exception handlers
  - Startup validation (Postgres + Redis connectivity)
  - Enhanced /health endpoint with service status
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError, app_error_handler, global_exception_handler
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware

# Configure logging immediately — must happen before any get_logger() call
# so that cache_logger_on_first_use captures the correct configuration.
configure_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    json_logs=os.getenv("APP_ENV", "development") != "development",
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "REDIS_HOST",
    "REDIS_PORT",
]


async def _check_postgres() -> bool:
    """Attempt a lightweight Postgres connection. Returns True if reachable."""
    try:
        conn = await asyncpg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "inventory_ops"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            timeout=5,
        )
        await conn.close()
        return True
    except Exception as exc:
        logger.warning("startup_check", service="database", status="unavailable", error=str(exc))
        return False


async def _check_redis() -> bool:
    """Attempt a Redis PING. Returns True if reachable."""
    try:
        client = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            socket_connect_timeout=5,
        )
        await client.ping()
        await client.aclose()
        return True
    except Exception as exc:
        logger.warning("startup_check", service="redis", status="unavailable", error=str(exc))
        return False


async def _validate_startup() -> None:
    """Run startup checks and log results. Crash in production if critical services are down."""
    app_env = os.getenv("APP_ENV", "development")

    # 1. Check required env vars
    missing = [v for v in _REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        logger.warning("startup_check", check="env_vars", missing=missing)
        if app_env == "production":
            raise RuntimeError(f"Missing required environment variables: {missing}")

    # 2. Check Postgres
    db_ok = await _check_postgres()
    logger.info("startup_check", service="database", status="ok" if db_ok else "unavailable")

    # 3. Check Redis
    redis_ok = await _check_redis()
    logger.info("startup_check", service="redis", status="ok" if redis_ok else "unavailable")

    if app_env == "production" and not (db_ok and redis_ok):
        raise RuntimeError("Critical services unreachable — refusing to start in production.")

    logger.info(
        "startup_complete",
        app_env=app_env,
        database="ok" if db_ok else "degraded",
        redis="ok" if redis_ok else "degraded",
    )


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
    app_env = os.getenv("APP_ENV", "development")

    app = FastAPI(
        title="AI Inventory & Operations Intelligence System",
        description="Automated inventory reconciliation and reporting for D2C brands.",
        version="0.1.0",
        lifespan=lifespan,
        # Hide /docs and /redoc in production
        docs_url=None if app_env == "production" else "/docs",
        redoc_url=None if app_env == "production" else "/redoc",
    )

    # Middleware (outermost = last registered)
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Routers (additional routers added here as phases progress)
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
