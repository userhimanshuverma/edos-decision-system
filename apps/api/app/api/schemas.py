from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

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
