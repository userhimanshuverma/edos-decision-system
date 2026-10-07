from __future__ import annotations

from typing import Any

from app.data.dataset import ShopFlowDataset
from app.data.generator import generate_shopflow_dataset
from app.domain.context import (
    ContextStatus,
    DailyDemandContextPoint,
    DecisionContext,
    DemandContext,
    DerivedContextMetrics,
    InventoryContext,
    ProductContext,
    SupplierContext,
    WarehouseContext,
)
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository, SupplierRiskLevel


class ContextEngineError(Exception):
    """Base exception for Context Engine operations."""


class ProductNotFoundError(ContextEngineError):
    """Raised when the specified product does not exist in catalog."""


class WarehouseNotFoundError(ContextEngineError):
    """Raised when the specified warehouse does not exist in dataset."""


class ContextEngine:
    """Core aggregation engine synthesizing operational state into unified DecisionContext.

    Combines Inventory, Historical Demand, and Supplier data layers into a single,
    deterministic, strongly typed operational snapshot.

    Answers: 'What do we know about this situation?'
    Strictly does NOT answer: 'What should we do?'
    """

    def __init__(
        self,
        inventory_repo: InventoryRepository | None = None,
        demand_repo: DemandRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        dataset: ShopFlowDataset | None = None,
    ) -> None:
        """Initializes ContextEngine with data repositories or a shared ShopFlow dataset."""
        if dataset is not None:
            self.inventory_repo = inventory_repo or InventoryRepository(dataset=dataset)
            self.demand_repo = demand_repo or DemandRepository(dataset=dataset)
            self.supplier_repo = supplier_repo or SupplierRepository(dataset=dataset)
        else:
            self.inventory_repo = inventory_repo or InventoryRepository()
            # Reuse dataset from inventory_repo to maintain consistent seed/dataset by default
            shared_dataset = self.inventory_repo.dataset
            self.demand_repo = demand_repo or DemandRepository(dataset=shared_dataset)
            self.supplier_repo = supplier_repo or SupplierRepository(dataset=shared_dataset)

    def get_decision_context(
        self,
        product_id: str,
        warehouse_id: str,
        supplier_id: str | None = None,
    ) -> DecisionContext:
        """Aggregates all known operational facts for a product and warehouse into a DecisionContext.

        Args:
            product_id: Unique product identifier (e.g. 'prod-001')
            warehouse_id: Unique warehouse identifier (e.g. 'wh-001')
            supplier_id: Optional explicit supplier ID override. If None, deterministically
                         resolves the primary operational supplier.

        Returns:
            DecisionContext: Complete, typed, deterministic operational snapshot.

        Raises:
            ProductNotFoundError: If product_id does not exist.
            WarehouseNotFoundError: If warehouse_id does not exist.
        """
        norm_product_id = product_id.strip()
        norm_warehouse_id = warehouse_id.strip()

        # 1. Retrieve & validate product
        product = self.inventory_repo.dataset.get_product(norm_product_id)
        if product is None:
            raise ProductNotFoundError(f"Product '{norm_product_id}' not found")
        product_ctx = ProductContext.from_domain(product)

        # 2. Retrieve & validate warehouse
        warehouse = self.inventory_repo.dataset.get_warehouse(norm_warehouse_id)
        if warehouse is None:
            raise WarehouseNotFoundError(f"Warehouse '{norm_warehouse_id}' not found")
        warehouse_ctx = WarehouseContext.from_domain(warehouse)

        # 3. Retrieve inventory position
        inv_position = self.inventory_repo.dataset.get_inventory(norm_product_id, norm_warehouse_id)
        if inv_position is not None:
            inventory_ctx = InventoryContext.from_domain(inv_position)
            available_qty = inv_position.available_quantity
            reorder_point = inv_position.reorder_point
        else:
            inventory_ctx = None
            available_qty = 0
            reorder_point = product.reorder_point

        # 4. Retrieve historical demand & trend
        trend_summary = self.demand_repo.get_product_demand_trend(
            product_id=norm_product_id,
            warehouse_id=norm_warehouse_id,
        )
        history_points = [
            DailyDemandContextPoint(date=item["date"], quantity=item["quantity"])
            for item in trend_summary.get("history", [])
        ]
        demand_ctx = DemandContext(
            total_demand=trend_summary["total_demand"],
            average_daily_demand=trend_summary["average_daily_demand"],
            trend_direction=trend_summary["trend_direction"],
            percentage_change=trend_summary["percentage_change"],
            window_days=len(history_points),
            history=history_points,
        )

        # 5. Retrieve supplier context
        supplier = None
        if supplier_id is not None:
            supplier = self.supplier_repo.get_by_id(supplier_id)
        if supplier is None:
            supplier = self.supplier_repo.get_supplier_for_product(
                product_id=norm_product_id,
                category=product.category,
            )

        supplier_ctx = SupplierContext.from_domain(supplier) if supplier is not None else None

        # 6. Calculate simple descriptive derived metrics
        # Coverage days: available_quantity / average_daily_demand (handle zero demand safely)
        avg_demand = demand_ctx.average_daily_demand
        if avg_demand > 0:
            coverage_days = round(available_qty / avg_demand, 2)
        else:
            coverage_days = None

        lead_time = supplier_ctx.lead_time_days if supplier_ctx is not None else None
        is_below_reorder = available_qty <= reorder_point
        net_deficit = max(0, reorder_point - available_qty)

        # Deterministic descriptive context status classification
        context_status = self._classify_context_status(
            inventory_ctx=inventory_ctx,
            available_qty=available_qty,
            reorder_point=reorder_point,
            coverage_days=coverage_days,
            lead_time_days=lead_time,
            supplier_ctx=supplier_ctx,
            demand_ctx=demand_ctx,
        )

        metrics = DerivedContextMetrics(
            coverage_days=coverage_days,
            lead_time_days=lead_time,
            is_below_reorder=is_below_reorder,
            net_deficit=net_deficit,
            context_status=context_status,
        )

        return DecisionContext(
            product_id=norm_product_id,
            warehouse_id=norm_warehouse_id,
            product=product_ctx,
            warehouse=warehouse_ctx,
            inventory=inventory_ctx,
            demand=demand_ctx,
            supplier=supplier_ctx,
            metrics=metrics,
            status=context_status,
        )

    def _classify_context_status(
        self,
        inventory_ctx: InventoryContext | None,
        available_qty: int,
        reorder_point: int,
        coverage_days: float | None,
        lead_time_days: int | None,
        supplier_ctx: SupplierContext | None,
        demand_ctx: DemandContext | None,
    ) -> ContextStatus:
        """Deterministically classifies descriptive operational status.

        Rules:
        - ELEVATED:
            * Inventory record missing or available quantity <= reorder point
            * Supplier risk is HIGH
            * Inventory coverage is shorter than supplier lead time (when both known)
        - ATTENTION:
            * Available quantity is approaching reorder point (within 125% of reorder)
            * Supplier risk is MEDIUM
            * Historical demand trend is increasing
        - NORMAL:
            * Operational indicators within standard operating buffers
        """
        if inventory_ctx is None or available_qty <= reorder_point:
            return ContextStatus.ELEVATED

        if supplier_ctx is not None and supplier_ctx.risk_level == SupplierRiskLevel.HIGH:
            return ContextStatus.ELEVATED

        if coverage_days is not None and lead_time_days is not None:
            if coverage_days < lead_time_days:
                return ContextStatus.ELEVATED

        if available_qty <= int(reorder_point * 1.25):
            return ContextStatus.ATTENTION

        if supplier_ctx is not None and supplier_ctx.risk_level == SupplierRiskLevel.MEDIUM:
            return ContextStatus.ATTENTION

        if demand_ctx is not None and demand_ctx.trend_direction == "increasing":
            return ContextStatus.ATTENTION

        return ContextStatus.NORMAL
