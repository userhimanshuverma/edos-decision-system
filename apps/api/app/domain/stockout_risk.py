from __future__ import annotations

from enum import Enum
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StockoutRiskModelType(str, Enum):
    """Supported deterministic stockout-risk calculation models."""

    DETERMINISTIC_LEAD_TIME_EXPOSURE = "DETERMINISTIC_LEAD_TIME_EXPOSURE"


class StockoutRiskLevel(str, Enum):
    """Deterministic operational stockout risk classification.

    - CRITICAL: Position is currently stocked out with active demand, or available inventory
                coverage is strictly shorter than supplier lead time (stockout projected before arrival).
    - HIGH: Inventory covers lead time, but available quantity is at or below reorder threshold,
            or runway buffer is very narrow (<= 3.0 days).
    - MEDIUM: Inventory is above reorder point but approaching threshold (<= 1.25x ROP),
              or supplier reliability is degraded (< 0.90) with moderate buffer.
    - LOW: Available inventory comfortably exceeds lead-time demand and reorder threshold
           with healthy buffer (> 3.0 days) and dependable supplier fulfillment.
    - NO_DEMAND: Zero observed daily demand. Inventory position has no consumption exposure.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NO_DEMAND = "NO_DEMAND"


class StockoutRiskBreakdown(BaseModel):
    """Detailed, auditable mathematical breakdown of a stockout-risk calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    available_quantity: int = Field(..., ge=0, description="Available unreserved inventory units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    average_daily_demand: float = Field(..., ge=0.0, description="Observed historical average daily demand (units/day)")
    lead_time_days: int = Field(..., ge=0, description="Supplier fulfillment lead time (days)")
    coverage_days: float | None = Field(
        default=None,
        ge=0.0,
        description="Runway in days: available_quantity / average_daily_demand, or None if zero demand",
    )
    lead_time_demand: float = Field(
        ...,
        ge=0.0,
        description="Projected demand during lead time: average_daily_demand * lead_time_days",
    )
    exposure_deficit: float = Field(
        ...,
        ge=0.0,
        description="Shortfall units exposed to stockout during lead time: max(0.0, lead_time_demand - available_quantity)",
    )
    buffer_days: float | None = Field(
        default=None,
        description="Runway buffer beyond lead time: coverage_days - lead_time_days (negative if stockout occurs before arrival)",
    )
    exposure_index: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized stockout exposure ratio in [0.0, 1.0] representing the fraction of lead-time demand exposed",
    )
    is_below_reorder: bool = Field(..., description="True if available_quantity <= reorder_point")
    demand_std_dev: float | None = Field(
        default=None,
        ge=0.0,
        description="Sample standard deviation of daily demand when historical observations are provided",
    )
    demand_coefficient_of_variation: float | None = Field(
        default=None,
        ge=0.0,
        description="Dispersion ratio (demand_std_dev / average_daily_demand) when historical observations are provided",
    )
    supplier_reliability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Primary supplier reliability score in [0.0, 1.0], if available",
    )
    calculation_notes: list[str] = Field(
        default_factory=list,
        description="Auditable step-by-step mathematical derivation notes",
    )


class StockoutRiskCalculationInputs(BaseModel):
    """Strongly typed input parameters for deterministic stockout-risk calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    available_quantity: int = Field(..., ge=0, description="Current available unreserved units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    average_daily_demand: float = Field(..., ge=0.0, description="Observed historical average daily demand (units/day)")
    lead_time_days: int = Field(..., ge=0, description="Supplier fulfillment lead time (days)")
    model_type: StockoutRiskModelType = Field(
        default=StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE,
        description="Deterministic stockout-risk calculation model to apply",
    )
    historical_daily_demands: list[int] | None = Field(
        default=None,
        description="Optional list of daily historical consumption observations for dispersion calculation",
    )
    supplier_reliability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Supplier reliability score between 0.0 and 1.0, if available",
    )

    @field_validator("historical_daily_demands")
    @classmethod
    def validate_daily_demands(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            for qty in v:
                if qty < 0:
                    raise ValueError(f"Historical daily demand observations cannot be negative: found {qty}")
        return v


class StockoutRiskCalculationResult(BaseModel):
    """Deterministic result of a stockout-risk calculation.

    Answers: 'How exposed is this inventory position to a potential stockout,
    based on the operational data and assumptions available to EDOS?'

    Strictly does NOT evaluate candidate actions, score trade-offs, or recommend orders.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    model_type: StockoutRiskModelType = Field(..., description="Risk model applied")
    risk_level: StockoutRiskLevel = Field(..., description="Deterministic operational stockout risk classification")
    exposure_index: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized stockout exposure ratio in [0.0, 1.0]. 0.0 = fully covered, 1.0 = fully exposed",
    )
    is_stockout_predicted: bool = Field(
        ...,
        description="True if inventory runs out before replenishment lead time or is currently exhausted",
    )
    is_probability: bool = Field(
        default=False,
        description="Always False. Clarifies that exposure_index is a deterministic physical exposure ratio, not an empirical probability.",
    )
    formula: str = Field(..., description="Textual description of the mathematical formula applied")
    assumptions: list[str] = Field(..., description="Explicit operational assumptions behind the calculation")
    limitations: list[str] = Field(..., description="Known model limitations and boundary conditions")
    breakdown: StockoutRiskBreakdown = Field(..., description="Detailed deterministic calculation breakdown")


def calculate_stockout_risk(
    inputs: StockoutRiskCalculationInputs,
) -> StockoutRiskCalculationResult:
    """Pure, deterministic calculation function for stockout risk and lead-time exposure.

    Requirements:
    - Pure function without HTTP, database, or network dependencies.
    - Deterministic: identical inputs always yield identical outputs.
    - Explicitly computes lead-time demand, exposure deficit, buffer days, and exposure ratio.
    - Distinguishes physical exposure from statistical probability (is_probability=False).
    - Preserves auditable intermediate calculations.
    """
    notes: list[str] = []
    avail = inputs.available_quantity
    rop = inputs.reorder_point
    avg_demand = inputs.average_daily_demand
    lead_time = inputs.lead_time_days
    is_below_reorder = avail <= rop

    # 1. Coverage Days (Runout duration)
    if avg_demand > 0.0:
        coverage_days = round(avail / avg_demand, 2)
        notes.append(
            f"Coverage days: {avail} units / {avg_demand:.2f} units/day = {coverage_days:.2f} days."
        )
    else:
        coverage_days = None
        notes.append("Coverage days: None (zero daily demand; no consumption depletion).")

    # 2. Expected Demand During Lead Time
    lead_time_demand = round(avg_demand * lead_time, 2)
    notes.append(
        f"Lead-time demand: {avg_demand:.2f} units/day * {lead_time} days = {lead_time_demand:.2f} units."
    )

    # 3. Lead-Time Stockout Deficit (Units Exposed)
    exposure_deficit = round(max(0.0, lead_time_demand - avail), 2)
    notes.append(
        f"Exposure deficit: max(0.0, {lead_time_demand:.2f} lead-time demand - {avail} available) = {exposure_deficit:.2f} units."
    )

    # 4. Buffer Days (Runway Gap relative to lead time)
    if coverage_days is not None:
        buffer_days = round(coverage_days - lead_time, 2)
        if buffer_days < 0.0:
            notes.append(
                f"Negative runway buffer: coverage ({coverage_days:.2f}d) is {abs(buffer_days):.2f} days shorter than lead time ({lead_time}d)."
            )
        else:
            notes.append(
                f"Positive runway buffer: coverage ({coverage_days:.2f}d) exceeds lead time ({lead_time}d) by {buffer_days:.2f} days."
            )
    else:
        buffer_days = None
        notes.append("Buffer days: None (zero daily demand).")

    # 5. Normalized Exposure Index in [0.0, 1.0]
    if lead_time_demand > 0.0:
        exposure_index = min(1.0, round(exposure_deficit / lead_time_demand, 4))
        notes.append(
            f"Exposure index: min(1.0, {exposure_deficit:.2f} deficit / {lead_time_demand:.2f} lead-time demand) = {exposure_index:.4f}."
        )
    else:
        if avail == 0 and avg_demand > 0.0:
            exposure_index = 1.0
            notes.append("Exposure index: 1.0000 (inventory is zero with positive daily demand; immediate stockout).")
        else:
            exposure_index = 0.0
            notes.append("Exposure index: 0.0000 (zero lead-time demand; zero exposure).")

    # 6. Demand Volatility Metrics (Dispersion)
    demand_std_dev: float | None = None
    demand_cv: float | None = None
    if inputs.historical_daily_demands is not None and len(inputs.historical_daily_demands) >= 2:
        hist = inputs.historical_daily_demands
        n = len(hist)
        mean_d = sum(hist) / n
        variance = sum((x - mean_d) ** 2 for x in hist) / (n - 1)
        demand_std_dev = round(math.sqrt(variance), 2)
        demand_cv = round(demand_std_dev / avg_demand, 2) if avg_demand > 0.0 else 0.0
        notes.append(
            f"Demand dispersion (N={n} days): sample std_dev={demand_std_dev:.2f}, coefficient_of_variation={demand_cv:.2f}."
        )

    # 7. Operational Risk Classification
    # Evaluate boundary and risk levels deterministically
    if avg_demand == 0.0:
        risk_level = StockoutRiskLevel.NO_DEMAND
        is_stockout_predicted = False
        notes.append("Classification: NO_DEMAND (historical average daily demand is 0.0; no consumption risk).")
    elif avail == 0:
        risk_level = StockoutRiskLevel.CRITICAL
        is_stockout_predicted = True
        notes.append("Classification: CRITICAL (available inventory is 0 with active daily demand; stockout present).")
    elif buffer_days is not None and buffer_days < 0.0:
        risk_level = StockoutRiskLevel.CRITICAL
        is_stockout_predicted = True
        notes.append(
            f"Classification: CRITICAL (coverage {coverage_days:.2f}d < lead time {lead_time}d; stockout projected before replenishment arrives)."
        )
    elif is_below_reorder or (buffer_days is not None and buffer_days <= 3.0):
        risk_level = StockoutRiskLevel.HIGH
        is_stockout_predicted = False
        notes.append(
            f"Classification: HIGH (available {avail} <= reorder_point {rop} or runway buffer <= 3.0 days)."
        )
    elif avail <= int(rop * 1.25) or (inputs.supplier_reliability is not None and inputs.supplier_reliability < 0.90):
        risk_level = StockoutRiskLevel.MEDIUM
        is_stockout_predicted = False
        notes.append(
            "Classification: MEDIUM (available inventory approaching reorder threshold <= 1.25x ROP, or degraded supplier reliability < 0.90)."
        )
    else:
        risk_level = StockoutRiskLevel.LOW
        is_stockout_predicted = False
        notes.append("Classification: LOW (healthy inventory coverage, buffer > 3.0 days, and available > 1.25x ROP).")

    formula = (
        "lead_time_demand = average_daily_demand * lead_time_days; "
        "coverage_days = available_quantity / average_daily_demand if average_daily_demand > 0 else None; "
        "buffer_days = coverage_days - lead_time_days if coverage_days is not None else None; "
        "exposure_deficit = max(0.0, lead_time_demand - available_quantity); "
        "exposure_index = min(1.0, exposure_deficit / lead_time_demand) if lead_time_demand > 0 else (1.0 if available == 0 and average_daily_demand > 0 else 0.0)"
    )

    assumptions = [
        "Historical average daily demand remains the expected consumption rate over the supplier lead-time window.",
        "Supplier lead time is constant and reflects the full procurement and fulfillment cycle.",
        "Available inventory (on-hand minus reserved) accurately represents unallocated stock.",
        "No unobserved replenishment orders or inbound transfers will arrive prior to the stated supplier lead time.",
    ]

    limitations = [
        "Does not compute statistical probability; the exposure_index represents the deterministic proportion of lead-time demand unfulfilled by current inventory.",
        "Does not account for non-stationary demand spikes, batch customer orders, or seasonal intraday shifts.",
        "Does not simulate stochastic lead-time distribution or random supply disruption events.",
        "Does not evaluate or recommend candidate actions; decision optimization is strictly deferred to downstream modules.",
    ]

    breakdown = StockoutRiskBreakdown(
        available_quantity=avail,
        reorder_point=rop,
        average_daily_demand=avg_demand,
        lead_time_days=lead_time,
        coverage_days=coverage_days,
        lead_time_demand=lead_time_demand,
        exposure_deficit=exposure_deficit,
        buffer_days=buffer_days,
        exposure_index=exposure_index,
        is_below_reorder=is_below_reorder,
        demand_std_dev=demand_std_dev,
        demand_coefficient_of_variation=demand_cv,
        supplier_reliability=inputs.supplier_reliability,
        calculation_notes=notes,
    )

    return StockoutRiskCalculationResult(
        product_id=inputs.product_id,
        warehouse_id=inputs.warehouse_id,
        model_type=inputs.model_type,
        risk_level=risk_level,
        exposure_index=exposure_index,
        is_stockout_predicted=is_stockout_predicted,
        is_probability=False,
        formula=formula,
        assumptions=assumptions,
        limitations=limitations,
        breakdown=breakdown,
    )
