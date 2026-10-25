from __future__ import annotations

from typing import Any

from app.domain.action_evaluation import ActionEvaluationResult
from app.domain.candidate_action import CandidateAction
from app.domain.recommendation import (
    Recommendation,
    RecommendationStatus,
    select_deterministic_recommendation,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.evaluation.service import (
    ActionEvaluationService,
    CandidateActionNotFoundError as EvalActionNotFoundError,
    DecisionNotFoundError as EvalDecisionNotFoundError,
    MissingEvaluationDataError,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.recommendation_repository import RecommendationRepository


class RecommendationError(Exception):
    """Base exception for recommendation service errors."""


class DecisionNotFoundError(RecommendationError, KeyError):
    """Raised when the specified decision does not exist."""


class RecommendationNotFoundError(RecommendationError, KeyError):
    """Raised when a recommendation does not exist."""


class RecommendationService:
    """Application coordination service for deterministic recommendation selection.

    Orchestrates candidate action retrieval, action evaluation execution (Day 19),
    deterministic multi-criteria selection (Lexicographic Operational Dominance),
    in-memory persistence, and Decision Graph traceability.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."

    Guarantees:
    - Pure, deterministic selection: Identical inputs always produce the identical recommendation.
    - Reuses Day 19 ActionEvaluationService without duplicating mathematical derivations.
    - Preserves decision lifecycle and versioning (does not auto-transition status).
    - Preserves candidate action integrity (does not mutate or execute actions).
    - Decoupled from human approval and purchase order execution.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
        evaluation_service: ActionEvaluationService,
        recommendation_repo: RecommendationRepository | None = None,
        graph_repo: DecisionGraphRepository | None = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._action_repo = action_repo
        self._evaluation_service = evaluation_service
        self._recommendation_repo = (
            recommendation_repo
            if recommendation_repo is not None
            else RecommendationRepository()
        )
        self._graph_repo = graph_repo

    @property
    def decision_repository(self) -> DecisionRepository:
        return self._decision_repo

    @property
    def action_repository(self) -> CandidateActionRepository:
        return self._action_repo

    @property
    def evaluation_service(self) -> ActionEvaluationService:
        return self._evaluation_service

    @property
    def recommendation_repository(self) -> RecommendationRepository:
        return self._recommendation_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository | None:
        return self._graph_repo

    def generate_recommendation(
        self,
        decision_id: str,
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        *,
        target_stock: int | None = None,
        enforce_reorder_trigger: bool = True,
        record_to_graph: bool = False,
    ) -> Recommendation:
        """Evaluates all candidate actions and selects the optimal recommendation deterministically.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        resolved_policy = (
            policy_type
            if isinstance(policy_type, ReplenishmentPolicyType)
            else ReplenishmentPolicyType(policy_type)
        )

        candidate_actions = self._action_repo.list_by_decision_id(decision.id)
        rec_id = self._recommendation_repo.generate_id()

        # Edge case: No candidate actions exist
        if not candidate_actions:
            rec = select_deterministic_recommendation(
                decision_id=decision.id,
                product_id=decision.product_id,
                warehouse_id=decision.warehouse_id,
                evaluations=[],
                candidate_actions=[],
                recommendation_id=rec_id,
                policy_type=resolved_policy,
            )
            stored_rec = self._recommendation_repo.record(rec)
            if record_to_graph and self._graph_repo is not None:
                self._graph_repo.attach_recommendation_node(decision.id, stored_rec)
            return stored_rec

        # Evaluate each candidate action via Day 19 ActionEvaluationService
        # Track successful evaluations and any per-action failures gracefully
        evaluations: list[ActionEvaluationResult] = []
        failed_evaluations: dict[str, str] = {}

        for action in candidate_actions:
            try:
                eval_res = self._evaluation_service.evaluate_action(
                    decision_id=decision.id,
                    action_id=action.id,
                    policy_type=resolved_policy,
                    target_stock=target_stock,
                    enforce_reorder_trigger=enforce_reorder_trigger,
                    record_to_graph=record_to_graph,
                )
                evaluations.append(eval_res)
            except Exception as exc:
                failed_evaluations[action.id] = str(exc)

        # Execute pure deterministic recommendation selection
        rec = select_deterministic_recommendation(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            evaluations=evaluations,
            candidate_actions=candidate_actions,
            recommendation_id=rec_id,
            policy_type=resolved_policy,
            failed_evaluations=failed_evaluations,
        )

        # Persist recommendation
        stored_rec = self._recommendation_repo.record(rec)

        # Synchronize with Decision Graph if requested
        if record_to_graph and self._graph_repo is not None:
            self._graph_repo.attach_recommendation_node(decision.id, stored_rec)

        return stored_rec

    def check_recommendation_freshness(
        self,
        recommendation: Recommendation,
    ) -> tuple[bool, str | None]:
        """Checks whether a stored recommendation remains fresh relative to current state.

        Performs multi-vector validation across:
        1. Decision existence: Verifies the decision entity has not been deleted.
        2. Candidate action parity: Verifies that candidate actions have not been added or removed.
        3. Action creation timestamps: Detects if any action was created after recommendation snapshot.
        4. Inventory position timestamp: Detects if inventory was updated after recommendation snapshot.
        5. Content-based inventory check: Directly compares available quantity, reorder point,
           and primary supplier against evaluated baseline values (protects against timestamp clock skew).
        6. Content-based supplier parameter check: Verifies baseline supplier lead time and reliability.
        7. Content-based catalog price check: Verifies product unit cost has not changed.

        Architectural Limitation:
        External modifications to underlying daily sales time-series (demand history) that do not
        alter inventory levels or candidate actions cannot be fully detected without re-aggregating
        historical distributions. Callers desiring unconditional fresh re-evaluation across all inputs
        should specify `recompute=True`.

        Returns:
            tuple[bool, str | None]: (is_fresh, stale_reason)
        """
        # 1. Decision existence check
        decision = self._decision_repo.get_by_id(recommendation.decision_id)
        if decision is None:
            return False, f"Decision '{recommendation.decision_id}' was removed"

        # 2. Candidate actions parity check
        current_actions = self._action_repo.list_by_decision_id(recommendation.decision_id)
        current_action_ids = {a.id for a in current_actions}
        evaluated_action_ids = {a.action_id for a in recommendation.alternatives}

        if current_action_ids != evaluated_action_ids:
            added = current_action_ids - evaluated_action_ids
            removed = evaluated_action_ids - current_action_ids
            reasons = []
            if added:
                reasons.append(f"new candidate actions created ({', '.join(sorted(added))})")
            if removed:
                reasons.append(f"candidate actions deleted ({', '.join(sorted(removed))})")
            return False, f"Candidate action set modified: {'; '.join(reasons)}"

        # 3. Check for any action created after recommendation snapshot
        for action in current_actions:
            if action.created_at > recommendation.created_at:
                return False, f"Candidate action '{action.id}' created after recommendation snapshot"

        # 4. Inventory position timestamp check
        inv = self._evaluation_service.inventory_repository.dataset.get_inventory(
            recommendation.product_id, recommendation.warehouse_id
        )
        if inv is not None and inv.updated_at > recommendation.created_at:
            return False, f"Inventory position updated at {inv.updated_at.isoformat()} after recommendation snapshot"

        # 5. Content-based checks (independent of timestamp reliability)
        if recommendation.selected_evaluation is not None:
            sel_eval = recommendation.selected_evaluation

            # 5a. Direct physical inventory verification
            if inv is not None:
                eval_avail = sel_eval.replenishment_impact.available_quantity
                if inv.available_quantity != eval_avail:
                    return (
                        False,
                        f"Inventory available quantity changed ({eval_avail} -> {inv.available_quantity}) since recommendation",
                    )
                eval_rop = sel_eval.replenishment_impact.reorder_point
                if inv.reorder_point != eval_rop:
                    return (
                        False,
                        f"Inventory reorder point changed ({eval_rop} -> {inv.reorder_point}) since recommendation",
                    )

            # 5b. Direct baseline supplier parameter verification
            curr_sup_id = sel_eval.supplier_impact.current_supplier_id
            curr_sup = self._evaluation_service.supplier_repository.get_by_id(curr_sup_id)
            if curr_sup is not None:
                if curr_sup.lead_time_days != sel_eval.supplier_impact.current_lead_time_days:
                    return (
                        False,
                        f"Supplier '{curr_sup_id}' lead time changed ({sel_eval.supplier_impact.current_lead_time_days}d -> {curr_sup.lead_time_days}d) since recommendation",
                    )
                if curr_sup.reliability != sel_eval.supplier_impact.current_reliability:
                    return (
                        False,
                        f"Supplier '{curr_sup_id}' reliability changed ({sel_eval.supplier_impact.current_reliability:.2f} -> {curr_sup.reliability:.2f}) since recommendation",
                    )

            # 5c. Direct product catalog unit cost verification
            if sel_eval.cost_impact.unit_cost is not None:
                prod = self._evaluation_service.inventory_repository.dataset.get_product(
                    recommendation.product_id
                )
                if prod is not None and prod.unit_cost != sel_eval.cost_impact.unit_cost:
                    return (
                        False,
                        f"Product unit cost changed (${sel_eval.cost_impact.unit_cost:.2f} -> ${prod.unit_cost:.2f}) since recommendation",
                    )

        return True, None

    def get_latest_recommendation(
        self,
        decision_id: str,
        *,
        ensure_fresh: bool = True,
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        target_stock: int | None = None,
        enforce_reorder_trigger: bool = True,
        record_to_graph: bool = False,
    ) -> Recommendation:
        """Retrieves the latest recommendation generated for a decision.

        If ensure_fresh is True and the recommendation is determined to be stale
        (e.g., candidate actions or inventory have changed), automatically re-evaluates
        and generates a fresh recommendation.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            RecommendationNotFoundError: If no recommendation has been generated.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        rec = self._recommendation_repo.get_latest_for_decision(norm_decision_id)
        if rec is None:
            raise RecommendationNotFoundError(
                f"No recommendation found for decision '{norm_decision_id}'"
            )

        if ensure_fresh:
            is_fresh, stale_reason = self.check_recommendation_freshness(rec)
            if not is_fresh:
                # Automatically re-evaluate and generate fresh recommendation
                fresh_rec = self.generate_recommendation(
                    decision_id=norm_decision_id,
                    policy_type=policy_type,
                    target_stock=target_stock,
                    enforce_reorder_trigger=enforce_reorder_trigger,
                    record_to_graph=record_to_graph,
                )
                return fresh_rec

        return rec


    def get_recommendation_by_id(self, recommendation_id: str) -> Recommendation:
        """Retrieves a recommendation by its unique identifier.

        Raises:
            RecommendationNotFoundError: If the recommendation does not exist.
        """
        norm_id = recommendation_id.strip()
        rec = self._recommendation_repo.get_by_id(norm_id)
        if rec is None:
            raise RecommendationNotFoundError(
                f"Recommendation '{norm_id}' not found"
            )
        return rec

    def list_recommendations_for_decision(self, decision_id: str) -> list[Recommendation]:
        """Lists all recommendations generated for a decision in deterministic order.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self._recommendation_repo.list_by_decision_id(norm_decision_id)
