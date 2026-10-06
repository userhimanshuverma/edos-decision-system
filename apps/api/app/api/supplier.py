from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import SupplierResponse
from app.repositories.supplier_repository import SupplierRepository

router = APIRouter()


@lru_cache
def get_supplier_repository() -> SupplierRepository:
    """Dependency provider returning the singleton SupplierRepository instance."""
    return SupplierRepository()


@router.get(
    "",
    response_model=list[SupplierResponse],
    summary="List all suppliers",
    description="Retrieve all operational suppliers with their lead times, reliability scores, and contextual risk level.",
)
def list_suppliers(
    active_only: bool = Query(default=False, description="Filter to only return active suppliers"),
    repo: SupplierRepository = Depends(get_supplier_repository),
) -> list[SupplierResponse]:
    records = repo.list_all(active_only=active_only)
    return [SupplierResponse.from_domain(s) for s in records]


@router.get(
    "/code/{supplier_code}",
    response_model=SupplierResponse,
    summary="Get supplier by business code",
    description="Retrieve a single supplier by their business code (e.g. SUP-PAC-01).",
)
def get_supplier_by_code(
    supplier_code: str,
    repo: SupplierRepository = Depends(get_supplier_repository),
) -> SupplierResponse:
    record = repo.get_by_code(supplier_code)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier with code '{supplier_code}' not found",
        )
    return SupplierResponse.from_domain(record)


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Get supplier by ID",
    description="Retrieve a single supplier by their unique supplier ID (e.g. sup-001).",
)
def get_supplier_by_id(
    supplier_id: str,
    repo: SupplierRepository = Depends(get_supplier_repository),
) -> SupplierResponse:
    record = repo.get_by_id(supplier_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier '{supplier_id}' not found",
        )
    return SupplierResponse.from_domain(record)
