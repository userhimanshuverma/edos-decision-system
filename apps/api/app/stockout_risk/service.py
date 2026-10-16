from __future__ import annotations

from typing import Any

from app.data.dataset import ShopFlowDataset
from app.domain.stockout_risk import (
    StockoutRiskBreakdown,
    StockoutRiskCalculationInputs,
    StockoutRiskCalculationResult,
    StockoutRiskLevel,
    StockoutRiskModelType,
    calculate_stockout_risk,
)
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


class StockoutRiskError(Exception):
    """Base exception for stockout-risk calculation service errors."""


class ProductNotFoundError(StockoutRiskError):
    """Raised when the specified product does not exist in catalog."""


class WarehouseNotFoundError(StockoutRiskError):
    """Raised when the specified warehouse does not exist in dataset."""


class DecisionNotFoundError(StockoutRiskError):
    """Raised when the specified decision does not exist."""


class MissingStockoutRiskDataError(StockoutRiskError):
    """Raised when required operational data for stockout-risk calculation cannot be resolved."""


class StockoutRiskService:
    """Application coordination service for deterministic stockout-risk calculations.

    Combines Inventory, Historical Demand, Supplier, and Warehouse operational data
    to answer:
    'How exposed is this inventory position to a potential stockout,
    based on the operational data and assumptions available to EDOS?'

    Does NOT decide which action is best, score alternatives, or recommend interventions.
    """

    def __init__(
        self,
        inventory_repo: InventoryRepository | None = None,
        demand_repo: DemandRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        decision_repo: DecisionRepository | None = None,
        dataset: ShopFlowDataset | None = None,
    ) -> None:
        """Initializes StockoutRiskService with repositories or shared ShopFlow dataset."""
        if dataset is not None:
            self._inventory_repo = inventory_repo or InventoryRepository(dataset=dataset)
            self._demand_repo = demand_repo or DemandRepository(dataset=dataset)
            self._supplier_repo = supplier_repo or SupplierRepository(dataset=dataset)
            self._decision_repo = decision_repo
        else:
            self._inventory_repo = inventory_repo or InventoryRepository()
            shared_ds = self._inventory_repo.dataset
            self._demand_repo = demand_repo or DemandRepository(dataset=shared_ds)
            self._supplier_repo = supplier_repo or SupplierRepository(dataset=shared_ds)
            self._decision_repo = decision_repo

    @property
    def inventory_repository(self) -> InventoryRepository:
        return self._inventory_repo

    @property
    def demand_repository(self) -> DemandRepository:
        return self._demand_repo

    @property
    def supplier_repository(self) -> SupplierRepository:
        return self._supplier_repo

    @property
    def decision_repository(self) -> DecisionRepository | None:
        return self._decision_repo

    def calculate_for_product_warehouse(
        self,
        product_id: str,
        warehouse_id: str,
        model_type: StockoutRiskModelType | str = StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE,
        *,
        supplier_id: str | None = None,
    ) -> StockoutRiskCalculationResult:
        """Calculates deterministic stockout risk and lead-time exposure for a product and warehouse.

        Args:
            product_id: Unique product identifier (e.g. 'prod-001')
            warehouse_id: Unique warehouse identifier (e.g. 'wh-001')
            model_type: Stockout risk calculation model to apply
            supplier_id: Optional supplier ID override for lead-time resolution

        Returns:
            StockoutRiskCalculationResult: Strongly typed calculation result with auditable breakdown.

        Raises:
            ProductNotFoundError: If product_id does not exist.
            WarehouseNotFoundError: If warehouse_id does not exist.
            MissingStockoutRiskDataError: If required supplier or operational data cannot be resolved.
            ValueError: If input parameters violate domain constraints.
        """
        norm_product_id = product_id.strip()
        norm_warehouse_id = warehouse_id.strip()

        # 1. Retrieve & validate product existence
        product = self._inventory_repo.dataset.get_product(norm_product_id)
        if product is None:
            raise ProductNotFoundError(f"Product '{norm_product_id}' not found")

        # 2. Retrieve & validate warehouse existence
        warehouse = self._inventory_repo.dataset.get_warehouse(norm_warehouse_id)
        if warehouse is None:
            raise WarehouseNotFoundError(f"Warehouse '{norm_warehouse_id}' not found")

        resolved_model = (
            model_type
            if isinstance(model_type, StockoutRiskModelType)
            else StockoutRiskModelType(model_type)
        )

        # 3. Retrieve inventory position
        inv_position = self._inventory_repo.dataset.get_inventory(norm_product_id, norm_warehouse_id)
        if inv_position is not None:
            available_qty = inv_position.available_quantity
            reorder_point = inv_position.reorder_point
        else:
            available_qty = 0
            reorder_point = product.reorder_point

        # 4. Retrieve historical demand trend & history points
        trend_summary = self._demand_repo.get_product_demand_trend(
            product_id=norm_product_id,
            warehouse_id=norm_warehouse_id,
        )
        average_daily_demand = float(trend_summary.get("average_daily_demand", 0.0))
        history_items = trend_summary.get("history", [])
        historical_daily_demands = [item["quantity"] for item in history_items] if history_items else None

        # 5. Retrieve supplier fulfillment parameters
        supplier = None
        if supplier_id is not None:
            norm_sup_id = supplier_id.strip()
            supplier = self._supplier_repo.get_by_id(norm_sup_id)
            if supplier is None:
                raise MissingStockoutRiskDataError(
                    f"Specified supplier '{norm_sup_id}' not found for stockout risk calculation"
                )
        else:
            supplier = self._supplier_repo.get_supplier_for_product(
                product_id=norm_product_id,
                category=product.category,
            )

        if supplier is None:
            raise MissingStockoutRiskDataError(
                f"No supplier found for product '{norm_product_id}' to resolve lead time"
            )

        lead_time_days = supplier.lead_time_days
        supplier_reliability = supplier.reliability

        # 6. Build strongly typed calculation inputs
        inputs = StockoutRiskCalculationInputs(
            product_id=norm_product_id,
            warehouse_id=norm_warehouse_id,
            available_quantity=available_qty,
            reorder_point=reorder_point,
            average_daily_demand=average_daily_demand,
            lead_time_days=lead_time_days,
            model_type=resolved_model,
            historical_daily_demands=historical_daily_demands,
            supplier_reliability=supplier_reliability,
        )

        # 7. Execute pure, deterministic calculation
        return calculate_stockout_risk(inputs)

    def calculate_for_decision(
        self,
        decision_id: str,
        model_type: StockoutRiskModelType | str = StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE,
        *,
        supplier_id: str | None = None,
    ) -> StockoutRiskCalculationResult:
        """Calculates deterministic stockout risk for a business decision.

        Looks up the decision's associated product_id and warehouse_id, then performs
        the stockout-risk calculation.

        Raises:
            DecisionNotFoundError: If decision_id does not exist.
        """
        if self._decision_repo is None:
            raise RuntimeError("DecisionRepository is required to calculate stockout risk by decision_id")

        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self.calculate_for_product_warehouse(
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            model_type=model_type,
            supplier_id=supplier_id,
        )
