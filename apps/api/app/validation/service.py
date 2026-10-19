from __future__ import annotations

from typing import Any

from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    SwitchSupplierParameters,
)
from app.domain.validation import (
    ActionValidationResult,
    ConstraintDefinition,
    DecisionValidationReport,
    DecisionValidationStatus,
    ValidationContextInputs,
    get_default_constraint_definitions,
    validate_candidate_action,
    validate_decision_actions,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository


class ValidationError(Exception):
    """Base exception for validation service errors."""


class DecisionNotFoundError(ValidationError, KeyError):
    """Raised when the specified decision does not exist."""


class CandidateActionNotFoundError(ValidationError, KeyError):
    """Raised when a candidate action does not exist or does not belong to the decision."""


class ValidationReportNotFoundError(ValidationError, KeyError):
    """Raised when a validation report does not exist."""


class ValidationService:
    """Application coordination service for deterministic candidate action validation.

    Evaluates candidate actions against explicitly defined hard constraints,
    ensuring actions satisfy operational rules (warehouse capacity, active status,
    supplier eligibility, budget ceilings, quantity bounds) before downstream steps.

    Guarantees:
    - Pure, deterministic evaluation: identical inputs produce identical results.
    - Zero execution side-effects: does NOT mutate inventory, place orders, or execute actions.
    - Decoupled from recommendation and approval: does NOT select recommendations or approve decisions.
    - Traceable outcomes: PASS, FAIL, and UNABLE_TO_EVALUATE preserved with evidence.
    - Missing data never silently passes: explicitly reported as UNABLE_TO_EVALUATE.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        action_repo: CandidateActionRepository,
        inventory_repo: InventoryRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        validation_repo: ValidationRepository | None = None,
        graph_repo: DecisionGraphRepository | None = None,
        dataset: Any = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._action_repo = action_repo
        shared_ds = dataset or getattr(decision_repo, "dataset", None)
        self._inventory_repo = inventory_repo or InventoryRepository(dataset=shared_ds)
        self._supplier_repo = supplier_repo or SupplierRepository(dataset=shared_ds)
        self._validation_repo = validation_repo or ValidationRepository()
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
    def supplier_repository(self) -> SupplierRepository:
        return self._supplier_repo

    @property
    def validation_repository(self) -> ValidationRepository:
        return self._validation_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository | None:
        return self._graph_repo

    def validate_action(
        self,
        decision_id: str,
        action_id: str,
        configured_constraints: list[ConstraintDefinition] | None = None,
    ) -> ActionValidationResult:
        """Deterministically validates a single candidate action against hard constraints.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            CandidateActionNotFoundError: If the action does not exist for this decision.
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

        # Resolve context entities gracefully (missing entities produce UNABLE_TO_EVALUATE, not crash)
        ds = getattr(self._inventory_repo, "dataset", None)
        product = ds.get_product(decision.product_id) if ds else None
        warehouse = ds.get_warehouse(decision.warehouse_id) if ds else None
        inventory = ds.get_inventory(decision.product_id, decision.warehouse_id) if ds else None

        current_supplier = None
        if product is not None:
            current_supplier = self._supplier_repo.get_supplier_for_product(
                product_id=product.id,
                category=product.category,
            )

        target_supplier = None
        if action.action_type == ActionType.SWITCH_SUPPLIER:
            assert isinstance(action.parameters, SwitchSupplierParameters)
            target_supplier = self._supplier_repo.get_by_id(action.parameters.target_supplier_id)

        ctx_inputs = ValidationContextInputs(
            action=action,
            product=product,
            warehouse=warehouse,
            inventory=inventory,
            current_supplier=current_supplier,
            target_supplier=target_supplier,
            configured_constraints=configured_constraints,
        )

        return validate_candidate_action(ctx_inputs)

    def validate_decision_actions(
        self,
        decision_id: str,
        *,
        action_ids: list[str] | None = None,
        configured_constraints: list[ConstraintDefinition] | None = None,
        record_to_graph: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionValidationReport:
        """Validates candidate actions for a decision and stores the resulting report.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        # Fetch candidate actions for the decision
        all_actions = self._action_repo.list_by_decision_id(decision.id)
        if action_ids is not None:
            requested_set = set(action_ids)
            found_ids = {a.id for a in all_actions}
            missing_or_unrelated = requested_set - found_ids
            if missing_or_unrelated:
                raise CandidateActionNotFoundError(
                    f"Candidate action(s) {sorted(missing_or_unrelated)} not found for decision '{norm_decision_id}'"
                )
            candidate_actions = [a for a in all_actions if a.id in requested_set]
        else:
            candidate_actions = all_actions

        # Resolve context entities
        ds = getattr(self._inventory_repo, "dataset", None)
        product = ds.get_product(decision.product_id) if ds else None
        warehouse = ds.get_warehouse(decision.warehouse_id) if ds else None
        inventory = ds.get_inventory(decision.product_id, decision.warehouse_id) if ds else None

        current_supplier = None
        if product is not None:
            current_supplier = self._supplier_repo.get_supplier_for_product(
                product_id=product.id,
                category=product.category,
            )

        target_suppliers: dict[str, Any] = {}
        for action in candidate_actions:
            if action.action_type == ActionType.SWITCH_SUPPLIER:
                assert isinstance(action.parameters, SwitchSupplierParameters)
                t_id = action.parameters.target_supplier_id
                t_sup = self._supplier_repo.get_by_id(t_id)
                if t_sup is not None:
                    target_suppliers[t_id] = t_sup

        report_id = self._validation_repo.generate_id()

        report = validate_decision_actions(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            candidate_actions=candidate_actions,
            product=product,
            warehouse=warehouse,
            inventory=inventory,
            current_supplier=current_supplier,
            target_suppliers=target_suppliers,
            configured_constraints=configured_constraints,
            report_id=report_id,
            metadata=metadata or {},
        )

        stored_report = self._validation_repo.record(report)

        if record_to_graph and self._graph_repo is not None:
            try:
                self._graph_repo.attach_validation_node(decision.id, stored_report)
            except Exception:
                self._validation_repo.remove(stored_report.id)
                raise

        return stored_report

    def get_latest_validation(self, decision_id: str) -> DecisionValidationReport | None:
        """Retrieves the most recent validation report for a decision."""
        norm_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_id}' not found")
        return self._validation_repo.get_latest_for_decision(norm_id)

    def get_validation_by_id(self, validation_id: str) -> DecisionValidationReport | None:
        """Retrieves a specific validation report by identifier (VAL-XXXX)."""
        return self._validation_repo.get_by_id(validation_id)
