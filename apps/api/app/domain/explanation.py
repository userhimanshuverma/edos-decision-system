from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DecisionExplanationContext(BaseModel):
    """Context assembled deterministically from recorded decision data for LLM explanation.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."

    Guarantees:
    - Only incorporates recorded facts, deterministic calculation results, and explicit assumptions.
    - Never fabricates evidence, provenance, replay, or scenario results.
    - Preserves decision and version linkage.
    - Highlights missing information and limitations rather than assuming complete data.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    decision_version_id: str | None = Field(default=None, description="Associated historical decision version identifier if linked")
    product_id: str = Field(..., min_length=1, description="Associated product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Associated warehouse identifier")
    decision_status: str = Field(..., description="Current lifecycle status of the decision")
    recommendation_status: str | None = Field(default=None, description="Outcome status of the recommendation engine")
    recommended_action_id: str | None = Field(default=None, description="Candidate action ID recommended by system")
    recommended_action_type: str | None = Field(default=None, description="Type of candidate action recommended")
    selection_rule: str | None = Field(default=None, description="Deterministic rule used for recommendation selection")
    selection_rationale: str | None = Field(default=None, description="Deterministic selection rationale")
    action_parameters: dict[str, Any] = Field(default_factory=dict, description="Operational parameters of the recommended action")
    calculation_results: list[dict[str, Any]] = Field(default_factory=list, description="Deterministic calculation outputs (replenishment, stockout risk, evaluations)")
    constraint_results: list[dict[str, Any]] = Field(default_factory=list, description="Evaluated constraint outcomes from validation report")
    evidence_items: list[dict[str, Any]] = Field(default_factory=list, description="Individual grounded facts and evidence references with stable IDs")
    assumptions: list[dict[str, Any]] = Field(default_factory=list, description="Explicit operational hypotheses and policy assumptions with stable IDs")
    provenance_trace_id: str | None = Field(default=None, description="Lineage trace identifier if recorded")
    replay_summary: dict[str, Any] | None = Field(default=None, description="Replay verification outcome if executed")
    scenario_summary: dict[str, Any] | None = Field(default=None, description="What-if scenario comparison if executed")
    known_limitations: list[str] = Field(default_factory=list, description="Explicit operational limitations known to the system")
    missing_information: list[str] = Field(default_factory=list, description="Missing or unavailable inputs explicitly disclosed")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when context was assembled",
    )

    @field_validator("collected_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class DecisionExplanation(BaseModel):
    """Structured, auditable explanation produced by a local LLM for a human reviewer.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."

    The explanation:
    - Explains the deterministic recommendation already produced by EDOS.
    - Cites only supporting evidence and calculation identifiers present in the decision context.
    - Explicitly separates recorded facts and calculations from assumptions, missing information, and risks.
    - Never modifies recommendations, calculates business numbers, or approves decisions.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    decision_version_id: str | None = Field(default=None, description="Associated decision version identifier if version-scoped")
    recommendation_summary: str = Field(..., min_length=1, description="Clear, human-readable summary of the system recommendation")
    reasoning_summary: str = Field(..., min_length=1, description="Concise rationale grounded strictly in supplied facts and calculation results")
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="References to known evidence IDs or recorded calculation IDs present in the supplied context",
    )
    risks_and_constraints: list[str] = Field(
        default_factory=list,
        description="Operational risks, evaluated constraints, and threshold considerations",
    )
    assumptions_and_missing_information: list[str] = Field(
        default_factory=list,
        description="Explicit operational assumptions and material missing or incomplete inputs",
    )
    review_considerations: list[str] = Field(
        default_factory=list,
        description="Actionable considerations and trade-offs for the human reviewer prior to approval",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Known operational and model limitations",
    )
    model_name: str = Field(..., min_length=1, description="Local Ollama model identifier that generated the narrative")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of explanation generation",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Runtime execution metadata")

    @field_validator("generated_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class DecisionQuestionStatus(str, Enum):
    """Evaluation status for a decision Q&A query."""

    ANSWERED = "ANSWERED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    UNANSWERABLE = "UNANSWERABLE"


class DecisionQuestionAnswer(BaseModel):
    """Structured, auditable answer to a natural-language question regarding a specific decision.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."

    Guarantees:
    - Grounded strictly in the decision's recorded context and calculation results.
    - Cites only validated evidence, calculation, or action IDs from context.
    - Does not mutate recommendations, calculate new numbers, or approve decisions.
    - Transparently reports when data is incomplete or unavailable.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    decision_version_id: str | None = Field(default=None, description="Associated decision version identifier if version-scoped")
    question: str = Field(..., min_length=1, description="Original reviewer question")
    answer: str = Field(..., min_length=1, description="Grounded, auditable answer produced by local LLM")
    status: DecisionQuestionStatus = Field(
        default=DecisionQuestionStatus.ANSWERED,
        description="Outcome status of the question evaluation",
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="References to verified evidence IDs or recorded calculation IDs from context",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Explicit limitations, missing data caveats, or boundaries disclosed in the response",
    )
    model_name: str = Field(..., min_length=1, description="Configured local model identifier that generated the response")
    answered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of question answering",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Runtime execution metadata")

    @field_validator("answered_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
