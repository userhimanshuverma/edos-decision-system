from __future__ import annotations

import pytest

from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_graph import (
    CrossDecisionGraphError,
    DecisionGraph,
    DuplicateGraphNodeError,
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphRelationshipType,
    InvalidEdgeReferenceError,
)
from app.repositories.decision_graph_repository import (
    DecisionGraphRepository,
    DuplicateDecisionGraphError,
)
from app.repositories.decision_repository import DecisionRepository


class TestDecisionGraphRepository:
    """Unit test suite for DecisionGraphRepository in-memory data access and operations."""

    def test_repository_initialization_and_len(self) -> None:
        """Verifies repository starts empty and has length 0 and is truthy."""
        repo = DecisionGraphRepository()
        assert len(repo) == 0
        assert bool(repo) is True
        assert repo.list_all() == []

    def test_generate_id_sequence(self) -> None:
        """Verifies stable sequential identifier generation in format GRA-XXXX."""
        repo = DecisionGraphRepository()
        id1 = repo.generate_id()
        id2 = repo.generate_id()
        assert id1 == "GRA-0001"
        assert id2 == "GRA-0002"

    def test_generate_node_and_edge_ids(self) -> None:
        """Verifies helper methods generate predictable node and edge IDs."""
        repo = DecisionGraphRepository()
        assert repo.generate_node_id() == "NOD-0001"
        assert repo.generate_node_id() == "NOD-0002"
        assert repo.generate_edge_id() == "EDG-0001"
        assert repo.generate_edge_id() == "EDG-0002"

    def test_record_and_get_by_id_and_decision_id(self) -> None:
        """Verifies storing a graph and retrieving it by graph ID and by decision ID."""
        repo = DecisionGraphRepository()
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id="DEC-0001")
        graph = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[n1], edges=[])

        stored = repo.record(graph)
        assert stored.id == "GRA-0001"
        assert stored.decision_id == "DEC-0001"

        by_id = repo.get_by_id("GRA-0001")
        assert by_id is not None
        assert by_id.id == "GRA-0001"
        assert len(by_id.nodes) == 1

        by_dec = repo.get_by_decision_id("DEC-0001")
        assert by_dec is not None
        assert by_dec.id == "GRA-0001"

    def test_unknown_id_and_decision_id_return_none(self) -> None:
        """Verifies non-existent IDs return None without raising errors."""
        repo = DecisionGraphRepository()
        assert repo.get_by_id("GRA-9999") is None
        assert repo.get_by_decision_id("DEC-9999") is None

    def test_create_graph_helper(self) -> None:
        """Verifies create_graph constructs and stores a graph automatically generating an ID."""
        repo = DecisionGraphRepository()
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id="DEC-0001")
        n2 = GraphNode(id="n2", type="ACTION", decision_id="DEC-0001")
        e1 = GraphEdge(id="e1", source_id="n1", target_id="n2", relationship_type=GraphRelationshipType.GENERATES)

        graph = repo.create_graph(decision_id="DEC-0001", nodes=[n1, n2], edges=[e1])
        assert graph.id == "GRA-0001"
        assert graph.decision_id == "DEC-0001"
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_build_default_graph(self) -> None:
        """Verifies build_default_graph creates baseline graph with CONTEXT node."""
        repo = DecisionGraphRepository()
        decision = Decision(
            id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            status=DecisionStatus.DRAFT,
        )

        graph = repo.build_default_graph(decision)
        assert graph.id == "GRA-0001"
        assert graph.decision_id == "DEC-0001"
        assert len(graph.nodes) == 1
        assert graph.nodes[0].node_type == GraphNodeType.CONTEXT
        assert graph.nodes[0].metadata["product_id"] == "prod-001"
        assert graph.nodes[0].metadata["warehouse_id"] == "wh-001"
        assert len(graph.edges) == 0

    def test_duplicate_graph_id_rejected(self) -> None:
        """Verifies recording a graph with an existing graph ID raises DuplicateDecisionGraphError."""
        repo = DecisionGraphRepository()
        g1 = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[], edges=[])
        g2 = DecisionGraph(id="GRA-0001", decision_id="DEC-0002", nodes=[], edges=[])

        repo.record(g1)
        with pytest.raises(DuplicateDecisionGraphError) as exc_info:
            repo.record(g2)
        assert "already exists" in str(exc_info.value)

    def test_duplicate_decision_id_rejected(self) -> None:
        """Verifies recording a second graph for the same decision ID raises DuplicateDecisionGraphError."""
        repo = DecisionGraphRepository()
        g1 = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[], edges=[])
        g2 = DecisionGraph(id="GRA-0002", decision_id="DEC-0001", nodes=[], edges=[])

        repo.record(g1)
        with pytest.raises(DuplicateDecisionGraphError) as exc_info:
            repo.record(g2)
        assert "already exists" in str(exc_info.value)

    def test_invalid_graph_does_not_corrupt_store(self) -> None:
        """Verifies that an invalid graph failing domain validation does not corrupt store state."""
        repo = DecisionGraphRepository()
        # Edge references unknown node
        with pytest.raises(InvalidEdgeReferenceError):
            repo.create_graph(
                decision_id="DEC-0001",
                nodes=[],
                edges=[GraphEdge(id="e1", source_id="bad", target_id="bad2", relationship_type=GraphRelationshipType.GENERATES)],
            )
        assert len(repo) == 0
        assert repo.get_by_decision_id("DEC-0001") is None

    def test_defensive_copies_on_write(self) -> None:
        """Verifies mutations to input object after record() do not affect stored repository state."""
        repo = DecisionGraphRepository()
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id="DEC-0001")
        nodes_list = [n1]
        graph = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=nodes_list, edges=[])

        repo.record(graph)

        # Mutate the original node
        n1.label = "Externally mutated"

        stored = repo.get_by_id("GRA-0001")
        assert stored is not None
        assert stored.nodes[0].label is None

    def test_defensive_copies_on_read(self) -> None:
        """Verifies mutations to returned graph do not affect stored repository state."""
        repo = DecisionGraphRepository()
        n1 = GraphNode(id="n1", type="CONTEXT", decision_id="DEC-0001")
        graph = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[n1], edges=[])
        repo.record(graph)

        read_graph = repo.get_by_id("GRA-0001")
        assert read_graph is not None
        read_graph.nodes.clear()

        # Check repository store again
        fresh_read = repo.get_by_id("GRA-0001")
        assert fresh_read is not None
        assert len(fresh_read.nodes) == 1

    def test_deterministic_ordering_in_list_all(self) -> None:
        """Verifies list_all sorts records primarily by decision_id and secondarily by graph id."""
        repo = DecisionGraphRepository()
        g3 = DecisionGraph(id="GRA-0003", decision_id="DEC-0003", nodes=[], edges=[])
        g1 = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[], edges=[])
        g2 = DecisionGraph(id="GRA-0002", decision_id="DEC-0002", nodes=[], edges=[])

        repo.record(g3)
        repo.record(g1)
        repo.record(g2)

        ordered = repo.list_all()
        assert [g.decision_id for g in ordered] == ["DEC-0001", "DEC-0002", "DEC-0003"]

    def test_remove_helper(self) -> None:
        """Verifies remove deletes graph and cleans decision index."""
        repo = DecisionGraphRepository()
        g1 = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[], edges=[])
        repo.record(g1)

        assert repo.remove("GRA-0001") is True
        assert repo.get_by_id("GRA-0001") is None
        assert repo.get_by_decision_id("DEC-0001") is None
        assert len(repo) == 0
        assert repo.remove("GRA-0001") is False

    def test_clear_resets_store_and_counters(self) -> None:
        """Verifies clear resets store and resets sequence counters for test isolation."""
        repo = DecisionGraphRepository()
        g1 = DecisionGraph(id="GRA-0001", decision_id="DEC-0001", nodes=[], edges=[])
        repo.record(g1)
        assert len(repo) == 1

        repo.clear()
        assert len(repo) == 0
        assert repo.generate_id() == "GRA-0001"
        assert repo.generate_node_id() == "NOD-0001"
        assert repo.generate_edge_id() == "EDG-0001"

    def test_integration_with_decision_repository(self) -> None:
        """Verifies DecisionRepository exposes graph_repository and clear() resets it."""
        dec_repo = DecisionRepository()
        assert isinstance(dec_repo.graph_repository, DecisionGraphRepository)

        # Store a graph via graph_repository
        dec_repo.graph_repository.create_graph(decision_id="DEC-0001")
        assert len(dec_repo.graph_repository) == 1

        # Clearing dec_repo clears graph_repository too
        dec_repo.clear()
        assert len(dec_repo.graph_repository) == 0
