from unittest.mock import patch
import pytest

from app.candidate_actions.service import CandidateActionService
from app.domain.candidate_action import ActionType, CandidateAction, PlaceOrderParameters
from app.domain.decision import Decision
from app.domain.decision_graph import (
    ALLOWED_RELATIONSHIPS,
    DecisionGraph,
    GraphEdge,
    GraphIntegrityError,
    GraphNode,
    GraphNodeType,
    GraphRelationshipType,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository


@pytest.fixture
def clean_environment():
    """Provides a fresh set of repositories and service for testing graph integration."""
    decision_repo = DecisionRepository()
    action_repo = CandidateActionRepository()
    graph_repo = DecisionGraphRepository()
    service = CandidateActionService(
        decision_repository=decision_repo,
        action_repository=action_repo,
        graph_repository=graph_repo,
    )
    return decision_repo, action_repo, graph_repo, service


def test_action_node_type_and_allowed_relationships():
    """Verifies that GraphNodeType.ACTION conforms to the ALLOWED_RELATIONSHIPS matrix."""
    # CONTEXT -> ACTION with GENERATES
    generates_pairs = ALLOWED_RELATIONSHIPS[GraphRelationshipType.GENERATES]
    assert (GraphNodeType.CONTEXT, GraphNodeType.ACTION) in generates_pairs

    # ACTION -> CONTEXT with DEPENDS_ON and DERIVED_FROM
    assert (GraphNodeType.ACTION, GraphNodeType.CONTEXT) in ALLOWED_RELATIONSHIPS[GraphRelationshipType.DEPENDS_ON]
    assert (GraphNodeType.ACTION, GraphNodeType.CONTEXT) in ALLOWED_RELATIONSHIPS[GraphRelationshipType.DERIVED_FROM]

    # ACTION <-> DECISION_VERSION with REFERENCES
    assert (GraphNodeType.DECISION_VERSION, GraphNodeType.ACTION) in ALLOWED_RELATIONSHIPS[GraphRelationshipType.REFERENCES]
    assert (GraphNodeType.ACTION, GraphNodeType.DECISION_VERSION) in ALLOWED_RELATIONSHIPS[GraphRelationshipType.REFERENCES]


def test_action_attachment_to_existing_decision_graph(clean_environment):
    """Verifies that creating an action attaches an ACTION node and GENERATES edge to an existing graph."""
    decision_repo, action_repo, graph_repo, service = clean_environment

    # 1. Create decision
    decision = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")

    # 2. Build default decision graph (has CONTEXT node)
    initial_graph = graph_repo.build_default_graph(decision)
    assert len(initial_graph.nodes) == 1
    assert initial_graph.nodes[0].node_type == GraphNodeType.CONTEXT
    assert len(initial_graph.edges) == 0

    # 3. Create candidate action via service
    action = service.create_candidate_action(
        decision_id=decision.id,
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 100},
        description="Replenish stock",
    )

    # 4. Verify graph now contains the ACTION node and GENERATES edge
    updated_graph = graph_repo.get_by_decision_id(decision.id)
    assert updated_graph is not None
    assert len(updated_graph.nodes) == 2
    assert len(updated_graph.edges) == 1

    action_node = next(n for n in updated_graph.nodes if n.node_type == GraphNodeType.ACTION)
    assert action_node.id == f"{decision.id}-node-{action.id}"
    assert action_node.metadata["action_id"] == action.id
    assert action_node.metadata["action_type"] == "PLACE_ORDER"
    assert action_node.metadata["parameters"] == {"quantity": 100}

    edge = updated_graph.edges[0]
    assert edge.relationship_type == GraphRelationshipType.GENERATES
    assert edge.source_id == initial_graph.nodes[0].id
    assert edge.target_id == action_node.id


def test_action_creation_without_graph_succeeds(clean_environment):
    """Verifies that candidate actions can be stored even if no graph has been created yet."""
    decision_repo, action_repo, graph_repo, service = clean_environment

    decision = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert graph_repo.get_by_decision_id(decision.id) is None

    action = service.create_candidate_action(
        decision_id=decision.id,
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    assert action.id.startswith("ACT-")
    assert len(action_repo.list_by_decision_id(decision.id)) == 1
    assert graph_repo.get_by_decision_id(decision.id) is None


def test_invalid_action_creation_leaves_no_orphaned_nodes(clean_environment):
    """Verifies that failed action validation leaves zero orphaned actions or nodes."""
    decision_repo, action_repo, graph_repo, service = clean_environment

    decision = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
    graph_repo.build_default_graph(decision)

    # Attempt action creation with invalid parameters (negative quantity)
    with pytest.raises(Exception):
        service.create_candidate_action(
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters={"quantity": -50},
        )

    # Action repository must remain empty
    assert len(action_repo.list_by_decision_id(decision.id)) == 0

    # Graph must retain only its initial CONTEXT node
    graph = graph_repo.get_by_decision_id(decision.id)
    assert graph is not None
    assert len(graph.nodes) == 1
    assert graph.nodes[0].node_type == GraphNodeType.CONTEXT
    assert len(graph.edges) == 0


def test_graph_failure_rolls_back_candidate_action_storage(clean_environment):
    """Verifies that a failure during graph update triggers rollback in candidate action storage."""
    decision_repo, action_repo, graph_repo, service = clean_environment

    decision = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
    graph_repo.build_default_graph(decision)

    # Mock attach_action_node to simulate an unexpected graph integrity failure
    with patch.object(graph_repo, "attach_action_node", side_effect=GraphIntegrityError("Simulated graph error")):
        with pytest.raises(GraphIntegrityError):
            service.create_candidate_action(
                decision_id=decision.id,
                action_type=ActionType.DO_NOTHING,
                parameters={},
            )

    # Action must be rolled back from repository
    assert len(action_repo.list_by_decision_id(decision.id)) == 0


def test_decision_events_and_versions_unaffected_by_actions(clean_environment):
    """Verifies that creating candidate actions does not alter decision event history or version snapshots."""
    decision_repo, action_repo, graph_repo, service = clean_environment

    decision = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
    initial_events_count = len(decision_repo.event_repository.get_by_decision_id(decision.id))
    initial_versions_count = len(decision_repo.version_repository.get_by_decision_id(decision.id))

    # Add candidate actions
    service.create_candidate_action(
        decision_id=decision.id,
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    service.create_candidate_action(
        decision_id=decision.id,
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 100},
    )

    # Audit events and versions must remain completely untouched
    assert len(decision_repo.event_repository.get_by_decision_id(decision.id)) == initial_events_count
    assert len(decision_repo.version_repository.get_by_decision_id(decision.id)) == initial_versions_count
