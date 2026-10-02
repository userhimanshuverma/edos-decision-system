from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Inventory(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the inventory position")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    quantity_on_hand: int = Field(..., ge=0, description="Physical units present in warehouse")
    quantity_reserved: int = Field(default=0, ge=0, description="Allocated or reserved units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold for this SKU at this location")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the most recent inventory update (UTC)",
    )

    @model_validator(mode="after")
    def validate_reserved_quantity(self) -> "Inventory":
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValueError(
                f"quantity_reserved ({self.quantity_reserved}) cannot exceed quantity_on_hand ({self.quantity_on_hand})"
            )
        return self

    @property
    def available_quantity(self) -> int:
        """Returns the unreserved inventory available for allocation."""
        return self.quantity_on_hand - self.quantity_reserved
