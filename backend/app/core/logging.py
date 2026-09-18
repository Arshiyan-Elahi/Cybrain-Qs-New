"""
Structured application logging for Cybrain QS.

Extends the existing request-id ContextVar rather than introducing a second
logging stack. Console format is human-scannable; JSON is available for
production shippers.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.redaction import redact_mapping, sanitize_text

# Set per request by RequestContextMiddleware so every log line, anywhere in
# the call stack, can be tied back to the request that produced it.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
company_id_var: ContextVar[str | None] = ContextVar("company_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

# Optional LLM/RAG call metadata (set by services around complete/search).
llm_call_context_var: ContextVar[dict[str, Any] | None] = ContextVar(
    "llm_call_context", default=None
)

_LOCAL_TZ = ZoneInfo("Asia/Karachi")


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def ensure_request_id(raw: str | None) -> str:
    if raw and raw.strip():
        value = raw.strip()
        return value if value.startswith("req_") else f"req_{value[:24]}"
    return new_request_id()


def set_llm_call_context(**fields: Any) -> Any:
    """Bind operation metadata for the next LLM/embed logs; returns reset token."""
    return llm_call_context_var.set({k: v for k, v in fields.items() if v is not None})


def reset_llm_call_context(token: Any) -> None:
    llm_call_context_var.reset(token)


def get_llm_call_context() -> dict[str, Any]:
    return dict(llm_call_context_var.get() or {})


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def format_timestamp(dt: datetime | None = None) -> str:
    moment = dt or datetime.now(tz=_LOCAL_TZ)
    return moment.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + moment.strftime(" %z")


class ConsoleFormatter(logging.Formatter):
    """Readable terminal lines with date/time/timezone and structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        ts = format_timestamp(
            datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone(_LOCAL_TZ)
        )
        request_id = getattr(record, "request_id", "-")
        event = getattr(record, "event", None) or "-"
        message = record.getMessage()
        extras = getattr(record, "extra_fields", {}) or {}
        compact: list[str] = []
        for key, value in extras.items():
            if key in {"results", "type_counts", "diagnostics"}:
                if isinstance(value, list):
                    compact.append(f"{key}={len(value)}")
                elif isinstance(value, dict):
                    compact.append(f"{key}={len(value)}")
                continue
            if isinstance(value, (dict, list)) and key not in {
                "retrieved_chunk_ids",
                "similarity_scores",
            }:
                continue
            if value is None:
                continue
            text = str(value)
            if len(text) > 120:
                text = text[:117] + "..."
            compact.append(f"{key}={text}")
        tail = (" | " + " ".join(compact)) if compact else ""
        line = f"{ts} | {record.levelname} | {request_id} | {event} | {message}{tail}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log shippers in deployed environments."""

    def format(self, record: logging.LogRecord) -> str:
        moment = datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone(_LOCAL_TZ)
        payload: dict[str, Any] = {
            "timestamp": moment.isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": getattr(record, "event", None) or "log",
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        company_id = company_id_var.get()
        user_id = user_id_var.get()
        if company_id:
            payload["company_id"] = company_id
        if user_id:
            payload["user_id"] = user_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(redact_mapping(payload), default=str)


def configure_logging(
    level: str = "INFO",
    *,
    as_json: bool | None = None,
    log_format: str | None = None,
) -> None:
    use_json = as_json if as_json is not None else (log_format or "console").lower() == "json"
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if use_json else ConsoleFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    message: str = "",
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit one structured application event (console or JSON)."""
    cleaned = redact_mapping({k: v for k, v in fields.items() if v is not None})
    if company_id_var.get() and "company_id" not in cleaned:
        cleaned["company_id"] = company_id_var.get()
    if user_id_var.get() and "user_id" not in cleaned:
        cleaned["user_id"] = user_id_var.get()
    record_message = message or event
    logger.log(
        level,
        record_message,
        extra={"event": event, "extra_fields": cleaned},
    )


def maybe_content(text: str | None, *, enabled: bool, max_chars: int) -> str | None:
    if not enabled or text is None:
        return None
    return sanitize_text(text, max_chars=max_chars)


def logging_flags() -> dict[str, Any]:
    """Lazy settings read so tests can override env after import."""
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "log_ai_content": bool(getattr(settings, "log_ai_content", False)),
        "log_ai_content_max_chars": int(getattr(settings, "log_ai_content_max_chars", 2000)),
        "log_requests": bool(getattr(settings, "log_requests", True)),
        "log_retrieval": bool(getattr(settings, "log_retrieval", True)),
        "log_ai_routing": bool(getattr(settings, "log_ai_routing", True)),
        "log_document_processing": bool(getattr(settings, "log_document_processing", True)),
    }
