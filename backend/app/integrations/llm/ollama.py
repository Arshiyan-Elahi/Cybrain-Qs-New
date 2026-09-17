import httpx

from app.integrations.llm.base import ChatMessage, Completion
from app.integrations.llm.errors import (
    classify_httpx_error,
    httpx_timeout,
    invalid_response,
    parse_json_object,
)


class OllamaProvider:
    """
    Talks to a local Ollama daemon (default http://localhost:11434).

    Uses Ollama's native API rather than its OpenAI-compatible shim because the
    native embeddings endpoint accepts a batch and reports the model back.
    """

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        embedding_dimensions: int,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.timeout = timeout

    def _timeout(self) -> httpx.Timeout:
        return httpx_timeout(self.timeout)

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = httpx.post(
                f"{self.base_url}{path}", json=payload, timeout=self._timeout()
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
                f"{self.base_url}/api/tags",
                timeout=httpx.Timeout(5.0, connect=2.0),
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return False
        installed = {m.get("name", "").split(":")[0] for m in response.json().get("models", [])}
        return self.chat_model.split(":")[0] in installed

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Completion:
        options: dict[str, float | int] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        data = self._post(
            "/api/chat",
            {
                "model": self.chat_model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                "options": options,
            },
        )
        message = data.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise invalid_response(self.name, "Ollama returned an invalid chat response.")
        return Completion(
            text=message.get("content") or "",
            model=data.get("model", self.chat_model),
            provider=self.name,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("/api/embed", {"model": self.embedding_model, "input": texts})
        vectors = data.get("embeddings") or []
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise invalid_response(
                self.name,
                f"Ollama returned {len(vectors) if isinstance(vectors, list) else 0} "
                f"embeddings for {len(texts)} inputs.",
            )
        return vectors
