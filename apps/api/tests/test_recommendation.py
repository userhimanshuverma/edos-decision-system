from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.action_evaluation import (
    ActionEvaluationResult,
    CostImpactEvaluation,
    EvaluationCostStatus,
    EvaluationEvidence,
    ReplenishmentImpactEvaluation,
    StockoutExposureEvaluation,
    SupplierImpactEvaluation,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.recommendation import (
    AlternativeComparison,
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
    select_deterministic_recommendation,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.domain.stockout_risk import StockoutRiskLevel
from app.domain.supplier import SupplierRiskLevel


def _make_dummy_evidence(action_id: str, action_type: ActionType, decision_id: str = "DEC-0001") -> EvaluationEvidence:
    return EvaluationEvidence(
        action_id=action_id,
        action_type=action_type,
        decision_id=decision_id,
        product_id="prod-001",
        warehouse_id="wh-001",
        inputs_summary={"available_quantity": 10, "reorder_point": 20},
        formulas={"test_formula": "formula_a"},
        assumptions=["Standard operational assumptions"],
        limitations=["Deterministic model boundaries"],
        calculation_notes=["Test evaluation step"],
    )


def _make_evaluation_result(
    action: CandidateAction,
    *,
    is_replenishment_needed: bool = True,
    recommended_qty: int = 10,
    shortfall_addressed: int = 10,
    excess_qty: int = 0,
    satisfaction_ratio: float = 1.0,
    exposure_delta: float = -0.5,
    supplier_risk: SupplierRiskLevel = SupplierRiskLevel.LOW,
    supplier_lead_time: int = 5,
    supplier_reliability: float = 0.95,
    direct_cost: float | None = 150.0,
    cost_status: EvaluationCostStatus = EvaluationCostStatus.CALCULATED,
    decision_id: str = "DEC-0001",
) -> ActionEvaluationResult:
    return ActionEvaluationResult(
        action_id=action.id,
        action_type=action.action_type,
        decision_id=decision_id,
        product_id="prod-001",
        warehouse_id="wh-001",
        evaluated_at=datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc),
        stockout_exposure=StockoutExposureEvaluation(
            is_probability=False,
            current_risk_level=StockoutRiskLevel.HIGH,
            current_exposure_index=0.6,
            current_exposure_deficit=30.0,
            projected_risk_level=StockoutRiskLevel.LOW,
            projected_exposure_index=0.1,
            projected_exposure_deficit=5.0,
            exposure_index_delta=exposure_delta,
            is_stockout_prevented_in_lead_time=False,
            post_arrival_coverage_days=5.0,
            notes=["Stockout test notes"],
        ),
        replenishment_impact=ReplenishmentImpactEvaluation(
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
            target_stock=20,
            available_quantity=10,
            reorder_point=20,
            recommended_replenishment_quantity=recommended_qty,
            is_replenishment_needed=is_replenishment_needed,
            action_order_quantity=action.parameters.quantity if isinstance(action.parameters, PlaceOrderParameters) else None,
            shortfall_addressed=shortfall_addressed,
            remaining_shortfall=max(0, recommended_qty - shortfall_addressed),
            excess_quantity=excess_qty,
            shortfall_satisfaction_ratio=satisfaction_ratio,
            notes=["Replenishment test notes"],
        ),
        supplier_impact=SupplierImpactEvaluation(
            current_supplier_id="sup-001",
            current_supplier_name="Acme Corp",
            current_lead_time_days=5,
            current_reliability=0.95,
            current_supplier_risk=SupplierRiskLevel.LOW,
            effective_supplier_id="sup-001",
            effective_supplier_name="Acme Corp",
            effective_lead_time_days=supplier_lead_time,
            effective_reliability=supplier_reliability,
            effective_supplier_risk=supplier_risk,
            is_supplier_switched=False,
            lead_time_delta_days=0,
            reliability_delta=0.0,
            notes=["Supplier test notes"],
        ),
        cost_impact=CostImpactEvaluation(
            is_cost_calculable=direct_cost is not None,
            unit_cost=15.0,
            order_quantity=action.parameters.quantity if isinstance(action.parameters, PlaceOrderParameters) else None,
            direct_procurement_cost=direct_cost,
            currency="USD",
            cost_status=cost_status,
            unavailability_reason=None if direct_cost is not None else "Pricing unobserved",
            notes=["Cost test notes"],
        ),
        evidence=_make_dummy_evidence(action.id, action.action_type, decision_id),
        overall_score=None,
        scoring_status="UNRESOLVED_MULTI_CRITERIA_DECISION",
        scoring_rationale="Multidimensional test scoring",
    )


class TestRecommendationSelectionLogic:
    """Comprehensive unit tests for the pure deterministic recommendation engine."""

    def test_shortfall_satisfaction_dominance(self) -> None:
        """Verifies that an action satisfying 100% of shortfall dominates an action satisfying 50%."""
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=5),
        )
        a2 = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        e1 = _make_evaluation_result(
            a1,
            recommended_qty=10,
            shortfall_addressed=5,
            excess_qty=0,
            satisfaction_ratio=0.5,
            direct_cost=75.0,
        )
        e2 = _make_evaluation_result(
            a2,
            recommended_qty=10,
            shortfall_addressed=10,
            excess_qty=0,
            satisfaction_ratio=1.0,
            direct_cost=150.0,
        )

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e1, e2],
            candidate_actions=[a1, a2],
        )

        assert rec.status == RecommendationStatus.RECOMMENDED
        assert rec.recommended_action_id == "ACT-0002"
        assert rec.recommended_action_type == ActionType.PLACE_ORDER
        assert rec.alternatives[0].rank == 1
        assert rec.alternatives[0].action_id == "ACT-0002"
        assert rec.alternatives[1].rank == 2
        assert rec.alternatives[1].action_id == "ACT-0001"

    def test_excess_avoidance_dominance(self) -> None:
        """Verifies that between two actions with 100% satisfaction, the one with zero excess dominates."""
        a_exact = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        a_over = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )

        e_exact = _make_evaluation_result(
            a_exact,
            recommended_qty=10,
            shortfall_addressed=10,
            excess_qty=0,
            satisfaction_ratio=1.0,
            direct_cost=150.0,
        )
        e_over = _make_evaluation_result(
            a_over,
            recommended_qty=10,
            shortfall_addressed=10,
            excess_qty=40,
            satisfaction_ratio=1.0,
            direct_cost=750.0,
        )

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e_over, e_exact],
            candidate_actions=[a_over, a_exact],
        )

        assert rec.recommended_action_id == "ACT-0001"
        assert rec.alternatives[0].action_id == "ACT-0001"
        assert rec.alternatives[1].action_id == "ACT-0002"

    def test_healthy_inventory_prefers_do_nothing(self) -> None:
        """Verifies that when shortfall is 0, DO_NOTHING is selected with status NO_ACTION_REQUIRED."""
        a_none = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        a_order = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=20),
        )

        e_none = _make_evaluation_result(
            a_none,
            is_replenishment_needed=False,
            recommended_qty=0,
            shortfall_addressed=0,
            excess_qty=0,
            satisfaction_ratio=1.0,
            direct_cost=0.0,
            cost_status=EvaluationCostStatus.ZERO_COST,
        )
        e_order = _make_evaluation_result(
            a_order,
            is_replenishment_needed=False,
            recommended_qty=0,
            shortfall_addressed=0,
            excess_qty=20,
            satisfaction_ratio=1.0,
            direct_cost=300.0,
        )

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e_order, e_none],
            candidate_actions=[a_order, a_none],
        )

        assert rec.status == RecommendationStatus.NO_ACTION_REQUIRED
        assert rec.recommended_action_id == "ACT-0001"
        assert rec.recommended_action_type == ActionType.DO_NOTHING
        assert "preserves capital with $0.00" in rec.selection_rationale

    def test_exposure_improvement_precedence(self) -> None:
        """Verifies that between two actions with identical shortfall/excess, greater exposure reduction wins."""
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        a2 = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        e1 = _make_evaluation_result(a1, exposure_delta=-0.3)
        e2 = _make_evaluation_result(a2, exposure_delta=-0.6)  # More negative = larger improvement

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e1, e2],
            candidate_actions=[a1, a2],
        )

        assert rec.recommended_action_id == "ACT-0002"

    def test_supplier_dependability_precedence(self) -> None:
        """Verifies that when operational replenishment metrics match, supplier risk and reliability decide."""
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        a2 = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        e1 = _make_evaluation_result(
            a1,
            supplier_risk=SupplierRiskLevel.HIGH,
            supplier_reliability=0.70,
            supplier_lead_time=10,
        )
        e2 = _make_evaluation_result(
            a2,
            supplier_risk=SupplierRiskLevel.LOW,
            supplier_reliability=0.98,
            supplier_lead_time=4,
        )

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e1, e2],
            candidate_actions=[a1, a2],
        )

        assert rec.recommended_action_id == "ACT-0002"

    def test_procurement_cost_precedence(self) -> None:
        """Verifies that between two actions with identical operational metrics, lower cost wins."""
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        a2 = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        e1 = _make_evaluation_result(a1, direct_cost=250.0)
        e2 = _make_evaluation_result(a2, direct_cost=150.0)

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e1, e2],
            candidate_actions=[a1, a2],
        )

        assert rec.recommended_action_id == "ACT-0002"
        assert rec.tie_broken is False
        assert rec.tie_break_method == TieBreakMethod.NONE

    def test_deterministic_tie_breaking(self) -> None:
        """Verifies that complete metric ties are broken deterministically by stable ID with tie_broken=True."""
        t_common = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
            created_at=t_common,
        )
        a2 = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
            created_at=t_common,
        )

        e1 = _make_evaluation_result(a1)
        e2 = _make_evaluation_result(a2)

        # Pass in reverse order to ensure sort determinism
        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e2, e1],
            candidate_actions=[a2, a1],
        )

        assert rec.recommended_action_id == "ACT-0001"
        assert rec.tie_broken is True
        assert rec.tie_break_method == TieBreakMethod.ACTION_IDENTIFIER
        assert "ACT-0001" in (rec.tie_breaking_rationale or "")

    def test_determinism_across_50_iterations(self) -> None:
        """Verifies that running selection 50 times with varied input order always yields the identical result."""
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        a2 = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=15),
        )

        e1 = _make_evaluation_result(a1, shortfall_addressed=10, excess_qty=0)
        e2 = _make_evaluation_result(a2, shortfall_addressed=10, excess_qty=5)

        first_rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e1, e2],
            candidate_actions=[a1, a2],
        )

        for i in range(50):
            # Alternating ordering
            evals = [e2, e1] if i % 2 == 0 else [e1, e2]
            actions = [a2, a1] if i % 2 == 0 else [a1, a2]
            rec_iter = select_deterministic_recommendation(
                decision_id="DEC-0001",
                product_id="prod-001",
                warehouse_id="wh-001",
                evaluations=evals,
                candidate_actions=actions,
            )
            assert rec_iter.recommended_action_id == first_rec.recommended_action_id
            assert rec_iter.status == first_rec.status
            assert rec_iter.selection_rationale == first_rec.selection_rationale

    def test_empty_candidate_actions(self) -> None:
        """Verifies that an empty actions list returns NO_CANDIDATE_ACTIONS with no recommended action."""
        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[],
            candidate_actions=[],
        )

        assert rec.status == RecommendationStatus.NO_CANDIDATE_ACTIONS
        assert rec.recommended_action_id is None
        assert rec.recommended_action is None
        assert rec.total_actions_evaluated == 0

    def test_all_evaluations_failed(self) -> None:
        """Verifies that when all action evaluations fail, ALL_EVALUATIONS_FAILED is returned."""
        a1 = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[],
            candidate_actions=[a1],
            failed_evaluations={"ACT-0001": "Missing inventory position data"},
        )

        assert rec.status == RecommendationStatus.ALL_EVALUATIONS_FAILED
        assert rec.recommended_action_id is None
        assert rec.alternatives[0].is_eligible is False
        assert rec.alternatives[0].ineligibility_reason == "Missing inventory position data"

    def test_partial_evaluation_failure(self) -> None:
        """Verifies that when one action fails evaluation, the remaining eligible action is selected."""
        a_fail = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-unknown"),
        )
        a_ok = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        e_ok = _make_evaluation_result(a_ok)

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e_ok],
            candidate_actions=[a_fail, a_ok],
            failed_evaluations={"ACT-0001": "Target supplier sup-unknown not found"},
        )

        assert rec.status == RecommendationStatus.RECOMMENDED
        assert rec.recommended_action_id == "ACT-0002"
        # Verify both alternatives are captured
        act_ids = [alt.action_id for alt in rec.alternatives]
        assert "ACT-0002" in act_ids
        assert "ACT-0001" in act_ids
        fail_alt = next(alt for alt in rec.alternatives if alt.action_id == "ACT-0001")
        assert fail_alt.is_eligible is False

    def test_deep_copy_isolation(self) -> None:
        """Verifies that modifying external objects does not mutate the preserved recommendation."""
        a = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        e = _make_evaluation_result(a)

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e],
            candidate_actions=[a],
        )

        assert rec.recommended_action is not None
        # Mutate local action metadata
        a.metadata["tampered"] = True
        assert "tampered" not in rec.recommended_action.metadata

    def test_validation_point_1_do_nothing_distinguishes_healthy_vs_persistent_exposure(self) -> None:
        """Validates Review Point 1:

        Confirm DO_NOTHING when replenishment is unnecessary.
        A zero shortfall under one policy should not automatically imply that every inventory situation is healthy.
        When exposure deficit is 0, rationale indicates healthy stock.
        When exposure deficit > 0, rationale explicitly notes persistent baseline lead-time exposure.
        """
        a_none = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )

        # Case A: Shortfall == 0 and exposure deficit == 0.0 (truly healthy)
        e_healthy = _make_evaluation_result(
            a_none,
            is_replenishment_needed=False,
            recommended_qty=0,
            shortfall_addressed=0,
            excess_qty=0,
            satisfaction_ratio=1.0,
            direct_cost=0.0,
            cost_status=EvaluationCostStatus.ZERO_COST,
        )
        e_healthy.stockout_exposure.current_exposure_deficit = 0.0

        rec_healthy = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e_healthy],
            candidate_actions=[a_none],
        )
        assert rec_healthy.status == RecommendationStatus.NO_ACTION_REQUIRED
        assert "Inventory level is healthy above the reorder threshold" in rec_healthy.selection_rationale

        # Case B: Shortfall == 0 but exposure deficit > 0 (e.g. 15 units under lead-time exposure)
        e_exposure = _make_evaluation_result(
            a_none,
            is_replenishment_needed=False,
            recommended_qty=0,
            shortfall_addressed=0,
            excess_qty=0,
            satisfaction_ratio=1.0,
            direct_cost=0.0,
            cost_status=EvaluationCostStatus.ZERO_COST,
        )
        e_exposure.stockout_exposure.current_exposure_deficit = 15.0
        e_exposure.stockout_exposure.current_risk_level = StockoutRiskLevel.HIGH

        rec_exposure = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e_exposure],
            candidate_actions=[a_none],
        )
        assert rec_exposure.status == RecommendationStatus.NO_ACTION_REQUIRED
        assert "Replenishment threshold is not triggered under policy" in rec_exposure.selection_rationale
        assert "baseline lead-time exposure deficit remains 15.0 units" in rec_exposure.selection_rationale
        assert "while baseline lead-time exposure persists" in rec_exposure.selection_rationale

    def test_validation_point_2_place_order_vs_switch_supplier_consistent_evidence(self) -> None:
        """Validates Review Point 2:

        Confirm that PLACE_ORDER and SWITCH_SUPPLIER use comparable quantity and exposure calculations.
        SWITCH_SUPPLIER re-benchmarks supplier parameters (lead time, reliability) but places 0 order units (0% shortfall addressed).
        PLACE_ORDER satisfies physical shortfall.
        The ranking compares them on consistent evidence and annotates SWITCH_SUPPLIER explicitly.
        """
        a_order = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=20),
        )
        a_switch = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
        )

        e_order = _make_evaluation_result(
            a_order,
            is_replenishment_needed=True,
            recommended_qty=20,
            shortfall_addressed=20,
            excess_qty=0,
            satisfaction_ratio=1.0,
            exposure_delta=-0.4,
            direct_cost=200.0,
        )
        e_switch = _make_evaluation_result(
            a_switch,
            is_replenishment_needed=True,
            recommended_qty=20,
            shortfall_addressed=0,
            excess_qty=0,
            satisfaction_ratio=0.0,
            exposure_delta=0.0,
            supplier_risk=SupplierRiskLevel.LOW,
            supplier_lead_time=3,
            supplier_reliability=0.98,
            direct_cost=0.0,
            cost_status=EvaluationCostStatus.ZERO_COST,
        )

        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[a_order, a_switch] and [e_order, e_switch],
            candidate_actions=[a_order, a_switch],
        )

        assert rec.status == RecommendationStatus.RECOMMENDED
        assert rec.recommended_action_id == "ACT-0001"
        assert rec.recommended_action_type == ActionType.PLACE_ORDER

        # Check alternative comparisons
        switch_alt = next(alt for alt in rec.alternatives if alt.action_id == "ACT-0002")
        assert switch_alt.rank == 2
        assert switch_alt.shortfall_satisfaction_ratio == 0.0
        assert switch_alt.shortfall_addressed == 0
        # Confirm explicit operational notes documenting that SWITCH_SUPPLIER re-benchmarks parameters
        assert any("SWITCH_SUPPLIER re-benchmarks lead time" in note for note in switch_alt.selection_notes)
        assert any("places 0 order units today" in note for note in switch_alt.selection_notes)

    def test_validation_point_3_missing_or_incomparable_cost_cannot_defeat_known_cost(self) -> None:
        """Validates Review Point 3:

        Missing or incomparable values must not accidentally beat known values.
        An unknown/unavailable cost (UNAVAILABLE) must never beat a known zero cost (ZERO_COST)
        or a known calculated cost (CALCULATED).
        """
        a_zero = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        a_unavail = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

        # Both have identical shortfall satisfaction, excess, exposure, risk, reliability, lead time
        e_zero = _make_evaluation_result(
            a_zero,
            direct_cost=0.0,
            cost_status=EvaluationCostStatus.ZERO_COST,
        )
        e_unavail = _make_evaluation_result(
            a_unavail,
            direct_cost=None,
            cost_status=EvaluationCostStatus.UNAVAILABLE,
        )

        # Send unavail first to test that order in candidate list does not matter
        rec = select_deterministic_recommendation(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            evaluations=[e_unavail, e_zero],
            candidate_actions=[a_unavail, a_zero],
        )

        # ZERO_COST must strictly defeat UNAVAILABLE
        assert rec.recommended_action_id == "ACT-0001"
        alt_zero = next(alt for alt in rec.alternatives if alt.action_id == "ACT-0001")
        alt_unavail = next(alt for alt in rec.alternatives if alt.action_id == "ACT-0002")
        assert alt_zero.rank == 1
        assert alt_unavail.rank == 2

