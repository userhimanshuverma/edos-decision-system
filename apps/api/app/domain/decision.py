from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DecisionStatus(str, Enum):
    """Minimal initial lifecycle status for an identifiable business decision."""

    DRAFT = "DRAFT"


class Decision(BaseModel):
    """Domain model representing the identity of a business decision.

    A decision is an identifiable operational entity associated with a specific
    product and warehouse context, tracked with a stable unique identifier
    and UTC timestamp.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the decision")
    product_id: str = Field(..., min_length=1, description="Associated product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Associated warehouse identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    status: DecisionStatus = Field(
        default=DecisionStatus.DRAFT,
        description="Minimal initial decision state",
    )

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        """Ensures creation timestamp is timezone-aware and normalized to UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
