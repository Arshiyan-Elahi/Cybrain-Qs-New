"""AI provider failure classification and structured 503 responses."""

import httpx
import pytest

from app.core.config import get_settings
from app.integrations.llm.errors import (
    LLMError,
    classify_httpx_error,
    invalid_response,
    to_ai_service_unavailable,
)
from app.integrations.llm.openai_compatible import OpenAICompatibleProvider


def test_classify_connect_timeout():
    err = classify_httpx_error(
        httpx.ConnectTimeout("timed out"),
        provider="openai_compatible",
        base_url="http://100.79.187.86:1234/v1",
    )
    assert err.reason == "connect_timeout"
    assert err.retryable is True


def test_classify_connection_refused():
    err = classify_httpx_error(
        httpx.ConnectError("[Errno 111] Connection refused"),
        provider="openai_compatible",
        base_url="http://100.79.187.86:1234/v1",
    )
    assert err.reason == "connection_refused"


def test_classify_host_unreachable():
    err = classify_httpx_error(
        httpx.ConnectError("Network is unreachable"),
        provider="ollama",
        base_url="http://localhost:11434",
    )
    assert err.reason == "host_unreachable"
    assert err.provider == "ollama"


def test_classify_read_timeout():
    err = classify_httpx_error(
        httpx.ReadTimeout("read timed out"),
        provider="openai_compatible",
        base_url="http://example",
    )
    assert err.reason == "read_timeout"


def test_classify_model_unavailable_status():
    request = httpx.Request("POST", "http://example/v1/chat/completions")
    response = httpx.Response(404, request=request, text='{"error":"model not found"}')
    err = classify_httpx_error(
        httpx.HTTPStatusError("missing", request=request, response=response),
        provider="openai_compatible",
        base_url="http://example/v1",
    )
    assert err.reason == "model_unavailable"
    assert err.status_code == 404


def test_invalid_response_is_not_retryable():
    err = invalid_response("openai_compatible", "AI service returned no chat choices.")
    assert err.reason == "invalid_response"
    assert err.retryable is False


def test_to_ai_service_unavailable_shape():
    mapped = to_ai_service_unavailable(
        LLMError("down", provider="openai_compatible", reason="connection_refused")
    )
    assert mapped.status_code == 503
    assert mapped.code == "AI_SERVICE_UNAVAILABLE"
    assert mapped.provider == "openai_compatible"
    assert mapped.retryable is True
    assert mapped.details["reason"] == "connection_refused"


def test_openai_compatible_complete_maps_connect_error(monkeypatch):
    provider = OpenAICompatibleProvider(
        base_url="http://100.79.187.86:1234/v1",
        chat_model="qwen",
        embedding_model="embed",
        embedding_dimensions=768,
        timeout=10,
    )

    def boom(*_args, **_kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(LLMError) as raised:
        from app.integrations.llm.base import ChatMessage

        provider.complete([ChatMessage(role="user", content="hi")])
    assert raised.value.reason == "connection_refused"


def test_extract_returns_structured_503_when_ai_unreachable(
    client, auth_headers, company, monkeypatch
):
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    get_settings.cache_clear()

    class DownProvider:
        name = "openai_compatible"
        chat_model = "x"
        embedding_model = "y"
        embedding_dimensions = 768

        def health(self):
            return False

    monkeypatch.setattr(
        "app.integrations.llm.factory.get_llm_provider",
        lambda: DownProvider(),
    )

    try:
        response = client.post(
            f"/api/v1/companies/{company['id']}/knowledge-objects/extract",
            headers=auth_headers,
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "AI_SERVICE_UNAVAILABLE"
    assert body["message"] == "The configured AI service is currently unavailable."
    assert body["provider"] == "openai_compatible"
    assert body["retryable"] is True
    assert body["error"]["code"] == "AI_SERVICE_UNAVAILABLE"


def test_llm_error_handler_returns_flat_503(client, monkeypatch):
    """Uncaught LLMError from any AI route becomes the structured availability body."""
    from app.main import create_app

    app = create_app()

    @app.get("/__test/llm-down")
    def _boom():
        raise LLMError(
            "Cannot reach AI service",
            provider="openai_compatible",
            reason="host_unreachable",
            retryable=True,
        )

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        response = test_client.get("/__test/llm-down")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "AI_SERVICE_UNAVAILABLE"
    assert body["provider"] == "openai_compatible"
    assert body["retryable"] is True
