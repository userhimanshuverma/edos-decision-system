from __future__ import annotations

import pytest

from app.data.generator import generate_shopflow_dataset
from app.domain.stockout_risk import (
    StockoutRiskLevel,
    StockoutRiskModelType,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository
from app.stockout_risk.service import (
    DecisionNotFoundError,
    MissingStockoutRiskDataError,
    ProductNotFoundError,
    StockoutRiskService,
    WarehouseNotFoundError,
)


@pytest.fixture
def shared_dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def stockout_risk_service(shared_dataset):
    inv_repo = InventoryRepository(dataset=shared_dataset)
    demand_repo = DemandRepository(dataset=shared_dataset)
    supplier_repo = SupplierRepository(dataset=shared_dataset)
    decision_repo = DecisionRepository(dataset=shared_dataset)
    return StockoutRiskService(
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=supplier_repo,
        decision_repo=decision_repo,
    )


class TestStockoutRiskService:
    """Tests the StockoutRiskService coordination, lookup resolution, and immutability."""

    def test_calculate_for_product_warehouse_success(self, stockout_risk_service):
        result = stockout_risk_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
        )

        assert result.product_id == "prod-001"
        assert result.warehouse_id == "wh-001"
        assert result.model_type == StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE
        assert 0.0 <= result.exposure_index <= 1.0
        assert isinstance(result.risk_level, StockoutRiskLevel)
        assert result.is_probability is False
        assert result.breakdown.lead_time_days > 0
        assert result.breakdown.average_daily_demand > 0
        assert result.breakdown.lead_time_demand > 0
        assert len(result.breakdown.calculation_notes) > 0

    def test_calculate_with_supplier_override(self, stockout_risk_service):
        # Use an explicit active supplier from the dataset
        suppliers = stockout_risk_service.supplier_repository.list_all()
        target_supplier = suppliers[0]

        result = stockout_risk_service.calculate_for_product_warehouse(
            product_id="prod-001",
            warehouse_id="wh-001",
            supplier_id=target_supplier.id,
        )

        assert result.breakdown.lead_time_days == target_supplier.lead_time_days
        assert result.breakdown.supplier_reliability == target_supplier.reliability

    def test_calculate_for_decision(self, stockout_risk_service):
        decision = stockout_risk_service.decision_repository.create(
            product_id="prod-002",
            warehouse_id="wh-001",
        )

        result = stockout_risk_service.calculate_for_decision(
            decision_id=decision.id,
        )

        assert result.product_id == "prod-002"
        assert result.warehouse_id == "wh-001"
        assert result.is_probability is False

    def test_unknown_product_raises_404(self, stockout_risk_service):
        with pytest.raises(ProductNotFoundError, match="Product 'prod-999' not found"):
            stockout_risk_service.calculate_for_product_warehouse(
                product_id="prod-999",
                warehouse_id="wh-001",
            )

    def test_unknown_warehouse_raises_404(self, stockout_risk_service):
        with pytest.raises(WarehouseNotFoundError, match="Warehouse 'wh-999' not found"):
            stockout_risk_service.calculate_for_product_warehouse(
                product_id="prod-001",
                warehouse_id="wh-999",
            )

    def test_unknown_decision_raises_not_found(self, stockout_risk_service):
        with pytest.raises(DecisionNotFoundError, match="Decision 'dec-missing' not found"):
            stockout_risk_service.calculate_for_decision(
                decision_id="dec-missing",
            )

    def test_missing_supplier_override_raises_missing_data(self, stockout_risk_service):
        with pytest.raises(MissingStockoutRiskDataError, match="Specified supplier 'sup-invalid' not found"):
            stockout_risk_service.calculate_for_product_warehouse(
                product_id="prod-001",
                warehouse_id="wh-001",
                supplier_id="sup-invalid",
            )

    def test_uninitialized_decision_repository_raises_runtime_error(self, shared_dataset):
        service = StockoutRiskService(
            inventory_repo=InventoryRepository(dataset=shared_dataset),
            decision_repo=None,
        )
        with pytest.raises(RuntimeError, match="DecisionRepository is required"):
            service.calculate_for_decision(decision_id="dec-001")

    def test_strict_immutability_of_source_records(self, stockout_risk_service):
        """Verify calculation does NOT mutate inventory, decisions, candidate actions, or graphs."""
        action_repo = CandidateActionRepository()
        graph_repo = DecisionGraphRepository()

        initial_inventory = [i.model_dump() for i in stockout_risk_service.inventory_repository.list_all()]
        initial_decisions = [d.model_dump() for d in stockout_risk_service.decision_repository.list_all()]
        initial_actions = action_repo.list_all()
        initial_graphs = graph_repo.list_all()

        # Run calculations
        _ = stockout_risk_service.calculate_for_product_warehouse("prod-001", "wh-001")
        _ = stockout_risk_service.calculate_for_product_warehouse("prod-002", "wh-001")

        after_inventory = [i.model_dump() for i in stockout_risk_service.inventory_repository.list_all()]
        after_decisions = [d.model_dump() for d in stockout_risk_service.decision_repository.list_all()]
        after_actions = action_repo.list_all()
        after_graphs = graph_repo.list_all()

        assert initial_inventory == after_inventory
        assert initial_decisions == after_decisions
        assert len(after_actions) == len(initial_actions) == 0
        assert len(after_graphs) == len(initial_graphs) == 0
