import pytest

from app.candidate_actions.service import (
    CandidateActionService,
    DecisionNotFoundError,
)
from app.data.generator import generate_shopflow_dataset
from app.domain.candidate_action import ActionType, PlaceOrderParameters
from app.domain.replenishment import (
    ReplenishmentBreakdown,
    ReplenishmentCalculationInputs,
    ReplenishmentCalculationResult,
    ReplenishmentPolicyType,
    calculate_replenishment_quantity,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.supplier_repository import SupplierRepository


@pytest.fixture
def setup_services():
    dataset = generate_shopflow_dataset(seed=42)
    decision_repo = DecisionRepository(dataset=dataset)
    action_repo = CandidateActionRepository()
    graph_repo = DecisionGraphRepository()
    supplier_repo = SupplierRepository(dataset=dataset)
    action_service = CandidateActionService(
        decision_repository=decision_repo,
        action_repository=action_repo,
        graph_repository=graph_repo,
        supplier_repository=supplier_repo,
    )
    decision = decision_repo.create(product_id="prod-001", warehouse_id="wh-001")
    return {
        "action_service": action_service,
        "decision_repo": decision_repo,
        "decision": decision,
    }


class TestCandidateActionReplenishmentIntegration:
    """Tests seamless decoupling and integration between replenishment calculation and candidate actions."""

    def test_create_replenishment_candidate_action(self, setup_services):
        action_service = setup_services["action_service"]
        decision = setup_services["decision"]

        # Run pure calculation
        calc_inputs = ReplenishmentCalculationInputs(
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            available_quantity=20,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        calc_result = calculate_replenishment_quantity(calc_inputs)
        assert calc_result.replenishment_quantity == 30

        # Create action explicitly from calculation result
        action = action_service.create_replenishment_candidate_action(
            decision_id=decision.id,
            calculation_result=calc_result,
        )

        assert action.action_type == ActionType.PLACE_ORDER
        assert isinstance(action.parameters, PlaceOrderParameters)
        assert action.parameters.quantity == 30
        assert action.metadata["source"] == "replenishment_calculation"
        assert action.metadata["policy_type"] == "REORDER_POINT_DEFICIT"
        assert "30" in action.description

    def test_rejects_zero_quantity_replenishment_action(self, setup_services):
        action_service = setup_services["action_service"]
        decision = setup_services["decision"]

        # Inventory at reorder point -> quantity = 0
        calc_inputs = ReplenishmentCalculationInputs(
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            available_quantity=50,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        calc_result = calculate_replenishment_quantity(calc_inputs)
        assert calc_result.replenishment_quantity == 0

        with pytest.raises(ValueError, match="non-positive replenishment quantity"):
            action_service.create_replenishment_candidate_action(
                decision_id=decision.id,
                calculation_result=calc_result,
            )

    def test_calculation_alone_does_not_mutate_candidate_actions(self, setup_services):
        action_service = setup_services["action_service"]
        decision = setup_services["decision"]

        initial_actions = action_service.list_candidate_actions(decision.id)
        assert len(initial_actions) == 0

        # Run calculation
        calc_inputs = ReplenishmentCalculationInputs(
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            available_quantity=10,
            reorder_point=50,
        )
        _ = calculate_replenishment_quantity(calc_inputs)

        # Candidate actions must remain untouched
        actions_after = action_service.list_candidate_actions(decision.id)
        assert len(actions_after) == 0
