from __future__ import annotations

import pytest

from app.data.generator import generate_shopflow_dataset
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SupplierNotFoundError,
    SwitchSupplierParameters,
)
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_graph import GraphNodeType, GraphRelationshipType
from app.domain.replenishment import ReplenishmentPolicyType
from app.evaluation.service import (
    ActionEvaluationService,
    CandidateActionNotFoundError,
    DecisionNotFoundError,
    MissingEvaluationDataError,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


@pytest.fixture
def dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def service_bundle(dataset):
    dec_repo = DecisionRepository(dataset=dataset)
    action_repo = CandidateActionRepository()
    inv_repo = InventoryRepository(dataset=dataset)
    demand_repo = DemandRepository(dataset=dataset)
    sup_repo = SupplierRepository(dataset=dataset)
    graph_repo = DecisionGraphRepository()

    service = ActionEvaluationService(
        decision_repo=dec_repo,
        action_repo=action_repo,
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=sup_repo,
        graph_repo=graph_repo,
        dataset=dataset,
    )
    return {
        "service": service,
        "dec_repo": dec_repo,
        "action_repo": action_repo,
        "inv_repo": inv_repo,
        "graph_repo": graph_repo,
    }


def test_evaluate_action_lifecycle_and_mutation_isolation(service_bundle) -> None:
    """Verifies evaluation does NOT mutate decision status, inventory, or action state."""
    service: ActionEvaluationService = service_bundle["service"]
    dec_repo: DecisionRepository = service_bundle["dec_repo"]
    action_repo: CandidateActionRepository = service_bundle["action_repo"]
    inv_repo: InventoryRepository = service_bundle["inv_repo"]

    # Create baseline decision and action
    dec = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert dec.status == DecisionStatus.DRAFT

    action = CandidateAction(
        id="ACT-ISO-1",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=25),
    )
    action_repo.record(action)

    inv_before = inv_repo.get_by_product_and_warehouse("prod-001", "wh-001")
    assert inv_before is not None
    qty_before = inv_before.quantity_on_hand

    # Execute evaluation
    result = service.evaluate_action(decision_id=dec.id, action_id=action.id)

    # 1. Decision lifecycle state must remain untouched
    dec_after = dec_repo.get_by_id(dec.id)
    assert dec_after is not None
    assert dec_after.status == DecisionStatus.DRAFT

    # 2. Inventory record must remain untouched
    inv_after = inv_repo.get_by_product_and_warehouse("prod-001", "wh-001")
    assert inv_after is not None
    assert inv_after.quantity_on_hand == qty_before

    # 3. Candidate action in repository must remain untouched
    action_after = action_repo.get_by_id(action.id)
    assert action_after is not None
    assert action_after.parameters.quantity == 25

    # 4. Evaluation result is valid
    assert result.action_id == action.id
    assert result.cost_impact.direct_procurement_cost is not None


def test_evaluate_decision_actions_collection(service_bundle) -> None:
    """Evaluates all candidate actions associated with a decision."""
    service: ActionEvaluationService = service_bundle["service"]
    dec_repo: DecisionRepository = service_bundle["dec_repo"]
    action_repo: CandidateActionRepository = service_bundle["action_repo"]

    dec = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

    # Add 3 candidate actions
    a1 = CandidateAction(
        id="ACT-DEC-1",
        decision_id=dec.id,
        action_type=ActionType.DO_NOTHING,
        parameters=DoNothingParameters(),
    )
    a2 = CandidateAction(
        id="ACT-DEC-2",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=30),
    )
    a3 = CandidateAction(
        id="ACT-DEC-3",
        decision_id=dec.id,
        action_type=ActionType.SWITCH_SUPPLIER,
        parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
    )
    action_repo.record(a1)
    action_repo.record(a2)
    action_repo.record(a3)

    report = service.evaluate_decision_actions(dec.id)

    assert report.decision_id == dec.id
    assert report.product_id == "prod-001"
    assert report.warehouse_id == "wh-001"
    assert report.total_actions_evaluated == 3
    assert len(report.evaluations) == 3

    types = [e.action_type for e in report.evaluations]
    assert ActionType.DO_NOTHING in types
    assert ActionType.PLACE_ORDER in types
    assert ActionType.SWITCH_SUPPLIER in types

    # Confirmation that recommendation selection remains Day 20
    for e in report.evaluations:
        assert e.overall_score is None
        assert e.scoring_status == "UNRESOLVED_MULTI_CRITERIA_DECISION"


def test_evaluate_action_with_graph_integration(service_bundle) -> None:
    """Tests optional graph attachment: attaches RESULT node with PRODUCES edge from ACTION."""
    service: ActionEvaluationService = service_bundle["service"]
    dec_repo: DecisionRepository = service_bundle["dec_repo"]
    action_repo: CandidateActionRepository = service_bundle["action_repo"]
    graph_repo: DecisionGraphRepository = service_bundle["graph_repo"]

    dec = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
    graph = graph_repo.build_default_graph(dec)

    action = CandidateAction(
        id="ACT-GRAPH-1",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=20),
    )
    action_repo.record(action)
    graph_repo.attach_action_node(dec.id, action)

    # Evaluate with record_to_graph=True
    service.evaluate_action(
        decision_id=dec.id,
        action_id=action.id,
        record_to_graph=True,
    )

    updated_graph = graph_repo.get_by_decision_id(dec.id)
    assert updated_graph is not None

    # Check RESULT node exists
    result_node = next(
        (n for n in updated_graph.nodes if n.node_type == GraphNodeType.RESULT),
        None,
    )
    assert result_node is not None
    assert result_node.id == f"{dec.id}-node-eval-{action.id}"

    # Check PRODUCES edge from ACTION to RESULT
    produces_edge = next(
        (e for e in updated_graph.edges if e.relationship_type == GraphRelationshipType.PRODUCES),
        None,
    )
    assert produces_edge is not None
    assert produces_edge.source_id == f"{dec.id}-node-{action.id}"
    assert produces_edge.target_id == result_node.id


def test_evaluate_action_unknown_decision(service_bundle) -> None:
    """Raises DecisionNotFoundError for non-existent decision."""
    service: ActionEvaluationService = service_bundle["service"]
    with pytest.raises(DecisionNotFoundError):
        service.evaluate_action(decision_id="DEC-NONEXISTENT", action_id="ACT-001")


def test_evaluate_action_unknown_action(service_bundle) -> None:
    """Raises CandidateActionNotFoundError for non-existent action."""
    service: ActionEvaluationService = service_bundle["service"]
    dec_repo: DecisionRepository = service_bundle["dec_repo"]
    dec = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

    with pytest.raises(CandidateActionNotFoundError):
        service.evaluate_action(decision_id=dec.id, action_id="ACT-NONEXISTENT")


def test_evaluate_action_cross_decision_isolation(service_bundle) -> None:
    """Cannot evaluate an action belonging to a different decision."""
    service: ActionEvaluationService = service_bundle["service"]
    dec_repo: DecisionRepository = service_bundle["dec_repo"]
    action_repo: CandidateActionRepository = service_bundle["action_repo"]

    dec1 = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
    dec2 = dec_repo.create(product_id="prod-002", warehouse_id="wh-001")

    action = CandidateAction(
        id="ACT-DEC1",
        decision_id=dec1.id,
        action_type=ActionType.DO_NOTHING,
        parameters=DoNothingParameters(),
    )
    action_repo.record(action)

    # Attempting to access via dec2 must raise CandidateActionNotFoundError
    with pytest.raises(CandidateActionNotFoundError):
        service.evaluate_action(decision_id=dec2.id, action_id=action.id)
