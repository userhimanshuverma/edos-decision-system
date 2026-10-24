from __future__ import annotations

import json
from typing import Any
import httpx


class OllamaClientError(Exception):
    """Base exception for Ollama client interactions."""


class OllamaConnectionError(OllamaClientError):
    """Raised when the Ollama server is unreachable or refused the connection."""


class OllamaTimeoutError(OllamaClientError):
    """Raised when an Ollama request times out."""


class OllamaModelNotFoundError(OllamaClientError):
    """Raised when the configured model is not installed or found on the Ollama server."""


class OllamaResponseError(OllamaClientError):
    """Raised when Ollama returns an error status code or malformed payload."""


class OllamaClient:
    """Client for interacting with a locally running Ollama LLM server.

    Communicates with Ollama's HTTP API (e.g. /api/chat).
    Does NOT depend on hosted cloud APIs or proprietary SDKs.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:1b",
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = client

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self.timeout)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        format_type: str | None = "json",
        options: dict[str, Any] | None = None,
    ) -> str:
        """Sends a chat completion request to the Ollama server.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            format_type: Format constraint (default 'json').
            options: Optional runtime options (e.g. temperature).

        Returns:
            The raw text content returned by the assistant.

        Raises:
            OllamaConnectionError: If Ollama cannot be reached.
            OllamaTimeoutError: If the request times out.
            OllamaModelNotFoundError: If the model is not found in Ollama.
            OllamaResponseError: If Ollama responds with an error or invalid structure.
        """
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if format_type:
            payload["format"] = format_type
        if options:
            payload["options"] = options
        else:
            payload["options"] = {"temperature": 0.1}

        client = self._get_client()
        close_client = self._client is None

        try:
            response = client.post(url, json=payload, timeout=self.timeout)
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise OllamaConnectionError(
                f"Unable to connect to Ollama server at '{self.base_url}'. "
                "Ensure Ollama is running locally via 'ollama serve'."
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                f"Ollama request to '{url}' timed out after {self.timeout}s."
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(
                f"HTTP communication error connecting to Ollama at '{self.base_url}': {exc}"
            ) from exc
        finally:
            if close_client:
                client.close()

        if response.status_code == 404:
            err_text = response.text
            if "model" in err_text.lower() and "not found" in err_text.lower():
                raise OllamaModelNotFoundError(
                    f"Configured model '{self.model}' was not found in Ollama. "
                    f"Install it locally using: 'ollama pull {self.model}'."
                )
            raise OllamaResponseError(
                f"Ollama endpoint not found (HTTP 404): {err_text}"
            )

        if response.status_code != 200:
            raise OllamaResponseError(
                f"Ollama returned HTTP status {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"Failed to parse Ollama response as JSON: {response.text}"
            ) from exc

        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaResponseError(
                f"Malformed response from Ollama: 'message' object missing: {data}"
            )

        content = message.get("content")
        if not content or not isinstance(content, str) or not content.strip():
            raise OllamaResponseError(
                "Ollama returned an empty or whitespace response."
            )

        return content.strip()

    def check_health(self) -> bool:
        """Checks if the Ollama server is reachable and responsive."""
        url = f"{self.base_url}/api/tags"
        client = self._get_client()
        close_client = self._client is None
        try:
            resp = client.get(url, timeout=min(3.0, self.timeout))
            return resp.status_code == 200
        except Exception:
            return False
        finally:
            if close_client:
                client.close()
