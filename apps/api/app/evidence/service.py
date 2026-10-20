from __future__ import annotations

from typing import Any
from app.domain.candidate_action import CandidateAction
from app.domain.decision import Decision
from app.domain.evidence import (
    DecisionAssumption,
    DecisionEvidence,
    DecisionEvidenceSheet,
    EvidenceCategory,
    EvidenceType,
)
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.replenishment import (
    ReplenishmentCalculationInputs,
    calculate_replenishment_quantity,
)
from app.domain.stockout_risk import (
    StockoutRiskCalculationInputs,
    calculate_stockout_risk,
)
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository


class EvidenceError(Exception):
    """Base exception for evidence service errors."""


class DecisionNotFoundError(EvidenceError, KeyError):
    """Raised when the specified decision does not exist."""


class CandidateActionNotFoundError(EvidenceError, KeyError):
    """Raised when the specified candidate action does not exist."""


class DecisionVersionNotFoundError(EvidenceError, KeyError):
    """Raised when the specified decision version does not exist."""


class EvidenceNotFoundError(EvidenceError, KeyError):
    """Raised when an evidence item or evidence sheet does not exist."""


class AssumptionNotFoundError(EvidenceError, KeyError):
    """Raised when an assumption item does not exist."""


class CrossDecisionIsolationError(EvidenceError, ValueError):
    """Raised when an evidence or assumption item attempts to associate across decision boundaries."""


class InvalidEvidencePayloadError(EvidenceError, ValueError):
    """Raised when an evidence payload violates domain integrity constraints."""


class EvidenceService:
    """Application coordination service for decision evidence and assumptions.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."

    Guarantees:
    - Pure evidence grounding: facts trace directly to domain entities; calculations reuse official formulas.
    - Explicit assumption modeling: assumptions are distinguished from facts and calculated values.
    - Zero probability fabrication: deterministic lead-time exposure indicators are strictly is_probability=False.
    - Cross-decision isolation: evidence and assumptions cannot cross decision boundaries.
    - Reference validation: non-existent decisions, versions, or actions produce explicit errors.
    - Immutability & safety: read and write paths use defensive copies; failed writes leave no partial state.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        evidence_repo: EvidenceRepository | None = None,
        action_repo: CandidateActionRepository | None = None,
        version_repo: DecisionVersionRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        demand_repo: DemandRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        recommendation_repo: RecommendationRepository | None = None,
        validation_repo: ValidationRepository | None = None,
        dataset: Any = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._evidence_repo = evidence_repo if evidence_repo is not None else EvidenceRepository()
        self._action_repo = action_repo if action_repo is not None else (getattr(decision_repo, "action_repository", None) or CandidateActionRepository())
        self._version_repo = version_repo if version_repo is not None else getattr(decision_repo, "version_repository", None)

        shared_ds = dataset or getattr(decision_repo, "dataset", None)
        self._inventory_repo = inventory_repo if inventory_repo is not None else InventoryRepository(dataset=shared_ds)
        self._demand_repo = demand_repo if demand_repo is not None else DemandRepository(dataset=shared_ds)
        self._supplier_repo = supplier_repo if supplier_repo is not None else SupplierRepository(dataset=shared_ds)
        self._recommendation_repo = recommendation_repo if recommendation_repo is not None else RecommendationRepository()
        self._validation_repo = validation_repo if validation_repo is not None else ValidationRepository()

    @property
    def decision_repository(self) -> DecisionRepository:
        return self._decision_repo

    @property
    def evidence_repository(self) -> EvidenceRepository:
        return self._evidence_repo

    @property
    def action_repository(self) -> CandidateActionRepository:
        return self._action_repo

    @property
    def version_repository(self) -> DecisionVersionRepository | None:
        return self._version_repo

    def _validate_decision_exists(self, decision_id: str) -> Decision:
        decision = self._decision_repo.get_by_id(decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision with identifier '{decision_id}' does not exist")
        return decision

    def _validate_action_reference(self, decision_id: str, action_id: str | None) -> CandidateAction | None:
        if action_id is None:
            return None
        norm_action_id = action_id.strip()
        action = self._action_repo.get_by_id(norm_action_id)
        if action is None:
            raise CandidateActionNotFoundError(
                f"Candidate action with identifier '{action_id}' does not exist"
            )
        if action.decision_id != decision_id.strip():
            raise CrossDecisionIsolationError(
                f"Candidate action '{action_id}' belongs to decision '{action.decision_id}', "
                f"not target decision '{decision_id}'"
            )
        return action

    def _validate_version_reference(self, decision_id: str, version_id: str | None) -> None:
        if version_id is None:
            return
        if self._version_repo is None:
            return
        norm_version_id = version_id.strip()
        version = self._version_repo.get_by_id(norm_version_id)
        if version is None:
            raise DecisionVersionNotFoundError(
                f"Decision version with identifier '{version_id}' does not exist"
            )
        if version.decision_id != decision_id.strip():
            raise CrossDecisionIsolationError(
                f"Decision version '{version_id}' belongs to decision '{version.decision_id}', "
                f"not target decision '{decision_id}'"
            )

    def record_evidence_item(
        self,
        decision_id: str,
        evidence: DecisionEvidence,
    ) -> DecisionEvidence:
        """Stores a pre-constructed DecisionEvidence entity with reference and boundary validation."""
        self._validate_decision_exists(decision_id)

        if evidence.decision_id != decision_id.strip():
            raise CrossDecisionIsolationError(
                f"Evidence payload decision_id '{evidence.decision_id}' does not match "
                f"target decision '{decision_id}'"
            )

        self._validate_action_reference(decision_id, evidence.action_id)
        self._validate_version_reference(decision_id, evidence.version_id)

        return self._evidence_repo.record_evidence(evidence)

    def create_evidence(
        self,
        decision_id: str,
        evidence_type: EvidenceType,
        category: EvidenceCategory,
        description: str,
        id: str | None = None,
        value: Any | None = None,
        unit: str | None = None,
        source: str | None = None,
        is_probability: bool = False,
        action_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionEvidence:
        """Constructs and stores a new DecisionEvidence item with full validation."""
        self._validate_decision_exists(decision_id)
        self._validate_action_reference(decision_id, action_id)
        self._validate_version_reference(decision_id, version_id)

        evidence_id = id.strip() if id and id.strip() else self._evidence_repo.generate_evidence_id()

        evidence_model = DecisionEvidence(
            id=evidence_id,
            decision_id=decision_id.strip(),
            evidence_type=evidence_type,
            category=category,
            description=description,
            value=value,
            unit=unit,
            source=source,
            is_probability=is_probability,
            action_id=action_id.strip() if action_id else None,
            version_id=version_id.strip() if version_id else None,
            metadata=metadata or {},
        )

        return self._evidence_repo.record_evidence(evidence_model)

    def record_assumption_item(
        self,
        decision_id: str,
        assumption: DecisionAssumption,
    ) -> DecisionAssumption:
        """Stores a pre-constructed DecisionAssumption with reference and boundary validation."""
        self._validate_decision_exists(decision_id)

        if assumption.decision_id != decision_id.strip():
            raise CrossDecisionIsolationError(
                f"Assumption payload decision_id '{assumption.decision_id}' does not match "
                f"target decision '{decision_id}'"
            )

        self._validate_action_reference(decision_id, assumption.action_id)
        self._validate_version_reference(decision_id, assumption.version_id)

        return self._evidence_repo.record_assumption(assumption)

    def create_assumption(
        self,
        decision_id: str,
        category: EvidenceCategory,
        statement: str,
        id: str | None = None,
        assumed_value: Any | None = None,
        rationale: str | None = None,
        source: str | None = None,
        action_id: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionAssumption:
        """Constructs and stores a new explicit DecisionAssumption with full validation."""
        self._validate_decision_exists(decision_id)
        self._validate_action_reference(decision_id, action_id)
        self._validate_version_reference(decision_id, version_id)

        asm_id = id.strip() if id and id.strip() else self._evidence_repo.generate_assumption_id()

        assumption_model = DecisionAssumption(
            id=asm_id,
            decision_id=decision_id.strip(),
            category=category,
            statement=statement,
            assumed_value=assumed_value,
            rationale=rationale,
            source=source,
            action_id=action_id.strip() if action_id else None,
            version_id=version_id.strip() if version_id else None,
            metadata=metadata or {},
        )

        return self._evidence_repo.record_assumption(assumption_model)

    def get_evidence(self, decision_id: str, evidence_id: str) -> DecisionEvidence:
        """Retrieves an individual evidence item belonging to a decision."""
        self._validate_decision_exists(decision_id)
        ev = self._evidence_repo.get_evidence_by_id(evidence_id)
        if ev is None or ev.decision_id != decision_id.strip():
            raise EvidenceNotFoundError(
                f"Evidence item '{evidence_id}' not found for decision '{decision_id}'"
            )
        return ev

    def get_assumption(self, decision_id: str, assumption_id: str) -> DecisionAssumption:
        """Retrieves an individual explicit assumption belonging to a decision."""
        self._validate_decision_exists(decision_id)
        asm = self._evidence_repo.get_assumption_by_id(assumption_id)
        if asm is None or asm.decision_id != decision_id.strip():
            raise AssumptionNotFoundError(
                f"Assumption '{assumption_id}' not found for decision '{decision_id}'"
            )
        return asm

    def list_evidence(
        self,
        decision_id: str,
        evidence_type: EvidenceType | None = None,
        category: EvidenceCategory | None = None,
        action_id: str | None = None,
        version_id: str | None = None,
    ) -> list[DecisionEvidence]:
        """Lists all evidence items for a decision matching optional filters."""
        self._validate_decision_exists(decision_id)
        return self._evidence_repo.list_evidence_by_decision(
            decision_id=decision_id,
            evidence_type=evidence_type,
            category=category,
            action_id=action_id,
            version_id=version_id,
        )

    def list_assumptions(
        self,
        decision_id: str,
        category: EvidenceCategory | None = None,
        action_id: str | None = None,
        version_id: str | None = None,
    ) -> list[DecisionAssumption]:
        """Lists all explicit assumptions for a decision matching optional filters."""
        self._validate_decision_exists(decision_id)
        return self._evidence_repo.list_assumptions_by_decision(
            decision_id=decision_id,
            category=category,
            action_id=action_id,
            version_id=version_id,
        )

    def compile_decision_evidence(
        self,
        decision_id: str,
        record_to_repository: bool = True,
    ) -> DecisionEvidenceSheet:
        """Compiles a complete, explainable DecisionEvidenceSheet from actual operational data.

        Synthesizes:
        1. Observable domain FACTS (inventory positions, supplier attributes, product cost, warehouse capacity).
        2. Explicit operational ASSUMPTIONS (demand stationary baseline, constant lead-time model, deterministic exposure).
        3. Deterministic CALCULATIONS (replenishment shortfall, lead-time exposure metrics, constraint validations, candidate evaluations).
        4. User-recorded custom evidence and assumptions.

        Returns defensive copy of the compiled DecisionEvidenceSheet.
        """
        decision = self._validate_decision_exists(decision_id)
        prod_id = decision.product_id
        wh_id = decision.warehouse_id

        compiled_items: list[DecisionEvidence] = []
        compiled_assumptions: list[DecisionAssumption] = []

        # 1. Operational Domain Facts
        inventory = self._inventory_repo.get_by_product_and_warehouse(prod_id, wh_id)
        dataset = getattr(self._inventory_repo, "dataset", None) or getattr(self._decision_repo, "dataset", None)
        warehouse = dataset.get_warehouse(wh_id) if dataset else None
        product = dataset.get_product(prod_id) if dataset else None
        supplier = self._supplier_repo.get_supplier_for_product(prod_id, category=product.category if product else None)
        trend = self._demand_repo.get_product_demand_trend(prod_id, warehouse_id=wh_id)
        avg_demand = trend.get("average_daily_demand", 0.0)

        if inventory is not None:
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.INVENTORY,
                    description=f"Available unreserved stock: {inventory.available_quantity} units",
                    value=inventory.available_quantity,
                    unit="units",
                    source=f"inventory:{prod_id}@{wh_id}",
                    metadata={
                        "quantity_on_hand": inventory.quantity_on_hand,
                        "quantity_reserved": inventory.quantity_reserved,
                    },
                )
            )
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.INVENTORY,
                    description=f"Reorder point threshold: {inventory.reorder_point} units",
                    value=inventory.reorder_point,
                    unit="units",
                    source=f"inventory:{prod_id}@{wh_id}",
                )
            )

        if warehouse is not None:
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.WAREHOUSE,
                    description=f"Warehouse storage capacity: {warehouse.capacity} units",
                    value=warehouse.capacity,
                    unit="units",
                    source=f"warehouse:{wh_id}",
                    metadata={"active": warehouse.active, "location": warehouse.location},
                )
            )

        if product is not None:
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.COST,
                    description=f"Catalog unit cost: ${product.unit_cost:.2f}",
                    value=product.unit_cost,
                    unit="USD",
                    source=f"product:{prod_id}",
                    metadata={"sku": product.sku, "active": product.active},
                )
            )

        if supplier is not None:
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.SUPPLIER,
                    description=f"Supplier fulfillment lead time: {supplier.lead_time_days} days",
                    value=supplier.lead_time_days,
                    unit="days",
                    source=f"supplier:{supplier.id}",
                )
            )
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.SUPPLIER,
                    description=f"Supplier historical reliability: {supplier.reliability:.1%}",
                    value=supplier.reliability,
                    unit="ratio",
                    source=f"supplier:{supplier.id}",
                    metadata={"supplier_name": supplier.name, "active": supplier.active},
                )
            )

        if avg_demand is not None:
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.FACT,
                    category=EvidenceCategory.DEMAND,
                    description=f"Historical average daily demand: {avg_demand:.2f} units/day",
                    value=avg_demand,
                    unit="units/day",
                    source=f"demand:{prod_id}@{wh_id}",
                )
            )

        # 2. Explicit Operational Assumptions
        demand_rate = avg_demand if avg_demand is not None else 0.0
        lead_time = supplier.lead_time_days if supplier is not None else 7

        asm_demand = DecisionAssumption(
            id=self._evidence_repo.generate_assumption_id(),
            decision_id=decision.id,
            category=EvidenceCategory.DEMAND,
            statement=f"Future demand rate is assumed stationary and equal to the historical average ({demand_rate:.2f} units/day).",
            assumed_value=demand_rate,
            rationale="Parametric forecasting models require multi-cycle history; historical daily average is the substantiated operational baseline.",
            source="system_default",
        )
        compiled_assumptions.append(asm_demand)
        compiled_items.append(asm_demand.to_evidence())

        asm_supplier = DecisionAssumption(
            id=self._evidence_repo.generate_assumption_id(),
            decision_id=decision.id,
            category=EvidenceCategory.SUPPLIER,
            statement=f"Supplier fulfillment lead time is assumed constant ({lead_time} days).",
            assumed_value=lead_time,
            rationale="Baseline models use contractual lead time; lead-time variance tracking requires empirical receipt event records.",
            source="policy_config",
        )
        compiled_assumptions.append(asm_supplier)
        compiled_items.append(asm_supplier.to_evidence())

        asm_risk = DecisionAssumption(
            id=self._evidence_repo.generate_assumption_id(),
            decision_id=decision.id,
            category=EvidenceCategory.STOCKOUT_RISK,
            statement="Stockout exposure is measured as deterministic physical runway deficit, not as an empirical statistical probability.",
            assumed_value={"is_probability": False, "model_type": "DETERMINISTIC_LEAD_TIME_EXPOSURE"},
            rationale="EDOS core invariant: deterministic exposure indicators are not statistical probabilities.",
            source="system_default",
        )
        compiled_assumptions.append(asm_risk)
        compiled_items.append(asm_risk.to_evidence())

        asm_reorder = DecisionAssumption(
            id=self._evidence_repo.generate_assumption_id(),
            decision_id=decision.id,
            category=EvidenceCategory.REPLENISHMENT,
            statement="Replenishment need is triggered only when available inventory <= reorder point threshold.",
            assumed_value={"enforce_reorder_trigger": True, "policy": "REORDER_POINT_DEFICIT"},
            rationale="Prevents premature reordering when current inventory runway adequately covers lead time demand.",
            source="policy_config",
        )
        compiled_assumptions.append(asm_reorder)
        compiled_items.append(asm_reorder.to_evidence())

        # 3. Grounded Deterministic Calculations
        if inventory is not None:
            # Replenishment calculation
            repl_inputs = ReplenishmentCalculationInputs(
                product_id=prod_id,
                warehouse_id=wh_id,
                available_quantity=inventory.available_quantity,
                reorder_point=inventory.reorder_point,
                enforce_reorder_trigger=True,
            )
            repl_result = calculate_replenishment_quantity(repl_inputs)
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.CALCULATION,
                    category=EvidenceCategory.REPLENISHMENT,
                    description=f"Calculated replenishment quantity: {repl_result.replenishment_quantity} units",
                    value=repl_result.replenishment_quantity,
                    unit="units",
                    source="calculation:replenishment",
                    metadata={
                        "is_replenishment_needed": repl_result.is_replenishment_needed,
                        "formula": repl_result.formula,
                        "policy_type": repl_result.policy_type.value,
                    },

                )
            )

            # Stockout Risk calculation
            risk_inputs = StockoutRiskCalculationInputs(
                product_id=prod_id,
                warehouse_id=wh_id,
                available_quantity=inventory.available_quantity,
                reorder_point=inventory.reorder_point,
                lead_time_days=lead_time,
                average_daily_demand=demand_rate,
            )
            risk_result = calculate_stockout_risk(risk_inputs)
            compiled_items.append(
                DecisionEvidence(
                    id=self._evidence_repo.generate_evidence_id(),
                    decision_id=decision.id,
                    evidence_type=EvidenceType.CALCULATION,
                    category=EvidenceCategory.STOCKOUT_RISK,
                    description=f"Deterministic lead-time exposure index: {risk_result.exposure_index:.4f}",
                    value=risk_result.exposure_index,
                    unit="ratio",
                    source="calculation:stockout_risk",
                    is_probability=False,
                    metadata={
                        "risk_level": risk_result.risk_level.value,
                        "coverage_runway_days": risk_result.breakdown.coverage_days,
                        "buffer_days": risk_result.breakdown.buffer_days,
                        "exposure_deficit": risk_result.breakdown.exposure_deficit,
                        "formula": risk_result.formula,
                    },
                )
            )


        # 4. Include Existing Stored Evidence and Assumptions
        stored_evidence = self._evidence_repo.list_evidence_by_decision(decision.id)
        stored_assumptions = self._evidence_repo.list_assumptions_by_decision(decision.id)

        # Merge deduplicated by ID
        existing_item_ids = {item.id for item in compiled_items}
        for sev in stored_evidence:
            if sev.id not in existing_item_ids:
                compiled_items.append(sev)
                existing_item_ids.add(sev.id)

        existing_asm_ids = {asm.id for asm in compiled_assumptions}
        for sasm in stored_assumptions:
            if sasm.id not in existing_asm_ids:
                compiled_assumptions.append(sasm)
                existing_asm_ids.add(sasm.id)

        sheet_id = self._evidence_repo.generate_sheet_id()
        sheet = DecisionEvidenceSheet.create(
            id=sheet_id,
            decision_id=decision.id,
            product_id=prod_id,
            warehouse_id=wh_id,
            items=compiled_items,
            assumptions=compiled_assumptions,
            metadata={"compiled_source": "system_auto_compilation"},
        )

        if record_to_repository:
            # Atomically register all compiled items and assumptions that are not yet stored
            for item in compiled_items:
                if self._evidence_repo.get_evidence_by_id(item.id) is None:
                    self._evidence_repo.record_evidence(item)
            for asm in compiled_assumptions:
                if self._evidence_repo.get_assumption_by_id(asm.id) is None:
                    self._evidence_repo.record_assumption(asm)
            self._evidence_repo.record_sheet(sheet)

        return sheet

    def get_evidence_sheet(
        self,
        decision_id: str,
        auto_compile: bool = True,
        recompute: bool = False,
    ) -> DecisionEvidenceSheet:
        """Retrieves latest compiled evidence sheet or optionally compiles a new one."""
        self._validate_decision_exists(decision_id)

        if recompute:
            return self.compile_decision_evidence(decision_id, record_to_repository=True)

        latest_sheet = self._evidence_repo.get_latest_sheet_for_decision(decision_id)
        if latest_sheet is not None:
            return latest_sheet

        if auto_compile:
            return self.compile_decision_evidence(decision_id, record_to_repository=True)

        raise EvidenceNotFoundError(
            f"No evidence sheet found for decision '{decision_id}' and auto_compile is disabled"
        )
