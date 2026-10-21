from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.decision import (
    get_candidate_action_repository,
    get_decision_repository,
    get_decision_version_repository,
    get_provenance_repository,
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
    ver_repo = get_decision_version_repository()
    prov_repo = get_provenance_repository()

    dec_repo.clear()
    action_repo.clear()
    ver_repo.clear()
    prov_repo.clear()
    yield
    dec_repo.clear()
    action_repo.clear()
    ver_repo.clear()
    prov_repo.clear()


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
        parameters=PlaceOrderParameters(quantity=50),
    )
    return action_repo.record(action)


def test_capture_and_get_provenance_trace_endpoint(
    client: TestClient,
    test_decision: dict,
    test_action: CandidateAction,
):
    dec_id = test_decision["id"]

    # 1. Capture provenance
    capture_resp = client.post(
        f"/api/decisions/{dec_id}/provenance/capture",
        json={"policy_type": "REORDER_POINT_DEFICIT", "trigger": "API_TEST"},
    )
    assert capture_resp.status_code == 201
    trace_data = capture_resp.json()
    assert trace_data["id"].startswith("PRV-")
    assert trace_data["decision_id"] == dec_id
    assert trace_data["trigger"] == "API_TEST"
    assert trace_data["status"] == "SUCCESS"
    assert len(trace_data["inputs"]) > 0
    assert len(trace_data["rules"]) > 0
    assert len(trace_data["calculations"]) > 0
    assert len(trace_data["results"]) > 0
    assert len(trace_data["lineage_edges"]) > 0

    trace_id = trace_data["id"]

    # 2. Get latest provenance trace
    latest_resp = client.get(f"/api/decisions/{dec_id}/provenance")
    assert latest_resp.status_code == 200
    assert latest_resp.json()["id"] == trace_id

    # 3. List provenance traces
    list_resp = client.get(f"/api/decisions/{dec_id}/provenance/traces")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == trace_id

    # 4. Get specific trace
    spec_resp = client.get(f"/api/decisions/{dec_id}/provenance/traces/{trace_id}")
    assert spec_resp.status_code == 200
    assert spec_resp.json()["id"] == trace_id

    # 5. Get derivation path
    deriv_resp = client.get(f"/api/decisions/{dec_id}/provenance/traces/{trace_id}/derivation")
    assert deriv_resp.status_code == 200
    deriv_data = deriv_resp.json()
    assert deriv_data["result"]["result_type"] == "RECOMMENDATION"
    assert len(deriv_data["calculations"]) > 0
    assert len(deriv_data["rules"]) > 0
    assert len(deriv_data["inputs"]) > 0
    assert len(deriv_data["lineage_edges"]) > 0


def test_provenance_endpoints_not_found(client: TestClient):
    # Nonexistent decision
    resp1 = client.get("/api/decisions/DEC-NONEXISTENT/provenance")
    assert resp1.status_code == 404

    resp2 = client.post("/api/decisions/DEC-NONEXISTENT/provenance/capture", json={})
    assert resp2.status_code == 404

    resp3 = client.get("/api/decisions/DEC-NONEXISTENT/provenance/traces")
    assert resp3.status_code == 404


def test_provenance_cross_decision_isolation(
    client: TestClient,
    test_decision: dict,
    test_action: CandidateAction,
):
    dec1_id = test_decision["id"]
    # Create second decision
    resp = client.post(
        "/api/decisions",
        json={"product_id": "prod-002", "warehouse_id": "wh-001"},
    )
    assert resp.status_code == 201
    dec2_id = resp.json()["id"]

    # Capture trace for dec1
    capture_resp = client.post(f"/api/decisions/{dec1_id}/provenance/capture", json={})
    assert capture_resp.status_code == 201
    trace1_id = capture_resp.json()["id"]

    # Requesting trace1 via dec2 must return 422
    cross_resp = client.get(f"/api/decisions/{dec2_id}/provenance/traces/{trace1_id}")
    assert cross_resp.status_code == 422
    assert "belongs to decision" in cross_resp.json()["detail"]


def test_provenance_direct_aliases(
    client: TestClient,
    test_decision: dict,
    test_action: CandidateAction,
):
    dec_id = test_decision["id"]

    # Capture using direct /decisions alias
    resp1 = client.post(f"/decisions/{dec_id}/provenance/capture", json={})
    assert resp1.status_code == 201

    # Get latest using /api/decision alias
    resp2 = client.get(f"/api/decision/{dec_id}/provenance")
    assert resp2.status_code == 200

    # Get latest using /decision alias
    resp3 = client.get(f"/decision/{dec_id}/provenance")
    assert resp3.status_code == 200
