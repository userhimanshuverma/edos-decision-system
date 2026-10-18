from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.domain.action_evaluation import (
    ActionEvaluationResult,
    EvaluationEvidence,
    EvaluationCostStatus,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
)
from app.domain.replenishment import ReplenishmentPolicyType


class RecommendationStatus(str, Enum):
    """Categorical status of a recommendation generation run."""

    RECOMMENDED = "RECOMMENDED"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"
    NO_CANDIDATE_ACTIONS = "NO_CANDIDATE_ACTIONS"
    NO_ELIGIBLE_ACTION = "NO_ELIGIBLE_ACTION"
    ALL_EVALUATIONS_FAILED = "ALL_EVALUATIONS_FAILED"


class TieBreakMethod(str, Enum):
    """Specific deterministic method used to break ties between candidate actions."""

    NONE = "NONE"
    ACTION_TYPE_PRIORITY = "ACTION_TYPE_PRIORITY"
    EARLIEST_TIMESTAMP = "EARLIEST_TIMESTAMP"
    ACTION_IDENTIFIER = "ACTION_IDENTIFIER"


class AlternativeComparison(BaseModel):
    """Auditable comparison summary for a candidate action considered by the engine."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., min_length=1, description="Candidate action identifier")
    action_type: ActionType = Field(..., description="Candidate action type")
    is_eligible: bool = Field(..., description="Whether action met operational eligibility criteria")
    ineligibility_reason: str | None = Field(default=None, description="Reason if action was marked ineligible")
    rank: int | None = Field(default=None, ge=1, description="1-indexed priority rank among evaluated alternatives")
    shortfall_satisfaction_ratio: float | None = Field(default=None, ge=0.0, description="Replenishment shortfall satisfaction ratio")
    shortfall_addressed: int | None = Field(default=None, ge=0, description="Shortfall units addressed")
    excess_quantity: int | None = Field(default=None, ge=0, description="Units ordered in excess of target")
    exposure_index_delta: float | None = Field(default=None, description="Stockout exposure index delta")
    effective_supplier_risk: str | None = Field(default=None, description="Supplier risk tier effective under action")
    effective_lead_time_days: int | None = Field(default=None, ge=0, description="Effective supplier fulfillment lead time")
    effective_reliability: float | None = Field(default=None, ge=0.0, le=1.0, description="Effective supplier reliability")
    direct_procurement_cost: float | None = Field(default=None, ge=0.0, description="Calculated direct purchase cost")
    cost_status: str | None = Field(default=None, description="Cost status classification")
    selection_notes: list[str] = Field(default_factory=list, description="Step-by-step ranking evaluation notes")


class Recommendation(BaseModel):
    """Deterministic recommendation selected from evaluated candidate actions.

    Adheres to the core principle:
    "The system calculates. AI explains. Humans approve."
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique recommendation identifier (REC-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    product_id: str = Field(..., min_length=1, description="Associated product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Associated warehouse identifier")
    status: RecommendationStatus = Field(..., description="Recommendation outcome status")
    selection_rule: str = Field(
        default="LEXICOGRAPHIC_OPERATIONAL_DOMINANCE",
        description="Name of deterministic rule used to select recommendation",
    )
    recommended_action_id: str | None = Field(
        default=None,
        description="Action identifier of the selected recommendation",
    )
    recommended_action_type: ActionType | None = Field(
        default=None,
        description="Action type of the selected recommendation",
    )
    recommended_action: CandidateAction | None = Field(
        default=None,
        description="Defensive deep copy of the selected candidate action",
    )
    selection_rationale: str = Field(
        ...,
        min_length=1,
        description="Transparent deterministic rationale explaining why this action was selected",
    )
    tie_broken: bool = Field(
        default=False,
        description="True if selection required breaking a tie between identical evaluations",
    )
    tie_break_method: TieBreakMethod = Field(
        default=TieBreakMethod.NONE,
        description="Method used if a tie had to be broken",
    )
    tie_breaking_rationale: str | None = Field(
        default=None,
        description="Detailed explanation of tie-breaking resolution",
    )
    total_actions_evaluated: int = Field(
        ...,
        ge=0,
        description="Total candidate actions considered during selection",
    )
    alternatives: list[AlternativeComparison] = Field(
        default_factory=list,
        description="Auditable summary of all candidate actions compared",
    )
    evaluation_evidence: EvaluationEvidence | None = Field(
        default=None,
        description="Preserved evaluation evidence for the recommended action",
    )
    selected_evaluation: ActionEvaluationResult | None = Field(
        default=None,
        description="Preserved full evaluation result of the selected candidate action",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC recommendation generation timestamp",
    )
    is_fresh: bool = Field(
        default=True,
        description="True if the recommendation reflects the latest candidate actions and inventory state",
    )
    stale_reason: str | None = Field(
        default=None,
        description="Reason if the recommendation has been determined to be stale",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata",
    )



# Priority order of action types when replenishment is actively needed
ACTION_TYPE_PRIORITY_REPLENISHMENT: dict[ActionType, int] = {
    ActionType.PLACE_ORDER: 0,
    ActionType.SWITCH_SUPPLIER: 1,
    ActionType.DO_NOTHING: 2,
}

# Priority order of action types when no replenishment is needed
ACTION_TYPE_PRIORITY_NO_REPLENISHMENT: dict[ActionType, int] = {
    ActionType.DO_NOTHING: 0,
    ActionType.SWITCH_SUPPLIER: 1,
    ActionType.PLACE_ORDER: 2,
}

# Supplier risk tier numeric weights for deterministic comparison (lower is better)
SUPPLIER_RISK_ORDER: dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}


def select_deterministic_recommendation(
    decision_id: str,
    product_id: str,
    warehouse_id: str,
    evaluations: list[ActionEvaluationResult],
    candidate_actions: list[CandidateAction],
    *,
    recommendation_id: str = "REC-0001",
    policy_type: ReplenishmentPolicyType | str | None = None,
    failed_evaluations: dict[str, str] | None = None,
) -> Recommendation:
    """Pure, deterministic selection of a final recommendation from evaluated candidate actions.

    Applies the Lexicographic Operational Dominance (LOD) policy:
    1. Operational Need: If shortfall == 0, prefer DO_NOTHING (NO_ACTION_REQUIRED).
    2. Shortfall Satisfaction: Maximize shortfall satisfaction ratio S_ratio.
    3. Excess Avoidance: Minimize excess units above target Q_excess.
    4. Stockout Exposure: Maximize exposure reduction (most negative delta_I_exposure).
    5. Supplier Dependability: Prefer LOW operational risk, higher reliability, shorter lead time.
    6. Procurement Cost: Prefer lower direct procurement cost.
    7. Deterministic Tie-Breaker: Action type priority -> Earliest timestamp -> Ascending action_id.

    Guarantees:
    - Pure calculation with zero side effects.
    - Deterministic output: Identical inputs always produce identical recommendations.
    - Full traceability of alternatives and evaluation evidence.
    """
    failed_map = failed_evaluations or {}
    total_actions_considered = len(candidate_actions)

    # Edge Case 1: No candidate actions exist
    if total_actions_considered == 0:
        return Recommendation(
            id=recommendation_id,
            decision_id=decision_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            status=RecommendationStatus.NO_CANDIDATE_ACTIONS,
            selection_rationale="No candidate actions have been constructed for this decision. Cannot generate a recommendation.",
            tie_broken=False,
            tie_break_method=TieBreakMethod.NONE,
            total_actions_evaluated=0,
            alternatives=[],
            recommended_action_id=None,
            recommended_action_type=None,
            recommended_action=None,
            evaluation_evidence=None,
            selected_evaluation=None,
        )

    # Edge Case 2: All evaluations failed
    if len(evaluations) == 0 and len(failed_map) > 0:
        alternatives = [
            AlternativeComparison(
                action_id=action.id,
                action_type=action.action_type,
                is_eligible=False,
                ineligibility_reason=failed_map.get(action.id, "Evaluation failed"),
                selection_notes=[f"Evaluation could not be performed: {failed_map.get(action.id, 'Unknown error')}."],
            )
            for action in candidate_actions
        ]
        return Recommendation(
            id=recommendation_id,
            decision_id=decision_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            status=RecommendationStatus.ALL_EVALUATIONS_FAILED,
            selection_rationale="All candidate action evaluations failed due to missing operational or catalog data. Cannot determine a recommendation.",
            tie_broken=False,
            tie_break_method=TieBreakMethod.NONE,
            total_actions_evaluated=total_actions_considered,
            alternatives=alternatives,
            recommended_action_id=None,
            recommended_action_type=None,
            recommended_action=None,
            evaluation_evidence=None,
            selected_evaluation=None,
        )

    # Map evaluations and candidate actions by action_id
    eval_by_id: dict[str, ActionEvaluationResult] = {e.action_id: e for e in evaluations}

    # Determine if replenishment shortfall exists from evaluations
    # All evaluations for the same decision evaluate against the same baseline inventory and policy
    is_replenishment_needed = False
    recommended_qty = 0
    resolved_policy_str = (
        policy_type.value if hasattr(policy_type, "value") else str(policy_type)
    ) if policy_type else "REORDER_POINT_DEFICIT"

    if evaluations:
        first_eval = evaluations[0]
        is_replenishment_needed = first_eval.replenishment_impact.is_replenishment_needed
        recommended_qty = first_eval.replenishment_impact.recommended_replenishment_quantity
        resolved_policy_str = first_eval.replenishment_impact.policy_type.value

    # Evaluate eligibility of candidate actions
    eligible_entries: list[tuple[CandidateAction, ActionEvaluationResult]] = []
    ineligible_alternatives: list[AlternativeComparison] = []

    for action in candidate_actions:
        if action.id in failed_map:
            ineligible_alternatives.append(
                AlternativeComparison(
                    action_id=action.id,
                    action_type=action.action_type,
                    is_eligible=False,
                    ineligibility_reason=failed_map[action.id],
                    selection_notes=[f"Action excluded from recommendation: {failed_map[action.id]}"],
                )
            )
            continue

        eval_res = eval_by_id.get(action.id)
        if eval_res is None:
            ineligible_alternatives.append(
                AlternativeComparison(
                    action_id=action.id,
                    action_type=action.action_type,
                    is_eligible=False,
                    ineligibility_reason="Missing evaluation result",
                    selection_notes=["Action was not evaluated."],
                )
            )
            continue

        eligible_entries.append((action, eval_res))

    # Edge Case 3: No eligible actions remain
    if not eligible_entries:
        return Recommendation(
            id=recommendation_id,
            decision_id=decision_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            status=RecommendationStatus.NO_ELIGIBLE_ACTION,
            selection_rationale="No candidate actions satisfied operational eligibility requirements.",
            tie_broken=False,
            tie_break_method=TieBreakMethod.NONE,
            total_actions_evaluated=total_actions_considered,
            alternatives=ineligible_alternatives,
            recommended_action_id=None,
            recommended_action_type=None,
            recommended_action=None,
            evaluation_evidence=None,
            selected_evaluation=None,
        )

    # SCENARIO A: No Replenishment Needed (Shortfall == 0)
    if not is_replenishment_needed or recommended_qty == 0:
        # Search for DO_NOTHING action among eligible actions
        do_nothing_entry = next(
            (e for e in eligible_entries if e[0].action_type == ActionType.DO_NOTHING),
            None,
        )

        ranked_alternatives: list[AlternativeComparison] = []

        if do_nothing_entry is not None:
            chosen_action, chosen_eval = do_nothing_entry
            has_exposure_deficit = chosen_eval.stockout_exposure.current_exposure_deficit > 0.0

            if not has_exposure_deficit:
                rationale = (
                    f"Inventory level is healthy above the reorder threshold (calculated replenishment shortfall is 0 units "
                    f"under {resolved_policy_str}). Taking no operational intervention preserves capital with $0.00 direct "
                    f"procurement cost and avoids unnecessary inventory holding excess."
                )
            else:
                rationale = (
                    f"Replenishment threshold is not triggered under policy {resolved_policy_str} (calculated shortfall is 0 units). "
                    f"However, baseline lead-time exposure deficit remains {chosen_eval.stockout_exposure.current_exposure_deficit:.1f} units "
                    f"(risk: {chosen_eval.stockout_exposure.current_risk_level.value}). "
                    f"DO_NOTHING preserves capital with $0.00 direct procurement cost while baseline lead-time exposure persists."
                )

            # Build comparison list with DO_NOTHING at rank 1
            rank = 1
            # Primary choice
            ranked_alternatives.append(
                AlternativeComparison(
                    action_id=chosen_action.id,
                    action_type=chosen_action.action_type,
                    is_eligible=True,
                    rank=rank,
                    shortfall_satisfaction_ratio=1.0,
                    shortfall_addressed=0,
                    excess_quantity=0,
                    exposure_index_delta=chosen_eval.stockout_exposure.exposure_index_delta,
                    effective_supplier_risk=chosen_eval.supplier_impact.effective_supplier_risk.value,
                    effective_lead_time_days=chosen_eval.supplier_impact.effective_lead_time_days,
                    effective_reliability=chosen_eval.supplier_impact.effective_reliability,
                    direct_procurement_cost=0.0,
                    cost_status=chosen_eval.cost_impact.cost_status.value,
                    selection_notes=[
                        "Rank 1 (Selected): DO_NOTHING preserves capital at zero direct procurement cost.",
                    ],
                )
            )

            # Other alternatives ordered by excess quantity and cost
            other_entries = [e for e in eligible_entries if e[0].id != chosen_action.id]
            # Sort other actions
            other_entries.sort(
                key=lambda item: (
                    item[1].replenishment_impact.excess_quantity,
                    0 if item[1].cost_impact.cost_status == EvaluationCostStatus.ZERO_COST else (
                        1 if item[1].cost_impact.cost_status == EvaluationCostStatus.CALCULATED else 2
                    ),
                    item[1].cost_impact.direct_procurement_cost if item[1].cost_impact.direct_procurement_cost is not None else float("inf"),
                    item[0].created_at,
                    item[0].id,
                )
            )
            for item_action, item_eval in other_entries:
                rank += 1
                notes = [
                    f"Rank {rank}: Orders {item_eval.replenishment_impact.excess_quantity} excess units when shortfall is 0.",
                ]
                ranked_alternatives.append(
                    AlternativeComparison(
                        action_id=item_action.id,
                        action_type=item_action.action_type,
                        is_eligible=True,
                        rank=rank,
                        shortfall_satisfaction_ratio=item_eval.replenishment_impact.shortfall_satisfaction_ratio,
                        shortfall_addressed=item_eval.replenishment_impact.shortfall_addressed,
                        excess_quantity=item_eval.replenishment_impact.excess_quantity,
                        exposure_index_delta=item_eval.stockout_exposure.exposure_index_delta,
                        effective_supplier_risk=item_eval.supplier_impact.effective_supplier_risk.value,
                        effective_lead_time_days=item_eval.supplier_impact.effective_lead_time_days,
                        effective_reliability=item_eval.supplier_impact.effective_reliability,
                        direct_procurement_cost=item_eval.cost_impact.direct_procurement_cost,
                        cost_status=item_eval.cost_impact.cost_status.value,
                        selection_notes=notes,
                    )
                )

            all_alternatives = ranked_alternatives + ineligible_alternatives

            return Recommendation(
                id=recommendation_id,
                decision_id=decision_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                status=RecommendationStatus.NO_ACTION_REQUIRED,
                selection_rationale=rationale,
                tie_broken=False,
                tie_break_method=TieBreakMethod.NONE,
                total_actions_evaluated=total_actions_considered,
                alternatives=all_alternatives,
                recommended_action_id=chosen_action.id,
                recommended_action_type=chosen_action.action_type,
                recommended_action=chosen_action.model_copy(deep=True),
                evaluation_evidence=chosen_eval.evidence.model_copy(deep=True),
                selected_evaluation=chosen_eval.model_copy(deep=True),
                metadata={
                    "shortfall_units": 0,
                    "policy_applied": resolved_policy_str,
                },
            )

    # SCENARIO B: Active Replenishment Shortfall (Q_rec > 0) or non-DO_NOTHING selection
    def _sorting_key(item: tuple[CandidateAction, ActionEvaluationResult]) -> tuple[Any, ...]:
        action, ev = item
        # 1. Shortfall satisfaction ratio: higher is better (negate for ascending sort, 0.0 if missing)
        sat_ratio = ev.replenishment_impact.shortfall_satisfaction_ratio
        ratio_key = -(sat_ratio if sat_ratio is not None else 0.0)

        # 2. Excess quantity: lower is better (inf if missing)
        excess_val = ev.replenishment_impact.excess_quantity
        excess_key = excess_val if excess_val is not None else float("inf")

        # 3. Exposure index delta: lower (more negative) is better (0.0 if missing)
        exp_delta = ev.stockout_exposure.exposure_index_delta
        exposure_key = exp_delta if exp_delta is not None else 0.0

        # 4. Supplier operational risk tier: LOW (0) < MEDIUM (1) < HIGH (2), missing defaults to HIGH (2)
        risk_tier_name = (
            ev.supplier_impact.effective_supplier_risk.value
            if hasattr(ev.supplier_impact.effective_supplier_risk, "value")
            else str(ev.supplier_impact.effective_supplier_risk)
        )
        risk_tier = SUPPLIER_RISK_ORDER.get(risk_tier_name, 2)

        # 5. Supplier reliability: higher is better (negate, 0.0 if missing)
        rel_val = ev.supplier_impact.effective_reliability if ev.supplier_impact.effective_reliability is not None else 0.0
        rel_key = -rel_val

        # 6. Supplier lead time: lower is better (inf if missing)
        lt_val = ev.supplier_impact.effective_lead_time_days
        lt_key = lt_val if lt_val is not None else float("inf")

        # 7. Direct procurement cost:
        # Category order: ZERO_COST (0) < CALCULATED (1) < UNAVAILABLE (2)
        # Then direct_procurement_cost ascending (inf if missing/UNAVAILABLE)
        cost_status_val = ev.cost_impact.cost_status
        cost_cat = 0 if cost_status_val == EvaluationCostStatus.ZERO_COST else (
            1 if cost_status_val == EvaluationCostStatus.CALCULATED else 2
        )
        cost_val = ev.cost_impact.direct_procurement_cost if ev.cost_impact.direct_procurement_cost is not None else float("inf")

        # 8. Action type priority
        priority_map = (
            ACTION_TYPE_PRIORITY_REPLENISHMENT
            if is_replenishment_needed
            else ACTION_TYPE_PRIORITY_NO_REPLENISHMENT
        )
        type_key = priority_map.get(action.action_type, 99)

        # 9. Earliest creation timestamp
        time_key = action.created_at

        # 10. Lexicographical action ID
        id_key = action.id

        return (
            ratio_key,
            excess_key,
            exposure_key,
            risk_tier,
            rel_key,
            lt_key,
            cost_cat,
            cost_val,
            type_key,
            time_key,
            id_key,
        )

    # Sort eligible entries deterministically
    sorted_entries = sorted(eligible_entries, key=_sorting_key)


    chosen_action, chosen_eval = sorted_entries[0]

    # Check for ties on operational criteria (indices 0 through 7: ratio, excess, exposure, risk, rel, lt, cost_cat, cost_val)
    def _operational_metrics(item: tuple[CandidateAction, ActionEvaluationResult]) -> tuple[Any, ...]:
        key = _sorting_key(item)
        return key[0:8]

    top_operational_metric = _operational_metrics(sorted_entries[0])
    tied_entries = [e for e in sorted_entries if _operational_metrics(e) == top_operational_metric]

    tie_broken = len(tied_entries) > 1
    tie_method = TieBreakMethod.NONE
    tie_rationale: str | None = None

    if tie_broken:
        # Check which tie-break level decided the winner
        type_0 = tied_entries[0][0].action_type
        all_same_type = all(e[0].action_type == type_0 for e in tied_entries)
        if not all_same_type:
            tie_method = TieBreakMethod.ACTION_TYPE_PRIORITY
            tie_rationale = (
                f"Multiple candidate actions achieved identical operational criteria. "
                f"Resolved by action type priority: {type_0.value} is prioritized."
            )
        else:
            time_0 = tied_entries[0][0].created_at
            all_same_time = all(e[0].created_at == time_0 for e in tied_entries)
            if not all_same_time:
                tie_method = TieBreakMethod.EARLIEST_TIMESTAMP
                tie_rationale = (
                    f"Multiple candidate actions of type {type_0.value} achieved identical operational criteria. "
                    f"Resolved by earliest creation timestamp ({time_0.isoformat()})."
                )
            else:
                tie_method = TieBreakMethod.ACTION_IDENTIFIER
                tie_rationale = (
                    f"Multiple candidate actions achieved identical operational criteria and timestamps. "
                    f"Resolved deterministically by ascending action identifier '{chosen_action.id}'."
                )

    # Build detailed ranking alternatives list
    ranked_alternatives = []
    for rank_idx, (act, ev) in enumerate(sorted_entries, start=1):
        sat_pct = (ev.replenishment_impact.shortfall_satisfaction_ratio or 0.0) * 100.0
        notes: list[str] = []

        if rank_idx == 1:
            notes.append(
                f"Rank 1 (Recommended): Satisfies {sat_pct:.1f}% of shortfall "
                f"({ev.replenishment_impact.shortfall_addressed}/{ev.replenishment_impact.recommended_replenishment_quantity} units) "
                f"with {ev.replenishment_impact.excess_quantity} excess units."
            )
            if ev.stockout_exposure.exposure_index_delta < 0:
                notes.append(
                    f"Exposure index improves by {ev.stockout_exposure.exposure_index_delta:.4f}."
                )
            if ev.cost_impact.direct_procurement_cost is not None:
                notes.append(
                    f"Direct procurement cost: ${ev.cost_impact.direct_procurement_cost:.2f} {ev.cost_impact.currency}."
                )
            if tie_broken and tie_rationale:
                notes.append(f"Tie-break: {tie_rationale}")
        else:
            higher_entry = sorted_entries[rank_idx - 2]
            higher_ev = higher_entry[1]
            if (ev.replenishment_impact.shortfall_satisfaction_ratio or 0.0) < (higher_ev.replenishment_impact.shortfall_satisfaction_ratio or 0.0):
                notes.append(
                    f"Rank {rank_idx}: Lower shortfall satisfaction ({sat_pct:.1f}%) than higher-ranked alternatives."
                )
            elif ev.replenishment_impact.excess_quantity > higher_ev.replenishment_impact.excess_quantity:
                notes.append(
                    f"Rank {rank_idx}: Identical satisfaction but higher excess quantity ({ev.replenishment_impact.excess_quantity} vs {higher_ev.replenishment_impact.excess_quantity} units)."
                )
            elif ev.stockout_exposure.exposure_index_delta > higher_ev.stockout_exposure.exposure_index_delta:
                notes.append(
                    f"Rank {rank_idx}: Lower exposure reduction delta ({ev.stockout_exposure.exposure_index_delta:.4f} vs {higher_ev.stockout_exposure.exposure_index_delta:.4f})."
                )
            else:
                notes.append(
                    f"Rank {rank_idx}: Subordinated by operational ranking and deterministic tie-breaking."
                )

        if act.action_type == ActionType.SWITCH_SUPPLIER:
            notes.append(
                f"Operational context: SWITCH_SUPPLIER re-benchmarks lead time ({ev.supplier_impact.effective_lead_time_days}d, delta: {ev.supplier_impact.lead_time_delta_days:+d}d) "
                f"and reliability ({ev.supplier_impact.effective_reliability:.2f}) but places 0 order units today (0% physical shortfall addressed)."
            )

        ranked_alternatives.append(

            AlternativeComparison(
                action_id=act.id,
                action_type=act.action_type,
                is_eligible=True,
                rank=rank_idx,
                shortfall_satisfaction_ratio=ev.replenishment_impact.shortfall_satisfaction_ratio,
                shortfall_addressed=ev.replenishment_impact.shortfall_addressed,
                excess_quantity=ev.replenishment_impact.excess_quantity,
                exposure_index_delta=ev.stockout_exposure.exposure_index_delta,
                effective_supplier_risk=ev.supplier_impact.effective_supplier_risk.value,
                effective_lead_time_days=ev.supplier_impact.effective_lead_time_days,
                effective_reliability=ev.supplier_impact.effective_reliability,
                direct_procurement_cost=ev.cost_impact.direct_procurement_cost,
                cost_status=ev.cost_impact.cost_status.value,
                selection_notes=notes,
            )
        )

    all_alternatives = ranked_alternatives + ineligible_alternatives

    # Construct comprehensive selection rationale
    top_sat_pct = (chosen_eval.replenishment_impact.shortfall_satisfaction_ratio or 0.0) * 100.0
    rationale_parts = [
        f"Selected {chosen_action.action_type.value} action '{chosen_action.id}' via Lexicographic Operational Dominance.",
        f"Under {resolved_policy_str}, replenishment shortfall is {chosen_eval.replenishment_impact.recommended_replenishment_quantity} units.",
        f"Action satisfies {chosen_eval.replenishment_impact.shortfall_addressed} units ({top_sat_pct:.1f}% of shortfall) "
        f"with {chosen_eval.replenishment_impact.excess_quantity} excess units.",
    ]
    if chosen_eval.cost_impact.direct_procurement_cost is not None:
        rationale_parts.append(
            f"Direct procurement cost is ${chosen_eval.cost_impact.direct_procurement_cost:.2f}."
        )
    if chosen_eval.stockout_exposure.exposure_index_delta < 0:
        rationale_parts.append(
            f"Post-arrival exposure index improves by {chosen_eval.stockout_exposure.exposure_index_delta:.4f}."
        )
    if tie_broken and tie_rationale:
        rationale_parts.append(tie_rationale)

    selection_rationale = " ".join(rationale_parts)

    status = (
        RecommendationStatus.RECOMMENDED
        if is_replenishment_needed
        else RecommendationStatus.NO_ACTION_REQUIRED
    )

    return Recommendation(
        id=recommendation_id,
        decision_id=decision_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        status=status,
        selection_rationale=selection_rationale,
        tie_broken=tie_broken,
        tie_break_method=tie_method,
        tie_breaking_rationale=tie_rationale,
        total_actions_evaluated=total_actions_considered,
        alternatives=all_alternatives,
        recommended_action_id=chosen_action.id,
        recommended_action_type=chosen_action.action_type,
        recommended_action=chosen_action.model_copy(deep=True),
        evaluation_evidence=chosen_eval.evidence.model_copy(deep=True),
        selected_evaluation=chosen_eval.model_copy(deep=True),
        metadata={
            "policy_applied": resolved_policy_str,
            "shortfall_units": chosen_eval.replenishment_impact.recommended_replenishment_quantity,
            "tied_candidates_count": len(tied_entries) if tie_broken else 1,
        },
    )
