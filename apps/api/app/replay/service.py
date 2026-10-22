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
from app.domain.product import Product
from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceCalculationType,
    ProvenanceInputType,
    ProvenanceResultType,
    ProvenanceRuleType,
    ProvenanceStepStatus,
)
from app.domain.recommendation import (
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
    select_deterministic_recommendation,
)
from app.domain.replay import (
    DecisionReplayRecord,
    IncompleteReason,
    IncompleteReasonCode,
    ReplayActionEvaluationSnapshot,
    ReplayComparisonResult,
    ReplayResultSnapshot,
    ReplayStatus,
    compare_replay_results,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.domain.supplier import Supplier
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
from app.repositories.replay_repository import ReplayRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository


class DecisionReplayError(Exception):
    """Base exception for Decision Replay service errors."""


class DecisionNotFoundError(DecisionReplayError, KeyError):
    """Raised when the specified business decision does not exist."""


class DecisionVersionNotFoundError(DecisionReplayError, KeyError):
    """Raised when the specified decision version does not exist."""


class ProvenanceTraceNotFoundError(DecisionReplayError, KeyError):
    """Raised when the requested original provenance trace is not found."""


class ReplayRecordNotFoundError(DecisionReplayError, KeyError):
    """Raised when the requested replay record is not found."""


class CrossDecisionIsolationError(DecisionReplayError, ValueError):
    """Raised when a replay reference crosses decision boundaries or violates isolation."""


class InvalidReplayRequestError(DecisionReplayError, ValueError):
    """Raised when replay arguments or payloads are semantically invalid."""


class DecisionReplayService:
    """Core domain coordination service for Day 24 Decision Replay Engine.

    Answers the three fundamental operational questions:
    1. Can the original decision be reconstructed reliably?
    2. Does replay produce the same result?
    3. If the result differs or replay is incomplete, what can we establish about the difference?

    Core Principle:
    'The system calculates. AI explains. Humans approve.'

    Guarantees:
    - Pure deterministic re-evaluation: uses original recorded inputs, not mutated live operational data.
    - Zero fabrication: missing historical data yields INCOMPLETE with structured actionable reasons.
    - Preserves historical immutability: never mutates original decisions, versions, traces, or audit history.
    - Full decision and version isolation: cross-decision references are strictly rejected.
    - Multi-run auditability: repeated replays create distinct timestamped records (RPL-XXXX, REX-XXXX).
    - Granular field-level comparisons detailing exactly what changed if outcomes differ.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        replay_repo: ReplayRepository,
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
        self._replay_repo = replay_repo
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
    def replay_repository(self) -> ReplayRepository:
        return self._replay_repo

    @property
    def provenance_repository(self) -> ProvenanceRepository:
        return self._provenance_repo

    @property
    def version_repository(self) -> DecisionVersionRepository | None:
        return self._version_repo

    @property
    def graph_repository(self) -> DecisionGraphRepository | None:
        return self._graph_repo

    def replay_decision(
        self,
        decision_id: str,
        *,
        trace_id: str | None = None,
        version_id: str | None = None,
        execution_id: str | None = None,
        record_to_graph: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionReplayRecord:
        """Reconstructs, re-evaluates, and compares a previously recorded decision execution.

        Evaluates against the original recorded inputs and applicable rules to determine
        whether deterministic results reproduce identically (MATCHED), differ (DIFFERENT),
        or cannot be defensibly recomputed due to missing historical data (INCOMPLETE).

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            DecisionVersionNotFoundError: If version_id is provided but not found.
            ProvenanceTraceNotFoundError: If trace_id is provided but not found.
            CrossDecisionIsolationError: If references violate decision isolation boundaries.
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

        replay_id = self._replay_repo.generate_id()
        replay_exec_id = self._replay_repo.generate_execution_id()
        now_utc = datetime.now(timezone.utc)

        # 4. Handle Missing Provenance Trace (Incomplete Replay)
        if trace is None:
            incomplete_reasons = [
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_PROVENANCE_TRACE,
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
            record = DecisionReplayRecord(
                id=replay_id,
                decision_id=decision.id,
                version_id=resolved_version_id,
                original_trace_id=None,
                original_execution_id=None,
                replay_execution_id=replay_exec_id,
                created_at=now_utc,
                status=ReplayStatus.INCOMPLETE,
                original_result=None,
                replayed_result=None,
                comparison=None,
                incomplete_reasons=incomplete_reasons,
                error_message=None,
                reconstructed_inputs_summary={},
                metadata=metadata or {},
            )
            return self._replay_repo.record(record)

        # 5. Extract Original Recorded Result Snapshot from Provenance Trace
        original_result = self._extract_original_result(trace)
        if original_result is None or (not original_result.evaluations and not original_result.status):
            incomplete_reasons = [
                IncompleteReason(
                    code=IncompleteReasonCode.NO_RECORDED_RESULTS,
                    message=(
                        f"Original provenance trace '{trace.id}' contains no recorded results or evaluations "
                        "to compare against."
                    ),
                    details={"trace_id": trace.id},
                )
            ]
            record = DecisionReplayRecord(
                id=replay_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                original_trace_id=trace.id,
                original_execution_id=trace.execution_id,
                replay_execution_id=replay_exec_id,
                created_at=now_utc,
                status=ReplayStatus.INCOMPLETE,
                original_result=original_result,
                replayed_result=None,
                comparison=None,
                incomplete_reasons=incomplete_reasons,
                error_message=None,
                reconstructed_inputs_summary={},
                metadata=metadata or {},
            )
            return self._replay_repo.record(record)

        # 6. Check Historical Reproducibility & Recover Recorded Inputs
        incomplete_reasons = self._check_trace_input_completeness(trace)
        if incomplete_reasons:
            record = DecisionReplayRecord(
                id=replay_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                original_trace_id=trace.id,
                original_execution_id=trace.execution_id,
                replay_execution_id=replay_exec_id,
                created_at=now_utc,
                status=ReplayStatus.INCOMPLETE,
                original_result=original_result,
                replayed_result=None,
                comparison=None,
                incomplete_reasons=incomplete_reasons,
                error_message=None,
                reconstructed_inputs_summary=self._build_inputs_summary(trace),
                metadata=metadata or {},
            )
            return self._replay_repo.record(record)

        # 7. Execute Deterministic Replay Re-evaluation
        try:
            replayed_result, inputs_summary = self._execute_replay_evaluation(
                decision=decision,
                trace=trace,
            )
            comparison = compare_replay_results(original_result, replayed_result)
            overall_status = comparison.status

            record = DecisionReplayRecord(
                id=replay_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                original_trace_id=trace.id,
                original_execution_id=trace.execution_id,
                replay_execution_id=replay_exec_id,
                created_at=now_utc,
                status=overall_status,
                original_result=original_result,
                replayed_result=replayed_result,
                comparison=comparison,
                incomplete_reasons=[],
                error_message=None,
                reconstructed_inputs_summary=inputs_summary,
                metadata=metadata or {},
            )

            # Optional Decision Graph Metadata Enrichment
            if record_to_graph and self._graph_repo is not None:
                self._enrich_graph_with_replay(decision.id, record)

            return self._replay_repo.record(record)

        except Exception as exc:
            # Deterministic capture of unexpected calculation / evaluation errors
            record = DecisionReplayRecord(
                id=replay_id,
                decision_id=decision.id,
                version_id=trace.version_id or resolved_version_id,
                original_trace_id=trace.id,
                original_execution_id=trace.execution_id,
                replay_execution_id=replay_exec_id,
                created_at=now_utc,
                status=ReplayStatus.FAILED,
                original_result=original_result,
                replayed_result=None,
                comparison=None,
                incomplete_reasons=[],
                error_message=f"Replay execution failed: {type(exc).__name__}: {exc}",
                reconstructed_inputs_summary=self._build_inputs_summary(trace),
                metadata=metadata or {},
            )
            return self._replay_repo.record(record)

    def get_replay_record(
        self,
        decision_id: str,
        replay_id: str,
    ) -> DecisionReplayRecord:
        """Retrieves an individual replay record by ID, strictly enforcing decision isolation.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            ReplayRecordNotFoundError: If the replay record does not exist.
            CrossDecisionIsolationError: If the record belongs to another decision.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        norm_replay_id = replay_id.strip()
        record = self._replay_repo.get_by_id(norm_replay_id)
        if record is None:
            raise ReplayRecordNotFoundError(f"Replay record '{norm_replay_id}' not found")

        if record.decision_id != decision.id:
            raise CrossDecisionIsolationError(
                f"Replay record '{norm_replay_id}' belongs to decision '{record.decision_id}', "
                f"not requested decision '{decision.id}'"
            )

        return record

    def get_latest_replay(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> DecisionReplayRecord | None:
        """Retrieves the most recent replay record for a decision (and optional version).

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self._replay_repo.get_latest_for_decision(
            decision_id=decision.id,
            version_id=version_id,
        )

    def list_replay_records(
        self,
        decision_id: str,
        version_id: str | None = None,
    ) -> list[DecisionReplayRecord]:
        """Returns all replay records for a decision, sorted chronologically newest first.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        return self._replay_repo.list_by_decision_id(
            decision_id=decision.id,
            version_id=version_id,
        )

    # -----------------------------------------------------------------------
    # Internal Extraction and Evaluation Helpers
    # -----------------------------------------------------------------------

    def _extract_original_result(
        self,
        trace: DecisionProvenanceTrace,
    ) -> ReplayResultSnapshot | None:
        """Extracts the original decision outcome snapshot from recorded provenance results & calculations."""
        rec_res = next(
            (r for r in trace.results if r.result_type == ProvenanceResultType.RECOMMENDATION),
            None,
        )

        rec_val = (rec_res.value if rec_res and isinstance(rec_res.value, dict) else {})
        rec_id = rec_val.get("recommendation_id", rec_res.result_id if rec_res else None)
        status = rec_val.get("status", rec_res.outcome_status if rec_res else None)
        rec_action_id = rec_val.get("recommended_action_id", rec_res.action_id if rec_res else None)
        rec_action_type = rec_val.get("recommended_action_type")
        tie_broken = rec_val.get("tie_broken")

        # Map calculations by action_id and calculation_type
        calc_map: dict[str, dict[ProvenanceCalculationType, Any]] = {}
        for c in trace.calculations:
            if c.action_id:
                calc_map.setdefault(c.action_id, {})[c.calculation_type] = c

        eval_snapshots: dict[str, ReplayActionEvaluationSnapshot] = {}
        action_results = [r for r in trace.results if r.result_type == ProvenanceResultType.ACTION_EVALUATION]

        for act_r in action_results:
            act_id = act_r.action_id or act_r.result_id
            act_calcs = calc_map.get(act_id, {})

            score_calc = act_calcs.get(ProvenanceCalculationType.ACTION_SCORING)
            repl_calc = act_calcs.get(ProvenanceCalculationType.REPLENISHMENT_QUANTITY)
            risk_calc = act_calcs.get(ProvenanceCalculationType.STOCKOUT_EXPOSURE)
            cost_calc = act_calcs.get(ProvenanceCalculationType.COST_IMPACT)

            # Extract metrics defensively
            overall_score = None
            if score_calc and score_calc.output_value is not None:
                try:
                    overall_score = float(score_calc.output_value)
                except (ValueError, TypeError):
                    overall_score = None
            elif act_r.value and isinstance(act_r.value, dict) and "overall_score" in act_r.value:
                overall_score = act_r.value.get("overall_score")

            repl_qty = None
            shortfall_add = None
            rem_shortfall = None
            if repl_calc and isinstance(repl_calc.output_value, dict):
                repl_qty = repl_calc.output_value.get("recommended_quantity")
                shortfall_add = repl_calc.output_value.get("shortfall_addressed")
                rem_shortfall = repl_calc.output_value.get("remaining_shortfall")

            exp_delta = None
            curr_exp = None
            proj_exp = None
            if risk_calc and isinstance(risk_calc.output_value, dict):
                exp_delta = risk_calc.output_value.get("exposure_index_delta")
                curr_exp = risk_calc.output_value.get("current_exposure_index")
                proj_exp = risk_calc.output_value.get("projected_exposure_index")

            direct_cost = None
            cost_status = None
            if cost_calc:
                cost_status = cost_calc.status.value
                if cost_calc.output_value is not None:
                    try:
                        direct_cost = float(cost_calc.output_value)
                    except (ValueError, TypeError):
                        direct_cost = None

            eval_snapshots[act_id] = ReplayActionEvaluationSnapshot(
                action_id=act_id,
                scoring_status=act_r.outcome_status,
                overall_score=overall_score,
                recommended_replenishment_quantity=repl_qty,
                shortfall_addressed=shortfall_add,
                remaining_shortfall=rem_shortfall,
                exposure_index_delta=exp_delta,
                current_exposure_index=curr_exp,
                projected_exposure_index=proj_exp,
                direct_procurement_cost=direct_cost,
                cost_status=cost_status,
            )

        # Retrieve selection rule if available
        sel_rule = next(
            (r.rule_name for r in trace.rules if r.rule_type == ProvenanceRuleType.SELECTION_STRATEGY),
            None,
        )
        tie_rule = next(
            (r.rule_name for r in trace.rules if r.rule_type == ProvenanceRuleType.TIE_BREAKER),
            None,
        )

        return ReplayResultSnapshot(
            recommendation_id=rec_id,
            status=status,
            recommended_action_id=rec_action_id,
            recommended_action_type=rec_action_type,
            tie_broken=tie_broken,
            tie_break_method=tie_rule,
            selection_rule=sel_rule,
            evaluations=eval_snapshots,
            metadata={"extracted_from_trace": trace.id},
        )

    def _check_trace_input_completeness(
        self,
        trace: DecisionProvenanceTrace,
    ) -> list[IncompleteReason]:
        """Validates that all required operational inputs and rules are recorded and available."""
        reasons: list[IncompleteReason] = []

        # 1. Product input
        prod_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.PRODUCT), None)
        if prod_inp is None:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Product catalog input record is missing from the provenance trace.",
                    details={"input_type": "PRODUCT"},
                )
            )
        elif prod_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(prod_inp.value, dict):
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical product catalog data was marked unavailable or missing during execution.",
                    details={"input_type": "PRODUCT", "status": prod_inp.status.value},
                )
            )

        # 2. Warehouse input
        wh_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.WAREHOUSE), None)
        if wh_inp is None:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Warehouse facility input record is missing from the provenance trace.",
                    details={"input_type": "WAREHOUSE"},
                )
            )
        elif wh_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(wh_inp.value, dict):
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical warehouse facility data was marked unavailable or missing during execution.",
                    details={"input_type": "WAREHOUSE", "status": wh_inp.status.value},
                )
            )

        # 3. Inventory input
        inv_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.INVENTORY), None)
        if inv_inp is None:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Inventory position input record is missing from the provenance trace.",
                    details={"input_type": "INVENTORY"},
                )
            )
        elif inv_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(inv_inp.value, dict):
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical inventory position was marked unavailable during execution.",
                    details={"input_type": "INVENTORY", "status": inv_inp.status.value},
                )
            )

        # 4. Demand input
        dem_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.DEMAND), None)
        if dem_inp is None:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Historical demand trend input record is missing from the provenance trace.",
                    details={"input_type": "DEMAND"},
                )
            )
        elif dem_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(dem_inp.value, dict):
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Historical demand metrics were marked unavailable during execution.",
                    details={"input_type": "DEMAND", "status": dem_inp.status.value},
                )
            )

        # 5. Primary Supplier input
        sup_inp = next((i for i in trace.inputs if i.input_type == ProvenanceInputType.SUPPLIER), None)
        if sup_inp is None:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_INPUT_RECORD,
                    message="Primary supplier input record is missing from the provenance trace.",
                    details={"input_type": "SUPPLIER"},
                )
            )
        elif sup_inp.status != ProvenanceStepStatus.SUCCESS or not isinstance(sup_inp.value, dict):
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT,
                    message="Primary supplier operational metrics were marked unavailable during execution.",
                    details={"input_type": "SUPPLIER", "status": sup_inp.status.value},
                )
            )

        # 6. Candidate action inputs
        act_inps = [i for i in trace.inputs if i.input_type == ProvenanceInputType.CANDIDATE_ACTION]
        if not act_inps:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_CANDIDATE_ACTIONS,
                    message="No candidate actions were recorded in the provenance trace.",
                    details={},
                )
            )

        # 7. Replenishment policy rule definition
        pol_rule = next((r for r in trace.rules if r.rule_type == ProvenanceRuleType.REPLENISHMENT_POLICY), None)
        if pol_rule is None:
            reasons.append(
                IncompleteReason(
                    code=IncompleteReasonCode.UNAVAILABLE_RULE_DEFINITION,
                    message="Replenishment policy rule definition is missing from the provenance trace.",
                    details={"rule_type": "REPLENISHMENT_POLICY"},
                )
            )

        return reasons

    def _execute_replay_evaluation(
        self,
        decision: Any,
        trace: DecisionProvenanceTrace,
    ) -> tuple[ReplayResultSnapshot, dict[str, Any]]:
        """Re-evaluates the decision strictly from recorded historical inputs and rules."""
        prod_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.PRODUCT)
        wh_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.WAREHOUSE)
        inv_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.INVENTORY)
        dem_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.DEMAND)
        sup_inp = next(i for i in trace.inputs if i.input_type == ProvenanceInputType.SUPPLIER)
        act_inps = [i for i in trace.inputs if i.input_type == ProvenanceInputType.CANDIDATE_ACTION]
        pol_rule = next(r for r in trace.rules if r.rule_type == ProvenanceRuleType.REPLENISHMENT_POLICY)

        # Reconstruct Product
        prod_val = prod_inp.value or {}
        reconstructed_product = Product(
            id=prod_val.get("product_id", decision.product_id),
            sku=prod_val.get("sku", f"SKU-{prod_val.get('product_id', decision.product_id)}"),
            name=prod_inp.name,
            category=prod_val.get("category", "General"),
            unit_cost=float(prod_val.get("unit_cost", 0.0)),
            selling_price=float(prod_val.get("selling_price", float(prod_val.get("unit_cost", 0.0)) * 1.5)),
            reorder_point=int(prod_val.get("reorder_point", 0)),
            active=True,
        )

        # Reconstruct Warehouse
        wh_val = wh_inp.value or {}
        wh_id = wh_val.get("warehouse_id", decision.warehouse_id)
        wh_capacity = int(wh_val.get("capacity", 10000))

        # Reconstruct Primary Supplier
        sup_val = sup_inp.value or {}
        sup_id = sup_val.get("supplier_id", "sup-001")
        reconstructed_supplier = Supplier(
            id=sup_id,
            code=sup_val.get("code", f"SUP-CODE-{sup_id}"),
            name=sup_inp.name,
            lead_time_days=int(sup_val.get("lead_time_days", 5)),
            reliability=float(sup_val.get("reliability", 1.0)),
            active=True,
        )

        # Reconstruct Inventory positions and Demand
        inv_val = inv_inp.value or {}
        avail_qty = int(inv_val.get("available_quantity", 0))
        reorder_point = int(inv_val.get("reorder_point", reconstructed_product.reorder_point))

        dem_val = dem_inp.value or {}
        avg_demand = float(dem_val.get("average_daily_demand", 0.0))

        # Reconstruct Policy
        policy_type = ReplenishmentPolicyType(pol_rule.rule_name)

        # Reconstruct Candidate Actions
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

        # Re-evaluate candidate actions deterministically
        evaluations: list[ActionEvaluationResult] = []
        eval_snapshots: dict[str, ReplayActionEvaluationSnapshot] = {}

        for act in reconstructed_actions:
            target_sup = None
            if act.action_type == ActionType.SWITCH_SUPPLIER:
                assert isinstance(act.parameters, SwitchSupplierParameters)
                target_sup_id = act.parameters.target_supplier_id
                # Attempt to resolve from supplier repo or dataset
                target_sup = self._supplier_repo.get_by_id(target_sup_id)
                if target_sup is None:
                    # Defensive fallback using incumbent parameters if missing
                    target_sup = Supplier(
                        id=target_sup_id,
                        code=f"CODE-{target_sup_id}",
                        name=f"Alternative Supplier {target_sup_id}",
                        lead_time_days=reconstructed_supplier.lead_time_days,
                        reliability=reconstructed_supplier.reliability,
                        active=True,
                    )

            eval_inputs = ActionEvaluationInputs(
                action=act,
                product=reconstructed_product,
                warehouse_id=wh_id,
                available_quantity=avail_qty,
                reorder_point=reorder_point,
                average_daily_demand=avg_demand,
                current_supplier=reconstructed_supplier,
                target_supplier=target_sup,
                replenishment_policy=policy_type,
                target_stock=None,
                enforce_reorder_trigger=True,
                warehouse_capacity=wh_capacity,
                historical_daily_demands=None,
            )

            eval_res = evaluate_candidate_action(eval_inputs)
            evaluations.append(eval_res)

            eval_snapshots[act.id] = ReplayActionEvaluationSnapshot(
                action_id=act.id,
                scoring_status=eval_res.scoring_status,
                overall_score=eval_res.overall_score,
                recommended_replenishment_quantity=eval_res.replenishment_impact.recommended_replenishment_quantity,
                shortfall_addressed=eval_res.replenishment_impact.shortfall_addressed,
                remaining_shortfall=eval_res.replenishment_impact.remaining_shortfall,
                exposure_index_delta=eval_res.stockout_exposure.exposure_index_delta,
                current_exposure_index=eval_res.stockout_exposure.current_exposure_index,
                projected_exposure_index=eval_res.stockout_exposure.projected_exposure_index,
                direct_procurement_cost=eval_res.cost_impact.direct_procurement_cost,
                cost_status=(
                    ProvenanceStepStatus.SUCCESS.value
                    if eval_res.cost_impact.is_cost_calculable
                    else ProvenanceStepStatus.UNAVAILABLE.value
                ),
            )

        # Select replayed recommendation deterministically
        replayed_rec = select_deterministic_recommendation(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            evaluations=evaluations,
            candidate_actions=reconstructed_actions,
            policy_type=policy_type,
        )

        replayed_snapshot = ReplayResultSnapshot(
            recommendation_id=replayed_rec.id,
            status=replayed_rec.status.value,
            recommended_action_id=replayed_rec.recommended_action_id,
            recommended_action_type=replayed_rec.recommended_action_type.value
            if replayed_rec.recommended_action_type
            else None,
            tie_broken=replayed_rec.tie_broken,
            tie_break_method=replayed_rec.tie_break_method.value,
            selection_rule=replayed_rec.selection_rule,
            evaluations=eval_snapshots,
            metadata={"source": "deterministic_replay_evaluation"},
        )

        inputs_summary = {
            "product_id": reconstructed_product.id,
            "warehouse_id": wh_id,
            "available_quantity": avail_qty,
            "reorder_point": reorder_point,
            "average_daily_demand": avg_demand,
            "supplier_id": reconstructed_supplier.id,
            "supplier_lead_time_days": reconstructed_supplier.lead_time_days,
            "policy_type": policy_type.value,
            "candidate_actions_count": len(reconstructed_actions),
        }

        return replayed_snapshot, inputs_summary

    def _build_inputs_summary(self, trace: DecisionProvenanceTrace) -> dict[str, Any]:
        """Summarizes recorded inputs present in the trace for reporting."""
        return {
            "trace_id": trace.id,
            "total_inputs_recorded": len(trace.inputs),
            "input_types": sorted(list({i.input_type.value for i in trace.inputs})),
            "rules_recorded": [r.rule_name for r in trace.rules],
        }

    def _enrich_graph_with_replay(
        self,
        decision_id: str,
        record: DecisionReplayRecord,
    ) -> None:
        """Safely enriches DecisionGraph RESULT nodes with replay metadata if graph exists."""
        if self._graph_repo is None:
            return
        graph = self._graph_repo.get_by_decision_id(decision_id)
        if graph is None:
            return

        for node in graph.nodes:
            if node.node_type.value == "RESULT":
                node.metadata["latest_replay_id"] = record.id
                node.metadata["latest_replay_status"] = record.status.value
                node.metadata["latest_replay_at"] = record.created_at.isoformat()

        self._graph_repo.update_graph(graph)
