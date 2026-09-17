from functools import lru_cache

from app.core.config import get_settings
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.ollama import OllamaProvider
from app.integrations.llm.openai_compatible import OpenAICompatibleProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


@lru_cache
def get_llm_provider() -> LLMProvider:
    """
    Build the configured provider.

    Changing local runtime or model is a configuration change only: set
    LLM_PROVIDER / LLM_BASE_URL / LLM_CHAT_MODEL / LLM_EMBEDDING_MODEL. No
    service or router imports a concrete provider.
    """
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.llm_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.llm_provider!r}. "
            f"Available: {', '.join(sorted(_PROVIDERS))}."
        )

    kwargs = {
        "base_url": settings.llm_base_url,
        "chat_model": settings.llm_chat_model,
        "embedding_model": settings.llm_embedding_model,
        "embedding_dimensions": settings.llm_embedding_dimensions,
        "timeout": settings.llm_timeout_seconds,
    }
    if provider_cls is OpenAICompatibleProvider:
        kwargs["api_key"] = settings.llm_api_key
    return provider_cls(**kwargs)


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)
