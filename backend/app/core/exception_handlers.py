from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import DomainError, AIServiceUnavailableError
from app.core.logging import get_logger, request_id_var
from app.integrations.llm.errors import LLMError, to_ai_service_unavailable

logger = get_logger("app.errors")


def _body(code: str, message: str, details: dict | None = None) -> dict:
    """
    One response shape for every error, so clients parse a single contract.

    The request id is included so a user-visible failure can be traced to a log
    line without asking them to reproduce it.
    """
    payload = {"error": {"code": code, "message": message}, "requestId": request_id_var.get()}
    if details:
        payload["error"]["details"] = details
    # `detail` is kept alongside for compatibility with existing clients and
    # FastAPI's own conventions.
    payload["detail"] = message
    return payload


def _ai_unavailable_body(exc: AIServiceUnavailableError) -> dict:
    """Flat AI availability contract plus the shared error envelope."""
    payload = _body(exc.code, exc.message, exc.details)
    payload.update(
        {
            "code": exc.code,
            "message": exc.message,
            "provider": exc.provider,
            "retryable": exc.retryable,
        }
    )
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AIServiceUnavailableError)
    async def _ai_unavailable(_: Request, exc: AIServiceUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_ai_unavailable_body(exc))

    @app.exception_handler(LLMError)
    async def _llm(_: Request, exc: LLMError) -> JSONResponse:
        # Any uncaught provider failure becomes a structured 503 instead of a
        # hung/CORS-looking browser network error.
        mapped = to_ai_service_unavailable(exc)
        logger.warning(
            "AI provider failure (%s/%s): %s", exc.provider, exc.reason, exc.message
        )
        return JSONResponse(status_code=mapped.status_code, content=_ai_unavailable_body(mapped))

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        if isinstance(exc, AIServiceUnavailableError):
            return JSONResponse(status_code=exc.status_code, content=_ai_unavailable_body(exc))
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": ".".join(str(p) for p in err.get("loc", [])[1:]), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body("validation_error", "Request validation failed.", {"fields": fields}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _database(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        # The driver message can leak schema detail, so it is logged and not returned.
        logger.exception("database error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500, content=_body("internal_error", "A database error occurred.")
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500, content=_body("internal_error", "An unexpected error occurred.")
        )
