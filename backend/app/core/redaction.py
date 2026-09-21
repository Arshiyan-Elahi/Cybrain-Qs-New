"""Centralized secret/PII redaction for structured logs."""

from __future__ import annotations

import re
from typing import Any

# Keys that look secret-ish but are safe metrics / identifiers.
_SAFE_KEYS = frozenset(
    {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "token_usage",
        "request_id",
    }
)

_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|password|passwd|secret|"
    r"api[_-]?key|gemini_api_key|llm_api_key|database_url|db_url|"
    r"access_token|refresh_token|^token$|bearer)",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"

# Query-string secrets (Gemini uses ?key= on generateContent if the key is
# passed as a param). Also scrub Google API keys that leak into free text.
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:key|api[_-]?key|access_token|refresh_token|client_secret|password|secret)=)[^&\s\"']+"
)
_GOOGLE_API_KEY = re.compile(r"AIza[0-9A-Za-z_-]{20,}")


def is_sensitive_key(key: str) -> bool:
    if (key or "") in _SAFE_KEYS:
        return False
    return bool(_SENSITIVE_KEY.search(key or ""))


def redact_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, str) and _looks_like_secret(value):
        return _REDACTED
    return value


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in data.items()}


def sanitize_text(text: str, *, max_chars: int = 2000) -> str:
    """Truncate and scrub obvious secret-looking substrings from free text."""
    cleaned = text
    cleaned = _QUERY_SECRET.sub(r"\1[REDACTED]", cleaned)
    cleaned = _GOOGLE_API_KEY.sub(_REDACTED, cleaned)
    cleaned = re.sub(
        r"(?i)(authorization|api[_-]?key|bearer)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        cleaned,
    )
    if len(cleaned) > max_chars:
        return cleaned[: max_chars - 3] + "..."
    return cleaned


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith("bearer "):
        return True
    if "postgresql://" in lowered or "postgres://" in lowered:
        return True
    return False
