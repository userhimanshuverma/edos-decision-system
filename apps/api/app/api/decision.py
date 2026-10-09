from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.inventory import get_inventory_repository
from app.api.schemas import CreateDecisionRequest, DecisionResponse
from app.repositories.decision_repository import DecisionRepository
from app.repositories.inventory_repository import InventoryRepository

router = APIRouter()


@lru_cache
def get_decision_repository() -> DecisionRepository:
    """Dependency provider returning the singleton DecisionRepository instance."""
    return DecisionRepository()


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
