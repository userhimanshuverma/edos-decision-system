from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.decision import (
    get_candidate_action_repository,
    get_decision_repository,
    get_validation_repository,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.decision import Decision, DecisionStatus
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_repositories():
    """Ensure repositories are cleared before each test."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    val_repo = get_validation_repository()
    dec_repo.clear()
    action_repo.clear()
    val_repo.clear()
    yield
    dec_repo.clear()
    action_repo.clear()
    val_repo.clear()


@pytest.fixture
def test_decision(client: TestClient) -> dict:
    """Creates a decision for testing."""
    resp = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert resp.status_code == 201
    return resp.json()


class TestValidationApi:
    """Tests for FastAPI candidate action validation endpoints."""

    def test_validate_decision_empty_actions(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]
        resp = client.post(f"/api/decisions/{dec_id}/validate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision_id"] == dec_id
        assert data["status"] == "NO_ACTIONS"
        assert data["total_actions_evaluated"] == 0
        assert data["valid_action_ids"] == []
        assert data["invalid_action_ids"] == []

    def test_validate_decision_with_candidate_actions(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]

        # Create candidate action 1: DO_NOTHING
        a1_resp = client.post(
            f"/api/decisions/{dec_id}/actions",
            json={"type": "DO_NOTHING"},
        )
        assert a1_resp.status_code == 201
        a1_id = a1_resp.json()["id"]

        # Create candidate action 2: PLACE_ORDER (normal quantity 30)
        a2_resp = client.post(
            f"/api/decisions/{dec_id}/actions",
            json={"type": "PLACE_ORDER", "parameters": {"quantity": 30}},
        )
        assert a2_resp.status_code == 201
        a2_id = a2_resp.json()["id"]

        # Validate decision
        resp = client.post(f"/api/decisions/{dec_id}/validate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ALL_SATISFIED"
        assert data["total_actions_evaluated"] == 2
        assert a1_id in data["valid_action_ids"]
        assert a2_id in data["valid_action_ids"]
        assert len(data["action_results"]) == 2

    def test_validate_decision_with_invalid_action(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]

        # Create candidate action exceeding warehouse capacity
        a_resp = client.post(
            f"/api/decisions/{dec_id}/actions",
            json={"type": "PLACE_ORDER", "parameters": {"quantity": 999999}},
        )
        assert a_resp.status_code == 201
        a_id = a_resp.json()["id"]

        resp = client.post(f"/api/decisions/{dec_id}/validate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ALL_VIOLATED"
        assert a_id in data["invalid_action_ids"]
        assert data["action_results"][0]["is_valid"] is False

    def test_validate_decision_with_custom_constraints(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]

        a_resp = client.post(
            f"/api/decisions/{dec_id}/actions",
            json={"type": "PLACE_ORDER", "parameters": {"quantity": 50}},
        )
        a_id = a_resp.json()["id"]

        # Send custom constraint: max_spend $100
        custom_payload = {
            "constraints": [
                {
                    "constraint_type": "MAX_BUDGET_LIMIT",
                    "name": "strict_budget",
                    "description": "Cap budget at $100",
                    "is_hard": True,
                    "parameters": {"max_spend": 100.0},
                }
            ]
        }
        resp = client.post(f"/api/decisions/{dec_id}/validate", json=custom_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ALL_VIOLATED"
        assert a_id in data["invalid_action_ids"]

    def test_get_decision_validation_retrieval_and_recompute(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]

        # 1. GET before validation runs -> automatically computes initial validation report
        resp1 = client.get(f"/api/decisions/{dec_id}/validation")
        assert resp1.status_code == 200
        data1 = resp1.json()
        val_id_1 = data1["id"]

        # 2. GET again without recompute -> returns same stored report
        resp2 = client.get(f"/api/decisions/{dec_id}/validation")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == val_id_1

        # 3. GET with recompute=true -> generates new report
        resp3 = client.get(f"/api/decisions/{dec_id}/validation?recompute=true")
        assert resp3.status_code == 200
        assert resp3.json()["id"] != val_id_1

    def test_validate_individual_action_endpoint(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]
        a_resp = client.post(
            f"/api/decisions/{dec_id}/actions",
            json={"type": "DO_NOTHING"},
        )
        a_id = a_resp.json()["id"]

        resp = client.post(f"/api/decisions/{dec_id}/actions/{a_id}/validate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_id"] == a_id
        assert data["status"] == "SATISFIED"
        assert data["is_valid"] is True
        assert len(data["constraint_results"]) >= 1

    def test_validate_unknown_decision_returns_404(self, client: TestClient):
        resp = client.post("/api/decisions/DEC-NONEXISTENT/validate", json={})
        assert resp.status_code == 404

        resp_get = client.get("/api/decisions/DEC-NONEXISTENT/validation")
        assert resp_get.status_code == 404

    def test_validate_unknown_action_returns_404(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]
        resp = client.post(f"/api/decisions/{dec_id}/actions/ACT-NONEXISTENT/validate", json={})
        assert resp.status_code == 404

    def test_route_aliases_work(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]

        # /decisions/...
        r1 = client.post(f"/decisions/{dec_id}/validate", json={})
        assert r1.status_code == 200

        # /api/decision/...
        r2 = client.get(f"/api/decision/{dec_id}/validation")
        assert r2.status_code == 200

        # /decision/...
        r3 = client.get(f"/decision/{dec_id}/validation")
        assert r3.status_code == 200

    def test_validate_decision_with_cross_decision_action_id_returns_404(self, client: TestClient, test_decision: dict):
        dec1_id = test_decision["id"]

        # Create second decision and an action under it
        d2_resp = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
        assert d2_resp.status_code == 201
        dec2_id = d2_resp.json()["id"]

        act2_resp = client.post(f"/api/decisions/{dec2_id}/actions", json={"type": "DO_NOTHING"})
        assert act2_resp.status_code == 201
        act2_id = act2_resp.json()["id"]

        # Attempt to validate act2_id under dec1_id -> HTTP 404
        resp = client.post(
            f"/api/decisions/{dec1_id}/validate",
            json={"action_ids": [act2_id]},
        )
        assert resp.status_code == 404

    def test_revalidation_when_actions_change(self, client: TestClient, test_decision: dict):
        dec_id = test_decision["id"]

        # 1. Create first action and validate
        a1_resp = client.post(f"/api/decisions/{dec_id}/actions", json={"type": "DO_NOTHING"})
        assert a1_resp.status_code == 201
        val1 = client.post(f"/api/decisions/{dec_id}/validate", json={}).json()
        assert val1["total_actions_evaluated"] == 1

        # 2. Add second candidate action
        a2_resp = client.post(
            f"/api/decisions/{dec_id}/actions",
            json={"type": "PLACE_ORDER", "parameters": {"quantity": 25}},
        )
        assert a2_resp.status_code == 201

        # 3. GET without recompute returns stored snapshot with 1 action
        cached = client.get(f"/api/decisions/{dec_id}/validation").json()
        assert cached["id"] == val1["id"]
        assert cached["total_actions_evaluated"] == 1

        # 4. GET with recompute=true evaluates current actions and reflects the new action
        fresh = client.get(f"/api/decisions/{dec_id}/validation?recompute=true").json()
        assert fresh["id"] != val1["id"]
        assert fresh["total_actions_evaluated"] == 2

