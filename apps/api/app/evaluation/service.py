from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.data.dataset import ShopFlowDataset
from app.domain.action_evaluation import (
    ActionEvaluationInputs,
    ActionEvaluationResult,
    DecisionEvaluationReport,
    evaluate_candidate_action,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    SwitchSupplierParameters,
    validate_supplier_eligibility,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository


class ActionEvaluationError(Exception):
    """Base exception for action evaluation service errors."""


class DecisionNotFoundError(ActionEvaluationError, KeyError):
    """Raised when the specified decision does not exist."""


class CandidateActionNotFoundError(ActionEvaluationError, KeyError):
    """Raised when the candidate action does not exist or does not belong to the decision."""


class MissingEvaluationDataError(ActionEvaluationError, ValueError):
    """Raised when required operational data for action evaluation cannot be resolved."""


class ActionEvaluationService:
    """Application coordination service for deterministic candidate action evaluation.

    Coordinates retrieval of Decision, CandidateAction, Product, Inventory, Historical Demand,
    and Supplier data to execute pure, transparent, deterministic evaluation across
    stockout exposure, replenishment impact, supplier parameters, and defensible costs.

    Guarantees:
    - Pure, deterministic calculation without hidden stochastic or LLM factors.
    - Preserves decision lifecycle and versioning (does not auto-transition status).
    - Preserves candidate action integrity (does not silently modify or execute actions).
    - Strictly does NOT select or recommend the final action (Day 20 milestone).
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
        inventory_repo: InventoryRepository | None = None,
        demand_repo: DemandRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        graph_repo: DecisionGraphRepository | None = None,
        dataset: ShopFlowDataset | None = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._action_repo = action_repo
        shared_ds = dataset or decision_repo.dataset
        self._inventory_repo = inventory_repo or InventoryRepository(dataset=shared_ds)
        self._demand_repo = demand_repo or DemandRepository(dataset=shared_ds)
        self._supplier_repo = supplier_repo or SupplierRepository(dataset=shared_ds)
        self._graph_repo = graph_repo

    @property
    def decision_repository(self) -> DecisionRepository:
        return self._decision_repo

    @property
    def action_repository(self) -> CandidateActionRepository:
        return self._action_repo

    @property
    def inventory_repository(self) -> InventoryRepository:
        return self._inventory_repo

    @property
    def demand_repository(self) -> DemandRepository:
        return self._demand_repo

    @property
    def supplier_repository(self) -> SupplierRepository:
        return self._supplier_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository | None:
        return self._graph_repo

    def evaluate_action(
        self,
        decision_id: str,
        action_id: str,
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        *,
        target_stock: int | None = None,
        enforce_reorder_trigger: bool = True,
        record_to_graph: bool = False,
    ) -> ActionEvaluationResult:
        """Evaluates an individual candidate action belonging to a business decision.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            CandidateActionNotFoundError: If the action does not exist or belongs to another decision.
            MissingEvaluationDataError: If essential operational inputs are missing.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        norm_action_id = action_id.strip()
        action = self._action_repo.get_by_id(norm_action_id)
        if action is None or action.decision_id != decision.id:
            raise CandidateActionNotFoundError(
                f"Candidate action '{norm_action_id}' not found for decision '{norm_decision_id}'"
            )

        resolved_policy = (
            policy_type
            if isinstance(policy_type, ReplenishmentPolicyType)
            else ReplenishmentPolicyType(policy_type)
        )

        inputs = self._build_evaluation_inputs(
            action=action,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            policy_type=resolved_policy,
            target_stock=target_stock,
            enforce_reorder_trigger=enforce_reorder_trigger,
        )

        evaluation = evaluate_candidate_action(inputs)

        if record_to_graph and self._graph_repo is not None:
            self._graph_repo.attach_evaluation_node(norm_decision_id, evaluation)

        return evaluation

    def evaluate_decision_actions(
        self,
        decision_id: str,
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        *,
        target_stock: int | None = None,
        enforce_reorder_trigger: bool = True,
        record_to_graph: bool = False,
    ) -> DecisionEvaluationReport:
        """Evaluates all candidate actions associated with a business decision.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            MissingEvaluationDataError: If essential operational inputs are missing.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        candidate_actions = self._action_repo.list_by_decision_id(decision.id)
        resolved_policy = (
            policy_type
            if isinstance(policy_type, ReplenishmentPolicyType)
            else ReplenishmentPolicyType(policy_type)
        )

        evaluations: list[ActionEvaluationResult] = []
        for action in candidate_actions:
            inputs = self._build_evaluation_inputs(
                action=action,
                product_id=decision.product_id,
                warehouse_id=decision.warehouse_id,
                policy_type=resolved_policy,
                target_stock=target_stock,
                enforce_reorder_trigger=enforce_reorder_trigger,
            )
            eval_res = evaluate_candidate_action(inputs)
            if record_to_graph and self._graph_repo is not None:
                self._graph_repo.attach_evaluation_node(norm_decision_id, eval_res)
            evaluations.append(eval_res)

        notes = [
            f"Evaluated {len(evaluations)} candidate action(s) for decision '{decision.id}'.",
            f"Replenishment policy applied: {resolved_policy.value}.",
            "Individual evaluations complete. Recommendation ranking and selection strictly deferred to Day 20.",
        ]

        return DecisionEvaluationReport(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            total_actions_evaluated=len(evaluations),
            evaluations=evaluations,
            summary_notes=notes,
        )

    def _build_evaluation_inputs(
        self,
        action: CandidateAction,
        product_id: str,
        warehouse_id: str,
        policy_type: ReplenishmentPolicyType,
        target_stock: int | None,
        enforce_reorder_trigger: bool,
    ) -> ActionEvaluationInputs:
        """Gathers and validates all domain data needed for deterministic evaluation."""
        # 1. Product
        product = self._inventory_repo.dataset.get_product(product_id)
        if product is None:
            raise MissingEvaluationDataError(f"Product '{product_id}' not found in catalog")

        # 2. Warehouse
        warehouse = self._inventory_repo.dataset.get_warehouse(warehouse_id)
        if warehouse is None:
            raise MissingEvaluationDataError(f"Warehouse '{warehouse_id}' not found in dataset")

        # 3. Inventory Position
        inv_position = self._inventory_repo.dataset.get_inventory(product_id, warehouse_id)
        if inv_position is not None:
            available_qty = inv_position.available_quantity
            reorder_point = inv_position.reorder_point
        else:
            available_qty = 0
            reorder_point = product.reorder_point

        # 4. Demand Summary and Historical Series
        trend_summary = self._demand_repo.get_product_demand_trend(
            product_id=product_id,
            warehouse_id=warehouse_id,
        )
        avg_demand = float(trend_summary.get("average_daily_demand", 0.0))
        history_items = trend_summary.get("history", [])
        historical_demands = [item["quantity"] for item in history_items] if history_items else None

        # 5. Primary Supplier Resolution

        current_supplier = self._supplier_repo.get_supplier_for_product(
            product_id=product_id,
            category=product.category,
        )
        if current_supplier is None:
            raise MissingEvaluationDataError(
                f"No primary supplier found for product '{product_id}' in category '{product.category}'"
            )

        # 6. Target Supplier Resolution (for SWITCH_SUPPLIER)
        target_supplier = None
        if action.action_type == ActionType.SWITCH_SUPPLIER:
            assert isinstance(action.parameters, SwitchSupplierParameters)
            target_sup_id = action.parameters.target_supplier_id
            target_supplier = validate_supplier_eligibility(
                target_sup_id,
                supplier_repo=self._supplier_repo,
            )

        return ActionEvaluationInputs(
            action=action,
            product=product,
            warehouse_id=warehouse.id,
            available_quantity=available_qty,
            reorder_point=reorder_point,
            average_daily_demand=avg_demand,
            current_supplier=current_supplier,
            target_supplier=target_supplier,
            replenishment_policy=policy_type,
            target_stock=target_stock,
            enforce_reorder_trigger=enforce_reorder_trigger,
            warehouse_capacity=warehouse.capacity,
            historical_daily_demands=historical_demands,
        )
