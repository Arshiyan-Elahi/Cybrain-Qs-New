"""Local Nomic embeddings via SentenceTransformers (in-process)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.integrations.llm.embedding_profile import EmbeddingProfile, TaskType
from app.integrations.llm.errors import LLMError, invalid_response

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_model_cache: dict[str, Any] = {}


class LocalNomicEmbedder:
    """
    In-process Hugging Face / SentenceTransformers embedder.

    Uses nomic-ai/nomic-embed-text-v1.5 with trust_remote_code when required.
    Dimension must remain 768 to match the remote Nomic / pgvector column.
    """

    name = "local_nomic"

    def __init__(self, model_id: str, profile: EmbeddingProfile) -> None:
        self.model_id = model_id
        self.profile = profile
        self.embedding_model = model_id
        self.embedding_dimensions = profile.dimensions
        self._unavailable_reason: str | None = None

    @property
    def ready(self) -> bool:
        return self._load() is not None and self._unavailable_reason is None

    @property
    def unavailable_reason(self) -> str | None:
        self._load()
        return self._unavailable_reason

    def _load(self) -> Any | None:
        if self.model_id in _model_cache:
            self._unavailable_reason = None
            return _model_cache[self.model_id]
        with _model_lock:
            if self.model_id in _model_cache:
                self._unavailable_reason = None
                return _model_cache[self.model_id]
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                self._unavailable_reason = "sentence_transformers_not_installed"
                logger.warning("Local embeddings unavailable: %s", exc)
                return None
            try:
                model = SentenceTransformer(
                    self.model_id, **_sentence_transformer_kwargs(self.model_id)
                )
                _model_cache[self.model_id] = model
                self._unavailable_reason = None
                return model
            except Exception as exc:  # noqa: BLE001 - model download/load failures
                self._unavailable_reason = "local_model_load_failed"
                logger.warning("Failed to load local embedding model %s: %s", self.model_id, exc)
                return None

    def embed(self, texts: list[str], *, task: TaskType = "document") -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        if model is None:
            raise LLMError(
                "Local embedding model is unavailable.",
                provider=self.name,
                reason="provider_unavailable",
                retryable=False,
            )
        prepared = self.profile.prepare(texts, task=task)
        try:
            raw = model.encode(
                prepared,
                batch_size=self.profile.batch_size,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
            vectors = [list(map(float, row)) for row in raw]
        except Exception as exc:  # noqa: BLE001
            raise invalid_response(self.name, f"Local embedding failed: {exc}") from exc
        try:
            self.profile.validate_dimensions(vectors)
        except ValueError as exc:
            raise invalid_response(self.name, str(exc)) from exc
        return self.profile.postprocess(vectors)


def _native_nomic_bert_available() -> bool:
    """True when transformers ships NomicBert (v5.5+) and Hub auto_map is stale."""
    try:
        from transformers.models.auto.modeling_auto import MODEL_MAPPING_NAMES
    except Exception:  # noqa: BLE001 - optional stack, load path still has a fallback
        return False
    return MODEL_MAPPING_NAMES.get("nomic_bert") == "NomicBertModel"


def _sentence_transformer_kwargs(model_id: str) -> dict[str, Any]:
    """
    Keep trust_remote_code=True for SentenceTransformer module loading.

    nomic-embed-text-v1.5 config.auto_map still points at nomic-bert-2048 custom
    code that calls PreTrainedModel.get_extended_attention_mask, removed in
    transformers 5. When the native NomicBert architecture is registered, load
    that instead of executing the Hub snapshot.
    """
    kwargs: dict[str, Any] = {"trust_remote_code": True}
    if "nomic" in model_id.lower() and _native_nomic_bert_available():
        native = {"trust_remote_code": False}
        kwargs["model_kwargs"] = dict(native)
        kwargs["config_kwargs"] = dict(native)
        kwargs["processor_kwargs"] = dict(native)
    return kwargs


def clear_local_model_cache() -> None:
    with _model_lock:
        _model_cache.clear()
