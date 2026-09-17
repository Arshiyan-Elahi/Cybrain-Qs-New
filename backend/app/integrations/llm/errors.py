"""LLM integration error taxonomy and httpx failure classification."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.errors import AIServiceUnavailableError


class LLMError(RuntimeError):
    """Raised when the configured model endpoint fails or returns an invalid payload."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        reason: str = "provider_error",
        retryable: bool = True,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.reason = reason
        self.retryable = retryable
        self.status_code = status_code


def to_ai_service_unavailable(exc: LLMError) -> AIServiceUnavailableError:
    return AIServiceUnavailableError(
        "The configured AI service is currently unavailable.",
        provider=exc.provider,
        retryable=exc.retryable,
        reason=exc.reason,
    )


def classify_httpx_error(exc: BaseException, *, provider: str, base_url: str) -> LLMError:
    """Map transport and HTTP failures to a typed LLMError."""
    if isinstance(exc, httpx.ConnectTimeout):
        return LLMError(
            f"Connect timeout reaching AI service at {base_url}.",
            provider=provider,
            reason="connect_timeout",
            retryable=True,
        )
    if isinstance(exc, httpx.ReadTimeout):
        return LLMError(
            f"Read timeout waiting for AI service at {base_url}.",
            provider=provider,
            reason="read_timeout",
            retryable=True,
        )
    if isinstance(exc, httpx.ConnectError):
        text = str(exc).lower()
        reason = "connection_refused"
        if any(
            token in text
            for token in ("unreachable", "no route", "name or service", "getaddrinfo", "nodename")
        ):
            reason = "host_unreachable"
        return LLMError(
            f"Cannot reach AI service at {base_url}: {exc}",
            provider=provider,
            reason=reason,
            retryable=True,
        )
    if isinstance(exc, httpx.TimeoutException):
        return LLMError(
            f"Timeout reaching AI service at {base_url}.",
            provider=provider,
            reason="connect_timeout",
            retryable=True,
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = (exc.response.text or "")[:300]
        lowered = body.lower()
        if status in {404, 400} and any(
            token in lowered for token in ("model", "not found", "does not exist", "unknown model")
        ):
            return LLMError(
                f"Configured model is unavailable at {base_url}: {status} {body}",
                provider=provider,
                reason="model_unavailable",
                retryable=True,
                status_code=status,
            )
        if status in {408, 425, 429, 500, 502, 503, 504}:
            return LLMError(
                f"AI service unavailable at {base_url}: {status} {body}",
                provider=provider,
                reason="provider_unavailable",
                retryable=True,
                status_code=status,
            )
        return LLMError(
            f"AI service returned {status}: {body}",
            provider=provider,
            reason="provider_error",
            retryable=False,
            status_code=status,
        )
    if isinstance(exc, httpx.HTTPError):
        return LLMError(
            f"Network error reaching AI service at {base_url}: {exc}",
            provider=provider,
            reason="network_error",
            retryable=True,
        )
    return LLMError(str(exc), provider=provider, reason="provider_error", retryable=False)


def invalid_response(provider: str, detail: str) -> LLMError:
    return LLMError(
        detail,
        provider=provider,
        reason="invalid_response",
        retryable=False,
    )


def parse_json_object(data: Any, *, provider: str) -> dict:
    if isinstance(data, dict):
        return data
    if isinstance(data, (bytes, bytearray, str)):
        try:
            parsed = json.loads(data)
        except (TypeError, json.JSONDecodeError) as exc:
            raise invalid_response(provider, "AI service returned invalid JSON.") from exc
        if isinstance(parsed, dict):
            return parsed
    raise invalid_response(provider, "AI service returned a non-object JSON payload.")


def httpx_timeout(total: float) -> httpx.Timeout:
    """Fail connect/host quickly when the remote PC is off; keep read budget for generation."""
    connect = min(5.0, max(1.0, total / 4 if total else 5.0))
    return httpx.Timeout(total, connect=connect, pool=connect)
