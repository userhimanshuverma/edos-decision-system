from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import DecisionContextResponse
from app.context.engine import (
    ContextEngine,
    ProductNotFoundError,
    WarehouseNotFoundError,
)

router = APIRouter()


@lru_cache
def get_context_engine() -> ContextEngine:
    """Dependency provider returning the singleton ContextEngine instance."""
    return ContextEngine()


@router.get(
    "/product/{product_id}/warehouse/{warehouse_id}",
    response_model=DecisionContextResponse,
    summary="Get unified decision context",
    description="Synthesizes inventory, historical demand, and supplier intelligence into a single deterministic decision context.",
)
def get_decision_context(
    product_id: str,
    warehouse_id: str,
    supplier_id: str | None = Query(default=None, description="Optional explicit supplier ID override"),
    engine: ContextEngine = Depends(get_context_engine),
) -> DecisionContextResponse:
    try:
        context = engine.get_decision_context(
            product_id=product_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
        )
        return DecisionContextResponse.from_domain(context)
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


@router.get(
    "",
    response_model=DecisionContextResponse,
    summary="Get unified decision context via query parameters",
    description="Query-parameter alias for retrieving a unified decision context for a product and warehouse.",
)
def get_decision_context_by_query(
    product_id: str = Query(..., description="Unique product ID (e.g. 'prod-001')"),
    warehouse_id: str = Query(..., description="Unique warehouse ID (e.g. 'wh-001')"),
    supplier_id: str | None = Query(default=None, description="Optional explicit supplier ID override"),
    engine: ContextEngine = Depends(get_context_engine),
) -> DecisionContextResponse:
    try:
        context = engine.get_decision_context(
            product_id=product_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
        )
        return DecisionContextResponse.from_domain(context)
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
