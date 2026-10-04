from datetime import datetime
from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


# ============================================================================
# 1. GET /api/inventory & GET /inventory (Collection Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_records(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    # Default seed 42 dataset produces 10 products x 3 warehouses = 30 positions
    assert len(data) == 30

    first_item = data[0]
    # Check all required fields are present
    expected_fields = {
        "inventory_id",
        "id",
        "product_id",
        "warehouse_id",
        "quantity_on_hand",
        "quantity_reserved",
        "available_quantity",
        "reorder_point",
        "updated_at",
    }
    assert expected_fields.issubset(set(first_item.keys()))


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_inventory_response_structure_and_types(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    for item in response.json():
        assert isinstance(item["inventory_id"], str)
        assert len(item["inventory_id"]) > 0
        assert item["id"] == item["inventory_id"]
        assert isinstance(item["product_id"], str)
        assert isinstance(item["warehouse_id"], str)
        assert isinstance(item["quantity_on_hand"], int)
        assert isinstance(item["quantity_reserved"], int)
        assert isinstance(item["available_quantity"], int)
        assert isinstance(item["reorder_point"], int)
        assert isinstance(item["updated_at"], str)

        # Datetime parse validation
        parsed_dt = datetime.fromisoformat(item["updated_at"])
        assert parsed_dt.tzinfo is not None


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_inventory_available_quantity_calculation(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    for item in response.json():
        expected_available = item["quantity_on_hand"] - item["quantity_reserved"]
        assert item["available_quantity"] == expected_available
        assert item["available_quantity"] >= 0


def test_inventory_records_are_deterministic():
    res1 = client.get("/api/inventory").json()
    res2 = client.get("/api/inventory").json()
    assert res1 == res2


def test_inventory_query_filtering():
    # Filter by product_id
    res_prod = client.get("/api/inventory?product_id=prod-001")
    assert res_prod.status_code == 200
    prod_data = res_prod.json()
    assert len(prod_data) == 3
    assert all(item["product_id"] == "prod-001" for item in prod_data)

    # Filter by warehouse_id
    res_wh = client.get("/api/inventory?warehouse_id=wh-001")
    assert res_wh.status_code == 200
    wh_data = res_wh.json()
    assert len(wh_data) == 10
    assert all(item["warehouse_id"] == "wh-001" for item in wh_data)

    # Filter by both
    res_both = client.get("/api/inventory?product_id=prod-001&warehouse_id=wh-001")
    assert res_both.status_code == 200
    both_data = res_both.json()
    assert len(both_data) == 1
    assert both_data[0]["product_id"] == "prod-001"
    assert both_data[0]["warehouse_id"] == "wh-001"

    # Query with no matches returns empty list
    res_empty = client.get("/api/inventory?product_id=nonexistent")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


# ============================================================================
# 2. GET /api/inventory/{inventory_id} & GET /inventory/{id}
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_by_id_valid(prefix: str):
    valid_id = "inv-prod-001-wh-001"
    response = client.get(f"{prefix}/{valid_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["inventory_id"] == valid_id
    assert data["id"] == valid_id
    assert data["product_id"] == "prod-001"
    assert data["warehouse_id"] == "wh-001"
    assert data["available_quantity"] == data["quantity_on_hand"] - data["quantity_reserved"]


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_by_id_unknown_returns_404(prefix: str):
    unknown_id = "inv-does-not-exist"
    response = client.get(f"{prefix}/{unknown_id}")
    assert response.status_code == 404
    assert f"Inventory position '{unknown_id}' not found" in response.json()["detail"]


# ============================================================================
# 3. GET /api/inventory/product/{product_id}
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_by_product_valid(prefix: str):
    product_id = "prod-001"
    response = client.get(f"{prefix}/product/{product_id}")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert all(item["product_id"] == product_id for item in data)

    # Verify positions cover distinct warehouses
    warehouses_found = {item["warehouse_id"] for item in data}
    assert warehouses_found == {"wh-001", "wh-002", "wh-003"}


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_by_product_unknown_returns_404(prefix: str):
    unknown_product = "prod-unknown-sku"
    response = client.get(f"{prefix}/product/{unknown_product}")
    assert response.status_code == 404
    assert f"Product '{unknown_product}' not found" in response.json()["detail"]


# ============================================================================
# 4. GET /api/inventory/warehouse/{warehouse_id}
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_by_warehouse_valid(prefix: str):
    warehouse_id = "wh-001"
    response = client.get(f"{prefix}/warehouse/{warehouse_id}")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 10
    assert all(item["warehouse_id"] == warehouse_id for item in data)

    # Verify positions cover all 10 products
    products_found = {item["product_id"] for item in data}
    assert len(products_found) == 10


@pytest.mark.parametrize("prefix", ["/api/inventory", "/inventory"])
def test_get_inventory_by_warehouse_unknown_returns_404(prefix: str):
    unknown_warehouse = "wh-unknown-loc"
    response = client.get(f"{prefix}/warehouse/{unknown_warehouse}")
    assert response.status_code == 404
    assert f"Warehouse '{unknown_warehouse}' not found" in response.json()["detail"]


# ============================================================================
# 5. Data Integrity & Invariants
# ============================================================================


def test_inventory_data_integrity_and_invariants():
    response = client.get("/api/inventory")
    assert response.status_code == 200
    records = response.json()

    # Collect known entities
    known_products = {f"prod-{i:03d}" for i in range(1, 11)}
    known_warehouses = {f"wh-{i:03d}" for i in range(1, 4)}

    for inv in records:
        # Product and warehouse referential integrity
        assert inv["product_id"] in known_products
        assert inv["warehouse_id"] in known_warehouses

        # Stock balance invariants
        assert inv["quantity_reserved"] <= inv["quantity_on_hand"]
        assert inv["available_quantity"] == inv["quantity_on_hand"] - inv["quantity_reserved"]
        assert inv["reorder_point"] >= 0
        assert inv["quantity_on_hand"] >= 0
        assert inv["quantity_reserved"] >= 0
