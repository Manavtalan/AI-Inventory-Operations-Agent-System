"""
Custom exception classes and FastAPI exception handlers.

All unhandled exceptions are caught, logged with full context (including request_id),
and returned as structured JSON responses. Stack traces are never exposed to clients.
"""

import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Base application exception. All domain errors should inherit from this."""

    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, **context) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class NotFoundError(AppError):
    """Resource not found."""

    http_status = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationError(AppError):
    """Input validation error."""

    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class ExternalServiceError(AppError):
    """Upstream / third-party service failure (Shopify, WhatsApp, etc.)."""

    http_status = status.HTTP_502_BAD_GATEWAY
    error_code = "external_service_error"


class ConflictError(AppError):
    """Resource state conflict (e.g. duplicate entry)."""

    http_status = status.HTTP_409_CONFLICT
    error_code = "conflict"


# ---------------------------------------------------------------------------
# Exception handlers (registered on the FastAPI app in main.py)
# ---------------------------------------------------------------------------


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle known AppError subclasses — log and return structured response."""
    logger.warning(
        exc.error_code,
        message=exc.message,
        path=request.url.path,
        method=request.method,
        **exc.context,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": exc.error_code,
            "message": exc.message,
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — log with full traceback, hide details from client."""
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )
