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
    DecisionResponse,
    DecisionVersionResponse,
    UpdateDecisionStatusRequest,
)
from app.candidate_actions.service import (
    CandidateActionNotFoundError,
    CandidateActionService,
    DecisionNotFoundError,
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
from app.repositories.inventory_repository import InventoryRepository

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



