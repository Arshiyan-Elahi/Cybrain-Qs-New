import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import (
    company_id_var,
    ensure_request_id,
    get_logger,
    log_event,
    logging_flags,
    request_id_var,
    user_id_var,
)

logger = get_logger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assigns a request id, logs the outcome, and echoes the id back.

    An inbound `X-Request-ID` is honoured so a trace survives across services
    and can be quoted by a client in a bug report.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = ensure_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = request_id_var.set(request_id)
        company_token = company_id_var.set(None)
        user_token = user_id_var.set(None)
        started = time.perf_counter()
        flags = logging_flags()

        if flags["log_requests"] and not _is_health(request.url.path):
            log_event(
                logger,
                "http_request_started",
                f"{request.method} {request.url.path}",
                method=request.method,
                path=request.url.path,
            )

        try:
            response = await call_next(request)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if flags["log_requests"] and not _is_health(request.url.path):
                level = 30 if response.status_code >= 500 else 20  # WARNING / INFO
                log_event(
                    logger,
                    "http_request_completed",
                    f"{request.method} {request.url.path} -> {response.status_code}",
                    level=level,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    latency_ms=elapsed_ms,
                )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            log_event(
                logger,
                "http_request_failed",
                f"{request.method} {request.url.path} failed",
                level=40,
                method=request.method,
                path=request.url.path,
                latency_ms=elapsed_ms,
                error_type=type(exc).__name__,
                error_message=str(exc)[:300],
            )
            logger.exception(
                "%s %s failed after %sms", request.method, request.url.path, elapsed_ms
            )
            raise
        finally:
            request_id_var.reset(token)
            company_id_var.reset(company_token)
            user_id_var.reset(user_token)


def _is_health(path: str) -> bool:
    return path in {"/health", "/health/ready"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline hardening headers. Cheap, and absent by default in FastAPI."""

    def __init__(self, app, *, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if self.hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
