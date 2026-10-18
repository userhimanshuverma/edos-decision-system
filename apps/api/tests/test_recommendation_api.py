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
def test_decision_with_actions(test_decision):
    """Helper fixture creating candidate actions for a test decision."""
    dec_id = test_decision["id"]

    # 1. DO_NOTHING
    client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "DO_NOTHING",
            "parameters": {},
            "description": "Baseline do nothing",
        },
    )

    # 2. PLACE_ORDER
    client.post(
        f"/api/decisions/{dec_id}/actions",
        json={
            "type": "PLACE_ORDER",
            "parameters": {"quantity": 25},
            "description": "Order 25 units",
        },
    )

    return test_decision


class TestRecommendationEndpoints:
    """API endpoint integration tests for Day 20 Recommendation Engine."""

    def test_post_generate_recommendation(self, test_decision_with_actions) -> None:
        dec_id = test_decision_with_actions["id"]

        res = client.post(
            f"/api/decisions/{dec_id}/recommendation",
            json={
                "policy_type": "REORDER_POINT_DEFICIT",
                "enforce_reorder_trigger": True,
            },
        )
        assert res.status_code == 200
        data = res.json()

        assert data["id"].startswith("REC-")
        assert data["decision_id"] == dec_id
        assert data["product_id"] == "prod-001"
        assert data["warehouse_id"] == "wh-001"
        assert data["status"] in ("RECOMMENDED", "NO_ACTION_REQUIRED")
        assert data["selection_rule"] == "LEXICOGRAPHIC_OPERATIONAL_DOMINANCE"
        assert data["recommended_action_id"] is not None
        assert data["recommended_action_type"] in ("PLACE_ORDER", "DO_NOTHING")
        assert len(data["selection_rationale"]) > 0
        assert data["total_actions_evaluated"] == 2
        assert len(data["alternatives"]) == 2
        assert data["evaluation_evidence"] is not None
        assert data["selected_evaluation"] is not None

    def test_get_recommendation_endpoint(self, test_decision_with_actions) -> None:
        dec_id = test_decision_with_actions["id"]

        # Call GET endpoint (auto-generates if not present)
        res = client.get(
            f"/api/decisions/{dec_id}/recommendation",
            params={
                "policy_type": "REORDER_POINT_DEFICIT",
                "enforce_reorder_trigger": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["decision_id"] == dec_id
        assert data["recommended_action_id"] is not None

    def test_get_recommendation_returns_persisted_without_recompute(self, test_decision_with_actions) -> None:
        dec_id = test_decision_with_actions["id"]

        # First generate via POST
        post_res = client.post(f"/api/decisions/{dec_id}/recommendation")
        assert post_res.status_code == 200
        first_id = post_res.json()["id"]

        # Subsequent GET should return the exact same persisted recommendation ID
        get_res = client.get(f"/api/decisions/{dec_id}/recommendation")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == first_id

    def test_recompute_flag_generates_new_recommendation(self, test_decision_with_actions) -> None:
        dec_id = test_decision_with_actions["id"]

        # First generate
        r1 = client.post(f"/api/decisions/{dec_id}/recommendation")
        id1 = r1.json()["id"]

        # GET with recompute=True
        r2 = client.get(f"/api/decisions/{dec_id}/recommendation", params={"recompute": True})
        assert r2.status_code == 200
        id2 = r2.json()["id"]

        assert id1 != id2
        assert id2 > id1

    def test_recommendation_for_decision_without_actions(self, test_decision) -> None:
        dec_id = test_decision["id"]

        res = client.post(f"/api/decisions/{dec_id}/recommendation")
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "NO_CANDIDATE_ACTIONS"
        assert data["recommended_action_id"] is None
        assert data["recommended_action"] is None
        assert data["total_actions_evaluated"] == 0

    def test_unknown_decision_returns_404(self) -> None:
        res = client.post("/api/decisions/DEC-UNKNOWN-999/recommendation")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

        res_get = client.get("/api/decisions/DEC-UNKNOWN-999/recommendation")
        assert res_get.status_code == 404

    def test_route_aliases(self, test_decision_with_actions) -> None:
        """Verifies endpoint accessible across canonical and alias routes."""
        dec_id = test_decision_with_actions["id"]

        # /decisions/...
        r1 = client.get(f"/decisions/{dec_id}/recommendation")
        assert r1.status_code == 200

        # /api/decision/...
        r2 = client.get(f"/api/decision/{dec_id}/recommendation")
        assert r2.status_code == 200

        # /decision/...
        r3 = client.get(f"/decision/{dec_id}/recommendation")
        assert r3.status_code == 200
