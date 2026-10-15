from __future__ import annotations

from typing import Any

from app.data.dataset import ShopFlowDataset
from app.domain.replenishment import (
    ReplenishmentBreakdown,
    ReplenishmentCalculationInputs,
    ReplenishmentCalculationResult,
    ReplenishmentPolicyType,
    calculate_replenishment_quantity,
)
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


class ReplenishmentError(Exception):
    """Base exception for replenishment calculation service errors."""


class ProductNotFoundError(ReplenishmentError):
    """Raised when the specified product does not exist in catalog."""


class WarehouseNotFoundError(ReplenishmentError):
    """Raised when the specified warehouse does not exist in data."""


class DecisionNotFoundError(ReplenishmentError):
    """Raised when the specified decision does not exist."""


class MissingReplenishmentDataError(ReplenishmentError):
    """Raised when required operational data for the chosen replenishment policy cannot be resolved."""


class ReplenishmentService:
    """Application coordination service for deterministic replenishment quantity calculations.

    Combines Inventory, Historical Demand, Supplier, and Warehouse operational data
    to answer:
    'How much should we order under an explicitly defined replenishment policy?'

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
        """Initializes ReplenishmentService with repositories or shared ShopFlow dataset."""
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
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        *,
        target_stock: int | None = None,
        supplier_id: str | None = None,
        enforce_reorder_trigger: bool = True,
    ) -> ReplenishmentCalculationResult:
        """Calculates deterministic replenishment order quantity for a product and warehouse.

        Args:
            product_id: Unique product identifier (e.g. 'prod-001')
            warehouse_id: Unique warehouse identifier (e.g. 'wh-001')
            policy_type: Replenishment policy formula to apply
            target_stock: Explicit target stock level (required for TARGET_STOCK policy)
            supplier_id: Optional supplier ID override (for LEAD_TIME_DEMAND policy)
            enforce_reorder_trigger: If True, only replenishes when available_quantity <= reorder_point

        Returns:
            ReplenishmentCalculationResult: Strongly typed calculation result with auditable breakdown.

        Raises:
            ProductNotFoundError: If product_id does not exist.
            WarehouseNotFoundError: If warehouse_id does not exist.
            MissingReplenishmentDataError: If policy requires data that cannot be resolved.
            ValueError: If calculation parameters are invalid.
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

        resolved_policy = (
            policy_type
            if isinstance(policy_type, ReplenishmentPolicyType)
            else ReplenishmentPolicyType(policy_type)
        )

        # 3. Retrieve inventory position
        inv_position = self._inventory_repo.dataset.get_inventory(norm_product_id, norm_warehouse_id)
        if inv_position is not None:
            available_qty = inv_position.available_quantity
            reorder_point = inv_position.reorder_point
        else:
            available_qty = 0
            reorder_point = product.reorder_point

        # 4. Conditionally resolve demand and lead time data if required by the policy
        average_daily_demand: float | None = None
        lead_time_days: int | None = None

        if resolved_policy == ReplenishmentPolicyType.LEAD_TIME_DEMAND:
            trend_summary = self._demand_repo.get_product_demand_trend(
                product_id=norm_product_id,
                warehouse_id=norm_warehouse_id,
            )
            average_daily_demand = float(trend_summary.get("average_daily_demand", 0.0))

            supplier = None
            if supplier_id is not None:
                norm_sup_id = supplier_id.strip()
                supplier = self._supplier_repo.get_by_id(norm_sup_id)
                if supplier is None:
                    raise MissingReplenishmentDataError(
                        f"Specified supplier '{norm_sup_id}' not found for lead time demand calculation"
                    )
            else:
                supplier = self._supplier_repo.get_supplier_for_product(
                    product_id=norm_product_id,
                    category=product.category,
                )

            if supplier is None:
                raise MissingReplenishmentDataError(
                    f"No supplier found for product '{norm_product_id}' to resolve lead time"
                )

            lead_time_days = supplier.lead_time_days

        # 5. Build inputs model (performs validation)
        inputs = ReplenishmentCalculationInputs(
            product_id=norm_product_id,
            warehouse_id=norm_warehouse_id,
            available_quantity=available_qty,
            reorder_point=reorder_point,
            policy_type=resolved_policy,
            target_stock=target_stock,
            average_daily_demand=average_daily_demand,
            lead_time_days=lead_time_days,
            warehouse_capacity=warehouse.capacity,
            enforce_reorder_trigger=enforce_reorder_trigger,
        )

        # 6. Run pure calculation
        return calculate_replenishment_quantity(inputs)

    def calculate_for_decision(
        self,
        decision_id: str,
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        *,
        target_stock: int | None = None,
        supplier_id: str | None = None,
        enforce_reorder_trigger: bool = True,
    ) -> ReplenishmentCalculationResult:
        """Calculates deterministic replenishment order quantity for a business decision.

        Looks up the decision's associated product_id and warehouse_id, then performs
        the replenishment calculation.

        Raises:
            DecisionNotFoundError: If decision_id does not exist.
        """
        if self._decision_repo is None:
            raise RuntimeError("DecisionRepository is required to calculate replenishment by decision_id")

        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self.calculate_for_product_warehouse(
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            policy_type=policy_type,
            target_stock=target_stock,
            supplier_id=supplier_id,
            enforce_reorder_trigger=enforce_reorder_trigger,
        )
