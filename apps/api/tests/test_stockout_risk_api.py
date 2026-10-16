from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


class TestInventoryStockoutRiskEndpoints:
    """Tests /api/inventory/stockout-risk endpoints."""

    def test_post_stockout_risk_success(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
        }
        response = client.post("/api/inventory/stockout-risk", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"
        assert data["model_type"] == "DETERMINISTIC_LEAD_TIME_EXPOSURE"
        assert 0.0 <= data["exposure_index"] <= 1.0
        assert data["is_probability"] is False
        assert "risk_level" in data
        assert "is_stockout_predicted" in data
        assert "formula" in data
        assert isinstance(data["assumptions"], list)
        assert len(data["assumptions"]) > 0
        assert isinstance(data["limitations"], list)
        assert len(data["limitations"]) > 0

        # Verify breakdown contents
        breakdown = data["breakdown"]
        assert "available_quantity" in breakdown
        assert "reorder_point" in breakdown
        assert "average_daily_demand" in breakdown
        assert "lead_time_days" in breakdown
        assert "lead_time_demand" in breakdown
        assert "exposure_deficit" in breakdown
        assert "exposure_index" in breakdown
        assert "is_below_reorder" in breakdown
        assert "calculation_notes" in breakdown

    def test_get_stockout_risk_via_query_params(self):
        response = client.get(
            "/api/inventory/stockout-risk",
            params={
                "product_id": "prod-001",
                "warehouse_id": "wh-001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"
        assert data["is_probability"] is False

    def test_post_stockout_risk_with_supplier_override(self):
        # Fetch valid supplier from suppliers endpoint
        sup_resp = client.get("/api/suppliers")
        assert sup_resp.status_code == 200
        suppliers = sup_resp.json()
        assert len(suppliers) > 0
        first_supplier_id = suppliers[0]["id"]

        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "supplier_id": first_supplier_id,
        }
        response = client.post("/api/inventory/stockout-risk", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["breakdown"]["lead_time_days"] == suppliers[0]["lead_time_days"]

    def test_unknown_product_returns_404(self):
        payload = {
            "product_id": "prod-nonexistent",
            "warehouse_id": "wh-001",
        }
        response = client.post("/api/inventory/stockout-risk", json=payload)
        assert response.status_code == 404
        assert "Product 'prod-nonexistent' not found" in response.json()["detail"]

    def test_unknown_warehouse_returns_404(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-nonexistent",
        }
        response = client.post("/api/inventory/stockout-risk", json=payload)
        assert response.status_code == 404
        assert "Warehouse 'wh-nonexistent' not found" in response.json()["detail"]

    def test_invalid_supplier_override_returns_422(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "supplier_id": "sup-nonexistent-123",
        }
        response = client.post("/api/inventory/stockout-risk", json=payload)
        assert response.status_code == 422
        assert "Specified supplier 'sup-nonexistent-123' not found" in response.json()["detail"]

    def test_invalid_payload_missing_fields_returns_422(self):
        response = client.post("/api/inventory/stockout-risk", json={"product_id": "prod-001"})
        assert response.status_code == 422

    def test_invalid_model_type_returns_422(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "model_type": "UNKNOWN_MODEL",
        }
        response = client.post("/api/inventory/stockout-risk", json=payload)
        assert response.status_code == 422


class TestDecisionStockoutRiskEndpoints:
    """Tests /api/decisions/{decision_id}/stockout-risk endpoints."""

    @pytest.fixture
    def created_decision(self):
        resp = client.post(
            "/api/decisions",
            json={"product_id": "prod-001", "warehouse_id": "wh-001"},
        )
        assert resp.status_code == 201
        return resp.json()

    def test_post_decision_stockout_risk_with_body(self, created_decision):
        decision_id = created_decision["id"]
        response = client.post(
            f"/api/decisions/{decision_id}/stockout-risk",
            json={"model_type": "DETERMINISTIC_LEAD_TIME_EXPOSURE"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"
        assert data["is_probability"] is False
        assert 0.0 <= data["exposure_index"] <= 1.0

    def test_post_decision_stockout_risk_empty_body(self, created_decision):
        decision_id = created_decision["id"]
        response = client.post(
            f"/api/decisions/{decision_id}/stockout-risk",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == "prod-001"

    def test_get_decision_stockout_risk_query_endpoint(self, created_decision):
        decision_id = created_decision["id"]
        response = client.get(f"/api/decisions/{decision_id}/stockout-risk")
        assert response.status_code == 200

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"

    def test_unknown_decision_returns_404(self):
        response = client.post(
            "/api/decisions/dec-nonexistent/stockout-risk",
            json={},
        )
        assert response.status_code == 404
        assert "Decision 'dec-nonexistent' not found" in response.json()["detail"]

    def test_unknown_decision_get_returns_404(self):
        response = client.get("/api/decisions/dec-nonexistent/stockout-risk")
        assert response.status_code == 404
        assert "Decision 'dec-nonexistent' not found" in response.json()["detail"]


class TestBackwardCompatibility:
    """Verifies existing Day 6-17 endpoints remain fully functional."""

    def test_existing_replenishment_route_functional(self):
        response = client.post(
            "/api/inventory/replenishment",
            json={
                "product_id": "prod-001",
                "warehouse_id": "wh-001",
                "policy_type": "REORDER_POINT_DEFICIT",
            },
        )
        assert response.status_code == 200

    def test_existing_inventory_detail_route_functional(self):
        # Fetch first inventory item
        list_resp = client.get("/api/inventory")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) > 0
        item_id = items[0]["id"]

        detail_resp = client.get(f"/api/inventory/{item_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["id"] == item_id
