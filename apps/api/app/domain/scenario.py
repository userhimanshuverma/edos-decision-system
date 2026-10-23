from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScenarioStatus(str, Enum):
    """Deterministic status outcome of a decision scenario execution.

    Semantics:
    - COMPLETED: Scenario recalculated and baseline comparison evaluated successfully.
    - INCOMPLETE: Required baseline inputs or rule definitions are missing or unavailable.
    - FAILED: Scenario execution failed due to an error, invalid reference, or runtime exception.
    """

    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


class ScenarioIncompleteReasonCode(str, Enum):
    """Categorical classification of reasons why a scenario cannot be reliably established."""

    MISSING_PROVENANCE_TRACE = "MISSING_PROVENANCE_TRACE"
    MISSING_INPUT_RECORD = "MISSING_INPUT_RECORD"
    UNAVAILABLE_HISTORICAL_INPUT = "UNAVAILABLE_HISTORICAL_INPUT"
    UNAVAILABLE_RULE_DEFINITION = "UNAVAILABLE_RULE_DEFINITION"
    MISSING_CANDIDATE_ACTIONS = "MISSING_CANDIDATE_ACTIONS"
    NO_RECORDED_RESULTS = "NO_RECORDED_RESULTS"
    UNSUPPORTED_OVERRIDE = "UNSUPPORTED_OVERRIDE"


class ScenarioIncompleteReason(BaseModel):
    """Actionable structured reason detailing an unavailable baseline input or unsupported scenario path."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: ScenarioIncompleteReasonCode = Field(..., description="Machine-readable incomplete reason category")
    message: str = Field(..., min_length=1, description="Concise human-readable explanation")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured contextual diagnostics")

    @field_validator("message")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Reason message must not be empty or whitespace-only")
        return trimmed


# ---------------------------------------------------------------------------
# Supported Scenario Overrides
# ---------------------------------------------------------------------------


class DemandOverride(BaseModel):
    """Controlled override of demand assumptions.

    Supports either an absolute average daily demand (units/day) or a proportional multiplier.
    Exactly one of demand_value or demand_multiplier must be provided.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    demand_value: float | None = Field(
        default=None,
        ge=0.0,
        description="Absolute average daily demand in units/day (non-negative)",
    )
    demand_multiplier: float | None = Field(
        default=None,
        ge=0.0,
        description="Proportional demand multiplier, e.g. 1.25 for +25% or 0.8 for -20%",
    )

    @model_validator(mode="after")
    def validate_single_demand_override(self) -> DemandOverride:
        has_val = self.demand_value is not None
        has_mult = self.demand_multiplier is not None
        if not has_val and not has_mult:
            raise ValueError("DemandOverride requires either 'demand_value' or 'demand_multiplier'")
        if has_val and has_mult:
            raise ValueError("DemandOverride cannot specify both 'demand_value' and 'demand_multiplier' simultaneously")
        return self


class LeadTimeOverride(BaseModel):
    """Controlled override of supplier fulfillment lead time (calendar days)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lead_time_days: int = Field(
        ...,
        ge=0,
        le=365,
        description="Fulfillment lead time in calendar days (0 to 365)",
    )


class CostOverride(BaseModel):
    """Controlled override of unit cost assumptions in standard currency (USD).

    Supports either an absolute unit cost or a proportional multiplier.
    Exactly one of unit_cost or cost_multiplier must be provided.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    unit_cost: float | None = Field(
        default=None,
        ge=0.0,
        description="Absolute catalog unit cost in standard currency USD (non-negative)",
    )
    cost_multiplier: float | None = Field(
        default=None,
        ge=0.0,
        description="Proportional unit-cost multiplier, e.g. 1.10 for +10% or 0.90 for -10%",
    )

    @model_validator(mode="after")
    def validate_single_cost_override(self) -> CostOverride:
        has_val = self.unit_cost is not None
        has_mult = self.cost_multiplier is not None
        if not has_val and not has_mult:
            raise ValueError("CostOverride requires either 'unit_cost' or 'cost_multiplier'")
        if has_val and has_mult:
            raise ValueError("CostOverride cannot specify both 'unit_cost' and 'cost_multiplier' simultaneously")
        return self


class ScenarioOverrides(BaseModel):
    """Typed container for scenario assumption overrides.

    EDOS Day 25 strictly supports only:
    1. Demand: demand_value or demand_multiplier
    2. Supplier lead time: lead_time_days
    3. Cost: unit_cost or cost_multiplier

    At least one override category must be provided. Unsupported override categories are forbidden.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    demand: DemandOverride | None = Field(default=None, description="Demand assumption override")
    lead_time: LeadTimeOverride | None = Field(default=None, description="Supplier lead time override")
    cost: CostOverride | None = Field(default=None, description="Product unit cost override")

    @model_validator(mode="after")
    def validate_at_least_one_override(self) -> ScenarioOverrides:
        if self.demand is None and self.lead_time is None and self.cost is None:
            raise ValueError("At least one scenario override (demand, lead_time, or cost) must be specified")
        return self


# ---------------------------------------------------------------------------
# Snapshots and Comparison Models
# ---------------------------------------------------------------------------


class ScenarioActionEvaluationSnapshot(BaseModel):
    """Evaluation snapshot for an individual candidate action within a scenario or baseline."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., min_length=1, description="Evaluated candidate action identifier")
    action_type: str | None = Field(default=None, description="Action type (e.g. PLACE_ORDER, SWITCH_SUPPLIER, DO_NOTHING)")
    scoring_status: str | None = Field(default=None, description="Action scoring status")
    overall_score: float | None = Field(default=None, description="Composite score if calculated")
    recommended_replenishment_quantity: int | None = Field(default=None, ge=0, description="Replenishment shortfall units")
    shortfall_addressed: int | None = Field(default=None, ge=0, description="Shortfall units addressed by this action")
    remaining_shortfall: int | None = Field(default=None, ge=0, description="Shortfall units remaining after action")
    exposure_index_delta: float | None = Field(default=None, description="Stockout exposure index delta")
    current_exposure_index: float | None = Field(default=None, ge=0.0, le=1.0, description="Baseline lead-time exposure index")
    projected_exposure_index: float | None = Field(default=None, ge=0.0, le=1.0, description="Projected lead-time exposure index")
    projected_risk_level: str | None = Field(default=None, description="Projected stockout risk level tier (LOW, MEDIUM, HIGH)")
    direct_procurement_cost: float | None = Field(default=None, ge=0.0, description="Direct purchase cost in USD")
    cost_status: str | None = Field(default=None, description="Cost calculability status")
    is_valid: bool | None = Field(default=None, description="Whether the action satisfies all hard constraints")
    violated_constraints: list[str] = Field(default_factory=list, description="Names of violated constraints if invalid")


class ScenarioResultSnapshot(BaseModel):
    """Normalized snapshot of decision results (baseline or scenario) for structured comparison."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_id: str | None = Field(default=None, description="Recommendation identifier")
    status: str | None = Field(default=None, description="Recommendation status (e.g. RECOMMENDED, NO_ACTION_REQUIRED)")
    recommended_action_id: str | None = Field(default=None, description="Selected candidate action identifier")
    recommended_action_type: str | None = Field(default=None, description="Selected candidate action type")
    tie_broken: bool | None = Field(default=None, description="Whether tie-breaking was triggered")
    tie_break_method: str | None = Field(default=None, description="Tie break method applied")
    selection_rule: str | None = Field(default=None, description="Selection rule applied")
    validation_status: str | None = Field(default=None, description="Decision-level constraint validation status")
    evaluations: dict[str, ScenarioActionEvaluationSnapshot] = Field(
        default_factory=dict,
        description="Action-level evaluation snapshots indexed by action_id",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary result metadata")


class MetricDelta(BaseModel):
    """Structured delta comparison for a single business metric between baseline and scenario."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    baseline_value: Any | None = Field(default=None, description="Observed baseline value")
    scenario_value: Any | None = Field(default=None, description="Recalculated scenario value")
    difference: Any | None = Field(default=None, description="Mathematical difference: scenario - baseline, or change description")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. units, USD, index [0-1], days)")


class ScenarioFieldDifference(BaseModel):
    """Granular field-level difference between baseline and scenario results."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    field_path: str = Field(..., min_length=1, description="Path representation of differing field")
    baseline_value: Any = Field(..., description="Observed baseline value")
    scenario_value: Any = Field(..., description="Recalculated scenario value")
    difference_description: str = Field(..., min_length=1, description="Deterministic explanation of the observed difference")

    @field_validator("field_path", "difference_description")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace-only")
        return trimmed


class ScenarioComparison(BaseModel):
    """Structured, deterministic comparison between baseline and scenario results."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_changed: bool = Field(
        ...,
        description="True if the selected candidate action or recommendation outcome changed under the scenario",
    )
    baseline_recommendation_id: str | None = Field(default=None, description="Baseline recommendation identifier")
    scenario_recommendation_id: str | None = Field(default=None, description="Scenario recommendation identifier")
    baseline_action_id: str | None = Field(default=None, description="Baseline selected action identifier")
    scenario_action_id: str | None = Field(default=None, description="Scenario selected action identifier")
    baseline_action_type: str | None = Field(default=None, description="Baseline selected action type")
    scenario_action_type: str | None = Field(default=None, description="Scenario selected action type")
    replenishment_quantity: MetricDelta = Field(..., description="Replenishment quantity comparison for recommended action")
    procurement_cost: MetricDelta = Field(..., description="Direct procurement cost comparison for recommended action")
    lead_time_exposure: MetricDelta = Field(..., description="Stockout exposure index comparison for recommended action")
    validation_status_changed: bool = Field(default=False, description="True if constraint validation status changed")
    baseline_validation_status: str | None = Field(default=None, description="Baseline validation status")
    scenario_validation_status: str | None = Field(default=None, description="Scenario validation status")
    newly_violated_constraints: list[str] = Field(
        default_factory=list,
        description="Constraints that passed in baseline but violated in scenario",
    )
    newly_satisfied_constraints: list[str] = Field(
        default_factory=list,
        description="Constraints that violated in baseline but satisfied in scenario",
    )
    differences: list[ScenarioFieldDifference] = Field(
        default_factory=list,
        description="Granular field differences across compared outputs",
    )
    compared_fields: list[str] = Field(
        default_factory=list,
        description="Explicit list of evaluated business fields",
    )
    summary: str = Field(..., min_length=1, description="Concise deterministic summary of the scenario comparison")

    @field_validator("summary")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Comparison summary must not be empty or whitespace-only")
        return trimmed


# ---------------------------------------------------------------------------
# Decision Scenario Forensic Record
# ---------------------------------------------------------------------------


class DecisionScenarioRecord(BaseModel):
    """Forensic record of a decision scenario execution.

    Maintains bidirectional traceability to the original decision, version snapshot,
    and baseline provenance trace without modifying historical state.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique scenario record identifier (SCN-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier (DEC-XXXX)")
    version_id: str | None = Field(default=None, description="Optional associated decision version identifier (VER-XXXX)")
    baseline_trace_id: str | None = Field(default=None, description="Associated baseline provenance trace (PRV-XXXX)")
    baseline_replay_id: str | None = Field(default=None, description="Associated baseline replay record (RPL-XXXX)")
    scenario_execution_id: str = Field(..., min_length=1, description="Unique scenario execution identifier (SCX-XXXX)")
    name: str | None = Field(default=None, description="Optional user-facing descriptive scenario name")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when scenario was evaluated",
    )
    status: ScenarioStatus = Field(..., description="Scenario execution outcome: COMPLETED, INCOMPLETE, FAILED")
    overrides: ScenarioOverrides = Field(..., description="Applied assumption overrides (demand, lead time, cost)")
    baseline_inputs_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of baseline operational inputs recovered from history",
    )
    applied_inputs_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of operational inputs effective after applying overrides",
    )
    baseline_result: ScenarioResultSnapshot | None = Field(default=None, description="Baseline execution outcome snapshot")
    scenario_result: ScenarioResultSnapshot | None = Field(default=None, description="Scenario recalculated outcome snapshot")
    comparison: ScenarioComparison | None = Field(default=None, description="Deterministic baseline-versus-scenario comparison")
    incomplete_reasons: list[ScenarioIncompleteReason] = Field(
        default_factory=list,
        description="Detailed reason codes if scenario is INCOMPLETE",
    )
    error_message: str | None = Field(default=None, description="Error diagnostics if scenario execution failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata")

    @field_validator("id", "decision_id", "scenario_execution_id")
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
    def validate_scenario_record_semantics(self) -> DecisionScenarioRecord:
        if self.status == ScenarioStatus.INCOMPLETE and not self.incomplete_reasons:
            raise ValueError("Scenario record marked INCOMPLETE must supply at least one incomplete_reason")
        if self.status == ScenarioStatus.COMPLETED and self.comparison is None:
            raise ValueError("Scenario record marked COMPLETED must supply a comparison result")
        if self.status == ScenarioStatus.FAILED and not self.error_message:
            raise ValueError("Scenario record marked FAILED must include an error_message")
        return self


# ---------------------------------------------------------------------------
# Deterministic Scenario Comparison Logic
# ---------------------------------------------------------------------------


SCENARIO_COMPARED_FIELDS: list[str] = [
    "recommendation.status",
    "recommendation.recommended_action_id",
    "recommendation.recommended_action_type",
    "validation.validation_status",
    "evaluations[*].recommended_replenishment_quantity",
    "evaluations[*].direct_procurement_cost",
    "evaluations[*].projected_exposure_index",
    "evaluations[*].projected_risk_level",
    "evaluations[*].is_valid",
]


def compare_scenario_results(
    baseline: ScenarioResultSnapshot,
    scenario: ScenarioResultSnapshot,
    overrides: ScenarioOverrides,
) -> ScenarioComparison:
    """Deterministically compares baseline execution results with scenario recalculation results.

    Requirements enforced:
    - Answers: 'How does the recommendation change under these assumptions?'
    - Explicit compared fields scope.
    - Zero arbitrary tolerances: exact numerical and categorical deltas.
    - Shows baseline value, scenario value, and difference wherever meaningful.
    - Represents unavailable values explicitly without treating missing values as zero.
    - Never describes stockout exposure as statistical probability.
    """
    differences: list[ScenarioFieldDifference] = []

    # 1. Recommendation Identity & Outcome Change
    rec_changed = (
        baseline.status != scenario.status
        or baseline.recommended_action_id != scenario.recommended_action_id
    )

    if baseline.status != scenario.status:
        differences.append(
            ScenarioFieldDifference(
                field_path="recommendation.status",
                baseline_value=baseline.status,
                scenario_value=scenario.status,
                difference_description=(
                    f"Recommendation status changed from '{baseline.status}' to '{scenario.status}'"
                ),
            )
        )

    if baseline.recommended_action_id != scenario.recommended_action_id:
        differences.append(
            ScenarioFieldDifference(
                field_path="recommendation.recommended_action_id",
                baseline_value=baseline.recommended_action_id,
                scenario_value=scenario.recommended_action_id,
                difference_description=(
                    f"Selected candidate action changed from '{baseline.recommended_action_id}' "
                    f"to '{scenario.recommended_action_id}'"
                ),
            )
        )

    if baseline.recommended_action_type != scenario.recommended_action_type:
        differences.append(
            ScenarioFieldDifference(
                field_path="recommendation.recommended_action_type",
                baseline_value=baseline.recommended_action_type,
                scenario_value=scenario.recommended_action_type,
                difference_description=(
                    f"Selected action type changed from '{baseline.recommended_action_type}' "
                    f"to '{scenario.recommended_action_type}'"
                ),
            )
        )

    # 2. Validation Status Change
    val_status_changed = baseline.validation_status != scenario.validation_status
    if val_status_changed:
        differences.append(
            ScenarioFieldDifference(
                field_path="validation.validation_status",
                baseline_value=baseline.validation_status,
                scenario_value=scenario.validation_status,
                difference_description=(
                    f"Constraint validation status changed from '{baseline.validation_status}' "
                    f"to '{scenario.validation_status}'"
                ),
            )
        )

    # 3. Action-Level Comparisons & Constraint Changes
    newly_violated: list[str] = []
    newly_satisfied: list[str] = []

    all_action_ids = sorted(list(set(baseline.evaluations.keys()) | set(scenario.evaluations.keys())))
    for act_id in all_action_ids:
        b_act = baseline.evaluations.get(act_id)
        s_act = scenario.evaluations.get(act_id)
        if b_act is None or s_act is None:
            continue

        # Check constraint validity changes
        if b_act.is_valid is not None and s_act.is_valid is not None:
            if b_act.is_valid != s_act.is_valid:
                differences.append(
                    ScenarioFieldDifference(
                        field_path=f"evaluations[{act_id}].is_valid",
                        baseline_value=b_act.is_valid,
                        scenario_value=s_act.is_valid,
                        difference_description=(
                            f"Action '{act_id}' validity changed from {b_act.is_valid} to {s_act.is_valid}"
                        ),
                    )
                )

        # Track newly violated or satisfied constraints
        b_violated = set(b_act.violated_constraints)
        s_violated = set(s_act.violated_constraints)
        for c in s_violated - b_violated:
            newly_violated.append(f"{act_id}:{c}")
        for c in b_violated - s_violated:
            newly_satisfied.append(f"{act_id}:{c}")

    # 4. Metric Deltas for Recommended Action (or primary action)
    target_rec_action_id = scenario.recommended_action_id or baseline.recommended_action_id
    b_target_eval = (
        baseline.evaluations.get(target_rec_action_id)
        if target_rec_action_id
        else next(iter(baseline.evaluations.values()), None)
    )
    s_target_eval = (
        scenario.evaluations.get(target_rec_action_id)
        if target_rec_action_id
        else next(iter(scenario.evaluations.values()), None)
    )

    # Replenishment Quantity Delta
    b_repl_qty = b_target_eval.recommended_replenishment_quantity if b_target_eval else None
    s_repl_qty = s_target_eval.recommended_replenishment_quantity if s_target_eval else None
    diff_repl_qty = (s_repl_qty - b_repl_qty) if (s_repl_qty is not None and b_repl_qty is not None) else None
    repl_delta = MetricDelta(
        baseline_value=b_repl_qty,
        scenario_value=s_repl_qty,
        difference=diff_repl_qty,
        unit="units",
    )
    if diff_repl_qty is not None and diff_repl_qty != 0:
        differences.append(
            ScenarioFieldDifference(
                field_path="recommendation.replenishment_quantity",
                baseline_value=b_repl_qty,
                scenario_value=s_repl_qty,
                difference_description=(
                    f"Recommended replenishment quantity changed from {b_repl_qty} to {s_repl_qty} units "
                    f"({'+' if diff_repl_qty > 0 else ''}{diff_repl_qty} units)"
                ),
            )
        )

    # Procurement Cost Delta
    b_cost = b_target_eval.direct_procurement_cost if b_target_eval else None
    s_cost = s_target_eval.direct_procurement_cost if s_target_eval else None
    diff_cost = round(s_cost - b_cost, 2) if (s_cost is not None and b_cost is not None) else None
    cost_delta = MetricDelta(
        baseline_value=b_cost,
        scenario_value=s_cost,
        difference=diff_cost,
        unit="USD",
    )
    if diff_cost is not None and diff_cost != 0.0:
        differences.append(
            ScenarioFieldDifference(
                field_path="recommendation.direct_procurement_cost",
                baseline_value=b_cost,
                scenario_value=s_cost,
                difference_description=(
                    f"Direct procurement cost changed from ${b_cost:,.2f} to ${s_cost:,.2f} "
                    f"({'+$' if diff_cost > 0 else '-$'}{abs(diff_cost):,.2f})"
                ),
            )
        )

    # Lead-Time Exposure Delta (Projected Exposure Index)
    b_exp = b_target_eval.projected_exposure_index if b_target_eval else None
    s_exp = s_target_eval.projected_exposure_index if s_target_eval else None
    diff_exp = round(s_exp - b_exp, 4) if (s_exp is not None and b_exp is not None) else None
    exp_delta = MetricDelta(
        baseline_value=b_exp,
        scenario_value=s_exp,
        difference=diff_exp,
        unit="exposure_index [0.0-1.0]",
    )
    if diff_exp is not None and diff_exp != 0.0:
        differences.append(
            ScenarioFieldDifference(
                field_path="recommendation.projected_exposure_index",
                baseline_value=b_exp,
                scenario_value=s_exp,
                difference_description=(
                    f"Deterministic projected exposure index changed from {b_exp:.4f} to {s_exp:.4f} "
                    f"({'+' if diff_exp > 0 else ''}{diff_exp:.4f})"
                ),
            )
        )

    # 5. Build Human-Readable Deterministic Summary
    summary_parts: list[str] = []
    if rec_changed:
        summary_parts.append(
            f"Scenario produced a DIFFERENT recommendation: baseline '{baseline.recommended_action_id}' "
            f"({baseline.recommended_action_type or baseline.status}) changed to "
            f"'{scenario.recommended_action_id}' ({scenario.recommended_action_type or scenario.status})."
        )
    else:
        summary_parts.append(
            f"Original recommendation remains VALID: '{baseline.recommended_action_id}' "
            f"({baseline.recommended_action_type or baseline.status})."
        )

    metric_parts: list[str] = []
    if diff_repl_qty is not None and diff_repl_qty != 0:
        metric_parts.append(f"replenishment quantity {'+' if diff_repl_qty > 0 else ''}{diff_repl_qty} units")
    if diff_cost is not None and diff_cost != 0.0:
        metric_parts.append(f"cost {'+$' if diff_cost > 0 else '-$'}{abs(diff_cost):,.2f}")
    if diff_exp is not None and diff_exp != 0.0:
        metric_parts.append(f"lead-time exposure index {'+' if diff_exp > 0 else ''}{diff_exp:.4f}")

    if metric_parts:
        summary_parts.append(f"Impact: {', '.join(metric_parts)}.")

    if newly_violated:
        summary_parts.append(f"Constraints newly violated: {', '.join(newly_violated)}.")
    if newly_satisfied:
        summary_parts.append(f"Constraints newly satisfied: {', '.join(newly_satisfied)}.")

    full_summary = " ".join(summary_parts)

    return ScenarioComparison(
        recommendation_changed=rec_changed,
        baseline_recommendation_id=baseline.recommendation_id,
        scenario_recommendation_id=scenario.recommendation_id,
        baseline_action_id=baseline.recommended_action_id,
        scenario_action_id=scenario.recommended_action_id,
        baseline_action_type=baseline.recommended_action_type,
        scenario_action_type=scenario.recommended_action_type,
        replenishment_quantity=repl_delta,
        procurement_cost=cost_delta,
        lead_time_exposure=exp_delta,
        validation_status_changed=val_status_changed,
        baseline_validation_status=baseline.validation_status,
        scenario_validation_status=scenario.validation_status,
        newly_violated_constraints=newly_violated,
        newly_satisfied_constraints=newly_satisfied,
        differences=differences,
        compared_fields=SCENARIO_COMPARED_FIELDS,
        summary=full_summary,
    )
