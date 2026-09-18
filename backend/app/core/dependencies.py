from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.errors import AIServiceUnavailableError, ServiceUnavailableError

# Reusable aliases so routers read as intent, not plumbing.
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def require_ai_enabled(settings: AppSettings) -> None:
    """
    Guard for routes needing an inference server.

    Answers 503 with an explanation instead of failing deep inside a service
    with a connection error.
    """
    if not settings.ai_features_enabled:
        raise ServiceUnavailableError(
            "AI features are disabled. Set AI_FEATURES_ENABLED=true and configure a "
            "local LLM endpoint to enable embeddings, retrieval and generation."
        )


def require_ai_ready(settings: AppSettings) -> None:
    """
    AI flag plus a cheap reachability probe.

    Used by knowledge extraction so a powered-off remote host fails in seconds
    with AI_SERVICE_UNAVAILABLE instead of holding the request open. With auto
    routing, Gemini counts as ready when the remote is offline.
    """
    require_ai_enabled(settings)
    from app.integrations.llm.factory import get_llm_provider

    provider = get_llm_provider()
    if not provider.health():
        raise AIServiceUnavailableError(
            "The configured AI service is currently unavailable.",
            provider=getattr(provider, "name", settings.llm_provider),
            retryable=True,
            reason="provider_unavailable",
        )


def get_llm_provider_dep(settings: AppSettings):
    """Imported lazily so the core app never depends on the LLM package."""
    from app.integrations.llm.factory import get_llm_provider

    return get_llm_provider()
