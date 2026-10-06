from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


# ============================================================================
# 1. GET /api/suppliers & GET /suppliers (Collection Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_list_suppliers_success(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4

    first_item = data[0]
    expected_fields = {
        "supplier_id",
        "id",
        "code",
        "name",
        "lead_time_days",
        "reliability",
        "active",
        "risk_level",
    }
    assert expected_fields.issubset(set(first_item.keys()))


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_supplier_response_structure_and_types(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    for item in response.json():
        assert isinstance(item["supplier_id"], str)
        assert len(item["supplier_id"]) > 0
        assert item["id"] == item["supplier_id"]
        assert isinstance(item["code"], str)
        assert len(item["code"]) > 0
        assert isinstance(item["name"], str)
        assert len(item["name"]) > 0
        assert isinstance(item["lead_time_days"], int)
        assert item["lead_time_days"] >= 0
        assert isinstance(item["reliability"], float)
        assert 0.0 <= item["reliability"] <= 1.0
        assert isinstance(item["active"], bool)
        assert item["risk_level"] in {"LOW", "MEDIUM", "HIGH"}


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_list_suppliers_active_filter(prefix: str):
    response = client.get(f"{prefix}?active_only=true")
    assert response.status_code == 200
    data = response.json()
    assert all(item["active"] is True for item in data)


# ============================================================================
# 2. GET /api/suppliers/{supplier_id} (Detail Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_get_supplier_by_id_success(prefix: str):
    response = client.get(f"{prefix}/sup-001")
    assert response.status_code == 200

    data = response.json()
    assert data["supplier_id"] == "sup-001"
    assert data["id"] == "sup-001"
    assert data["code"] == "SUP-PAC-01"
    assert data["name"] == "Pacific Dynamics Core"
    assert data["lead_time_days"] == 10
    assert data["reliability"] == 0.98
    assert data["active"] is True
    assert data["risk_level"] == "LOW"


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_get_supplier_by_id_not_found(prefix: str):
    response = client.get(f"{prefix}/sup-nonexistent-999")
    assert response.status_code == 404
    detail = response.json().get("detail", "")
    assert "sup-nonexistent-999" in detail
    assert "not found" in detail.lower()


# ============================================================================
# 3. GET /api/suppliers/code/{supplier_code} (Code Lookup Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_get_supplier_by_code_success(prefix: str):
    response = client.get(f"{prefix}/code/SUP-PAC-01")
    assert response.status_code == 200

    data = response.json()
    assert data["supplier_id"] == "sup-001"
    assert data["code"] == "SUP-PAC-01"
    assert data["lead_time_days"] == 10
    assert data["risk_level"] == "LOW"


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_get_supplier_by_code_case_insensitive(prefix: str):
    response = client.get(f"{prefix}/code/sup-pac-01")
    assert response.status_code == 200
    data = response.json()
    assert data["supplier_id"] == "sup-001"
    assert data["code"] == "SUP-PAC-01"


@pytest.mark.parametrize("prefix", ["/api/suppliers", "/suppliers"])
def test_get_supplier_by_code_not_found(prefix: str):
    response = client.get(f"{prefix}/code/UNKNOWN-CODE")
    assert response.status_code == 404
    detail = response.json().get("detail", "")
    assert "UNKNOWN-CODE" in detail
    assert "not found" in detail.lower()


# ============================================================================
# 4. Determinism & Risk Context
# ============================================================================


def test_repeated_calls_deterministic():
    res1 = client.get("/api/suppliers").json()
    res2 = client.get("/api/suppliers").json()
    assert res1 == res2

    detail1 = client.get("/api/suppliers/sup-002").json()
    detail2 = client.get("/api/suppliers/sup-002").json()
    assert detail1 == detail2


def test_alias_parity():
    canonical = client.get("/api/suppliers").json()
    alias = client.get("/suppliers").json()
    assert canonical == alias

    canonical_detail = client.get("/api/suppliers/sup-003").json()
    alias_detail = client.get("/suppliers/sup-003").json()
    assert canonical_detail == alias_detail
