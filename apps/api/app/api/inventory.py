from __future__ import annotations

from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import (
    CalculateReplenishmentRequest,
    InventoryResponse,
    ReplenishmentPolicyType,
    ReplenishmentResponse,
)
from app.replenishment.service import (
    MissingReplenishmentDataError,
    ProductNotFoundError,
    ReplenishmentService,
    WarehouseNotFoundError,
)
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import SupplierRepository

router = APIRouter()


@lru_cache
def get_inventory_repository() -> InventoryRepository:
    """Dependency provider returning the singleton InventoryRepository instance."""
    return InventoryRepository()


@lru_cache
def get_replenishment_service() -> ReplenishmentService:
    """Dependency provider returning the singleton ReplenishmentService instance."""
    inv_repo = get_inventory_repository()
    shared_dataset = inv_repo.dataset
    demand_repo = DemandRepository(dataset=shared_dataset)
    supplier_repo = SupplierRepository(dataset=shared_dataset)
    return ReplenishmentService(
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=supplier_repo,
    )


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


@router.post(
    "/replenishment",
    response_model=ReplenishmentResponse,
    summary="Calculate replenishment order quantity",
    description="Deterministically calculates replenishment order quantity under an explicit policy for a product and warehouse.",
)
def calculate_replenishment(
    payload: CalculateReplenishmentRequest,
    service: ReplenishmentService = Depends(get_replenishment_service),
) -> ReplenishmentResponse:
    try:
        result = service.calculate_for_product_warehouse(
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
            policy_type=payload.policy_type,
            target_stock=payload.target_stock,
            supplier_id=payload.supplier_id,
            enforce_reorder_trigger=payload.enforce_reorder_trigger,
        )
        return ReplenishmentResponse.from_domain(result)
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
    "/replenishment",
    response_model=ReplenishmentResponse,
    summary="Calculate replenishment order quantity via query parameters",
    description="Query-parameter endpoint for calculating deterministic replenishment order quantity.",
)
def calculate_replenishment_by_query(
    product_id: str = Query(..., description="Unique product ID (e.g. 'prod-001')"),
    warehouse_id: str = Query(..., description="Unique warehouse ID (e.g. 'wh-001')"),
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
    service: ReplenishmentService = Depends(get_replenishment_service),
) -> ReplenishmentResponse:
    try:
        result = service.calculate_for_product_warehouse(
            product_id=product_id,
            warehouse_id=warehouse_id,
            policy_type=policy_type,
            target_stock=target_stock,
            supplier_id=supplier_id,
            enforce_reorder_trigger=enforce_reorder_trigger,
        )
        return ReplenishmentResponse.from_domain(result)
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
