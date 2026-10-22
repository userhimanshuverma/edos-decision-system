from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReplayStatus(str, Enum):
    """Deterministic status outcome of a decision replay execution.

    Semantics:
    - MATCHED: Replay completed and the defined business comparison found equivalent results.
    - DIFFERENT: Replay completed, but meaningful business result fields differ from original.
    - INCOMPLETE: Required historical inputs or rule definitions are missing or unavailable.
    - FAILED: Replay execution failed due to an error, invalid reference, or runtime exception.
    """

    MATCHED = "MATCHED"
    DIFFERENT = "DIFFERENT"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


class IncompleteReasonCode(str, Enum):
    """Categorical classification of reasons why a historical execution cannot be replayed."""

    MISSING_PROVENANCE_TRACE = "MISSING_PROVENANCE_TRACE"
    MISSING_INPUT_RECORD = "MISSING_INPUT_RECORD"
    UNAVAILABLE_HISTORICAL_INPUT = "UNAVAILABLE_HISTORICAL_INPUT"
    UNAVAILABLE_RULE_DEFINITION = "UNAVAILABLE_RULE_DEFINITION"
    MISSING_CANDIDATE_ACTIONS = "MISSING_CANDIDATE_ACTIONS"
    NO_RECORDED_RESULTS = "NO_RECORDED_RESULTS"
    UNSUPPORTED_REPLAY_OPERATION = "UNSUPPORTED_REPLAY_OPERATION"


class IncompleteReason(BaseModel):
    """Actionable structured reason detailing an unavailable input or unsupported replay path."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: IncompleteReasonCode = Field(..., description="Machine-readable incomplete reason category")
    message: str = Field(..., min_length=1, description="Concise human-readable explanation")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured contextual diagnostics")

    @field_validator("message")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Reason message must not be empty or whitespace-only")
        return trimmed


class ReplayFieldDifference(BaseModel):
    """Granular field-level difference between original and replayed business outputs."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    field_path: str = Field(..., min_length=1, description="Dot-delimited or path representation of differing field")
    original_value: Any = Field(..., description="Observed original output value")
    replayed_value: Any = Field(..., description="Recomputed replayed output value")
    difference_description: str = Field(..., min_length=1, description="Explanation of how and why the values differ")

    @field_validator("field_path", "difference_description")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed


class ReplayActionEvaluationSnapshot(BaseModel):
    """Business metrics snapshot for an individual candidate action evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., min_length=1, description="Evaluated candidate action identifier")
    scoring_status: str | None = Field(default=None, description="Scoring status (e.g. COMPUTED, UNAVAILABLE)")
    overall_score: float | None = Field(default=None, description="Composite evaluation score")
    recommended_replenishment_quantity: int | None = Field(default=None, ge=0, description="Replenishment quantity")
    shortfall_addressed: int | None = Field(default=None, ge=0, description="Shortfall units addressed")
    remaining_shortfall: int | None = Field(default=None, ge=0, description="Shortfall units remaining")
    exposure_index_delta: float | None = Field(default=None, description="Stockout exposure index delta")
    current_exposure_index: float | None = Field(default=None, ge=0.0, description="Baseline exposure index")
    projected_exposure_index: float | None = Field(default=None, ge=0.0, description="Projected exposure index")
    direct_procurement_cost: float | None = Field(default=None, ge=0.0, description="Direct purchase cost")
    cost_status: str | None = Field(default=None, description="Cost calculability status")


class ReplayResultSnapshot(BaseModel):
    """Normalized snapshot of decision execution results for deterministic comparison."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_id: str | None = Field(default=None, description="Domain identifier of the recommendation")
    status: str | None = Field(default=None, description="Primary outcome status (e.g. RECOMMENDED, NO_ACTION_REQUIRED)")
    recommended_action_id: str | None = Field(default=None, description="Selected candidate action identifier")
    recommended_action_type: str | None = Field(default=None, description="Selected action type")
    tie_broken: bool | None = Field(default=None, description="Whether tie-breaking rule was triggered")
    tie_break_method: str | None = Field(default=None, description="Tie breaking method applied")
    selection_rule: str | None = Field(default=None, description="Selection strategy rule name applied")
    evaluations: dict[str, ReplayActionEvaluationSnapshot] = Field(
        default_factory=dict,
        description="Action-level evaluation snapshots indexed by action_id",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary result metadata")


class ReplayComparisonResult(BaseModel):
    """Structured, deterministic comparison between original and replayed execution results."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: ReplayStatus = Field(..., description="Comparison outcome: MATCHED or DIFFERENT")
    compared_fields: list[str] = Field(..., description="Explicit list of business fields evaluated in the comparison")
    ignored_fields: list[str] = Field(
        default_factory=list,
        description="Fields deliberately excluded from comparison (e.g. timestamps, transient IDs)",
    )
    differences: list[ReplayFieldDifference] = Field(
        default_factory=list,
        description="Field-level differences observed if status is DIFFERENT",
    )
    summary: str = Field(..., min_length=1, description="Concise human-readable comparison summary")

    @field_validator("summary")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Comparison summary must not be empty or whitespace-only")
        return trimmed

    @model_validator(mode="after")
    def validate_comparison_integrity(self) -> ReplayComparisonResult:
        if self.status == ReplayStatus.DIFFERENT and not self.differences:
            raise ValueError("Comparison marked DIFFERENT must provide at least one ReplayFieldDifference")
        if self.status == ReplayStatus.MATCHED and self.differences:
            raise ValueError("Comparison marked MATCHED cannot contain field differences")
        return self


class DecisionReplayRecord(BaseModel):
    """Forensic record of a decision replay execution.

    Maintains bidirectional traceability to the original decision, version snapshot,
    and provenance trace without overwriting original historical state.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique replay record identifier (RPL-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier (DEC-XXXX)")
    version_id: str | None = Field(default=None, description="Optional associated decision version identifier (VER-XXXX)")
    original_trace_id: str | None = Field(default=None, description="Associated original provenance trace (PRV-XXXX)")
    original_execution_id: str | None = Field(default=None, description="Execution ID of the original run")
    replay_execution_id: str = Field(..., min_length=1, description="Execution ID of this specific replay run (REX-XXXX)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the replay was executed",
    )
    status: ReplayStatus = Field(..., description="Replay outcome status: MATCHED, DIFFERENT, INCOMPLETE, FAILED")
    original_result: ReplayResultSnapshot | None = Field(default=None, description="Original recorded result snapshot")
    replayed_result: ReplayResultSnapshot | None = Field(default=None, description="Recomputed result snapshot")
    comparison: ReplayComparisonResult | None = Field(default=None, description="Field-by-field comparison result")
    incomplete_reasons: list[IncompleteReason] = Field(
        default_factory=list,
        description="Detailed reason codes if replay is INCOMPLETE",
    )
    error_message: str | None = Field(default=None, description="Error diagnostics if replay status is FAILED")
    reconstructed_inputs_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of historical inputs recovered for evaluation",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured execution metadata")

    @field_validator("id", "decision_id", "replay_execution_id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
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

    @model_validator(mode="after")
    def validate_replay_record_semantics(self) -> DecisionReplayRecord:
        if self.status == ReplayStatus.INCOMPLETE and not self.incomplete_reasons:
            raise ValueError("Replay record marked INCOMPLETE must supply at least one incomplete_reason")
        if self.status in (ReplayStatus.MATCHED, ReplayStatus.DIFFERENT) and self.comparison is None:
            raise ValueError(f"Replay record marked {self.status.value} must supply a comparison result")
        if self.status == ReplayStatus.FAILED and not self.error_message:
            raise ValueError("Replay record marked FAILED must include an error_message")
        return self


# ---------------------------------------------------------------------------
# Deterministic Comparison Logic
# ---------------------------------------------------------------------------

DEFAULT_COMPARED_FIELDS: list[str] = [
    "recommendation.status",
    "recommendation.recommended_action_id",
    "recommendation.recommended_action_type",
    "recommendation.tie_broken",
    "evaluations[*].scoring_status",
    "evaluations[*].overall_score",
    "evaluations[*].recommended_replenishment_quantity",
    "evaluations[*].shortfall_addressed",
    "evaluations[*].remaining_shortfall",
    "evaluations[*].exposure_index_delta",
    "evaluations[*].current_exposure_index",
    "evaluations[*].projected_exposure_index",
    "evaluations[*].direct_procurement_cost",
    "evaluations[*].cost_status",
]

DEFAULT_IGNORED_FIELDS: list[str] = [
    "created_at",
    "evaluated_at",
    "replay_execution_id",
    "original_execution_id",
    "id",
    "recommendation_id",
    "diagnostic_notes",
    "trace_id",
]


def compare_replay_results(
    original: ReplayResultSnapshot,
    replayed: ReplayResultSnapshot,
) -> ReplayComparisonResult:
    """Deterministically compares original recorded results with recomputed replayed results.

    Requirements enforced:
    - Explicit compared fields scope.
    - Zero arbitrary tolerances: exact value normalization.
    - Captures field-level difference details explaining what differs.
    - Returns MATCHED if and only if all evaluated fields are equivalent.
    """
    differences: list[ReplayFieldDifference] = []

    # 1. Recommendation outcome status
    if original.status != replayed.status:
        differences.append(
            ReplayFieldDifference(
                field_path="recommendation.status",
                original_value=original.status,
                replayed_value=replayed.status,
                difference_description=(
                    f"Recommendation status changed from '{original.status}' to '{replayed.status}'"
                ),
            )
        )

    # 2. Recommended action ID
    if original.recommended_action_id != replayed.recommended_action_id:
        differences.append(
            ReplayFieldDifference(
                field_path="recommendation.recommended_action_id",
                original_value=original.recommended_action_id,
                replayed_value=replayed.recommended_action_id,
                difference_description=(
                    f"Recommended action ID changed from '{original.recommended_action_id}' "
                    f"to '{replayed.recommended_action_id}'"
                ),
            )
        )

    # 3. Recommended action type
    if original.recommended_action_type != replayed.recommended_action_type:
        differences.append(
            ReplayFieldDifference(
                field_path="recommendation.recommended_action_type",
                original_value=original.recommended_action_type,
                replayed_value=replayed.recommended_action_type,
                difference_description=(
                    f"Recommended action type changed from '{original.recommended_action_type}' "
                    f"to '{replayed.recommended_action_type}'"
                ),
            )
        )

    # 4. Tie broken flag
    if original.tie_broken != replayed.tie_broken:
        differences.append(
            ReplayFieldDifference(
                field_path="recommendation.tie_broken",
                original_value=original.tie_broken,
                replayed_value=replayed.tie_broken,
                difference_description=(
                    f"Recommendation tie_broken changed from {original.tie_broken} to {replayed.tie_broken}"
                ),
            )
        )

    # 5. Candidate action evaluations comparison
    all_action_ids = sorted(list(set(original.evaluations.keys()) | set(replayed.evaluations.keys())))
    for act_id in all_action_ids:
        orig_ev = original.evaluations.get(act_id)
        repl_ev = replayed.evaluations.get(act_id)

        if orig_ev is None:
            differences.append(
                ReplayFieldDifference(
                    field_path=f"evaluations[{act_id}]",
                    original_value=None,
                    replayed_value="EVALUATED",
                    difference_description=f"Action '{act_id}' was evaluated in replay but was not present in original",
                )
            )
            continue

        if repl_ev is None:
            differences.append(
                ReplayFieldDifference(
                    field_path=f"evaluations[{act_id}]",
                    original_value="EVALUATED",
                    replayed_value=None,
                    difference_description=f"Action '{act_id}' was present in original but not evaluated in replay",
                )
            )
            continue

        # Sub-field comparisons
        metric_pairs = [
            ("scoring_status", orig_ev.scoring_status, repl_ev.scoring_status),
            ("overall_score", orig_ev.overall_score, repl_ev.overall_score),
            ("recommended_replenishment_quantity", orig_ev.recommended_replenishment_quantity, repl_ev.recommended_replenishment_quantity),
            ("shortfall_addressed", orig_ev.shortfall_addressed, repl_ev.shortfall_addressed),
            ("remaining_shortfall", orig_ev.remaining_shortfall, repl_ev.remaining_shortfall),
            ("exposure_index_delta", orig_ev.exposure_index_delta, repl_ev.exposure_index_delta),
            ("current_exposure_index", orig_ev.current_exposure_index, repl_ev.current_exposure_index),
            ("projected_exposure_index", orig_ev.projected_exposure_index, repl_ev.projected_exposure_index),
            ("direct_procurement_cost", orig_ev.direct_procurement_cost, repl_ev.direct_procurement_cost),
            ("cost_status", orig_ev.cost_status, repl_ev.cost_status),
        ]

        for metric_name, orig_val, repl_val in metric_pairs:
            # Handle float rounding / precision explicitly without arbitrary tolerance
            differs = False
            if orig_val is None and repl_val is None:
                differs = False
            elif orig_val is None or repl_val is None:
                differs = True
            elif isinstance(orig_val, float) and isinstance(repl_val, float):
                differs = round(orig_val, 6) != round(repl_val, 6)
            else:
                differs = orig_val != repl_val

            if differs:
                differences.append(
                    ReplayFieldDifference(
                        field_path=f"evaluations[{act_id}].{metric_name}",
                        original_value=orig_val,
                        replayed_value=repl_val,
                        difference_description=(
                            f"Action '{act_id}' {metric_name} changed from {orig_val} to {repl_val}"
                        ),
                    )
                )

    if differences:
        summary = (
            f"Replay completed with {len(differences)} meaningful difference(s) detected across business results."
        )
        return ReplayComparisonResult(
            status=ReplayStatus.DIFFERENT,
            compared_fields=DEFAULT_COMPARED_FIELDS,
            ignored_fields=DEFAULT_IGNORED_FIELDS,
            differences=differences,
            summary=summary,
        )

    return ReplayComparisonResult(
        status=ReplayStatus.MATCHED,
        compared_fields=DEFAULT_COMPARED_FIELDS,
        ignored_fields=DEFAULT_IGNORED_FIELDS,
        differences=[],
        summary="Replay completed with identical business results across all compared dimensions.",
    )
