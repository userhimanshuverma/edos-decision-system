from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


@pytest.fixture
def test_decision():
    """Helper fixture creating a fresh test decision."""
    res = client.post(
        "/api/decisions",
        json={"product_id": "prod-001", "warehouse_id": "wh-001"},
    )
    assert res.status_code == 201
    return res.json()


@pytest.fixture
def test_actions(test_decision):
    """Helper fixture creating candidate actions for the test decision."""
    dec_id = test_decision["id"]

    # 1. DO_NOTHING
    r1 = client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "DO_NOTHING",
            "parameters": {},
            "description": "Baseline no action",
        },
    )
    assert r1.status_code == 201
    a1 = r1.json()

    # 2. PLACE_ORDER
    r2 = client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "PLACE_ORDER",
            "parameters": {"quantity": 25},
            "description": "Order 25 units",
        },
    )
    assert r2.status_code == 201
    a2 = r2.json()

    # 3. SWITCH_SUPPLIER
    r3 = client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "SWITCH_SUPPLIER",
            "parameters": {"target_supplier_id": "sup-002"},
            "description": "Switch to alternative supplier",
        },
    )
    assert r3.status_code == 201
    a3 = r3.json()

    return {
        "decision_id": dec_id,
        "do_nothing": a1,
        "place_order": a2,
        "switch_supplier": a3,
    }


class TestActionEvaluationEndpoints:
    """Tests for Day 19 Action Evaluation API endpoints."""

    def test_evaluate_individual_action_place_order(self, test_actions):
        dec_id = test_actions["decision_id"]
        act_id = test_actions["place_order"]["id"]

        response = client.post(
            f"/api/decisions/{dec_id}/actions/{act_id}/evaluate",
            json={
                "policy_type": "REORDER_POINT_DEFICIT",
                "enforce_reorder_trigger": True,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["action_id"] == act_id
        assert data["action_type"] == "PLACE_ORDER"
        assert data["decision_id"] == dec_id
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"

        # Stockout exposure checks
        exposure = data["stockout_exposure"]
        assert exposure["is_probability"] is False
        assert 0.0 <= exposure["current_exposure_index"] <= 1.0
        assert 0.0 <= exposure["projected_exposure_index"] <= 1.0
        assert "notes" in exposure

        # Replenishment impact checks
        replen = data["replenishment_impact"]
        assert replen["policy_type"] == "REORDER_POINT_DEFICIT"
        assert replen["action_order_quantity"] == 25
        assert replen["shortfall_addressed"] >= 0
        assert replen["remaining_shortfall"] >= 0

        # Cost impact checks: 25 units * unit_cost
        cost = data["cost_impact"]
        assert cost["is_cost_calculable"] is True
        assert cost["cost_status"] == "CALCULATED"
        assert cost["order_quantity"] == 25
        assert cost["direct_procurement_cost"] is not None
        assert cost["direct_procurement_cost"] > 0

        # Evidence checks
        evidence = data["evidence"]
        assert "inputs_summary" in evidence
        assert "formulas" in evidence
        assert "assumptions" in evidence
        assert len(evidence["assumptions"]) > 0

        # Day 20 boundary check: score is None
        assert data["overall_score"] is None
        assert data["scoring_status"] == "UNRESOLVED_MULTI_CRITERIA_DECISION"

    def test_evaluate_individual_action_do_nothing(self, test_actions):
        dec_id = test_actions["decision_id"]
        act_id = test_actions["do_nothing"]["id"]

        response = client.post(f"/api/decisions/{dec_id}/actions/{act_id}/evaluate")
        assert response.status_code == 200
        data = response.json()

        assert data["action_type"] == "DO_NOTHING"
        assert data["cost_impact"]["cost_status"] == "ZERO_COST"
        assert data["cost_impact"]["direct_procurement_cost"] == 0.0
        assert data["replenishment_impact"]["shortfall_addressed"] == 0

    def test_evaluate_individual_action_switch_supplier(self, test_actions):
        dec_id = test_actions["decision_id"]
        act_id = test_actions["switch_supplier"]["id"]

        response = client.post(f"/api/decisions/{dec_id}/actions/{act_id}/evaluate")
        assert response.status_code == 200
        data = response.json()

        assert data["action_type"] == "SWITCH_SUPPLIER"
        sup = data["supplier_impact"]
        assert sup["is_supplier_switched"] is True
        assert sup["effective_supplier_id"] == "sup-002"

        # Cost must be marked UNAVAILABLE rather than fabricated
        assert data["cost_impact"]["cost_status"] == "UNAVAILABLE"
        assert data["cost_impact"]["direct_procurement_cost"] is None
        assert data["cost_impact"]["unavailability_reason"] is not None

    def test_get_evaluate_individual_action_query_params(self, test_actions):
        dec_id = test_actions["decision_id"]
        act_id = test_actions["place_order"]["id"]

        response = client.get(
            f"/api/decisions/{dec_id}/actions/{act_id}/evaluate",
            params={"policy_type": "REORDER_POINT_DEFICIT"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action_id"] == act_id

    def test_evaluate_decision_actions_endpoint(self, test_actions):
        dec_id = test_actions["decision_id"]

        response = client.post(
            f"/api/decisions/{dec_id}/actions/evaluate",
            json={"policy_type": "REORDER_POINT_DEFICIT"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["decision_id"] == dec_id
        assert data["total_actions_evaluated"] == 3
        assert len(data["evaluations"]) == 3
        assert len(data["summary_notes"]) > 0

    def test_get_evaluate_decision_actions_endpoint(self, test_actions):
        dec_id = test_actions["decision_id"]

        response = client.get(
            f"/api/decisions/{dec_id}/actions/evaluate",
            params={"policy_type": "REORDER_POINT_DEFICIT"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_actions_evaluated"] == 3

    def test_evaluate_decision_alias_endpoints(self, test_actions):
        dec_id = test_actions["decision_id"]

        res_post = client.post(f"/api/decisions/{dec_id}/evaluation")
        assert res_post.status_code == 200
        assert res_post.json()["total_actions_evaluated"] == 3

        res_get = client.get(f"/api/decisions/{dec_id}/evaluation")
        assert res_get.status_code == 200
        assert res_get.json()["total_actions_evaluated"] == 3

    def test_evaluate_unknown_decision_404(self):
        response = client.post("/api/decisions/DEC-NONEXISTENT/actions/ACT-001/evaluate")
        assert response.status_code == 404

    def test_evaluate_unknown_action_404(self, test_decision):
        dec_id = test_decision["id"]
        response = client.post(f"/api/decisions/{dec_id}/actions/ACT-NONEXISTENT/evaluate")
        assert response.status_code == 404

    def test_evaluate_target_stock_policy_prerequisites(self, test_actions):
        dec_id = test_actions["decision_id"]
        act_id = test_actions["place_order"]["id"]

        # Missing target_stock for TARGET_STOCK policy -> 422
        response = client.post(
            f"/api/decisions/{dec_id}/actions/{act_id}/evaluate",
            json={"policy_type": "TARGET_STOCK"},
        )
        assert response.status_code == 422
