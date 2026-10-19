from __future__ import annotations

import pytest

from app.data.generator import generate_shopflow_dataset
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_graph import GraphNodeType, GraphRelationshipType
from app.domain.validation import (
    ActionValidationStatus,
    ConstraintDefinition,
    ConstraintType,
    DecisionValidationStatus,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository
from app.validation.service import (
    CandidateActionNotFoundError,
    DecisionNotFoundError,
    ValidationService,
)


@pytest.fixture
def test_dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def decision_repo(test_dataset: ShopFlowDataset) -> DecisionRepository:
    return DecisionRepository(dataset=test_dataset)


@pytest.fixture
def action_repo() -> CandidateActionRepository:
    return CandidateActionRepository()


@pytest.fixture
def inventory_repo(test_dataset: ShopFlowDataset) -> InventoryRepository:
    return InventoryRepository(dataset=test_dataset)


@pytest.fixture
def supplier_repo(test_dataset: ShopFlowDataset) -> SupplierRepository:
    return SupplierRepository(dataset=test_dataset)


@pytest.fixture
def graph_repo() -> DecisionGraphRepository:
    return DecisionGraphRepository()


@pytest.fixture
def validation_repo() -> ValidationRepository:
    return ValidationRepository()


@pytest.fixture
def validation_service(
    decision_repo: DecisionRepository,
    action_repo: CandidateActionRepository,
    inventory_repo: InventoryRepository,
    supplier_repo: SupplierRepository,
    validation_repo: ValidationRepository,
    graph_repo: DecisionGraphRepository,
    test_dataset: ShopFlowDataset,
) -> ValidationService:
    return ValidationService(
        decision_repo=decision_repo,
        action_repo=action_repo,
        inventory_repo=inventory_repo,
        supplier_repo=supplier_repo,
        validation_repo=validation_repo,
        graph_repo=graph_repo,
        dataset=test_dataset,
    )


class TestValidationService:
    """Tests ValidationService orchestration, constraint checking, and graph integration."""

    def test_validate_unknown_decision_raises_404(self, validation_service: ValidationService):
        with pytest.raises(DecisionNotFoundError, match="Decision 'DEC-UNKNOWN' not found"):
            validation_service.validate_decision_actions("DEC-UNKNOWN")

    def test_validate_unknown_action_raises_404(self, validation_service: ValidationService, decision_repo: DecisionRepository):
        dec = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
        with pytest.raises(CandidateActionNotFoundError, match="not found for decision"):
            validation_service.validate_action(dec.id, "ACT-UNKNOWN")

    def test_validate_single_action(
        self,
        validation_service: ValidationService,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
    ):
        dec = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
        action = action_repo.record(
            CandidateAction(
                id="ACT-0001",
                decision_id=dec.id,
                type=ActionType.PLACE_ORDER,
                parameters=PlaceOrderParameters(quantity=25),
            )
        )
        result = validation_service.validate_action(dec.id, action.id)
        assert result.action_id == action.id
        assert result.status == ActionValidationStatus.SATISFIED
        assert result.is_valid is True
        assert result.constraints_passed == 5

    def test_validate_decision_actions_default_constraints(
        self,
        validation_service: ValidationService,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
    ):
        dec = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
        # Action 1: DO_NOTHING (valid)
        act1 = action_repo.record(
            CandidateAction(
                id="ACT-0001",
                decision_id=dec.id,
                type=ActionType.DO_NOTHING,
                parameters=DoNothingParameters(),
            )
        )
        # Action 2: PLACE_ORDER small (valid)
        act2 = action_repo.record(
            CandidateAction(
                id="ACT-0002",
                decision_id=dec.id,
                type=ActionType.PLACE_ORDER,
                parameters=PlaceOrderParameters(quantity=30),
            )
        )
        # Action 3: PLACE_ORDER massive exceeding warehouse capacity 10000 (invalid)
        act3 = action_repo.record(
            CandidateAction(
                id="ACT-0003",
                decision_id=dec.id,
                type=ActionType.PLACE_ORDER,
                parameters=PlaceOrderParameters(quantity=999999),
            )
        )

        report = validation_service.validate_decision_actions(dec.id)
        assert report.id == "VAL-0001"
        assert report.decision_id == dec.id
        assert report.status == DecisionValidationStatus.SOME_VIOLATED
        assert report.total_actions_evaluated == 3
        assert act1.id in report.valid_action_ids
        assert act2.id in report.valid_action_ids
        assert act3.id in report.invalid_action_ids

        # Verify persisted in repository
        latest = validation_service.get_latest_validation(dec.id)
        assert latest is not None
        assert latest.id == "VAL-0001"

    def test_validate_with_custom_constraints(
        self,
        validation_service: ValidationService,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
    ):
        dec = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
        act = action_repo.record(
            CandidateAction(
                id="ACT-0001",
                decision_id=dec.id,
                type=ActionType.PLACE_ORDER,
                parameters=PlaceOrderParameters(quantity=100),
            )
        )
        # Custom tight budget constraint: max $500 (unit cost is ~65 -> 100 * 65 = 6500 > 500)
        custom_constraints = [
            ConstraintDefinition(
                constraint_type=ConstraintType.MAX_BUDGET_LIMIT,
                name="tight_budget",
                description="Strict spending cap",
                parameters={"max_spend": 500.0},
            )
        ]
        report = validation_service.validate_decision_actions(
            dec.id,
            configured_constraints=custom_constraints,
        )
        assert report.status == DecisionValidationStatus.ALL_VIOLATED
        assert act.id in report.invalid_action_ids
        assert report.action_results[0].status == ActionValidationStatus.VIOLATED

    def test_record_to_graph_integration(
        self,
        validation_service: ValidationService,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
        graph_repo: DecisionGraphRepository,
    ):
        dec = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
        # Build baseline graph
        graph = graph_repo.build_default_graph(dec)

        # Create action and attach action node
        act = action_repo.record(
            CandidateAction(
                id="ACT-0001",
                decision_id=dec.id,
                type=ActionType.PLACE_ORDER,
                parameters=PlaceOrderParameters(quantity=20),
            )
        )
        # Attach action node manually
        graph_repo.attach_action_node(dec.id, act)

        # Validate with record_to_graph=True
        report = validation_service.validate_decision_actions(
            dec.id,
            record_to_graph=True,
        )

        updated_graph = graph_repo.get_by_decision_id(dec.id)
        assert updated_graph is not None

        # Check for VALIDATION node
        val_nodes = [n for n in updated_graph.nodes if n.node_type == GraphNodeType.VALIDATION]
        assert len(val_nodes) == 1
        assert val_nodes[0].metadata["validation_id"] == report.id

        # Check for VALIDATES edge: action_node -> val_node
        val_edges = [
            e for e in updated_graph.edges
            if e.relationship_type == GraphRelationshipType.VALIDATES
        ]
        assert len(val_edges) == 1
        assert val_edges[0].target_id == val_nodes[0].id
