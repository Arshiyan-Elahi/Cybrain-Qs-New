"""Gemini LLM fallback via the Google Generative Language API."""

from __future__ import annotations

import httpx

from app.integrations.llm.base import ChatMessage, Completion
from app.integrations.llm.errors import (
    LLMError,
    classify_httpx_error,
    httpx_timeout,
    invalid_response,
    parse_json_object,
)

_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


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

    def health(self) -> bool:
        if not self.api_key:
            return False
        try:
            response = httpx.get(
                f"{_API_ROOT}/models/{self.chat_model}",
                params={"key": self.api_key},
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
                params={"key": self.api_key},
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

        text = _extract_text(data)
        usage = data.get("usageMetadata") or {}
        return Completion(
            text=text,
            model=data.get("modelVersion") or self.chat_model,
            provider=self.name,
            usage={
                "prompt_tokens": int(usage.get("promptTokenCount") or 0)
                if isinstance(usage, dict)
                else 0,
                "completion_tokens": int(usage.get("candidatesTokenCount") or 0)
                if isinstance(usage, dict)
                else 0,
            },
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError(
            "Gemini provider does not serve embeddings in this deployment.",
            provider=self.name,
            reason="provider_unavailable",
            retryable=False,
        )


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        # Some prompts still return plain text if JSON mime fails; surface clearly.
        raise invalid_response("gemini", "Gemini returned no candidates.")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        raise invalid_response("gemini", "Gemini returned an empty content payload.")
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    joined = "".join(texts).strip()
    if not joined:
        raise invalid_response("gemini", "Gemini returned empty text.")
    return joined
