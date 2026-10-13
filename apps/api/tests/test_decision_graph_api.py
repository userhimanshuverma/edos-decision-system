from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.decision import (
    get_decision_event_repository,
    get_decision_graph_repository,
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
    get_decision_graph_repository().clear()
    yield
    get_decision_repository().clear()
    get_decision_event_repository().clear()
    get_decision_version_repository().clear()
    get_decision_graph_repository().clear()


def create_sample_decision() -> str:
    """Helper creating a test decision returning its unique ID."""
    res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
    assert res.status_code == 201
    return res.json()["id"]


class TestDecisionGraphApi:
    """Integration test suite for Decision Graph FastAPI endpoints."""

    def test_post_decision_graph_default_payload(self) -> None:
        """Verifies POST /api/decisions/{decision_id}/graph with empty payload creates default graph."""
        decision_id = create_sample_decision()

        res = client.post(f"/api/decisions/{decision_id}/graph", json={})
        assert res.status_code == 201
        data = res.json()

        assert data["id"].startswith("GRA-")
        assert data["graph_id"] == data["id"]
        assert data["decision_id"] == decision_id
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["type"] == "CONTEXT"
        assert data["nodes"][0]["node_type"] == "CONTEXT"
        assert data["nodes"][0]["decision_id"] == decision_id
        assert data["nodes"][0]["metadata"]["product_id"] == "prod-001"
        assert len(data["edges"]) == 0

    def test_post_decision_graph_custom_nodes_and_edges(self) -> None:
        """Verifies creating a full lineage graph with custom nodes and directed edges."""
        decision_id = create_sample_decision()

        payload = {
            "nodes": [
                {
                    "id": "ctx-1",
                    "type": "CONTEXT",
                    "label": "Operational Context",
                    "metadata": {"source": "ShopFlow"},
                },
                {
                    "id": "act-1",
                    "type": "ACTION",
                    "label": "Replenish 200 units",
                },
                {
                    "id": "val-1",
                    "type": "VALIDATION",
                    "label": "Capacity check passed",
                },
                {
                    "id": "scn-1",
                    "type": "SCENARIO",
                    "label": "Base Demand Projection",
                },
                {
                    "id": "res-1",
                    "type": "RESULT",
                    "label": "Recommended Order",
                },
            ],
            "edges": [
                {"id": "e1", "source_id": "ctx-1", "target_id": "act-1", "relationship_type": "GENERATES"},
                {"id": "e2", "source_id": "act-1", "target_id": "val-1", "relationship_type": "VALIDATES"},
                {"id": "e3", "source_id": "val-1", "target_id": "scn-1", "relationship_type": "SIMULATES"},
                {"id": "e4", "source_id": "scn-1", "target_id": "res-1", "relationship_type": "PRODUCES"},
            ],
        }

        res = client.post(f"/api/decisions/{decision_id}/graph", json=payload)
        assert res.status_code == 201
        data = res.json()

        assert data["decision_id"] == decision_id
        assert len(data["nodes"]) == 5
        assert len(data["edges"]) == 4

        # Validate edge connections
        edges = {e["id"]: e for e in data["edges"]}
        assert edges["e1"]["source_id"] == "ctx-1"
        assert edges["e1"]["target_id"] == "act-1"
        assert edges["e1"]["relationship_type"] == "GENERATES"
        assert edges["e4"]["relationship_type"] == "PRODUCES"

    def test_get_decision_graph_success(self) -> None:
        """Verifies GET /api/decisions/{decision_id}/graph retrieves the stored graph."""
        decision_id = create_sample_decision()
        client.post(f"/api/decisions/{decision_id}/graph", json={})

        get_res = client.get(f"/api/decisions/{decision_id}/graph")
        assert get_res.status_code == 200
        data = get_res.json()

        assert data["decision_id"] == decision_id
        assert len(data["nodes"]) == 1

    def test_get_decision_graph_unknown_decision_returns_404(self) -> None:
        """Verifies GET for unknown decision returns HTTP 404."""
        res = client.get("/api/decisions/DEC-NONEXISTENT/graph")
        assert res.status_code == 404
        assert "DEC-NONEXISTENT" in res.json()["detail"]

    def test_get_decision_graph_not_found_returns_404(self) -> None:
        """Verifies GET for decision without graph returns HTTP 404."""
        decision_id = create_sample_decision()
        res = client.get(f"/api/decisions/{decision_id}/graph")
        assert res.status_code == 404
        assert "Decision graph" in res.json()["detail"]

    def test_post_decision_graph_unknown_decision_returns_404(self) -> None:
        """Verifies POST for unknown decision returns HTTP 404."""
        res = client.post("/api/decisions/DEC-NONEXISTENT/graph", json={})
        assert res.status_code == 404
        assert "DEC-NONEXISTENT" in res.json()["detail"]

    def test_post_duplicate_decision_graph_returns_409(self) -> None:
        """Verifies creating a second graph for the same decision returns HTTP 409 Conflict."""
        decision_id = create_sample_decision()
        first = client.post(f"/api/decisions/{decision_id}/graph", json={})
        assert first.status_code == 201

        second = client.post(f"/api/decisions/{decision_id}/graph", json={})
        assert second.status_code == 409
        assert "already exists" in second.json()["detail"]

    def test_post_graph_invalid_edge_reference_returns_422(self) -> None:
        """Verifies edge referencing non-existent node returns HTTP 422 Unprocessable Entity."""
        decision_id = create_sample_decision()
        payload = {
            "nodes": [
                {"id": "n1", "type": "CONTEXT"},
            ],
            "edges": [
                {"id": "e1", "source_id": "n1", "target_id": "ghost-node", "relationship_type": "GENERATES"},
            ],
        }
        res = client.post(f"/api/decisions/{decision_id}/graph", json=payload)
        assert res.status_code == 422
        assert "ghost-node" in res.json()["detail"]

    def test_post_graph_cross_decision_node_returns_422(self) -> None:
        """Verifies node referencing another decision ID returns HTTP 422."""
        decision_id = create_sample_decision()
        payload = {
            "nodes": [
                {"id": "n1", "type": "CONTEXT", "decision_id": "DEC-WRONG"},
            ],
            "edges": [],
        }
        res = client.post(f"/api/decisions/{decision_id}/graph", json=payload)
        assert res.status_code == 422
        assert "does not match graph decision_id" in res.json()["detail"]

    def test_post_graph_invalid_relationship_type_returns_422(self) -> None:
        """Verifies disallowed relationship between node types returns HTTP 422."""
        decision_id = create_sample_decision()
        payload = {
            "nodes": [
                {"id": "n1", "type": "RESULT"},
                {"id": "n2", "type": "CONTEXT"},
            ],
            "edges": [
                # RESULT -> CONTEXT with GENERATES is invalid
                {"id": "e1", "source_id": "n1", "target_id": "n2", "relationship_type": "GENERATES"},
            ],
        }
        res = client.post(f"/api/decisions/{decision_id}/graph", json=payload)
        assert res.status_code == 422
        assert "not permitted" in res.json()["detail"]

    def test_post_graph_self_loop_edge_returns_422(self) -> None:
        """Verifies self-loop edge returns HTTP 422."""
        decision_id = create_sample_decision()
        payload = {
            "nodes": [
                {"id": "n1", "type": "CONTEXT"},
            ],
            "edges": [
                {"id": "e1", "source_id": "n1", "target_id": "n1", "relationship_type": "REFERENCES"},
            ],
        }
        res = client.post(f"/api/decisions/{decision_id}/graph", json=payload)
        assert res.status_code == 422
        assert "identical source and target" in res.json()["detail"]

    def test_post_graph_extra_fields_forbidden(self) -> None:
        """Verifies extra payload fields are rejected with HTTP 422."""
        decision_id = create_sample_decision()
        res = client.post(
            f"/api/decisions/{decision_id}/graph",
            json={"unrecognized_field": "test"},
        )
        assert res.status_code == 422

    def test_route_aliases_support(self) -> None:
        """Verifies canonical and route alias endpoints (/decisions, /api/decision, /decision)."""
        dec_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
        assert dec_res.status_code == 201
        decision_id = dec_res.json()["id"]

        # 1. Alias: POST /decisions/{id}/graph
        alias_post = client.post(f"/decisions/{decision_id}/graph", json={})
        assert alias_post.status_code == 201

        # 2. Alias: GET /api/decision/{id}/graph
        alias_get1 = client.get(f"/api/decision/{decision_id}/graph")
        assert alias_get1.status_code == 200

        # 3. Alias: GET /decision/{id}/graph
        alias_get2 = client.get(f"/decision/{decision_id}/graph")
        assert alias_get2.status_code == 200

    def test_existing_endpoints_remain_functional(self) -> None:
        """Verifies that existing decision lifecycle, audit event, and version endpoints remain unaffected."""
        # Create decision
        dec_res = client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
        assert dec_res.status_code == 201
        decision_id = dec_res.json()["id"]

        # Lifecycle transition
        patch_res = client.patch(f"/api/decisions/{decision_id}/status", json={"status": "CONTEXTUALIZING"})
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "CONTEXTUALIZING"

        # Events endpoint
        events_res = client.get(f"/api/decisions/{decision_id}/events")
        assert events_res.status_code == 200
        assert len(events_res.json()) == 2

        # Version endpoint
        ver_res = client.post(f"/api/decisions/{decision_id}/versions", json={"description": "v1 snapshot"})
        assert ver_res.status_code == 201
        assert ver_res.json()["version_number"] == 1

        # Create Graph
        graph_res = client.post(f"/api/decisions/{decision_id}/graph", json={})
        assert graph_res.status_code == 201
