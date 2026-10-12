import pytest
from fastapi.testclient import TestClient

from app.api.decision import (
    get_decision_event_repository,
    get_decision_repository,
    get_decision_version_repository,
)
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repositories():
    """Ensures each API test starts with clean, isolated repositories."""
    get_decision_repository().clear()
    get_decision_event_repository().clear()
    get_decision_version_repository().clear()
    yield
    get_decision_repository().clear()
    get_decision_event_repository().clear()
    get_decision_version_repository().clear()


# ============================================================================
# 1. POST /api/decisions/{decision_id}/versions (Create Version Endpoint)
# ============================================================================


def test_post_decision_version_success_default_payload():
    """Verifies creating a version with empty or default payload returns HTTP 201."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    assert create_res.status_code == 201
    decision_id = create_res.json()["id"]

    # POST version without payload
    ver_res = client.post(f"/api/decisions/{decision_id}/versions")
    assert ver_res.status_code == 201

    data = ver_res.json()
    assert data["id"].startswith("VER-")
    assert data["version_id"] == data["id"]
    assert data["decision_id"] == decision_id
    assert data["version_number"] == 1
    assert data["description"] is None
    assert data["snapshot"]["decision_id"] == decision_id
    assert data["snapshot"]["product_id"] == "prod-001"
    assert data["snapshot"]["warehouse_id"] == "wh-001"
    assert data["snapshot"]["status"] == "DRAFT"


def test_post_decision_version_success_with_description():
    """Verifies creating a version with explicit description notes."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    ver_res = client.post(
        f"/api/decisions/{decision_id}/versions",
        json={"description": "Baseline before context ingestion"},
    )
    assert ver_res.status_code == 201
    data = ver_res.json()
    assert data["version_number"] == 1
    assert data["description"] == "Baseline before context ingestion"


def test_post_decision_version_increments_version_number():
    """Verifies subsequent version creations increment version_number monotonically."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    v1_res = client.post(f"/api/decisions/{decision_id}/versions", json={"description": "v1"})
    assert v1_res.status_code == 201
    assert v1_res.json()["version_number"] == 1

    v2_res = client.post(f"/api/decisions/{decision_id}/versions", json={"description": "v2"})
    assert v2_res.status_code == 201
    assert v2_res.json()["version_number"] == 2


def test_post_decision_version_not_found():
    """Verifies creating a version for an unknown decision returns HTTP 404."""
    response = client.post("/api/decisions/DEC-NONEXISTENT/versions", json={"description": "Test"})
    assert response.status_code == 404
    assert "Decision 'DEC-NONEXISTENT' not found" in response.json()["detail"]


def test_post_decision_version_extra_fields_forbidden():
    """Verifies unexpected fields in version creation payload are rejected with HTTP 422."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    response = client.post(
        f"/api/decisions/{decision_id}/versions",
        json={"description": "Valid", "forged_version_number": 99},
    )
    assert response.status_code == 422


# ============================================================================
# 2. GET /api/decisions/{decision_id}/versions (List Versions Endpoint)
# ============================================================================


def test_list_decision_versions_empty_returns_200():
    """Verifies that an existing decision with no versions returns an empty list with HTTP 200."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    response = client.get(f"/api/decisions/{decision_id}/versions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_decision_versions_not_found():
    """Verifies that listing versions for an unknown decision returns HTTP 404."""
    response = client.get("/api/decisions/DEC-NONEXISTENT/versions")
    assert response.status_code == 404
    assert "Decision 'DEC-NONEXISTENT' not found" in response.json()["detail"]


def test_list_decision_versions_deterministic_ordering():
    """Verifies versions are returned strictly sorted by version_number ascending."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "First"})
    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "Second"})
    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "Third"})

    list_res = client.get(f"/api/decisions/{decision_id}/versions")
    assert list_res.status_code == 200
    versions = list_res.json()
    assert len(versions) == 3
    assert [v["version_number"] for v in versions] == [1, 2, 3]
    assert [v["description"] for v in versions] == ["First", "Second", "Third"]


def test_list_decision_versions_cross_decision_isolation():
    """Verifies versions of one decision are never leaked to another decision."""
    d1 = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"}).json()["id"]
    d2 = client.post("/api/decisions", json={"product_id": "prod-002", "warehouse_id": "wh-002"}).json()["id"]

    client.post(f"/api/decisions/{d1}/versions", json={"description": "D1-v1"})
    client.post(f"/api/decisions/{d1}/versions", json={"description": "D1-v2"})
    client.post(f"/api/decisions/{d2}/versions", json={"description": "D2-v1"})

    v1_list = client.get(f"/api/decisions/{d1}/versions").json()
    v2_list = client.get(f"/api/decisions/{d2}/versions").json()

    assert len(v1_list) == 2
    assert all(v["decision_id"] == d1 for v in v1_list)

    assert len(v2_list) == 1
    assert all(v["decision_id"] == d2 for v in v2_list)


# ============================================================================
# 3. GET /api/decisions/{decision_id}/versions/{version_number} (Retrieve Endpoint)
# ============================================================================


def test_get_decision_version_by_number_success():
    """Verifies retrieving a specific version by its version number."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "First draft"})
    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "Second draft"})

    v1_res = client.get(f"/api/decisions/{decision_id}/versions/1")
    assert v1_res.status_code == 200
    assert v1_res.json()["version_number"] == 1
    assert v1_res.json()["description"] == "First draft"

    v2_res = client.get(f"/api/decisions/{decision_id}/versions/2")
    assert v2_res.status_code == 200
    assert v2_res.json()["version_number"] == 2
    assert v2_res.json()["description"] == "Second draft"


def test_get_decision_version_by_number_not_found():
    """Verifies HTTP 404 when either decision or version number is not found."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    # Decision exists, version does not
    res_no_ver = client.get(f"/api/decisions/{decision_id}/versions/42")
    assert res_no_ver.status_code == 404
    assert f"Version '42' for decision '{decision_id}' not found" in res_no_ver.json()["detail"]

    # Decision does not exist
    res_no_dec = client.get("/api/decisions/DEC-NONEXISTENT/versions/1")
    assert res_no_dec.status_code == 404
    assert "Decision 'DEC-NONEXISTENT' not found" in res_no_dec.json()["detail"]


# ============================================================================
# 4. Snapshot Immutability Across Lifecycle Transitions
# ============================================================================


def test_snapshot_immutability_across_lifecycle_transitions():
    """Verifies that earlier snapshots do not mutate when the decision transitions statuses."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    # 1. Version 1 taken in DRAFT
    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "Draft snapshot"})

    # 2. Transition to CONTEXTUALIZING
    patch1 = client.patch(f"/api/decisions/{decision_id}/status", json={"status": "CONTEXTUALIZING"})
    assert patch1.status_code == 200

    # 3. Version 2 taken in CONTEXTUALIZING
    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "Contextualizing snapshot"})

    # 4. Transition to CONSTRUCTING
    patch2 = client.patch(f"/api/decisions/{decision_id}/status", json={"status": "CONSTRUCTING"})
    assert patch2.status_code == 200

    # 5. Check live decision is CONSTRUCTING
    live_dec = client.get(f"/api/decisions/{decision_id}").json()
    assert live_dec["status"] == "CONSTRUCTING"

    # 6. Check historical versions: v1 is still DRAFT, v2 is still CONTEXTUALIZING
    v1 = client.get(f"/api/decisions/{decision_id}/versions/1").json()
    assert v1["snapshot"]["status"] == "DRAFT"

    v2 = client.get(f"/api/decisions/{decision_id}/versions/2").json()
    assert v2["snapshot"]["status"] == "CONTEXTUALIZING"


# ============================================================================
# 5. Route Aliases & Backward Compatibility
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/decisions", "/decisions", "/api/decision", "/decision"])
def test_version_endpoints_route_aliases(prefix: str):
    """Verifies version endpoints work across canonical and mounted alias prefixes."""
    post_res = client.post(prefix, json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    # Create version
    v_create = client.post(f"{prefix}/{decision_id}/versions", json={"description": "Alias test"})
    assert v_create.status_code == 201

    # List versions
    v_list = client.get(f"{prefix}/{decision_id}/versions")
    assert v_list.status_code == 200
    assert len(v_list.json()) == 1

    # Get specific version
    v_get = client.get(f"{prefix}/{decision_id}/versions/1")
    assert v_get.status_code == 200
    assert v_get.json()["version_number"] == 1


def test_backward_compatibility_with_events_and_decision_lifecycle():
    """Verifies that versioning does not alter or break Day 11, 12, or 13 features."""
    dec = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"}).json()
    decision_id = dec["id"]

    # Day 13 events exist (DECISION_CREATED)
    events = client.get(f"/api/decisions/{decision_id}/events").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "DECISION_CREATED"

    # Day 14 version created explicitly
    client.post(f"/api/decisions/{decision_id}/versions", json={"description": "Explicit v1"})

    # Events count is still 1 (creating a version does NOT emit a lifecycle event)
    events_after = client.get(f"/api/decisions/{decision_id}/events").json()
    assert len(events_after) == 1

    # Day 12 transition works and emits LIFECYCLE_TRANSITION event
    client.patch(f"/api/decisions/{decision_id}/status", json={"status": "CONTEXTUALIZING"})
    events_transition = client.get(f"/api/decisions/{decision_id}/events").json()
    assert len(events_transition) == 2
    assert events_transition[1]["event_type"] == "LIFECYCLE_TRANSITION"

    # Versions count remains 1 (lifecycle transition does NOT automatically create versions)
    versions = client.get(f"/api/decisions/{decision_id}/versions").json()
    assert len(versions) == 1
