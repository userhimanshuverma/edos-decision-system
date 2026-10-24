from __future__ import annotations

import httpx
import pytest

from app.explanation.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaTimeoutError,
)


def test_ollama_client_success():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": '{"recommendation_summary": "Order 150 units"}',
                },
            },
        )

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", model="llama3.2:1b", client=client)

    result = ollama.chat_completion([{"role": "user", "content": "Explain decision"}])
    assert result == '{"recommendation_summary": "Order 150 units"}'


def test_ollama_client_connection_error():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", client=client)

    with pytest.raises(OllamaConnectionError, match="Unable to connect to Ollama server"):
        ollama.chat_completion([{"role": "user", "content": "Explain decision"}])


def test_ollama_client_timeout():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out")

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", timeout=5.0, client=client)

    with pytest.raises(OllamaTimeoutError, match="timed out after 5.0s"):
        ollama.chat_completion([{"role": "user", "content": "Explain decision"}])


def test_ollama_client_model_not_found():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            text='{"error":"model \'llama3.2:1b\' not found, try pulling it first"}',
        )

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", model="llama3.2:1b", client=client)

    with pytest.raises(OllamaModelNotFoundError, match="was not found in Ollama"):
        ollama.chat_completion([{"role": "user", "content": "Explain decision"}])


def test_ollama_client_server_error():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", client=client)

    with pytest.raises(OllamaResponseError, match="HTTP status 500"):
        ollama.chat_completion([{"role": "user", "content": "Explain decision"}])


def test_ollama_client_empty_content():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"model": "llama3.2:1b", "message": {"role": "assistant", "content": "   "}},
        )

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", client=client)

    with pytest.raises(OllamaResponseError, match="empty or whitespace response"):
        ollama.chat_completion([{"role": "user", "content": "Explain decision"}])


def test_ollama_client_check_health():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"models": []})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    ollama = OllamaClient(base_url="http://localhost:11434", client=client)
    assert ollama.check_health() is True
