from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestContextAPI:
    """Integration tests for the unified Decision Context API endpoints."""

    def test_get_context_success(self, client: TestClient):
        response = client.get("/api/context/product/prod-001/warehouse/wh-001")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"

        # Verify product context
        assert data["product"]["id"] == "prod-001"
        assert data["product"]["sku"] == "SKU-ELEC-1001"
        assert data["product"]["category"] == "Industrial Electronics"
        assert data["product"]["unit_cost"] > 0
        assert data["product"]["reorder_point"] == 50

        # Verify warehouse context
        assert data["warehouse"]["id"] == "wh-001"
        assert data["warehouse"]["code"] == "WH-EAST-01"

        # Verify inventory context
        assert data["inventory"] is not None
        assert data["inventory"]["inventory_id"] == "inv-prod-001-wh-001"
        assert data["inventory"]["quantity_on_hand"] >= 0
        assert data["inventory"]["available_quantity"] == (
            data["inventory"]["quantity_on_hand"] - data["inventory"]["quantity_reserved"]
        )

        # Verify demand context
        assert data["demand"] is not None
        assert data["demand"]["total_demand"] >= 0
        assert data["demand"]["average_daily_demand"] >= 0
        assert data["demand"]["trend_direction"] in ("increasing", "decreasing", "stable")
        assert len(data["demand"]["history"]) > 0

        # Verify supplier context
        assert data["supplier"] is not None
        assert data["supplier"]["code"] == "SUP-PAC-01"
        assert data["supplier"]["risk_level"] in ("LOW", "MEDIUM", "HIGH")

        # Verify derived metrics
        assert "coverage_days" in data["metrics"]
        assert "lead_time_days" in data["metrics"]
        assert "is_below_reorder" in data["metrics"]
        assert "net_deficit" in data["metrics"]
        assert "context_status" in data["metrics"]

        # Verify overall status
        assert data["status"] in ("NORMAL", "ATTENTION", "ELEVATED")

    def test_get_context_unknown_product_returns_404(self, client: TestClient):
        response = client.get("/api/context/product/prod-nonexistent/warehouse/wh-001")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "prod-nonexistent" in response.json()["detail"]

    def test_get_context_unknown_warehouse_returns_404(self, client: TestClient):
        response = client.get("/api/context/product/prod-001/warehouse/wh-nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "wh-nonexistent" in response.json()["detail"]

    def test_get_context_with_supplier_override(self, client: TestClient):
        response = client.get("/api/context/product/prod-001/warehouse/wh-001?supplier_id=sup-002")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["supplier"]["supplier_id"] == "sup-002"
        assert data["supplier"]["code"] == "SUP-APX-02"

    def test_get_context_by_query_parameters(self, client: TestClient):
        response = client.get("/api/context?product_id=prod-001&warehouse_id=wh-001")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"

    def test_get_context_alias_route(self, client: TestClient):
        response = client.get("/context/product/prod-001/warehouse/wh-001")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["product_id"] == "prod-001"

    def test_repeated_calls_are_strictly_deterministic(self, client: TestClient):
        res1 = client.get("/api/context/product/prod-001/warehouse/wh-001")
        res2 = client.get("/api/context/product/prod-001/warehouse/wh-001")

        assert res1.status_code == status.HTTP_200_OK
        assert res2.status_code == status.HTTP_200_OK
        assert res1.json() == res2.json()
