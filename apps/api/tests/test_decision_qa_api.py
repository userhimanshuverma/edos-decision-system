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
    res = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert res.status_code == 201
    dec = res.json()
    dec_id = dec["id"]

    client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "PLACE_ORDER",
            "parameters": {"quantity": 60},
            "description": "Order 60 units",
        },
    )

    rec_res = client.post(
        f"/api/decisions/{dec_id}/recommendation",
        json={
            "policy_type": "REORDER_POINT_DEFICIT",
            "enforce_reorder_trigger": True,
        },
    )
    assert rec_res.status_code == 200

    return dec


def test_post_question_success(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    model_response_json = {
        "answer": "The system recommended ordering 60 units because the inventory position was below reorder point.",
        "status": "ANSWERED",
        "supporting_evidence": [],
        "limitations": ["Supplier volatility not included in calculation."],
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
        res = client.post(
            f"/api/decisions/{dec_id}/questions",
            json={"question": "Why was this replenishment recommended?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["decision_id"] == dec_id
        assert data["question"] == "Why was this replenishment recommended?"
        assert data["status"] == "ANSWERED"
        assert "60 units" in data["answer"]
        assert data["model_name"] == "llama3.2:1b"
        assert "answered_at" in data

        # Invariant check: decision and recommendation are NOT mutated
        dec_check = client.get(f"/api/decisions/{dec_id}")
        assert dec_check.status_code == 200
        assert dec_check.json()["status"] == test_decision_with_recommendation["status"]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_question_route_aliases(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    model_response_json = {
        "answer": "Grounded answer via route alias.",
        "status": "ANSWERED",
        "supporting_evidence": [],
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
        # 1. Direct path /decisions/{id}/questions
        res1 = client.post(
            f"/decisions/{dec_id}/questions",
            json={"question": "What is the recommended action?"},
        )
        assert res1.status_code == 200

        # 2. QA alias /api/decisions/{id}/qa
        res2 = client.post(
            f"/api/decisions/{dec_id}/qa",
            json={"question": "What is the recommended action?"},
        )
        assert res2.status_code == 200
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_question_decision_isolation():
    """Verify that asking a question on Decision A only receives Decision A's context, not Decision B's."""
    # Create Decision A
    res_a = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    assert res_a.status_code == 201
    dec_a_id = res_a.json()["id"]

    # Create Decision B with different product/warehouse
    res_b = client.post("/api/decisions", json={"product_id": "prod-002", "warehouse_id": "wh-002"})
    assert res_b.status_code == 201
    dec_b_id = res_b.json()["id"]

    captured_prompts: list[str] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        for msg in body.get("messages", []):
            if msg.get("role") == "user":
                captured_prompts.append(msg.get("content", ""))
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:1b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"answer": "Isolated answer.", "status": "ANSWERED", "supporting_evidence": [], "limitations": []}),
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(f"/api/decisions/{dec_a_id}/questions", json={"question": "What warehouse?"})
        assert res.status_code == 200
        assert len(captured_prompts) == 1
        assert dec_a_id in captured_prompts[0]
        assert "wh-001" in captured_prompts[0]
        assert dec_b_id not in captured_prompts[0]
        assert "wh-002" not in captured_prompts[0]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_question_version_scoped():
    """Verify that version_id is passed and preserved."""
    res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    dec_id = res.json()["id"]

    # Invalidate version_id
    res_bad_ver = client.post(
        f"/api/decisions/{dec_id}/questions",
        json={"question": "What happened?", "version_id": "VER-NONEXISTENT"},
    )
    assert res_bad_ver.status_code == 404


def test_post_question_decision_not_found():
    res = client.post(
        "/api/decisions/DEC-NONEXISTENT/questions",
        json={"question": "Why was this recommended?"},
    )
    assert res.status_code == 404


def test_post_question_empty_or_whitespace_rejected():
    res_empty = client.post(
        "/api/decisions/DEC-0001/questions",
        json={"question": ""},
    )
    assert res_empty.status_code == 422

    res_whitespace = client.post(
        "/api/decisions/DEC-0001/questions",
        json={"question": "     \n\t   "},
    )
    assert res_whitespace.status_code == 422


def test_post_question_ollama_unavailable(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by Ollama daemon")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(
            f"/api/decisions/{dec_id}/questions",
            json={"question": "Why was this recommended?"},
        )
        assert res.status_code == 503
        assert "Ollama server" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_question_ollama_timeout(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Inference timed out after 30s")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_ollama = OllamaClient(client=mock_client)
    app.dependency_overrides[get_ollama_client] = lambda: mock_ollama

    try:
        res = client.post(
            f"/api/decisions/{dec_id}/questions",
            json={"question": "Why was this recommended?"},
        )
        assert res.status_code == 503
        assert "timed out" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)


def test_post_question_ungrounded_evidence_rejected(test_decision_with_recommendation):
    dec_id = test_decision_with_recommendation["id"]

    model_response_json = {
        "answer": "Recommendation supported by evidence.",
        "status": "ANSWERED",
        "supporting_evidence": ["EVD-FABRICATED-999"],
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
        res = client.post(
            f"/api/decisions/{dec_id}/questions",
            json={"question": "What evidence supports this?"},
        )
        assert res.status_code == 502
        assert "unverified identifier 'EVD-FABRICATED-999'" in res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_ollama_client, None)
