from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.decision import (
    get_candidate_action_repository,
    get_decision_repository,
    get_evidence_repository,
    get_validation_repository,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    PlaceOrderParameters,
)
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_repositories():
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    val_repo = get_validation_repository()
    ev_repo = get_evidence_repository()

    dec_repo.clear()
    action_repo.clear()
    val_repo.clear()
    ev_repo.clear()
    yield
    dec_repo.clear()
    action_repo.clear()
    val_repo.clear()
    ev_repo.clear()


@pytest.fixture
def test_decision(client: TestClient) -> dict:
    resp = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def test_action(test_decision: dict) -> CandidateAction:
    action_repo = get_candidate_action_repository()
    action = CandidateAction(
        id="ACT-0001",
        decision_id=test_decision["id"],
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=45),
    )
    return action_repo.record(action)


def test_create_evidence_endpoint_success(client: TestClient, test_decision: dict, test_action: CandidateAction):
    decision_id = test_decision["id"]
    payload = {
        "evidence_type": "FACT",
        "category": "INVENTORY",
        "description": "Available stock count",
        "value": 45,
        "unit": "units",
        "source": "inventory:prod-001@wh-001",
        "action_id": test_action.id,
    }
    resp = client.post(f"/api/decisions/{decision_id}/evidence", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["decision_id"] == decision_id
    assert data["evidence_type"] == "FACT"
    assert data["category"] == "INVENTORY"
    assert data["value"] == 45
    assert data["action_id"] == test_action.id
    assert data["is_probability"] is False


def test_create_evidence_endpoint_decision_not_found(client: TestClient):
    payload = {
        "evidence_type": "FACT",
        "category": "INVENTORY",
        "description": "Available stock count",
    }
    resp = client.post("/api/decisions/DEC-NONEXISTENT/evidence", json=payload)
    assert resp.status_code == 404


def test_create_evidence_endpoint_action_not_found(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    payload = {
        "evidence_type": "FACT",
        "category": "INVENTORY",
        "description": "Available stock count",
        "action_id": "ACT-9999",
    }
    resp = client.post(f"/api/decisions/{decision_id}/evidence", json=payload)
    assert resp.status_code == 404


def test_create_evidence_endpoint_cross_decision_action_rejected(client: TestClient, test_decision: dict):
    # Create a second decision and an action on it
    resp2 = client.post("/api/decisions", json={"product_id": "prod-002", "warehouse_id": "wh-001"})
    dec2 = resp2.json()

    action_repo = get_candidate_action_repository()
    action2 = action_repo.record(
        CandidateAction(
            id="ACT-0002",
            decision_id=dec2["id"],
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
    )

    # Attempt to attach action2 (belongs to dec2) to test_decision
    payload = {
        "evidence_type": "FACT",
        "category": "INVENTORY",
        "description": "Cross-decision attempt",
        "action_id": action2.id,
    }
    resp = client.post(f"/api/decisions/{test_decision['id']}/evidence", json=payload)
    assert resp.status_code == 422
    assert "belongs to decision" in resp.json()["detail"]


def test_create_evidence_endpoint_duplicate_id(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    payload = {
        "id": "EVD-CUSTOM-01",
        "evidence_type": "FACT",
        "category": "INVENTORY",
        "description": "Custom ID test",
    }
    resp1 = client.post(f"/api/decisions/{decision_id}/evidence", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post(f"/api/decisions/{decision_id}/evidence", json=payload)
    assert resp2.status_code == 409


def test_create_evidence_stockout_risk_probability_rejected(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    payload = {
        "evidence_type": "CALCULATION",
        "category": "STOCKOUT_RISK",
        "description": "Exposure index",
        "value": 0.45,
        "is_probability": True,  # Invariant violation!
    }
    resp = client.post(f"/api/decisions/{decision_id}/evidence", json=payload)
    assert resp.status_code == 422


def test_list_and_get_evidence_endpoint(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    client.post(
        f"/api/decisions/{decision_id}/evidence",
        json={"evidence_type": "FACT", "category": "INVENTORY", "description": "Fact item"},
    )
    client.post(
        f"/api/decisions/{decision_id}/evidence",
        json={"evidence_type": "CALCULATION", "category": "COST", "description": "Calc item"},
    )

    # List all
    resp = client.get(f"/api/decisions/{decision_id}/evidence")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    # Filter by evidence_type
    resp_facts = client.get(f"/api/decisions/{decision_id}/evidence?evidence_type=FACT")
    assert resp_facts.status_code == 200
    assert len(resp_facts.json()) == 1
    ev_id = resp_facts.json()[0]["id"]

    # Get single item
    resp_single = client.get(f"/api/decisions/{decision_id}/evidence/{ev_id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["id"] == ev_id

    # 404 for unknown evidence
    resp_404 = client.get(f"/api/decisions/{decision_id}/evidence/EVD-UNKNOWN")
    assert resp_404.status_code == 404


def test_create_and_list_assumptions_endpoint(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    payload = {
        "category": "DEMAND",
        "statement": "Demand is expected to remain constant",
        "assumed_value": 15.0,
        "rationale": "Historical average",
        "source": "system_default",
    }
    resp = client.post(f"/api/decisions/{decision_id}/assumptions", json=payload)
    assert resp.status_code == 201
    asm = resp.json()
    assert asm["category"] == "DEMAND"
    assert asm["statement"] == "Demand is expected to remain constant"
    assert asm["assumed_value"] == 15.0

    # List
    list_resp = client.get(f"/api/decisions/{decision_id}/assumptions")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Get single
    get_resp = client.get(f"/api/decisions/{decision_id}/assumptions/{asm['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == asm["id"]


def test_get_evidence_sheet_endpoint(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    resp = client.get(f"/api/decisions/{decision_id}/evidence-sheet")
    assert resp.status_code == 200
    sheet = resp.json()
    assert sheet["decision_id"] == decision_id
    assert sheet["summary"]["total_items"] > 0
    assert sheet["summary"]["total_facts"] > 0
    assert sheet["summary"]["total_assumptions"] > 0
    assert sheet["summary"]["total_calculations"] > 0

    # Test route alias /decisions/...
    alias_resp = client.get(f"/decisions/{decision_id}/evidence-sheet")
    assert alias_resp.status_code == 200
    assert alias_resp.json()["id"] == sheet["id"]


def test_compile_evidence_sheet_endpoint(client: TestClient, test_decision: dict):
    decision_id = test_decision["id"]
    resp = client.post(f"/api/decisions/{decision_id}/evidence-sheet/compile")
    assert resp.status_code == 200
    sheet = resp.json()
    assert sheet["decision_id"] == decision_id
    assert sheet["summary"]["total_items"] > 0
