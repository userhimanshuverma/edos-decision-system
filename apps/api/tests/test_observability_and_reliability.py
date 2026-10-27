"""
Tests for Day 29: Backend Observability, Failure Handling & Reliability.

Covers:
- Request correlation and timing headers (X-Request-ID, X-Response-Time-Ms).
- Structured error handling with stable error codes and categories.
- Sanitization of sensitive data and protection against log flooding.
- Decision state and history preservation across failure paths.
"""

from __future__ import annotations

import json
from fastapi.testclient import TestClient
import httpx
import pytest

from app.api.decision import get_ollama_client
from app.explanation.ollama_client import OllamaClient
from app.main import app
from app.observability import map_status_to_error_code, sanitize_data

client = TestClient(app)


def test_observability_headers_and_timing():
    """Verify X-Request-ID is automatically generated and X-Response-Time-Ms is returned."""
    res = client.get("/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert res.headers["X-Request-ID"].startswith("req-")
    assert "X-Response-Time-Ms" in res.headers
    duration = float(res.headers["X-Response-Time-Ms"])
    assert duration >= 0.0


def test_observability_custom_request_id_preserved():
    """Verify incoming client request ID is preserved for end-to-end tracing."""
    custom_id = "req-client-trace-12345"
    res = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == custom_id


def test_consistent_404_decision_not_found():
    """Verify 404 error response format for non-existent decision."""
    res = client.get("/api/decisions/DEC-NONEXISTENT-999")
    assert res.status_code == 404
    data = res.json()
    assert "detail" in data
    assert "DEC-NONEXISTENT-999" in data["detail"]
    assert data["error_code"] == "DECISION_NOT_FOUND"
    assert data["category"] == "NOT_FOUND"
    assert "message" in data


def test_consistent_404_resource_not_found():
    """Verify 404 error response format when creating decision with invalid product."""
    res = client.post(
        "/api/decisions",
        json={"product_id": "prod-nonexistent-xyz", "warehouse_id": "wh-001"},
    )
    assert res.status_code == 404
    data = res.json()
    assert "prod-nonexistent-xyz" in data["detail"]
    assert data["error_code"] == "RESOURCE_NOT_FOUND"
    assert data["category"] == "NOT_FOUND"


def test_consistent_422_validation_error():
    """Verify 422 RequestValidationError provides structured error_code while keeping detail list."""
    res = client.post("/api/decisions", json={"invalid_field": 123})
    assert res.status_code == 422
    data = res.json()
    assert isinstance(data["detail"], list)  # Preserves Pydantic detail list
    assert data["error_code"] == "VALIDATION_ERROR"
    assert data["category"] == "VALIDATION"
    assert "Input validation failed" in data["message"]


def test_consistent_422_invalid_lifecycle_transition():
    """Verify 422 invalid lifecycle transition emits stable error code."""
    res_dec = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert res_dec.status_code == 201
    dec_id = res_dec.json()["id"]

    # Attempt illegal transition: DRAFT directly to READY
    res_bad = client.patch(
        f"/api/decisions/{dec_id}/status",
        json={"status": "READY"},
    )
    assert res_bad.status_code == 422
    data = res_bad.json()
    assert data["error_code"] == "INVALID_LIFECYCLE_TRANSITION"
    assert data["category"] == "LIFECYCLE"

    # Verify decision state was NOT modified by the failed transition
    res_check = client.get(f"/api/decisions/{dec_id}")
    assert res_check.status_code == 200
    assert res_check.json()["status"] == "DRAFT"


def test_consistent_503_ollama_unavailable():
    """Verify 503 Ollama offline maps to LLM_RUNTIME_UNAVAILABLE."""
    res_dec = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    dec_id = res_dec.json()["id"]

    client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "PLACE_ORDER",
            "parameters": {"quantity": 60},
            "description": "Order 60 units",
        },
    )
    client.post(
        f"/api/decisions/{dec_id}/recommendation",
        json={
            "policy_type": "REORDER_POINT_DEFICIT",
            "enforce_reorder_trigger": True,
        },
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by Ollama daemon")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(
            f"/api/decisions/{dec_id}/explanation",
            json={},
        )
        assert res.status_code == 503
        data = res.json()
        assert data["error_code"] == "LLM_RUNTIME_UNAVAILABLE"
        assert data["category"] == "AI_PROVIDER"
        assert "Ollama" in data["message"]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_data_sanitization_removes_sensitive_information():
    """Verify sensitive tokens, credentials, and api keys are redacted."""
    raw_payload = {
        "user_id": "usr-100",
        "api_key": "sk-secret-123456789",
        "authorization": "Bearer eyJhbGciOi...",
        "db_password": "super_secret_db_pass",
        "nested": {
            "auth_token": "token-xyz",
            "safe_metric": 42,
        },
    }
    sanitized = sanitize_data(raw_payload)
    assert sanitized["user_id"] == "usr-100"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["db_password"] == "[REDACTED]"
    assert sanitized["nested"]["auth_token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_metric"] == 42


def test_data_sanitization_limits_large_arrays():
    """Verify massive lists are truncated to prevent log flooding."""
    huge_list = list(range(100))
    sanitized = sanitize_data(huge_list)
    assert len(sanitized) == 51  # 50 items + truncation notice
    assert sanitized[-1] == "... 50 more items"


def test_status_code_mapping():
    """Verify map_status_to_error_code maps HTTP codes accurately."""
    assert map_status_to_error_code(400, "Bad input") == ("INVALID_REQUEST", "INVALID_INPUT")
    assert map_status_to_error_code(404, "Decision 'DEC-01' not found") == (
        "DECISION_NOT_FOUND",
        "NOT_FOUND",
    )
    assert map_status_to_error_code(404, "Product 'prod-01' not found") == (
        "RESOURCE_NOT_FOUND",
        "NOT_FOUND",
    )
    assert map_status_to_error_code(422, "Invalid lifecycle transition") == (
        "INVALID_LIFECYCLE_TRANSITION",
        "LIFECYCLE",
    )
    assert map_status_to_error_code(422, "Cross-decision isolation violation") == (
        "CROSS_DECISION_ISOLATION_VIOLATION",
        "ISOLATION",
    )
    assert map_status_to_error_code(502, "Ungrounded evidence citation") == (
        "LLM_UNGROUNDED_EVIDENCE",
        "AI_PROVIDER",
    )
    assert map_status_to_error_code(503, "Ollama connection timeout") == (
        "LLM_TIMEOUT",
        "AI_PROVIDER",
    )
    assert map_status_to_error_code(500, "Unexpected failure") == (
        "INTERNAL_SERVER_ERROR",
        "INTERNAL_ERROR",
    )
