from __future__ import annotations

import datetime as dt
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


from app.domain.demand import DemandRecord
from app.domain.inventory import Inventory


class InventoryResponse(BaseModel):
    """Clean typed response model representing an operational inventory position."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    inventory_id: str = Field(..., description="Unique identifier for the inventory position")
    id: str = Field(..., description="Inventory position identifier (alias for inventory_id)")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    quantity_on_hand: int = Field(..., ge=0, description="Physical units present in warehouse")
    quantity_reserved: int = Field(..., ge=0, description="Allocated or reserved units")
    available_quantity: int = Field(..., description="Unreserved inventory available for allocation")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold for this SKU at this location")
    updated_at: datetime = Field(..., description="Timestamp of the most recent inventory update (UTC)")

    @classmethod
    def from_domain(cls, inventory: Inventory) -> InventoryResponse:
        """Constructs an InventoryResponse model from a domain Inventory instance."""
        return cls(
            inventory_id=inventory.id,
            id=inventory.id,
            product_id=inventory.product_id,
            warehouse_id=inventory.warehouse_id,
            quantity_on_hand=inventory.quantity_on_hand,
            quantity_reserved=inventory.quantity_reserved,
            available_quantity=inventory.available_quantity,
            reorder_point=inventory.reorder_point,
            updated_at=inventory.updated_at,
        )


class DemandResponse(BaseModel):
    """Clean typed response model representing an observed historical demand record."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    demand_id: str = Field(..., description="Unique identifier for the demand record")
    id: str = Field(..., description="Demand record identifier (alias for demand_id)")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    date: dt.date = Field(..., description="Observed demand calendar date")
    quantity: int = Field(..., ge=0, description="Observed units demanded/consumed")

    @classmethod
    def from_domain(cls, demand: DemandRecord) -> DemandResponse:
        """Constructs a DemandResponse model from a domain DemandRecord instance."""
        return cls(
            demand_id=demand.id,
            id=demand.id,
            product_id=demand.product_id,
            warehouse_id=demand.warehouse_id,
            date=demand.date,
            quantity=demand.quantity,
        )


class DailyDemandPoint(BaseModel):
    """Daily demand data point within a trend sequence."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    date: dt.date = Field(..., description="Demand date")
    quantity: int = Field(..., ge=0, description="Aggregated units consumed on this date")


class DemandTrendResponse(BaseModel):
    """Deterministic historical demand aggregation and observed trend response."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str | None = Field(default=None, description="Optional warehouse identifier if filtered")
    total_demand: int = Field(..., ge=0, description="Total units consumed across the observed window")
    average_daily_demand: float = Field(..., ge=0.0, description="Average daily consumption across observed days")
    trend_direction: str = Field(..., description="Historical trend trajectory ('increasing', 'decreasing', or 'stable')")
    percentage_change: float = Field(..., description="Percentage shift between first half and second half of window")
    history: list[DailyDemandPoint] = Field(default_factory=list, description="Chronological daily demand observations")

