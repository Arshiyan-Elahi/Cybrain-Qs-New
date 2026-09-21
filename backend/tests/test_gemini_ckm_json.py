"""Gemini JSON-mode CKM extraction: schema, thinking off, thought-part skip, secrets."""

from __future__ import annotations

import logging

import httpx

from app.core.logging import SecretScrubFilter
from app.core.redaction import sanitize_text
from app.integrations.llm.base import ChatMessage
from app.integrations.llm.gemini import GEMINI_JSON_ARRAY_SCHEMA, GeminiProvider


def _provider() -> GeminiProvider:
    return GeminiProvider(
        api_key="AIzaSyTestGeminiKeyValue1234567890abcd",
        chat_model="gemini-2.5-flash",
        embedding_model="unused",
        embedding_dimensions=768,
    )


def _response(payload: dict):
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return payload

    return _Resp()


def test_json_mode_sends_array_schema_thinking_off_and_header_auth(monkeypatch):
    captured: dict = {}

    def fake_post(url, *, headers=None, json=None, timeout=None, params=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["params"] = params
        return _response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "[]"}]},
                    }
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 2},
                "modelVersion": "gemini-2.5-flash",
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = _provider().complete(
        [
            ChatMessage(role="system", content="Respond with a JSON array of objects."),
            ChatMessage(role="user", content="chunks"),
        ],
        max_tokens=4096,
    )
    assert captured["params"] is None
    assert "key=" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "AIzaSyTestGeminiKeyValue1234567890abcd"
    generation = captured["json"]["generationConfig"]
    assert generation["responseMimeType"] == "application/json"
    assert generation["responseSchema"] == GEMINI_JSON_ARRAY_SCHEMA
    assert generation["responseSchema"]["type"] == "ARRAY"
    assert generation["thinkingConfig"] == {"thinkingBudget": 0}
    assert generation["maxOutputTokens"] == 4096
    assert result.provider == "gemini"
    assert result.text == "[]"
    assert result.usage["finish_reason"] == "STOP"
    assert result.usage["thought_parts"] == 0


def test_extract_text_skips_thought_parts(monkeypatch):
    def fake_post(url, **kwargs):
        return _response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"thought": True, "text": "I will extract roles from the SOP."},
                                {
                                    "text": '[{"type":"role","label":"Trainer","sourceChunkId":"abc"}]'
                                },
                            ]
                        },
                    }
                ],
                "modelVersion": "gemini-2.5-flash",
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = _provider().complete(
        [ChatMessage(role="user", content="return json please")],
        max_tokens=4096,
    )
    assert result.text.startswith('[{"type":"role"')
    assert "I will extract" not in result.text
    assert result.usage["thought_parts"] == 1


def test_query_string_and_google_api_keys_redacted():
    leaked = (
        "HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent?key=AIzaSySecretKeyValue1234567890abcd "
        '"HTTP/1.1 200 OK"'
    )
    cleaned = sanitize_text(leaked)
    assert "AIzaSySecretKeyValue1234567890abcd" not in cleaned
    assert "key=[REDACTED]" in cleaned


def test_secret_scrub_filter_rewrites_httpx_log_line():
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        "HTTP Request: POST https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=%s",
        ("AIzaSySecretKeyValue1234567890abcd",),
        None,
    )
    assert SecretScrubFilter().filter(record) is True
    message = record.getMessage()
    assert "AIzaSySecretKeyValue1234567890abcd" not in message
    assert "[REDACTED]" in message
