from pydantic import BaseModel, ConfigDict, Field


class Product(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the product")
    sku: str = Field(..., min_length=1, description="Stock keeping unit code")
    name: str = Field(..., min_length=1, description="Product display name")
    category: str = Field(..., min_length=1, description="Product category")
    unit_cost: float = Field(..., ge=0.0, description="Cost per unit in standard currency")
    selling_price: float = Field(..., ge=0.0, description="Retail selling price per unit")
    reorder_point: int = Field(..., ge=0, description="Inventory threshold triggering replenishment")
    active: bool = Field(default=True, description="Whether the product is currently active")
