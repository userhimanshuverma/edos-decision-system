import datetime as dt
from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


# ============================================================================
# 1. GET /api/demand & GET /demand (Collection Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_records(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    # Default seed 42 dataset produces 10 products x 3 warehouses x 14 days = 420 records
    assert len(data) == 420

    first_item = data[0]
    expected_fields = {
        "demand_id",
        "id",
        "product_id",
        "warehouse_id",
        "date",
        "quantity",
    }
    assert expected_fields.issubset(set(first_item.keys()))


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_demand_response_structure_and_types(prefix: str):
    response = client.get(prefix)
    assert response.status_code == 200

    for item in response.json():
        assert isinstance(item["demand_id"], str)
        assert len(item["demand_id"]) > 0
        assert item["id"] == item["demand_id"]
        assert isinstance(item["product_id"], str)
        assert isinstance(item["warehouse_id"], str)
        assert isinstance(item["date"], str)
        assert isinstance(item["quantity"], int)
        assert item["quantity"] >= 0

        # Validate date string format YYYY-MM-DD
        parsed_date = dt.date.fromisoformat(item["date"])
        assert parsed_date is not None


def test_demand_records_are_deterministic():
    res1 = client.get("/api/demand")
    res2 = client.get("/api/demand")
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == res2.json()


def test_demand_query_filtering():
    # Filter by product_id
    res_prod = client.get("/api/demand?product_id=prod-001")
    assert res_prod.status_code == 200
    data_prod = res_prod.json()
    # 3 warehouses x 14 days = 42 records
    assert len(data_prod) == 42
    assert all(r["product_id"] == "prod-001" for r in data_prod)

    # Filter by warehouse_id
    res_wh = client.get("/api/demand?warehouse_id=wh-001")
    assert res_wh.status_code == 200
    data_wh = res_wh.json()
    # 10 products x 14 days = 140 records
    assert len(data_wh) == 140
    assert all(r["warehouse_id"] == "wh-001" for r in data_wh)

    # Combined filter
    res_combined = client.get("/api/demand?product_id=prod-001&warehouse_id=wh-001")
    assert res_combined.status_code == 200
    data_comb = res_combined.json()
    # 14 days
    assert len(data_comb) == 14
    assert all(r["product_id"] == "prod-001" and r["warehouse_id"] == "wh-001" for r in data_comb)

    # Filter by date range
    all_dates = sorted({r["date"] for r in client.get("/api/demand").json()})
    start_d = all_dates[3]
    end_d = all_dates[7]
    res_date = client.get(f"/api/demand?start_date={start_d}&end_date={end_d}")
    assert res_date.status_code == 200
    data_date = res_date.json()
    # 5 dates x 10 products x 3 warehouses = 150 records
    assert len(data_date) == 150
    assert all(start_d <= r["date"] <= end_d for r in data_date)


# ============================================================================
# 2. GET /api/demand/{demand_id} (Individual Record Endpoint)
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_by_id_valid(prefix: str):
    all_records = client.get("/api/demand").json()
    target_id = all_records[0]["demand_id"]

    response = client.get(f"{prefix}/{target_id}")
    assert response.status_code == 200
    item = response.json()
    assert item["demand_id"] == target_id
    assert item["id"] == target_id
    assert item["product_id"] == all_records[0]["product_id"]
    assert item["warehouse_id"] == all_records[0]["warehouse_id"]
    assert item["quantity"] == all_records[0]["quantity"]


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_by_id_unknown_returns_404(prefix: str):
    response = client.get(f"{prefix}/non-existent-demand-id-999")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


# ============================================================================
# 3. GET /api/demand/product/{product_id}
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_by_product_valid(prefix: str):
    response = client.get(f"{prefix}/product/prod-001")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 42
    assert all(r["product_id"] == "prod-001" for r in data)


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_by_product_unknown_returns_404(prefix: str):
    response = client.get(f"{prefix}/product/ghost-product-999")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "ghost-product-999" in body["detail"]


def test_get_demand_by_product_with_warehouse_filter():
    response = client.get("/api/demand/product/prod-001?warehouse_id=wh-001")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 14
    assert all(r["product_id"] == "prod-001" and r["warehouse_id"] == "wh-001" for r in data)

    # Unknown warehouse under valid product
    res_err = client.get("/api/demand/product/prod-001?warehouse_id=ghost-wh")
    assert res_err.status_code == 404


# ============================================================================
# 4. GET /api/demand/warehouse/{warehouse_id}
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_by_warehouse_valid(prefix: str):
    response = client.get(f"{prefix}/warehouse/wh-001")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 140
    assert all(r["warehouse_id"] == "wh-001" for r in data)


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_by_warehouse_unknown_returns_404(prefix: str):
    response = client.get(f"{prefix}/warehouse/ghost-warehouse-999")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "ghost-warehouse-999" in body["detail"]


# ============================================================================
# 5. GET /api/demand/product/{product_id}/trend
# ============================================================================


@pytest.mark.parametrize("prefix", ["/api/demand", "/demand"])
def test_get_demand_trend_valid(prefix: str):
    response = client.get(f"{prefix}/product/prod-001/trend")
    assert response.status_code == 200
    data = response.json()

    assert data["product_id"] == "prod-001"
    assert data["warehouse_id"] is None
    assert isinstance(data["total_demand"], int)
    assert data["total_demand"] > 0
    assert isinstance(data["average_daily_demand"], float)
    assert data["average_daily_demand"] > 0.0
    assert data["trend_direction"] in {"increasing", "decreasing", "stable"}
    assert isinstance(data["percentage_change"], float)
    assert isinstance(data["history"], list)
    assert len(data["history"]) == 14

    for point in data["history"]:
        assert "date" in point
        assert "quantity" in point
        assert isinstance(point["quantity"], int)
        assert point["quantity"] >= 0


def test_get_demand_trend_with_warehouse_filter():
    response = client.get("/api/demand/product/prod-001/trend?warehouse_id=wh-001")
    assert response.status_code == 200
    data = response.json()

    assert data["product_id"] == "prod-001"
    assert data["warehouse_id"] == "wh-001"
    assert len(data["history"]) == 14


def test_get_demand_trend_unknown_product_returns_404():
    response = client.get("/api/demand/product/ghost-prod-999/trend")
    assert response.status_code == 404
    body = response.json()
    assert "ghost-prod-999" in body["detail"]


def test_get_demand_trend_unknown_warehouse_returns_404():
    response = client.get("/api/demand/product/prod-001/trend?warehouse_id=ghost-wh-999")
    assert response.status_code == 404
    body = response.json()
    assert "ghost-wh-999" in body["detail"]
