from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.decision import DecisionStatus


class DecisionEventType(str, Enum):
    """Constrained types of decision lifecycle audit events."""

    DECISION_CREATED = "DECISION_CREATED"
    LIFECYCLE_TRANSITION = "LIFECYCLE_TRANSITION"


class DecisionEvent(BaseModel):
    """Domain model representing an immutable audit event for an operational decision.

    Captures lifecycle state changes, timestamps, and decision references
    for deterministic auditability and forensic traceability.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the decision event")
    decision_id: str = Field(..., min_length=1, description="Associated decision identifier")
    event_type: DecisionEventType = Field(
        ...,
        description="Constrained event type representing the lifecycle change",
    )
    from_status: DecisionStatus | None = Field(
        default=None,
        description="Previous lifecycle status where applicable",
    )
    to_status: DecisionStatus = Field(
        ...,
        description="Target lifecycle status",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the event occurred",
    )

    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("occurred_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        """Ensures occurrence timestamp is timezone-aware and normalized to UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_event_semantics(self) -> DecisionEvent:
        """Enforces semantic consistency for creation and transition events."""
        if self.event_type == DecisionEventType.DECISION_CREATED:
            if self.from_status is not None:
                raise ValueError("DECISION_CREATED event cannot have a previous status (from_status must be None)")
            if self.to_status != DecisionStatus.DRAFT:
                raise ValueError(f"DECISION_CREATED event must have initial status DRAFT, got '{self.to_status.value}'")
        elif self.event_type == DecisionEventType.LIFECYCLE_TRANSITION:
            if self.from_status is None:
                raise ValueError("LIFECYCLE_TRANSITION event must have a preceding status (from_status cannot be None)")
            if self.from_status == self.to_status:
                raise ValueError(f"LIFECYCLE_TRANSITION event cannot transition to the same status '{self.to_status.value}'")
        return self
