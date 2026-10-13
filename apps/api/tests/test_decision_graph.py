from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.domain.decision_graph import (
    ALLOWED_RELATIONSHIPS,
    CrossDecisionGraphError,
    DecisionGraph,
    DuplicateGraphEdgeError,
    DuplicateGraphNodeError,
    GraphEdge,
    GraphIntegrityError,
    GraphNode,
    GraphNodeType,
    GraphRelationshipType,
    InvalidEdgeReferenceError,
    InvalidGraphRelationshipError,
    SelfLoopEdgeError,
)


class TestDecisionGraphDomain:
    """Unit test suite for Decision Graph domain models and integrity validation."""

    def test_valid_node_creation(self) -> None:
        """Verifies creating a valid GraphNode with required and optional attributes."""
        node = GraphNode(
            id="node-001",
            type="CONTEXT",
            decision_id="DEC-0001",
            label="Situation Context",
            metadata={"product_id": "prod-001", "warehouse_id": "wh-001"},
        )
        assert node.id == "node-001"
        assert node.node_type == GraphNodeType.CONTEXT
        assert node.type == GraphNodeType.CONTEXT
        assert node.decision_id == "DEC-0001"
        assert node.label == "Situation Context"
        assert node.metadata["product_id"] == "prod-001"
        assert node.created_at.tzinfo == timezone.utc

    def test_node_empty_or_whitespace_identifier_rejected(self) -> None:
        """Verifies empty or whitespace-only identifiers are rejected."""
        with pytest.raises(ValidationError):
            GraphNode(id="", type="CONTEXT", decision_id="DEC-0001")
        with pytest.raises(ValidationError):
            GraphNode(id="   ", type="CONTEXT", decision_id="DEC-0001")
        with pytest.raises(ValidationError):
            GraphNode(id="node-1", type="CONTEXT", decision_id="")

    def test_node_invalid_type_rejected(self) -> None:
        """Verifies invalid node types are rejected by schema validation."""
        with pytest.raises(ValidationError):
            GraphNode(id="node-1", type="UNSUPPORTED_STAGE", decision_id="DEC-0001")

    def test_node_extra_fields_forbidden(self) -> None:
        """Verifies strict field validation forbids arbitrary undeclared fields."""
        with pytest.raises(ValidationError):
            GraphNode(
                id="node-1",
                type="CONTEXT",
                decision_id="DEC-0001",
                unsupported_extra_field=123,  # type: ignore[call-arg]
            )

    def test_valid_edge_creation(self) -> None:
        """Verifies creating a valid GraphEdge."""
        edge = GraphEdge(
            id="edg-001",
            source_id="node-ctx-1",
            target_id="node-act-1",
            relationship_type=GraphRelationshipType.GENERATES,
            decision_id="DEC-0001",
            metadata={"rule": "replenishment_trigger"},
        )
        assert edge.id == "edg-001"
        assert edge.source_id == "node-ctx-1"
        assert edge.target_id == "node-act-1"
        assert edge.relationship_type == GraphRelationshipType.GENERATES
        assert edge.decision_id == "DEC-0001"
        assert edge.metadata["rule"] == "replenishment_trigger"

    def test_edge_self_loop_rejected(self) -> None:
        """Verifies an edge cannot point to the same source and target node."""
        with pytest.raises(SelfLoopEdgeError):
            GraphEdge(
                id="edg-001",
                source_id="node-1",
                target_id="node-1",
                relationship_type=GraphRelationshipType.REFERENCES,
            )

    def test_edge_empty_identifiers_rejected(self) -> None:
        """Verifies empty edge identifiers are rejected."""
        with pytest.raises(ValidationError):
            GraphEdge(
                id="",
                source_id="n1",
                target_id="n2",
                relationship_type=GraphRelationshipType.GENERATES,
            )
        with pytest.raises(ValidationError):
            GraphEdge(
                id="e1",
                source_id="",
                target_id="n2",
                relationship_type=GraphRelationshipType.GENERATES,
            )

    def test_valid_decision_graph_full_lineage(self) -> None:
        """Verifies a fully connected DecisionGraph modeling the Context -> Actions -> Validation -> Scenarios -> Result lineage."""
        decision_id = "DEC-0001"
        n_ctx = GraphNode(id="n-ctx", type="CONTEXT", decision_id=decision_id)
        n_act = GraphNode(id="n-act", type="ACTION", decision_id=decision_id)
        n_val = GraphNode(id="n-val", type="VALIDATION", decision_id=decision_id)
        n_scn = GraphNode(id="n-scn", type="SCENARIO", decision_id=decision_id)
        n_res = GraphNode(id="n-res", type="RESULT", decision_id=decision_id)
        n_ver = GraphNode(id="n-ver", type="DECISION_VERSION", decision_id=decision_id)

        edges = [
            GraphEdge(id="e1", source_id="n-ctx", target_id="n-act", relationship_type=GraphRelationshipType.GENERATES),
            GraphEdge(id="e2", source_id="n-act", target_id="n-val", relationship_type=GraphRelationshipType.VALIDATES),
            GraphEdge(id="e3", source_id="n-val", target_id="n-scn", relationship_type=GraphRelationshipType.SIMULATES),
            GraphEdge(id="e4", source_id="n-scn", target_id="n-res", relationship_type=GraphRelationshipType.PRODUCES),
            GraphEdge(id="e5", source_id="n-ver", target_id="n-ctx", relationship_type=GraphRelationshipType.REFERENCES),
        ]

        graph = DecisionGraph(
            id="GRA-0001",
            decision_id=decision_id,
            nodes=[n_ctx, n_act, n_val, n_scn, n_res, n_ver],
            edges=edges,
        )

        assert graph.id == "GRA-0001"
        assert graph.decision_id == decision_id
        assert len(graph.nodes) == 6
        assert len(graph.edges) == 5
        assert graph.get_node("n-ctx") is not None
        assert graph.get_edge("e1") is not None
        assert len(graph.outgoing_edges("n-ctx")) == 1
        assert len(graph.incoming_edges("n-act")) == 1

    def test_empty_graph_valid(self) -> None:
        """Verifies a DecisionGraph with zero initial nodes and edges is valid."""
        graph = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[], edges=[])
        assert graph.id == "GRA-0001"
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_duplicate_node_id_rejected(self) -> None:
        """Verifies duplicate node IDs within a graph raise DuplicateGraphNodeError."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="node-dup", type="CONTEXT", decision_id=decision_id)
        n2 = GraphNode(id="node-dup", type="ACTION", decision_id=decision_id)

        with pytest.raises(DuplicateGraphNodeError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1, n2], edges=[])
        assert "Duplicate node ID 'node-dup'" in str(exc_info.value)

    def test_duplicate_edge_id_rejected(self) -> None:
        """Verifies duplicate edge IDs within a graph raise DuplicateGraphEdgeError."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id)
        n2 = GraphNode(id="n2", type="ACTION", decision_id=decision_id)
        n3 = GraphNode(id="n3", type="ACTION", decision_id=decision_id)

        e1 = GraphEdge(id="edg-dup", source_id="n1", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)
        e2 = GraphEdge(id="edg-dup", source_id="n1", target_id="n3", relationship_type=GraphRelationshipType.GENERATES)

        with pytest.raises(DuplicateGraphEdgeError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1, n2, n3], edges=[e1, e2])
        assert "Duplicate edge ID 'edg-dup'" in str(exc_info.value)

    def test_duplicate_directed_edge_relationship_rejected(self) -> None:
        """Verifies identical source, target, and relationship_type raise DuplicateGraphEdgeError."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id)
        n2 = GraphNode(id="n2", type="ACTION", decision_id=decision_id)

        e1 = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)
        e2 = GraphEdge(id="e2", source_id="n1", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)

        with pytest.raises(DuplicateGraphEdgeError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1, n2], edges=[e1, e2])
        assert "Duplicate directed edge" in str(exc_info.value)

    def test_unknown_edge_source_rejected(self) -> None:
        """Verifies edge referencing an unknown source node ID raises InvalidEdgeReferenceError."""
        decision_id = "DEC-0001"
        n2 = GraphNode(id="n2", type="ACTION", decision_id=decision_id)
        edge = GraphEdge(id="e1", source_id="non-existent", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)

        with pytest.raises(InvalidEdgeReferenceError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n2], edges=[edge])
        assert "unknown source node 'non-existent'" in str(exc_info.value)

    def test_unknown_edge_target_rejected(self) -> None:
        """Verifies edge referencing an unknown target node ID raises InvalidEdgeReferenceError."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id)
        edge = GraphEdge(id="e1", source_id="n1", target_id="non-existent", relationship_type=GraphRelationshipType.GENERATES)

        with pytest.raises(InvalidEdgeReferenceError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1], edges=[edge])
        assert "unknown target node 'non-existent'" in str(exc_info.value)

    def test_cross_decision_node_rejected(self) -> None:
        """Verifies a node with mismatched decision_id raises CrossDecisionGraphError."""
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id="DEC-OTHER")

        with pytest.raises(CrossDecisionGraphError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[n1], edges=[])
        assert "does not match graph decision_id" in str(exc_info.value)

    def test_cross_decision_edge_rejected(self) -> None:
        """Verifies an edge with mismatched decision_id raises CrossDecisionGraphError."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id)
        n2 = GraphNode(id="n2", type="ACTION", decision_id=decision_id)
        edge = GraphEdge(
            id="e1",
            source_id="n1",
            target_id="n2",
            relationship_type=GraphRelationshipType.GENERATES,
            decision_id="DEC-OTHER",
        )

        with pytest.raises(CrossDecisionGraphError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1, n2], edges=[edge])
        assert "does not match graph decision_id" in str(exc_info.value)

    def test_disallowed_relationship_rejected(self) -> None:
        """Verifies relationship type not permitted between source and target node types raises InvalidGraphRelationshipError."""
        decision_id = "DEC-0001"
        # CONTEXT -> CONTEXT with GENERATES is not permitted
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id)
        n2 = GraphNode(id="n2", type="CONTEXT", decision_id=decision_id)
        edge = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)

        with pytest.raises(InvalidGraphRelationshipError) as exc_info:
            DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1, n2], edges=[edge])
        assert "Relationship 'GENERATES' is not permitted" in str(exc_info.value)

    def test_defensive_copies_returned_by_getters(self) -> None:
        """Verifies get_node and get_edge return defensive copies that cannot mutate stored graph state."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id, label="Original Label")
        graph = DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1], edges=[])

        retrieved = graph.get_node("n1")
        assert retrieved is not None
        retrieved.label = "Mutated Label"

        # Stored node remains untouched
        stored = graph.get_node("n1")
        assert stored is not None
        assert stored.label == "Original Label"

    def test_serialization_and_deserialization_roundtrip(self) -> None:
        """Verifies serialization to dict and JSON roundtrip preserves graph integrity."""
        decision_id = "DEC-0001"
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id=decision_id)
        n2 = GraphNode(id="n2", type="ACTION", decision_id=decision_id)
        e1 = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)

        graph = DecisionGraph(id="GRA-0001", decision_id=decision_id, nodes=[n1, n2], edges=[e1])
        dumped = graph.model_dump()
        reconstructed = DecisionGraph.model_validate(dumped)

        assert reconstructed.id == graph.id
        assert reconstructed.decision_id == graph.decision_id
        assert len(reconstructed.nodes) == 2
        assert len(reconstructed.edges) == 1
        assert reconstructed.nodes[0].node_type == GraphNodeType.CONTEXT
        assert reconstructed.edges[0].relationship_type == GraphRelationshipType.GENERATES
