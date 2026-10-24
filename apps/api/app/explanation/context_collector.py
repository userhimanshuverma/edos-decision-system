from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from app.domain.decision import Decision
from app.domain.explanation import DecisionExplanationContext
from app.domain.recommendation import Recommendation
from app.domain.validation import DecisionValidationReport
from app.domain.evidence import DecisionEvidenceSheet, EvidenceCategory, EvidenceType
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.provenance_repository import ProvenanceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.replay_repository import ReplayRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.validation_repository import ValidationRepository
from app.evidence.service import EvidenceService
from app.recommendation.service import RecommendationService
from app.validation.service import ValidationService


class DecisionExplanationContextError(Exception):
    """Base exception for explanation context assembly."""


class DecisionNotFoundError(DecisionExplanationContextError, KeyError):
    """Raised when the specified decision does not exist."""


class DecisionVersionNotFoundError(DecisionExplanationContextError, KeyError):
    """Raised when the specified decision version does not exist."""


class DecisionExplanationContextCollector:
    """Assembles grounded, deterministic decision context for local LLM explanation.

    Adheres strictly to the core principle:
    "The system calculates. AI explains. Humans approve."

    Guarantees:
    - Never fabricates evidence, provenance, replay, or scenario results.
    - Explicitly isolates historical version records from live mutable state.
    - Clearly records missing information and limitations when context is incomplete.
    """

    def __init__(
        self,
        decision_repo: DecisionRepository,
        version_repo: DecisionVersionRepository | None = None,
        recommendation_repo: RecommendationRepository | None = None,
        recommendation_service: RecommendationService | None = None,
        validation_repo: ValidationRepository | None = None,
        validation_service: ValidationService | None = None,
        action_repo: CandidateActionRepository | None = None,
        evidence_repo: EvidenceRepository | None = None,
        evidence_service: EvidenceService | None = None,
        provenance_repo: ProvenanceRepository | None = None,
        replay_repo: ReplayRepository | None = None,
        scenario_repo: ScenarioRepository | None = None,
    ) -> None:
        self._decision_repo = decision_repo
        self._version_repo = version_repo or getattr(decision_repo, "version_repository", None)
        self._recommendation_repo = recommendation_repo or RecommendationRepository()
        self._recommendation_service = recommendation_service
        self._validation_repo = validation_repo or ValidationRepository()
        self._validation_service = validation_service
        self._action_repo = action_repo or getattr(decision_repo, "action_repository", None) or CandidateActionRepository()
        self._evidence_repo = evidence_repo or EvidenceRepository()
        self._evidence_service = evidence_service
        self._provenance_repo = provenance_repo or ProvenanceRepository()
        self._replay_repo = replay_repo or ReplayRepository()
        self._scenario_repo = scenario_repo or ScenarioRepository()

    def collect_context(
        self,
        decision_id: str,
        *,
        version_id: str | None = None,
    ) -> DecisionExplanationContext:
        """Assembles a verified, typed context representation for an existing decision.

        Args:
            decision_id: Identifier of the business decision.
            version_id: Optional specific historical version identifier.

        Raises:
            DecisionNotFoundError: If the decision does not exist.
            DecisionVersionNotFoundError: If version_id is provided but not found or belongs to another decision.
        """
        norm_decision_id = decision_id.strip()
        decision = self._decision_repo.get_by_id(norm_decision_id)
        if decision is None:
            raise DecisionNotFoundError(f"Decision '{norm_decision_id}' not found")

        known_limitations: list[str] = []
        missing_information: list[str] = []

        # 1. Version Linkage
        target_version_id: str | None = None
        if version_id:
            norm_version_id = version_id.strip()
            if self._version_repo is None:
                raise DecisionVersionNotFoundError(f"Version repository unavailable; version '{norm_version_id}' not found")
            version = self._version_repo.get_by_id(norm_version_id)
            if version is None or version.decision_id != decision.id:
                raise DecisionVersionNotFoundError(
                    f"Decision version '{norm_version_id}' not found for decision '{decision.id}'"
                )
            target_version_id = version.id
            known_limitations.append(
                f"Explanation is scoped to historical decision version {version.id} (sequence #{version.version_number})."
            )
        else:
            known_limitations.append(
                "Explanation is scoped to current decision state (no explicit version was specified)."
            )

        # 2. Recommendation
        recommendation = None
        if self._recommendation_service is not None:
            try:
                recommendation = self._recommendation_service.get_latest_recommendation(decision.id)
            except Exception:
                recommendation = None
        if recommendation is None:
            recommendation = self._recommendation_repo.get_latest_for_decision(decision.id)

        rec_status: str | None = None
        rec_action_id: str | None = None
        rec_action_type: str | None = None
        rec_selection_rule: str | None = None
        rec_selection_rationale: str | None = None
        action_parameters: dict[str, Any] = {}

        if recommendation is not None:
            rec_status = recommendation.status.value
            rec_action_id = recommendation.recommended_action_id
            rec_selection_rule = recommendation.selection_rule
            rec_selection_rationale = recommendation.selection_rationale

            if rec_action_id:
                action = self._action_repo.get_by_id(rec_action_id)
                if action is not None:
                    rec_action_type = action.action_type.value
                    if hasattr(action.parameters, "model_dump"):
                        action_parameters = action.parameters.model_dump()
                    elif isinstance(action.parameters, dict):
                        action_parameters = action.parameters
        else:
            missing_information.append(
                "No recommendation has been recorded for this decision yet. Evaluation pipeline may be incomplete."
            )

        # 3. Validation Report (Constraints)
        constraint_results: list[dict[str, Any]] = []
        validation_report = None
        if self._validation_service is not None:
            try:
                validation_report = self._validation_service.get_latest_validation_report(decision.id)
            except Exception:
                validation_report = None
        if validation_report is None:
            validation_report = self._validation_repo.get_latest_for_decision(decision.id)
        if validation_report is not None:
            for act_res in validation_report.action_results:
                for c_res in act_res.constraint_results:
                    constraint_results.append({
                        "action_id": act_res.action_id,
                        "constraint_name": c_res.constraint_name,
                        "constraint_type": c_res.constraint_type.value if hasattr(c_res.constraint_type, "value") else str(c_res.constraint_type),
                        "status": c_res.status.value if hasattr(c_res.status, "value") else str(c_res.status),
                        "observed_value": c_res.observed_value,
                        "threshold_value": c_res.threshold_value,
                        "unit": c_res.unit,
                        "reason": c_res.reason,
                    })
        else:
            missing_information.append(
                "No constraint validation report was found for this decision."
            )

        # 4. Evidence and Assumptions
        evidence_items: list[dict[str, Any]] = []
        assumptions: list[dict[str, Any]] = []
        calculation_results: list[dict[str, Any]] = []

        # Check for compiled evidence sheet or compile if evidence service is wired
        sheet: DecisionEvidenceSheet | None = None
        if self._evidence_service is not None:
            try:
                sheet = self._evidence_service.compile_evidence_sheet(
                    decision_id=decision.id,
                    version_id=target_version_id,
                )
            except Exception:
                sheet = None

        if sheet is not None:
            for it in sheet.items:
                item_dict = {
                    "id": it.id,
                    "evidence_type": it.evidence_type.value if hasattr(it.evidence_type, "value") else str(it.evidence_type),
                    "category": it.category.value if hasattr(it.category, "value") else str(it.category),
                    "description": it.description,
                    "value": it.value,
                    "unit": it.unit,
                    "source": it.source,
                }
                if it.evidence_type == EvidenceType.CALCULATION:
                    calculation_results.append(item_dict)
                evidence_items.append(item_dict)

            for asm in sheet.assumptions:
                assumptions.append({
                    "id": asm.id,
                    "category": asm.category.value if hasattr(asm.category, "value") else str(asm.category),
                    "statement": asm.statement,
                    "assumed_value": asm.assumed_value,
                    "rationale": asm.rationale,
                    "source": asm.source,
                })
        else:
            # Fall back to repository evidence and assumptions
            stored_evidence = self._evidence_repo.list_evidence_by_decision(decision.id)
            for ev in stored_evidence:
                item_dict = {
                    "id": ev.id,
                    "evidence_type": ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type),
                    "category": ev.category.value if hasattr(ev.category, "value") else str(ev.category),
                    "description": ev.description,
                    "value": ev.value,
                    "unit": ev.unit,
                    "source": ev.source,
                }
                if ev.evidence_type == EvidenceType.CALCULATION:
                    calculation_results.append(item_dict)
                evidence_items.append(item_dict)

            stored_asms = self._evidence_repo.list_assumptions_by_decision(decision.id)
            for asm in stored_asms:
                assumptions.append({
                    "id": asm.id,
                    "category": asm.category.value if hasattr(asm.category, "value") else str(asm.category),
                    "statement": asm.statement,
                    "assumed_value": asm.assumed_value,
                    "rationale": asm.rationale,
                    "source": asm.source,
                })

        if not evidence_items and not assumptions:
            missing_information.append(
                "No grounded evidence sheet or assumption records were compiled for this decision."
            )

        # 5. Provenance Trace
        provenance_trace_id: str | None = None
        latest_trace = self._provenance_repo.get_latest_for_decision(decision.id, version_id=target_version_id)
        if latest_trace is not None:
            provenance_trace_id = latest_trace.id

        # 6. Replay Status
        replay_summary: dict[str, Any] | None = None
        latest_replay = self._replay_repo.get_latest_for_decision(decision.id, version_id=target_version_id)
        if latest_replay is not None:
            replay_summary = {
                "replay_id": latest_replay.id,
                "status": latest_replay.status.value,
                "has_differences": bool(latest_replay.comparison.differences) if latest_replay.comparison else False,
                "executed_at": latest_replay.executed_at.isoformat(),
            }

        # 7. Scenario Status
        scenario_summary: dict[str, Any] | None = None
        latest_scenario = self._scenario_repo.get_latest_for_decision(decision.id, version_id=target_version_id)
        if latest_scenario is not None:
            scenario_summary = {
                "scenario_id": latest_scenario.id,
                "name": latest_scenario.name,
                "status": latest_scenario.status.value,
                "executed_at": latest_scenario.executed_at.isoformat(),
            }

        return DecisionExplanationContext(
            decision_id=decision.id,
            decision_version_id=target_version_id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            decision_status=decision.status.value,
            recommendation_status=rec_status,
            recommended_action_id=rec_action_id,
            recommended_action_type=rec_action_type,
            selection_rule=rec_selection_rule,
            selection_rationale=rec_selection_rationale,
            action_parameters=action_parameters,
            calculation_results=calculation_results,
            constraint_results=constraint_results,
            evidence_items=evidence_items,
            assumptions=assumptions,
            provenance_trace_id=provenance_trace_id,
            replay_summary=replay_summary,
            scenario_summary=scenario_summary,
            known_limitations=known_limitations,
            missing_information=missing_information,
            collected_at=datetime.now(timezone.utc),
        )
