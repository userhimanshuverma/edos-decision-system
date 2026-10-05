from __future__ import annotations

import datetime as dt
from pydantic import BaseModel, ConfigDict, Field


class DemandRecord(BaseModel):
    """Historical observed demand record for a product at a specific warehouse.

    Represents raw historical consumption data. Contains no predictive,
    forecasting, or replenishment calculation fields.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the demand record")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    date: dt.date = Field(..., description="Observed demand calendar date")
    quantity: int = Field(..., ge=0, description="Observed units consumed on this date (non-negative)")
