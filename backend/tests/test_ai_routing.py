"""Automatic AI primary/fallback routing."""

from __future__ import annotations

import math

import pytest

from app.core.config import get_settings
from app.integrations.llm.base import ChatMessage, Completion
from app.integrations.llm.embedding_profile import (
    COMPAT_SENTINEL_DOCUMENT,
    COMPAT_SENTINEL_QUERY,
    NOMIC_V15_PROFILE,
    cosine_similarity,
)
from app.integrations.llm.errors import LLMError
from app.integrations.llm.factory import reset_llm_provider
from app.integrations.llm.router import RoutingLLMProvider


def _unit(seed: float, dims: int = 768) -> list[float]:
    raw = [math.sin(seed + i * 0.01) for i in range(dims)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


class FakeRemote:
    name = "openai_compatible"
    chat_model = "remote-chat"
    embedding_model = "nomic-embed-text"
    embedding_dimensions = 768

    def __init__(self, *, llm_up=True, embed_up=True, fail_complete=False, fail_embed=False):
        self.llm_up = llm_up
        self.embed_up = embed_up
        self.fail_complete = fail_complete
        self.fail_embed = fail_embed
        self.complete_calls = 0
        self.embed_calls = 0

    def health(self):
        return self.llm_up

    def health_llm(self):
        return self.llm_up

    def health_embeddings(self):
        return self.embed_up

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        self.complete_calls += 1
        if self.fail_complete or not self.llm_up:
            raise LLMError(
                "remote down",
                provider=self.name,
                reason="connection_refused",
                retryable=True,
            )
        return Completion(text='[{"type":"role","label":"QA"}]', model=self.chat_model, provider=self.name)

    def embed(self, texts, *, task="document"):
        self.embed_calls += 1
        if self.fail_embed or not self.embed_up:
            raise LLMError(
                "embed down",
                provider=self.name,
                reason="connection_refused",
                retryable=True,
            )
        out = []
        for text in texts:
            seed = 1.0 if text == COMPAT_SENTINEL_QUERY else 2.0
            if text == COMPAT_SENTINEL_DOCUMENT:
                seed = 2.0
            elif "query" in task:
                seed = 1.0
            out.append(_unit(seed))
        return out


class FakeGemini:
    name = "gemini"
    chat_model = "gemini-2.5-flash"
    embedding_model = "unused"
    embedding_dimensions = 768
    api_key = "test-key"

    def __init__(self, *, up=True):
        self.up = up
        self.complete_calls = 0

    def health(self):
        return self.up and bool(self.api_key)

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        self.complete_calls += 1
        if not self.up:
            raise LLMError(
                "gemini down",
                provider=self.name,
                reason="provider_unavailable",
                retryable=True,
            )
        return Completion(text="[]", model=self.chat_model, provider=self.name)

    def embed(self, texts):
        raise LLMError("no embed", provider=self.name, reason="provider_unavailable", retryable=False)


class FakeLocal:
    name = "local_nomic"
    model_id = "nomic-ai/nomic-embed-text-v1.5"
    embedding_model = model_id
    embedding_dimensions = 768

    def __init__(self, *, ready=True, drift=0.0):
        self._ready = ready
        self.drift = drift
        self.embed_calls = 0
        self.unavailable_reason = None if ready else "local_model_load_failed"

    @property
    def ready(self):
        return self._ready

    def embed(self, texts, *, task="document"):
        self.embed_calls += 1
        if not self._ready:
            raise LLMError(
                "local unavailable",
                provider=self.name,
                reason="provider_unavailable",
                retryable=False,
            )
        out = []
        for text in texts:
            seed = 1.0 if text == COMPAT_SENTINEL_QUERY or task == "query" else 2.0
            if text == COMPAT_SENTINEL_DOCUMENT:
                seed = 2.0
            vector = _unit(seed + self.drift)
            out.append(vector)
        return out


def _router(
    *,
    mode="auto",
    remote=None,
    gemini=None,
    local=None,
    cooldown=0.0,
    min_cos=0.85,
) -> RoutingLLMProvider:
    return RoutingLLMProvider(
        mode=mode,
        remote=remote or FakeRemote(),
        gemini=gemini if gemini is not None else FakeGemini(),
        local_embedder=local if local is not None else FakeLocal(),
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=cooldown,
        compat_min_cosine=min_cos,
    )


def test_remote_llm_and_embedding_healthy():
    remote = FakeRemote()
    local = FakeLocal()
    r = _router(remote=remote, local=local)
    assert r.ensure_embedding_compatibility() is True
    completion = r.complete([ChatMessage(role="user", content="hi")])
    assert completion.provider == "openai_compatible"
    vectors = r.embed(["doc text"])
    assert len(vectors[0]) == 768
    assert remote.complete_calls == 1
    assert remote.embed_calls >= 1
    snap = r.runtime_snapshot()
    assert snap.overall == "healthy"
    assert snap.llm_active == "remote"
    assert snap.embedding_active == "remote"


def test_remote_fully_offline_uses_gemini_and_local():
    remote = FakeRemote(llm_up=False, embed_up=False)
    gemini = FakeGemini()
    local = FakeLocal()
    r = _router(remote=remote, gemini=gemini, local=local)
    # Seed compat as previously verified while remote was up.
    r._compat.compatible = True
    completion = r.complete([ChatMessage(role="user", content="hi")])
    assert completion.provider == "gemini"
    vectors = r.embed(["doc"])
    assert len(vectors[0]) == 768
    assert gemini.complete_calls == 1
    assert local.embed_calls == 1
    snap = r.runtime_snapshot()
    assert snap.overall == "fallback_active"
    assert snap.llm_active == "gemini"
    assert snap.embedding_active == "local"


def test_remote_llm_fails_embedding_still_remote():
    remote = FakeRemote(llm_up=False, embed_up=True)
    gemini = FakeGemini()
    r = _router(remote=remote, gemini=gemini)
    r._compat.compatible = True
    assert r.complete([ChatMessage(role="user", content="x")]).provider == "gemini"
    before = remote.embed_calls
    r.embed(["keep remote embed"])
    assert remote.embed_calls == before + 1


def test_remote_embedding_fails_llm_still_remote():
    remote = FakeRemote(llm_up=True, embed_up=False)
    local = FakeLocal()
    r = _router(remote=remote, local=local)
    r._compat.compatible = True
    assert r.complete([ChatMessage(role="user", content="x")]).provider == "openai_compatible"
    r.embed(["fallback embed"])
    assert local.embed_calls == 1


def test_both_llm_providers_fail_raises():
    remote = FakeRemote(llm_up=False)
    gemini = FakeGemini(up=False)
    r = _router(remote=remote, gemini=gemini)
    with pytest.raises(LLMError) as raised:
        r.complete([ChatMessage(role="user", content="x")])
    assert raised.value.retryable is True


def test_local_embedding_unavailable_blocks_fallback():
    remote = FakeRemote(embed_up=False)
    local = FakeLocal(ready=False)
    r = _router(remote=remote, local=local)
    with pytest.raises(LLMError) as raised:
        r.embed(["x"])
    assert raised.value.reason == "provider_unavailable"


def test_incompatible_embedding_profile_blocks_fallback():
    remote = FakeRemote()
    local = FakeLocal(drift=10.0)  # orthogonal-ish space
    r = _router(remote=remote, local=local, min_cos=0.99)
    assert r.ensure_embedding_compatibility() is False
    remote.embed_up = False
    with pytest.raises(LLMError):
        r.embed(["x"])
    snap = r.runtime_snapshot()
    assert snap.embedding_compatible is False
    assert snap.embedding_local == "ready"


def test_fallback_mode_uses_local_when_remote_offline_even_if_incompatible():
    remote = FakeRemote(llm_up=False, embed_up=False)
    local = FakeLocal()
    r = _router(mode="fallback", remote=remote, local=local)
    # Simulate a prior failed auto-mode compat check (must not block forced fallback).
    r._compat.compatible = False
    r._compat.reason = "cosine_below_threshold"
    vectors = r.embed(["document text for local path"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 768
    assert local.embed_calls == 1
    snap = r.runtime_snapshot()
    assert snap.mode == "fallback"
    assert snap.embedding_active == "local"
    assert snap.embedding_model == local.model_id
    assert snap.embedding_dimensions == 768
    assert snap.embedding_local == "ready"
    assert snap.overall == "fallback_active"
    assert snap.fallback_reason == "mode_fallback"


def test_auto_mode_still_blocks_unverified_incompatible_fallback():
    remote = FakeRemote(embed_up=False)
    local = FakeLocal()
    r = _router(mode="auto", remote=remote, local=local)
    # Never verified and remote offline → blocked.
    with pytest.raises(LLMError) as raised:
        r.embed(["x"])
    assert raised.value.reason == "provider_unavailable"
    snap = r.runtime_snapshot()
    assert snap.embedding_active == "remote"
    assert snap.embedding_compatible is False


def test_runtime_status_matches_executable_embedding_route():
    remote = FakeRemote(embed_up=False)
    local = FakeLocal()
    r = _router(mode="fallback", remote=remote, local=local)
    snap = r.runtime_snapshot()
    assert snap.embedding_active == "local"
    assert snap.embedding_model == "nomic-ai/nomic-embed-text-v1.5"
    vectors = r.embed(["route check"])
    assert len(vectors[0]) == 768
    assert r.embedding_model == local.model_id


def test_automatic_recovery_when_remote_returns():
    remote = FakeRemote(llm_up=False, embed_up=False)
    gemini = FakeGemini()
    local = FakeLocal()
    r = _router(remote=remote, gemini=gemini, local=local, cooldown=0.0)
    r._compat.compatible = True
    assert r.complete([ChatMessage(role="user", content="a")]).provider == "gemini"
    remote.llm_up = True
    remote.embed_up = True
    assert r.complete([ChatMessage(role="user", content="b")]).provider == "openai_compatible"
    snap = r.runtime_snapshot()
    assert snap.llm_remote == "online"


def test_non_retryable_remote_error_does_not_fallback():
    remote = FakeRemote()

    def bad_complete(*_a, **_k):
        raise LLMError(
            "bad request",
            provider="openai_compatible",
            reason="invalid_response",
            retryable=False,
        )

    remote.complete = bad_complete  # type: ignore[method-assign]
    gemini = FakeGemini()
    r = _router(remote=remote, gemini=gemini)
    with pytest.raises(LLMError) as raised:
        r.complete([ChatMessage(role="user", content="x")])
    assert raised.value.reason == "invalid_response"
    assert gemini.complete_calls == 0


def test_runtime_endpoint_never_exposes_secrets(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-gemini-key")
    monkeypatch.setenv("AI_ROUTING_MODE", "auto")
    get_settings.cache_clear()
    reset_llm_provider()

    remote = FakeRemote(llm_up=False, embed_up=False)
    gemini = FakeGemini()
    local = FakeLocal()
    provider = _router(remote=remote, gemini=gemini, local=local)
    provider._compat.compatible = True
    monkeypatch.setattr(
        "app.modules.ai.router.get_llm_provider",
        lambda: provider,
    )
    try:
        response = client.get("/api/v1/ai/runtime", headers=auth_headers)
    finally:
        get_settings.cache_clear()
        reset_llm_provider()

    assert response.status_code == 200
    body = response.json()
    dumped = str(body)
    assert "super-secret-gemini-key" not in dumped
    assert "api_key" not in dumped.lower()
    assert body["llm"]["active"] == "gemini"
    assert body["embedding"]["dimensions"] == 768
    assert "overall" in body


def test_cosine_helper_and_profile_dimensions():
    a = _unit(1.0)
    assert cosine_similarity(a, a) == pytest.approx(1.0)
    assert NOMIC_V15_PROFILE.dimensions == 768
    prepared = NOMIC_V15_PROFILE.prepare(["hello"], task="document")
    assert prepared == ["hello"]
