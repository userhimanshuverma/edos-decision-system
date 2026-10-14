from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Union
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ActionType(str, Enum):
    """Constrained category of candidate operational interventions."""

    DO_NOTHING = "DO_NOTHING"
    PLACE_ORDER = "PLACE_ORDER"
    SWITCH_SUPPLIER = "SWITCH_SUPPLIER"


# Conceptual alias matching architecture naming
CandidateActionType = ActionType


class IneligibleSupplierError(ValueError):
    """Raised when a proposed supplier is inactive or not eligible according to domain data."""


class SupplierNotFoundError(ValueError):
    """Raised when a referenced supplier identifier does not exist in domain data."""


class DoNothingParameters(BaseModel):
    """Parameters for DO_NOTHING candidate action.

    Represents an intentional choice of no operational intervention.
    Strictly forbids extraneous parameters (e.g., quantities, suppliers).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PlaceOrderParameters(BaseModel):
    """Parameters for PLACE_ORDER candidate action.

    Represents a replenishment order with an explicitly specified, validated positive quantity.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )

    quantity: int = Field(
        ...,
        gt=0,
        description="Explicit replenishment order quantity (must be a strictly positive integer)",
    )

    @property
    def order_quantity(self) -> int:
        """Alias property for quantity."""
        return self.quantity

    @model_validator(mode="before")
    @classmethod
    def resolve_order_quantity_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            resolved = dict(data)
            if "quantity" not in resolved and "order_quantity" in resolved:
                resolved["quantity"] = resolved.pop("order_quantity")
            return resolved
        return data


class SwitchSupplierParameters(BaseModel):
    """Parameters for SWITCH_SUPPLIER candidate action.

    Identifies the proposed alternative target supplier for operational intervention.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )

    target_supplier_id: str = Field(
        ...,
        min_length=1,
        description="Proposed target supplier identifier",
    )

    @property
    def supplier_id(self) -> str:
        """Alias property for target_supplier_id."""
        return self.target_supplier_id

    @field_validator("target_supplier_id")
    @classmethod
    def validate_non_empty_target_supplier(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("target_supplier_id must not be empty or whitespace-only")
        return trimmed

    @model_validator(mode="before")
    @classmethod
    def resolve_supplier_id_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            resolved = dict(data)
            if "target_supplier_id" not in resolved and "supplier_id" in resolved:
                resolved["target_supplier_id"] = resolved.pop("supplier_id")
            return resolved
        return data



ActionParameters = Union[
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
]


class CandidateAction(BaseModel):
    """Strongly typed domain model representing a candidate action for a business decision.

    Answers 'What could we do?' by representing possible operational interventions
    (DO_NOTHING, PLACE_ORDER, SWITCH_SUPPLIER) without prematurely calculating, scoring,
    ranking, or recommending them.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: str = Field(..., min_length=1, description="Unique action identifier (ACT-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated decision identifier (DEC-XXXX)")
    action_type: ActionType = Field(..., alias="type", description="Constrained category of candidate action")
    parameters: ActionParameters = Field(..., description="Validated action-specific parameters")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    description: str | None = Field(default=None, description="Optional human-readable label or description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured metadata for the action")

    @property
    def action_id(self) -> str:
        """Alias property matching id."""
        return self.id

    @property
    def type(self) -> ActionType:
        """Alias property matching action_type."""
        return self.action_type

    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="before")
    @classmethod
    def parse_action_parameters(cls, data: Any) -> Any:
        """Parses parameter dictionary into the appropriate typed parameter model based on action_type."""
        if not isinstance(data, dict):
            return data

        raw_type = data.get("action_type") or data.get("type")
        resolved_type: ActionType | None = None
        if isinstance(raw_type, ActionType):
            resolved_type = raw_type
        elif isinstance(raw_type, str):
            try:
                resolved_type = ActionType(raw_type)
            except ValueError:
                # Let Pydantic's standard field validator reject unknown action_type
                return data

        raw_params = data.get("parameters")

        if resolved_type == ActionType.DO_NOTHING:
            if raw_params is None:
                data["parameters"] = DoNothingParameters()
            elif isinstance(raw_params, dict):
                data["parameters"] = DoNothingParameters(**raw_params)
        elif resolved_type == ActionType.PLACE_ORDER:
            if isinstance(raw_params, dict):
                data["parameters"] = PlaceOrderParameters(**raw_params)
        elif resolved_type == ActionType.SWITCH_SUPPLIER:
            if isinstance(raw_params, dict):
                data["parameters"] = SwitchSupplierParameters(**raw_params)

        return data

    @model_validator(mode="after")
    def validate_action_parameter_type_match(self) -> CandidateAction:
        """Ensures the parameter model strictly matches the action_type."""
        if self.action_type == ActionType.DO_NOTHING:
            if not isinstance(self.parameters, DoNothingParameters):
                raise ValueError(
                    f"Parameters for {self.action_type.value} must be DoNothingParameters, got {type(self.parameters).__name__}"
                )
        elif self.action_type == ActionType.PLACE_ORDER:
            if not isinstance(self.parameters, PlaceOrderParameters):
                raise ValueError(
                    f"Parameters for {self.action_type.value} must be PlaceOrderParameters, got {type(self.parameters).__name__}"
                )
        elif self.action_type == ActionType.SWITCH_SUPPLIER:
            if not isinstance(self.parameters, SwitchSupplierParameters):
                raise ValueError(
                    f"Parameters for {self.action_type.value} must be SwitchSupplierParameters, got {type(self.parameters).__name__}"
                )
        return self


def validate_supplier_eligibility(
    supplier_id: str,
    *,
    dataset: Any = None,
    supplier_repo: Any = None,
) -> Any:
    """Validates that a proposed target supplier exists and is eligible (active) according to domain data.

    Args:
        supplier_id: Identifier of the supplier to validate.
        dataset: Optional ShopFlowDataset to query.
        supplier_repo: Optional SupplierRepository to query.

    Returns:
        The validated Supplier domain entity.

    Raises:
        SupplierNotFoundError: If the supplier ID does not exist.
        IneligibleSupplierError: If the supplier exists but active is False.
    """
    norm_id = supplier_id.strip() if supplier_id else ""
    if not norm_id:
        raise SupplierNotFoundError("Supplier ID must not be empty or whitespace-only")

    supplier = None
    if supplier_repo is not None:
        supplier = supplier_repo.get_by_id(norm_id)
    elif dataset is not None:
        supplier = dataset.get_supplier(norm_id)
    else:
        from app.data.generator import generate_shopflow_dataset
        ds = generate_shopflow_dataset(seed=42)
        supplier = ds.get_supplier(norm_id)

    if supplier is None:
        raise SupplierNotFoundError(f"Supplier '{norm_id}' not found in domain data")

    if not supplier.active:
        raise IneligibleSupplierError(
            f"Supplier '{norm_id}' ({supplier.name}) is inactive and not eligible for intervention"
        )

    return supplier
