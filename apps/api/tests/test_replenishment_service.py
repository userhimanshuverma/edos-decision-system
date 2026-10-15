import pytest

from app.data.generator import generate_shopflow_dataset
from app.domain.replenishment import (
    ReplenishmentPolicyType,
)
from app.replenishment.service import (
    DecisionNotFoundError,
    MissingReplenishmentDataError,
    ProductNotFoundError,
    ReplenishmentService,
    WarehouseNotFoundError,
)
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


@pytest.fixture
def shared_dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def replenishment_service(shared_dataset):
    inv_repo = InventoryRepository(dataset=shared_dataset)
    demand_repo = DemandRepository(dataset=shared_dataset)
    supplier_repo = SupplierRepository(dataset=shared_dataset)
    decision_repo = DecisionRepository(dataset=shared_dataset)
    return ReplenishmentService(
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=supplier_repo,
        decision_repo=decision_repo,
    )


class TestReplenishmentService:
    """Tests the ReplenishmentService orchestration and repository integration."""

    def test_calculate_reorder_point_deficit(self, replenishment_service):
        result = replenishment_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )

        assert result.product_id == "prod-001"
        assert result.warehouse_id == "wh-001"
        assert result.policy_type == ReplenishmentPolicyType.REORDER_POINT_DEFICIT
        assert result.replenishment_quantity >= 0
        assert result.target_stock > 0

    def test_calculate_lead_time_demand(self, replenishment_service):
        result = replenishment_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
        )

        assert result.policy_type == ReplenishmentPolicyType.LEAD_TIME_DEMAND
        assert result.breakdown.lead_time_days is not None
        assert result.breakdown.lead_time_days > 0
        assert result.breakdown.average_daily_demand is not None
        assert result.breakdown.lead_time_demand is not None
        assert result.target_stock >= result.breakdown.reorder_point

    def test_calculate_target_stock_policy(self, replenishment_service):
        result = replenishment_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
            policy_type=ReplenishmentPolicyType.TARGET_STOCK,
            target_stock=250,
        )

        assert result.policy_type == ReplenishmentPolicyType.TARGET_STOCK
        assert result.target_stock == 250

    def test_calculate_for_decision(self, replenishment_service):
        # Create a decision in repository
        decision = replenishment_service.decision_repository.create(
            product_id="prod-002",
            warehouse_id="wh-001",
        )

        result = replenishment_service.calculate_for_decision(
            decision_id=decision.id,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )

        assert result.product_id == "prod-002"
        assert result.warehouse_id == "wh-001"

    def test_unknown_product_raises_404_domain_error(self, replenishment_service):
        with pytest.raises(ProductNotFoundError, match="Product 'prod-999' not found"):
            replenishment_service.calculate_for_product_warehouse(
                product_id="prod-999",
                warehouse_id="wh-001",
            )

    def test_unknown_warehouse_raises_404_domain_error(self, replenishment_service):
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 'wh-999' not found"):
            replenishment_service.calculate_for_product_warehouse(
                product_id="prod-001",
                warehouse_id="wh-999",
            )

    def test_unknown_decision_raises_not_found(self, replenishment_service):
        with pytest.raises(DecisionNotFoundError, match="Decision 'dec-nonexistent' not found"):
            replenishment_service.calculate_for_decision(
                decision_id="dec-nonexistent",
            )

    def test_missing_supplier_override_raises_missing_data(self, replenishment_service):
        with pytest.raises(MissingReplenishmentDataError, match="Specified supplier 'sup-999' not found"):
            replenishment_service.calculate_for_product_warehouse(
                product_id="prod-001",
                warehouse_id="wh-001",
                policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
                supplier_id="sup-999",
            )

    def test_no_mutation_of_inventory_or_decisions(self, replenishment_service):
        initial_inv = [i.model_dump() for i in replenishment_service.inventory_repository.list_all()]
        initial_decisions = len(replenishment_service.decision_repository.list_all())

        # Perform multiple calculations
        replenishment_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        replenishment_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
        )

        after_inv = [i.model_dump() for i in replenishment_service.inventory_repository.list_all()]
        after_decisions = len(replenishment_service.decision_repository.list_all())

        assert initial_inv == after_inv
        assert initial_decisions == after_decisions
