from __future__ import annotations

from enum import Enum
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplenishmentPolicyType(str, Enum):
    """Explicitly supported deterministic replenishment policies."""

    REORDER_POINT_DEFICIT = "REORDER_POINT_DEFICIT"
    LEAD_TIME_DEMAND = "LEAD_TIME_DEMAND"
    TARGET_STOCK = "TARGET_STOCK"


class ReplenishmentBreakdown(BaseModel):
    """Detailed, auditable mathematical breakdown of a replenishment calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    available_quantity: int = Field(..., description="Available unreserved inventory units")
    reorder_point: int = Field(..., ge=0, description="Replenishment trigger threshold")
    is_below_reorder: bool = Field(..., description="True if available_quantity <= reorder_point")
    target_stock: int = Field(..., ge=0, description="Target stock level determined by policy")
    net_deficit: int = Field(
        ...,
        ge=0,
        description="Units below reorder point: max(0, reorder_point - available_quantity)",
    )
    gross_deficit: int = Field(
        ...,
        ge=0,
        description="Units below target stock: max(0, target_stock - available_quantity)",
    )
    lead_time_days: int | None = Field(default=None, ge=0, description="Supplier lead time in days, if applicable")
    average_daily_demand: float | None = Field(
        default=None,
        ge=0.0,
        description="Historical average daily demand, if applicable",
    )
    lead_time_demand: int | None = Field(
        default=None,
        ge=0,
        description="Projected demand during lead time: ceil(average_daily_demand * lead_time_days)",
    )
    warehouse_capacity: int | None = Field(default=None, ge=0, description="Warehouse total storage capacity, if known")
    policy_notes: list[str] = Field(default_factory=list, description="Step-by-step auditable calculation notes")


class ReplenishmentCalculationInputs(BaseModel):
    """Strongly typed input parameters for deterministic replenishment calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    available_quantity: int = Field(..., description="Current available unreserved units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    policy_type: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to apply",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level for TARGET_STOCK policy",
    )
    average_daily_demand: float | None = Field(
        default=None,
        ge=0.0,
        description="Observed average daily demand for LEAD_TIME_DEMAND policy",
    )
    lead_time_days: int | None = Field(
        default=None,
        ge=0,
        description="Supplier lead time in days for LEAD_TIME_DEMAND policy",
    )
    warehouse_capacity: int | None = Field(
        default=None,
        ge=0,
        description="Warehouse physical storage capacity constraint, if known",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="When True, order quantity is 0 unless available_quantity <= reorder_point",
    )

    @model_validator(mode="after")
    def validate_policy_prerequisites(self) -> ReplenishmentCalculationInputs:
        if self.policy_type == ReplenishmentPolicyType.TARGET_STOCK:
            if self.target_stock is None:
                raise ValueError("target_stock is required when policy_type is TARGET_STOCK")
            if self.target_stock < self.reorder_point:
                raise ValueError(
                    f"target_stock ({self.target_stock}) cannot be less than reorder_point ({self.reorder_point})"
                )

        if self.policy_type == ReplenishmentPolicyType.LEAD_TIME_DEMAND:
            if self.average_daily_demand is None:
                raise ValueError("average_daily_demand is required when policy_type is LEAD_TIME_DEMAND")
            if self.lead_time_days is None:
                raise ValueError("lead_time_days is required when policy_type is LEAD_TIME_DEMAND")

        return self


class ReplenishmentCalculationResult(BaseModel):
    """Deterministic result of a replenishment quantity calculation.

    Answers: 'How much should we order under an explicitly defined replenishment policy?'
    Strictly does NOT evaluate candidate actions or make recommendations.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    policy_type: ReplenishmentPolicyType = Field(..., description="Replenishment policy applied")
    replenishment_quantity: int = Field(..., ge=0, description="Calculated deterministic order quantity")
    is_replenishment_needed: bool = Field(..., description="True if replenishment quantity > 0")
    available_quantity: int = Field(..., description="Available inventory units used by calculation")
    target_stock: int = Field(..., ge=0, description="Target stock level determined by policy")
    formula: str = Field(..., description="Textual description of the mathematical formula applied")
    breakdown: ReplenishmentBreakdown = Field(..., description="Detailed deterministic calculation breakdown")


def calculate_replenishment_quantity(
    inputs: ReplenishmentCalculationInputs,
) -> ReplenishmentCalculationResult:
    """Pure, deterministic calculation function for replenishment quantity.

    Requirements:
    - Pure function without HTTP, database, or network dependencies.
    - Deterministic: identical inputs always yield identical results.
    - Validates inputs and prevents negative quantities.
    - Handles zero demand, missing optional data, and boundary values safely.
    """
    notes: list[str] = []
    avail = inputs.available_quantity
    rop = inputs.reorder_point
    is_below_reorder = avail <= rop
    net_deficit = max(0, rop - avail)

    lead_time_demand: int | None = None
    target_stock: int

    if inputs.policy_type == ReplenishmentPolicyType.REORDER_POINT_DEFICIT:
        target_stock = rop
        formula = "replenishment_quantity = max(0, reorder_point - available_quantity) if available <= reorder_point else 0"
        notes.append(f"Policy REORDER_POINT_DEFICIT: Target stock set to reorder point ({rop}).")

    elif inputs.policy_type == ReplenishmentPolicyType.LEAD_TIME_DEMAND:
        avg_demand = inputs.average_daily_demand if inputs.average_daily_demand is not None else 0.0
        lead_time = inputs.lead_time_days if inputs.lead_time_days is not None else 0
        lead_time_demand = math.ceil(avg_demand * lead_time)
        target_stock = rop + lead_time_demand
        formula = (
            "lead_time_demand = ceil(average_daily_demand * lead_time_days); "
            "target_stock = reorder_point + lead_time_demand; "
            "replenishment_quantity = max(0, target_stock - available_quantity) if available <= reorder_point else 0"
        )
        notes.append(
            f"Policy LEAD_TIME_DEMAND: avg_daily_demand={avg_demand:.2f}, lead_time_days={lead_time} -> "
            f"lead_time_demand={lead_time_demand} units. Target stock = {rop} + {lead_time_demand} = {target_stock}."
        )

    elif inputs.policy_type == ReplenishmentPolicyType.TARGET_STOCK:
        assert inputs.target_stock is not None
        target_stock = inputs.target_stock
        formula = "replenishment_quantity = max(0, target_stock - available_quantity) if available <= reorder_point else 0"
        notes.append(f"Policy TARGET_STOCK: Explicit target stock specified as {target_stock}.")

    else:
        raise ValueError(f"Unsupported replenishment policy type: {inputs.policy_type}")

    gross_deficit = max(0, target_stock - avail)

    # Evaluate replenishment trigger condition
    if inputs.enforce_reorder_trigger and not is_below_reorder:
        replenishment_quantity = 0
        is_needed = False
        notes.append(
            f"Available inventory ({avail}) is above reorder point ({rop}). "
            "Reorder trigger not activated; replenishment quantity is 0."
        )
    else:
        replenishment_quantity = gross_deficit
        is_needed = replenishment_quantity > 0
        if is_needed:
            notes.append(
                f"Reorder triggered (available={avail} <= reorder_point={rop}). "
                f"Deficit to target ({target_stock}) is {replenishment_quantity} units."
            )
        else:
            notes.append(
                f"Available inventory ({avail}) meets or exceeds target stock ({target_stock}); "
                "no replenishment needed."
            )

    # Informational warehouse capacity audit (does not silently alter quantity)
    if inputs.warehouse_capacity is not None:
        projected = avail + replenishment_quantity
        if projected > inputs.warehouse_capacity:
            notes.append(
                f"Notice: Projected post-replenishment stock ({projected}) exceeds warehouse capacity "
                f"({inputs.warehouse_capacity})."
            )

    breakdown = ReplenishmentBreakdown(
        available_quantity=avail,
        reorder_point=rop,
        is_below_reorder=is_below_reorder,
        target_stock=target_stock,
        net_deficit=net_deficit,
        gross_deficit=gross_deficit,
        lead_time_days=inputs.lead_time_days,
        average_daily_demand=inputs.average_daily_demand,
        lead_time_demand=lead_time_demand,
        warehouse_capacity=inputs.warehouse_capacity,
        policy_notes=notes,
    )

    return ReplenishmentCalculationResult(
        product_id=inputs.product_id,
        warehouse_id=inputs.warehouse_id,
        policy_type=inputs.policy_type,
        replenishment_quantity=replenishment_quantity,
        is_replenishment_needed=is_needed,
        available_quantity=avail,
        target_stock=target_stock,
        formula=formula,
        breakdown=breakdown,
    )
