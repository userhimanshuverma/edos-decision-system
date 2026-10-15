from __future__ import annotations

from typing import Any

from app.domain.candidate_action import (
    ActionParameters,
    ActionType,
    CandidateAction,
    PlaceOrderParameters,
    SwitchSupplierParameters,
    validate_supplier_eligibility,
)
from app.domain.replenishment import ReplenishmentCalculationResult
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.supplier_repository import SupplierRepository


class DecisionNotFoundError(KeyError):
    """Raised when the referenced decision identifier does not exist."""


class CandidateActionNotFoundError(KeyError):
    """Raised when the referenced candidate action identifier does not exist for the decision."""


class CandidateActionService:
    """Application coordination service for Candidate Actions.

    Safely coordinates candidate action validation, repository persistence,
    supplier reference checking, and Decision Graph integration with
    explicit consistency guarantees and rollback semantics.
    """

    def __init__(
        self,
        decision_repository: DecisionRepository,
        action_repository: CandidateActionRepository,
        graph_repository: DecisionGraphRepository,
        supplier_repository: SupplierRepository | None = None,
    ) -> None:
        self._decision_repo = decision_repository
        self._action_repo = action_repository
        self._graph_repo = graph_repository
        self._supplier_repo = (
            supplier_repository
            if supplier_repository is not None
            else SupplierRepository(dataset=decision_repository.dataset)
        )

    @property
    def decision_repository(self) -> DecisionRepository:
        return self._decision_repo

    @property
    def action_repository(self) -> CandidateActionRepository:
        return self._action_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository:
        return self._graph_repo

    @property
    def supplier_repository(self) -> SupplierRepository:
        return self._supplier_repo

    def create_candidate_action(
        self,
        decision_id: str,
        action_type: ActionType | str,
        parameters: ActionParameters | dict[str, Any],
        *,
        description: str | None = None,
        id: str | None = None,
    ) -> CandidateAction:
        """Coordinates validation, creation, storage, and graph linking for a candidate action.

        Guarantees:
        - Rejects unknown decision identifiers with DecisionNotFoundError.
        - Validates supplier existence and eligibility for SWITCH_SUPPLIER actions.
        - Integrates with the Decision Graph if present; rolls back stored action if graph linking fails.
        - Returns a defensive deep copy of the created CandidateAction.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        resolved_type = (
            action_type
            if isinstance(action_type, ActionType)
            else ActionType(action_type)
        )

        # Validate supplier references for SWITCH_SUPPLIER before creating action
        if resolved_type == ActionType.SWITCH_SUPPLIER:
            target_sup_id: str | None = None
            if isinstance(parameters, SwitchSupplierParameters):
                target_sup_id = parameters.target_supplier_id
            elif isinstance(parameters, dict):
                target_sup_id = parameters.get("target_supplier_id") or parameters.get("supplier_id")
            if target_sup_id is not None:
                validate_supplier_eligibility(
                    target_sup_id,
                    supplier_repo=self._supplier_repo,
                )

        act_id = id if id is not None else self._action_repo.generate_id()
        action = CandidateAction(
            id=act_id,
            decision_id=decision.id,
            action_type=resolved_type,
            parameters=parameters,
            description=description,
        )

        # Step 1: Record in candidate action repository
        stored_action = self._action_repo.record(action)

        # Step 2: Synchronize with Decision Graph if graph exists
        try:
            self._graph_repo.attach_action_node(decision.id, stored_action)
        except Exception:
            # Explicit rollback: remove candidate action if graph linking fails
            self._action_repo.remove(stored_action.id)
            raise

        return stored_action

    def create_replenishment_candidate_action(
        self,
        decision_id: str,
        calculation_result: ReplenishmentCalculationResult,
        *,
        description: str | None = None,
        id: str | None = None,
    ) -> CandidateAction:
        """Explicitly creates a PLACE_ORDER candidate action from a calculated replenishment result.

        Guarantees:
        - Maintains decoupled boundaries: does not auto-create actions during calculation.
        - Rejects zero or non-positive replenishment quantities.
        - Attaches auditable calculation metadata (policy_type, formula, target_stock).
        - Validates decision reference and updates Decision Graph.
        """
        if calculation_result.replenishment_quantity <= 0:
            raise ValueError(
                f"Cannot create PLACE_ORDER candidate action with non-positive replenishment quantity "
                f"({calculation_result.replenishment_quantity})"
            )

        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        desc = (
            description
            if description is not None
            else f"Replenish {calculation_result.replenishment_quantity} units via {calculation_result.policy_type.value}"
        )

        metadata = {
            "source": "replenishment_calculation",
            "policy_type": calculation_result.policy_type.value,
            "target_stock": calculation_result.target_stock,
            "available_quantity": calculation_result.available_quantity,
            "formula": calculation_result.formula,
        }

        act_id = id if id is not None else self._action_repo.generate_id()
        action = CandidateAction(
            id=act_id,
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=calculation_result.replenishment_quantity),
            description=desc,
            metadata=metadata,
        )

        stored_action = self._action_repo.record(action)
        try:
            self._graph_repo.attach_action_node(decision.id, stored_action)
        except Exception:
            self._action_repo.remove(stored_action.id)
            raise

        return stored_action

    def get_candidate_action(
        self,
        decision_id: str,
        action_id: str,
    ) -> CandidateAction:
        """Retrieves a single candidate action belonging to the specified decision.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            CandidateActionNotFoundError: If the action does not exist or belongs to another decision.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        norm_action_id = action_id.strip()
        action = self._action_repo.get_by_id(norm_action_id)
        if action is None:
            raise CandidateActionNotFoundError(
                f"Candidate action '{norm_action_id}' not found for decision '{norm_decision_id}'"
            )

        # Cross-decision isolation check
        if action.decision_id != decision.id:
            raise CandidateActionNotFoundError(
                f"Candidate action '{norm_action_id}' does not belong to decision '{norm_decision_id}'"
            )

        return action

    def list_candidate_actions(
        self,
        decision_id: str,
    ) -> list[CandidateAction]:
        """Lists all candidate actions for a decision in deterministic order.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self._action_repo.list_by_decision_id(norm_decision_id)
