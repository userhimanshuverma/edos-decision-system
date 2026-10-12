from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.context import DecisionContext
from app.domain.decision import Decision, DecisionStatus


class DecisionSnapshot(BaseModel):
    """Immutable snapshot capturing the operational state of a decision at version creation time.

    Contains the essential attributes representing what the decision was at that point
    in time, with optional situational context if available.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision_id: str = Field(..., min_length=1, description="Associated decision identifier")
    product_id: str = Field(..., min_length=1, description="Snapshot product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Snapshot warehouse identifier")
    status: DecisionStatus = Field(..., description="Lifecycle status at snapshot time")
    decision_created_at: datetime = Field(
        ...,
        description="Original creation timestamp of the snapshotted decision (UTC)",
    )
    context: DecisionContext | None = Field(
        default=None,
        description="Optional situational operational context captured at snapshot time",
    )

    @field_validator("decision_id", "product_id", "warehouse_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("decision_created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        """Ensures decision creation timestamp is timezone-aware and normalized to UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def from_decision(
        cls,
        decision: Decision,
        context: DecisionContext | None = None,
    ) -> DecisionSnapshot:
        """Constructs an immutable DecisionSnapshot from a Decision entity."""
        return cls(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            status=decision.status,
            decision_created_at=decision.created_at,
            context=context.model_copy(deep=True) if context is not None else None,
        )


class DecisionVersion(BaseModel):
    """Domain model representing a historical, immutable version of a business decision.

    Guarantees:
    - Positive, deterministic version numbering within a decision.
    - Timezone-aware UTC timestamp marking when this version was created.
    - Immutable snapshot of decision data at creation time.
    - Defensive immutability against later state mutations.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the decision version (VER-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated decision identifier")
    version_number: int = Field(..., ge=1, description="Positive sequential version number for this decision")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the version was captured",
    )
    snapshot: DecisionSnapshot = Field(..., description="Data snapshot representing this version")
    description: str | None = Field(
        default=None,
        description="Optional human-readable explanation or change note for this version",
    )

    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("version_number")
    @classmethod
    def validate_positive_version_number(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Version number must be a positive integer (>= 1)")
        return value

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        """Ensures creation timestamp is timezone-aware and normalized to UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
