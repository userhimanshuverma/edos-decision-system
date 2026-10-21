from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.action_evaluation import (
    ActionEvaluationResult,
    EvaluationCostStatus,
    evaluate_candidate_action,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    SwitchSupplierParameters,
    validate_supplier_eligibility,
)
from app.domain.decision_graph import DecisionGraph
from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceCalculationRecord,
    ProvenanceCalculationType,
    ProvenanceDerivationChain,
    ProvenanceInputRecord,
    ProvenanceInputType,
    ProvenanceLineageEdge,
    ProvenanceResultRecord,
    ProvenanceResultType,
    ProvenanceRuleRecord,
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
from app.evaluation.service import ActionEvaluationService
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.provenance_repository import ProvenanceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository


class ProvenanceServiceError(Exception):
    """Base exception for provenance service errors."""


class DecisionNotFoundError(ProvenanceServiceError, KeyError):
    """Raised when the specified business decision does not exist."""


class DecisionVersionNotFoundError(ProvenanceServiceError, KeyError):
    """Raised when the specified decision version does not exist."""


class ProvenanceTraceNotFoundError(ProvenanceServiceError, KeyError):
    """Raised when the requested provenance trace is not found."""


class CrossDecisionIsolationError(ProvenanceServiceError, ValueError):
    """Raised when a reference crosses decision boundaries or violates isolation."""


class InvalidProvenancePayloadError(ProvenanceServiceError, ValueError):
    """Raised when a provenance payload or trace fails validation."""


class ProvenanceService:
    """Application coordination service for Decision Provenance.

    Orchestrates capturing, recording, querying, and graph synchronization of
    deterministic decision derivation traces across:
    Input -> Rule -> Calculation -> Result.

    Guarantees:
    - Never fabricates steps or claims a calculation ran when it did not.
    - Preserves decision and version isolation.
    - Explicitly distinguishes SUCCESS, FAILED, MISSING, UNAVAILABLE, and SKIPPED steps.
    - Multi-execution disambiguation via unique execution_id and chronological tracking.
    - In-memory architecture with defensive copies.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        provenance_repo: ProvenanceRepository,
        action_repo: CandidateActionRepository,
        version_repo: DecisionVersionRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        demand_repo: DemandRepository | None = None,
        supplier_repo: SupplierRepository | None = None,
        evaluation_service: ActionEvaluationService | None = None,
        recommendation_repo: RecommendationRepository | None = None,
        validation_repo: ValidationRepository | None = None,
        evidence_repo: EvidenceRepository | None = None,
        graph_repo: DecisionGraphRepository | None = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._provenance_repo = provenance_repo
        self._action_repo = action_repo
        self._version_repo = version_repo
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
        self._recommendation_repo = (
            recommendation_repo if recommendation_repo is not None else RecommendationRepository()
        )
        self._validation_repo = (
            validation_repo if validation_repo is not None else ValidationRepository()
        )
        self._evidence_repo = (
            evidence_repo if evidence_repo is not None else EvidenceRepository()
        )
        self._graph_repo = graph_repo

    @property
    def decision_repository(self) -> DecisionRepository:
        return self._decision_repo

    @property
    def provenance_repository(self) -> ProvenanceRepository:
        return self._provenance_repo

    @property
    def action_repository(self) -> CandidateActionRepository:
        return self._action_repo

    @property
    def version_repository(self) -> DecisionVersionRepository | None:
        return self._version_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository | None:
        return self._graph_repo

    def capture_decision_provenance(
        self,
        decision_id: str,
        *,
        version_id: str | None = None,
        policy_type: ReplenishmentPolicyType | str = ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        target_stock: int | None = None,
        enforce_reorder_trigger: bool = True,
        record_to_graph: bool = False,
        trigger: str = "RECOMMENDATION",
        metadata: dict[str, Any] | None = None,
    ) -> DecisionProvenanceTrace:
        """Executes real domain evaluation and captures an end-to-end provenance trace.

        Strictly follows: Input -> Rule -> Calculation -> Result.
        Does NOT fabricate missing steps.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            DecisionVersionNotFoundError: If version_id is provided but not found.
            CrossDecisionIsolationError: If version_id does not belong to the decision.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        resolved_version_id = None
        if version_id is not None:
            norm_ver_id = version_id.strip()
            if self._version_repo is None:
                raise DecisionVersionNotFoundError(
                    f"Decision version repository not configured, cannot verify version '{norm_ver_id}'"
                )
            version_record = self._version_repo.get_by_id(norm_ver_id)
            if version_record is None:
                raise DecisionVersionNotFoundError(
                    f"Decision version '{norm_ver_id}' not found"
                )
            if version_record.decision_id != decision.id:
                raise CrossDecisionIsolationError(
                    f"Version '{norm_ver_id}' belongs to decision '{version_record.decision_id}', "
                    f"not '{decision.id}'"
                )
            resolved_version_id = version_record.id

        resolved_policy = (
            policy_type
            if isinstance(policy_type, ReplenishmentPolicyType)
            else ReplenishmentPolicyType(policy_type)
        )

        trace_id = self._provenance_repo.generate_id()
        exec_id = self._provenance_repo.generate_execution_id()

        inputs: list[ProvenanceInputRecord] = []
        rules: list[ProvenanceRuleRecord] = []
        calculations: list[ProvenanceCalculationRecord] = []
        results: list[ProvenanceResultRecord] = []
        edges: list[ProvenanceLineageEdge] = []

        ds = getattr(self._inventory_repo, "dataset", None)

        # -------------------------------------------------------------------
        # 1. Inputs Capture
        # -------------------------------------------------------------------
        # 1a. Product
        product = ds.get_product(decision.product_id) if ds else None
        prod_inp_id = self._provenance_repo.generate_input_id()
        if product is not None:
            inputs.append(
                ProvenanceInputRecord(
                    id=prod_inp_id,
                    input_type=ProvenanceInputType.PRODUCT,
                    source_id=product.id,
                    name=f"Catalog Product: {product.name}",
                    value={
                        "product_id": product.id,
                        "category": product.category,
                        "unit_cost": product.unit_cost,
                        "reorder_point": product.reorder_point,
                    },
                    unit=None,
                    status=ProvenanceStepStatus.SUCCESS,
                    metadata={"category": product.category},
                )
            )
        else:
            inputs.append(
                ProvenanceInputRecord(
                    id=prod_inp_id,
                    input_type=ProvenanceInputType.PRODUCT,
                    source_id=decision.product_id,
                    name=f"Product: {decision.product_id}",
                    value=None,
                    status=ProvenanceStepStatus.MISSING,
                    metadata={"error": "Product not found in catalog dataset"},
                )
            )

        # 1b. Warehouse
        warehouse = ds.get_warehouse(decision.warehouse_id) if ds else None
        wh_inp_id = self._provenance_repo.generate_input_id()
        if warehouse is not None:
            inputs.append(
                ProvenanceInputRecord(
                    id=wh_inp_id,
                    input_type=ProvenanceInputType.WAREHOUSE,
                    source_id=warehouse.id,
                    name=f"Warehouse: {warehouse.name}",
                    value={
                        "warehouse_id": warehouse.id,
                        "capacity": warehouse.capacity,
                    },
                    unit="units_capacity",
                    status=ProvenanceStepStatus.SUCCESS,
                    metadata={"capacity": warehouse.capacity},
                )
            )
        else:
            inputs.append(
                ProvenanceInputRecord(
                    id=wh_inp_id,
                    input_type=ProvenanceInputType.WAREHOUSE,
                    source_id=decision.warehouse_id,
                    name=f"Warehouse: {decision.warehouse_id}",
                    value=None,
                    status=ProvenanceStepStatus.MISSING,
                    metadata={"error": "Warehouse not found in dataset"},
                )
            )

        # 1c. Inventory Position
        inv = ds.get_inventory(decision.product_id, decision.warehouse_id) if ds else None
        inv_inp_id = self._provenance_repo.generate_input_id()
        if inv is not None:
            available_qty = inv.available_quantity
            reorder_point = inv.reorder_point
            inputs.append(
                ProvenanceInputRecord(
                    id=inv_inp_id,
                    input_type=ProvenanceInputType.INVENTORY,
                    source_id=f"inv:{decision.product_id}@{decision.warehouse_id}",
                    name="Current Available Inventory Position",
                    value={
                        "available_quantity": available_qty,
                        "reorder_point": reorder_point,
                    },
                    unit="units",
                    status=ProvenanceStepStatus.SUCCESS,
                )
            )
        else:
            available_qty = 0
            reorder_point = product.reorder_point if product else 0
            inputs.append(
                ProvenanceInputRecord(
                    id=inv_inp_id,
                    input_type=ProvenanceInputType.INVENTORY,
                    source_id=f"inv:{decision.product_id}@{decision.warehouse_id}",
                    name="Inventory Position (Default/Zero)",
                    value={
                        "available_quantity": 0,
                        "reorder_point": reorder_point,
                    },
                    unit="units",
                    status=ProvenanceStepStatus.UNAVAILABLE,
                    metadata={"note": "Inventory position record missing; defaulted available_quantity to 0"},
                )
            )

        # 1d. Demand Trend
        trend_summary = self._demand_repo.get_product_demand_trend(
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
        )
        avg_demand = float(trend_summary.get("average_daily_demand", 0.0))
        demand_inp_id = self._provenance_repo.generate_input_id()
        inputs.append(
            ProvenanceInputRecord(
                id=demand_inp_id,
                input_type=ProvenanceInputType.DEMAND,
                source_id=f"demand:{decision.product_id}@{decision.warehouse_id}",
                name="Historical Daily Demand Trend",
                value={"average_daily_demand": avg_demand},
                unit="units/day",
                status=ProvenanceStepStatus.SUCCESS if avg_demand > 0 else ProvenanceStepStatus.UNAVAILABLE,
            )
        )

        # 1e. Primary Supplier
        primary_sup = None
        if product is not None:
            primary_sup = self._supplier_repo.get_supplier_for_product(
                product_id=product.id,
                category=product.category,
            )
        sup_inp_id = self._provenance_repo.generate_input_id()
        if primary_sup is not None:
            inputs.append(
                ProvenanceInputRecord(
                    id=sup_inp_id,
                    input_type=ProvenanceInputType.SUPPLIER,
                    source_id=primary_sup.id,
                    name=f"Primary Supplier: {primary_sup.name}",
                    value={
                        "supplier_id": primary_sup.id,
                        "lead_time_days": primary_sup.lead_time_days,
                        "reliability": getattr(primary_sup, "reliability", getattr(primary_sup, "reliability_score", 1.0)),
                    },
                    unit=None,
                    status=ProvenanceStepStatus.SUCCESS,
                )
            )
        else:
            inputs.append(
                ProvenanceInputRecord(
                    id=sup_inp_id,
                    input_type=ProvenanceInputType.SUPPLIER,
                    source_id="UNKNOWN_SUPPLIER",
                    name="Primary Supplier",
                    value=None,
                    status=ProvenanceStepStatus.MISSING,
                    metadata={"error": "No eligible primary supplier found for product"},
                )
            )

        # 1f. Decision Version (if specified)
        if resolved_version_id is not None:
            ver_inp_id = self._provenance_repo.generate_input_id()
            inputs.append(
                ProvenanceInputRecord(
                    id=ver_inp_id,
                    input_type=ProvenanceInputType.DECISION_VERSION,
                    source_id=resolved_version_id,
                    name=f"Decision Version {resolved_version_id}",
                    value={"version_id": resolved_version_id},
                    status=ProvenanceStepStatus.SUCCESS,
                )
            )

        # 1g. Day 22 Assumptions & Facts cross-referencing
        if self._evidence_repo is not None:
            decision_assumptions = self._evidence_repo.list_assumptions_by_decision(decision.id)
            for asm in decision_assumptions:
                asm_inp_id = self._provenance_repo.generate_input_id()
                inputs.append(
                    ProvenanceInputRecord(
                        id=asm_inp_id,
                        input_type=ProvenanceInputType.ASSUMPTION,
                        source_id=asm.id,
                        name=f"Assumption: {asm.statement}",
                        value=asm.assumed_value,
                        status=ProvenanceStepStatus.SUCCESS,
                        evidence_id=asm.id,
                        metadata={"rationale": asm.rationale, "source": asm.source},
                    )
                )

        # -------------------------------------------------------------------
        # 2. Candidate Actions Inputs
        # -------------------------------------------------------------------
        candidate_actions = self._action_repo.list_by_decision_id(decision.id)
        action_input_ids: dict[str, str] = {}
        for act in candidate_actions:
            act_inp_id = self._provenance_repo.generate_input_id()
            action_input_ids[act.id] = act_inp_id
            inputs.append(
                ProvenanceInputRecord(
                    id=act_inp_id,
                    input_type=ProvenanceInputType.CANDIDATE_ACTION,
                    source_id=act.id,
                    name=f"Candidate Action: {act.action_type.value} ({act.id})",
                    value={
                        "action_id": act.id,
                        "action_type": act.action_type.value,
                        "parameters": act.parameters.model_dump(mode="json")
                        if hasattr(act.parameters, "model_dump")
                        else act.parameters,
                    },
                    status=ProvenanceStepStatus.SUCCESS,
                )
            )

        # -------------------------------------------------------------------
        # 3. Rules Evaluation
        # -------------------------------------------------------------------
        # 3a. Replenishment Policy Rule
        policy_rule_id = self._provenance_repo.generate_rule_id()
        is_triggered = available_qty <= reorder_point
        rules.append(
            ProvenanceRuleRecord(
                id=policy_rule_id,
                rule_type=ProvenanceRuleType.REPLENISHMENT_POLICY,
                rule_name=resolved_policy.value,
                action_id=None,
                inputs_considered=[inv_inp_id, prod_inp_id],
                status=ProvenanceStepStatus.SUCCESS,
                condition_met=is_triggered,
                outcome="TRIGGERED" if is_triggered else "NOT_TRIGGERED",
                notes=[
                    f"Policy {resolved_policy.value} evaluated against available_qty={available_qty} and reorder_point={reorder_point}.",
                    f"Reorder trigger condition (available_qty <= reorder_point) is {is_triggered}.",
                ],
            )
        )
        edges.append(
            ProvenanceLineageEdge(
                source_id=inv_inp_id,
                target_id=policy_rule_id,
                relationship="FEEDS_INTO_RULE",
            )
        )

        # 3b. Constraint Validations (if validation report exists or validation repo holds records)
        validation_report = self._validation_repo.get_latest_for_decision(decision.id)
        validation_report_id = validation_report.id if validation_report else None
        action_constraint_rule_ids: dict[str, list[str]] = {}
        if validation_report is not None:
            for act_res in validation_report.action_results:
                action_constraint_rule_ids.setdefault(act_res.action_id, [])
                c_evs = getattr(act_res, "constraint_results", getattr(act_res, "constraint_evaluations", []))
                for c_ev in c_evs:
                    c_rule_id = self._provenance_repo.generate_rule_id()
                    action_constraint_rule_ids[act_res.action_id].append(c_rule_id)
                    st_val = getattr(c_ev.status, "value", str(c_ev.status))
                    cond_met = st_val in ("PASS", "PASSED")
                    c_type_val = getattr(c_ev.constraint_type, "value", str(c_ev.constraint_type))
                    inputs_for_constraint = (
                        [wh_inp_id, prod_inp_id]
                        if c_type_val == "WAREHOUSE_CAPACITY"
                        else [prod_inp_id]
                    )
                    step_st = (
                        ProvenanceStepStatus.SUCCESS
                        if st_val != "UNABLE_TO_EVALUATE"
                        else ProvenanceStepStatus.UNAVAILABLE
                    )
                    reason_msg = getattr(c_ev, "reason", getattr(c_ev, "message", "")) or ""
                    rules.append(
                        ProvenanceRuleRecord(
                            id=c_rule_id,
                            rule_type=ProvenanceRuleType.CONSTRAINT_CHECK,
                            rule_name=c_type_val,
                            action_id=act_res.action_id,
                            inputs_considered=inputs_for_constraint,
                            status=step_st,
                            condition_met=cond_met,
                            outcome=st_val,
                            validation_report_id=validation_report_id,
                            notes=[reason_msg] if reason_msg else [],
                        )
                    )
                    for inp_id in inputs_for_constraint:
                        edges.append(
                            ProvenanceLineageEdge(
                                source_id=inp_id,
                                target_id=c_rule_id,
                                relationship="FEEDS_INTO_RULE",
                            )
                        )

        # -------------------------------------------------------------------
        # 4. Action Calculations & Action Results
        # -------------------------------------------------------------------
        evaluations: list[ActionEvaluationResult] = []
        action_calc_ids: dict[str, list[str]] = {}
        action_result_ids: dict[str, str] = {}

        for act in candidate_actions:
            action_calcs: list[str] = []
            act_inp_id = action_input_ids[act.id]

            # Try real calculation via ActionEvaluationService
            try:
                eval_res = self._evaluation_service.evaluate_action(
                    decision_id=decision.id,
                    action_id=act.id,
                    policy_type=resolved_policy,
                    target_stock=target_stock,
                    enforce_reorder_trigger=enforce_reorder_trigger,
                    record_to_graph=record_to_graph,
                )
                evaluations.append(eval_res)

                # Replenishment calculation step
                repl_calc_id = self._provenance_repo.generate_calculation_id()
                action_calcs.append(repl_calc_id)
                calculations.append(
                    ProvenanceCalculationRecord(
                        id=repl_calc_id,
                        calculation_type=ProvenanceCalculationType.REPLENISHMENT_QUANTITY,
                        calculation_name=f"Replenishment Shortfall ({act.id})",
                        action_id=act.id,
                        formula="shortfall = max(0, target_stock - available_quantity)",
                        inputs_used=[inv_inp_id, act_inp_id],
                        rules_applied=[policy_rule_id],
                        status=ProvenanceStepStatus.SUCCESS,
                        output_value={
                            "recommended_quantity": eval_res.replenishment_impact.recommended_replenishment_quantity,
                            "shortfall_addressed": eval_res.replenishment_impact.shortfall_addressed,
                            "remaining_shortfall": eval_res.replenishment_impact.remaining_shortfall,
                        },
                        unit="units",
                    )
                )
                edges.append(
                    ProvenanceLineageEdge(
                        source_id=act_inp_id,
                        target_id=repl_calc_id,
                        relationship="FEEDS_CALCULATION",
                    )
                )
                edges.append(
                    ProvenanceLineageEdge(
                        source_id=policy_rule_id,
                        target_id=repl_calc_id,
                        relationship="GOVERNS_CALCULATION",
                    )
                )

                # Stockout risk calculation step
                risk_calc_id = self._provenance_repo.generate_calculation_id()
                action_calcs.append(risk_calc_id)
                calculations.append(
                    ProvenanceCalculationRecord(
                        id=risk_calc_id,
                        calculation_type=ProvenanceCalculationType.STOCKOUT_EXPOSURE,
                        calculation_name=f"Lead-Time Stockout Exposure ({act.id})",
                        action_id=act.id,
                        formula="exposure_index = lead_time_demand / available_stock",
                        inputs_used=[inv_inp_id, demand_inp_id, sup_inp_id],
                        status=ProvenanceStepStatus.SUCCESS,
                        output_value={
                            "exposure_index_delta": eval_res.stockout_exposure.exposure_index_delta,
                            "current_exposure_index": eval_res.stockout_exposure.current_exposure_index,
                            "projected_exposure_index": eval_res.stockout_exposure.projected_exposure_index,
                        },
                        unit="ratio [0.0, 1.0]",
                    )
                )

                # Cost impact calculation step
                cost_calc_id = self._provenance_repo.generate_calculation_id()
                action_calcs.append(cost_calc_id)
                cost_status = eval_res.cost_impact.cost_status
                if cost_status == EvaluationCostStatus.CALCULATED or cost_status == EvaluationCostStatus.ZERO_COST:
                    calc_st = ProvenanceStepStatus.SUCCESS
                    calc_err = None
                else:
                    calc_st = ProvenanceStepStatus.UNAVAILABLE
                    calc_err = eval_res.cost_impact.unavailability_reason or "Monetary cost incalculable"

                calculations.append(
                    ProvenanceCalculationRecord(
                        id=cost_calc_id,
                        calculation_type=ProvenanceCalculationType.COST_IMPACT,
                        calculation_name=f"Direct Procurement Cost ({act.id})",
                        action_id=act.id,
                        formula="direct_procurement_cost = order_quantity * unit_cost",
                        inputs_used=[act_inp_id, prod_inp_id],
                        status=calc_st,
                        output_value=eval_res.cost_impact.direct_procurement_cost,
                        unit=eval_res.cost_impact.currency,
                        error_message=calc_err,
                    )
                )

                # Action scoring calculation step
                score_calc_id = self._provenance_repo.generate_calculation_id()
                action_calcs.append(score_calc_id)
                calculations.append(
                    ProvenanceCalculationRecord(
                        id=score_calc_id,
                        calculation_type=ProvenanceCalculationType.ACTION_SCORING,
                        calculation_name=f"Multi-Criteria Composite Score ({act.id})",
                        action_id=act.id,
                        formula="lexicographic_composite_score",
                        inputs_used=[act_inp_id],
                        status=ProvenanceStepStatus.SUCCESS
                        if eval_res.scoring_status == "COMPUTED"
                        else ProvenanceStepStatus.UNAVAILABLE,
                        output_value=eval_res.overall_score,
                        unit="score [0.0, 1.0]",
                    )
                )

                # Action Result step
                # Action Result step
                act_res_id = self._provenance_repo.generate_result_id()
                action_result_ids[act.id] = act_res_id
                action_calc_ids[act.id] = action_calcs
                act_rules = [policy_rule_id] + action_constraint_rule_ids.get(act.id, [])
                results.append(
                    ProvenanceResultRecord(
                        id=act_res_id,
                        result_type=ProvenanceResultType.ACTION_EVALUATION,
                        result_id=act.id,
                        action_id=act.id,
                        status=ProvenanceStepStatus.SUCCESS,
                        outcome_status=eval_res.scoring_status,
                        summary=f"Evaluated {act.action_type.value} with overall score {eval_res.overall_score}",
                        calculations_used=action_calcs,
                        rules_applied=act_rules,
                        value={"overall_score": eval_res.overall_score},
                    )
                )

                for cid in action_calcs:
                    edges.append(
                        ProvenanceLineageEdge(
                            source_id=cid,
                            target_id=act_res_id,
                            relationship="PRODUCES_EVALUATION",
                        )
                    )
                for c_rule_id in action_constraint_rule_ids.get(act.id, []):
                    edges.append(
                        ProvenanceLineageEdge(
                            source_id=c_rule_id,
                            target_id=act_res_id,
                            relationship="GOVERNS_ACTION_VALIDATION",
                        )
                    )

            except Exception as exc:
                # Actual calculation failure - recorded transparently
                fail_calc_id = self._provenance_repo.generate_calculation_id()
                action_calcs.append(fail_calc_id)
                calculations.append(
                    ProvenanceCalculationRecord(
                        id=fail_calc_id,
                        calculation_type=ProvenanceCalculationType.ACTION_SCORING,
                        calculation_name=f"Evaluation Execution ({act.id})",
                        action_id=act.id,
                        formula=None,
                        inputs_used=[act_inp_id],
                        status=ProvenanceStepStatus.FAILED,
                        output_value=None,
                        error_message=str(exc),
                    )
                )
                act_res_id = self._provenance_repo.generate_result_id()
                action_result_ids[act.id] = act_res_id
                action_calc_ids[act.id] = action_calcs
                act_rules = [policy_rule_id] + action_constraint_rule_ids.get(act.id, [])
                results.append(
                    ProvenanceResultRecord(
                        id=act_res_id,
                        result_type=ProvenanceResultType.ACTION_EVALUATION,
                        result_id=act.id,
                        action_id=act.id,
                        status=ProvenanceStepStatus.FAILED,
                        outcome_status="FAILED",
                        summary=f"Evaluation failed: {exc}",
                        calculations_used=action_calcs,
                        rules_applied=act_rules,
                        value=None,
                    )
                )

        # -------------------------------------------------------------------
        # 5. Recommendation Selection & Final Result
        # -------------------------------------------------------------------
        rec_id = self._recommendation_repo.generate_id()
        recommendation = select_deterministic_recommendation(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            evaluations=evaluations,
            candidate_actions=candidate_actions,
            recommendation_id=rec_id,
            policy_type=resolved_policy,
        )

        # Persist recommendation in repo
        stored_rec = self._recommendation_repo.record(recommendation)

        # Selection rule step
        sel_rule_id = self._provenance_repo.generate_rule_id()
        rules.append(
            ProvenanceRuleRecord(
                id=sel_rule_id,
                rule_type=ProvenanceRuleType.SELECTION_STRATEGY,
                rule_name=stored_rec.selection_rule,
                action_id=stored_rec.recommended_action_id,
                inputs_considered=list(action_input_ids.values()),
                status=ProvenanceStepStatus.SUCCESS,
                condition_met=stored_rec.status == RecommendationStatus.RECOMMENDED,
                outcome=stored_rec.status.value,
                notes=[stored_rec.selection_rationale],
            )
        )

        rec_rules = [sel_rule_id]
        if stored_rec.tie_broken:
            tie_rule_id = self._provenance_repo.generate_rule_id()
            rec_rules.append(tie_rule_id)
            rules.append(
                ProvenanceRuleRecord(
                    id=tie_rule_id,
                    rule_type=ProvenanceRuleType.TIE_BREAKER,
                    rule_name=stored_rec.tie_break_method.value,
                    action_id=stored_rec.recommended_action_id,
                    inputs_considered=list(action_input_ids.values()),
                    status=ProvenanceStepStatus.SUCCESS,
                    condition_met=True,
                    outcome="TIE_RESOLVED",
                    notes=[stored_rec.tie_breaking_rationale or "Tie broken deterministically"],
                )
            )

        # Recommendation result step
        all_eval_calcs = [cid for calcs in action_calc_ids.values() for cid in calcs]
        rec_res_id = self._provenance_repo.generate_result_id()
        results.append(
            ProvenanceResultRecord(
                id=rec_res_id,
                result_type=ProvenanceResultType.RECOMMENDATION,
                result_id=stored_rec.id,
                action_id=stored_rec.recommended_action_id,
                status=ProvenanceStepStatus.SUCCESS,
                outcome_status=stored_rec.status.value,
                summary=stored_rec.selection_rationale,
                calculations_used=all_eval_calcs,
                rules_applied=rec_rules,
                value={
                    "recommendation_id": stored_rec.id,
                    "status": stored_rec.status.value,
                    "recommended_action_id": stored_rec.recommended_action_id,
                    "recommended_action_type": stored_rec.recommended_action_type.value
                    if stored_rec.recommended_action_type
                    else None,
                    "tie_broken": stored_rec.tie_broken,
                },
            )
        )

        # Edges to recommendation
        for r_id in rec_rules:
            edges.append(
                ProvenanceLineageEdge(
                    source_id=r_id,
                    target_id=rec_res_id,
                    relationship="PRODUCES_RECOMMENDATION",
                )
            )
        for act_id, act_res_id in action_result_ids.items():
            edges.append(
                ProvenanceLineageEdge(
                    source_id=act_res_id,
                    target_id=rec_res_id,
                    relationship="CONSIDERED_IN_RECOMMENDATION",
                )
            )
        for cid in all_eval_calcs:
            edges.append(
                ProvenanceLineageEdge(
                    source_id=cid,
                    target_id=rec_res_id,
                    relationship="FEEDS_RECOMMENDATION",
                )
            )

        # -------------------------------------------------------------------
        # 6. Synchronize with Decision Graph if requested
        # -------------------------------------------------------------------
        graph_id = None
        if record_to_graph and self._graph_repo is not None:
            # Attach recommendation node to graph
            rec_node, rec_edge = self._graph_repo.attach_recommendation_node(decision.id, stored_rec)
            graph = self._graph_repo.get_by_decision_id(decision.id)
            if graph is not None:
                graph_id = graph.id
                # Enrich RESULT node metadata with provenance trace ID
                if rec_node is not None:
                    for n in graph.nodes:
                        if n.id == rec_node.id:
                            n.metadata["provenance_trace_id"] = trace_id
                            n.metadata["provenance_step_id"] = rec_res_id
                    self._graph_repo.update_graph(graph)

        # -------------------------------------------------------------------
        # 7. Construct & Store DecisionProvenanceTrace
        # -------------------------------------------------------------------
        has_failed_steps = any(
            s.status == ProvenanceStepStatus.FAILED
            for s in (*inputs, *rules, *calculations, *results)
        )
        overall_status = ProvenanceStepStatus.FAILED if has_failed_steps else ProvenanceStepStatus.SUCCESS

        trace = DecisionProvenanceTrace(
            id=trace_id,
            decision_id=decision.id,
            version_id=resolved_version_id,
            execution_id=exec_id,
            created_at=datetime.now(timezone.utc),
            trigger=trigger,
            status=overall_status,
            inputs=inputs,
            rules=rules,
            calculations=calculations,
            results=results,
            lineage_edges=edges,
            graph_id=graph_id,
            metadata=metadata or {},
        )

        stored_trace = self._provenance_repo.record(trace)
        return stored_trace

    def get_provenance_trace(
        self,
        decision_id: str,
        trace_id: str,
    ) -> DecisionProvenanceTrace:
        """Retrieves an individual provenance trace by ID, strictly enforcing decision isolation.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            ProvenanceTraceNotFoundError: If the trace does not exist.
            CrossDecisionIsolationError: If the trace belongs to a different decision.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        norm_trace_id = trace_id.strip()
        trace = self._provenance_repo.get_by_id(norm_trace_id)
        if trace is None:
            raise ProvenanceTraceNotFoundError(
                f"Provenance trace '{norm_trace_id}' not found"
            )

        if trace.decision_id != decision.id:
            raise CrossDecisionIsolationError(
                f"Provenance trace '{norm_trace_id}' belongs to decision '{trace.decision_id}', "
                f"not requested decision '{decision.id}'"
            )

        return trace

    def get_latest_provenance(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> DecisionProvenanceTrace | None:
        """Retrieves the most recent provenance trace for a decision.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self._provenance_repo.get_latest_for_decision(
            decision_id=decision.id,
            version_id=version_id,
        )

    def list_provenance_traces(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> list[DecisionProvenanceTrace]:
        """Lists all provenance traces for a decision, sorted chronologically descending.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self._provenance_repo.list_for_decision(
            decision_id=decision.id,
            version_id=version_id,
        )

    def get_derivation_path(
        self,
        decision_id: str,
        trace_id: str | None = None,
        result_id: str | None = None,
    ) -> ProvenanceDerivationChain:
        """Extracts the Input -> Rule -> Calculation -> Result derivation path for a result step.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            ProvenanceTraceNotFoundError: If trace_id is specified but not found.
            ValueError: If result_id is not found in trace.
        """
        if trace_id is not None:
            trace = self.get_provenance_trace(decision_id=decision_id, trace_id=trace_id)
        else:
            trace = self.get_latest_provenance(decision_id=decision_id)
            if trace is None:
                raise ProvenanceTraceNotFoundError(
                    f"No provenance traces exist for decision '{decision_id}'"
                )

        return trace.get_derivation_path(result_id=result_id)

    def record_trace(self, trace: DecisionProvenanceTrace) -> DecisionProvenanceTrace:
        """Directly stores a pre-constructed trace with strict isolation and reference validation.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            DecisionVersionNotFoundError: If version_id does not exist.
            CrossDecisionIsolationError: If any step references an entity outside this decision.
        """
        norm_decision_id = trace.decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        if trace.version_id is not None and self._version_repo is not None:
            ver = self._version_repo.get_by_id(trace.version_id)
            if ver is None:
                raise DecisionVersionNotFoundError(f"Decision version '{trace.version_id}' not found")
            if ver.decision_id != decision.id:
                raise CrossDecisionIsolationError(
                    f"Version '{trace.version_id}' does not belong to decision '{decision.id}'"
                )

        # Cross-decision validation of candidate actions referenced in steps
        for step in trace.rules:
            if step.action_id:
                act = self._action_repo.get_by_id(step.action_id)
                if act is not None and act.decision_id != decision.id:
                    raise CrossDecisionIsolationError(
                        f"Rule step '{step.id}' references action '{step.action_id}' belonging to decision '{act.decision_id}'"
                    )

        for step in trace.calculations:
            if step.action_id:
                act = self._action_repo.get_by_id(step.action_id)
                if act is not None and act.decision_id != decision.id:
                    raise CrossDecisionIsolationError(
                        f"Calculation step '{step.id}' references action '{step.action_id}' belonging to decision '{act.decision_id}'"
                    )

        for step in trace.results:
            if step.action_id:
                act = self._action_repo.get_by_id(step.action_id)
                if act is not None and act.decision_id != decision.id:
                    raise CrossDecisionIsolationError(
                        f"Result step '{step.id}' references action '{step.action_id}' belonging to decision '{act.decision_id}'"
                    )

        return self._provenance_repo.record(trace)
