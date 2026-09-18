"""
Automatic primary/fallback routing for LLM and embeddings.

Remote OpenAI-compatible (or Ollama) is preferred when healthy. On failure,
LLM falls back to Gemini and embeddings to local SentenceTransformers Nomic,
but only when the shared embedding profile passes a compatibility self-test.
LLM and embedding failover are independent. Provider choice is pinned for a
single complete()/embed() call so generation does not oscillate mid-request.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

from app.integrations.llm.base import ChatMessage, Completion, LLMProvider
from app.integrations.llm.circuit_breaker import CircuitBreaker
from app.integrations.llm.embedding_profile import (
    COMPAT_SENTINEL_DOCUMENT,
    COMPAT_SENTINEL_QUERY,
    EmbeddingProfile,
    NOMIC_V15_PROFILE,
    TaskType,
    cosine_similarity,
)
from app.integrations.llm.errors import LLMError
from app.integrations.llm.gemini import GeminiProvider
from app.integrations.llm.local_embeddings import LocalNomicEmbedder
from app.core.logging import (
    get_llm_call_context,
    get_logger,
    log_event,
    logging_flags,
    maybe_content,
)

logger = get_logger("app.ai.routing")

LlmSource = Literal["remote", "gemini"]
EmbedSource = Literal["remote", "local"]
Readiness = Literal["ready", "unavailable"]
OnlineStatus = Literal["online", "offline"]


@dataclass
class RuntimeSnapshot:
    mode: str
    remote_status: OnlineStatus
    llm_active: LlmSource
    llm_model: str
    llm_remote: OnlineStatus
    llm_fallback: Readiness
    embedding_active: EmbedSource
    embedding_model: str
    embedding_dimensions: int
    embedding_remote: OnlineStatus
    embedding_local: Readiness
    embedding_compatible: bool
    last_health_check_at: float | None = None
    fallback_reason: str | None = None
    overall: Literal["healthy", "fallback_active", "degraded"] = "degraded"


@dataclass
class _CompatState:
    compatible: bool | None = None
    reason: str | None = None
    tested_at: float | None = None
    query_cosine: float | None = None
    document_cosine: float | None = None


class RoutingLLMProvider:
    """LLMProvider that routes complete/embed independently with circuit breakers."""

    name = "routing"

    def __init__(
        self,
        *,
        mode: str,
        remote: LLMProvider,
        gemini: GeminiProvider | None,
        local_embedder: LocalNomicEmbedder | None,
        profile: EmbeddingProfile = NOMIC_V15_PROFILE,
        cooldown_seconds: float = 30.0,
        compat_min_cosine: float = 0.85,
    ) -> None:
        self.mode = mode
        self.remote = remote
        self.gemini = gemini
        self.local_embedder = local_embedder
        self.profile = profile
        self.compat_min_cosine = compat_min_cosine
        self.chat_model = getattr(remote, "chat_model", "")
        self.embedding_model = getattr(remote, "embedding_model", profile.model_family)
        self.embedding_dimensions = profile.dimensions
        self._llm_breaker = CircuitBreaker(
            cooldown_seconds=cooldown_seconds,
            name="remote_llm",
            on_open=lambda reason: self._log_circuit("llm", "opened", reason),
            on_close=lambda: self._log_circuit("llm", "closed", None),
            on_retry=lambda: self._log_circuit("llm", "retry", None),
        )
        self._embed_breaker = CircuitBreaker(
            cooldown_seconds=cooldown_seconds,
            name="remote_embedding",
            on_open=lambda reason: self._log_circuit("embedding", "opened", reason),
            on_close=lambda: self._log_circuit("embedding", "closed", None),
            on_retry=lambda: self._log_circuit("embedding", "retry", None),
        )
        self._compat = _CompatState()
        self._compat_lock = threading.Lock()
        self._active_llm: LlmSource = "remote"
        self._active_embed: EmbedSource = "remote"
        self._fallback_reason: str | None = None
        self._last_health_check_at: float | None = None

    def _routing_enabled(self) -> bool:
        return bool(logging_flags().get("log_ai_routing", True))

    def _log_circuit(self, capability: str, action: str, reason: str | None) -> None:
        if not self._routing_enabled():
            return
        if action == "opened":
            log_event(
                logger,
                "circuit_opened",
                f"Remote {capability} circuit opened",
                level=30,
                capability=capability,
                reason=reason,
            )
            log_event(
                logger,
                "remote_ai_unavailable",
                f"Remote {capability} unavailable",
                level=30,
                capability=capability,
                reason=reason,
            )
        elif action == "closed":
            log_event(
                logger,
                "circuit_closed",
                f"Remote {capability} circuit closed",
                capability=capability,
            )
            log_event(
                logger,
                "remote_recovered",
                f"Remote {capability} recovered",
                capability=capability,
            )
        elif action == "retry":
            log_event(
                logger,
                "remote_retry_started",
                f"Retrying remote {capability} after cooldown",
                capability=capability,
            )

    # ------------------------------------------------------------------ health

    def health(self) -> bool:
        """True when at least one LLM path can serve complete()."""
        self._refresh_probes()
        if self._llm_remote_online():
            return True
        return self._gemini_ready()

    def _refresh_probes(self) -> None:
        self._probe_llm()
        self._probe_embeddings()
        self._last_health_check_at = time.time()

    def _probe_llm(self) -> bool:
        if self.mode == "fallback":
            self._llm_breaker.record_failure("mode_fallback")
            return False
        if self._llm_breaker.cached_offline():
            return False
        if not self._llm_breaker.should_probe():
            last = self._llm_breaker.last
            return bool(last and last.online)
        probe = getattr(self.remote, "health_llm", None) or self.remote.health
        try:
            ok = bool(probe())
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self._llm_breaker.record_success()
            return True
        self._llm_breaker.record_failure("remote_llm_unreachable")
        return False

    def _probe_embeddings(self) -> bool:
        if self.mode == "fallback":
            self._embed_breaker.record_failure("mode_fallback")
            return False
        if self._embed_breaker.cached_offline():
            return False
        if not self._embed_breaker.should_probe():
            last = self._embed_breaker.last
            return bool(last and last.online)
        probe = getattr(self.remote, "health_embeddings", None) or self.remote.health
        try:
            ok = bool(probe())
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self._embed_breaker.record_success()
            return True
        self._embed_breaker.record_failure("remote_embeddings_unreachable")
        return False

    def _llm_remote_online(self) -> bool:
        if self.mode == "fallback":
            return False
        if self.mode == "remote":
            return self._probe_llm()
        last = self._llm_breaker.last
        if last is None or self._llm_breaker.should_probe():
            return self._probe_llm()
        return bool(last.online)

    def _embed_remote_online(self) -> bool:
        if self.mode == "fallback":
            return False
        if self.mode == "remote":
            return self._probe_embeddings()
        last = self._embed_breaker.last
        if last is None or self._embed_breaker.should_probe():
            return self._probe_embeddings()
        return bool(last.online)

    def _gemini_ready(self) -> bool:
        return bool(self.gemini and self.gemini.api_key)

    def _local_embed_ready(self) -> bool:
        return bool(self.local_embedder and self.local_embedder.ready)

    # ----------------------------------------------------------- compatibility

    def ensure_embedding_compatibility(self) -> bool:
        """
        Compare remote vs local vectors for fixed sentinels.

        If incompatible, local fallback is reported unavailable so we never
        write/query mixed embedding spaces.
        """
        with self._compat_lock:
            if self._compat.compatible is not None:
                return self._compat.compatible
        return self._run_compat_test()

    def _run_compat_test(self) -> bool:
        if not self._local_embed_ready() or not self.local_embedder:
            with self._compat_lock:
                self._compat = _CompatState(
                    compatible=False,
                    reason="local_embeddings_unavailable",
                    tested_at=time.time(),
                )
            return False
        if not self._embed_remote_online():
            # Cannot compare without remote; do not approve fallback blindly.
            with self._compat_lock:
                self._compat = _CompatState(
                    compatible=False,
                    reason="remote_unavailable_for_compat_test",
                    tested_at=time.time(),
                )
            return False
        try:
            remote_q = self._remote_embed([COMPAT_SENTINEL_QUERY], task="query")[0]
            remote_d = self._remote_embed([COMPAT_SENTINEL_DOCUMENT], task="document")[0]
            local_q = self.local_embedder.embed([COMPAT_SENTINEL_QUERY], task="query")[0]
            local_d = self.local_embedder.embed([COMPAT_SENTINEL_DOCUMENT], task="document")[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding compatibility test failed: %s", exc)
            with self._compat_lock:
                self._compat = _CompatState(
                    compatible=False,
                    reason="compat_test_failed",
                    tested_at=time.time(),
                )
            return False

        if len(remote_q) != self.profile.dimensions or len(local_q) != self.profile.dimensions:
            with self._compat_lock:
                self._compat = _CompatState(
                    compatible=False,
                    reason="dimension_mismatch",
                    tested_at=time.time(),
                )
            return False

        q_cos = cosine_similarity(remote_q, local_q)
        d_cos = cosine_similarity(remote_d, local_d)
        ok = q_cos >= self.compat_min_cosine and d_cos >= self.compat_min_cosine
        with self._compat_lock:
            self._compat = _CompatState(
                compatible=ok,
                reason=None if ok else "cosine_below_threshold",
                tested_at=time.time(),
                query_cosine=q_cos,
                document_cosine=d_cos,
            )
        if self._routing_enabled():
            log_event(
                logger,
                "embedding_compatibility_check",
                "Embedding compatibility self-test",
                level=20 if ok else 30,
                remote_model=self.embedding_model,
                local_model=self.local_embedder.model_id if self.local_embedder else None,
                dimensions_match=True,
                cosine=round(min(q_cos, d_cos), 4),
                query_cosine=round(q_cos, 4),
                document_cosine=round(d_cos, 4),
                threshold=self.compat_min_cosine,
                compatible=ok,
            )
        if not ok:
            logger.warning(
                "Local embedding fallback blocked: query_cos=%.3f document_cos=%.3f threshold=%.3f",
                q_cos,
                d_cos,
                self.compat_min_cosine,
            )
        return ok

    def invalidate_compat_cache(self) -> None:
        with self._compat_lock:
            self._compat = _CompatState()

    # ---------------------------------------------------------------- complete

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Completion:
        flags = logging_flags()
        ctx = get_llm_call_context()
        provider, source = self._select_llm()
        self._active_llm = source
        provider_name = getattr(provider, "name", source)
        model_name = getattr(provider, "chat_model", self.chat_model)
        provider_source = "primary" if source == "remote" else "fallback"
        if flags.get("log_ai_routing", True):
            log_event(
                logger,
                "ai_route_selected",
                f"LLM route → {provider_name}",
                capability="llm",
                provider=provider_name,
                model=model_name,
                source=provider_source,
                reason=None if source == "remote" else self._fallback_reason,
            )
            if source != "remote":
                log_event(
                    logger,
                    "fallback_activated",
                    "LLM fallback activated",
                    capability="llm",
                    provider=provider_name,
                    reason=self._fallback_reason,
                )

        started = time.perf_counter()
        log_event(
            logger,
            "llm_request_started",
            f"LLM request started ({model_name})",
            operation=ctx.get("operation", "other"),
            provider=provider_name,
            provider_source=provider_source,
            model_name=model_name,
            prompt_version=ctx.get("prompt_version"),
            retrieved_chunk_ids=ctx.get("retrieved_chunk_ids"),
            similarity_scores=ctx.get("similarity_scores"),
        )
        if flags.get("log_ai_content"):
            for message in messages:
                content = maybe_content(
                    message.content,
                    enabled=True,
                    max_chars=flags["log_ai_content_max_chars"],
                )
                log_event(
                    logger,
                    "llm_prompt_content",
                    f"LLM {message.role} content",
                    level=10,
                    role=message.role,
                    content=content,
                )

        try:
            result = provider.complete(
                messages, temperature=temperature, max_tokens=max_tokens
            )
            if source == "remote":
                self._llm_breaker.record_success()
                self._fallback_reason = None
            latency_ms = int((time.perf_counter() - started) * 1000)
            usage = result.usage or {}
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = None
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                total_tokens = input_tokens + output_tokens
            fields = {
                "operation": ctx.get("operation", "other"),
                "provider": result.provider or provider_name,
                "provider_source": provider_source,
                "model_name": result.model or model_name,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens if isinstance(input_tokens, int) else None,
                "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
                "total_tokens": total_tokens,
                "response_chars": len(result.text or ""),
                "retrieved_chunk_ids": ctx.get("retrieved_chunk_ids"),
                "similarity_scores": ctx.get("similarity_scores"),
                "prompt_version": ctx.get("prompt_version"),
                "error_message": None,
            }
            if flags.get("log_ai_content"):
                fields["final_response"] = maybe_content(
                    result.text,
                    enabled=True,
                    max_chars=flags["log_ai_content_max_chars"],
                )
            log_event(
                logger,
                "llm_request_completed",
                f"LLM request completed in {latency_ms}ms",
                **fields,
            )
            return result
        except LLMError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            if source == "remote" and exc.retryable and self._gemini_ready() and self.mode == "auto":
                self._llm_breaker.record_failure(exc.reason)
                self._fallback_reason = exc.reason
                self._active_llm = "gemini"
                assert self.gemini is not None
                log_event(
                    logger,
                    "llm_failover",
                    "Failing over LLM to Gemini",
                    level=30,
                    from_provider=provider_name,
                    to_provider="gemini",
                    reason=exc.reason,
                    failed_latency_ms=latency_ms,
                )
                # Re-enter through the same path with Gemini selected.
                fallback_started = time.perf_counter()
                fb_model = self.gemini.chat_model
                log_event(
                    logger,
                    "ai_route_selected",
                    "LLM route → gemini",
                    capability="llm",
                    provider="gemini",
                    model=fb_model,
                    source="fallback",
                    reason=exc.reason,
                )
                log_event(
                    logger,
                    "fallback_activated",
                    "LLM fallback activated",
                    capability="llm",
                    provider="gemini",
                    reason=exc.reason,
                )
                log_event(
                    logger,
                    "llm_request_started",
                    f"LLM request started ({fb_model})",
                    operation=ctx.get("operation", "other"),
                    provider="gemini",
                    provider_source="fallback",
                    model_name=fb_model,
                    prompt_version=ctx.get("prompt_version"),
                    retrieved_chunk_ids=ctx.get("retrieved_chunk_ids"),
                    similarity_scores=ctx.get("similarity_scores"),
                )
                try:
                    result = self.gemini.complete(
                        messages, temperature=temperature, max_tokens=max_tokens
                    )
                except LLMError as gemini_exc:
                    fb_latency = int((time.perf_counter() - fallback_started) * 1000)
                    log_event(
                        logger,
                        "llm_request_failed",
                        f"LLM fallback failed: {gemini_exc.reason}",
                        level=40,
                        provider="gemini",
                        model=fb_model,
                        error_type=gemini_exc.reason,
                        error_message=str(gemini_exc)[:300],
                        latency_ms=fb_latency,
                        retryable=gemini_exc.retryable,
                    )
                    raise
                fb_latency = int((time.perf_counter() - fallback_started) * 1000)
                usage = result.usage or {}
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                total_tokens = (
                    input_tokens + output_tokens
                    if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                    else None
                )
                fb_fields = {
                    "operation": ctx.get("operation", "other"),
                    "provider": result.provider or "gemini",
                    "provider_source": "fallback",
                    "model_name": result.model or fb_model,
                    "latency_ms": fb_latency,
                    "input_tokens": input_tokens if isinstance(input_tokens, int) else None,
                    "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
                    "total_tokens": total_tokens,
                    "response_chars": len(result.text or ""),
                    "retrieved_chunk_ids": ctx.get("retrieved_chunk_ids"),
                    "similarity_scores": ctx.get("similarity_scores"),
                    "prompt_version": ctx.get("prompt_version"),
                    "error_message": None,
                }
                if flags.get("log_ai_content"):
                    fb_fields["final_response"] = maybe_content(
                        result.text,
                        enabled=True,
                        max_chars=flags["log_ai_content_max_chars"],
                    )
                log_event(
                    logger,
                    "llm_request_completed",
                    f"LLM fallback completed in {fb_latency}ms",
                    **fb_fields,
                )
                return result
            if source == "remote":
                self._llm_breaker.record_failure(exc.reason)
            log_event(
                logger,
                "llm_request_failed",
                f"LLM request failed: {exc.reason}",
                level=40,
                provider=provider_name,
                model=model_name,
                error_type=exc.reason,
                error_message=str(exc)[:300],
                latency_ms=latency_ms,
                retryable=exc.retryable,
            )
            raise

    def _select_llm(self) -> tuple[Any, LlmSource]:
        if self.mode == "fallback":
            if not self._gemini_ready() or self.gemini is None:
                raise LLMError(
                    "Gemini fallback is not configured.",
                    provider="gemini",
                    reason="provider_unavailable",
                    retryable=False,
                )
            self._fallback_reason = "mode_fallback"
            return self.gemini, "gemini"

        if self.mode == "remote" or self._llm_remote_online():
            return self.remote, "remote"

        if self._gemini_ready() and self.gemini is not None and self.mode == "auto":
            self._fallback_reason = (
                self._llm_breaker.last.reason if self._llm_breaker.last else "remote_offline"
            )
            return self.gemini, "gemini"

        raise LLMError(
            "No LLM provider is available.",
            provider=self.name,
            reason="provider_unavailable",
            retryable=True,
        )

    # ------------------------------------------------------------------- embed

    def embed(self, texts: list[str], *, task: TaskType = "document") -> list[list[float]]:
        source = self._select_embed_source()
        self._active_embed = source
        started = time.perf_counter()
        if source == "remote":
            if self._routing_enabled():
                log_event(
                    logger,
                    "ai_route_selected",
                    "Embedding route → remote",
                    capability="embedding",
                    provider="remote_openai_compatible",
                    model=self.embedding_model,
                    dimensions=self.embedding_dimensions,
                    source="primary",
                )
                log_event(
                    logger,
                    "embedding_started",
                    "Embedding started",
                    provider="remote",
                    model=self.embedding_model,
                    dimensions=self.embedding_dimensions,
                    batch_size=self.profile.batch_size,
                    input_count=len(texts),
                    task=task,
                )
            try:
                vectors = self._remote_embed(texts, task=task)
                self._embed_breaker.record_success()
                if self._routing_enabled():
                    log_event(
                        logger,
                        "embedding_completed",
                        "Embedding completed",
                        provider="remote",
                        model=self.embedding_model,
                        dimensions=self.embedding_dimensions,
                        input_count=len(texts),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                return vectors
            except LLMError as exc:
                if exc.retryable and self.mode == "auto" and self._local_fallback_allowed():
                    self._embed_breaker.record_failure(exc.reason)
                    self._fallback_reason = exc.reason
                    self._active_embed = "local"
                    assert self.local_embedder is not None
                    self.embedding_model = self.local_embedder.model_id
                    if self._routing_enabled():
                        log_event(
                            logger,
                            "embedding_failover",
                            "Failing over embeddings to local Nomic",
                            level=30,
                            from_provider="remote",
                            to_provider="local_sentence_transformers",
                            reason=exc.reason,
                        )
                        log_event(
                            logger,
                            "fallback_activated",
                            "Embedding fallback activated",
                            capability="embedding",
                            provider="local_sentence_transformers",
                            reason=exc.reason,
                        )
                        log_event(
                            logger,
                            "ai_route_selected",
                            "Embedding route → local",
                            capability="embedding",
                            provider="local_sentence_transformers",
                            model=self.local_embedder.model_id,
                            dimensions=self.embedding_dimensions,
                            source="fallback",
                            reason=exc.reason,
                        )
                        log_event(
                            logger,
                            "embedding_started",
                            "Local embedding started",
                            provider="local",
                            model=self.local_embedder.model_id,
                            dimensions=self.embedding_dimensions,
                            batch_size=self.profile.batch_size,
                            input_count=len(texts),
                            task=task,
                        )
                    local_started = time.perf_counter()
                    vectors = self.local_embedder.embed(texts, task=task)
                    if self._routing_enabled():
                        log_event(
                            logger,
                            "embedding_completed",
                            "Local embedding completed",
                            provider="local",
                            model=self.local_embedder.model_id,
                            dimensions=self.embedding_dimensions,
                            input_count=len(texts),
                            latency_ms=int((time.perf_counter() - local_started) * 1000),
                        )
                    return vectors
                self._embed_breaker.record_failure(exc.reason)
                raise

        # source == "local" — selection already applied mode-specific gates
        # (compat for auto; readiness-only for forced fallback).
        if self.local_embedder is None or not self._local_embed_ready():
            raise LLMError(
                "Local embedding fallback is unavailable.",
                provider="local_nomic",
                reason="provider_unavailable",
                retryable=False,
            )
        self.embedding_model = self.local_embedder.model_id
        if self._routing_enabled():
            log_event(
                logger,
                "ai_route_selected",
                "Embedding route → local",
                capability="embedding",
                provider="local_sentence_transformers",
                model=self.local_embedder.model_id,
                dimensions=self.embedding_dimensions,
                source="fallback",
                reason=self._fallback_reason,
            )
            log_event(
                logger,
                "embedding_started",
                "Local embedding started",
                provider="local",
                model=self.local_embedder.model_id,
                dimensions=self.embedding_dimensions,
                batch_size=self.profile.batch_size,
                input_count=len(texts),
                task=task,
            )
        vectors = self.local_embedder.embed(texts, task=task)
        if self._routing_enabled():
            log_event(
                logger,
                "embedding_completed",
                "Local embedding completed",
                provider="local",
                model=self.local_embedder.model_id,
                dimensions=self.embedding_dimensions,
                input_count=len(texts),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        return vectors

    def _select_embed_source(self) -> EmbedSource:
        if self.mode == "fallback":
            if not self._local_embed_ready():
                raise LLMError(
                    "Local embedding model is unavailable.",
                    provider="local_nomic",
                    reason="provider_unavailable",
                    retryable=False,
                )
            # Forced fallback: use local for development/testing even when remote
            # compatibility was never verified or previously failed.
            self._fallback_reason = "mode_fallback"
            self.embedding_model = (
                self.local_embedder.model_id if self.local_embedder else self.embedding_model
            )
            return "local"

        # Prefer remote model id while remote is selected.
        self.embedding_model = getattr(self.remote, "embedding_model", self.profile.model_family)

        if self.mode == "remote" or self._embed_remote_online():
            return "remote"

        if self.mode == "auto" and self._local_fallback_allowed():
            self._fallback_reason = (
                self._embed_breaker.last.reason
                if self._embed_breaker.last
                else "remote_embeddings_offline"
            )
            if self.local_embedder:
                self.embedding_model = self.local_embedder.model_id
            return "local"

        raise LLMError(
            "No embedding provider is available.",
            provider=self.name,
            reason="provider_unavailable",
            retryable=True,
        )

    def _local_fallback_allowed(self) -> bool:
        if not self._local_embed_ready():
            return False
        if self.mode == "fallback":
            return True
        # Prefer a prior successful compat test. If remote is currently down and
        # we never tested, block fallback to avoid mixed spaces.
        with self._compat_lock:
            if self._compat.compatible is True:
                return True
            if self._compat.compatible is False:
                return False
        if self._embed_remote_online():
            return self.ensure_embedding_compatibility()
        return False

    def _remote_embed(self, texts: list[str], *, task: TaskType) -> list[list[float]]:
        embed = self.remote.embed
        try:
            return embed(texts, task=task)  # type: ignore[call-arg]
        except TypeError:
            prepared = self.profile.prepare(texts, task=task)
            vectors = embed(prepared)
            float_vectors = [list(map(float, v)) for v in vectors]
            self.profile.validate_dimensions(float_vectors)
            return self.profile.postprocess(float_vectors)

    # ---------------------------------------------------------------- snapshot

    def runtime_snapshot(self) -> RuntimeSnapshot:
        self._refresh_probes()
        llm_remote: OnlineStatus = "online" if self._llm_remote_online() else "offline"
        emb_remote: OnlineStatus = "online" if self._embed_remote_online() else "offline"
        # Resolve active without performing work.
        if self.mode == "fallback":
            llm_active: LlmSource = "gemini"
            emb_active: EmbedSource = "local"
            self._fallback_reason = "mode_fallback"
        else:
            llm_active = "remote" if llm_remote == "online" else (
                "gemini" if self._gemini_ready() else "remote"
            )
            if emb_remote == "online":
                emb_active = "remote"
            elif self._local_fallback_allowed():
                emb_active = "local"
            else:
                emb_active = "remote"
        self._active_llm = llm_active
        self._active_embed = emb_active

        local_ready: Readiness = "ready" if self._local_embed_ready() else "unavailable"
        gemini_ready: Readiness = "ready" if self._gemini_ready() else "unavailable"
        # Report last measured compat truthfully; forced fallback does not require it.
        compatible = bool(self._compat.compatible) if self._compat.compatible is not None else False
        if (
            self.mode != "fallback"
            and emb_remote == "online"
            and self._local_embed_ready()
            and self._compat.compatible is None
        ):
            compatible = self.ensure_embedding_compatibility()

        remote_overall: OnlineStatus = (
            "online" if llm_remote == "online" or emb_remote == "online" else "offline"
        )
        if llm_remote == "online" and emb_remote == "online" and self.mode != "fallback":
            overall: Literal["healthy", "fallback_active", "degraded"] = "healthy"
        elif llm_active == "gemini" or emb_active == "local" or self.mode == "fallback":
            overall = "fallback_active"
        else:
            overall = "degraded"

        model = (
            self.gemini.chat_model
            if llm_active == "gemini" and self.gemini
            else self.chat_model
        )
        emb_model = (
            self.local_embedder.model_id
            if emb_active == "local" and self.local_embedder
            else getattr(self.remote, "embedding_model", self.profile.model_family)
        )
        if emb_active == "local":
            self.embedding_model = emb_model

        if self.mode == "fallback":
            reason: str | None = "mode_fallback"
        else:
            reason = self._fallback_reason or (
                self._compat.reason if not compatible else None
            )

        return RuntimeSnapshot(
            mode=self.mode,
            remote_status=remote_overall,
            llm_active=llm_active,
            llm_model=model,
            llm_remote=llm_remote,
            llm_fallback=gemini_ready,
            embedding_active=emb_active,
            embedding_model=emb_model,
            embedding_dimensions=self.embedding_dimensions,
            embedding_remote=emb_remote,
            embedding_local=local_ready,
            embedding_compatible=compatible,
            last_health_check_at=self._last_health_check_at,
            fallback_reason=reason,
            overall=overall,
        )
