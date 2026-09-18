"""Authenticated AI runtime status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.integrations.llm.factory import get_llm_provider
from app.integrations.llm.router import RoutingLLMProvider
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(prefix="/ai", tags=["ai"])


class RemoteStatus(BaseModel):
    status: str


class LlmRuntimeStatus(BaseModel):
    active: str
    model: str
    remote: str
    fallback: str


class EmbeddingRuntimeStatus(BaseModel):
    active: str
    model: str
    dimensions: int
    remote: str
    local: str
    compatible: bool


class AiRuntimeResponse(BaseModel):
    mode: str
    overall: str
    remote: RemoteStatus
    llm: LlmRuntimeStatus
    embedding: EmbeddingRuntimeStatus
    last_health_check: str | None = None
    fallback_reason: str | None = Field(
        default=None,
        description="Safe machine reason code when fallback is active or blocked.",
    )


@router.get("/runtime", response_model=AiRuntimeResponse)
def ai_runtime(_current_user: CurrentUser) -> AiRuntimeResponse:
    """
    Compact runtime view for the settings AI Runtime card.

    Never returns API keys or raw provider exception text.
    """
    settings = get_settings()
    if not settings.ai_features_enabled:
        return AiRuntimeResponse(
            mode=settings.ai_routing_mode,
            overall="degraded",
            remote=RemoteStatus(status="offline"),
            llm=LlmRuntimeStatus(
                active="remote",
                model=settings.llm_chat_model,
                remote="offline",
                fallback="ready" if settings.gemini_api_key else "unavailable",
            ),
            embedding=EmbeddingRuntimeStatus(
                active="remote",
                model=settings.local_embedding_model,
                dimensions=settings.local_embedding_dimensions,
                remote="offline",
                local="unavailable",
                compatible=False,
            ),
            last_health_check=None,
            fallback_reason="ai_features_disabled",
        )

    provider = get_llm_provider()
    if isinstance(provider, RoutingLLMProvider):
        snap = provider.runtime_snapshot()
        checked = (
            datetime.fromtimestamp(snap.last_health_check_at, tz=timezone.utc).isoformat()
            if snap.last_health_check_at
            else None
        )
        return AiRuntimeResponse(
            mode=snap.mode,
            overall=snap.overall,
            remote=RemoteStatus(status=snap.remote_status),
            llm=LlmRuntimeStatus(
                active=snap.llm_active,
                model=snap.llm_model,
                remote=snap.llm_remote,
                fallback=snap.llm_fallback,
            ),
            embedding=EmbeddingRuntimeStatus(
                active=snap.embedding_active,
                model=snap.embedding_model,
                dimensions=snap.embedding_dimensions,
                remote=snap.embedding_remote,
                local=snap.embedding_local,
                compatible=snap.embedding_compatible,
            ),
            last_health_check=checked,
            fallback_reason=snap.fallback_reason,
        )

    # Non-routing provider (should not happen with current factory).
    online = "online" if provider.health() else "offline"
    return AiRuntimeResponse(
        mode=settings.ai_routing_mode,
        overall="healthy" if online == "online" else "degraded",
        remote=RemoteStatus(status=online),
        llm=LlmRuntimeStatus(
            active="remote",
            model=provider.chat_model,
            remote=online,
            fallback="unavailable",
        ),
        embedding=EmbeddingRuntimeStatus(
            active="remote",
            model=provider.embedding_model,
            dimensions=provider.embedding_dimensions,
            remote=online,
            local="unavailable",
            compatible=False,
        ),
        last_health_check=datetime.now(tz=timezone.utc).isoformat(),
        fallback_reason=None,
    )
