"""Structured logging: correlation, redaction, AI/retrieval observability."""

from __future__ import annotations

import io
import logging

import pytest

from app.core.logging import (
    ConsoleFormatter,
    JsonFormatter,
    RequestIdFilter,
    configure_logging,
    ensure_request_id,
    get_logger,
    log_event,
    maybe_content,
    new_request_id,
    request_id_var,
    set_llm_call_context,
    reset_llm_call_context,
)
from app.core.redaction import redact_mapping, sanitize_text
from app.integrations.llm.base import ChatMessage, Completion
from app.integrations.llm.embedding_profile import NOMIC_V15_PROFILE
from app.integrations.llm.errors import LLMError
from app.integrations.llm.router import RoutingLLMProvider


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def capture_logs():
    configure_logging("DEBUG", log_format="console")
    handler = _Capture()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(ConsoleFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    yield handler
    root.removeHandler(handler)


def test_request_id_format_and_propagation(capture_logs):
    rid = new_request_id()
    assert rid.startswith("req_")
    token = request_id_var.set(rid)
    try:
        log_event(get_logger("test"), "probe_event", "hello", foo=1)
    finally:
        request_id_var.reset(token)
    assert capture_logs.records
    assert capture_logs.records[-1].request_id == rid
    assert getattr(capture_logs.records[-1], "event") == "probe_event"


def test_timestamp_present_in_console_and_json():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", (), None)
    record.request_id = "req_abc"
    record.event = "http_request_started"
    record.extra_fields = {"method": "GET"}
    console = ConsoleFormatter().format(record)
    assert "| INFO |" in console
    assert "req_abc" in console
    assert "http_request_started" in console
    # Date-like prefix YYYY-MM-DD
    assert console[0:4].isdigit() and console[4] == "-"
    payload = JsonFormatter().format(record)
    assert '"timestamp"' in payload
    assert "req_abc" in payload


def test_secrets_redacted():
    cleaned = redact_mapping(
        {
            "authorization": "Bearer secret",
            "GEMINI_API_KEY": "abc",
            "safe": "ok",
            "nested": {"llm_api_key": "x", "count": 1},
        }
    )
    assert cleaned["authorization"] == "[REDACTED]"
    assert cleaned["GEMINI_API_KEY"] == "[REDACTED]"
    assert cleaned["safe"] == "ok"
    assert cleaned["nested"]["llm_api_key"] == "[REDACTED]"
    assert "secret" not in sanitize_text("Authorization: Bearer abcdef password=1")
    url = "POST https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=AIzaSySecretKeyValue1234567890abcd"
    scrubbed = sanitize_text(url)
    assert "AIzaSySecretKeyValue1234567890abcd" not in scrubbed
    assert "key=[REDACTED]" in scrubbed


def test_ai_content_gated(monkeypatch):
    assert maybe_content("hello", enabled=False, max_chars=10) is None
    text = maybe_content("x" * 50, enabled=True, max_chars=20)
    assert text is not None and len(text) <= 20


def _fake_remote(*, fail_complete=False, llm_up=True):
    class Remote:
        name = "openai_compatible"
        chat_model = "qwen/qwen2.5-vl-7b"
        embedding_model = "text-embedding-nomic-embed-text-v1.5"
        embedding_dimensions = 768

        def health(self):
            return llm_up

        def health_llm(self):
            return llm_up

        def health_embeddings(self):
            return True

        def complete(self, messages, *, temperature=0.2, max_tokens=None):
            if fail_complete:
                raise LLMError(
                    "down",
                    provider=self.name,
                    reason="connection_refused",
                    retryable=True,
                )
            return Completion(
                text="[]",
                model=self.chat_model,
                provider=self.name,
                usage={"prompt_tokens": 10, "completion_tokens": 2},
            )

        def embed(self, texts, *, task="document"):
            return [[0.1] * 768 for _ in texts]

    return Remote()


def _fake_gemini():
    class Gemini:
        name = "gemini"
        chat_model = "gemini-2.5-flash"
        embedding_model = "unused"
        embedding_dimensions = 768
        api_key = "test"

        def health(self):
            return True

        def complete(self, messages, *, temperature=0.2, max_tokens=None):
            return Completion(text="[]", model=self.chat_model, provider=self.name, usage={})

        def embed(self, texts):
            raise LLMError("no", provider=self.name, reason="provider_unavailable", retryable=False)

    return Gemini()


def test_llm_provider_model_and_token_logging(capture_logs, monkeypatch):
    monkeypatch.setenv("LOG_AI_ROUTING", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    router = RoutingLLMProvider(
        mode="auto",
        remote=_fake_remote(),
        gemini=_fake_gemini(),
        local_embedder=None,
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=0,
    )
    token = set_llm_call_context(operation="ckm_extraction", prompt_version="v2")
    try:
        result = router.complete([ChatMessage(role="user", content="hi")])
    finally:
        reset_llm_call_context(token)
    events = [getattr(r, "event", None) for r in capture_logs.records]
    assert "ai_route_selected" in events
    assert "llm_request_started" in events
    assert "llm_request_completed" in events
    completed = next(
        r for r in capture_logs.records if getattr(r, "event", None) == "llm_request_completed"
    )
    fields = completed.extra_fields
    assert fields["provider"] == "openai_compatible"
    assert fields["model_name"] == "qwen/qwen2.5-vl-7b"
    assert fields["input_tokens"] == 10
    assert fields["output_tokens"] == 2
    assert fields["total_tokens"] == 12
    assert "final_response" not in fields
    assert result.text == "[]"
    get_settings.cache_clear()


def test_remote_to_gemini_failover_log(capture_logs, monkeypatch):
    monkeypatch.setenv("LOG_AI_ROUTING", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    router = RoutingLLMProvider(
        mode="auto",
        remote=_fake_remote(fail_complete=True, llm_up=True),
        gemini=_fake_gemini(),
        local_embedder=None,
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=0,
    )
    router.complete([ChatMessage(role="user", content="hi")])
    events = [getattr(r, "event", None) for r in capture_logs.records]
    assert "llm_failover" in events
    assert "fallback_activated" in events
    completed = [
        r for r in capture_logs.records if getattr(r, "event", None) == "llm_request_completed"
    ][-1]
    assert completed.extra_fields["provider"] == "gemini"
    assert completed.extra_fields["provider_source"] == "fallback"
    # Gemini fake returns empty usage → null tokens
    assert completed.extra_fields.get("input_tokens") is None
    get_settings.cache_clear()


def test_embedding_failover_and_no_vectors_logged(capture_logs, monkeypatch):
    monkeypatch.setenv("LOG_AI_ROUTING", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class Local:
        name = "local_nomic"
        model_id = "nomic-ai/nomic-embed-text-v1.5"
        ready = True

        def embed(self, texts, *, task="document"):
            return [[0.2] * 768 for _ in texts]

    class RemoteDownEmbed(_fake_remote().__class__):
        def health_embeddings(self):
            return False

        def embed(self, texts, *, task="document"):
            raise LLMError(
                "embed down",
                provider="openai_compatible",
                reason="connection_refused",
                retryable=True,
            )

    remote = RemoteDownEmbed()
    local = Local()
    router = RoutingLLMProvider(
        mode="auto",
        remote=remote,
        gemini=_fake_gemini(),
        local_embedder=local,
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=0,
    )
    router._compat.compatible = True
    vectors = router.embed(["hello"])
    assert len(vectors[0]) == 768
    blob = " ".join(str(getattr(r, "extra_fields", {})) for r in capture_logs.records)
    assert "0.2" not in blob  # no vector values
    events = [getattr(r, "event", None) for r in capture_logs.records]
    assert "embedding_failover" in events or "ai_route_selected" in events
    get_settings.cache_clear()


def test_compatibility_logging(capture_logs, monkeypatch):
    monkeypatch.setenv("LOG_AI_ROUTING", "true")
    from app.core.config import get_settings
    from app.integrations.llm.embedding_profile import (
        COMPAT_SENTINEL_DOCUMENT,
        COMPAT_SENTINEL_QUERY,
    )
    import math

    get_settings.cache_clear()

    def unit(seed):
        raw = [math.sin(seed + i * 0.01) for i in range(768)]
        n = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / n for x in raw]

    class Remote:
        name = "openai_compatible"
        chat_model = "x"
        embedding_model = "text-embedding-nomic-embed-text-v1.5"
        embedding_dimensions = 768

        def health(self):
            return True

        def health_llm(self):
            return True

        def health_embeddings(self):
            return True

        def complete(self, *a, **k):
            raise NotImplementedError

        def embed(self, texts, *, task="document"):
            out = []
            for text in texts:
                seed = 1.0 if text == COMPAT_SENTINEL_QUERY else 2.0
                out.append(unit(seed))
            return out

    class Local:
        model_id = "nomic-ai/nomic-embed-text-v1.5"
        ready = True

        def embed(self, texts, *, task="document"):
            out = []
            for text in texts:
                seed = 1.0 if text == COMPAT_SENTINEL_QUERY else 2.0
                out.append(unit(seed))
            return out

    router = RoutingLLMProvider(
        mode="auto",
        remote=Remote(),
        gemini=_fake_gemini(),
        local_embedder=Local(),
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=0,
        compat_min_cosine=0.85,
    )
    assert router.ensure_embedding_compatibility() is True
    events = [getattr(r, "event", None) for r in capture_logs.records]
    assert "embedding_compatibility_check" in events
    get_settings.cache_clear()


def test_error_logging_on_llm_failure(capture_logs, monkeypatch):
    monkeypatch.setenv("LOG_AI_ROUTING", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class DeadRemote(_fake_remote().__class__):
        def health_llm(self):
            return True

        def complete(self, *a, **k):
            raise LLMError(
                "bad",
                provider="openai_compatible",
                reason="invalid_response",
                retryable=False,
            )

    router = RoutingLLMProvider(
        mode="auto",
        remote=DeadRemote(),
        gemini=_fake_gemini(),
        local_embedder=None,
        profile=NOMIC_V15_PROFILE,
        cooldown_seconds=0,
    )
    with pytest.raises(LLMError):
        router.complete([ChatMessage(role="user", content="x")])
    events = [getattr(r, "event", None) for r in capture_logs.records]
    assert "llm_request_failed" in events
    get_settings.cache_clear()


def test_ensure_request_id_prefix():
    assert ensure_request_id(None).startswith("req_")
    assert ensure_request_id("req_abc") == "req_abc"
    assert ensure_request_id("abcdef").startswith("req_")


def test_runtime_unchanged_ai_availability(client, auth_headers, company, monkeypatch):
    """Existing structured 503 behaviour still works with logging enabled."""
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class Down:
        name = "openai_compatible"
        chat_model = "x"
        embedding_model = "y"
        embedding_dimensions = 768

        def health(self):
            return False

    monkeypatch.setattr("app.integrations.llm.factory.get_llm_provider", lambda: Down())
    try:
        response = client.post(
            f"/api/v1/companies/{company['id']}/knowledge-objects/extract",
            headers=auth_headers,
        )
    finally:
        get_settings.cache_clear()
    assert response.status_code == 503
    assert response.json()["code"] == "AI_SERVICE_UNAVAILABLE"
    assert "X-Request-ID" in response.headers or "x-request-id" in {
        k.lower() for k in response.headers.keys()
    }
