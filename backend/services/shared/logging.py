"""Structured logging helpers shared across services."""

from __future__ import annotations

import logging
import sys
from typing import Optional
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import structlog


_TENANT_HEADER = "X-Tenant-ID"
_REQUEST_ID_HEADER = "X-Request-ID"
_TRACE_ID_HEADER = "X-Trace-ID"


def configure_logging(service_name: str, level: int = logging.INFO) -> structlog.stdlib.BoundLogger:
    """Configure structlog to emit JSON logs with contextual information."""

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger().bind(service=service_name)


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    """Attach request context to structlog and log request lifecycle events."""

    def __init__(self, app, *, logger: Optional[structlog.stdlib.BoundLogger] = None) -> None:
        super().__init__(app)
        self._logger = logger or structlog.get_logger()

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid4())
        trace_id = request.headers.get(_TRACE_ID_HEADER) or request_id
        tenant_id = request.headers.get(_TENANT_HEADER) or request.query_params.get("tenant_id")

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            path=request.url.path,
            method=request.method,
        )

        try:
            response = await call_next(request)
            self._logger.info("request_completed", status_code=response.status_code)
            return response
        except Exception:
            self._logger.exception("request_failed")
            raise
        finally:
            structlog.contextvars.clear_contextvars()
