import httpx

from app.integrations.llm.base import ChatMessage, Completion
from app.integrations.llm.errors import (
    classify_httpx_error,
    httpx_timeout,
    invalid_response,
    parse_json_object,
)


class OpenAICompatibleProvider:
    """
    Any local server exposing the OpenAI chat/embeddings routes.

    Covers LM Studio, vLLM, llama.cpp's server, LocalAI, text-generation-webui
    and Ollama's own /v1 shim. `api_key` is optional because local servers
    usually ignore it; it is sent only when configured.
    """

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        embedding_dimensions: int,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.api_key = api_key
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _timeout(self) -> httpx.Timeout:
        return httpx_timeout(self.timeout)

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = httpx.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._headers,
                timeout=self._timeout(),
            )
            response.raise_for_status()
            return parse_json_object(response.json(), provider=self.name)
        except Exception as exc:
            if isinstance(exc, httpx.HTTPError):
                raise classify_httpx_error(exc, provider=self.name, base_url=self.base_url) from exc
            from app.integrations.llm.errors import LLMError

            if isinstance(exc, LLMError):
                raise
            raise invalid_response(self.name, f"AI service call failed: {exc}") from exc

    def health(self) -> bool:
        try:
            response = httpx.get(
                f"{self.base_url}/models",
                headers=self._headers,
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
        payload: dict = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        data = self._post("/chat/completions", payload)
        choices = data.get("choices") or []
        if not choices:
            raise invalid_response(self.name, "AI service returned no chat choices.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict) or "content" not in message:
            raise invalid_response(self.name, "AI service returned an invalid chat completion.")
        usage = data.get("usage") or {}
        return Completion(
            text=message.get("content") or "",
            model=data.get("model", self.chat_model),
            provider=self.name,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0,
                "completion_tokens": usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0,
            },
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("/embeddings", {"model": self.embedding_model, "input": texts})
        rows = data.get("data") or []
        if not isinstance(rows, list):
            raise invalid_response(self.name, "AI service returned invalid embeddings payload.")
        try:
            ordered = sorted(rows, key=lambda row: row.get("index", 0))
            vectors = [row["embedding"] for row in ordered]
        except (TypeError, KeyError, AttributeError) as exc:
            raise invalid_response(self.name, "AI service returned invalid embedding rows.") from exc
        if len(vectors) != len(texts):
            raise invalid_response(
                self.name,
                f"AI service returned {len(vectors)} embeddings for {len(texts)} inputs.",
            )
        return vectors
