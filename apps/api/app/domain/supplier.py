from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class SupplierRiskLevel(str, Enum):
    """Deterministic supplier operational risk classification.

    Classification is based purely on the supplier's own observable operational profile:
    - LOW: Dependable supplier with standard fulfillment speed (reliability >= 0.92, lead_time <= 14 days, active)
    - MEDIUM: Moderate operational lead time or reliability (lead_time 15–21 days, or reliability 0.85–0.92)
    - HIGH: Elevated operational risk (reliability < 0.85, lead_time > 21 days, or inactive)
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def classify_supplier_risk(
    lead_time_days: int,
    reliability: float,
    active: bool = True,
) -> SupplierRiskLevel:
    """Deterministically classifies supplier operational risk based on lead time and reliability.

    Rules:
    1. Inactive suppliers represent high operational risk if called upon.
    2. Reliability < 0.85 or lead_time > 21 days indicates high operational risk.
    3. Reliability < 0.92 or lead_time > 14 days indicates medium (elevated) operational risk.
    4. Reliability >= 0.92 and lead_time <= 14 days indicates low operational risk.
    """
    if not active:
        return SupplierRiskLevel.HIGH
    if reliability < 0.85 or lead_time_days > 21:
        return SupplierRiskLevel.HIGH
    if reliability < 0.92 or lead_time_days > 14:
        return SupplierRiskLevel.MEDIUM
    return SupplierRiskLevel.LOW


class Supplier(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the supplier")
    code: str = Field(..., min_length=1, description="Supplier code/reference identifier")
    name: str = Field(..., min_length=1, description="Supplier business name")
    lead_time_days: int = Field(..., ge=0, description="Standard supplier fulfillment lead time in days")
    reliability: float = Field(..., ge=0.0, le=1.0, description="Supplier reliability score between 0.0 and 1.0")
    active: bool = Field(default=True, description="Whether the supplier is active")
