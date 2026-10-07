from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.demand import DemandRecord
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier, SupplierRiskLevel, classify_supplier_risk
from app.domain.warehouse import Warehouse


class ContextStatus(str, Enum):
    """Deterministic operational status reflecting current operational state.

    Descriptive status only:
    - NORMAL: All operational dimensions are within healthy thresholds.
    - ATTENTION: Approaching replenishment boundaries, elevated lead time, or increasing demand.
    - ELEVATED: Critical state: unallocated inventory at or below reorder threshold,
                high-risk supplier, or inventory coverage insufficient for supplier lead time.
    """

    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    ELEVATED = "ELEVATED"


class ProductContext(BaseModel):
    """Snapshot of product catalog attributes for the decision context."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the product")
    sku: str = Field(..., min_length=1, description="Stock keeping unit code")
    name: str = Field(..., min_length=1, description="Product display name")
    category: str = Field(..., min_length=1, description="Product category")
    unit_cost: float = Field(..., ge=0.0, description="Cost per unit in standard currency")
    selling_price: float = Field(..., ge=0.0, description="Retail selling price per unit")
    reorder_point: int = Field(..., ge=0, description="Replenishment trigger threshold")
    active: bool = Field(default=True, description="Whether the product is currently active")

    @classmethod
    def from_domain(cls, product: Product) -> ProductContext:
        return cls(
            id=product.id,
            sku=product.sku,
            name=product.name,
            category=product.category,
            unit_cost=product.unit_cost,
            selling_price=product.selling_price,
            reorder_point=product.reorder_point,
            active=product.active,
        )


class WarehouseContext(BaseModel):
    """Snapshot of warehouse facility attributes for the decision context."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the warehouse")
    code: str = Field(..., min_length=1, description="Warehouse facility code")
    name: str = Field(..., min_length=1, description="Warehouse facility name")
    location: str = Field(..., min_length=1, description="Geographic location or address")
    capacity: int = Field(..., ge=0, description="Total storage unit capacity")
    active: bool = Field(default=True, description="Whether the warehouse is operational")

    @classmethod
    def from_domain(cls, warehouse: Warehouse) -> WarehouseContext:
        return cls(
            id=warehouse.id,
            code=warehouse.code,
            name=warehouse.name,
            location=warehouse.location,
            capacity=warehouse.capacity,
            active=warehouse.active,
        )


class InventoryContext(BaseModel):
    """Snapshot of current physical and available inventory positions."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    inventory_id: str | None = Field(default=None, description="Unique inventory position identifier")
    quantity_on_hand: int = Field(..., ge=0, description="Physical units present in warehouse")
    quantity_reserved: int = Field(..., ge=0, description="Allocated or reserved units")
    available_quantity: int = Field(..., description="Unreserved inventory available for allocation")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold for this SKU at this location")
    updated_at: dt.datetime | None = Field(default=None, description="Timestamp of the most recent inventory update (UTC)")

    @classmethod
    def from_domain(cls, inventory: Inventory) -> InventoryContext:
        return cls(
            inventory_id=inventory.id,
            quantity_on_hand=inventory.quantity_on_hand,
            quantity_reserved=inventory.quantity_reserved,
            available_quantity=inventory.available_quantity,
            reorder_point=inventory.reorder_point,
            updated_at=inventory.updated_at,
        )


class DailyDemandContextPoint(BaseModel):
    """Historical daily demand point within the context observation window."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    date: dt.date = Field(..., description="Observed demand calendar date")
    quantity: int = Field(..., ge=0, description="Observed units demanded/consumed")


class DemandContext(BaseModel):
    """Snapshot of observed historical consumption and trajectory."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    total_demand: int = Field(..., ge=0, description="Total units consumed across the observed window")
    average_daily_demand: float = Field(..., ge=0.0, description="Average daily consumption across observed days")
    trend_direction: str = Field(..., description="Historical trend trajectory ('increasing', 'decreasing', or 'stable')")
    percentage_change: float = Field(..., description="Percentage shift between first half and second half of window")
    window_days: int = Field(..., ge=0, description="Number of observed days in the historical window")
    history: list[DailyDemandContextPoint] = Field(default_factory=list, description="Chronological daily demand observations")


class SupplierContext(BaseModel):
    """Snapshot of primary supplier fulfillment parameters and operational risk."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    supplier_id: str = Field(..., min_length=1, description="Unique identifier for the supplier")
    code: str = Field(..., min_length=1, description="Supplier code/reference identifier")
    name: str = Field(..., min_length=1, description="Supplier business name")
    lead_time_days: int = Field(..., ge=0, description="Standard supplier fulfillment lead time in days")
    reliability: float = Field(..., ge=0.0, le=1.0, description="Supplier reliability score between 0.0 and 1.0")
    active: bool = Field(default=True, description="Whether the supplier is active")
    risk_level: SupplierRiskLevel = Field(..., description="Deterministic supplier operational risk classification")

    @classmethod
    def from_domain(cls, supplier: Supplier) -> SupplierContext:
        return cls(
            supplier_id=supplier.id,
            code=supplier.code,
            name=supplier.name,
            lead_time_days=supplier.lead_time_days,
            reliability=supplier.reliability,
            active=supplier.active,
            risk_level=classify_supplier_risk(
                lead_time_days=supplier.lead_time_days,
                reliability=supplier.reliability,
                active=supplier.active,
            ),
        )


class DerivedContextMetrics(BaseModel):
    """Purely descriptive operational metrics derived deterministically from the snapshot.

    Contains NO predictive scoring, forecasting, or optimization calculations.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    coverage_days: float | None = Field(
        default=None,
        description="Inventory coverage in days (available_quantity / average_daily_demand), or None if zero demand",
    )
    lead_time_days: int | None = Field(
        default=None,
        description="Primary supplier lead time in days, or None if no supplier data",
    )
    is_below_reorder: bool = Field(
        ...,
        description="True if available inventory is at or below the reorder point",
    )
    net_deficit: int = Field(
        default=0,
        ge=0,
        description="Units below reorder threshold (max(0, reorder_point - available_quantity))",
    )
    context_status: ContextStatus = Field(
        ...,
        description="Descriptive operational status (NORMAL, ATTENTION, ELEVATED)",
    )


class DecisionContext(BaseModel):
    """Unified operational snapshot representing all known operational facts for a situation.

    Answers: 'What do we know about this situation?'
    Must NEVER answer: 'What should we do?'
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    product: ProductContext = Field(..., description="Product catalog context")
    warehouse: WarehouseContext = Field(..., description="Warehouse facility context")
    inventory: InventoryContext | None = Field(default=None, description="Operational inventory position context")
    demand: DemandContext | None = Field(default=None, description="Historical demand and trend context")
    supplier: SupplierContext | None = Field(default=None, description="Primary supplier and risk context")
    metrics: DerivedContextMetrics = Field(..., description="Derived descriptive contextual metrics")
    status: ContextStatus = Field(..., description="Unified operational context status (NORMAL, ATTENTION, ELEVATED)")
