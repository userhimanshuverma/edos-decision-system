from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import InventoryResponse
from app.repositories.inventory_repository import InventoryRepository

router = APIRouter()


@lru_cache
def get_inventory_repository() -> InventoryRepository:
    """Dependency provider returning the singleton InventoryRepository instance."""
    return InventoryRepository()


@router.get(
    "",
    response_model=list[InventoryResponse],
    summary="List all inventory records",
    description="Retrieve all operational inventory positions, with optional filtering by product or warehouse.",
)
def list_inventory(
    product_id: str | None = Query(default=None, description="Optional product ID filter"),
    warehouse_id: str | None = Query(default=None, description="Optional warehouse ID filter"),
    repo: InventoryRepository = Depends(get_inventory_repository),
) -> list[InventoryResponse]:
    records = repo.list_all(product_id=product_id, warehouse_id=warehouse_id)
    return [InventoryResponse.from_domain(inv) for inv in records]


@router.get(
    "/product/{product_id}",
    response_model=list[InventoryResponse],
    summary="Get inventory by product",
    description="Retrieve all inventory positions for a specific product ID across all warehouses.",
)
def get_inventory_by_product(
    product_id: str,
    repo: InventoryRepository = Depends(get_inventory_repository),
) -> list[InventoryResponse]:
    if not repo.product_exists(product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found",
        )
    records = repo.get_by_product_id(product_id)
    return [InventoryResponse.from_domain(inv) for inv in records]


@router.get(
    "/warehouse/{warehouse_id}",
    response_model=list[InventoryResponse],
    summary="Get inventory by warehouse",
    description="Retrieve all inventory positions located in a specific warehouse.",
)
def get_inventory_by_warehouse(
    warehouse_id: str,
    repo: InventoryRepository = Depends(get_inventory_repository),
) -> list[InventoryResponse]:
    if not repo.warehouse_exists(warehouse_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )
    records = repo.get_by_warehouse_id(warehouse_id)
    return [InventoryResponse.from_domain(inv) for inv in records]


@router.get(
    "/{inventory_id}",
    response_model=InventoryResponse,
    summary="Get inventory record by ID",
    description="Retrieve a single inventory position by its unique inventory ID.",
)
def get_inventory_by_id(
    inventory_id: str,
    repo: InventoryRepository = Depends(get_inventory_repository),
) -> InventoryResponse:
    record = repo.get_by_id(inventory_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory position '{inventory_id}' not found",
        )
    return InventoryResponse.from_domain(record)
