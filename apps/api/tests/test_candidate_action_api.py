from datetime import datetime
from fastapi.testclient import TestClient
import pytest

from app.api.decision import get_decision_repository
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repository():
    """Ensures each test operates on an isolated, clean repository state."""
    repo = get_decision_repository()
    repo.clear()
    yield repo
    repo.clear()


def create_sample_decision(repo, product_id="prod-001", warehouse_id="wh-001"):
    """Helper creating a baseline decision."""
    return repo.create(product_id=product_id, warehouse_id=warehouse_id)


# ============================================================================
# 1. Action Creation Endpoints (POST /api/decisions/{decision_id}/actions)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/decisions", "/decisions", "/api/decision", "/decision"])
def test_create_candidate_action_do_nothing(clean_repository, prefix: str):
    """Verifies creating a DO_NOTHING candidate action returns HTTP 201."""
    decision = create_sample_decision(clean_repository)
    payload = {
        "action_type": "DO_NOTHING",
        "parameters": {},
        "description": "No intervention required",
    }
    response = client.post(f"{prefix}/{decision.id}/actions", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"].startswith("ACT-")
    assert data["action_id"] == data["id"]
    assert data["decision_id"] == decision.id
    assert data["action_type"] == "DO_NOTHING"
    assert data["type"] == "DO_NOTHING"
    assert data["parameters"] == {}
    assert data["description"] == "No intervention required"
    assert "created_at" in data


def test_create_candidate_action_place_order(clean_repository):
    """Verifies creating a PLACE_ORDER candidate action returns HTTP 201."""
    decision = create_sample_decision(clean_repository)
    payload = {
        "type": "PLACE_ORDER",
        "parameters": {"quantity": 120},
        "description": "Replenish 120 units",
    }
    response = client.post(f"/api/decisions/{decision.id}/actions", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["action_type"] == "PLACE_ORDER"
    assert data["parameters"]["quantity"] == 120
    assert data["description"] == "Replenish 120 units"


def test_create_candidate_action_switch_supplier(clean_repository):
    """Verifies creating a SWITCH_SUPPLIER candidate action with valid active supplier returns HTTP 201."""
    decision = create_sample_decision(clean_repository)
    # sup-002 is active in ShopFlow dataset
    payload = {
        "action_type": "SWITCH_SUPPLIER",
        "parameters": {"target_supplier_id": "sup-002"},
        "description": "Switch to secondary active supplier",
    }
    response = client.post(f"/api/decisions/{decision.id}/actions", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["action_type"] == "SWITCH_SUPPLIER"
    assert data["parameters"]["target_supplier_id"] == "sup-002"


def test_create_action_unknown_decision_returns_404(clean_repository):
    """Verifies creating an action for a non-existent decision returns HTTP 404."""
    payload = {
        "action_type": "DO_NOTHING",
        "parameters": {},
    }
    response = client.post("/api/decisions/DEC-9999/actions", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_action_invalid_place_order_quantity_returns_422(clean_repository):
    """Verifies non-positive or missing order quantities return HTTP 422."""
    decision = create_sample_decision(clean_repository)

    # Negative quantity
    res1 = client.post(
        f"/api/decisions/{decision.id}/actions",
        json={"action_type": "PLACE_ORDER", "parameters": {"quantity": -10}},
    )
    assert res1.status_code == 422

    # Zero quantity
    res2 = client.post(
        f"/api/decisions/{decision.id}/actions",
        json={"action_type": "PLACE_ORDER", "parameters": {"quantity": 0}},
    )
    assert res2.status_code == 422

    # Missing quantity
    res3 = client.post(
        f"/api/decisions/{decision.id}/actions",
        json={"action_type": "PLACE_ORDER", "parameters": {}},
    )
    assert res3.status_code == 422


def test_create_action_invalid_supplier_returns_422(clean_repository):
    """Verifies switch supplier with non-existent supplier returns HTTP 422."""
    decision = create_sample_decision(clean_repository)
    payload = {
        "action_type": "SWITCH_SUPPLIER",
        "parameters": {"target_supplier_id": "sup-nonexistent"},
    }
    response = client.post(f"/api/decisions/{decision.id}/actions", json=payload)
    assert response.status_code == 422
    assert "not found" in response.json()["detail"].lower()


def test_create_action_do_nothing_with_extra_params_returns_422(clean_repository):
    """Verifies extraneous parameters on DO_NOTHING return HTTP 422."""
    decision = create_sample_decision(clean_repository)
    payload = {
        "action_type": "DO_NOTHING",
        "parameters": {"quantity": 100},
    }
    response = client.post(f"/api/decisions/{decision.id}/actions", json=payload)
    assert response.status_code == 422


def test_create_action_invalid_type_returns_422(clean_repository):
    """Verifies unknown action types return HTTP 422."""
    decision = create_sample_decision(clean_repository)
    payload = {
        "action_type": "INVALID_ACTION_TYPE",
        "parameters": {},
    }
    response = client.post(f"/api/decisions/{decision.id}/actions", json=payload)
    assert response.status_code == 422


# ============================================================================
# 2. List Actions Endpoints (GET /api/decisions/{decision_id}/actions)
# ============================================================================


def test_list_actions_empty_for_decision_without_actions(clean_repository):
    """Verifies existing decision with zero actions returns HTTP 200 with empty list."""
    decision = create_sample_decision(clean_repository)
    response = client.get(f"/api/decisions/{decision.id}/actions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_actions_unknown_decision_returns_404(clean_repository):
    """Verifies listing actions for unknown decision returns HTTP 404."""
    response = client.get("/api/decisions/DEC-9999/actions")
    assert response.status_code == 404


def test_list_actions_deterministic_order_and_isolation(clean_repository):
    """Verifies listing returns only that decision's actions in deterministic order."""
    dec1 = create_sample_decision(clean_repository, "prod-001", "wh-001")
    dec2 = create_sample_decision(clean_repository, "prod-002", "wh-002")

    # Add actions to dec1
    client.post(
        f"/api/decisions/{dec1.id}/actions",
        json={"action_type": "DO_NOTHING", "parameters": {}},
    )
    client.post(
        f"/api/decisions/{dec1.id}/actions",
        json={"action_type": "PLACE_ORDER", "parameters": {"quantity": 50}},
    )

    # Add action to dec2
    client.post(
        f"/api/decisions/{dec2.id}/actions",
        json={"action_type": "SWITCH_SUPPLIER", "parameters": {"target_supplier_id": "sup-002"}},
    )

    res1 = client.get(f"/api/decisions/{dec1.id}/actions")
    assert res1.status_code == 200
    actions1 = res1.json()
    assert len(actions1) == 2
    assert actions1[0]["action_type"] == "DO_NOTHING"
    assert actions1[1]["action_type"] == "PLACE_ORDER"

    res2 = client.get(f"/api/decisions/{dec2.id}/actions")
    assert res2.status_code == 200
    actions2 = res2.json()
    assert len(actions2) == 1
    assert actions2[0]["action_type"] == "SWITCH_SUPPLIER"


# ============================================================================
# 3. Single Action Retrieval (GET /api/decisions/{decision_id}/actions/{action_id})
# ============================================================================


def test_get_single_action_success(clean_repository):
    """Verifies retrieving a specific action by ID returns HTTP 200."""
    decision = create_sample_decision(clean_repository)
    post_res = client.post(
        f"/api/decisions/{decision.id}/actions",
        json={"action_type": "PLACE_ORDER", "parameters": {"quantity": 75}},
    )
    action_id = post_res.json()["id"]

    get_res = client.get(f"/api/decisions/{decision.id}/actions/{action_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == action_id
    assert data["decision_id"] == decision.id
    assert data["parameters"]["quantity"] == 75


def test_get_single_action_unknown_returns_404(clean_repository):
    """Verifies querying a nonexistent action ID returns HTTP 404."""
    decision = create_sample_decision(clean_repository)
    response = client.get(f"/api/decisions/{decision.id}/actions/ACT-9999")
    assert response.status_code == 404


def test_get_single_action_cross_decision_rejected(clean_repository):
    """Verifies accessing an action under a different decision returns HTTP 404."""
    dec1 = create_sample_decision(clean_repository, "prod-001", "wh-001")
    dec2 = create_sample_decision(clean_repository, "prod-002", "wh-002")

    post_res = client.post(
        f"/api/decisions/{dec1.id}/actions",
        json={"action_type": "DO_NOTHING", "parameters": {}},
    )
    act1_id = post_res.json()["id"]

    # Attempt to retrieve act1 under dec2
    response = client.get(f"/api/decisions/{dec2.id}/actions/{act1_id}")
    assert response.status_code == 404


# ============================================================================
# 4. Backward Compatibility with Days 11-15 Endpoints
# ============================================================================


def test_backward_compatibility_days_11_to_15(clean_repository):
    """Verifies that decision creation, status updates, events, versions, and graphs function normally."""
    # Day 11: Create decision
    create_res = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert create_res.status_code == 201
    dec_id = create_res.json()["id"]

    # Day 12: Transition status
    patch_res = client.patch(
        f"/api/decisions/{dec_id}/status",
        json={"status": "CONTEXTUALIZING"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "CONTEXTUALIZING"

    # Day 13: Decision events
    events_res = client.get(f"/api/decisions/{dec_id}/events")
    assert events_res.status_code == 200
    assert len(events_res.json()) == 2

    # Day 14: Decision version snapshot
    version_res = client.post(f"/api/decisions/{dec_id}/versions")
    assert version_res.status_code == 201
    assert version_res.json()["version_number"] == 1

    # Day 15: Decision graph
    graph_res = client.post(f"/api/decisions/{dec_id}/graph")
    assert graph_res.status_code == 201
    assert len(graph_res.json()["nodes"]) >= 1

    # Day 16: Create action on this decision
    action_res = client.post(
        f"/api/decisions/{dec_id}/actions",
        json={"action_type": "DO_NOTHING", "parameters": {}},
    )
    assert action_res.status_code == 201
