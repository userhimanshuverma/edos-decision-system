from __future__ import annotations

import json
from fastapi.testclient import TestClient
import httpx
import pytest

from app.api.decision import get_ollama_client
from app.explanation.ollama_client import OllamaClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def test_decision_with_recommendation():
    """Helper fixture creating a decision with candidate actions and a generated recommendation."""
    # 1. Create Decision
    res = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert res.status_code == 201
    dec = res.json()
    dec_id = dec["id"]

    # 2. Add Candidate Action
    client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "PLACE_ORDER",
            "parameters": {"quantity": 60},
            "description": "Order 60 units",
        },
    )

    # 3. Generate Recommendation
    rec_res = client.post(
        f"/api/decisions/{dec_id}/recommendation",
        json={
            "policy_type": "REORDER_POINT_DEFICIT",
            "enforce_reorder_trigger": True,
        },
    )
    assert rec_res.status_code == 200

    return dec


def test_post_explanation_success(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    # Mock Ollama boundary
    model_response_json = {
        "recommendation_summary": "Order 60 units from current supplier.",
        "reasoning_summary": "Replenishment deficit calculation indicates 60 units needed to restore target stock.",
        "supporting_evidence": [],
        "risks_and_constraints": ["Supplier reliability is 95%."],
        "assumptions_and_missing_information": ["Demand stationary at historical daily average."],
        "review_considerations": ["Check storage capacity before receipt."],
        "limitations": ["Model does not account for seasonal sales spike."],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_response_json),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(f"/api/decisions/{dec_id}/explanation", json={})
        assert res.status_code == 200
        data = res.json()
        assert data["decision_id"] == dec_id
        assert "recommendation_summary" in data
        assert "reasoning_summary" in data
        assert data["model_name"] == "llama3.2:1b"
        assert "generated_at" in data

        # Check invariant: decision is not mutated
        dec_check = client.get(f"/api/decisions/{dec_id}")
        assert dec_check.status_code == 200
        assert dec_check.json()["status"] == test_decision_with_recommendation["status"]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_explanation_decision_not_found():
    res = client.post("/api/decisions/DEC-NONEXISTENT/explanation", json={})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_post_explanation_missing_recommendation():
    # Fresh decision without recommendation
    res = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert res.status_code == 201
    dec_id = res.json()["id"]

    res_exp = client.post(f"/api/decisions/{dec_id}/explanation", json={})
    assert res_exp.status_code == 422
    assert "no recorded recommendation" in res_exp.json()["detail"].lower()


def test_post_explanation_ollama_unavailable(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(f"/api/decisions/{dec_id}/explanation", json={})
        assert res.status_code == 503
        assert "unable to connect to ollama" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_explanation_ollama_timeout(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(f"/api/decisions/{dec_id}/explanation", json={})
        assert res.status_code == 503
        assert "timed out" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_explanation_model_not_found(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404, text='{"error":"model not found"}')

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(f"/api/decisions/{dec_id}/explanation", json={})
        assert res.status_code == 503
        assert "not found in ollama" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_explanation_ungrounded_evidence_rejected(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    model_response_json = {
        "recommendation_summary": "Order 60 units.",
        "reasoning_summary": "Based on unverified evidence.",
        "supporting_evidence": ["EVD-8888"],  # Non-existent ID
        "risks_and_constraints": [],
        "assumptions_and_missing_information": [],
        "review_considerations": [],
        "limitations": [],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(model_response_json),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(f"/api/decisions/{dec_id}/explanation", json={})
        assert res.status_code == 502
        assert "unverified identifier 'evd-8888'" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)
