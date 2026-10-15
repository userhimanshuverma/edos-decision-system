from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


class TestInventoryReplenishmentEndpoints:
    """Tests /api/inventory/replenishment endpoints."""

    def test_post_replenishment_reorder_point_deficit(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "policy_type": "REORDER_POINT_DEFICIT",
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"
        assert data["policy_type"] == "REORDER_POINT_DEFICIT"
        assert "replenishment_quantity" in data
        assert "breakdown" in data
        assert "available_quantity" in data["breakdown"]
        assert "reorder_point" in data["breakdown"]
        assert "policy_notes" in data["breakdown"]

    def test_post_replenishment_lead_time_demand(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "policy_type": "LEAD_TIME_DEMAND",
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["policy_type"] == "LEAD_TIME_DEMAND"
        assert data["breakdown"]["lead_time_days"] is not None
        assert data["breakdown"]["lead_time_demand"] is not None

    def test_post_replenishment_target_stock(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "policy_type": "TARGET_STOCK",
            "target_stock": 300,
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["target_stock"] == 300
        assert data["policy_type"] == "TARGET_STOCK"

    def test_get_replenishment_via_query_params(self):
        response = client.get(
            "/api/inventory/replenishment",
            params={
                "product_id": "prod-001",
                "warehouse_id": "wh-001",
                "policy_type": "REORDER_POINT_DEFICIT",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == "prod-001"

    def test_unknown_product_returns_404(self):
        payload = {
            "product_id": "prod-nonexistent",
            "warehouse_id": "wh-001",
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 404
        assert "Product 'prod-nonexistent' not found" in response.json()["detail"]

    def test_unknown_warehouse_returns_404(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-nonexistent",
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 404
        assert "Warehouse 'wh-nonexistent' not found" in response.json()["detail"]

    def test_invalid_target_stock_returns_422(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "policy_type": "TARGET_STOCK",
            "target_stock": 5,  # Much lower than reorder_point
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 422
        assert "cannot be less than reorder_point" in response.json()["detail"]

    def test_missing_target_stock_for_target_policy_returns_422(self):
        payload = {
            "product_id": "prod-001",
            "warehouse_id": "wh-001",
            "policy_type": "TARGET_STOCK",
        }
        response = client.post("/api/inventory/replenishment", json=payload)
        assert response.status_code == 422


class TestDecisionReplenishmentEndpoints:
    """Tests /api/decisions/{decision_id}/replenishment endpoints."""

    @pytest.fixture
    def created_decision(self):
        resp = client.post(
            "/api/decisions",
            json={"product_id": "prod-001", "warehouse_id": "wh-001"},
        )
        assert resp.status_code == 201
        return resp.json()

    def test_post_decision_replenishment(self, created_decision):
        decision_id = created_decision["id"]
        response = client.post(
            f"/api/decisions/{decision_id}/replenishment",
            json={"policy_type": "REORDER_POINT_DEFICIT"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"
        assert data["policy_type"] == "REORDER_POINT_DEFICIT"

    def test_get_decision_replenishment(self, created_decision):
        decision_id = created_decision["id"]
        response = client.get(
            f"/api/decisions/{decision_id}/replenishment",
            params={"policy_type": "REORDER_POINT_DEFICIT"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == "prod-001"

    def test_unknown_decision_replenishment_returns_404(self):
        response = client.post(
            "/api/decisions/dec-nonexistent/replenishment",
            json={"policy_type": "REORDER_POINT_DEFICIT"},
        )
        assert response.status_code == 404
        assert "Decision 'dec-nonexistent' not found" in response.json()["detail"]
