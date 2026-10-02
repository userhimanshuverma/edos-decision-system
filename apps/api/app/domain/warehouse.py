from pydantic import BaseModel, ConfigDict, Field


class Warehouse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the warehouse")
    code: str = Field(..., min_length=1, description="Warehouse facility code")
    name: str = Field(..., min_length=1, description="Warehouse facility name")
    location: str = Field(..., min_length=1, description="Geographic location or address")
    capacity: int = Field(..., ge=0, description="Total storage unit capacity")
    active: bool = Field(default=True, description="Whether the warehouse is operational")
