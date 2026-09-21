"""Gemini LLM fallback via the Google Generative Language API."""

from __future__ import annotations

import httpx

from app.core.logging import get_logger, log_event, logging_flags, maybe_content
from app.integrations.llm.base import ChatMessage, Completion
from app.integrations.llm.errors import (
    LLMError,
    classify_httpx_error,
    httpx_timeout,
    invalid_response,
    parse_json_object,
)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
_API_KEY_HEADER = "x-goog-api-key"
logger = get_logger("app.ai.gemini")

# CKM extract (and any JSON-array prompt) must emit a top-level array the
# parser accepts. Gemini JSON mode otherwise often returns a wrapped object,
# and Gemini 2.5 thinking can consume maxOutputTokens before any JSON lands.
GEMINI_JSON_ARRAY_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "type": {
                "type": "STRING",
                "enum": [
                    "regulation",
                    "role",
                    "responsibility",
                    "workflow",
                    "process",
                    "business_rule",
                    "form_or_record",
                    "relationship",
                    "best_practice",
                ],
            },
            "label": {"type": "STRING"},
            "sourceChunkId": {"type": "STRING"},
            "payload": {
                "type": "OBJECT",
                "properties": {"evidence": {"type": "STRING"}},
            },
        },
        "required": ["type", "label", "sourceChunkId"],
    },
}


class GeminiProvider:
    """
    Server-side Gemini chat fallback.

    API key is read only from backend settings. Embeddings are not served here;
    the routing provider uses local Nomic for that path.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        embedding_dimensions: int,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.timeout = timeout

    def _timeout(self) -> httpx.Timeout:
        return httpx_timeout(self.timeout)

    def _auth_headers(self) -> dict[str, str]:
        return {_API_KEY_HEADER: self.api_key}

    def health(self) -> bool:
        if not self.api_key:
            return False
        try:
            response = httpx.get(
                f"{_API_ROOT}/models/{self.chat_model}",
                headers=self._auth_headers(),
                timeout=httpx.Timeout(5.0, connect=2.0),
            )
            return response.status_code < 400
        except httpx.HTTPError:
            return False

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Completion:
        if not self.api_key:
            raise LLMError(
                "Gemini API key is not configured.",
                provider=self.name,
                reason="provider_unavailable",
                retryable=False,
            )

        system_parts = [m.content for m in messages if m.role == "system" and m.content]
        contents: list[dict] = []
        for message in messages:
            if message.role == "system":
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": ""}]}]

        generation: dict = {
            "temperature": temperature,
        }
        wants_json = any("json" in (m.content or "").lower() for m in messages)
        if wants_json:
            generation["responseMimeType"] = "application/json"
            generation["responseSchema"] = GEMINI_JSON_ARRAY_SCHEMA
            generation["thinkingConfig"] = {"thinkingBudget": 0}
        if max_tokens is not None:
            generation["maxOutputTokens"] = max_tokens

        payload: dict = {
            "contents": contents,
            "generationConfig": generation,
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

        url = f"{_API_ROOT}/models/{self.chat_model}:generateContent"
        try:
            response = httpx.post(
                url,
                headers=self._auth_headers(),
                json=payload,
                timeout=self._timeout(),
            )
            response.raise_for_status()
            data = parse_json_object(response.json(), provider=self.name)
        except Exception as exc:
            if isinstance(exc, httpx.HTTPError):
                raise classify_httpx_error(exc, provider=self.name, base_url=_API_ROOT) from exc
            if isinstance(exc, LLMError):
                raise
            raise invalid_response(self.name, f"Gemini call failed: {exc}") from exc

        text, meta = _extract_text(data)
        self._log_raw_response(text, meta)
        usage = data.get("usageMetadata") or {}
        usage_fields: dict[str, int | str] = {
            "prompt_tokens": int(usage.get("promptTokenCount") or 0)
            if isinstance(usage, dict)
            else 0,
            "completion_tokens": int(usage.get("candidatesTokenCount") or 0)
            if isinstance(usage, dict)
            else 0,
        }
        if meta.get("finish_reason"):
            usage_fields["finish_reason"] = str(meta["finish_reason"])
        usage_fields["thought_parts"] = int(meta.get("thought_parts") or 0)
        return Completion(
            text=text,
            model=data.get("modelVersion") or self.chat_model,
            provider=self.name,
            usage=usage_fields,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError(
            "Gemini provider does not serve embeddings in this deployment.",
            provider=self.name,
            reason="provider_unavailable",
            retryable=False,
        )

    def _log_raw_response(self, text: str, meta: dict) -> None:
        from app.core.config import get_settings

        flags = logging_flags()
        settings = get_settings()
        fields: dict = {
            "provider": self.name,
            "model": self.chat_model,
            "finish_reason": meta.get("finish_reason"),
            "thought_parts": meta.get("thought_parts"),
            "visible_parts": meta.get("visible_parts"),
            "response_chars": len(text or ""),
            "http_status": 200,
        }
        if settings.environment != "production" or flags.get("log_ai_content"):
            fields["response_preview"] = maybe_content(
                text,
                enabled=True,
                max_chars=min(int(flags.get("log_ai_content_max_chars", 2000)), 500),
            )
        log_event(
            logger,
            "gemini_generate_content_received",
            "Gemini generateContent response received",
            **fields,
        )


def _extract_text(data: dict) -> tuple[str, dict]:
    candidates = data.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise invalid_response("gemini", "Gemini returned no candidates.")
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    content = candidate.get("content") or {}
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        raise invalid_response(
            "gemini",
            f"Gemini returned an empty content payload (finishReason={finish_reason}).",
        )
    thought_parts = 0
    visible: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("thought"):
            thought_parts += 1
            continue
        text = part.get("text")
        if isinstance(text, str):
            visible.append(text)
    joined = "".join(visible).strip()
    meta = {
        "finish_reason": finish_reason,
        "thought_parts": thought_parts,
        "visible_parts": len(visible),
        "candidate_count": len(candidates),
    }
    if not joined:
        raise invalid_response(
            "gemini",
            "Gemini returned empty visible text "
            f"(finishReason={finish_reason}, thought_parts={thought_parts}).",
        )
    return joined, meta
