from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.action_evaluation import (
    ActionEvaluationInputs,
    ActionEvaluationResult,
    evaluate_candidate_action,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceInputType,
    ProvenanceRuleType,
    ProvenanceStepStatus,
)
from app.domain.recommendation import (
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
    select_deterministic_recommendation,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.domain.scenario import (
    DecisionScenarioRecord,
    MetricDelta,
    ScenarioActionEvaluationSnapshot,
    ScenarioComparison,
    ScenarioFieldDifference,
    ScenarioIncompleteReason,
    ScenarioIncompleteReasonCode,
    ScenarioOverrides,
    ScenarioResultSnapshot,
    ScenarioStatus,
    compare_scenario_results,
)
from app.domain.supplier import Supplier
from app.domain.validation import (
    ActionValidationResult,
    DecisionValidationReport,
    ValidationContextInputs,
    validate_candidate_action,
    validate_decision_actions,
)
from app.domain.warehouse import Warehouse
from app.evaluation.service import ActionEvaluationService
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.provenance_repository import ProvenanceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository
from app.validation.service import ValidationService


class DecisionScenarioError(Exception):
    """Base exception for Decision Scenario service errors."""


class DecisionNotFoundError(DecisionScenarioError, KeyError):
    """Raised when the specified business decision does not exist."""


class DecisionVersionNotFoundError(DecisionScenarioError, KeyError):
    """Raised when the specified decision version does not exist."""


class ProvenanceTraceNotFoundError(DecisionScenarioError, KeyError):
    """Raised when the requested baseline provenance trace is not found."""


class ScenarioRecordNotFoundError(DecisionScenarioError, KeyError):
    """Raised when the requested scenario record is not found."""


class CrossDecisionIsolationError(DecisionScenarioError, ValueError):
    """Raised when a scenario reference crosses decision boundaries or violates isolation."""


class InvalidScenarioRequestError(DecisionScenarioError, ValueError):
    """Raised when scenario arguments, overrides, or payloads are semantically invalid."""


class ScenarioService:
    """Core domain coordination service for Day 25 Scenario Engine.

    Answers the fundamental business question:
    "How would the existing decision change if specific business assumptions changed?"

    Core Principles:
    - "The system calculates. AI explains. Humans approve."
    - Zero AI-based calculations: pure deterministic re-evaluation.
    - Zero live operational mutation: uses isolated deep copies of historical recorded inputs.
    - Zero fabrication: missing historical data yields INCOMPLETE with structured actionable reasons.
    - Preserves historical immutability: never mutates original decisions, versions, traces, or audit history.
    - Full decision and version isolation: cross-decision references are strictly rejected.
    - Supported override categories:
        1. Demand: demand_value (units/day) or demand_multiplier
        2. Supplier lead time: lead_time_days (calendar days)
        3. Cost: unit_cost (USD) or cost_multiplier
    - Structured baseline-versus-scenario comparisons:
        quantities, procurement costs, lead-time exposure indices, constraints, and recommendations.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        scenario_repo: ScenarioRepository,
        provenance_repo: ProvenanceRepository,
        action_repo: CandidateActionRepository,
        version_repo: DecisionVersionRepository | None = None,
        recommendation_repo: RecommendationRepository | None = None,
        validation_repo: ValidationRepository | None = None,
        evaluation_service: ActionEvaluationService | None = None,
        inventory_repo: InventoryRepository | None = None,
        demand_repo: DemandRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        graph_repo: DecisionGraphRepository | None = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._scenario_repo = scenario_repo
        self._provenance_repo = provenance_repo
        self._action_repo = action_repo
        self._version_repo = version_repo
        self._recommendation_repo = (
            recommendation_repo if recommendation_repo is not None else RecommendationRepository()
        )
        self._validation_repo = (
            validation_repo if validation_repo is not None else ValidationRepository()
        )
        self._graph_repo = graph_repo

        shared_ds = getattr(decision_repo, "dataset", None)
        self._inventory_repo = (
            inventory_repo if inventory_repo is not None else InventoryRepository(dataset=shared_ds)
        )
        self._demand_repo = (
            demand_repo if demand_repo is not None else DemandRepository(dataset=shared_ds)
        )
        self._supplier_repo = (
            supplier_repo if supplier_repo is not None else SupplierRepository(dataset=shared_ds)
        )
        self._evaluation_service = (
            evaluation_service
            if evaluation_service is not None
            else ActionEvaluationService(
                decision_repo=decision_repo,
                action_repo=action_repo,
                inventory_repo=self._inventory_repo,
                demand_repo=self._demand_repo,
                supplier_repo=self._supplier_repo,
                graph_repo=graph_repo,
            )
        )

    @property
    def decision_repository(self) -> DecisionRepository:
        return self._decision_repo

    @property
    def scenario_repository(self) -> ScenarioRepository:
        return self._scenario_repo

    @property
    def provenance_repository(self) -> ProvenanceRepository:
        return self._provenance_repo

    @property
    def version_repository(self) -> DecisionVersionRepository | None:
        return self._version_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository | None:
        return self._graph_repo

    def execute_scenario(
        self,
        decision_id: str,
        overrides: ScenarioOverrides,
        *,
        version_id: str | None = None,
        trace_id: str | None = None,
        name: str | None = None,
        record_to_graph: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionScenarioRecord:
        """Executes what-if scenario assumptions against an established baseline decision.

        1. Validates decision exists and version isolation holds.
        2. Retrieves the baseline provenance trace representing recorded inputs and rules.
        3. If historical baseline data is incomplete or missing, returns an honest INCOMPLETE record.
        4. Reconstructs baseline inputs and evaluates baseline results.
        5. Applies overrides to an isolated copy of inputs.
        6. Deterministically recalculates outputs using existing domain services.
        7. Produces a structured comparison between baseline and scenario results.
        8. Stores and returns an immutable DecisionScenarioRecord.
        """
        # 1. Validate Decision Exists
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        # 2. Validate Version Reference (if provided)
        resolved_version_id = None
        if version_id is not None:
            norm_ver_id = version_id.strip()
            if self._version_repo is None:
                raise DecisionVersionNotFoundError(
                    f"Decision version repository not configured, cannot verify version '{norm_ver_id}'"
                )
            version_record = self._version_repo.get_by_id(norm_ver_id)
            if version_record is None:
                raise DecisionVersionNotFoundError(f"Decision version '{norm_ver_id}' not found")
            if version_record.decision_id != decision.id:
                raise CrossDecisionIsolationError(
                    f"Version '{norm_ver_id}' belongs to decision '{version_record.decision_id}', "
                    f"not requested decision '{decision.id}'"
                )
            resolved_version_id = version_record.id

        # 3. Locate Original Provenance Trace
        trace: DecisionProvenanceTrace | None = None
        if trace_id is not None:
            norm_trace_id = trace_id.strip()
            trace = self._provenance_repo.get_by_id(norm_trace_id)
            if trace is None:
                raise ProvenanceTraceNotFoundError(f"Provenance trace '{norm_trace_id}' not found")
            if trace.decision_id != decision.id:
                raise CrossDecisionIsolationError(
                    f"Provenance trace '{norm_trace_id}' belongs to decision '{trace.decision_id}', "
                    f"not requested decision '{decision.id}'"
                )
            if resolved_version_id is not None and trace.version_id is not None:
                if trace.version_id != resolved_version_id:
                    raise CrossDecisionIsolationError(
                        f"Trace '{norm_trace_id}' is bound to version '{trace.version_id}', "
                        f"which conflicts with requested version '{resolved_version_id}'"
                    )
        else:
            trace = self._provenance_repo.get_latest_for_decision(
                decision.id,
                version_id=resolved_version_id,
            )

        scenario_id = self._scenario_repo.generate_id()
        scenario_exec_id = self._scenario_repo.generate_execution_id()
        now_utc = datetime.now(timezone.utc)

        # 4. Handle Missing Provenance Trace (Incomplete Scenario)
        if trace is None:
            incomplete_reasons = [
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_PROVENANCE_TRACE,
                    message=(
                        f"No provenance trace found for decision '{decision.id}'. "
                        "Historical operational inputs, rules, and calculation steps were not recorded."
                    ),
                    details={
                        "decision_id": decision.id,
                        "version_id": resolved_version_id,
                    },
                )
            ]
            record = DecisionScenarioRecord(
                id=scenario_id,
                decision_id=decision.id,
                version_id=resolved_version_id,
                baseline_trace_id=None,
                baseline_replay_id=None,
                scenario_execution_id=scenario_exec_id,
                name=name,
                created_at=now_utc,
                status=ScenarioStatus.INCOMPLETE,
                overrides=overrides,
                baseline_inputs_summary={},
                applied_inputs_summary={},
                baseline_result=None,
                scenario_result=None,
                comparison=None,
                incomplete_reasons=incomplete_reasons,
                error_message=None,
                metadata=metadata or {},
            )
            return self._scenario_repo.record(record)

        # 5. Check Historical Input Completeness
        incomplete_reasons = self._check_trace_input_completeness(trace)
        if incomplete_reasons:
            record = DecisionScenarioRecord(
                id=scenario_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                baseline_trace_id=trace.id,
                baseline_replay_id=None,
                scenario_execution_id=scenario_exec_id,
                name=name,
                created_at=now_utc,
                status=ScenarioStatus.INCOMPLETE,
                overrides=overrides,
                baseline_inputs_summary=self._build_inputs_summary(trace),
                applied_inputs_summary={},
                baseline_result=None,
                scenario_result=None,
                comparison=None,
                incomplete_reasons=incomplete_reasons,
                error_message=None,
                metadata=metadata or {},
            )
            return self._scenario_repo.record(record)

        # 6. Reconstruct Baseline Inputs & Execute Recalculation
        try:
            (
                baseline_result,
                scenario_result,
                baseline_inputs_summary,
                applied_inputs_summary,
            ) = self._execute_scenario_evaluation(
                decision=decision,
                trace=trace,
                overrides=overrides,
            )

            comparison = compare_scenario_results(
                baseline=baseline_result,
                scenario=scenario_result,
                overrides=overrides,
            )

            record = DecisionScenarioRecord(
                id=scenario_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                baseline_trace_id=trace.id,
                baseline_replay_id=None,
                scenario_execution_id=scenario_exec_id,
                name=name,
                created_at=now_utc,
                status=ScenarioStatus.COMPLETED,
                overrides=overrides,
                baseline_inputs_summary=baseline_inputs_summary,
                applied_inputs_summary=applied_inputs_summary,
                baseline_result=baseline_result,
                scenario_result=scenario_result,
                comparison=comparison,
                incomplete_reasons=[],
                error_message=None,
                metadata=metadata or {},
            )

            # Optional Decision Graph Metadata Enrichment
            if record_to_graph and self._graph_repo is not None:
                self._enrich_graph_with_scenario(decision.id, record)

            return self._scenario_repo.record(record)

        except Exception as exc:
            record = DecisionScenarioRecord(
                id=scenario_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                baseline_trace_id=trace.id,
                baseline_replay_id=None,
                scenario_execution_id=scenario_exec_id,
                name=name,
                created_at=now_utc,
                status=ScenarioStatus.FAILED,
                overrides=overrides,
                baseline_inputs_summary=self._build_inputs_summary(trace),
                applied_inputs_summary={},
                baseline_result=None,
                scenario_result=None,
                comparison=None,
                incomplete_reasons=[],
                error_message=f"Scenario execution failed: {type(exc).__name__}: {exc}",
                metadata=metadata or {},
            )
            return self._scenario_repo.record(record)

    def get_scenario_record(
        self,
        decision_id: str,
        scenario_id: str,
    ) -> DecisionScenarioRecord:
        """Retrieves an individual scenario record by ID, strictly enforcing decision isolation."""
        norm_dec_id = decision_id.strip()
        norm_scn_id = scenario_id.strip()

        record = self._scenario_repo.get_by_id(norm_scn_id)
        if record is None:
            raise ScenarioRecordNotFoundError(
                f"Scenario record '{norm_scn_id}' not found for decision '{norm_dec_id}'"
            )
        if record.decision_id != norm_dec_id:
            raise CrossDecisionIsolationError(
                f"Scenario record '{norm_scn_id}' belongs to decision '{record.decision_id}', "
                f"not requested decision '{norm_dec_id}'"
            )
        return record

    def get_latest_scenario(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> DecisionScenarioRecord | None:
        """Retrieves the most recent scenario record for a decision (and optional version)."""
        norm_dec_id = decision_id.strip()
        norm_ver_id = version_id.strip() if version_id is not None else None

        decision = self._decision_repo.get_by_id(norm_dec_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_dec_id}' not found")

        return self._scenario_repo.get_latest_for_decision(
            decision_id=norm_dec_id,
            version_id=norm_ver_id,
        )

    def list_scenario_records(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> list[DecisionScenarioRecord]:
        """Lists all scenario records for a decision, chronologically descending."""
        norm_dec_id = decision_id.strip()
        norm_ver_id = version_id.strip() if version_id is not None else None

        decision = self._decision_repo.get_by_id(norm_dec_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_dec_id}' not found")

        return self._scenario_repo.list_by_decision_id(
            decision_id=norm_dec_id,
            version_id=norm_ver_id,
        )

    def get_scenario_comparison(
        self,
        decision_id: str,
        scenario_id: str,
    ) -> ScenarioComparison:
        """Retrieves baseline-versus-scenario comparison results for an executed scenario."""
        record = self.get_scenario_record(decision_id=decision_id, scenario_id=scenario_id)
        if record.comparison is None:
            raise ScenarioRecordNotFoundError(
                f"Scenario record '{scenario_id}' has status '{record.status.value}' and contains no comparison"
            )
        return record.comparison

    # -----------------------------------------------------------------------
    # Internal Helpers: Validation, Reconstruction, and Recalculation
    # -----------------------------------------------------------------------

    def _check_trace_input_completeness(
        self,
        trace: DecisionProvenanceTrace,
    ) -> list[ScenarioIncompleteReason]:
        """Validates that all required operational inputs and rules are recorded and available."""
        reasons: list[ScenarioIncompleteReason] = []

        # 1. Product input
        prod_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.PRODUCT), None)
        if prod_inp is None:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Product catalog input record is missing from the provenance trace.",
                    details={"input_type": "PRODUCT"},
                )
            )
        elif prod_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(prod_inp.value, dict):
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical product catalog data was marked unavailable or missing during execution.",
                    details={"input_type": "PRODUCT", "status": prod_inp.status.value},
                )
            )

        # 2. Warehouse input
        wh_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.WAREHOUSE), None)
        if wh_inp is None:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Warehouse facility input record is missing from the provenance trace.",
                    details={"input_type": "WAREHOUSE"},
                )
            )
        elif wh_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(wh_inp.value, dict):
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical warehouse facility data was marked unavailable or missing during execution.",
                    details={"input_type": "WAREHOUSE", "status": wh_inp.status.value},
                )
            )

        # 3. Inventory input
        inv_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.INVENTORY), None)
        if inv_inp is None:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Inventory position input record is missing from the provenance trace.",
                    details={"input_type": "INVENTORY"},
                )
            )
        elif inv_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(inv_inp.value, dict):
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical inventory position was marked unavailable during execution.",
                    details={"input_type": "INVENTORY", "status": inv_inp.status.value},
                )
            )

        # 4. Demand input
        dem_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.DEMAND), None)
        if dem_inp is None:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Historical demand trend input record is missing from the provenance trace.",
                    details={"input_type": "DEMAND"},
                )
            )
        elif dem_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(dem_inp.value, dict):
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical demand metrics were marked unavailable during execution.",
                    details={"input_type": "DEMAND", "status": dem_inp.status.value},
                )
            )

        # 5. Primary Supplier input
        sup_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.SUPPLIER), None)
        if sup_inp is None:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Primary supplier input record is missing from the provenance trace.",
                    details={"input_type": "SUPPLIER"},
                )
            )
        elif sup_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(sup_inp.value, dict):
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Primary supplier operational metrics were marked unavailable during execution.",
                    details={"input_type": "SUPPLIER", "status": sup_inp.status.value},
                )
            )

        # 6. Candidate action inputs
        act_inps = [i for i in trace.inputs if i.input_type == ProvenanceInputType.CANDIDATE_ACTION]
        if not act_inps:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_CANDIDATE_ACTIONS,
                    message="No candidate actions were recorded in the provenance trace.",
                    details={},
                )
            )

        # 7. Replenishment policy rule definition
        pol_rule = next((r for r in trace.rules if r.rule_type == ProvenanceRuleType.REPLENISHMENT_POLICY), None)
        if pol_rule is None:
            reasons.append(
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.UNAVAILABLE_RULE_DEFINITION,
                    message="Replenishment policy rule definition is missing from the provenance trace.",
                    details={"rule_type": "REPLENISHMENT_POLICY"},
                )
            )

        return reasons

    def _execute_scenario_evaluation(
        self,
        decision: Any,
        trace: DecisionProvenanceTrace,
        overrides: ScenarioOverrides,
    ) -> tuple[ScenarioResultSnapshot, ScenarioResultSnapshot, dict[str, Any], dict[str, Any]]:
        """Performs baseline evaluation and recalculated scenario evaluation on isolated input copies."""
        prod_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.PRODUCT)
        wh_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.WAREHOUSE)
        inv_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.INVENTORY)
        dem_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.DEMAND)
        sup_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.SUPPLIER)
        act_inps = [i for i in trace.inputs if i.input_type == ProvenanceInputType.CANDIDATE_ACTION]
        pol_rule = next(r for r in trace.rules if r.rule_type == ProvenanceRuleType.REPLENISHMENT_POLICY)

        # --- Reconstruct Baseline Domain Entities ---
        prod_val = prod_inp.value or {}
        base_product = Product(
            id=prod_val.get("product_id", decision.product_id),
            sku=prod_val.get("sku", f"SKU-{prod_val.get('product_id', decision.product_id)}"),
            name=prod_inp.name,
            category=prod_val.get("category", "General"),
            unit_cost=float(prod_val.get("unit_cost", 0.0)),
            selling_price=float(prod_val.get("selling_price", float(prod_val.get("unit_cost", 0.0)) * 1.5)),
            reorder_point=int(prod_val.get("reorder_point", 0)),
            active=True,
        )

        wh_val = wh_inp.value or {}
        wh_id = wh_val.get("warehouse_id", decision.warehouse_id)
        wh_capacity = int(wh_val.get("capacity", 10000))
        base_warehouse = Warehouse(
            id=wh_id,
            code=wh_val.get("code", f"WH-{wh_id}"),
            name=wh_inp.name,
            location=wh_val.get("location", "Standard Facility"),
            capacity=wh_capacity,
            active=True,
        )

        sup_val = sup_inp.value or {}
        sup_id = sup_val.get("supplier_id", "sup-001")
        base_supplier = Supplier(
            id=sup_id,
            code=sup_val.get("code", f"SUP-CODE-{sup_id}"),
            name=sup_inp.name,
            lead_time_days=int(sup_val.get("lead_time_days", 5)),
            reliability=float(sup_val.get("reliability", 1.0)),
            active=True,
        )

        inv_val = inv_inp.value or {}
        avail_qty = int(inv_val.get("available_quantity", 0))
        qty_on_hand = int(inv_val.get("quantity_on_hand", avail_qty))
        reorder_point = int(inv_val.get("reorder_point", base_product.reorder_point))
        base_inventory = Inventory(
            id=f"inv-{decision.id}",
            product_id=base_product.id,
            warehouse_id=wh_id,
            quantity_on_hand=qty_on_hand,
            quantity_reserved=int(inv_val.get("quantity_reserved", inv_val.get("reserved_quantity", 0))),
            reorder_point=reorder_point,
        )


        dem_val = dem_inp.value or {}
        base_avg_demand = float(dem_val.get("average_daily_demand", 0.0))

        policy_type = ReplenishmentPolicyType(pol_rule.rule_name)

        reconstructed_actions: list[CandidateAction] = []
        for act_inp in act_inps:
            act_val = act_inp.value or {}
            act_id = act_val.get("action_id", act_inp.source_id)
            act_type = ActionType(act_val.get("action_type"))
            raw_params = act_val.get("parameters", {})

            if act_type == ActionType.DO_NOTHING:
                params = DoNothingParameters()
            elif act_type == ActionType.PLACE_ORDER:
                params = PlaceOrderParameters(quantity=raw_params.get("quantity", raw_params.get("order_quantity", 1)))
            elif act_type == ActionType.SWITCH_SUPPLIER:
                params = SwitchSupplierParameters(target_supplier_id=raw_params.get("target_supplier_id", raw_params.get("supplier_id", "")))
            else:
                params = DoNothingParameters()

            reconstructed_actions.append(
                CandidateAction(
                    id=act_id,
                    decision_id=decision.id,
                    action_type=act_type,
                    parameters=params,
                )
            )

        # --- Evaluate Baseline State ---
        baseline_evals, baseline_snapshots, baseline_val_status = self._evaluate_actions_state(
            decision_id=decision.id,
            product=base_product,
            warehouse=base_warehouse,
            inventory=base_inventory,
            supplier=base_supplier,
            demand_rate=base_avg_demand,
            policy_type=policy_type,
            actions=reconstructed_actions,
        )

        baseline_rec = select_deterministic_recommendation(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            evaluations=baseline_evals,
            candidate_actions=reconstructed_actions,
            policy_type=policy_type,
        )

        baseline_result = ScenarioResultSnapshot(
            recommendation_id=baseline_rec.id,
            status=baseline_rec.status.value,
            recommended_action_id=baseline_rec.recommended_action_id,
            recommended_action_type=baseline_rec.recommended_action_type.value if baseline_rec.recommended_action_type else None,
            tie_broken=baseline_rec.tie_broken,
            tie_break_method=baseline_rec.tie_break_method.value,
            selection_rule=baseline_rec.selection_rule,
            validation_status=baseline_val_status,
            evaluations=baseline_snapshots,
            metadata={"source": "deterministic_baseline_evaluation"},
        )

        baseline_inputs_summary = {
            "product_id": base_product.id,
            "product_unit_cost": base_product.unit_cost,
            "warehouse_id": wh_id,
            "warehouse_capacity": wh_capacity,
            "available_quantity": avail_qty,
            "reorder_point": reorder_point,
            "average_daily_demand": base_avg_demand,
            "supplier_id": base_supplier.id,
            "supplier_lead_time_days": base_supplier.lead_time_days,
            "supplier_reliability": base_supplier.reliability,
            "policy_type": policy_type.value,
            "candidate_actions_count": len(reconstructed_actions),
        }

        # --- Apply Overrides to Isolated Deep Copies ---
        # 1. Cost Override
        scenario_unit_cost = base_product.unit_cost
        if overrides.cost is not None:
            if overrides.cost.unit_cost is not None:
                scenario_unit_cost = overrides.cost.unit_cost
            elif overrides.cost.cost_multiplier is not None:
                scenario_unit_cost = round(base_product.unit_cost * overrides.cost.cost_multiplier, 4)

        scenario_product = base_product.model_copy(update={"unit_cost": scenario_unit_cost}, deep=True)

        # 2. Demand Override
        scenario_avg_demand = base_avg_demand
        if overrides.demand is not None:
            if overrides.demand.demand_value is not None:
                scenario_avg_demand = overrides.demand.demand_value
            elif overrides.demand.demand_multiplier is not None:
                scenario_avg_demand = round(base_avg_demand * overrides.demand.demand_multiplier, 4)

        # 3. Supplier Lead Time Override
        scenario_lead_time_days = base_supplier.lead_time_days
        if overrides.lead_time is not None:
            scenario_lead_time_days = overrides.lead_time.lead_time_days

        scenario_supplier = base_supplier.model_copy(update={"lead_time_days": scenario_lead_time_days}, deep=True)

        # --- Evaluate Scenario State ---
        scenario_evals, scenario_snapshots, scenario_val_status = self._evaluate_actions_state(
            decision_id=decision.id,
            product=scenario_product,
            warehouse=base_warehouse,
            inventory=base_inventory,
            supplier=scenario_supplier,
            demand_rate=scenario_avg_demand,
            policy_type=policy_type,
            actions=reconstructed_actions,
        )

        scenario_rec = select_deterministic_recommendation(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            evaluations=scenario_evals,
            candidate_actions=reconstructed_actions,
            policy_type=policy_type,
        )

        scenario_result = ScenarioResultSnapshot(
            recommendation_id=scenario_rec.id,
            status=scenario_rec.status.value,
            recommended_action_id=scenario_rec.recommended_action_id,
            recommended_action_type=scenario_rec.recommended_action_type.value if scenario_rec.recommended_action_type else None,
            tie_broken=scenario_rec.tie_broken,
            tie_break_method=scenario_rec.tie_break_method.value,
            selection_rule=scenario_rec.selection_rule,
            validation_status=scenario_val_status,
            evaluations=scenario_snapshots,
            metadata={"source": "deterministic_scenario_recalculation"},
        )

        applied_inputs_summary = {
            "product_id": scenario_product.id,
            "product_unit_cost": scenario_product.unit_cost,
            "warehouse_id": wh_id,
            "warehouse_capacity": wh_capacity,
            "available_quantity": avail_qty,
            "reorder_point": reorder_point,
            "average_daily_demand": scenario_avg_demand,
            "supplier_id": scenario_supplier.id,
            "supplier_lead_time_days": scenario_supplier.lead_time_days,
            "supplier_reliability": scenario_supplier.reliability,
            "policy_type": policy_type.value,
            "candidate_actions_count": len(reconstructed_actions),
        }

        return baseline_result, scenario_result, baseline_inputs_summary, applied_inputs_summary

    def _evaluate_actions_state(
        self,
        decision_id: str,
        product: Product,
        warehouse: Warehouse,
        inventory: Inventory,
        supplier: Supplier,
        demand_rate: float,
        policy_type: ReplenishmentPolicyType,
        actions: list[CandidateAction],
    ) -> tuple[list[ActionEvaluationResult], dict[str, ScenarioActionEvaluationSnapshot], str]:
        """Evaluates and validates candidate actions against a specific configuration of domain inputs."""
        evaluations: list[ActionEvaluationResult] = []
        snapshots: dict[str, ScenarioActionEvaluationSnapshot] = {}

        # 1. Action evaluations and individual validations
        for act in actions:
            target_sup = None
            if act.action_type == ActionType.SWITCH_SUPPLIER:
                assert isinstance(act.parameters, SwitchSupplierParameters)
                target_sup_id = act.parameters.target_supplier_id
                target_sup = self._supplier_repo.get_by_id(target_sup_id)
                if target_sup is None:
                    target_sup = Supplier(
                        id=target_sup_id,
                        code=f"CODE-{target_sup_id}",
                        name=f"Alternative Supplier {target_sup_id}",
                        lead_time_days=supplier.lead_time_days,
                        reliability=supplier.reliability,
                        active=True,
                    )

            # Constraint Validation
            val_inputs = ValidationContextInputs(
                action=act,
                product=product,
                warehouse=warehouse,
                inventory=inventory,
                current_supplier=supplier,
                target_supplier=target_sup,
            )
            act_val_result = validate_candidate_action(val_inputs)

            # Operational Impact Evaluation
            eval_inputs = ActionEvaluationInputs(
                action=act,
                product=product,
                warehouse_id=warehouse.id,
                available_quantity=inventory.available_quantity,
                reorder_point=inventory.reorder_point,
                average_daily_demand=demand_rate,
                current_supplier=supplier,
                target_supplier=target_sup,
                replenishment_policy=policy_type,
                target_stock=None,
                enforce_reorder_trigger=True,
                warehouse_capacity=warehouse.capacity,
                historical_daily_demands=None,
            )

            eval_res = evaluate_candidate_action(eval_inputs)
            evaluations.append(eval_res)

            violated = [
                c.constraint_name for c in act_val_result.constraint_results if c.status.value == "FAIL"
            ]

            snapshots[act.id] = ScenarioActionEvaluationSnapshot(
                action_id=act.id,
                action_type=act.action_type.value,
                scoring_status=eval_res.scoring_status,
                overall_score=eval_res.overall_score,
                recommended_replenishment_quantity=eval_res.replenishment_impact.recommended_replenishment_quantity,
                shortfall_addressed=eval_res.replenishment_impact.shortfall_addressed,
                remaining_shortfall=eval_res.replenishment_impact.remaining_shortfall,
                exposure_index_delta=eval_res.stockout_exposure.exposure_index_delta,
                current_exposure_index=eval_res.stockout_exposure.current_exposure_index,
                projected_exposure_index=eval_res.stockout_exposure.projected_exposure_index,
                projected_risk_level=eval_res.stockout_exposure.projected_risk_level.value,
                direct_procurement_cost=eval_res.cost_impact.direct_procurement_cost,
                cost_status=(
                    ProvenanceStepStatus.SUCCESS.value
                    if eval_res.cost_impact.is_cost_calculable
                    else ProvenanceStepStatus.UNAVAILABLE.value
                ),
                is_valid=act_val_result.is_valid,
                violated_constraints=violated,
            )

        # 2. Decision-level validation report status
        all_valid = all(s.is_valid for s in snapshots.values())
        any_valid = any(s.is_valid for s in snapshots.values())
        if all_valid:
            overall_val_status = "ALL_SATISFIED"
        elif any_valid:
            overall_val_status = "SOME_VIOLATED"
        else:
            overall_val_status = "ALL_VIOLATED"

        return evaluations, snapshots, overall_val_status

    def _build_inputs_summary(self, trace: DecisionProvenanceTrace) -> dict[str, Any]:
        """Summarizes recorded inputs present in the trace for reporting."""
        return {
            "trace_id": trace.id,
            "total_inputs_recorded": len(trace.inputs),
            "input_types": sorted(list({i.input_type.value for i in trace.inputs})),
            "rules_recorded": [r.rule_name for r in trace.rules],
        }

    def _enrich_graph_with_scenario(
        self,
        decision_id: str,
        record: DecisionScenarioRecord,
    ) -> None:
        """Safely enriches DecisionGraph RESULT nodes with scenario metadata if graph exists."""
        if self._graph_repo is None:
            return
        graph = self._graph_repo.get_by_decision_id(decision_id)
        if graph is None:
            return

        for node in graph.nodes:
            if node.node_type.value == "RESULT":
                node.metadata["latest_scenario_id"] = record.id
                node.metadata["latest_scenario_status"] = record.status.value
                node.metadata["latest_scenario_at"] = record.created_at.isoformat()

        self._graph_repo.update_graph(graph)
