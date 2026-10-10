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


# ============================================================================
# 1. POST /api/decisions (Decision Creation Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/decisions", "/decisions", "/api/decision", "/decision"])
def test_create_decision_success(prefix: str):
    """Verifies that creating a decision with valid references returns HTTP 201 with generated identity."""
    payload = {
        "product_id": "prod-001",
        "warehouse_id": "wh-001",
    }
    response = client.post(prefix, json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert "decision_id" in data
    assert data["id"] == data["decision_id"]
    assert data["id"].startswith("DEC-")
    assert data["product_id"] == "prod-001"
    assert data["warehouse_id"] == "wh-001"
    assert data["status"] == "DRAFT"

    # Datetime parse validation
    parsed_dt = datetime.fromisoformat(data["created_at"])
    assert parsed_dt.tzinfo is not None


def test_create_decision_increments_unique_ids():
    """Verifies sequential decision creations receive distinct unique identifiers."""
    res1 = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    res2 = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-002"})

    assert res1.status_code == 201
    assert res2.status_code == 201

    d1 = res1.json()
    d2 = res2.json()

    assert d1["id"] != d2["id"]
    assert d1["id"] == "DEC-0001"
    assert d2["id"] == "DEC-0002"


def test_create_decision_unknown_product_returns_404():
    """Verifies that an unknown product identifier returns HTTP 404."""
    payload = {
        "product_id": "prod-nonexistent-999",
        "warehouse_id": "wh-001",
    }
    response = client.post("/api/decisions", json=payload)
    assert response.status_code == 404
    assert "Product 'prod-nonexistent-999' not found" in response.json()["detail"]


def test_create_decision_unknown_warehouse_returns_404():
    """Verifies that an unknown warehouse identifier returns HTTP 404."""
    payload = {
        "product_id": "prod-001",
        "warehouse_id": "wh-nonexistent-999",
    }
    response = client.post("/api/decisions", json=payload)
    assert response.status_code == 404
    assert "Warehouse 'wh-nonexistent-999' not found" in response.json()["detail"]


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {},  # Empty body
        {"product_id": "prod-001"},  # Missing warehouse_id
        {"warehouse_id": "wh-001"},  # Missing product_id
        {"product_id": "", "warehouse_id": "wh-001"},  # Empty product_id
        {"product_id": "prod-001", "warehouse_id": ""},  # Empty warehouse_id
        {"product_id": "   ", "warehouse_id": "wh-001"},  # Whitespace-only product_id
        {"product_id": "prod-001", "warehouse_id": "wh-001", "extra": "invalid"},  # Extra field
    ],
)
def test_create_decision_invalid_payloads_rejected(invalid_payload: dict):
    """Verifies that malformed or incomplete payloads are rejected with 422 Unprocessable Entity."""
    response = client.post("/api/decisions", json=invalid_payload)
    assert response.status_code == 422


# ============================================================================
# 2. GET /api/decisions (Decision Collection Endpoint)
# ============================================================================


def test_list_decisions_empty():
    """Verifies that listing an empty repository returns an empty list with HTTP 200."""
    response = client.get("/api/decisions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_decisions_multiple():
    """Verifies that all stored decisions are returned with deterministic ordering."""
    client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    client.post("/api/decisions", json={"product_id": "prod-002", "warehouse_id": "wh-002"})

    response = client.get("/api/decisions")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "DEC-0001"
    assert data[1]["id"] == "DEC-0002"


def test_list_decisions_filtering():
    """Verifies optional query filtering by product_id and warehouse_id."""
    client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-002"})
    client.post("/api/decisions", json={"product_id": "prod-002", "warehouse_id": "wh-001"})

    # Filter by product_id
    res_prod = client.get("/api/decisions?product_id=prod-001")
    assert res_prod.status_code == 200
    assert len(res_prod.json()) == 2

    # Filter by warehouse_id
    res_wh = client.get("/api/decisions?warehouse_id=wh-002")
    assert res_wh.status_code == 200
    assert len(res_wh.json()) == 1
    assert res_wh.json()[0]["product_id"] == "prod-001"

    # Filter non-matching
    res_none = client.get("/api/decisions?product_id=prod-003")
    assert res_none.status_code == 200
    assert res_none.json() == []


# ============================================================================
# 3. GET /api/decisions/{decision_id} (Decision Item Endpoint)
# ============================================================================


def test_get_decision_by_id_success():
    """Verifies retrieving a decision by its ID returns the matching record."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-003", "warehouse_id": "wh-001"})
    created_id = create_res.json()["id"]

    get_res = client.get(f"/api/decisions/{created_id}")
    assert get_res.status_code == 200

    item = get_res.json()
    assert item["id"] == created_id
    assert item["decision_id"] == created_id
    assert item["product_id"] == "prod-003"
    assert item["warehouse_id"] == "wh-001"
    assert item["status"] == "DRAFT"


def test_get_decision_by_id_repeated_consistency():
    """Verifies repeated retrieval returns identical values."""
    create_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = create_res.json()["id"]

    res1 = client.get(f"/api/decisions/{decision_id}").json()
    res2 = client.get(f"/api/decisions/{decision_id}").json()

    assert res1 == res2


def test_get_decision_by_id_not_found():
    """Verifies retrieving an unknown decision returns HTTP 404."""
    response = client.get("/api/decisions/DEC-NONEXISTENT")
    assert response.status_code == 404
    assert "Decision 'DEC-NONEXISTENT' not found" in response.json()["detail"]


@pytest.mark.parametrize("prefix", ["/api/decisions", "/decisions", "/api/decision", "/decision"])
def test_decision_route_aliases(prefix: str):
    """Verifies that all canonical and alias endpoints operate consistently."""
    # List empty
    assert client.get(prefix).status_code == 200

    # Create
    post_res = client.post(prefix, json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    assert post_res.status_code == 201
    created_id = post_res.json()["id"]

    # Get by ID
    get_res = client.get(f"{prefix}/{created_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == created_id


# ============================================================================
# 4. PATCH /api/decisions/{decision_id}/status (Lifecycle Transition Endpoint)
# ============================================================================


def test_patch_decision_status_success():
    """Verifies that a valid transition updates decision status and returns 200."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    assert post_res.status_code == 201
    decision_id = post_res.json()["id"]
    assert post_res.json()["status"] == "DRAFT"

    patch_res = client.patch(f"/api/decisions/{decision_id}/status", json={"status": "CONTEXTUALIZING"})
    assert patch_res.status_code == 200

    data = patch_res.json()
    assert data["id"] == decision_id
    assert data["decision_id"] == decision_id
    assert data["product_id"] == "prod-001"
    assert data["warehouse_id"] == "wh-001"
    assert data["status"] == "CONTEXTUALIZING"

    # Verify subsequent GET returns the updated status
    get_res = client.get(f"/api/decisions/{decision_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "CONTEXTUALIZING"


def test_patch_decision_status_full_progression_sequence():
    """Verifies walking an operational decision through all six lifecycle stages via PATCH."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    stages = [
        "CONTEXTUALIZING",
        "CONSTRUCTING",
        "VALIDATING",
        "EVALUATING",
        "READY",
    ]

    for stage in stages:
        patch_res = client.patch(
            f"/api/decisions/{decision_id}/status",
            json={"status": stage},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == stage

    # Final state is READY
    final_res = client.get(f"/api/decisions/{decision_id}")
    assert final_res.json()["status"] == "READY"


@pytest.mark.parametrize(
    "skipped_target",
    [
        "CONSTRUCTING",
        "VALIDATING",
        "EVALUATING",
        "READY",
    ],
)
def test_patch_decision_status_skipped_stages_return_422(skipped_target: str):
    """Verifies skipping lifecycle stages returns HTTP 422."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    patch_res = client.patch(
        f"/api/decisions/{decision_id}/status",
        json={"status": skipped_target},
    )
    assert patch_res.status_code == 422
    assert "Invalid lifecycle transition" in patch_res.json()["detail"]

    # Verify decision remains in DRAFT
    get_res = client.get(f"/api/decisions/{decision_id}")
    assert get_res.json()["status"] == "DRAFT"


def test_patch_decision_status_same_state_rejected():
    """Verifies requesting a transition to the current status returns HTTP 422."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    # DRAFT -> DRAFT
    patch_res = client.patch(
        f"/api/decisions/{decision_id}/status",
        json={"status": "DRAFT"},
    )
    assert patch_res.status_code == 422
    assert "Invalid lifecycle transition" in patch_res.json()["detail"]


def test_patch_decision_status_backward_transition_rejected():
    """Verifies backward transitions return HTTP 422."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    # Advance to CONTEXTUALIZING
    client.patch(f"/api/decisions/{decision_id}/status", json={"status": "CONTEXTUALIZING"})

    # Attempt CONTEXTUALIZING -> DRAFT
    patch_res = client.patch(f"/api/decisions/{decision_id}/status", json={"status": "DRAFT"})
    assert patch_res.status_code == 422

    # Status must remain CONTEXTUALIZING
    assert client.get(f"/api/decisions/{decision_id}").json()["status"] == "CONTEXTUALIZING"


def test_patch_decision_status_from_ready_rejected():
    """Verifies that transitioning from terminal READY status returns HTTP 422."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    # Advance to READY
    for stage in ["CONTEXTUALIZING", "CONSTRUCTING", "VALIDATING", "EVALUATING", "READY"]:
        client.patch(f"/api/decisions/{decision_id}/status", json={"status": stage})

    # Attempt to transition out of READY
    patch_res = client.patch(f"/api/decisions/{decision_id}/status", json={"status": "DRAFT"})
    assert patch_res.status_code == 422
    assert "Invalid lifecycle transition" in patch_res.json()["detail"]


def test_patch_decision_status_unknown_id_returns_404():
    """Verifies transitioning an unknown decision returns HTTP 404."""
    response = client.patch(
        "/api/decisions/DEC-UNKNOWN-999/status",
        json={"status": "CONTEXTUALIZING"},
    )
    assert response.status_code == 404
    assert "Decision 'DEC-UNKNOWN-999' not found" in response.json()["detail"]


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {},  # Empty
        {"status": "NONEXISTENT_STATE"},  # Unknown enum
        {"status": "APPROVED"},  # Out-of-scope status
        {"status": "EXECUTED"},  # Out-of-scope status
        {"status": ""},  # Empty string
        {"status": "contextualizing"},  # Lowercase
        {"status": "CONTEXTUALIZING", "extra": "forbidden"},  # Extra field
    ],
)
def test_patch_decision_status_schema_validation_failures(invalid_payload: dict):
    """Verifies that invalid payloads are rejected with HTTP 422 schema validation error."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    response = client.patch(f"/api/decisions/{decision_id}/status", json=invalid_payload)
    assert response.status_code == 422

    # Status remains DRAFT
    assert client.get(f"/api/decisions/{decision_id}").json()["status"] == "DRAFT"


@pytest.mark.parametrize("prefix", ["/api/decisions", "/decisions", "/api/decision", "/decision"])
def test_patch_decision_status_aliases(prefix: str):
    """Verifies that PATCH status works across canonical and alias routes."""
    post_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    decision_id = post_res.json()["id"]

    patch_res = client.patch(f"{prefix}/{decision_id}/status", json={"status": "CONTEXTUALIZING"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "CONTEXTUALIZING"
