"""
Request ID middleware for end-to-end request tracing.

Every inbound request gets a unique request_id (taken from the X-Request-ID header
if provided by the caller, otherwise generated as a UUID4). The ID is:
  - Bound into structlog contextvars so it appears in every log line during the request
  - Returned in the X-Request-ID response header for client-side correlation
  - Logged at request start and request completion with timing info
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to each request and bind it into the log context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind request_id into structlog context for this request's lifetime
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response
