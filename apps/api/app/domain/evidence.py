from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceType(str, Enum):
    """Categorical nature of a decision evidence item.

    Strictly separates:
    - FACT: Directly observed operational data from catalog, inventory, supplier, or warehouse.
    - ASSUMPTION: Explicit operational or policy hypothesis adopted in decision modeling.
    - CALCULATION: Deterministic mathematical output produced by EDOS calculation services.
    """

    FACT = "FACT"
    ASSUMPTION = "ASSUMPTION"
    CALCULATION = "CALCULATION"


class EvidenceCategory(str, Enum):
    """Domain category of an evidence or assumption item."""

    INVENTORY = "INVENTORY"
    DEMAND = "DEMAND"
    SUPPLIER = "SUPPLIER"
    WAREHOUSE = "WAREHOUSE"
    REPLENISHMENT = "REPLENISHMENT"
    STOCKOUT_RISK = "STOCKOUT_RISK"
    CONSTRAINT_VALIDATION = "CONSTRAINT_VALIDATION"
    COST = "COST"
    ACTION_EVALUATION = "ACTION_EVALUATION"
    RECOMMENDATION = "RECOMMENDATION"
    OPERATIONAL = "OPERATIONAL"


class DecisionAssumption(BaseModel):
    """Explicitly formulated operational assumption supporting a decision.

    Guarantees:
    - Kept strictly distinct from observed physical facts and calculated values.
    - Identifies assumption rationale and source (e.g. system_default, policy_config, operator_stated).
    - Can optionally bind to specific candidate actions or decision versions.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique assumption identifier (ASM-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    category: EvidenceCategory = Field(..., description="Domain category of the assumption")
    statement: str = Field(..., min_length=1, description="Explicit human-readable assumption statement")
    assumed_value: Any | None = Field(default=None, description="Assumed numeric or structured parameter value")
    rationale: str | None = Field(default=None, description="Reason or justification for adopting this assumption")
    source: str | None = Field(default=None, description="Source of assumption: system_default, policy_config, operator_stated")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    version_id: str | None = Field(default=None, description="Associated decision version if version-specific")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata",
    )

    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("action_id", "version_id")
    @classmethod
    def validate_optional_identifiers(cls, value: str | None) -> str | None:
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                return None
            return trimmed
        return None

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def to_evidence(self) -> DecisionEvidence:
        """Converts this assumption to a typed DecisionEvidence entity."""
        return DecisionEvidence(
            id=self.id,
            decision_id=self.decision_id,
            evidence_type=EvidenceType.ASSUMPTION,
            category=self.category,
            description=self.statement,
            value=self.assumed_value,
            unit=None,
            source=self.source,
            is_probability=False,
            action_id=self.action_id,
            version_id=self.version_id,
            created_at=self.created_at,
            metadata={"rationale": self.rationale, **self.metadata} if self.rationale else self.metadata,
        )


class DecisionEvidence(BaseModel):
    """Strongly typed decision evidence item.

    Captures an individual observed fact, explicit assumption, or calculated output
    supporting an EDOS business decision.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique evidence identifier (EVD-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    evidence_type: EvidenceType = Field(..., description="Categorical nature: FACT, ASSUMPTION, or CALCULATION")
    category: EvidenceCategory = Field(..., description="Operational domain category")
    description: str = Field(..., min_length=1, description="Human-readable description of this evidence item")
    value: Any | None = Field(default=None, description="Structured value, metric, or concise payload")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. units, days, USD, ratio)")
    source: str | None = Field(default=None, description="Traceable reference identifying actual domain input or calculation")
    is_probability: bool = Field(
        default=False,
        description="Strictly False for deterministic exposure indicators; statistical probabilities require verified empirical distribution.",
    )
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    version_id: str | None = Field(default=None, description="Associated decision version if version-specific")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata",
    )

    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("action_id", "version_id")
    @classmethod
    def validate_optional_identifiers(cls, value: str | None) -> str | None:
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                return None
            return trimmed
        return None

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_exposure_probability_invariant(self) -> DecisionEvidence:
        """Enforces that deterministic exposure metrics are never labeled as empirical probabilities."""
        if self.category == EvidenceCategory.STOCKOUT_RISK and self.is_probability:
            raise ValueError(
                "Deterministic stockout risk exposure indicators cannot be labeled as empirical probabilities "
                "without statistical distribution parameters."
            )
        return self


class DecisionEvidenceSummary(BaseModel):
    """Concise count and categorical breakdown of evidence supporting a decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    total_items: int = Field(..., ge=0, description="Total evidence items")
    total_facts: int = Field(..., ge=0, description="Count of observed factual items")
    total_assumptions: int = Field(..., ge=0, description="Count of explicit assumptions")
    total_calculations: int = Field(..., ge=0, description="Count of calculated metrics")
    categories_represented: list[EvidenceCategory] = Field(
        default_factory=list,
        description="Distinct domain categories present in evidence",
    )
    actions_with_evidence: list[str] = Field(
        default_factory=list,
        description="Action identifiers that have associated evidence",
    )


class DecisionEvidenceSheet(BaseModel):
    """Consolidated evidence sheet capturing all supporting facts, assumptions, and calculations for a decision.

    Provides a comprehensive, explainable basis for why a decision was reached,
    allowing human operators and downstream AI explanation layers to inspect the rationale.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique evidence sheet identifier (EVS-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC sheet compilation timestamp",
    )
    items: list[DecisionEvidence] = Field(
        default_factory=list,
        description="All individual evidence items (facts, assumptions, calculations)",
    )
    assumptions: list[DecisionAssumption] = Field(
        default_factory=list,
        description="Explicit operational assumptions supporting this decision",
    )
    summary: DecisionEvidenceSummary = Field(
        ...,
        description="Categorical breakdown and counts",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata",
    )

    @field_validator("id", "decision_id", "product_id", "warehouse_id")
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

    @classmethod
    def create(
        cls,
        id: str,
        decision_id: str,
        product_id: str,
        warehouse_id: str,
        items: list[DecisionEvidence] | None = None,
        assumptions: list[DecisionAssumption] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEvidenceSheet:
        """Factory constructor computing summary metrics automatically."""
        ev_items = items or []
        asm_items = assumptions or []

        facts_count = sum(1 for item in ev_items if item.evidence_type == EvidenceType.FACT)
        calculations_count = sum(1 for item in ev_items if item.evidence_type == EvidenceType.CALCULATION)
        # Count assumptions from items plus any standalone assumptions
        assumptions_count = sum(1 for item in ev_items if item.evidence_type == EvidenceType.ASSUMPTION)
        if not assumptions_count and asm_items:
            assumptions_count = len(asm_items)

        total_count = len(ev_items)

        categories = sorted(
            list({item.category for item in ev_items}.union({asm.category for asm in asm_items})),
            key=lambda c: c.value,
        )
        actions = sorted(
            list(
                {item.action_id for item in ev_items if item.action_id}.union(
                    {asm.action_id for asm in asm_items if asm.action_id}
                )
            )
        )

        summary = DecisionEvidenceSummary(
            total_items=total_count,
            total_facts=facts_count,
            total_assumptions=assumptions_count,
            total_calculations=calculations_count,
            categories_represented=categories,
            actions_with_evidence=actions,
        )

        return cls(
            id=id,
            decision_id=decision_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            items=ev_items,
            assumptions=asm_items,
            summary=summary,
            metadata=metadata or {},
        )
