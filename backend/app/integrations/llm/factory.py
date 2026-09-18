from functools import lru_cache

from app.core.config import get_settings
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.embedding_profile import NOMIC_V15_PROFILE
from app.integrations.llm.gemini import GeminiProvider
from app.integrations.llm.local_embeddings import LocalNomicEmbedder
from app.integrations.llm.ollama import OllamaProvider
from app.integrations.llm.openai_compatible import OpenAICompatibleProvider
from app.integrations.llm.router import RoutingLLMProvider

_PROVIDERS = {
    "ollama": OllamaProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def _build_remote() -> LLMProvider:
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.llm_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.llm_provider!r}. "
            f"Available: {', '.join(sorted(_PROVIDERS))}."
        )

    kwargs: dict = {
        "base_url": settings.llm_base_url,
        "chat_model": settings.llm_chat_model,
        "embedding_model": settings.llm_embedding_model,
        "embedding_dimensions": settings.llm_embedding_dimensions,
        "timeout": settings.llm_timeout_seconds,
    }
    if provider_cls is OpenAICompatibleProvider:
        kwargs["api_key"] = settings.llm_api_key
        kwargs["health_timeout"] = settings.ai_health_timeout_seconds
        kwargs["embedding_profile"] = NOMIC_V15_PROFILE
    return provider_cls(**kwargs)


@lru_cache
def get_llm_provider() -> LLMProvider:
    """
    Build the configured provider, wrapping with auto routing when enabled.

    Changing local runtime or model is a configuration change only. No service
    or router imports a concrete provider.
    """
    settings = get_settings()
    remote = _build_remote()
    mode = settings.ai_routing_mode

    # Legacy single-provider path when routing is forced off via remote-only and
    # no fallback credentials — still wrap so runtime status stays consistent.
    gemini = None
    if settings.gemini_api_key:
        gemini = GeminiProvider(
            api_key=settings.gemini_api_key,
            chat_model=settings.gemini_model,
            embedding_model=settings.local_embedding_model,
            embedding_dimensions=settings.local_embedding_dimensions,
            timeout=settings.gemini_timeout_seconds,
        )

    local_embedder = None
    if settings.local_embedding_dimensions == NOMIC_V15_PROFILE.dimensions:
        local_embedder = LocalNomicEmbedder(
            model_id=settings.local_embedding_model,
            profile=NOMIC_V15_PROFILE,
        )

    provider = RoutingLLMProvider(
        mode=mode,
        remote=remote,
        gemini=gemini,
        local_embedder=local_embedder,
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=settings.ai_failover_cooldown_seconds,
        compat_min_cosine=settings.ai_embedding_compat_min_cosine,
    )
    # Warm compatibility when remote embeddings are already up.
    try:
        if mode == "auto" and provider._embed_remote_online() and local_embedder:
            provider.ensure_embedding_compatibility()
    except Exception:  # noqa: BLE001 - never block startup on probe
        pass
    return provider


def reset_llm_provider() -> None:
    """Clear cached provider (tests / settings reload)."""
    get_llm_provider.cache_clear()


def available_providers() -> list[str]:
    return sorted(_PROVIDERS)
