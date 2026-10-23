from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError


from app.api.inventory import get_inventory_repository
from app.api.schemas import (
    CandidateActionResponse,
    CreateCandidateActionRequest,
    CreateDecisionGraphRequest,
    CreateDecisionRequest,
    CreateDecisionVersionRequest,
    DecisionEventResponse,
    DecisionGraphResponse,
    DecisionReplenishmentRequest,
    DecisionResponse,
    DecisionStockoutRiskRequest,
    DecisionVersionResponse,
    ReplenishmentPolicyType,
    ReplenishmentResponse,
    StockoutRiskModelType,
    StockoutRiskResponse,
    UpdateDecisionStatusRequest,
    ActionEvaluationResponse,
    DecisionEvaluationReportResponse,
    EvaluateActionRequest,
    EvaluateDecisionActionsRequest,
    GenerateRecommendationRequest,
    RecommendationResponse,
    ActionValidationResponse,
    ConstraintConfigRequest,
    DecisionValidationReportResponse,
    ValidateActionRequest,
    ValidateDecisionRequest,
    CreateEvidenceRequest,
    CreateAssumptionRequest,
    DecisionEvidenceResponse,
    DecisionAssumptionResponse,
    DecisionEvidenceSummaryResponse,
    DecisionEvidenceSheetResponse,
    EvidenceCategory,
    EvidenceType,
    CaptureProvenanceRequest,
    DecisionProvenanceTraceResponse,
    ProvenanceDerivationResponse,
    DecisionReplayResponse,
    ReplayDecisionRequest,
    DecisionScenarioResponse,
    ExecuteScenarioRequest,
    ScenarioComparisonResponse,
)

from app.candidate_actions.service import (
    CandidateActionNotFoundError,
    CandidateActionService,
    DecisionNotFoundError,
)
from app.evaluation.service import (
    ActionEvaluationService,
    CandidateActionNotFoundError as EvalActionNotFoundError,
    DecisionNotFoundError as EvalDecisionNotFoundError,
    MissingEvaluationDataError,
)
from app.recommendation.service import (
    DecisionNotFoundError as RecDecisionNotFoundError,
    RecommendationNotFoundError,
    RecommendationService,
)
from app.validation.service import (
    CandidateActionNotFoundError as ValActionNotFoundError,
    DecisionNotFoundError as ValDecisionNotFoundError,
    ValidationError,
    ValidationReportNotFoundError,
    ValidationService,
)
from app.evidence.service import (
    AssumptionNotFoundError,
    CandidateActionNotFoundError as EvActionNotFoundError,
    CrossDecisionIsolationError,
    DecisionNotFoundError as EvDecisionNotFoundError,
    DecisionVersionNotFoundError as EvVersionNotFoundError,
    EvidenceNotFoundError,
    EvidenceService,
    InvalidEvidencePayloadError,
)
from app.provenance.service import (
    CrossDecisionIsolationError as PrvCrossDecisionIsolationError,
    DecisionNotFoundError as PrvDecisionNotFoundError,
    DecisionVersionNotFoundError as PrvVersionNotFoundError,
    InvalidProvenancePayloadError as PrvInvalidPayloadError,
    ProvenanceService,
    ProvenanceTraceNotFoundError,
)
from app.repositories.provenance_repository import (
    DuplicateProvenanceTraceError,
    ProvenanceRepository,
)
from app.replay.service import (
    CrossDecisionIsolationError as RplCrossDecisionIsolationError,
    DecisionNotFoundError as RplDecisionNotFoundError,
    DecisionVersionNotFoundError as RplVersionNotFoundError,
    InvalidReplayRequestError as RplInvalidRequestError,
    ProvenanceTraceNotFoundError as RplProvenanceNotFoundError,
    ReplayRecordNotFoundError,
    DecisionReplayService,
)
from app.repositories.replay_repository import (
    DuplicateReplayRecordError,
    ReplayRepository,
)
from app.scenario.service import (
    CrossDecisionIsolationError as ScnCrossDecisionIsolationError,
    DecisionNotFoundError as ScnDecisionNotFoundError,
    DecisionScenarioError,
    DecisionVersionNotFoundError as ScnVersionNotFoundError,
    InvalidScenarioRequestError as ScnInvalidRequestError,
    ProvenanceTraceNotFoundError as ScnProvenanceNotFoundError,
    ScenarioRecordNotFoundError,
    ScenarioService,
)
from app.repositories.scenario_repository import (
    DuplicateScenarioRecordError,
    ScenarioRepository,
)






from app.replenishment.service import (
    DecisionNotFoundError as ReplenishmentDecisionNotFoundError,
    MissingReplenishmentDataError,
    ProductNotFoundError,
    ReplenishmentService,
    WarehouseNotFoundError,
)
from app.stockout_risk.service import (
    DecisionNotFoundError as StockoutRiskDecisionNotFoundError,
    MissingStockoutRiskDataError,
    ProductNotFoundError as RiskProductNotFoundError,
    StockoutRiskService,
    WarehouseNotFoundError as RiskWarehouseNotFoundError,
)
from app.domain.candidate_action import (
    IneligibleSupplierError,
    SupplierNotFoundError,
)
from app.domain.decision_graph import (
    GraphEdge,
    GraphIntegrityError,
    GraphNode,
)
from app.lifecycle.service import InvalidLifecycleTransitionError
from app.repositories.candidate_action_repository import (
    CandidateActionRepository,
    DuplicateCandidateActionError,
)
from app.repositories.decision_event_repository import DecisionEventRepository
from app.repositories.decision_graph_repository import (
    DecisionGraphRepository,
    DuplicateDecisionGraphError,
)
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository
from app.repositories.evidence_repository import (
    DuplicateAssumptionError,
    DuplicateEvidenceError,
    DuplicateEvidenceSheetError,
    EvidenceRepository,
)


router = APIRouter()


@lru_cache
def get_decision_event_repository() -> DecisionEventRepository:
    """Dependency provider returning the singleton DecisionEventRepository instance."""
    return DecisionEventRepository()


@lru_cache
def get_decision_version_repository() -> DecisionVersionRepository:
    """Dependency provider returning the singleton DecisionVersionRepository instance."""
    return DecisionVersionRepository()


@lru_cache
def get_decision_graph_repository() -> DecisionGraphRepository:
    """Dependency provider returning the singleton DecisionGraphRepository instance."""
    return DecisionGraphRepository()


@lru_cache
def get_candidate_action_repository() -> CandidateActionRepository:
    """Dependency provider returning the singleton CandidateActionRepository instance."""
    return CandidateActionRepository()


@lru_cache
def get_decision_repository() -> DecisionRepository:
    """Dependency provider returning the singleton DecisionRepository instance."""
    return DecisionRepository(
        event_repository=get_decision_event_repository(),
        version_repository=get_decision_version_repository(),
        graph_repository=get_decision_graph_repository(),
        action_repository=get_candidate_action_repository(),
    )


@lru_cache
def get_candidate_action_service() -> CandidateActionService:
    """Dependency provider returning the singleton CandidateActionService instance."""
    return CandidateActionService(
        decision_repository=get_decision_repository(),
        action_repository=get_candidate_action_repository(),
        graph_repository=get_decision_graph_repository(),
    )


@lru_cache
def get_decision_replenishment_service() -> ReplenishmentService:
    """Dependency provider returning ReplenishmentService wired to decision repository."""
    dec_repo = get_decision_repository()
    shared_dataset = dec_repo.dataset
    return ReplenishmentService(
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        decision_repo=dec_repo,
    )


@lru_cache
def get_decision_stockout_risk_service() -> StockoutRiskService:
    """Dependency provider returning StockoutRiskService wired to decision repository."""
    dec_repo = get_decision_repository()
    shared_dataset = dec_repo.dataset
    return StockoutRiskService(
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        decision_repo=dec_repo,
    )


@lru_cache
def get_action_evaluation_service() -> ActionEvaluationService:
    """Dependency provider returning ActionEvaluationService wired to repositories."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    graph_repo = get_decision_graph_repository()
    shared_dataset = dec_repo.dataset
    return ActionEvaluationService(
        decision_repo=dec_repo,
        action_repo=action_repo,
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        graph_repo=graph_repo,
    )


@lru_cache
def get_recommendation_repository() -> RecommendationRepository:
    """Dependency provider returning singleton RecommendationRepository."""
    return RecommendationRepository()


@lru_cache
def get_recommendation_service() -> RecommendationService:
    """Dependency provider returning RecommendationService wired to repositories."""
    return RecommendationService(
        decision_repo=get_decision_repository(),
        action_repo=get_candidate_action_repository(),
        evaluation_service=get_action_evaluation_service(),
        recommendation_repo=get_recommendation_repository(),
        graph_repo=get_decision_graph_repository(),
    )


@lru_cache
def get_validation_repository() -> ValidationRepository:
    """Dependency provider returning singleton ValidationRepository."""
    return ValidationRepository()


@lru_cache
def get_validation_service() -> ValidationService:
    """Dependency provider returning ValidationService wired to repositories."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    graph_repo = get_decision_graph_repository()
    shared_dataset = dec_repo.dataset
    return ValidationService(
        decision_repo=dec_repo,
        action_repo=action_repo,
        inventory_repo=get_inventory_repository(),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        validation_repo=get_validation_repository(),
        graph_repo=graph_repo,
    )


@lru_cache
def get_evidence_repository() -> EvidenceRepository:
    """Dependency provider returning singleton EvidenceRepository."""
    return EvidenceRepository()


@lru_cache
def get_evidence_service() -> EvidenceService:
    """Dependency provider returning EvidenceService wired to repositories."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    version_repo = get_decision_version_repository()
    shared_dataset = dec_repo.dataset
    return EvidenceService(
        decision_repo=dec_repo,
        evidence_repo=get_evidence_repository(),
        action_repo=action_repo,
        version_repo=version_repo,
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        recommendation_repo=get_recommendation_repository(),
        validation_repo=get_validation_repository(),
    )


@lru_cache
def get_provenance_repository() -> ProvenanceRepository:
    """Dependency provider returning singleton ProvenanceRepository."""
    return ProvenanceRepository()


@lru_cache
def get_provenance_service() -> ProvenanceService:
    """Dependency provider returning ProvenanceService wired to repositories."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    version_repo = get_decision_version_repository()
    graph_repo = get_decision_graph_repository()
    shared_dataset = dec_repo.dataset
    return ProvenanceService(
        decision_repo=dec_repo,
        provenance_repo=get_provenance_repository(),
        action_repo=action_repo,
        version_repo=version_repo,
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        evaluation_service=get_action_evaluation_service(),
        recommendation_repo=get_recommendation_repository(),
        validation_repo=get_validation_repository(),
        evidence_repo=get_evidence_repository(),
        graph_repo=graph_repo,
    )


@lru_cache
def get_replay_repository() -> ReplayRepository:
    """Dependency provider returning singleton ReplayRepository."""
    return ReplayRepository()


@lru_cache
def get_replay_service() -> DecisionReplayService:
    """Dependency provider returning DecisionReplayService wired to repositories."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    version_repo = get_decision_version_repository()
    graph_repo = get_decision_graph_repository()
    shared_dataset = dec_repo.dataset
    return DecisionReplayService(
        decision_repo=dec_repo,
        replay_repo=get_replay_repository(),
        provenance_repo=get_provenance_repository(),
        action_repo=action_repo,
        version_repo=version_repo,
        recommendation_repo=get_recommendation_repository(),
        validation_repo=get_validation_repository(),
        evaluation_service=get_action_evaluation_service(),
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        graph_repo=graph_repo,
    )


@lru_cache
def get_scenario_repository() -> ScenarioRepository:
    """Dependency provider returning singleton ScenarioRepository."""
    return ScenarioRepository()


@lru_cache
def get_scenario_service() -> ScenarioService:
    """Dependency provider returning ScenarioService wired to repositories."""
    dec_repo = get_decision_repository()
    action_repo = get_candidate_action_repository()
    version_repo = get_decision_version_repository()
    graph_repo = get_decision_graph_repository()
    shared_dataset = dec_repo.dataset
    return ScenarioService(
        decision_repo=dec_repo,
        scenario_repo=get_scenario_repository(),
        provenance_repo=get_provenance_repository(),
        action_repo=action_repo,
        version_repo=version_repo,
        recommendation_repo=get_recommendation_repository(),
        validation_repo=get_validation_repository(),
        evaluation_service=get_action_evaluation_service(),
        inventory_repo=get_inventory_repository(),
        demand_repo=DemandRepository(dataset=shared_dataset),
        supplier_repo=SupplierRepository(dataset=shared_dataset),
        graph_repo=graph_repo,
    )








@router.post(
    "",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new business decision",
    description="Creates a decision associated with a valid product and warehouse in DRAFT status.",
)
def create_decision(
    payload: CreateDecisionRequest,
    decision_repo: DecisionRepository = Depends(get_decision_repository),
    inventory_repo: InventoryRepository = Depends(get_inventory_repository),
) -> DecisionResponse:
    if not inventory_repo.product_exists(payload.product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{payload.product_id}' not found",
        )
    if not inventory_repo.warehouse_exists(payload.warehouse_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{payload.warehouse_id}' not found",
        )

    decision = decision_repo.create(
        product_id=payload.product_id,
        warehouse_id=payload.warehouse_id,
    )
    return DecisionResponse.from_domain(decision)


@router.get(
    "",
    response_model=list[DecisionResponse],
    summary="List all decisions",
    description="Returns decisions currently held by the repository with deterministic ordering.",
)
def list_decisions(
    product_id: str | None = Query(default=None, description="Optional product ID filter"),
    warehouse_id: str | None = Query(default=None, description="Optional warehouse ID filter"),
    repo: DecisionRepository = Depends(get_decision_repository),
) -> list[DecisionResponse]:
    records = repo.list_all(product_id=product_id, warehouse_id=warehouse_id)
    return [DecisionResponse.from_domain(d) for d in records]


@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
    summary="Get decision by ID",
    description="Retrieves a single business decision by its unique identifier.",
)
def get_decision_by_id(
    decision_id: str,
    repo: DecisionRepository = Depends(get_decision_repository),
) -> DecisionResponse:
    record = repo.get_by_id(decision_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    return DecisionResponse.from_domain(record)


@router.patch(
    "/{decision_id}/status",
    response_model=DecisionResponse,
    summary="Update decision lifecycle status",
    description="Transitions a business decision to the next sequential lifecycle state following deterministic validation rules.",
)
def update_decision_status(
    decision_id: str,
    payload: UpdateDecisionStatusRequest,
    repo: DecisionRepository = Depends(get_decision_repository),
) -> DecisionResponse:
    existing = repo.get_by_id(decision_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )

    try:
        updated = repo.update_status(decision_id=decision_id, new_status=payload.status)
    except InvalidLifecycleTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )

    return DecisionResponse.from_domain(updated)


@router.get(
    "/{decision_id}/events",
    response_model=list[DecisionEventResponse],
    summary="Get decision event history",
    description="Returns chronological audit trail events for a specific business decision.",
)
def get_decision_events(
    decision_id: str,
    repo: DecisionRepository = Depends(get_decision_repository),
    event_repo: DecisionEventRepository = Depends(get_decision_event_repository),
) -> list[DecisionEventResponse]:
    record = repo.get_by_id(decision_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    events = event_repo.get_by_decision_id(decision_id)
    return [DecisionEventResponse.from_domain(e) for e in events]


@router.post(
    "/{decision_id}/versions",
    response_model=DecisionVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new decision version",
    description="Captures an immutable snapshot of the decision's current operational state.",
)
def create_decision_version(
    decision_id: str,
    payload: CreateDecisionVersionRequest | None = None,
    repo: DecisionRepository = Depends(get_decision_repository),
    version_repo: DecisionVersionRepository = Depends(get_decision_version_repository),
) -> DecisionVersionResponse:
    existing = repo.get_by_id(decision_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    description = payload.description if payload is not None else None
    version = version_repo.create_version(
        decision=existing,
        description=description,
    )
    return DecisionVersionResponse.from_domain(version)


@router.get(
    "/{decision_id}/versions",
    response_model=list[DecisionVersionResponse],
    summary="List decision versions",
    description="Returns all historical versions for a specific business decision sorted by version_number ascending.",
)
def list_decision_versions(
    decision_id: str,
    repo: DecisionRepository = Depends(get_decision_repository),
    version_repo: DecisionVersionRepository = Depends(get_decision_version_repository),
) -> list[DecisionVersionResponse]:
    existing = repo.get_by_id(decision_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    versions = version_repo.get_by_decision_id(decision_id)
    return [DecisionVersionResponse.from_domain(v) for v in versions]


@router.get(
    "/{decision_id}/versions/{version_number}",
    response_model=DecisionVersionResponse,
    summary="Get a specific decision version",
    description="Retrieves a historical version by version number for an operational decision.",
)
def get_decision_version_by_number(
    decision_id: str,
    version_number: int,
    repo: DecisionRepository = Depends(get_decision_repository),
    version_repo: DecisionVersionRepository = Depends(get_decision_version_repository),
) -> DecisionVersionResponse:
    existing = repo.get_by_id(decision_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )
    version = version_repo.get_by_version_number(decision_id, version_number)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version '{version_number}' for decision '{decision_id}' not found",
        )
    return DecisionVersionResponse.from_domain(version)


@router.post(
    "/{decision_id}/graph",
    response_model=DecisionGraphResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or build decision graph",
    description="Creates or builds the foundational graph representation connecting a decision and its related information.",
)
def create_decision_graph(
    decision_id: str,
    payload: CreateDecisionGraphRequest | None = None,
    repo: DecisionRepository = Depends(get_decision_repository),
    graph_repo: DecisionGraphRepository = Depends(get_decision_graph_repository),
) -> DecisionGraphResponse:
    decision = repo.get_by_id(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )

    existing_graph = graph_repo.get_by_decision_id(decision_id)
    if existing_graph is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Decision graph for decision '{decision_id}' already exists",
        )

    try:
        # If payload is empty or nodes & edges are omitted, build baseline default graph
        if payload is None or (payload.nodes is None and payload.edges is None):
            graph = graph_repo.build_default_graph(decision=decision)
        else:
            norm_dec_id = decision.id
            domain_nodes: list[GraphNode] = []
            if payload.nodes is not None:
                for n_req in payload.nodes:
                    nid = n_req.id if n_req.id is not None else graph_repo.generate_node_id()
                    dec_id = n_req.decision_id if n_req.decision_id is not None else norm_dec_id
                    domain_nodes.append(
                        GraphNode(
                            id=nid,
                            node_type=n_req.node_type,
                            decision_id=dec_id,
                            label=n_req.label,
                            metadata=n_req.metadata,
                        )
                    )

            domain_edges: list[GraphEdge] = []
            if payload.edges is not None:
                for e_req in payload.edges:
                    eid = e_req.id if e_req.id is not None else graph_repo.generate_edge_id()
                    dec_id = e_req.decision_id if e_req.decision_id is not None else norm_dec_id
                    domain_edges.append(
                        GraphEdge(
                            id=eid,
                            source_id=e_req.source_id,
                            target_id=e_req.target_id,
                            relationship_type=e_req.relationship_type,
                            decision_id=dec_id,
                            metadata=e_req.metadata,
                        )
                    )

            graph = graph_repo.create_graph(
                decision_id=norm_dec_id,
                nodes=domain_nodes,
                edges=domain_edges,
            )
    except (GraphIntegrityError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except DuplicateDecisionGraphError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


    return DecisionGraphResponse.from_domain(graph)


@router.get(
    "/{decision_id}/graph",
    response_model=DecisionGraphResponse,
    summary="Get decision graph",
    description="Retrieves the decision graph connecting a business decision and its related information.",
)
def get_decision_graph(
    decision_id: str,
    repo: DecisionRepository = Depends(get_decision_repository),
    graph_repo: DecisionGraphRepository = Depends(get_decision_graph_repository),
) -> DecisionGraphResponse:
    decision = repo.get_by_id(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found",
        )

    graph = graph_repo.get_by_decision_id(decision_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision graph for decision '{decision_id}' not found",
        )

    return DecisionGraphResponse.from_domain(graph)


@router.post(
    "/{decision_id}/actions",
    response_model=CandidateActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create candidate action",
    description="Creates a strongly typed candidate action representing an operational alternative for an existing decision.",
)
def create_candidate_action(
    decision_id: str,
    payload: CreateCandidateActionRequest,
    action_service: CandidateActionService = Depends(get_candidate_action_service),
) -> CandidateActionResponse:
    try:
        action = action_service.create_candidate_action(
            decision_id=decision_id,
            action_type=payload.action_type,
            parameters=payload.parameters,
            description=payload.description,
        )
    except DecisionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateCandidateActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (IneligibleSupplierError, SupplierNotFoundError, ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return CandidateActionResponse.from_domain(action)


@router.get(
    "/{decision_id}/actions",
    response_model=list[CandidateActionResponse],
    summary="List candidate actions",
    description="Retrieves all candidate actions associated with a specific operational decision in deterministic order.",
)
def list_candidate_actions(
    decision_id: str,
    action_service: CandidateActionService = Depends(get_candidate_action_service),
) -> list[CandidateActionResponse]:
    try:
        actions = action_service.list_candidate_actions(decision_id=decision_id)
    except DecisionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [CandidateActionResponse.from_domain(a) for a in actions]


# Day 19 Action Evaluation Endpoints


@router.post(
    "/{decision_id}/actions/evaluate",
    response_model=DecisionEvaluationReportResponse,
    summary="Evaluate all candidate actions for a decision",
    description="Evaluates all candidate actions associated with a business decision across standard dimensions without selecting a recommendation.",
)
def evaluate_decision_candidate_actions(
    decision_id: str,
    payload: EvaluateDecisionActionsRequest | None = None,
    service: ActionEvaluationService = Depends(get_action_evaluation_service),
) -> DecisionEvaluationReportResponse:
    req = payload or EvaluateDecisionActionsRequest()
    try:
        report = service.evaluate_decision_actions(
            decision_id=decision_id,
            policy_type=req.policy_type,
            target_stock=req.target_stock,
            enforce_reorder_trigger=req.enforce_reorder_trigger,
            record_to_graph=req.record_to_graph,
        )
        return DecisionEvaluationReportResponse.from_domain(report)
    except (DecisionNotFoundError, EvalDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingEvaluationDataError, IneligibleSupplierError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/actions/evaluate",
    response_model=DecisionEvaluationReportResponse,
    summary="Evaluate all candidate actions for a decision via query parameters",
    description="Query-parameter endpoint for evaluating all candidate actions associated with a decision.",
)
def get_evaluate_decision_candidate_actions(
    decision_id: str,
    policy_type: ReplenishmentPolicyType = Query(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    ),
    target_stock: int | None = Query(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    ),
    enforce_reorder_trigger: bool = Query(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    ),
    record_to_graph: bool = Query(
        default=False,
        description="When True, attaches evaluation RESULT nodes to the Decision Graph",
    ),
    service: ActionEvaluationService = Depends(get_action_evaluation_service),
) -> DecisionEvaluationReportResponse:
    try:
        report = service.evaluate_decision_actions(
            decision_id=decision_id,
            policy_type=policy_type,
            target_stock=target_stock,
            enforce_reorder_trigger=enforce_reorder_trigger,
            record_to_graph=record_to_graph,
        )
        return DecisionEvaluationReportResponse.from_domain(report)
    except (DecisionNotFoundError, EvalDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingEvaluationDataError, IneligibleSupplierError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{decision_id}/actions/{action_id}/evaluate",
    response_model=ActionEvaluationResponse,
    summary="Evaluate an individual candidate action",
    description="Deterministically evaluates an individual candidate action across stockout exposure, replenishment impact, supplier parameters, and defensible costs.",
)
def evaluate_individual_action(
    decision_id: str,
    action_id: str,
    payload: EvaluateActionRequest | None = None,
    service: ActionEvaluationService = Depends(get_action_evaluation_service),
) -> ActionEvaluationResponse:
    req = payload or EvaluateActionRequest()
    try:
        result = service.evaluate_action(
            decision_id=decision_id,
            action_id=action_id,
            policy_type=req.policy_type,
            target_stock=req.target_stock,
            enforce_reorder_trigger=req.enforce_reorder_trigger,
            record_to_graph=req.record_to_graph,
        )
        return ActionEvaluationResponse.from_domain(result)
    except (
        DecisionNotFoundError,
        EvalDecisionNotFoundError,
        CandidateActionNotFoundError,
        EvalActionNotFoundError,
        SupplierNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingEvaluationDataError, IneligibleSupplierError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/actions/{action_id}/evaluate",
    response_model=ActionEvaluationResponse,
    summary="Evaluate an individual candidate action via query parameters",
    description="Query-parameter endpoint for evaluating an individual candidate action.",
)
def get_evaluate_individual_action(
    decision_id: str,
    action_id: str,
    policy_type: ReplenishmentPolicyType = Query(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    ),
    target_stock: int | None = Query(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    ),
    enforce_reorder_trigger: bool = Query(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    ),
    record_to_graph: bool = Query(
        default=False,
        description="When True, attaches evaluation RESULT node to the Decision Graph",
    ),
    service: ActionEvaluationService = Depends(get_action_evaluation_service),
) -> ActionEvaluationResponse:
    try:
        result = service.evaluate_action(
            decision_id=decision_id,
            action_id=action_id,
            policy_type=policy_type,
            target_stock=target_stock,
            enforce_reorder_trigger=enforce_reorder_trigger,
            record_to_graph=record_to_graph,
        )
        return ActionEvaluationResponse.from_domain(result)
    except (
        DecisionNotFoundError,
        EvalDecisionNotFoundError,
        CandidateActionNotFoundError,
        EvalActionNotFoundError,
        SupplierNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingEvaluationDataError, IneligibleSupplierError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{decision_id}/evaluation",
    response_model=DecisionEvaluationReportResponse,
    summary="Evaluate all candidate actions for a decision (canonical alias)",
    description="Canonical alias for evaluating all candidate actions of a decision.",
    include_in_schema=False,
)
def evaluate_decision_alias_post(
    decision_id: str,
    payload: EvaluateDecisionActionsRequest | None = None,
    service: ActionEvaluationService = Depends(get_action_evaluation_service),
) -> DecisionEvaluationReportResponse:
    return evaluate_decision_candidate_actions(decision_id=decision_id, payload=payload, service=service)


@router.get(
    "/{decision_id}/evaluation",
    response_model=DecisionEvaluationReportResponse,
    summary="Evaluate all candidate actions for a decision via query params (canonical alias)",
    description="Canonical query-parameter alias for evaluating all candidate actions of a decision.",
    include_in_schema=False,
)
def evaluate_decision_alias_get(
    decision_id: str,
    policy_type: ReplenishmentPolicyType = Query(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    ),
    target_stock: int | None = Query(default=None, ge=0),
    enforce_reorder_trigger: bool = Query(default=True),
    record_to_graph: bool = Query(default=False),
    service: ActionEvaluationService = Depends(get_action_evaluation_service),
) -> DecisionEvaluationReportResponse:
    return get_evaluate_decision_candidate_actions(
        decision_id=decision_id,
        policy_type=policy_type,
        target_stock=target_stock,
        enforce_reorder_trigger=enforce_reorder_trigger,
        record_to_graph=record_to_graph,
        service=service,
    )


@router.get(
    "/{decision_id}/actions/{action_id}",

    response_model=CandidateActionResponse,
    summary="Get candidate action by ID",
    description="Retrieves a specific candidate action belonging to the specified business decision.",
)
def get_candidate_action_by_id(
    decision_id: str,
    action_id: str,
    action_service: CandidateActionService = Depends(get_candidate_action_service),
) -> CandidateActionResponse:
    try:
        action = action_service.get_candidate_action(
            decision_id=decision_id,
            action_id=action_id,
        )
    except (DecisionNotFoundError, CandidateActionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return CandidateActionResponse.from_domain(action)


@router.post(
    "/{decision_id}/replenishment",
    response_model=ReplenishmentResponse,
    summary="Calculate replenishment for a decision",
    description="Deterministically calculates replenishment order quantity under an explicit policy for a decision's product and warehouse.",
)
def calculate_decision_replenishment(
    decision_id: str,
    payload: DecisionReplenishmentRequest | None = None,
    service: ReplenishmentService = Depends(get_decision_replenishment_service),
) -> ReplenishmentResponse:
    req = payload or DecisionReplenishmentRequest()
    try:
        result = service.calculate_for_decision(
            decision_id=decision_id,
            policy_type=req.policy_type,
            target_stock=req.target_stock,
            supplier_id=req.supplier_id,
            enforce_reorder_trigger=req.enforce_reorder_trigger,
        )
        return ReplenishmentResponse.from_domain(result)
    except (DecisionNotFoundError, ReplenishmentDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WarehouseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingReplenishmentDataError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/replenishment",
    response_model=ReplenishmentResponse,
    summary="Calculate replenishment for a decision via query parameters",
    description="Query-parameter endpoint for calculating deterministic replenishment order quantity for a decision.",
)
def get_decision_replenishment(
    decision_id: str,
    policy_type: ReplenishmentPolicyType = Query(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to apply",
    ),
    target_stock: int | None = Query(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    ),
    supplier_id: str | None = Query(
        default=None,
        description="Optional supplier ID override for lead time demand calculation",
    ),
    enforce_reorder_trigger: bool = Query(
        default=True,
        description="If True, only replenishes when available_quantity <= reorder_point",
    ),
    service: ReplenishmentService = Depends(get_decision_replenishment_service),
) -> ReplenishmentResponse:
    try:
        result = service.calculate_for_decision(
            decision_id=decision_id,
            policy_type=policy_type,
            target_stock=target_stock,
            supplier_id=supplier_id,
            enforce_reorder_trigger=enforce_reorder_trigger,
        )
        return ReplenishmentResponse.from_domain(result)
    except (DecisionNotFoundError, ReplenishmentDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except WarehouseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingReplenishmentDataError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{decision_id}/stockout-risk",
    response_model=StockoutRiskResponse,
    summary="Calculate stockout risk for a decision",
    description="Deterministically calculates stockout risk and lead-time exposure for a decision's product and warehouse.",
)
def calculate_decision_stockout_risk(
    decision_id: str,
    payload: DecisionStockoutRiskRequest | None = None,
    service: StockoutRiskService = Depends(get_decision_stockout_risk_service),
) -> StockoutRiskResponse:
    req = payload or DecisionStockoutRiskRequest()
    try:
        result = service.calculate_for_decision(
            decision_id=decision_id,
            model_type=req.model_type,
            supplier_id=req.supplier_id,
        )
        return StockoutRiskResponse.from_domain(result)
    except (DecisionNotFoundError, StockoutRiskDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ProductNotFoundError, RiskProductNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (WarehouseNotFoundError, RiskWarehouseNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingStockoutRiskDataError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/stockout-risk",
    response_model=StockoutRiskResponse,
    summary="Calculate stockout risk for a decision via query parameters",
    description="Query-parameter endpoint for calculating deterministic stockout risk and lead-time exposure for a decision.",
)
def get_decision_stockout_risk(
    decision_id: str,
    model_type: StockoutRiskModelType = Query(
        default=StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE,
        description="Deterministic stockout-risk calculation model to apply",
    ),
    supplier_id: str | None = Query(
        default=None,
        description="Optional supplier ID override for lead-time resolution",
    ),
    service: StockoutRiskService = Depends(get_decision_stockout_risk_service),
) -> StockoutRiskResponse:
    try:
        result = service.calculate_for_decision(
            decision_id=decision_id,
            model_type=model_type,
            supplier_id=supplier_id,
        )
        return StockoutRiskResponse.from_domain(result)
    except (DecisionNotFoundError, StockoutRiskDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ProductNotFoundError, RiskProductNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (WarehouseNotFoundError, RiskWarehouseNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingStockoutRiskDataError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# Day 20 Recommendation Engine Endpoints


@router.post(
    "/{decision_id}/recommendation",
    response_model=RecommendationResponse,
    summary="Generate deterministic recommendation for a decision",
    description="Evaluates all candidate actions and deterministically selects the optimal recommendation via Lexicographic Operational Dominance.",
)
def generate_decision_recommendation(
    decision_id: str,
    payload: GenerateRecommendationRequest | None = None,
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    req = payload or GenerateRecommendationRequest()
    try:
        rec = service.generate_recommendation(
            decision_id=decision_id,
            policy_type=req.policy_type,
            target_stock=req.target_stock,
            enforce_reorder_trigger=req.enforce_reorder_trigger,
            record_to_graph=req.record_to_graph,
        )
        return RecommendationResponse.from_domain(rec)
    except (DecisionNotFoundError, RecDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingEvaluationDataError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/recommendation",
    response_model=RecommendationResponse,
    summary="Get or generate recommendation for a decision via query parameters",
    description="Retrieves the latest recommendation or generates one using specified query parameters.",
)
def get_decision_recommendation(
    decision_id: str,
    policy_type: ReplenishmentPolicyType = Query(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    ),
    target_stock: int | None = Query(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    ),
    enforce_reorder_trigger: bool = Query(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    ),
    record_to_graph: bool = Query(
        default=False,
        description="When True, attaches recommendation RESULT node to the Decision Graph",
    ),
    recompute: bool = Query(
        default=False,
        description="When True, forces re-evaluating and generating a new recommendation",
    ),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    try:
        if not recompute:
            try:
                rec = service.get_latest_recommendation(decision_id=decision_id)
                return RecommendationResponse.from_domain(rec)
            except RecommendationNotFoundError:
                pass

        rec = service.generate_recommendation(
            decision_id=decision_id,
            policy_type=policy_type,
            target_stock=target_stock,
            enforce_reorder_trigger=enforce_reorder_trigger,
            record_to_graph=record_to_graph,
        )
        return RecommendationResponse.from_domain(rec)
    except (DecisionNotFoundError, RecDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (MissingEvaluationDataError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# Day 21 Hard-Constraint Validation Endpoints

@router.post(
    "/{decision_id}/validate",
    response_model=DecisionValidationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate candidate actions for a decision against hard constraints",
    description="Evaluates all (or specified subset of) candidate actions against explicitly defined operational hard constraints without mutating inventory or executing actions.",
)
def validate_decision_actions_endpoint(
    decision_id: str,
    payload: ValidateDecisionRequest | None = None,
    service: ValidationService = Depends(get_validation_service),
) -> DecisionValidationReportResponse:
    req = payload or ValidateDecisionRequest()
    try:
        configured_constraints = None
        if req.constraints is not None:
            configured_constraints = [c.to_domain() for c in req.constraints]

        report = service.validate_decision_actions(
            decision_id=decision_id,
            action_ids=req.action_ids,
            configured_constraints=configured_constraints,
            record_to_graph=req.record_to_graph,
        )
        return DecisionValidationReportResponse.from_domain(report)
    except (
        DecisionNotFoundError,
        ValDecisionNotFoundError,
        CandidateActionNotFoundError,
        ValActionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/validation",
    response_model=DecisionValidationReportResponse,
    summary="Get latest validation report or revalidate a decision",
    description="Retrieves the latest stored validation report for the decision or executes a revalidation run.",
)
def get_decision_validation_endpoint(
    decision_id: str,
    recompute: bool = Query(
        default=False,
        description="When True, forces running a new hard-constraint validation run",
    ),
    record_to_graph: bool = Query(
        default=False,
        description="When True, attaches VALIDATION node to the Decision Graph",
    ),
    service: ValidationService = Depends(get_validation_service),
) -> DecisionValidationReportResponse:
    try:
        if not recompute:
            report = service.get_latest_validation(decision_id=decision_id)
            if report is not None:
                return DecisionValidationReportResponse.from_domain(report)

        report = service.validate_decision_actions(
            decision_id=decision_id,
            record_to_graph=record_to_graph,
        )
        return DecisionValidationReportResponse.from_domain(report)
    except (DecisionNotFoundError, ValDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{decision_id}/actions/{action_id}/validate",
    response_model=ActionValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate an individual candidate action against hard constraints",
    description="Evaluates an individual candidate action against operational hard constraints.",
)
def validate_candidate_action_endpoint(
    decision_id: str,
    action_id: str,
    payload: ValidateActionRequest | None = None,
    service: ValidationService = Depends(get_validation_service),
) -> ActionValidationResponse:
    req = payload or ValidateActionRequest()
    try:
        configured_constraints = None
        if req.constraints is not None:
            configured_constraints = [c.to_domain() for c in req.constraints]

        result = service.validate_action(
            decision_id=decision_id,
            action_id=action_id,
            configured_constraints=configured_constraints,
        )
        return ActionValidationResponse.from_domain(result)
    except (
        DecisionNotFoundError,
        ValDecisionNotFoundError,
        CandidateActionNotFoundError,
        ValActionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Day 22: Decision Evidence Model Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{decision_id}/evidence",
    response_model=DecisionEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an evidence item for a decision",
    description="Explicitly records an observed fact, explicit assumption, or calculated output supporting a decision.",
)
def create_decision_evidence_endpoint(
    decision_id: str,
    payload: CreateEvidenceRequest,
    service: EvidenceService = Depends(get_evidence_service),
) -> DecisionEvidenceResponse:
    try:
        ev = service.create_evidence(
            decision_id=decision_id,
            evidence_type=payload.evidence_type,
            category=payload.category,
            description=payload.description,
            id=payload.id,
            value=payload.value,
            unit=payload.unit,
            source=payload.source,
            is_probability=payload.is_probability,
            action_id=payload.action_id,
            version_id=payload.version_id,
            metadata=payload.metadata,
        )
        return DecisionEvidenceResponse.from_domain(ev)
    except (
        DecisionNotFoundError,
        EvDecisionNotFoundError,
        CandidateActionNotFoundError,
        EvActionNotFoundError,
        EvVersionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (DuplicateEvidenceError,) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (CrossDecisionIsolationError, InvalidEvidencePayloadError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/evidence",
    response_model=list[DecisionEvidenceResponse],
    summary="List evidence items for a decision",
    description="Retrieves deterministically sorted evidence items supporting a decision, with optional filtering.",
)
def list_decision_evidence_endpoint(
    decision_id: str,
    evidence_type: EvidenceType | None = Query(default=None, description="Filter by evidence nature (FACT, ASSUMPTION, CALCULATION)"),
    category: EvidenceCategory | None = Query(default=None, description="Filter by operational domain category"),
    action_id: str | None = Query(default=None, description="Filter by candidate action association"),
    version_id: str | None = Query(default=None, description="Filter by decision version association"),
    service: EvidenceService = Depends(get_evidence_service),
) -> list[DecisionEvidenceResponse]:
    try:
        items = service.list_evidence(
            decision_id=decision_id,
            evidence_type=evidence_type,
            category=category,
            action_id=action_id,
            version_id=version_id,
        )
        return [DecisionEvidenceResponse.from_domain(item) for item in items]
    except (DecisionNotFoundError, EvDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/evidence/{evidence_id}",
    response_model=DecisionEvidenceResponse,
    summary="Get a specific decision evidence item",
    description="Retrieves an individual evidence item by ID for the specified decision.",
)
def get_decision_evidence_item_endpoint(
    decision_id: str,
    evidence_id: str,
    service: EvidenceService = Depends(get_evidence_service),
) -> DecisionEvidenceResponse:
    try:
        ev = service.get_evidence(decision_id=decision_id, evidence_id=evidence_id)
        return DecisionEvidenceResponse.from_domain(ev)
    except (DecisionNotFoundError, EvDecisionNotFoundError, EvidenceNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{decision_id}/assumptions",
    response_model=DecisionAssumptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an explicit assumption for a decision",
    description="Records an explicit operational assumption, distinguishing it from observed facts and calculated outputs.",
)
def create_decision_assumption_endpoint(
    decision_id: str,
    payload: CreateAssumptionRequest,
    service: EvidenceService = Depends(get_evidence_service),
) -> DecisionAssumptionResponse:
    try:
        asm = service.create_assumption(
            decision_id=decision_id,
            category=payload.category,
            statement=payload.statement,
            id=payload.id,
            assumed_value=payload.assumed_value,
            rationale=payload.rationale,
            source=payload.source,
            action_id=payload.action_id,
            version_id=payload.version_id,
            metadata=payload.metadata,
        )
        return DecisionAssumptionResponse.from_domain(asm)
    except (
        DecisionNotFoundError,
        EvDecisionNotFoundError,
        CandidateActionNotFoundError,
        EvActionNotFoundError,
        EvVersionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (DuplicateAssumptionError,) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (CrossDecisionIsolationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/assumptions",
    response_model=list[DecisionAssumptionResponse],
    summary="List explicit assumptions for a decision",
    description="Retrieves deterministically sorted explicit assumptions supporting a decision.",
)
def list_decision_assumptions_endpoint(
    decision_id: str,
    category: EvidenceCategory | None = Query(default=None, description="Filter by operational domain category"),
    action_id: str | None = Query(default=None, description="Filter by candidate action association"),
    version_id: str | None = Query(default=None, description="Filter by decision version association"),
    service: EvidenceService = Depends(get_evidence_service),
) -> list[DecisionAssumptionResponse]:
    try:
        items = service.list_assumptions(
            decision_id=decision_id,
            category=category,
            action_id=action_id,
            version_id=version_id,
        )
        return [DecisionAssumptionResponse.from_domain(asm) for asm in items]
    except (DecisionNotFoundError, EvDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/assumptions/{assumption_id}",
    response_model=DecisionAssumptionResponse,
    summary="Get a specific explicit assumption",
    description="Retrieves an individual explicit assumption by ID for the specified decision.",
)
def get_decision_assumption_item_endpoint(
    decision_id: str,
    assumption_id: str,
    service: EvidenceService = Depends(get_evidence_service),
) -> DecisionAssumptionResponse:
    try:
        asm = service.get_assumption(decision_id=decision_id, assumption_id=assumption_id)
        return DecisionAssumptionResponse.from_domain(asm)
    except (DecisionNotFoundError, EvDecisionNotFoundError, AssumptionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/evidence-sheet",
    response_model=DecisionEvidenceSheetResponse,
    summary="Get consolidated evidence sheet for a decision",
    description="Retrieves or compiles the full consolidated evidence sheet for a decision, including facts, assumptions, and calculations.",
)
def get_decision_evidence_sheet_endpoint(
    decision_id: str,
    auto_compile: bool = Query(default=True, description="When True, automatically compiles sheet from operational context if not already stored"),
    recompute: bool = Query(default=False, description="When True, forces fresh re-compilation across all operational domains"),
    service: EvidenceService = Depends(get_evidence_service),
) -> DecisionEvidenceSheetResponse:
    try:
        sheet = service.get_evidence_sheet(
            decision_id=decision_id,
            auto_compile=auto_compile,
            recompute=recompute,
        )
        return DecisionEvidenceSheetResponse.from_domain(sheet)
    except (DecisionNotFoundError, EvDecisionNotFoundError, EvidenceNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{decision_id}/evidence-sheet/compile",
    response_model=DecisionEvidenceSheetResponse,
    summary="Compile and record decision evidence sheet",
    description="Explicitly triggers operational evidence synthesis and stores the resulting evidence sheet and items.",
)
def compile_decision_evidence_sheet_endpoint(
    decision_id: str,
    service: EvidenceService = Depends(get_evidence_service),
) -> DecisionEvidenceSheetResponse:
    try:
        sheet = service.compile_decision_evidence(decision_id=decision_id, record_to_repository=True)
        return DecisionEvidenceSheetResponse.from_domain(sheet)
    except (DecisionNotFoundError, EvDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Day 23: Decision Provenance Engine Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{decision_id}/provenance/capture",
    response_model=DecisionProvenanceTraceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture decision provenance trace",
    description="Executes deterministic evaluation and captures an auditable Input -> Rule -> Calculation -> Result trace.",
)
def capture_decision_provenance_endpoint(
    decision_id: str,
    payload: CaptureProvenanceRequest | None = None,
    service: ProvenanceService = Depends(get_provenance_service),
) -> DecisionProvenanceTraceResponse:
    req = payload or CaptureProvenanceRequest()
    try:
        trace = service.capture_decision_provenance(
            decision_id=decision_id,
            version_id=req.version_id,
            policy_type=req.policy_type,
            target_stock=req.target_stock,
            enforce_reorder_trigger=req.enforce_reorder_trigger,
            record_to_graph=req.record_to_graph,
            trigger=req.trigger,
            metadata=req.metadata,
        )
        return DecisionProvenanceTraceResponse.from_domain(trace)
    except (
        DecisionNotFoundError,
        PrvDecisionNotFoundError,
        PrvVersionNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (PrvCrossDecisionIsolationError, PrvInvalidPayloadError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/provenance",
    response_model=DecisionProvenanceTraceResponse,
    summary="Get latest decision provenance trace",
    description="Retrieves the most recent provenance trace for a business decision, optionally filtered by version.",
)
def get_latest_decision_provenance_endpoint(
    decision_id: str,
    version_id: str | None = Query(default=None, description="Optional decision version filter"),
    service: ProvenanceService = Depends(get_provenance_service),
) -> DecisionProvenanceTraceResponse:
    try:
        trace = service.get_latest_provenance(decision_id=decision_id, version_id=version_id)
        if trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No provenance trace found for decision '{decision_id}'",
            )
        return DecisionProvenanceTraceResponse.from_domain(trace)
    except (DecisionNotFoundError, PrvDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/provenance/traces",
    response_model=list[DecisionProvenanceTraceResponse],
    summary="List decision provenance traces",
    description="Retrieves all provenance traces for a decision, sorted chronologically descending.",
)
def list_decision_provenance_traces_endpoint(
    decision_id: str,
    version_id: str | None = Query(default=None, description="Optional decision version filter"),
    service: ProvenanceService = Depends(get_provenance_service),
) -> list[DecisionProvenanceTraceResponse]:
    try:
        traces = service.list_provenance_traces(decision_id=decision_id, version_id=version_id)
        return [DecisionProvenanceTraceResponse.from_domain(t) for t in traces]
    except (DecisionNotFoundError, PrvDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/provenance/traces/{trace_id}",
    response_model=DecisionProvenanceTraceResponse,
    summary="Get specific decision provenance trace",
    description="Retrieves an individual provenance trace by ID, strictly enforcing decision isolation.",
)
def get_decision_provenance_trace_endpoint(
    decision_id: str,
    trace_id: str,
    service: ProvenanceService = Depends(get_provenance_service),
) -> DecisionProvenanceTraceResponse:
    try:
        trace = service.get_provenance_trace(decision_id=decision_id, trace_id=trace_id)
        return DecisionProvenanceTraceResponse.from_domain(trace)
    except (
        DecisionNotFoundError,
        PrvDecisionNotFoundError,
        ProvenanceTraceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (PrvCrossDecisionIsolationError,) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/provenance/traces/{trace_id}/derivation",
    response_model=ProvenanceDerivationResponse,
    summary="Get derivation path for a result step",
    description="Extracts the Input -> Rule -> Calculation -> Result derivation chain for a given result in the trace.",
)
def get_decision_provenance_derivation_endpoint(
    decision_id: str,
    trace_id: str,
    result_id: str | None = Query(default=None, description="Optional result step identifier (defaults to primary recommendation)"),
    service: ProvenanceService = Depends(get_provenance_service),
) -> ProvenanceDerivationResponse:
    try:
        chain = service.get_derivation_path(decision_id=decision_id, trace_id=trace_id, result_id=result_id)
        return ProvenanceDerivationResponse.from_domain(chain)
    except (
        DecisionNotFoundError,
        PrvDecisionNotFoundError,
        ProvenanceTraceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (PrvCrossDecisionIsolationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Day 24: Decision Replay Engine Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{decision_id}/replay",
    response_model=DecisionReplayResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Replay a previously executed decision",
    description="Reconstructs historical decision execution using recorded inputs and rules, recomputes outcomes, and compares with original result.",
)
def replay_decision_endpoint(
    decision_id: str,
    payload: ReplayDecisionRequest | None = None,
    service: DecisionReplayService = Depends(get_replay_service),
) -> DecisionReplayResponse:
    req = payload or ReplayDecisionRequest()
    try:
        record = service.replay_decision(
            decision_id=decision_id,
            trace_id=req.trace_id,
            version_id=req.version_id,
            record_to_graph=req.record_to_graph,
            metadata=req.metadata,
        )
        return DecisionReplayResponse.from_domain(record)
    except (
        DecisionNotFoundError,
        RplDecisionNotFoundError,
        RplVersionNotFoundError,
        RplProvenanceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (RplCrossDecisionIsolationError, RplInvalidRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/replay/latest",
    response_model=DecisionReplayResponse,
    summary="Get latest decision replay record",
    description="Retrieves the most recent replay record for a decision, optionally filtered by version.",
)
def get_latest_decision_replay_endpoint(
    decision_id: str,
    version_id: str | None = Query(default=None, description="Optional decision version filter"),
    service: DecisionReplayService = Depends(get_replay_service),
) -> DecisionReplayResponse:
    try:
        record = service.get_latest_replay(decision_id=decision_id, version_id=version_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No replay record found for decision '{decision_id}'",
            )
        return DecisionReplayResponse.from_domain(record)
    except (DecisionNotFoundError, RplDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/replay/records",
    response_model=list[DecisionReplayResponse],
    summary="List decision replay records",
    description="Retrieves all replay execution records for a decision, sorted chronologically descending.",
)
def list_decision_replay_records_endpoint(
    decision_id: str,
    version_id: str | None = Query(default=None, description="Optional decision version filter"),
    service: DecisionReplayService = Depends(get_replay_service),
) -> list[DecisionReplayResponse]:
    try:
        records = service.list_replay_records(decision_id=decision_id, version_id=version_id)
        return [DecisionReplayResponse.from_domain(r) for r in records]
    except (DecisionNotFoundError, RplDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/replay/records/{replay_id}",
    response_model=DecisionReplayResponse,
    summary="Get specific decision replay record",
    description="Retrieves an individual replay record by ID, strictly enforcing decision isolation.",
)
def get_decision_replay_record_endpoint(
    decision_id: str,
    replay_id: str,
    service: DecisionReplayService = Depends(get_replay_service),
) -> DecisionReplayResponse:
    try:
        record = service.get_replay_record(decision_id=decision_id, replay_id=replay_id)
        return DecisionReplayResponse.from_domain(record)
    except (
        DecisionNotFoundError,
        RplDecisionNotFoundError,
        ReplayRecordNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (RplCrossDecisionIsolationError,) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Day 25: Decision Scenario Engine Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{decision_id}/scenarios",
    response_model=DecisionScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a what-if scenario for a decision",
    description="Recalculates decision outcomes under modified demand, lead-time, or cost assumptions and compares against baseline.",
)
def execute_scenario_endpoint(
    decision_id: str,
    payload: ExecuteScenarioRequest,
    service: ScenarioService = Depends(get_scenario_service),
) -> DecisionScenarioResponse:
    try:
        record = service.execute_scenario(
            decision_id=decision_id,
            overrides=payload.overrides.to_domain(),
            version_id=payload.version_id,
            trace_id=payload.trace_id,
            name=payload.name,
            record_to_graph=payload.record_to_graph,
            metadata=payload.metadata,
        )
        return DecisionScenarioResponse.from_domain(record)
    except (
        DecisionNotFoundError,
        ScnDecisionNotFoundError,
        ScnVersionNotFoundError,
        ScnProvenanceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (ScnCrossDecisionIsolationError, ScnInvalidRequestError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/scenarios/latest",
    response_model=DecisionScenarioResponse,
    summary="Get latest decision scenario record",
    description="Retrieves the most recent scenario record for a decision, optionally filtered by version.",
)
def get_latest_decision_scenario_endpoint(
    decision_id: str,
    version_id: str | None = Query(default=None, description="Optional decision version filter"),
    service: ScenarioService = Depends(get_scenario_service),
) -> DecisionScenarioResponse:
    try:
        record = service.get_latest_scenario(decision_id=decision_id, version_id=version_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No scenario record found for decision '{decision_id}'",
            )
        return DecisionScenarioResponse.from_domain(record)
    except (DecisionNotFoundError, ScnDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/scenarios",
    response_model=list[DecisionScenarioResponse],
    summary="List decision scenario records",
    description="Retrieves all scenario execution records for a decision, sorted chronologically descending.",
)
def list_decision_scenarios_endpoint(
    decision_id: str,
    version_id: str | None = Query(default=None, description="Optional decision version filter"),
    service: ScenarioService = Depends(get_scenario_service),
) -> list[DecisionScenarioResponse]:
    try:
        records = service.list_scenario_records(decision_id=decision_id, version_id=version_id)
        return [DecisionScenarioResponse.from_domain(r) for r in records]
    except (DecisionNotFoundError, ScnDecisionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/scenarios/{scenario_id}",
    response_model=DecisionScenarioResponse,
    summary="Get specific decision scenario record",
    description="Retrieves an individual scenario record by ID, strictly enforcing decision isolation.",
)
def get_decision_scenario_record_endpoint(
    decision_id: str,
    scenario_id: str,
    service: ScenarioService = Depends(get_scenario_service),
) -> DecisionScenarioResponse:
    try:
        record = service.get_scenario_record(decision_id=decision_id, scenario_id=scenario_id)
        return DecisionScenarioResponse.from_domain(record)
    except (
        DecisionNotFoundError,
        ScnDecisionNotFoundError,
        ScenarioRecordNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ScnCrossDecisionIsolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{decision_id}/scenarios/{scenario_id}/comparison",
    response_model=ScenarioComparisonResponse,
    summary="Get baseline-versus-scenario comparison",
    description="Retrieves structured baseline-versus-scenario comparison results for an executed scenario.",
)
def get_decision_scenario_comparison_endpoint(
    decision_id: str,
    scenario_id: str,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioComparisonResponse:
    try:
        comparison = service.get_scenario_comparison(decision_id=decision_id, scenario_id=scenario_id)
        return ScenarioComparisonResponse.from_domain(comparison)
    except (
        DecisionNotFoundError,
        ScnDecisionNotFoundError,
        ScenarioRecordNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ScnCrossDecisionIsolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc



